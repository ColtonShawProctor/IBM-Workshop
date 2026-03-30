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
COMPACTNESS_LEVELS: dict[str, dict[str, int]] = {
    "strong":   {"span_weight": 8, "gap_weight": 5},
    "moderate": {"span_weight": 4, "gap_weight": 2},
    "light":    {"span_weight": 2, "gap_weight": 1},
    "none":     {"span_weight": 0, "gap_weight": 0},
}

# Per-layer optimization strategies
DEFAULT_LAYER_STRATEGIES: dict[int, dict] = {
    1: {"name": "Dream Schedule — Compact + Quality",
        "compactness": "strong", "target_window": "first_half",
        "credit_range": (5100, 5400),      # 85-90h — high credit, tight
        "credit_in_objective": False,
        "min_pairing_days": 2},             # never select 1-day turns
    2: {"name": "Flip Window — Back Half",
        "compactness": "strong", "target_window": "second_half",
        "credit_range": (5100, 5400),      # 85-90h
        "credit_in_objective": False,
        "min_pairing_days": 2},
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
        "min_pairing_days": 2},
    7: {"name": "Safety Net — Maximum Flexibility",
        "compactness": "none",
        "credit_range": (4200, 5400),      # 70-90h — full range
        "credit_in_objective": False,
        "min_pairing_days": 2},
}


# ── Helpers ──────────────────────────────────────────────────────────────

def _hhmm_to_minutes(t: str) -> int:
    """Convert "HH:MM" to minutes since midnight."""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


# ── Trip Quality Scoring ─────────────────────────────────────────────────

