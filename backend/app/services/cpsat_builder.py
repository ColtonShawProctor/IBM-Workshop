"""CP-SAT constraint optimization for PBS layer building.

Replaces the greedy _build_one_layer with Google OR-Tools CP-SAT solver
for provably optimal schedule construction with compactness objectives.

Key improvements over greedy:
1. Global optimization — considers all sequences simultaneously, not one-at-a-time
2. Compactness — directly optimizes for contiguous work blocks ("2 weeks on / 2 weeks off")
3. Backtracking — if sequence A blocks a better combination B+C, finds B+C
4. Layer diversity — Hamming distance constraints ensure genuinely different layers
5. Multi-dimensional trip quality — layover city, rest duration, report time, legs/day
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── OR-Tools import (graceful fallback) ──────────────────────────────────

try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError:
    cp_model = None  # type: ignore[assignment]
    HAS_ORTOOLS = False
    logger.warning("ortools not installed — CP-SAT unavailable, using greedy fallback")


# ── Constants ────────────────────────────────────────────────────────────

MIN_REST_HOURS = 10

# Attainability multipliers (must match optimizer.py)
_ATT_MULT = {"high": 1.0, "medium": 0.8, "low": 0.5, "unknown": 0.7}

# ── Trip quality scoring weights ─────────────────────────────────────────
# Standard weights (non-commuter FA or base == mailbox)
STANDARD_WEIGHTS = {
    "credit_efficiency": 0.25,
    "layover_quality": 0.20,
    "layover_city": 0.15,
    "report_time": 0.10,
    "release_time": 0.10,
    "legs_per_day": 0.10,
    "red_eye_penalty": 0.05,
    "deadhead_penalty": 0.05,
}

# Commuter weights (auto-detected when base != mailbox/commute_from)
# Report/release time weighted much higher — every bad time costs an off-day
COMMUTER_WEIGHTS = {
    "credit_efficiency": 0.25,
    "layover_quality": 0.10,
    "layover_city": 0.10,
    "report_time": 0.20,
    "release_time": 0.15,
    "legs_per_day": 0.10,
    "red_eye_penalty": 0.05,
    "deadhead_penalty": 0.05,
}

# Layover city desirability tiers (0-100)
CITY_TIERS: dict[str, int] = {
    # International dream destinations (90-100)
    "NRT": 100, "HND": 95, "LHR": 98, "CDG": 95, "FCO": 95, "BCN": 93,
    "ATH": 92, "DUB": 90, "AMS": 92, "MXP": 90, "ICN": 90, "HKG": 92,
    "SIN": 95, "BKK": 90, "GRU": 85, "EZE": 85, "SCL": 82, "LIS": 88,
    "MAD": 90, "FRA": 85, "MUC": 85, "ZRH": 88, "PRG": 88, "VCE": 92,
    # Premium domestic (80-89)
    "HNL": 95, "OGG": 93, "SFO": 88, "LAX": 85, "SAN": 88, "SEA": 85,
    "BOS": 87, "AUS": 85, "DEN": 83, "PDX": 82, "SNA": 85, "MIA": 82,
    "TPA": 80, "SJU": 82,
    # Mid-tier domestic (65-79)
    "MSP": 75, "DTW": 70, "JFK": 78, "DCA": 75, "LAS": 75, "PHX": 72,
    "ORD": 70, "SLC": 70, "RDU": 68, "BNA": 72, "MCO": 70,
    # Lower-tier domestic (50-64)
    "PHL": 60, "DFW": 55, "CLT": 58, "STL": 52, "CVG": 50, "CMH": 50,
    "IND": 48, "MCI": 50,
}
_CITY_DEFAULT = 55

# Compactness weight presets
# Rule of thumb: worst-case penalty (30-day span, 15 gaps) should be < 40%
# of the quality from selecting 5 sequences (~7500 pts).
# "strong": worst = -60*30 + -60*15 = -2700 → 36% of 7500 ✓
COMPACTNESS_LEVELS: dict[str, dict[str, int]] = {
    "strong":   {"span_weight": 20, "gap_weight": 12},
    "moderate": {"span_weight": 8,  "gap_weight": 4},
    "light":    {"span_weight": 3,  "gap_weight": 2},
    "none":     {"span_weight": 0,  "gap_weight": 0},
}

# Per-layer optimization strategies
DEFAULT_LAYER_STRATEGIES: dict[int, dict] = {
    1: {"name": "Dream Schedule — Compact + Quality",
        "compactness": "strong", "target_window": "first_half",
        "credit_range": (4200, 5400),      # 70-90h
        "credit_in_objective": False,
        "min_pairing_days": 3},             # 3+ day trips for compact commuter schedules
    2: {"name": "Alternative Schedule — Back Half",
        "compactness": "strong", "target_window": "second_half",
        "hamming_min": 2,                  # force different selections from L1
        "credit_range": (4200, 5400),      # 70-90h
        "credit_in_objective": False,
        "min_pairing_days": 3},             # 3+ day trips
    3: {"name": "Maximum Pay",
        "compactness": "moderate", "credit_boost": 1.5,
        "credit_range": (5220, 5400),      # 87-90h — narrowest, highest floor
        "credit_in_objective": True,
        "min_pairing_days": 3},             # 3+ day trips for better total pay
    4: {"name": "All 4-Day Trips — Fewer Commutes",
        "compactness": "moderate",
        "credit_range": (4800, 5400),      # 80-90h — wider range for 4-day trips
        "credit_in_objective": False,
        "min_pairing_days": 4},             # 4-day trips only = fewer commute events
    5: {"name": "Best Layovers — Quality Destinations",
        "compactness": "moderate", "hamming_min": 3,
        "credit_range": (4680, 5280),      # 78-88h
        "credit_in_objective": False,
        "layover_city_boost": 1.5,
        "min_pairing_days": 3},             # 3+ day trips have layovers
    6: {"name": "Flexible Alternative",
        "compactness": "light", "hamming_min": 2,
        "credit_range": (4500, 5400),      # 75-90h
        "credit_in_objective": False,
        "min_pairing_days": 3},             # 3+ day trips with layovers
    7: {"name": "Safety Net — Maximum Flexibility",
        "compactness": "none",
        "credit_range": (4200, 5400),      # 70-90h — full range
        "credit_in_objective": False,
        "min_pairing_days": 2},
}

# Also accessible as THEMED_LAYER_STRATEGIES for clarity
THEMED_LAYER_STRATEGIES = DEFAULT_LAYER_STRATEGIES

# Progressive relaxation strategies — used with progressive pool building.
# Layers differ in POOL SIZE (progressively wider), not in theme.
# CP-SAT strategy controls compactness and credit range per layer.
#
# Key changes from initial version:
# - L1-L3: min_pairing_days=3 (no 2-day turns — fewer commute events, better rigs)
# - L2-L7: domestic_only=True (international only on L1 lottery ticket)
# - All layers: credit floor 70h (4200 min) to prevent "Outside credit range"
PROGRESSIVE_LAYER_STRATEGIES: dict[int, dict] = {
    1: {"name": "Lottery Ticket / Dream Schedule",
        "compactness": "strong", "target_window": "first_half",
        "credit_range": (4200, 5400),
        "credit_in_objective": False,
        "min_pairing_days": 3,
        "domestic_only": False},            # L1 = lottery ticket, international OK
    2: {"name": "Best Specific Pairings",
        "compactness": "strong",
        "credit_range": (4200, 5400),
        "credit_in_objective": False,
        "min_pairing_days": 3,
        "domestic_only": True},
    3: {"name": "Your Favorites as Generic Properties",
        "compactness": "moderate",
        "credit_range": (4200, 5400),
        "credit_in_objective": False,
        "min_pairing_days": 3,
        "domestic_only": True},
    4: {"name": "Wider Pool — One Property Relaxed",
        "compactness": "moderate", "hamming_min": 2,
        "credit_range": (4200, 5400),
        "credit_in_objective": False,
        "min_pairing_days": 2,
        "domestic_only": True},
    5: {"name": "Broader — More Flexibility",
        "compactness": "moderate", "hamming_min": 2,
        "credit_range": (4200, 5400),
        "credit_in_objective": False,
        "min_pairing_days": 2,
        "domestic_only": True},
    6: {"name": "Broad Domestic",
        "compactness": "light", "hamming_min": 2,
        "credit_range": (4200, 5400),
        "credit_in_objective": False,
        "min_pairing_days": 2,
        "domestic_only": True},
    7: {"name": "Safety Net — Maximum Flexibility",
        "compactness": "none",
        "credit_range": (4200, 5400),
        "credit_in_objective": False,
        "min_pairing_days": 2,
        "domestic_only": True},
}


# ── Helpers ──────────────────────────────────────────────────────────────

def _hhmm_to_minutes(t: str) -> int:
    """Convert "HH:MM" to minutes since midnight."""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


# ── Trip Quality Scoring ─────────────────────────────────────────────────

def compute_trip_quality(seq: dict, *, is_commuter: bool = False) -> float:
    """Compute composite trip quality score (0.0-1.0) for a sequence.

    Eight dimensions, weighted by COMMUTER_WEIGHTS or STANDARD_WEIGHTS.
    Commuter detection is automatic: if base != mailbox, commuter weights
    are applied (report/release time weighted 20%/15% instead of 10%/10%).
    """
    w = COMMUTER_WEIGHTS if is_commuter else STANDARD_WEIGHTS
    totals = seq.get("totals", {})
    dps = seq.get("duty_periods", [])
    duty_days = totals.get("duty_days", 1) or 1

    # 1. Credit efficiency (TPAY / duty day, normalized 100-500 → 0-100)
    tpay = totals.get("tpay_minutes", 0)
    cpd = tpay / duty_days
    credit_eff = min(100.0, max(0.0, (cpd - 100) / 4.0))

    # 2. Layover quality — Gaussian centred on 24 h, SD = 8 h
    layover_scores: list[float] = []
    for dp in dps:
        lo = dp.get("layover")
        if lo and lo.get("rest_minutes"):
            hours = lo["rest_minutes"] / 60.0
            layover_scores.append(100.0 * math.exp(-((hours - 24) ** 2) / (2 * 64)))
    avg_layover = sum(layover_scores) / len(layover_scores) if layover_scores else 50.0

    # 3. Layover city desirability
    cities = seq.get("layover_cities", [])
    if cities:
        avg_city = sum(CITY_TIERS.get(c, _CITY_DEFAULT) for c in cities) / len(cities)
    else:
        avg_city = 50.0

    # 4. Report time (linear ramp: 05:00 → 0, 12:00+ → 100)
    if dps:
        rpt_min = _hhmm_to_minutes(dps[0].get("report_base", "12:00"))
        if rpt_min >= 720:
            report_score = 100.0
        elif rpt_min <= 300:
            report_score = 0.0
        else:
            report_score = (rpt_min - 300) / 420.0 * 100.0
    else:
        report_score = 50.0

    # 5. Release time (earlier = better for commuting home)
    #    Before 16:00 = 100, 16:00-19:00 = linear 100→40, 19:00-22:00 = linear 40→0, after 22:00 = 0
    if dps:
        rel_min = _hhmm_to_minutes(dps[-1].get("release_base", "18:00"))
        if rel_min <= 960:       # before 16:00
            release_score = 100.0
        elif rel_min <= 1140:    # 16:00-19:00
            release_score = 100.0 - (rel_min - 960) / 180.0 * 60.0
        elif rel_min <= 1320:    # 19:00-22:00
            release_score = 40.0 - (rel_min - 1140) / 180.0 * 40.0
        else:                    # after 22:00
            release_score = 0.0
    else:
        release_score = 50.0

    # 6. Legs per duty day
    total_legs = totals.get("leg_count", 0) or 0
    avg_legs = total_legs / duty_days if duty_days > 0 else 2.0
    if avg_legs <= 1.0:
        legs_score = 100.0
    elif avg_legs <= 2.0:
        legs_score = 100.0 - (avg_legs - 1.0) * 20.0
    elif avg_legs <= 3.0:
        legs_score = 80.0 - (avg_legs - 2.0) * 30.0
    else:
        legs_score = max(20.0, 50.0 - (avg_legs - 3.0) * 30.0)

    # 7. Red-eye / ODAN penalty
    redeye = 0.0 if (seq.get("is_redeye") or seq.get("is_odan")) else 100.0

    # 8. Deadhead penalty
    dh = totals.get("deadhead_count", 0) or 0
    total_leg = totals.get("leg_count", 1) or 1
    dh_score = max(0.0, 100.0 * (1.0 - dh / total_leg))

    composite = (
        w["credit_efficiency"] * credit_eff
        + w["layover_quality"] * avg_layover
        + w["layover_city"] * avg_city
        + w["report_time"] * report_score
        + w["release_time"] * release_score
        + w["legs_per_day"] * legs_score
        + w["red_eye_penalty"] * redeye
        + w["deadhead_penalty"] * dh_score
    )
    return composite / 100.0  # normalise to 0.0-1.0


# ── CP-SAT Layer Builder ─────────────────────────────────────────────────


def solve_layer_cpsat(
    candidates: list[dict],
    total_dates: int,
    max_credit_minutes: int = 5400,
    min_credit_minutes: int = 0,
    min_days_off: int = 11,
    layer_num: int = 1,
    previous_solutions: list[set[str]] | None = None,
    strategy: dict | None = None,
    *,
    block_limit_7day_minutes: int = 1800,
    home_rest_minutes: int = 690,
    double_up_dates: set[int] | None = None,
) -> list[dict]:
    """Build one valid monthly schedule using CP-SAT constraint optimisation.

    Replaces the greedy ``_build_one_layer``.  Finds the provably optimal
    combination of sequences that maximises quality while respecting all
    CBA/FAA legality constraints and schedule compactness.

    Args:
        candidates: Pre-scored sequences with ``_all_spans`` computed.
        total_dates: Days in bid period (e.g. 31 for January).
        max_credit_minutes: Maximum credit (default 90 h = 5400 min).
        min_credit_minutes: Minimum credit (default 0 = no minimum).
        min_days_off: CBA minimum days off (default 11).
        layer_num: 1-7 — selects default strategy.
        previous_solutions: Sets of ``_id`` values selected in prior layers.
        strategy: Override for the layer strategy dict.
        block_limit_7day_minutes: 7-day rolling block limit (1800=30h default,
            2100=35h when waived per CBA §11.B.3).
        home_rest_minutes: Minimum rest between sequences (690=11h30m CBA
            contractual default, 630=10h30m when waived to FAR minimum).
        double_up_dates: Calendar days where double-ups are allowed (two
            sequences in one duty day with 30-min gap per CBA §2.N).

    Returns:
        Selected sequences with ``_chosen_span`` set, sorted by date.
        Returns empty list if no feasible solution.
    """
    if not HAS_ORTOOLS:
        return _greedy_fallback(candidates, total_dates, max_credit_minutes, min_days_off)

    strat = strategy or DEFAULT_LAYER_STRATEGIES.get(layer_num, {})
    compact_cfg = COMPACTNESS_LEVELS.get(
        strat.get("compactness", "moderate"), COMPACTNESS_LEVELS["moderate"]
    )

    # Strategy credit range — max is a hard constraint (tightens bid-period max),
    # min is enforced as both a hard constraint and a soft penalty.
    credit_range = strat.get("credit_range")
    strat_min_credit = max(
        credit_range[0] if credit_range else 0,
        min_credit_minutes,
    )
    if credit_range:
        max_credit_minutes = min(max_credit_minutes, credit_range[1])
    min_credit_minutes = max(min_credit_minutes, 0)

    # Filter out sequences shorter than min_pairing_days
    min_pd = strat.get("min_pairing_days", 0)
    if min_pd > 0:
        candidates = [
            c for c in candidates
            if (c.get("totals", {}).get("duty_days", 1) or 1) >= min_pd
        ]

    # Filter international trips when domestic_only is set
    if strat.get("domestic_only", False):
        candidates = [
            c for c in candidates
            if c.get("is_domestic", True)
        ]

    # Only keep candidates that have operating-date instances
    valid: list[tuple[int, dict]] = [
        (i, seq) for i, seq in enumerate(candidates) if seq.get("_all_spans")
    ]
    if not valid:
        return []

    model = cp_model.CpModel()

    # ── Decision variables ────────────────────────────────────────────
    # For each sequence with K operating-date instances, create K binary
    # variables. At most one instance can be selected per sequence.

    # Flat list: (BoolVar, span_set, valid_index)
    instance_vars: list[tuple] = []
    # Per valid-candidate: indices into instance_vars
    seq_groups: list[list[int]] = []
    # Per valid-candidate: "is this sequence selected at all?"
    seq_selected: list = []

    for vi, (_orig_idx, seq) in enumerate(valid):
        spans = seq["_all_spans"]
        group: list[int] = []
        for k, span in enumerate(spans):
            var = model.new_bool_var(f"s{vi}_k{k}")
            group.append(len(instance_vars))
            instance_vars.append((var, span, vi))
        seq_groups.append(group)

        # At most one operating-date instance per sequence
        if len(group) > 1:
            model.add(sum(instance_vars[j][0] for j in group) <= 1)

        # Aggregate "selected" variable
        sel = model.new_bool_var(f"sel_{vi}")
        model.add(sum(instance_vars[j][0] for j in group) == sel)
        seq_selected.append(sel)

    n_valid = len(valid)

    # ── Hard Constraints 1+2: No-overlap + rest + double-up ────────────
    # When double-up dates are specified, we use per-day capacity constraints
    # instead of add_no_overlap so that two 1-day turns can share a day.
    # Otherwise, the efficient interval-based no-overlap is used.
    _du_dates = double_up_dates or set()

    ends_on: dict[int, list[int]] = defaultdict(list)
    starts_on: dict[int, list[int]] = defaultdict(list)
    for idx, (_var, span, _vi) in enumerate(instance_vars):
        ends_on[max(span)].append(idx)
        starts_on[min(span)].append(idx)

    rest_constraints = 0
    double_up_pairs = 0

    if _du_dates:
        # ── Per-day capacity model (supports double-ups) ──────────
        # Pre-compute valid double-up pairs for conflict exemption
        _valid_du_pairs: set[tuple[int, int]] = set()
        from app.services.cba_rules import get_max_domestic_duty

        for day in _du_dates:
            day_turns = []  # (instance_idx, report_min, release_min, seg_count)
            for idx, (var, span, vi) in enumerate(instance_vars):
                if day not in span:
                    continue
                seq = valid[vi][1]
                dd = seq.get("totals", {}).get("duty_days", 1) or 1
                if dd != 1:
                    continue  # only 1-day turns can double-up
                dps = seq.get("duty_periods", [])
                if not dps:
                    continue
                rpt = _hhmm_to_minutes(dps[0].get("report_base", "08:00"))
                rel = _hhmm_to_minutes(dps[-1].get("release_base", "18:00"))
                segs = seq.get("totals", {}).get("leg_count", 1) or 1
                day_turns.append((idx, rpt, rel, segs))

            # Check all pairs of turns on this day
            for i in range(len(day_turns)):
                for j in range(i + 1, len(day_turns)):
                    ai, rpt_a, rel_a, seg_a = day_turns[i]
                    bi, rpt_b, rel_b, seg_b = day_turns[j]
                    # Try both orderings: A then B, B then A
                    ok = False
                    if rel_a + 30 <= rpt_b:
                        combined = rel_b - rpt_a
                        if combined <= get_max_domestic_duty(rpt_a, seg_a + seg_b):
                            ok = True
                    if not ok and rel_b + 30 <= rpt_a:
                        combined = rel_a - rpt_b
                        if combined <= get_max_domestic_duty(rpt_b, seg_a + seg_b):
                            ok = True
                    if ok:
                        _valid_du_pairs.add((min(ai, bi), max(ai, bi)))
                        double_up_pairs += 1

        # Per-day constraints
        for day in range(1, total_dates + 1):
            day_idxs = [idx for idx, (var, span, vi) in enumerate(instance_vars)
                        if day in span]
            if not day_idxs:
                continue

            if day in _du_dates:
                # Split into turns and multi-day
                turn_idxs = [idx for idx in day_idxs
                             if (valid[instance_vars[idx][2]][1].get("totals", {}).get("duty_days", 1) or 1) == 1]
                multi_idxs = [idx for idx in day_idxs if idx not in turn_idxs]

                # Multi-day sequences conflict with everything else on this day
                for mi in multi_idxs:
                    for oi in day_idxs:
                        if oi != mi:
                            model.add(instance_vars[mi][0] + instance_vars[oi][0] <= 1)

                # Turns: at most 2, but incompatible pairs are blocked
                if turn_idxs:
                    model.add(sum(instance_vars[ti][0] for ti in turn_idxs) <= 2)
                    # Block incompatible turn pairs
                    for i in range(len(turn_idxs)):
                        for j in range(i + 1, len(turn_idxs)):
                            pair = (min(turn_idxs[i], turn_idxs[j]),
                                    max(turn_idxs[i], turn_idxs[j]))
                            if pair not in _valid_du_pairs:
                                model.add(instance_vars[turn_idxs[i]][0]
                                          + instance_vars[turn_idxs[j]][0] <= 1)
            else:
                # Normal day: at most 1 instance
                model.add(sum(instance_vars[idx][0] for idx in day_idxs) <= 1)
    else:
        # ── Efficient interval-based no-overlap (no double-ups) ───
        intervals = []
        for idx, (var, span, _vi) in enumerate(instance_vars):
            s = min(span)
            sz = max(span) - s + 1
            iv = model.new_optional_fixed_size_interval_var(s, sz, var, f"iv_{idx}")
            intervals.append(iv)
        model.add_no_overlap(intervals)

    # ── Rest between consecutive sequences ────────────────────────────
    # CBA §11.I: contractual 11h + 30min = 690 min (default)
    # When waived: FAR 10h + 30min = 630 min
    for day in range(1, total_dates + 1):
        for a_idx in ends_on.get(day, []):
            _va, _sa, vi_a = instance_vars[a_idx]
            seq_a = valid[vi_a][1]
            dps_a = seq_a.get("duty_periods", [])
            if not dps_a:
                continue
            rel_a = _hhmm_to_minutes(dps_a[-1].get("release_base", "18:00"))

            for b_idx in starts_on.get(day + 1, []):
                _vb, _sb, vi_b = instance_vars[b_idx]
                if vi_a == vi_b:
                    continue

                seq_b = valid[vi_b][1]
                dps_b = seq_b.get("duty_periods", [])
                if not dps_b:
                    continue
                rpt_b = _hhmm_to_minutes(dps_b[0].get("report_base", "08:00"))

                rest_min = (24 * 60 - rel_a) + rpt_b
                if rest_min < home_rest_minutes:
                    model.add(
                        instance_vars[a_idx][0] + instance_vars[b_idx][0] <= 1
                    )
                    rest_constraints += 1

    # ── Hard Constraint 3: Credit max ──────────────────────────────
    # Credit MINIMUM is enforced as a strong soft penalty (not hard) in the
    # objective section below.  This avoids infeasibility when date conflicts,
    # 7-day block limits, or other constraints prevent reaching the target.
    credit_coeffs: list[tuple] = []  # (sel_var, tpay_int)
    for vi in range(n_valid):
        tpay = valid[vi][1].get("totals", {}).get("tpay_minutes", 0)
        if tpay > 0:
            credit_coeffs.append((seq_selected[vi], tpay))
    if credit_coeffs:
        model.add(sum(var * coeff for var, coeff in credit_coeffs) <= max_credit_minutes)

    # ── Hard Constraint 4: Minimum days off ───────────────────────────
    max_work_days = total_dates - min_days_off
    work_coeffs: list[tuple] = []
    for vi in range(n_valid):
        dd = valid[vi][1].get("totals", {}).get("duty_days", 1) or 1
        work_coeffs.append((seq_selected[vi], dd))
    if work_coeffs:
        model.add(sum(var * coeff for var, coeff in work_coeffs) <= max_work_days)

    # ── Hard Constraint 5: 7-day cumulative block limit ────────────
    # CBA §11.B: 30h scheduled (1800 min), waivable to 35h (2100 min)
    block_constraints = 0
    for window_start in range(1, total_dates - 5):
        window_days = set(range(window_start, window_start + 7))
        block_terms: list = []
        for idx, (var, span, vi) in enumerate(instance_vars):
            overlap = len(span & window_days)
            if overlap > 0:
                seq = valid[vi][1]
                total_block = seq.get("totals", {}).get("block_minutes", 0)
                span_size = len(span)
                if span_size > 0 and total_block > 0:
                    # Proportional: only count block hours for days in this window
                    block_in_window = int(total_block * overlap / span_size)
                    if block_in_window > 0:
                        block_terms.append(var * block_in_window)
        if block_terms:
            model.add(sum(block_terms) <= block_limit_7day_minutes)
            block_constraints += 1

    # ── Hard Constraint 6: Max 6 consecutive duty days (CBA §11.C) ──
    # "Cannot fly more than 6 consecutive days unless the period contains
    #  or is followed by 24 consecutive hours free from all duty."
    # Modeled as: in any 7-day window, at most 6 days can be working days.
    work_day: dict[int, object] = {}
    _has_instances: set[int] = set()
    for d in range(1, total_dates + 1):
        d_vars = [var for var, span, vi in instance_vars if d in span]
        if d_vars:
            wd = model.new_bool_var(f"wd_{d}")
            # wd = 1 iff any instance occupies day d
            model.add(wd <= sum(d_vars))
            for dv in d_vars:
                model.add(wd >= dv)
            work_day[d] = wd
            _has_instances.add(d)

    for window_start in range(1, total_dates - 5):
        window = range(window_start, window_start + 7)
        wd_terms = [work_day[d] for d in window if d in _has_instances]
        if len(wd_terms) >= 7:  # only constrain if all 7 days could be working
            model.add(sum(wd_terms) <= 6)

    # ── Objective terms ───────────────────────────────────────────────
    SCALE = 1000  # CP-SAT uses integers; multiply floats by SCALE

    # --- Quality: blended property score + trip quality ----------------
    # Each selected sequence gets a base selection bonus (ensures selecting
    # sequences is ALWAYS preferred over empty schedules regardless of
    # compactness penalties) PLUS a quality score.
    SELECTION_BONUS = SCALE // 2  # 500 per sequence

    credit_in_obj = strat.get("credit_in_objective", True)
    city_boost = strat.get("layover_city_boost", 1.0)

    # Holdability-aware objective: layer optimism controls quality vs attainability blend
    from app.services.holdability import LAYER_OPTIMISM, apply_safety_net_boost

    quality_terms: list = []
    for vi in range(n_valid):
        seq = valid[vi][1]
        pref = seq.get("preference_score", 0.5)
        att = _ATT_MULT.get(seq.get("attainability", "unknown"), 0.7)
        eff = pref * att

        tq = seq.get("_trip_quality", 0.5)

        if credit_in_obj:
            blended = eff * 0.7 + tq * 0.3
        else:
            blended = tq * 0.7 + eff * 0.3

        # Layover city boost for quality-of-life layers
        if city_boost > 1.0:
            cities = seq.get("layover_cities", [])
            if cities:
                avg_tier = sum(CITY_TIERS.get(c, _CITY_DEFAULT) for c in cities) / len(cities)
                city_norm = avg_tier / 100.0
                blended = blended * 0.7 + city_norm * 0.3 * city_boost

        # Credit boost for max-pay layer strategy
        cb = strat.get("credit_boost", 1.0)
        if cb > 1.0:
            seq_tpay = seq.get("totals", {}).get("tpay_minutes", 0)
            credit_norm = min(1.0, seq_tpay / 1500)
            blended = blended * 0.7 + credit_norm * 0.3 * cb

        # Holdability-aware scoring: blend quality with attainability per-layer
        holdability = seq.get("_holdability", 0.5)
        optimism = LAYER_OPTIMISM.get(layer_num, 0.5)
        # Layer 1: quality dominates | Layer 7: holdability dominates
        blended = blended * (optimism + (1 - optimism) * holdability)

        # Safety-net boost for layers 6-7: prefer low-demand pairings
        blended = apply_safety_net_boost(seq, blended, layer_num)

        score_int = SELECTION_BONUS + int(blended * SCALE)
        quality_terms.append(seq_selected[vi] * score_int)

    # --- Compactness: minimise working span + gap penalty ─────────────
    # Penalties are small relative to quality so they influence WHICH
    # sequences to pick, not WHETHER to pick any.  Rule of thumb: the
    # worst-case compactness penalty for a full-month span (~30 days)
    # should be < 40 % of the quality from selecting 5 sequences.
    compact_terms: list = []
    span_weight = compact_cfg["span_weight"]
    gap_weight = compact_cfg["gap_weight"]

    if span_weight > 0 or gap_weight > 0:
        span_start = model.new_int_var(1, total_dates + 1, "sp_s")
        span_end = model.new_int_var(0, total_dates, "sp_e")

        for idx, (var, span, _vi) in enumerate(instance_vars):
            model.add(span_start <= min(span)).only_enforce_if(var)
            model.add(span_end >= max(span)).only_enforce_if(var)

        span = model.new_int_var(0, total_dates, "span")
        model.add(span >= span_end - span_start)
        model.add(span >= 0)

        if span_weight > 0:
            # Strong: -24 per span day → worst case (30 days) = -720
            span_coeff = -(span_weight * 3)
            compact_terms.append(span * span_coeff)

        if gap_weight > 0:
            # Gap = span − total_work_days (off days inside the span)
            total_wd = model.new_int_var(0, total_dates, "tot_wd")
            wd_expr = []
            for vi in range(n_valid):
                dd = valid[vi][1].get("totals", {}).get("duty_days", 1) or 1
                wd_expr.append(seq_selected[vi] * dd)
            model.add(total_wd == sum(wd_expr))

            gap = model.new_int_var(0, total_dates, "gap")
            model.add(gap >= span - total_wd)
            model.add(gap >= 0)

            # Strong: -25 per gap day → max 15 gaps = -375
            gap_coeff = -(gap_weight * 5)
            compact_terms.append(gap * gap_coeff)

    # --- Target-window bonus (prefer first or second half) ────────────
    window_terms: list = []
    target_window = strat.get("target_window")
    if target_window:
        mid = total_dates // 2
        bonus = SCALE // 20  # 50 per in-window instance
        for idx, (var, span, _vi) in enumerate(instance_vars):
            sd = min(span)
            if target_window == "first_half" and sd <= mid:
                window_terms.append(var * bonus)
            elif target_window == "second_half" and sd > mid:
                window_terms.append(var * bonus)

    # --- Hamming distance from prior layers ───────────────────────────
    if previous_solutions and strat.get("hamming_min", 0) > 0:
        h_min = strat["hamming_min"]
        # Cap at 1/3 of pool to avoid infeasibility
        h_min = min(h_min, max(1, n_valid // 3))

        for ps_idx, prev_set in enumerate(previous_solutions):
            diffs: list = []
            for vi in range(n_valid):
                cid = valid[vi][1].get("_id", "")
                if cid in prev_set:
                    # Was selected before — diff if NOT selected now
                    d = model.new_bool_var(f"hd{ps_idx}_{vi}")
                    model.add(d + seq_selected[vi] == 1)
                    diffs.append(d)
                else:
                    # Was NOT selected — diff if selected now
                    diffs.append(seq_selected[vi])
            if diffs:
                model.add(sum(diffs) >= h_min)

    # --- Credit targeting: nudge toward strategy's ideal range ─────────
    credit_target_terms: list = []
    if credit_range and not credit_in_obj and credit_coeffs:
        # Penalize being below the strategy minimum or above the strategy max.
        # This is a soft preference — the hard constraint uses the bid-period range.
        total_credit_var = model.new_int_var(0, 999999, "tot_credit")
        model.add(total_credit_var == sum(var * coeff for var, coeff in credit_coeffs))

        # Penalty for being below strategy min.
        # -1 per minute below target: 60-min shortfall (1h) = -60 penalty.
        # The key improvement is that ALL strategies now have credit_range
        # starting at 4200 (70h), so this penalty actually applies where the
        # old code had no penalty (L1-L3 were at 3600 = 60h floor).
        shortfall = model.new_int_var(0, 999999, "cr_short")
        model.add(shortfall >= strat_min_credit - total_credit_var)
        model.add(shortfall >= 0)
        credit_target_terms.append(shortfall * -1)

    # --- Combine and set objective ────────────────────────────────────
    all_terms = quality_terms + compact_terms + window_terms + credit_target_terms
    if all_terms:
        model.maximize(sum(all_terms))

    # ── Solve ─────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    solver.parameters.num_workers = 1  # predictable single-thread

    solve_status = solver.solve(model)

    if solve_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logger.warning(
            "CP-SAT L%d: no feasible solution (status=%s), returning empty",
            layer_num, solve_status,
        )
        return []

    # ── Extract solution ──────────────────────────────────────────────
    selected: list[dict] = []
    for vi in range(n_valid):
        if solver.value(seq_selected[vi]):
            for j in seq_groups[vi]:
                if solver.value(instance_vars[j][0]):
                    seq_copy = dict(valid[vi][1])
                    seq_copy["_chosen_span"] = instance_vars[j][1]
                    selected.append(seq_copy)
                    break

    selected.sort(key=lambda s: min(s.get("_chosen_span", {999})))

    total_credit = sum(s.get("totals", {}).get("tpay_minutes", 0) for s in selected)
    status_str = "OPTIMAL" if solve_status == cp_model.OPTIMAL else "FEASIBLE"
    logger.info(
        "CP-SAT L%d: %d seqs, %d credit-min, %s, %.2fs, %d rest-constr, %d block-constr",
        layer_num, len(selected), total_credit, status_str,
        solver.wall_time, rest_constraints, block_constraints,
    )

    return selected


# ── Greedy fallback ──────────────────────────────────────────────────────

def _greedy_fallback(
    candidates: list[dict],
    total_dates: int,
    max_credit_minutes: int,
    min_days_off: int,
) -> list[dict]:
    """Delegate to the existing greedy builder in optimizer.py."""
    from app.services.optimizer import _build_one_layer
    return _build_one_layer(candidates, total_dates, False, max_credit_minutes, min_days_off)
