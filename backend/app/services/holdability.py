"""Seniority-aware holdability prediction for PBS optimization.

Three levels of prediction accuracy:
  Level 1 — Seniority percentile heuristic (no historical data needed)
  Level 2 — Historical calibration (after 3+ months of award data)
  Level 3 — Base-wide award analysis (with APFA award files)

The holdability score modifies the CP-SAT *objective*, not constraints.
All pairings remain legally selectable — but the solver prefers pairings
the FA can realistically hold at her seniority.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Premium station sets (drive demand) ──────────────────────────────────

PREMIUM_INTL = {
    "NRT", "HND", "LHR", "CDG", "FCO", "BCN", "ATH", "AMS", "SIN", "HKG",
    "ICN", "BKK", "DUB", "VCE", "LIS", "MAD", "PRG", "ZRH", "MUC", "FRA",
    "GRU", "EZE", "SCL",
}

PREMIUM_DOMESTIC = {
    "SFO", "BOS", "HNL", "OGG", "SAN", "SNA", "SEA", "LAX", "AUS", "PDX",
    "SJU", "MIA", "TPA",
}

# ── Demand modifiers — how desirable is this pairing type? ───────────────
# >1.0 = senior FAs compete for these (reduces survival for junior FAs)
# <1.0 = senior FAs pass on these (increases survival)

DEMAND_MODIFIERS: dict[str, float] = {
    # Calibrated from ORD base-wide award data (Jan-Mar 2026, ~2200 lines).
    #
    # Key empirical finding: at a large base (2200+ FAs), the supply of
    # pairings is much larger than assumed. High-credit trips survive deep
    # into seniority because there are many instances. Low-credit + morning
    # trips are the most contested (short, popular schedule).
    #
    # High demand — REDUCE survival for junior FAs
    "premium_international": 1.15,    # was 1.4 — intl trips have many ops, survive longer
    "premium_domestic": 1.05,         # was 1.2 — HNL/SFO/etc well-supplied at ORD
    "high_credit": 0.85,              # was 1.3 — empirical: 89% survival at 30% seniority
    "weekend_off_pattern": 1.15,      # was 1.2 — weekends still slightly contested
    "long_layover": 1.05,             # was 1.15 — marginally more popular, not scarce
    # Low demand — INCREASE survival
    "weekday_only": 0.75,             # was 0.7 — still unpopular, slight adjustment
    "early_report": 0.85,             # was 0.8 — early reports less avoided than assumed
    "low_credit": 1.05,               # was 0.7 — empirical: low credit = MORE contested (short/easy trips)
    "undesirable_city": 0.8,          # unchanged
    "holiday_touch": 0.65,            # was 0.6 — slight adjustment
    "redeye_odan": 0.45,              # was 0.4 — slight adjustment
    "late_release": 0.85,             # unchanged
    "high_legs": 0.8,                 # was 0.75 — slight adjustment
}

# ── Layer optimism — how aspirational should each layer be? ──────────────
# 1.0 = full quality weight (dream big)
# 0.0 = full attainability weight (bid what you can hold)

LAYER_OPTIMISM: dict[int, float] = {
    1: 1.0,    # Dream — shoot for the best
    2: 0.85,   # Slightly realistic
    3: 0.70,   # Moderate
    4: 0.55,   # Realistic
    5: 0.45,   # Conservative
    6: 0.30,   # Pessimistic — target what others pass on
    7: 0.15,   # Safety net — assume most good stuff is gone
}


# ── Level 1: Seniority Percentile Heuristic ─────────────────────────────


def _hhmm_to_minutes(t: str) -> int:
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def compute_pairing_desirability(seq: dict) -> float:
    """Compute raw desirability (0.0-1.0) based on pairing characteristics.

    Higher = more senior FAs will compete for this.
    """
    totals = seq.get("totals", {})
    dps = seq.get("duty_periods", [])
    cities = seq.get("layover_cities", [])
    duty_days = totals.get("duty_days", 1) or 1

    # Start with credit efficiency as base desirability
    tpay = totals.get("tpay_minutes", 0)
    cpd = tpay / duty_days if duty_days > 0 else 0
    base = min(1.0, max(0.0, (cpd - 100) / 400))

    # Apply demand modifiers
    modifier = 1.0

    # City desirability
    if any(c in PREMIUM_INTL for c in cities):
        modifier *= DEMAND_MODIFIERS["premium_international"]
    elif any(c in PREMIUM_DOMESTIC for c in cities):
        modifier *= DEMAND_MODIFIERS["premium_domestic"]

    # Credit level
    credit_hours = tpay / 60.0
    if credit_hours > 20:
        modifier *= DEMAND_MODIFIERS["high_credit"]
    elif credit_hours < 12:
        modifier *= DEMAND_MODIFIERS["low_credit"]

    # Report time
    if dps:
        rpt = _hhmm_to_minutes(dps[0].get("report_base", "12:00"))
        if rpt < 360:  # before 06:00
            modifier *= DEMAND_MODIFIERS["early_report"]

    # Release time
    if dps:
        rel = _hhmm_to_minutes(dps[-1].get("release_base", "18:00"))
        if rel >= 1260:  # after 21:00
            modifier *= DEMAND_MODIFIERS["late_release"]

    # Weekend pattern
    op_dates = seq.get("operating_dates", [])
    weekends = {6, 7, 13, 14, 20, 21, 27, 28}
    if op_dates and not any(d in weekends for spans in [set(range(d, d + duty_days)) for d in op_dates] for d in spans):
        modifier *= DEMAND_MODIFIERS["weekend_off_pattern"]
    elif op_dates and all(d not in weekends for d in op_dates):
        modifier *= DEMAND_MODIFIERS["weekday_only"]

    # Red-eye / ODAN
    if seq.get("is_redeye") or seq.get("is_odan"):
        modifier *= DEMAND_MODIFIERS["redeye_odan"]

    # Holiday touch
    if seq.get("has_holiday"):
        modifier *= DEMAND_MODIFIERS["holiday_touch"]

    # Legs per day
    total_legs = totals.get("leg_count", 0) or 0
    if total_legs / max(duty_days, 1) >= 3.5:
        modifier *= DEMAND_MODIFIERS["high_legs"]

    return min(1.0, base * modifier)


def compute_attainability(
    seniority_number: int,
    total_fas: int,
    pairing_desirability: float,
    pool_supply: int,
    seniority_percentage: float | None = None,
) -> float:
    """Estimate probability this pairing survives to this FA's seniority.

    Level 1 heuristic: uses only seniority position and pairing traits.
    No historical data required.

    Args:
        seniority_number: FA's position at base (1 = most senior).
        total_fas: Total FAs at base.
        pairing_desirability: 0-1, from compute_pairing_desirability().
        pool_supply: How many similar pairings exist in the pool.
        seniority_percentage: 0-100 from PBS portal (overrides number/total).

    Returns:
        Survival probability (0.0-1.0).
    """
    if seniority_percentage is not None:
        seniority_pct = seniority_percentage / 100.0
    elif total_fas and total_fas > 0:
        seniority_pct = seniority_number / total_fas
    else:
        return 0.5  # unknown seniority — neutral

    # Base survival: inverse relationship between desirability and depth
    # At top seniority (0.0), everything survives
    # At bottom seniority (1.0), only undesirable pairings survive
    base_survival = max(0.0, 1.0 - (seniority_pct * pairing_desirability))

    # Pool adjustment: surplus supply improves survival
    # Each FA needs ~4-5 pairings/month, so pool_supply / (total_fas * 0.3)
    # gives a rough ratio of supply to demand for this pairing type
    supply_ratio = pool_supply / max(total_fas * 0.3, 1)
    if supply_ratio > 1.5:
        base_survival = min(1.0, base_survival * 1.3)  # surplus
    elif supply_ratio < 0.5:
        base_survival *= 0.7  # scarcity

    return round(base_survival, 3)


def holdability_category(attainability: float) -> str:
    """Classify attainability into human-readable category."""
    if attainability >= 0.70:
        return "LIKELY"
    elif attainability >= 0.40:
        return "COMPETITIVE"
    else:
        return "LONG SHOT"


def compute_effective_score(
    quality: float,
    attainability: float,
    layer_num: int,
) -> float:
    """Score that balances quality with holdability, per-layer optimism.

    Layer 1: quality dominates (dream big).
    Layer 7: attainability dominates (bid what you can hold).
    """
    optimism = LAYER_OPTIMISM.get(layer_num, 0.5)
    effective = quality * (optimism + (1 - optimism) * attainability)
    return round(effective, 4)


def compute_pool_supply(seq: dict, all_sequences: list[dict]) -> int:
    """Count how many similar pairings exist in the pool.

    Similarity: same duty_days and overlapping layover city tier.
    """
    duty_days = seq.get("totals", {}).get("duty_days", 1) or 1
    cities = set(seq.get("layover_cities", []))
    is_intl = any(c in PREMIUM_INTL for c in cities)
    is_dom_premium = any(c in PREMIUM_DOMESTIC for c in cities)

    count = 0
    for other in all_sequences:
        other_dd = other.get("totals", {}).get("duty_days", 1) or 1
        if other_dd != duty_days:
            continue
        other_cities = set(other.get("layover_cities", []))
        if is_intl and any(c in PREMIUM_INTL for c in other_cities):
            count += 1
        elif is_dom_premium and any(c in PREMIUM_DOMESTIC for c in other_cities):
            count += 1
        elif not is_intl and not is_dom_premium:
            if not any(c in PREMIUM_INTL for c in other_cities) and \
               not any(c in PREMIUM_DOMESTIC for c in other_cities):
                count += 1
    return count


# ── Safety-net layer boosters ────────────────────────────────────────────


def apply_safety_net_boost(seq: dict, effective_score: float, layer_num: int) -> float:
    """For layers 6-7, boost pairings with LOW demand (high survival).

    Mid-week, moderate credit, less popular cities — the hidden gems.
    """
    if layer_num < 6:
        return effective_score

    op_dates = seq.get("operating_dates", [])
    weekends = {6, 7, 13, 14, 20, 21, 27, 28}
    tpay = seq.get("totals", {}).get("tpay_minutes", 0)
    credit_hours = tpay / 60.0
    dps = seq.get("duty_periods", [])

    boost = 1.0

    # Weekday trips survive deep into seniority
    if op_dates and not any(d in weekends for d in op_dates):
        boost *= 1.3

    # Modest credit = less competition
    if credit_hours < 16:
        boost *= 1.2

    # Late reports = less popular
    if dps:
        rpt = _hhmm_to_minutes(dps[0].get("report_base", "12:00"))
        if rpt >= 600:  # 10:00+
            boost *= 1.1

    return effective_score * boost


# ── Level 2: Historical Calibration ─────────────────────────────────────


@dataclass
class AwardedPairing:
    """One pairing from a monthly award."""
    seq_id: str
    award_code: str           # P1-P7, PN, CN
    credit_minutes: int = 0
    layover_cities: list[str] = field(default_factory=list)
    duty_days: int = 0
    is_ipd: bool = False
    is_redeye: bool = False
    report_hour: int = 0      # hour of first report
    touches_weekend: bool = False


@dataclass
class MonthlyRecord:
    """One month of award data for calibration."""
    month: str                    # "2026-04"
    seniority: int                # 847
    total_base: int               # 1650
    pairings: list[AwardedPairing] = field(default_factory=list)
    total_credit_minutes: int = 0
    line_label: str = ""          # "P3" (highest layer used)
    lost_pairings: list[str] = field(default_factory=list)  # seq_ids wanted but didn't get


@dataclass
class CalibrationResult:
    """Output of historical calibration."""
    layer_distribution: dict[str, int] = field(default_factory=dict)
    typical_layer: str = ""
    months_of_data: int = 0
    survival_by_trait: dict[str, float] = field(default_factory=dict)
    improving: bool = False
    stable: bool = True

    def predict(self, seq: dict, seniority: int, total_fas: int) -> float:
        """Use calibrated rates to predict attainability."""
        # Start with Level 1 baseline
        desirability = compute_pairing_desirability(seq)
        base = compute_attainability(seniority, total_fas, desirability, 10)

        # Adjust using historical survival rates for traits
        traits = _extract_traits(seq)
        adjustments = []
        for trait in traits:
            if trait in self.survival_by_trait:
                adjustments.append(self.survival_by_trait[trait])

        if adjustments:
            historical_avg = sum(adjustments) / len(adjustments)
            # Blend: 60% historical, 40% heuristic
            return round(base * 0.4 + historical_avg * 0.6, 3)

        return base


def _extract_traits(seq: dict) -> list[str]:
    """Extract trait tags from a sequence for calibration matching."""
    traits = []
    totals = seq.get("totals", {})
    duty_days = totals.get("duty_days", 1) or 1
    tpay = totals.get("tpay_minutes", 0)
    cities = seq.get("layover_cities", [])

    traits.append(f"dd_{duty_days}")

    if tpay / 60 > 20:
        traits.append("high_credit")
    elif tpay / 60 < 12:
        traits.append("low_credit")
    else:
        traits.append("mid_credit")

    if any(c in PREMIUM_INTL for c in cities):
        traits.append("intl_premium")
    elif any(c in PREMIUM_DOMESTIC for c in cities):
        traits.append("dom_premium")
    else:
        traits.append("dom_standard")

    if seq.get("is_redeye") or seq.get("is_odan"):
        traits.append("redeye")

    if seq.get("is_ipd"):
        traits.append("ipd")

    return traits


def calibrate(records: list[MonthlyRecord]) -> CalibrationResult:
    """From 3+ months of award data, compute calibrated holdability rates.

    Analyzes which pairing characteristics survived to this FA's seniority
    (awarded from P1-P3) vs which were lost (PN/CN or in lost_pairings).
    """
    if len(records) < 3:
        return CalibrationResult(months_of_data=len(records))

    layer_dist: Counter = Counter()
    survived_traits: list[list[str]] = []
    lost_traits: list[list[str]] = []

    for record in records:
        for p in record.pairings:
            layer_dist[p.award_code] += 1

            # Build trait profile
            traits = [f"dd_{p.duty_days}"]
            if p.credit_minutes / 60 > 20:
                traits.append("high_credit")
            elif p.credit_minutes / 60 < 12:
                traits.append("low_credit")
            else:
                traits.append("mid_credit")
            if any(c in PREMIUM_INTL for c in p.layover_cities):
                traits.append("intl_premium")
            elif any(c in PREMIUM_DOMESTIC for c in p.layover_cities):
                traits.append("dom_premium")
            else:
                traits.append("dom_standard")
            if p.is_redeye:
                traits.append("redeye")
            if p.is_ipd:
                traits.append("ipd")

            if p.award_code in ("P1", "P2", "P3"):
                survived_traits.append(traits)
            elif p.award_code in ("PN", "CN"):
                lost_traits.append(traits)

    # Compute survival rate per trait
    trait_survived: Counter = Counter()
    trait_total: Counter = Counter()

    for traits in survived_traits:
        for t in traits:
            trait_survived[t] += 1
            trait_total[t] += 1
    for traits in lost_traits:
        for t in traits:
            trait_total[t] += 1

    survival_by_trait = {}
    for t in trait_total:
        if trait_total[t] >= 3:  # need minimum samples
            survival_by_trait[t] = round(trait_survived[t] / trait_total[t], 3)

    # Determine typical layer
    typical = layer_dist.most_common(1)[0][0] if layer_dist else ""

    # Trend: compare first half vs second half of records
    mid = len(records) // 2
    first_half_layers = []
    second_half_layers = []
    layer_order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5, "P6": 6, "P7": 7, "PN": 8, "CN": 9}

    for i, rec in enumerate(records):
        label_num = layer_order.get(rec.line_label, 5)
        if i < mid:
            first_half_layers.append(label_num)
        else:
            second_half_layers.append(label_num)

    first_avg = sum(first_half_layers) / len(first_half_layers) if first_half_layers else 5
    second_avg = sum(second_half_layers) / len(second_half_layers) if second_half_layers else 5
    improving = second_avg < first_avg - 0.5
    stable = abs(second_avg - first_avg) <= 0.5

    return CalibrationResult(
        layer_distribution=dict(layer_dist),
        typical_layer=typical,
        months_of_data=len(records),
        survival_by_trait=survival_by_trait,
        improving=improving,
        stable=stable,
    )


# ── Level 3: Base-Wide Award Analysis ─────────────────────────────────


# City tier lookup for survival trait classification
_INTL_PREMIUM_CITIES = {
    "NRT", "HND", "LHR", "CDG", "FCO", "BCN", "ATH", "AMS", "SIN", "HKG",
    "ICN", "BKK", "DUB", "VCE", "LIS", "MAD", "PRG", "ZRH", "MUC", "FRA",
    "GRU", "EZE", "SCL",
}
_DOM_PREMIUM_CITIES = {
    "SFO", "BOS", "HNL", "OGG", "SAN", "SNA", "SEA", "LAX", "AUS", "PDX",
    "SJU", "MIA", "TPA",
}


def _classify_credit_band(block_minutes: int) -> str:
    """Classify pairing by credit band."""
    hours = block_minutes / 60.0
    if hours > 20:
        return "high_credit"
    elif hours >= 12:
        return "mid_credit"
    else:
        return "low_credit"


def _classify_report_time(report_hhmm: str) -> str:
    """Classify by report time bucket."""
    if not report_hhmm or len(report_hhmm) != 4:
        return "midday"
    hour = int(report_hhmm[:2])
    if hour < 6:
        return "early"
    elif hour < 10:
        return "morning"
    elif hour < 14:
        return "midday"
    else:
        return "afternoon"


def _classify_pairing_traits(pairing: dict) -> dict[str, str]:
    """Classify an award pairing instance into trait buckets.

    Args:
        pairing: dict with keys from extract_pairing_award_map() —
            block_minutes, report_time, release_time, line_number, etc.

    Returns:
        Dict of trait dimensions → trait values.
    """
    blk = pairing.get("block_minutes", 0)
    rpt = pairing.get("report_time", "")

    return {
        "credit": _classify_credit_band(blk),
        "report": _classify_report_time(rpt),
    }


def _build_trait_key(traits: dict[str, str]) -> str:
    """Build a combined trait key string from trait dict."""
    return "|".join(f"{traits.get(k, '?')}" for k in ("credit", "report"))


# Seniority percentile breakpoints for survival curves
_PERCENTILE_STEPS = [round(p / 100.0, 2) for p in range(5, 100, 5)]  # 0.05, 0.10, ..., 0.95


def build_survival_curves(award_file_data: list[dict]) -> dict:
    """Build empirical survival curves from parsed APFA award file data.

    Each entry in award_file_data should be a dict with:
        - total_lines: int (total FA lines in that month)
        - pairings: list of dicts, each with:
            - line_number: int (seniority position of FA awarded this pairing)
            - block_minutes: int
            - report_time: str (HHMM)
            - priority: str (P1-P7, PN, CN)

    Returns:
        Dict mapping trait_key → list of (seniority_pct, survival_rate) tuples.
        survival_rate at pct X = fraction of pairings in this bucket that were
        awarded to someone at seniority >= X% (i.e., "survived past" the top X%).
    """
    if not award_file_data:
        return {}

    # Collect all pairing instances across months, keyed by trait bucket
    # Each instance records the seniority_pct at which it was taken
    trait_buckets: dict[str, list[float]] = {}

    for month_data in award_file_data:
        total_lines = month_data.get("total_lines", 1)
        pairings = month_data.get("pairings", [])

        for p in pairings:
            line_num = p.get("line_number", 0)
            if line_num <= 0 or total_lines <= 0:
                continue
            seniority_pct = line_num / total_lines

            traits = _classify_pairing_traits(p)
            key = _build_trait_key(traits)
            trait_buckets.setdefault(key, []).append(seniority_pct)

            # Also add to individual trait keys for fallback matching
            for dim, val in traits.items():
                trait_buckets.setdefault(val, []).append(seniority_pct)

    # Build survival curves for each bucket
    curves: dict[str, list[tuple[float, float]]] = {}

    for key, seniority_pcts in trait_buckets.items():
        if len(seniority_pcts) < 5:
            continue  # Too few samples

        n = len(seniority_pcts)
        curve = []
        for step in _PERCENTILE_STEPS:
            # Fraction of pairings awarded at seniority >= step
            survived = sum(1 for s in seniority_pcts if s >= step) / n
            curve.append((step, round(survived, 4)))
        curves[key] = curve

    logger.info(
        "Level 3 survival curves: %d trait buckets from %d month(s), %d total pairing instances",
        len(curves), len(award_file_data),
        sum(len(v) for v in trait_buckets.values()),
    )
    return curves


def lookup_survival(
    curves: dict[str, list[tuple[float, float]]],
    seniority_pct: float,
    block_minutes: int = 0,
    report_time: str = "",
) -> float | None:
    """Look up empirical survival rate for a pairing at given seniority.

    Tries combined trait key first, then falls back to individual traits.
    Returns None if no empirical data available.
    """
    if not curves:
        return None

    traits = _classify_pairing_traits({
        "block_minutes": block_minutes,
        "report_time": report_time,
    })
    combined_key = _build_trait_key(traits)

    # Try combined key first, then individual trait keys
    keys_to_try = [combined_key] + list(traits.values())

    for key in keys_to_try:
        curve = curves.get(key)
        if curve is None:
            continue
        return _interpolate_curve(curve, seniority_pct)

    return None


def _interpolate_curve(
    curve: list[tuple[float, float]], target_pct: float
) -> float:
    """Interpolate survival rate from a curve at a given seniority percentile."""
    if not curve:
        return 0.5

    # Clamp to curve range
    if target_pct <= curve[0][0]:
        return curve[0][1]
    if target_pct >= curve[-1][0]:
        return curve[-1][1]

    # Linear interpolation between bracketing points
    for i in range(len(curve) - 1):
        pct_lo, surv_lo = curve[i]
        pct_hi, surv_hi = curve[i + 1]
        if pct_lo <= target_pct <= pct_hi:
            if pct_hi == pct_lo:
                return surv_lo
            frac = (target_pct - pct_lo) / (pct_hi - pct_lo)
            return surv_lo + frac * (surv_hi - surv_lo)

    return curve[-1][1]


# Module-level cache for survival curves
_survival_curves_cache: dict[str, list[tuple[float, float]]] | None = None


def get_cached_survival_curves() -> dict[str, list[tuple[float, float]]] | None:
    """Return cached survival curves, or None if not yet computed."""
    return _survival_curves_cache


def set_cached_survival_curves(curves: dict[str, list[tuple[float, float]]]) -> None:
    """Store computed survival curves in module-level cache."""
    global _survival_curves_cache
    _survival_curves_cache = curves
    logger.info("Survival curves cached: %d trait buckets", len(curves))


# ── Holdability Report ──────────────────────────────────────────────────


def generate_holdability_report(
    layers: list[dict],
    seniority_number: int,
    total_fas: int,
    seniority_percentage: float | None = None,
    calibration: CalibrationResult | None = None,
) -> dict:
    """Generate the overall holdability report card.

    Returns a dict with:
      - seniority_label: "Senior" / "Upper-mid" / "Mid" / "Lower-mid" / "Junior"
      - seniority_pct: 0.0-1.0
      - layers: list of per-layer holdability summaries
      - best_realistic_layers: which layers the FA will likely get
      - recommendation: personalized advice string
      - trend: improving / stable / declining (if calibration available)
    """
    if seniority_percentage is not None:
        pct = seniority_percentage / 100.0
    elif total_fas and total_fas > 0:
        pct = seniority_number / total_fas
    else:
        pct = 0.5

    # Seniority label
    if pct < 0.15:
        label = "Senior"
    elif pct < 0.4:
        label = "Upper-mid"
    elif pct < 0.6:
        label = "Mid"
    elif pct < 0.8:
        label = "Lower-mid"
    else:
        label = "Junior"

    layer_reports = []
    for ldata in layers:
        layer_num = ldata.get("layer_num", 0)
        sequences = ldata.get("sequences", [])
        strategy_name = ldata.get("strategy_name", "")
        credit_hours = ldata.get("credit_hours", 0)

        # Average holdability across sequences in this layer
        holdabilities = [s.get("_holdability", 0.5) for s in sequences]
        avg_hold = sum(holdabilities) / len(holdabilities) if holdabilities else 0.5

        # Most contested pairing
        if sequences:
            most_contested = min(sequences, key=lambda s: s.get("_holdability", 1.0))
            mc_id = most_contested.get("seq_number", "?")
        else:
            mc_id = None

        hold_cat = holdability_category(avg_hold)

        # Verdict
        if avg_hold >= 0.70:
            verdict = "LIKELY -- strong position"
        elif avg_hold >= 0.55:
            verdict = "COMPETITIVE -- worth bidding"
        elif avg_hold >= 0.40:
            verdict = "ASPIRATIONAL -- stretch goal"
        else:
            verdict = "LONG SHOT -- dream layer"

        layer_reports.append({
            "layer_num": layer_num,
            "strategy_name": strategy_name,
            "credit_hours": credit_hours,
            "holdability_pct": round(avg_hold * 100, 0),
            "holdability_category": hold_cat,
            "verdict": verdict,
            "most_contested_seq": mc_id,
            "pool_size": ldata.get("pool_size", 0),
        })

    # Best realistic layers (>= 55% holdability)
    best_realistic = [lr for lr in layer_reports if lr["holdability_pct"] >= 55]
    best_realistic_nums = [lr["layer_num"] for lr in best_realistic]

    # Recommendation
    recommendation = _generate_recommendation(layer_reports, pct, calibration)

    # Trend
    trend = None
    if calibration and calibration.months_of_data >= 3:
        if calibration.improving:
            trend = "improving"
        elif calibration.stable:
            trend = "stable"
        else:
            trend = "declining"

    return {
        "seniority_label": label,
        "seniority_pct": round(pct, 3),
        "seniority_display": f"#{seniority_number} of {total_fas}",
        "layers": layer_reports,
        "best_realistic_layers": best_realistic_nums,
        "recommendation": recommendation,
        "trend": trend,
        "calibration_months": calibration.months_of_data if calibration else 0,
    }


def _generate_recommendation(
    layer_reports: list[dict],
    seniority_pct: float,
    calibration: CalibrationResult | None,
) -> str:
    """Personalized bidding advice based on holdability analysis."""
    if calibration and calibration.months_of_data >= 3:
        typical = calibration.typical_layer
        layer_order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5, "P6": 6, "P7": 7}
        typical_num = layer_order.get(typical, 5)

        if typical_num <= 2:
            return (
                "At your seniority, you typically hold Layers 1-2 most months. "
                "Focus on fine-tuning Layer 1 for the perfect schedule shape. "
                "Consider narrowing your L1 filters to get exactly the trips you want."
            )
        elif typical_num <= 4:
            return (
                "You're in the competitive middle. Layers 2-4 are your realistic range. "
                "Make sure these layers have genuinely different strategies -- not just "
                "reshuffled versions of Layer 1. Layer 2 should be your 'realistic dream' "
                "and Layer 4 should be your 'good enough' fallback."
            )
        else:
            return (
                "At your seniority, Layers 5-7 are where your schedule actually comes from. "
                "Invest time making these layers great -- they're not throwaway safety nets, "
                "they're your real schedule. Target trips senior FAs pass on: mid-week flying, "
                "moderate credit, less popular cities. These are the hidden gems."
            )

    # No calibration — use seniority percentile
    if seniority_pct < 0.25:
        return (
            "Your seniority gives you strong position. Layers 1-2 should be achievable. "
            "Focus on making Layer 1 exactly what you want -- narrow filters, premium trips. "
            "Start recording your award results each month to refine predictions."
        )
    elif seniority_pct < 0.5:
        return (
            "Upper-mid seniority means Layers 2-4 are your sweet spot. "
            "Layer 1 is worth the reach but build Layers 2-3 as if they're your real schedule. "
            "Start recording your award results to calibrate -- after 3 months we'll know "
            "exactly which trips survive to your position."
        )
    elif seniority_pct < 0.75:
        return (
            "At your seniority, focus energy on Layers 4-6. These are your working layers. "
            "Target mid-week flying and moderate-credit trips that senior FAs pass on. "
            "Layer 7 is critical insurance. Start recording awards to build your calibration data."
        )
    else:
        return (
            "Junior seniority means Layers 5-7 are where your schedule comes from. "
            "Don't waste time perfecting Layer 1 -- invest in making Layers 6-7 genuinely good. "
            "Target pairings senior FAs skip: early reports, mid-week, secondary cities. "
            "These hidden gems will build you a much better schedule than chasing premium trips."
        )