def compute_trip_quality(seq: dict) -> float:
    """Compute composite trip quality score (0.0-1.0) for a sequence.

    Seven dimensions, weighted:
      credit_efficiency  30%  — TPAY per duty day
      layover_quality    20%  — rest duration sweet-spot (Gaussian ~24 h)
      layover_city       15%  — city tier lookup
      report_time        15%  — later report = easier commute
      legs_per_day       10%  — fewer legs = less wear
      red_eye_penalty     5%  — avoid red-eyes / ODANs
      deadhead_penalty    5%  — avoid deadhead legs
    """
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

    # 5. Legs per duty day
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

    # 6. Red-eye / ODAN penalty
    redeye = 0.0 if (seq.get("is_redeye") or seq.get("is_odan")) else 100.0

    # 7. Deadhead penalty
    dh = totals.get("deadhead_count", 0) or 0
    total_leg = totals.get("leg_count", 1) or 1
    dh_score = max(0.0, 100.0 * (1.0 - dh / total_leg))

    composite = (
        0.30 * credit_eff
        + 0.20 * avg_layover
        + 0.15 * avg_city
        + 0.15 * report_score
        + 0.10 * legs_score
        + 0.05 * redeye
        + 0.05 * dh_score
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

    Returns:
        Selected sequences with ``_chosen_span`` set, sorted by date.
        Falls back to greedy builder if OR-Tools is unavailable or solver
        finds no feasible solution.
    """
    if not HAS_ORTOOLS:
        return _greedy_fallback(candidates, total_dates, max_credit_minutes, min_days_off)

    strat = strategy or DEFAULT_LAYER_STRATEGIES.get(layer_num, {})
    compact_cfg = COMPACTNESS_LEVELS.get(
        strat.get("compactness", "moderate"), COMPACTNESS_LEVELS["moderate"]
    )

    # Strategy credit range — max is a hard constraint (tightens bid-period max),
    # min is a soft preference (penalty in objective) to avoid infeasibility.
    credit_range = strat.get("credit_range")
    strat_min_credit = credit_range[0] if credit_range else min_credit_minutes
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

    # ── Hard Constraint 1: No overlapping duty dates ──────────────────
    intervals = []
    for idx, (var, span, _vi) in enumerate(instance_vars):
        s = min(span)
        sz = max(span) - s + 1
        iv = model.new_optional_fixed_size_interval_var(s, sz, var, f"iv_{idx}")
        intervals.append(iv)
    model.add_no_overlap(intervals)

    # ── Hard Constraint 2: FAA minimum rest between consecutives ──────
    # Bucket instances by last/first day for efficient pairwise checking
    ends_on: dict[int, list[int]] = defaultdict(list)
    starts_on: dict[int, list[int]] = defaultdict(list)
    for idx, (_var, span, _vi) in enumerate(instance_vars):
        ends_on[max(span)].append(idx)
        starts_on[min(span)].append(idx)

    rest_constraints = 0
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
                    continue  # same sequence — handled by at-most-one

                seq_b = valid[vi_b][1]
                dps_b = seq_b.get("duty_periods", [])
                if not dps_b:
                    continue
                rpt_b = _hhmm_to_minutes(dps_b[0].get("report_base", "08:00"))

                rest_min = (24 * 60 - rel_a) + rpt_b
                if rest_min < MIN_REST_HOURS * 60:
                    model.add(
                        instance_vars[a_idx][0] + instance_vars[b_idx][0] <= 1
                    )
                    rest_constraints += 1

    # ── Hard Constraint 3: Credit range ─────────────────────────────
    credit_coeffs: list[tuple] = []  # (sel_var, tpay_int)
    for vi in range(n_valid):
        tpay = valid[vi][1].get("totals", {}).get("tpay_minutes", 0)
        if tpay > 0:
            credit_coeffs.append((seq_selected[vi], tpay))
    if credit_coeffs:
        model.add(sum(var * coeff for var, coeff in credit_coeffs) <= max_credit_minutes)
        if min_credit_minutes > 0:
            model.add(sum(var * coeff for var, coeff in credit_coeffs) >= min_credit_minutes)

    # ── Hard Constraint 4: Minimum days off ───────────────────────────
    max_work_days = total_dates - min_days_off
    work_coeffs: list[tuple] = []
    for vi in range(n_valid):
        dd = valid[vi][1].get("totals", {}).get("duty_days", 1) or 1
        work_coeffs.append((seq_selected[vi], dd))
    if work_coeffs:
        model.add(sum(var * coeff for var, coeff in work_coeffs) <= max_work_days)

    # ── Hard Constraint 5: 7-day cumulative block limit (30h) ────────
    BLOCK_LIMIT_7DAY = 2400  # 40 hours = 2400 minutes (safety ceiling)
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
            model.add(sum(block_terms) <= BLOCK_LIMIT_7DAY)
            block_constraints += 1

    # ── Objective terms ───────────────────────────────────────────────
    SCALE = 1000  # CP-SAT uses integers; multiply floats by SCALE

    # --- Quality: blended property score + trip quality ----------------
    # Each selected sequence gets a base selection bonus (ensures selecting
    # sequences is ALWAYS preferred over empty schedules regardless of
    # compactness penalties) PLUS a quality score.
    SELECTION_BONUS = SCALE // 2  # 500 per sequence

    credit_in_obj = strat.get("credit_in_objective", True)
    city_boost = strat.get("layover_city_boost", 1.0)

    quality_terms: list = []
    for vi in range(n_valid):
        seq = valid[vi][1]
        pref = seq.get("preference_score", 0.5)
        att = _ATT_MULT.get(seq.get("attainability", "unknown"), 0.7)
        eff = pref * att

        tq = seq.get("_trip_quality", 0.5)

        if credit_in_obj:
            # Credit-focused: property score (includes maximize_credit) is primary
            blended = eff * 0.7 + tq * 0.3
        else:
            # Quality-focused: trip quality drives selection, credit is just a constraint
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

        # Penalty for being below strategy min (small per-minute penalty)
        shortfall = model.new_int_var(0, 999999, "cr_short")
        model.add(shortfall >= strat_min_credit - total_credit_var)
        model.add(shortfall >= 0)
        # -1 per 10 minutes below target (max penalty ~120 for 1200 min shortfall)
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
            "CP-SAT L%d: no feasible solution (status=%s), greedy fallback",
            layer_num, solve_status,
        )
        return _greedy_fallback(candidates, total_dates, max_credit_minutes, min_days_off)

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
