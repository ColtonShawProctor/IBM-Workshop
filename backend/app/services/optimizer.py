"""Bid optimization engine — builds 9 valid schedule layers.

Each layer is a set of non-conflicting sequences that forms a legal monthly
schedule.  Sequences within a layer have no overlapping duty dates and respect
FAA minimum rest (10 h between sequences).  Layer 1 is the dream schedule,
Layer 9 is the safety-net fallback.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# FAA FAR 117 minimum rest between sequences (hours)
MIN_REST_HOURS = 10

# IPD destination stations: Europe, Asia, Deep South America
_IPD_STATIONS = {
    # Europe
    "LHR", "CDG", "FCO", "BCN", "MAD", "AMS", "FRA", "MUC", "ZRH", "DUB",
    "MXP", "LGW", "EDI", "ATH", "PRG", "BUD", "VCE", "LIS",
    # Asia
    "NRT", "HND", "ICN", "PVG", "HKG", "PEK", "BKK", "SIN", "DEL", "BOM",
    "TPE", "MNL", "KIX", "CTS",
    # Deep South America
    "GRU", "EZE", "SCL", "GIG", "LIM", "BOG",
}


# ── Helpers ──────────────────────────────────────────────────────────────


def _hhmm_to_minutes(t: str) -> int:
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _extract_day_from_property(value, total_dates: int) -> int | None:
    """Convert a property value (int day number or date string) to a day number."""
    if isinstance(value, int):
        return value if 1 <= value <= total_dates else None
    if isinstance(value, str):
        # Try as day number first
        try:
            d = int(value)
            return d if 1 <= d <= total_dates else None
        except ValueError:
            pass
        # Try as date string "YYYY-MM-DD" — extract day of month
        try:
            return int(value.split("-")[2])
        except (IndexError, ValueError):
            return None
    return None


def _all_possible_date_spans(seq: dict) -> list[set[int]]:
    """Return a list of date-spans, one per OPS instance.

    A 3-duty-day trip with operating_dates [5, 10, 15] has three instances:
    {5,6,7}, {10,11,12}, {15,16,17}.  The FA is awarded ONE of these.
    """
    duty_days = seq.get("totals", {}).get("duty_days", 1) or 1
    spans: list[set[int]] = []
    for start in seq.get("operating_dates", []):
        spans.append(set(range(start, start + duty_days)))
    return spans


def _occupied_dates(seq: dict) -> set[int]:
    """All dates this sequence COULD occupy (union of all OPS instances)."""
    spans = _all_possible_date_spans(seq)
    result: set[int] = set()
    for span in spans:
        result |= span
    return result


def _last_release_minutes(seq: dict) -> Optional[int]:
    """Return the release time in minutes for the last duty period."""
    dps = seq.get("duty_periods", [])
    if not dps:
        return None
    t = dps[-1].get("release_base")
    if not t:
        return None
    return _hhmm_to_minutes(t)


def _first_report_minutes(seq: dict) -> Optional[int]:
    """Return the report time in minutes for the first duty period."""
    dps = seq.get("duty_periods", [])
    if not dps:
        return None
    t = dps[0].get("report_base")
    if not t:
        return None
    return _hhmm_to_minutes(t)


def _rest_ok(prev_seq: dict, next_seq: dict) -> bool:
    """Check FAA minimum rest between two back-to-back sequences.

    If the last day of prev_seq is immediately followed by the first day of
    next_seq, we need at least MIN_REST_HOURS between release and report.
    """
    prev_dates = _occupied_dates(prev_seq)
    next_dates = _occupied_dates(next_seq)
    if not prev_dates or not next_dates:
        return True  # can't check, assume ok

    prev_last = max(prev_dates)
    next_first = min(next_dates)

    # Not back-to-back — at least one day gap
    if next_first > prev_last + 1:
        return True

    # Same day or consecutive day — check times
    if next_first <= prev_last:
        return False  # overlapping dates

    # Consecutive days (next_first == prev_last + 1) — check rest
    release = _last_release_minutes(prev_seq)
    report = _first_report_minutes(next_seq)
    if release is None or report is None:
        return True  # can't check, assume ok

    # Release on day N, report on day N+1
    # rest = (24:00 - release) + report  (overnight gap)
    rest_minutes = (24 * 60 - release) + report
    return rest_minutes >= MIN_REST_HOURS * 60


# ── Phase 1: Preference Scoring ───────────────────────────────────────────


def _score_tpay(seq: dict, prefs: dict) -> float:
    tpay = seq.get("totals", {}).get("tpay_minutes", 0)
    lo = prefs.get("tpay_min_minutes")
    hi = prefs.get("tpay_max_minutes")
    if lo is None and hi is None:
        return 0.5
    if lo is not None and hi is not None:
        if lo <= tpay <= hi:
            return 1.0
        spread = max(hi - lo, 1)
        if tpay < lo:
            return max(0.0, 1.0 - (lo - tpay) / spread)
        return max(0.0, 1.0 - (tpay - hi) / spread)
    if lo is not None:
        return 1.0 if tpay >= lo else max(0.0, tpay / lo)
    return 1.0 if tpay <= hi else max(0.0, 1.0 - (tpay - hi) / hi)  # type: ignore[operator]


def _score_days_off(seq: dict, prefs: dict) -> float:
    blocked = set(prefs.get("preferred_days_off", []))
    if not blocked:
        return 1.0
    # For multi-OPS: score based on best possible instance (at least one
    # instance that doesn't conflict with preferred days off)
    spans = _all_possible_date_spans(seq)
    if not spans:
        return 1.0
    # Fraction of instances that DON'T conflict with preferred days off
    clean = sum(1 for span in spans if not (blocked & span))
    return clean / len(spans) if spans else 1.0


def _score_layover_city(seq: dict, prefs: dict) -> float:
    preferred = set(prefs.get("preferred_layover_cities", []))
    avoided = set(prefs.get("avoided_layover_cities", []))
    cities = seq.get("layover_cities", [])
    if not cities:
        return 0.5
    scores = []
    for c in cities:
        if c in avoided:
            scores.append(0.0)
        elif c in preferred:
            scores.append(1.0)
        else:
            scores.append(0.5)
    return sum(scores) / len(scores) if scores else 0.5


def _score_equipment(seq: dict, prefs: dict) -> float:
    preferred = set(prefs.get("preferred_equipment", []))
    if not preferred:
        return 0.5
    dps = seq.get("duty_periods", [])
    eqs = {lg.get("equipment") for dp in dps for lg in dp.get("legs", [])}
    if not eqs:
        return 0.5
    return 1.0 if eqs & preferred else 0.5


def _score_time_window(
    seq: dict, prefs: dict,
    field_earliest: str, field_latest: str,
    time_key: str, dp_index: int,
) -> float:
    earliest = prefs.get(field_earliest)
    latest = prefs.get(field_latest)
    if earliest is None and latest is None:
        return 0.5
    dps = seq.get("duty_periods", [])
    if not dps:
        return 0.5
    dp = dps[dp_index] if abs(dp_index) <= len(dps) else dps[0]
    t = dp.get(time_key)
    if not t:
        return 0.5
    mins = _hhmm_to_minutes(t)
    if earliest is not None and latest is not None:
        if earliest <= mins <= latest:
            return 1.0
        spread = max(latest - earliest, 1)
        if mins < earliest:
            return max(0.0, 1.0 - (earliest - mins) / spread)
        return max(0.0, 1.0 - (mins - latest) / spread)
    if earliest is not None:
        return 1.0 if mins >= earliest else max(0.0, mins / earliest if earliest else 1.0)
    return 1.0 if mins <= latest else max(0.0, 1.0 - (mins - latest) / (latest if latest else 1))  # type: ignore[operator]


def _score_redeye(seq: dict, prefs: dict) -> float:
    if prefs.get("avoid_redeyes") and seq.get("is_redeye"):
        return 0.0
    return 1.0


def _score_trip_length(seq: dict, prefs: dict) -> float:
    prefer_turns = prefs.get("prefer_turns")
    if prefer_turns is None:
        return 0.5
    is_turn = seq.get("is_turn", False)
    return 1.0 if is_turn == prefer_turns else 0.5


def score_sequence(seq: dict, prefs: dict) -> float:
    """Phase 1: Compute weighted preference score (0.0-1.0) for a sequence."""
    weights = prefs.get("weights", {})
    criteria = [
        (weights.get("tpay", 5), _score_tpay(seq, prefs)),
        (weights.get("days_off", 5), _score_days_off(seq, prefs)),
        (weights.get("layover_city", 5), _score_layover_city(seq, prefs)),
        (weights.get("equipment", 5), _score_equipment(seq, prefs)),
        (weights.get("report_time", 5), _score_time_window(
            seq, prefs, "report_earliest_minutes", "report_latest_minutes", "report_base", 0)),
        (weights.get("release_time", 5), _score_time_window(
            seq, prefs, "release_earliest_minutes", "release_latest_minutes", "release_base", -1)),
        (weights.get("redeye", 5), _score_redeye(seq, prefs)),
        (weights.get("trip_length", 5), _score_trip_length(seq, prefs)),
    ]
    total_weight = sum(w for w, _ in criteria)
    if total_weight == 0:
        return 0.5
    weighted_sum = sum(w * s for w, s in criteria)
    return round(weighted_sum / total_weight, 4)


# ── Phase 2: Attainability Estimation ─────────────────────────────────────


ATTAINABILITY_MULT = {"high": 1.0, "medium": 0.8, "low": 0.5, "unknown": 0.7}


def estimate_attainability(
    seq: dict, seniority_number: int, total_base_fas: int, user_langs: list[str],
    seniority_percentage: float | None = None,
    all_sequences: list[dict] | None = None,
) -> str:
    """Estimate attainability using seniority-aware holdability model.

    Uses Level 1 heuristic from holdability.py when seniority data is available.
    When Level 3 empirical survival curves are cached, blends 80% empirical +
    20% heuristic for improved accuracy.
    Also stores the numeric holdability on seq["_holdability"] for use by the
    explainer and CP-SAT objective.
    """
    from app.services.holdability import (
        compute_attainability as compute_att,
        compute_pairing_desirability,
        compute_pool_supply,
        get_cached_survival_curves,
        lookup_survival,
    )

    # Use seniority_percentage directly if provided (from PBS portal)
    if seniority_percentage is not None:
        percentile = seniority_percentage / 100.0
    elif total_base_fas and total_base_fas > 0:
        percentile = seniority_number / total_base_fas
    else:
        seq["_holdability"] = 0.5
        return "unknown"

    # Compute desirability and pool supply for Level 1 holdability
    desirability = compute_pairing_desirability(seq)
    pool_supply = compute_pool_supply(seq, all_sequences) if all_sequences else 10

    # Level 1 holdability (numeric 0.0-1.0)
    heuristic_att = compute_att(
        seniority_number, total_base_fas, desirability, pool_supply,
        seniority_percentage=seniority_percentage,
    )

    # Language bonus -- language-qualified sequences have less competition
    lang = seq.get("language")
    if lang and lang in user_langs:
        heuristic_att = min(1.0, heuristic_att + 0.15)

    # OPS count bonus -- more instances = more likely to survive
    ops = seq.get("ops_count", 1)
    ops_bonus = min(ops / 25.0, 1.0) * 0.1
    heuristic_att = min(1.0, heuristic_att + ops_bonus)

    # Level 3: blend with empirical survival curves if available
    curves = get_cached_survival_curves()
    if curves:
        # Extract report time from first duty period
        dps = seq.get("duty_periods", [])
        report_time = ""
        if dps:
            rpt_str = dps[0].get("report_base", "")
            report_time = rpt_str.replace(":", "")

        # Block minutes for credit band classification
        totals = seq.get("totals", {})
        block_min = totals.get("block_minutes", 0) or totals.get("tpay_minutes", 0) or 0

        empirical = lookup_survival(
            curves, percentile,
            block_minutes=block_min,
            report_time=report_time,
        )
        if empirical is not None:
            # 80% empirical + 20% heuristic
            numeric_att = 0.8 * empirical + 0.2 * heuristic_att
        else:
            numeric_att = heuristic_att
    else:
        numeric_att = heuristic_att

    # Store numeric holdability for explainer and CP-SAT
    seq["_holdability"] = round(numeric_att, 3)

    # Map to categorical for backward compatibility
    if numeric_att >= 0.70:
        return "high"
    elif numeric_att >= 0.40:
        return "medium"
    else:
        return "low"


# ── Layer Builder ─────────────────────────────────────────────────────────


def _effective_score(seq: dict) -> float:
    return seq.get("preference_score", 0) * ATTAINABILITY_MULT.get(
        seq.get("attainability", "unknown"), 0.7
    )


def _rest_ok_spans(span_a: set[int], seq_a: dict,
                   span_b: set[int], seq_b: dict) -> bool:
    """Check FAA minimum rest between two sequences using their chosen spans.

    Automatically determines chronological order.
    """
    if not span_a or not span_b:
        return True

    # Date overlap — never ok
    if span_a & span_b:
        return False

    # Determine which comes first chronologically
    a_last = max(span_a)
    b_first = min(span_b)
    b_last = max(span_b)
    a_first = min(span_a)

    # Check both orderings
    if a_last < b_first:
        # A finishes before B starts
        if b_first > a_last + 1:
            return True  # gap of 2+ days, rest guaranteed
        # Consecutive days — check rest
        release = _last_release_minutes(seq_a)
        report = _first_report_minutes(seq_b)
        if release is None or report is None:
            return True
        rest_minutes = (24 * 60 - release) + report
        return rest_minutes >= MIN_REST_HOURS * 60
    elif b_last < a_first:
        # B finishes before A starts
        if a_first > b_last + 1:
            return True
        release = _last_release_minutes(seq_b)
        report = _first_report_minutes(seq_a)
        if release is None or report is None:
            return True
        rest_minutes = (24 * 60 - release) + report
        return rest_minutes >= MIN_REST_HOURS * 60
    else:
        # Overlapping
        return False


def _build_one_layer(
    candidates: list[dict],
    total_dates: int,
    cluster_trips: bool,
    max_credit_minutes: int = 5400,
    min_days_off: int = 11,
) -> list[dict]:
    """Build one valid monthly schedule respecting CBA limits.

    A layer = a realistic schedule an FA could actually fly in one month.
    Constraints:
    - No date conflicts (no overlapping duty days)
    - FAA minimum rest between consecutive sequences
    - Credit hours within Line of Time (default max 90h = 5400 min)
    - Minimum days off (default 11 per CBA §11.H)
    """
    occupied: set[int] = set()
    selected: list[dict] = []
    selected_spans: list[set[int]] = []
    total_credit: int = 0

    ranked = sorted(candidates, key=_effective_score, reverse=True)

    for seq in ranked:
        spans = seq.get("_all_spans", [])
        if not spans:
            continue

        # Would adding this sequence exceed credit limit?
        seq_credit = seq.get("totals", {}).get("tpay_minutes", 0)
        if total_credit + seq_credit > max_credit_minutes:
            continue

        # Would adding this sequence leave too few days off?
        seq_duty_days = seq.get("totals", {}).get("duty_days", 1) or 1
        current_duty_days = len(occupied)
        if (current_duty_days + seq_duty_days) > (total_dates - min_days_off):
            continue

        best_span: set[int] | None = None
        for span in spans:
            if span & occupied:
                continue

            rest_ok = True
            for i, prev in enumerate(selected):
                prev_span = selected_spans[i]
                if not _rest_ok_spans(prev_span, prev, span, seq):
                    rest_ok = False
                    break
            if not rest_ok:
                continue

            best_span = span
            break

        if best_span is None:
            continue

        seq_copy = dict(seq)
        seq_copy["_chosen_span"] = best_span
        selected.append(seq_copy)
        selected_spans.append(best_span)
        occupied |= best_span
        total_credit += seq_credit

    selected.sort(key=lambda s: min(s.get("_chosen_span", {999})))

    return selected


def build_layers(
    scored_sequences: list[dict],
    total_dates: int,
    cluster_trips: bool,
    num_layers: int = 9,
    max_credit_minutes: int = 5400,
) -> list[list[dict]]:
    """Build N layers, each a valid non-conflicting schedule.

    Layer 1 uses the best sequences.  Layer 2 picks the best from what's left
    (or alternative sequences for the same dates).  Each subsequent layer
    degrades gracefully.
    """
    # Pre-compute all possible date spans for each sequence
    for seq in scored_sequences:
        seq["_all_spans"] = _all_possible_date_spans(seq)

    # Filter to sequences that have date info
    with_dates = [s for s in scored_sequences if s["_all_spans"]]
    without_dates = [s for s in scored_sequences if not s["_all_spans"]]

    if without_dates:
        logger.info(
            "%d sequences have no operating dates and are excluded from layers",
            len(without_dates),
        )

    layers: list[list[dict]] = []
    used_in_prior_layers: set[str] = set()

    for layer_idx in range(num_layers):
        # For each layer, all sequences are candidates, but we prefer
        # sequences not used in prior layers.  This creates variety.
        # Score bonus for fresh sequences (not in prior layers).
        candidates = []
        for seq in with_dates:
            sid = seq["_id"]
            # Create a copy with adjusted score if already used
            if sid in used_in_prior_layers:
                # Penalize reuse — push to later layers
                adj = dict(seq)
                adj["preference_score"] = seq["preference_score"] * 0.6
                candidates.append(adj)
            else:
                candidates.append(seq)

        layer = _build_one_layer(candidates, total_dates, cluster_trips,
                                 max_credit_minutes=max_credit_minutes,
                                 min_days_off=11)
        layers.append(layer)

        # Track which sequences were used
        for seq in layer:
            used_in_prior_layers.add(seq["_id"])

    return layers


# ── Rationale Generation ─────────────────────────────────────────────────


def generate_rationale(seq: dict, pref_score: float, attainability: str, prefs: dict) -> str:
    parts = []

    tpay = seq.get("totals", {}).get("tpay_minutes", 0)
    hours = tpay // 60
    mins = tpay % 60
    parts.append(f"TPAY {hours}:{mins:02d}")

    duty_days = seq.get("totals", {}).get("duty_days", 0)
    parts.append(f"{duty_days}d trip")

    cities = seq.get("layover_cities", [])
    preferred_cities = set(prefs.get("preferred_layover_cities", []))
    if cities:
        matched = [c for c in cities if c in preferred_cities]
        if matched:
            parts.append(f"layover: {', '.join(matched)} (preferred)")
        else:
            parts.append(f"layover: {', '.join(cities)}")
    else:
        parts.append("turn")

    dates = seq.get("_chosen_span") or _occupied_dates(seq)
    if dates:
        parts.append(f"days {min(dates)}-{max(dates)}")

    lang = seq.get("language")
    if lang:
        parts.append(f"LANG {lang}")

    parts.append(f"{attainability} attainability")
    parts.append(f"{pref_score:.0%} match")

    return "; ".join(parts)


# ── Commute Annotations ──────────────────────────────────────────────────


def annotate_commute(entries: list[dict], sequences: list[dict], commute_from: str) -> None:
    """Add commute_notes to each entry in-place.

    Flags:
    - early_report: report before 10:00 HBT on first duty (need hotel night before or very early commute)
    - late_release: release after 19:00 HBT on last duty (won't get home same day)
    - hotel_nights: number of nights at base hotel needed for commuting
    - back_to_back: previous trip ends day N, this starts day N+1 or N+2 (no time to go home)
    """
    seq_lookup = {s["_id"]: s for s in sequences}

    # Sort active entries by chosen dates for back-to-back detection
    active = sorted(
        [e for e in entries if not e.get("is_excluded")],
        key=lambda e: min(e.get("chosen_dates", e.get("operating_dates", [999]))),
    )

    prev_end_day = 0
    for entry in active:
        seq = seq_lookup.get(entry.get("sequence_id"))
        if not seq:
            continue

        notes = []
        dps = seq.get("duty_periods", [])
        if not dps:
            entry["commute_notes"] = notes
            continue

        # First duty report time
        first_report = dps[0].get("report_base", "12:00")
        rpt_min = _hhmm_to_minutes(first_report)
        first_legs = len(dps[0].get("legs", []))

        # Last duty release time
        last_release = dps[-1].get("release_base", "18:00")
        rls_min = _hhmm_to_minutes(last_release)
        last_legs = len(dps[-1].get("legs", []))

        # Check report time
        if rpt_min < 600:  # before 10:00
            if rpt_min < 420:  # before 07:00 — definitely need hotel
                notes.append(f"Hotel night before: reports {first_report} — no {commute_from}→base flight that early")
            else:
                notes.append(f"Very early commute: reports {first_report} — need early {commute_from}→base flight")

        # Check release time
        if rls_min >= 1140:  # 19:00 or later
            if rls_min >= 1320:  # 22:00 or later — no way home
                notes.append(f"Hotel night after: releases {last_release} — no base→{commute_from} flight that late")
            else:
                notes.append(f"Late release {last_release} — tight for base→{commute_from} flight")

        # First/last duty leg count
        if first_legs > 2:
            notes.append(f"Heavy first day: {first_legs} legs after commuting from {commute_from}")
        if last_legs > 2:
            notes.append(f"Heavy last day: {last_legs} legs before commuting to {commute_from}")

        # Back-to-back with previous trip
        chosen = entry.get("chosen_dates", entry.get("operating_dates", []))
        if chosen:
            start_day = min(chosen)
            gap = start_day - prev_end_day
            if gap <= 1 and prev_end_day > 0:
                notes.append(f"Back-to-back: no time to commute to {commute_from} between trips")
            elif gap == 2 and prev_end_day > 0:
                notes.append(f"Tight turnaround: only 1 day at {commute_from} between trips")

            prev_end_day = max(chosen)

        entry["commute_notes"] = notes


# ── Progressive Relaxation Engine ─────────────────────────────────────────
#
# Default layer strategy: L1 dream → L2 specific → L3 generic(L2) → L4-L7
# progressively widening pools.  Each subsequent layer's pool is a strict
# superset of the prior layer (hard gate — auto-fixed if violated).


POOL_SIZE_TARGETS: dict[int, tuple[int, int]] = {
    3: (40, 80),       # Generic version of L2 — enough combos for PBS
    4: (80, 150),      # Widen one property
    5: (150, 300),     # Widen further
    6: (300, 600),     # Broad domestic
    7: (800, 99999),   # Safety net — everything except garbage
}


def auto_select_l2_picks(
    sequences: list[dict],
    max_picks: int = 25,
) -> list[dict]:
    """Auto-select top 15-25 pairings for L2 when FA hasn't hand-picked.

    Uses trip quality × holdability composite.  Prefers 3-4 day trips for
    compact schedules.
    """
    scored = []
    for seq in sequences:
        tq = seq.get("_trip_quality", 0.5)
        hold = seq.get("_holdability", 0.5)
        dd = seq.get("totals", {}).get("duty_days", 1) or 1
        # Prefer 3-4 day trips (0.2 bonus), penalise 1-day turns
        length_bonus = 0.2 if dd in (3, 4) else (0.0 if dd >= 2 else -0.1)
        composite = tq * 0.5 + hold * 0.3 + length_bonus
        scored.append((composite, seq))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [seq for _, seq in scored[:max_picks]]


def derive_generic_properties(selections: list[dict]) -> dict:
    """Analyze FA's hand-picked L2 pairings and extract common properties.

    These properties define what the FA LIKES about her picks.  Applied as
    generic PBS filters in L3, they capture the same quality of trip while
    giving PBS many more options to build a legal line.

    Returns dict with keys: trip_lengths, layover_cities, report_range,
    release_range, credit_range, equipment.  Values are None when there's
    insufficient data to derive a meaningful filter.
    """
    if not selections:
        return {}

    from collections import Counter

    # ── Trip lengths (all unique duty-day counts) ──
    trip_lengths = sorted(set(
        s.get("totals", {}).get("duty_days", 1) or 1 for s in selections
    ))

    # ── Layover cities — most common (top 10) ──
    city_counts: Counter = Counter()
    for s in selections:
        for c in s.get("layover_cities", []):
            city_counts[c] += 1
    top_cities = [c for c, _ in city_counts.most_common(10)] or None

    # ── Report time range (10th–90th percentile) ──
    report_times: list[int] = []
    for s in selections:
        dps = s.get("duty_periods", [])
        if dps:
            rpt = _hhmm_to_minutes(dps[0].get("report_base", "12:00"))
            report_times.append(rpt)
    report_times.sort()
    if len(report_times) >= 3:
        p10 = report_times[max(0, int(len(report_times) * 0.1))]
        p90 = report_times[min(len(report_times) - 1, int(len(report_times) * 0.9))]
        report_range: tuple[int, int] | None = (p10, p90)
    else:
        report_range = None

    # ── Release time range (10th–90th percentile) ──
    release_times: list[int] = []
    for s in selections:
        dps = s.get("duty_periods", [])
        if dps:
            rel = _hhmm_to_minutes(dps[-1].get("release_base", "18:00"))
            release_times.append(rel)
    release_times.sort()
    if len(release_times) >= 3:
        p10 = release_times[max(0, int(len(release_times) * 0.1))]
        p90 = release_times[min(len(release_times) - 1, int(len(release_times) * 0.9))]
        release_range: tuple[int, int] | None = (p10, p90)
    else:
        release_range = None

    # ── Per-pairing credit range (min×0.9 .. max×1.1) ──
    credits = [
        s.get("totals", {}).get("tpay_minutes", 0)
        for s in selections
        if s.get("totals", {}).get("tpay_minutes", 0) > 0
    ]
    credit_range: tuple[int, int] | None = None
    if credits:
        credit_range = (int(min(credits) * 0.9), int(max(credits) * 1.1))

    # ── Equipment types ──
    equipment: set[str] = set()
    for s in selections:
        for dp in s.get("duty_periods", []):
            for lg in dp.get("legs", []):
                eq = lg.get("equipment")
                if eq:
                    equipment.add(eq)

    return {
        "trip_lengths": trip_lengths,
        "layover_cities": top_cities,
        "report_range": report_range,
        "release_range": release_range,
        "credit_range": credit_range,
        "equipment": sorted(equipment) if equipment else None,
    }


def apply_generic_filter(all_sequences: list[dict], properties: dict) -> list[dict]:
    """Filter sequences using derived generic properties.

    A sequence passes if it matches ALL active (non-None) properties.
    Properties set to None are skipped (no filter).
    """
    result = []
    for seq in all_sequences:
        # Trip length
        tl = properties.get("trip_lengths")
        if tl:
            dd = seq.get("totals", {}).get("duty_days", 1) or 1
            if dd not in tl:
                continue

        # Report time window
        rr = properties.get("report_range")
        if rr:
            dps = seq.get("duty_periods", [])
            if dps:
                rpt = _hhmm_to_minutes(dps[0].get("report_base", "12:00"))
                if rpt < rr[0] or rpt > rr[1]:
                    continue

        # Release time window
        rl = properties.get("release_range")
        if rl:
            dps = seq.get("duty_periods", [])
            if dps:
                rel = _hhmm_to_minutes(dps[-1].get("release_base", "18:00"))
                if rel < rl[0] or rel > rl[1]:
                    continue

        # Layover cities (at least one match; turns with no layovers pass)
        lc = properties.get("layover_cities")
        if lc:
            cities = seq.get("layover_cities", [])
            if cities and not any(c in lc for c in cities):
                continue

        # Equipment
        eq_filter = properties.get("equipment")
        if eq_filter:
            seq_eq: set[str] = set()
            for dp in seq.get("duty_periods", []):
                for lg in dp.get("legs", []):
                    eq = lg.get("equipment")
                    if eq:
                        seq_eq.add(eq)
            if seq_eq and not (seq_eq & set(eq_filter)):
                continue

        # Per-pairing credit range
        cr = properties.get("credit_range")
        if cr:
            tpay = seq.get("totals", {}).get("tpay_minutes", 0)
            if tpay < cr[0] or tpay > cr[1]:
                continue

        result.append(seq)
    return result


def _count_filter_impact(
    all_sequences: list[dict], properties: dict, prop_key: str,
) -> int:
    """Count how many MORE sequences pass if *prop_key* is removed."""
    with_prop = len(apply_generic_filter(all_sequences, properties))
    relaxed = {k: v for k, v in properties.items() if k != prop_key and v is not None}
    without_prop = len(apply_generic_filter(all_sequences, relaxed))
    return without_prop - with_prop


def relax_properties_for_layer(
    base_properties: dict,
    all_sequences: list[dict],
    layer_num: int,
) -> tuple[dict, list[dict], list[str]]:
    """Progressively relax properties to hit pool-size targets.

    Relaxation strategy:
    1. For L6-L7: aggressive widening (broad domestic / safety net)
    2. For L3-L5: measure each property's restrictiveness, relax the
       most restrictive first.  Widen before dropping when possible.

    Returns (relaxed_properties, filtered_pool, relaxation_notes).
    """
    target_min, _ = POOL_SIZE_TARGETS.get(layer_num, (40, 99999))

    # L6: Broad domestic — 2+ day trips only
    if layer_num == 6:
        props: dict = {"trip_lengths": [2, 3, 4, 5]}
        pool = apply_generic_filter(all_sequences, props)
        return props, pool, [f"Broad domestic filter → {len(pool)} pairings"]

    # L7: Safety net — everything except ODANs
    if layer_num >= 7:
        props = {}  # no filters = everything
        pool = list(all_sequences)
        return props, pool, [f"Safety net — all {len(pool)} pairings"]

    # L3-L5: Start from base properties, relax as needed
    props = {k: v for k, v in base_properties.items() if v is not None}
    pool = apply_generic_filter(all_sequences, props)
    notes: list[str] = []

    if len(pool) >= target_min:
        notes.append(f"Derived properties yield {len(pool)} pairings (target: {target_min}+)")
        return props, pool, notes

    # Sort by actual impact — relax the MOST restrictive filter first
    relaxable = [
        ("layover_cities", "layover city filter"),
        ("credit_range", "per-pairing credit range"),
        ("report_range", "report time window"),
        ("release_range", "release time window"),
        ("equipment", "equipment filter"),
        ("trip_lengths", "trip length filter"),
    ]
    impacts = []
    for prop_key, desc in relaxable:
        if prop_key in props and props[prop_key] is not None:
            impact = _count_filter_impact(all_sequences, props, prop_key)
            impacts.append((impact, prop_key, desc))
    impacts.sort(reverse=True)

    for _impact, prop_key, desc in impacts:
        if len(pool) >= target_min:
            break

        # Try widening before dropping
        widened = False
        if prop_key == "report_range" and props.get("report_range"):
            lo, hi = props["report_range"]
            new_range = (max(0, lo - 120), min(1440, hi + 120))
            test = dict(props)
            test["report_range"] = new_range
            test_pool = apply_generic_filter(all_sequences, test)
            if len(test_pool) > len(pool):
                props = test
                pool = test_pool
                notes.append(
                    f"Widened report time to "
                    f"{new_range[0]//60:02d}:{new_range[0]%60:02d}"
                    f"–{new_range[1]//60:02d}:{new_range[1]%60:02d} "
                    f"→ {len(pool)} pairings"
                )
                widened = True
                if len(pool) >= target_min:
                    continue

        if prop_key == "release_range" and props.get("release_range") and not widened:
            lo, hi = props["release_range"]
            new_range = (max(0, lo - 120), min(1440, hi + 120))
            test = dict(props)
            test["release_range"] = new_range
            test_pool = apply_generic_filter(all_sequences, test)
            if len(test_pool) > len(pool):
                props = test
                pool = test_pool
                notes.append(f"Widened release time → {len(pool)} pairings")
                widened = True
                if len(pool) >= target_min:
                    continue

        if prop_key == "trip_lengths" and props.get("trip_lengths") and not widened:
            current = set(props["trip_lengths"])
            expanded = set(current)
            for tl in list(current):
                if tl - 1 >= 2:
                    expanded.add(tl - 1)
                expanded.add(tl + 1)
            test = dict(props)
            test["trip_lengths"] = sorted(expanded)
            test_pool = apply_generic_filter(all_sequences, test)
            if len(test_pool) > len(pool):
                added_lengths = sorted(expanded - current)
                props = test
                pool = test_pool
                notes.append(f"Added {added_lengths}-day trips → {len(pool)} pairings")
                widened = True
                if len(pool) >= target_min:
                    continue

        if prop_key == "credit_range" and props.get("credit_range") and not widened:
            lo, hi = props["credit_range"]
            test = dict(props)
            test["credit_range"] = (int(lo * 0.75), int(hi * 1.25))
            test_pool = apply_generic_filter(all_sequences, test)
            if len(test_pool) > len(pool):
                props = test
                pool = test_pool
                notes.append(f"Widened credit range → {len(pool)} pairings")
                widened = True
                if len(pool) >= target_min:
                    continue

        # Widen didn't help enough or wasn't applicable — drop the filter
        if not widened:
            props.pop(prop_key, None)
            pool = apply_generic_filter(all_sequences, props)
            notes.append(f"Dropped {desc} → {len(pool)} pairings")

    if not notes:
        notes.append(f"Properties yield {len(pool)} pairings")

    return props, pool, notes


def ensure_superset(
    curr_pool: list[dict],
    prev_pool_ids: set[str],
    all_sequences_by_id: dict[str, dict],
) -> tuple[list[dict], list[str]]:
    """Hard gate: ensure current pool is a strict superset of previous pool.

    Adds any missing sequences from the previous layer.  Returns
    (fixed_pool, list_of_added_ids).
    """
    curr_ids = {s["_id"] for s in curr_pool}
    missing = prev_pool_ids - curr_ids

    if not missing:
        return curr_pool, []

    added: list[str] = []
    for mid in sorted(missing):
        if mid in all_sequences_by_id:
            curr_pool.append(all_sequences_by_id[mid])
            added.append(mid)

    logger.info(
        "Superset fix: added %d pairings from prior layer", len(added),
    )
    return curr_pool, added


def pool_health_check(pool_size: int, layer_num: int) -> dict:
    """Assess pool health for a layer.  Returns status dict."""
    if layer_num == 1:
        return {"status": "ok", "note": "Lottery ticket — pool size doesn't matter"}
    if layer_num == 2:
        if pool_size < 15:
            return {"status": "critical", "note": f"Only {pool_size} specific pairings — add 5-10 more if possible"}
        if pool_size < 20:
            return {"status": "warning", "note": f"TIGHT — {pool_size} pairings. If senior FAs take 3-4, PBS can't build a legal line"}
        return {"status": "ok", "note": f"{pool_size} specific pairings — healthy"}

    targets = POOL_SIZE_TARGETS.get(layer_num)
    if not targets:
        return {"status": "ok", "note": f"{pool_size} pairings"}

    target_min, target_max = targets
    if pool_size < int(target_min * 0.75):
        return {"status": "critical", "note": f"Only {pool_size} pairings (need {target_min}+) — PBS will struggle to build a legal line"}
    if pool_size < target_min:
        return {"status": "warning", "note": f"{pool_size} pairings (target: {target_min}+) — consider relaxing a property"}
    return {"status": "ok", "note": f"{pool_size} pairings — healthy"}


def _build_progressive_pools(
    eligible: list[dict],
    pinned_ids: set[str],
) -> tuple[dict[int, list[dict]], dict[int, dict]]:
    """Build per-layer candidate pools using progressive relaxation.

    L1: Full pool (dream / lottery — CP-SAT picks the best schedule)
    L2: Pinned entries (or auto-selected top 15-25)
    L3: Generic properties derived from L2 picks
    L4-L7: Progressively relaxed with superset validation (hard gate)

    Returns (layer_pools, pool_metadata) where layer_pools maps
    layer_num → list of candidate sequences, and pool_metadata maps
    layer_num → {pool_type, notes, derived_properties, health, ...}.
    """
    seq_by_id = {s["_id"]: s for s in eligible}

    # ── L2: Specific picks ──
    if pinned_ids:
        l2_picks = [seq_by_id[sid] for sid in pinned_ids if sid in seq_by_id]
    else:
        l2_picks = auto_select_l2_picks(eligible)

    # ── L1: Dream schedule from full pool ──
    l1_pool = list(eligible)

    # ── Derive generic properties from L2 ──
    derived = derive_generic_properties(l2_picks)
    logger.info(
        "Derived generic properties from %d L2 picks: trip_lengths=%s, "
        "cities=%s, report=%s, equipment=%s",
        len(l2_picks),
        derived.get("trip_lengths"),
        (derived.get("layover_cities") or [])[:5],
        derived.get("report_range"),
        derived.get("equipment"),
    )

    # ── L3: Apply derived properties ──
    l3_props, l3_pool, l3_notes = relax_properties_for_layer(
        derived, eligible, 3,
    )
    # L3 must include L2 picks (superset of L2)
    l2_ids = {s["_id"] for s in l2_picks}
    l3_pool, l3_added = ensure_superset(l3_pool, l2_ids, seq_by_id)
    if l3_added:
        l3_notes.append(f"Added {len(l3_added)} L2 pairings for superset guarantee")

    layers: dict[int, list[dict]] = {1: l1_pool, 2: l2_picks, 3: l3_pool}
    metadata: dict[int, dict] = {
        1: {
            "pool_type": "full",
            "notes": [f"Full pool — {len(l1_pool)} pairings (dream schedule)"],
            "health": pool_health_check(len(l1_pool), 1),
        },
        2: {
            "pool_type": "specific",
            "notes": [
                f"{'Hand-picked' if pinned_ids else 'Auto-selected'}: "
                f"{len(l2_picks)} pairings"
            ],
            "health": pool_health_check(len(l2_picks), 2),
            "pick_count": len(l2_picks),
        },
        3: {
            "pool_type": "generic",
            "derived_properties": l3_props,
            "notes": l3_notes,
            "health": pool_health_check(len(l3_pool), 3),
        },
    }

    # ── L4-L7: Progressive relaxation with superset hard gate ──
    prev_pool_ids = {s["_id"] for s in l3_pool}

    for layer_num in range(4, 8):
        props_relaxed, pool, notes = relax_properties_for_layer(
            derived, eligible, layer_num,
        )

        # Hard gate: ensure superset of previous layer
        pool, added = ensure_superset(pool, prev_pool_ids, seq_by_id)
        if added:
            notes.append(
                f"Added {len(added)} pairings from L{layer_num - 1} "
                f"for superset guarantee"
            )

        layers[layer_num] = pool
        metadata[layer_num] = {
            "pool_type": "relaxed",
            "relaxed_properties": props_relaxed,
            "notes": notes,
            "health": pool_health_check(len(pool), layer_num),
        }
        prev_pool_ids = {s["_id"] for s in pool}

    return layers, metadata


# ── Main Optimize Function ────────────────────────────────────────────────


def optimize_bid(
    sequences: list[dict],
    prefs: dict,
    seniority_number: int,
    total_base_fas: int,
    user_langs: list[str],
    pinned_entries: list[dict],
    excluded_ids: set[str],
    total_dates: int,
    bid_properties: list[dict] | None = None,
    target_credit_min_minutes: int = 4200,
    target_credit_max_minutes: int = 5400,
    seniority_percentage: float | None = None,
    commute_from: str | None = None,
    strategy_mode: str | None = None,
) -> tuple[list[dict], dict | None]:
    """Run the full optimization pipeline and return layered entries.

    Strategy modes:
    - "progressive" (DEFAULT): L1 dream → L2 specific → L3 generic(L2) →
      L4-L7 progressively wider pools.  Superset validation is a hard gate.
    - "themed": Each layer has a different theme (Dream, Max Pay, 4-Day,
      Best Layovers, etc.).  Kept for FAs who prefer this approach.

    Commuter detection is automatic: if commute_from is set, commuter
    scoring weights are applied (report/release time weighted higher).
    """
    # Filter out excluded
    eligible = [s for s in sequences if s["_id"] not in excluded_ids]

    # Auto-detect commuter: commute_from set = commuter
    is_commuter = bool(commute_from)

    # Default strategy: themed when bid_properties provided (property-based
    # filtering per layer), progressive relaxation otherwise (auto pools).
    if strategy_mode is None:
        strategy_mode = "themed" if bid_properties else "progressive"

    # ── Common setup: trip quality, holdability, date spans ──────────────
    from app.services.cpsat_builder import (
        compute_trip_quality, solve_layer_cpsat,
        PROGRESSIVE_LAYER_STRATEGIES, THEMED_LAYER_STRATEGIES,
    )
    from app.services.pdf_parser import enrich_sequence_totals

    for seq in eligible:
        # Ensure TPAY reflects CBA guarantee (fixes uniform 5h/day for DB data)
        enrich_sequence_totals(seq)
        # Ensure is_domestic flag exists (for DB data parsed before this field)
        if "is_domestic" not in seq:
            cat = (seq.get("category") or "").upper()
            seq["is_domestic"] = "INTL" not in cat
        seq["_trip_quality"] = compute_trip_quality(seq, is_commuter=is_commuter)
        seq["attainability"] = estimate_attainability(
            seq, seniority_number, total_base_fas, user_langs,
            seniority_percentage=seniority_percentage,
            all_sequences=eligible,
        )
        if "_all_spans" not in seq:
            seq["_all_spans"] = _all_possible_date_spans(seq)

    with_dates = [s for s in eligible if s.get("_all_spans")]

    # ── Extract waiver properties (apply to ALL layers) ──────────────────
    max_credit = target_credit_max_minutes
    min_days_off = 11          # CBA §11.H default
    block_limit_7day = 1800    # 30h (CBA §11.B default)
    home_rest_min = 690        # 11h + 30min (CBA §11.I contractual)
    double_up_dates: set[int] = set()

    if bid_properties:
        for p in bid_properties:
            pk = p.get("property_key")
            pv = p.get("value")
            if pk == "target_credit_range" and isinstance(pv, dict):
                prop_max = pv.get("end", target_credit_max_minutes)
                max_credit = min(prop_max, target_credit_max_minutes)
            elif pk == "waive_minimum_days_off" and pv:
                min_days_off = 8
            elif pk == "waive_30hrs_in_7_days" and pv:
                block_limit_7day = 2100
            elif pk == "waive_minimum_domicile_rest" and pv:
                home_rest_min = 630
            elif pk == "allow_multiple_pairings" and pv:
                double_up_dates = set(range(1, total_dates + 1))
            elif pk == "allow_double_up_on_date" and pv:
                day = _extract_day_from_property(pv, total_dates)
                if day:
                    double_up_dates.add(day)
            elif pk == "allow_double_up_by_range" and isinstance(pv, dict):
                s = _extract_day_from_property(pv.get("start"), total_dates)
                e = _extract_day_from_property(pv.get("end"), total_dates)
                if s and e:
                    double_up_dates.update(range(s, e + 1))

    # ── Build per-layer pools ────────────────────────────────────────────
    if strategy_mode == "progressive":
        pinned_ids = {
            e["sequence_id"] for e in pinned_entries
            if not e.get("is_excluded")
        }
        layer_pools, pool_metadata = _build_progressive_pools(
            with_dates, pinned_ids,
        )
        strategy_set = PROGRESSIVE_LAYER_STRATEGIES
    elif bid_properties:
        # Themed mode with bid_properties
        layer_pools, pool_metadata = _build_themed_pools(
            with_dates, eligible, bid_properties,
        )
        strategy_set = THEMED_LAYER_STRATEGIES
    else:
        # Preference fallback (no properties, no progressive)
        return _optimize_preference_fallback(
            eligible, sequences, prefs, seniority_number, total_base_fas,
            user_langs, excluded_ids, total_dates, target_credit_max_minutes,
            seniority_percentage, commute_from,
        )

    # ── Score sequences per layer pool ───────────────────────────────────
    num_layers = 7
    layers: list[list[dict]] = []
    layers_explanation_data: list[dict] = []
    used_in_prior: set[str] = set()
    previous_solutions: list[set[str]] = []

    for layer_num in range(1, num_layers + 1):
        candidates_raw = layer_pools.get(layer_num, with_dates)

        # Score sequences for this layer
        for seq in candidates_raw:
            if bid_properties:
                seq["preference_score"] = score_sequence_from_properties(
                    seq, bid_properties, layer_num,
                )
            elif "preference_score" not in seq:
                seq["preference_score"] = score_sequence(seq, prefs)

        # Filter to sequences with date info
        candidates_raw = [s for s in candidates_raw if s.get("_all_spans")]

        # Penalize reuse from prior layers (encourages diversity)
        candidates = []
        for seq in candidates_raw:
            if seq["_id"] in used_in_prior:
                adj = dict(seq)
                adj["_all_spans"] = seq["_all_spans"]
                adj["preference_score"] = seq.get("preference_score", 0.5) * 0.6
                candidates.append(adj)
            else:
                candidates.append(seq)

        # CP-SAT solver
        strat = strategy_set.get(layer_num, {})
        layer = solve_layer_cpsat(
            candidates, total_dates,
            max_credit_minutes=max_credit,
            min_credit_minutes=target_credit_min_minutes,
            min_days_off=min_days_off,
            layer_num=layer_num,
            previous_solutions=previous_solutions,
            strategy=strat,
            block_limit_7day_minutes=block_limit_7day,
            home_rest_minutes=home_rest_min,
            double_up_dates=double_up_dates or None,
        )
        layers.append(layer)

        # Collect explanation metadata
        total_credit_min = sum(
            s.get("totals", {}).get("tpay_minutes", 0) for s in layer
        )
        working_dates: set[int] = set()
        for s in layer:
            working_dates |= set(s.get("_chosen_span", set()))
        holdabilities = [s.get("_holdability", 0.5) for s in layer]
        avg_hold = (
            sum(holdabilities) / len(holdabilities) if holdabilities else 0.5
        )
        span_days = (
            (max(working_dates) - min(working_dates) + 1)
            if working_dates else 0
        )

        meta = pool_metadata.get(layer_num, {})
        layers_explanation_data.append({
            "layer_num": layer_num,
            "strategy_name": strat.get("name", f"Layer {layer_num}"),
            "strategy_mode": strategy_mode,
            "sequences": layer,
            "pool_sequences": candidates,
            "pool_size": len(candidates),
            "selected": layer,
            "total_credit_minutes": total_credit_min,
            "days_off": total_dates - len(working_dates),
            "span_days": span_days,
            "avg_holdability": round(avg_hold * 100, 0),
            "credit_hours": round(total_credit_min / 60, 1),
            "max_credit_minutes": max_credit,
            "min_days_off": min_days_off,
            "total_dates": total_dates,
            "has_double_up": bool(double_up_dates),
            "has_waiver": block_limit_7day > 1800 or home_rest_min < 690,
            # Progressive relaxation metadata
            "pool_metadata": meta,
            "pool_health": meta.get("health", {}),
            "pool_notes": meta.get("notes", []),
            "derived_properties": meta.get("derived_properties"),
            "relaxed_properties": meta.get("relaxed_properties"),
        })

        # Track selections
        layer_ids: set[str] = set()
        for seq in layer:
            used_in_prior.add(seq["_id"])
            layer_ids.add(seq["_id"])
        previous_solutions.append(layer_ids)

    # Log
    for i, layer in enumerate(layers, 1):
        pool_sz = len(layer_pools.get(i, []))
        logger.info(
            "%s L%d: %d selected from %d pool",
            strategy_mode.title(), i, len(layer), pool_sz,
        )

    # ── Flatten to ranked entries ────────────────────────────────────────
    entries: list[dict] = []
    rank = 1
    for layer_idx, layer_seqs in enumerate(layers, start=1):
        ranked_seqs = sorted(layer_seqs, key=_effective_score, reverse=True)
        for seq in ranked_seqs:
            chosen = seq.get("_chosen_span")
            att_val = seq.get("_holdability", 0.5)
            if att_val >= 0.70:
                hold_cat = "LIKELY"
            elif att_val >= 0.40:
                hold_cat = "COMPETITIVE"
            else:
                hold_cat = "LONG SHOT"

            entries.append({
                "rank": rank,
                "sequence_id": seq["_id"],
                "seq_number": seq.get("seq_number", 0),
                "is_pinned": False,
                "is_excluded": False,
                "rationale": generate_rationale(
                    seq, seq.get("preference_score", 0.5),
                    seq.get("attainability", "unknown"), prefs,
                ),
                "preference_score": seq.get("preference_score", 0.5),
                "attainability": seq.get("attainability", "unknown"),
                "holdability_pct": round(att_val * 100, 0),
                "holdability_category": hold_cat,
                "date_conflict_group": f"layer-{layer_idx}",
                "operating_dates": (
                    sorted(chosen) if chosen
                    else seq.get("operating_dates", [])
                ),
                "chosen_dates": sorted(chosen) if chosen else [],
                "layer": layer_idx,
            })
            rank += 1

    # Append excluded entries
    for seq in sequences:
        if seq["_id"] in excluded_ids:
            entries.append({
                "rank": rank,
                "sequence_id": seq["_id"],
                "seq_number": seq.get("seq_number", 0),
                "is_pinned": False,
                "is_excluded": True,
                "rationale": "Excluded by user",
                "preference_score": 0.0,
                "attainability": "unknown",
                "date_conflict_group": None,
                "operating_dates": seq.get("operating_dates", []),
                "layer": 0,
            })
            rank += 1

    # Annotate commute info
    if commute_from:
        annotate_commute(entries, sequences, commute_from)

    # Build explanation data
    explanation_data = None
    if layers_explanation_data:
        try:
            from app.services.explainer import generate_full_explanation
            explanation_data = generate_full_explanation(
                layers_explanation_data,
                seniority_number=seniority_number,
                total_fas=total_base_fas,
                seniority_percentage=seniority_percentage,
                total_dates=total_dates,
            )
        except Exception:
            logger.exception("Failed to generate explanation data")
            explanation_data = None

    return entries, explanation_data


def _build_themed_pools(
    with_dates: list[dict],
    eligible: list[dict],
    bid_properties: list[dict],
) -> tuple[dict[int, list[dict]], dict[int, dict]]:
    """Build per-layer pools using themed strategy (legacy).

    Each layer filters sequences using the user's bid_properties assigned
    to that layer.
    """
    layer_pools: dict[int, list[dict]] = {}
    metadata: dict[int, dict] = {}

    for layer_num in range(1, 8):
        filtered = filter_sequences_for_layer(eligible, bid_properties, layer_num)
        filtered = [s for s in filtered if s.get("_all_spans")]
        layer_pools[layer_num] = filtered
        metadata[layer_num] = {
            "pool_type": "themed",
            "notes": [f"Property filter: {len(filtered)} pairings"],
            "health": pool_health_check(len(filtered), layer_num),
        }

    return layer_pools, metadata


def _optimize_preference_fallback(
    eligible: list[dict],
    all_sequences: list[dict],
    prefs: dict,
    seniority_number: int,
    total_base_fas: int,
    user_langs: list[str],
    excluded_ids: set[str],
    total_dates: int,
    target_credit_max_minutes: int,
    seniority_percentage: float | None,
    commute_from: str | None,
) -> tuple[list[dict], None]:
    """Preference-based fallback (no properties, no progressive).

    Uses the greedy build_layers approach.
    """
    num_layers = 7
    cluster_trips = prefs.get("cluster_trips", False)

    for seq in eligible:
        if "preference_score" not in seq:
            seq["preference_score"] = score_sequence(seq, prefs)
        if "attainability" not in seq:
            seq["attainability"] = estimate_attainability(
                seq, seniority_number, total_base_fas, user_langs,
                seniority_percentage=seniority_percentage,
                all_sequences=eligible,
            )

    layers_default = build_layers(
        eligible, total_dates, cluster_trips,
        num_layers=num_layers,
        max_credit_minutes=target_credit_max_minutes,
    )

    for i, layer in enumerate(layers_default, 1):
        logger.info("Fallback Layer %d: %d sequences", i, len(layer))

    entries: list[dict] = []
    rank = 1
    for layer_idx, layer_seqs in enumerate(layers_default, start=1):
        ranked_seqs = sorted(layer_seqs, key=_effective_score, reverse=True)
        for seq in ranked_seqs:
            chosen = seq.get("_chosen_span")
            entries.append({
                "rank": rank,
                "sequence_id": seq["_id"],
                "seq_number": seq.get("seq_number", 0),
                "is_pinned": False,
                "is_excluded": False,
                "rationale": generate_rationale(
                    seq, seq["preference_score"], seq["attainability"], prefs,
                ),
                "preference_score": seq["preference_score"],
                "attainability": seq["attainability"],
                "date_conflict_group": f"layer-{layer_idx}",
                "operating_dates": (
                    sorted(chosen) if chosen
                    else seq.get("operating_dates", [])
                ),
                "chosen_dates": sorted(chosen) if chosen else [],
                "layer": layer_idx,
            })
            rank += 1

    # Append excluded
    for seq in all_sequences:
        if seq["_id"] in excluded_ids:
            entries.append({
                "rank": rank,
                "sequence_id": seq["_id"],
                "seq_number": seq.get("seq_number", 0),
                "is_pinned": False,
                "is_excluded": True,
                "rationale": "Excluded by user",
                "preference_score": 0.0,
                "attainability": "unknown",
                "date_conflict_group": None,
                "operating_dates": seq.get("operating_dates", []),
                "layer": 0,
            })
            rank += 1

    if commute_from:
        annotate_commute(entries, all_sequences, commute_from)

    return entries, None


# Keep old function names for backward compatibility with tests
def build_conflict_groups(sequences: list[dict]) -> dict[str, str]:
    """Legacy — returns empty conflict groups."""
    return {}


def analyze_coverage(entries: list[dict], total_dates: int) -> dict:
    all_period_dates = set(range(1, total_dates + 1))
    covered: set[int] = set()
    for e in entries:
        if not e.get("is_excluded", False):
            for d in e.get("operating_dates", []):
                covered.add(d)
    covered_in_period = sorted(covered & all_period_dates)
    uncovered = sorted(all_period_dates - covered)
    rate = len(covered_in_period) / total_dates if total_dates > 0 else 0.0
    return {
        "covered_dates": covered_in_period,
        "uncovered_dates": uncovered,
        "coverage_rate": round(rate, 4),
    }


def compute_projected_schedule(
    entries: list[dict],
    sequences: list[dict],
    layer: int,
    total_dates: int = 30,
    credit_min_minutes: int = 4200,
    credit_max_minutes: int = 5400,
) -> dict:
    """Compute a best-case projected schedule for a single layer.

    Greedily selects highest-ranked non-conflicting sequences for the layer
    until adding more would exceed credit max or no candidates remain.

    Returns dict with sequences, total_credit_hours, total_days_off,
    working_dates, off_dates, schedule_shape, within_credit_range.
    """
    seq_lookup = {s.get("_id", s.get("sequence_id", "")): s for s in sequences}

    layer_entries = sorted(
        [e for e in entries if e.get("layer") == layer and not e.get("is_excluded")],
        key=lambda e: e.get("rank", 999),
    )

    selected = []
    used_dates: set[int] = set()
    total_credit = 0

    for entry in layer_entries:
        seq = seq_lookup.get(entry.get("sequence_id"))
        if not seq:
            continue

        op_dates = set(seq.get("operating_dates", []))
        tpay = seq.get("totals", {}).get("tpay_minutes", 0)

        # Skip if date conflict
        if op_dates & used_dates:
            continue

        # Skip if would exceed credit max
        if total_credit + tpay > credit_max_minutes:
            continue

        selected.append({
            "seq_number": seq.get("seq_number", 0),
            "category": seq.get("category", ""),
            "tpay_minutes": tpay,
            "duty_days": seq.get("totals", {}).get("duty_days", 0),
            "operating_dates": sorted(op_dates),
        })
        used_dates |= op_dates
        total_credit += tpay

    credit_hours = round(total_credit / 60, 1)
    all_dates = set(range(1, total_dates + 1))
    working = sorted(used_dates & all_dates)
    off = sorted(all_dates - used_dates)
    days_off = len(off)

    within_range = credit_min_minutes <= total_credit <= credit_max_minutes

    # Classify schedule shape
    if working:
        mid = total_dates / 2
        front_count = sum(1 for d in working if d <= mid)
        back_count = len(working) - front_count
        if front_count > back_count * 2:
            shape_label = "front-loaded"
        elif back_count > front_count * 2:
            shape_label = "back-loaded"
        else:
            # Check for contiguous block
            if working[-1] - working[0] + 1 == len(working):
                shape_label = "block"
            else:
                shape_label = "balanced"
    else:
        shape_label = "empty"

    shape = f"{len(selected)} trips, {credit_hours} credit hours, {days_off} days off, {shape_label}"

    return {
        "layer_number": layer,
        "sequences": selected,
        "total_credit_hours": credit_hours,
        "total_days_off": days_off,
        "working_dates": working,
        "off_dates": off,
        "schedule_shape": shape,
        "within_credit_range": within_range,
    }


# ── PBS Property-Based Filtering (Task 95) ──────────────────────────────────


def _matches_property(seq: dict, prop_key: str, value) -> bool:
    """Test whether a sequence matches a single pairing property.

    Returns True if matched (or property is unknown — pass-through).
    """
    totals = seq.get("totals", {})
    dps = seq.get("duty_periods", [])

    if prop_key == "report_between":
        if not dps:
            return True
        report = _hhmm_to_minutes(dps[0].get("report_base", "00:00"))
        start = value.get("start", 0) if isinstance(value, dict) else 0
        end = value.get("end", 1440) if isinstance(value, dict) else 1440
        return start <= report <= end

    elif prop_key == "release_between":
        if not dps:
            return True
        release = _hhmm_to_minutes(dps[-1].get("release_base", "00:00"))
        start = value.get("start", 0) if isinstance(value, dict) else 0
        end = value.get("end", 1440) if isinstance(value, dict) else 1440
        return start <= release <= end

    elif prop_key == "prefer_pairing_type":
        v = str(value).lower()
        if v == "ipd":
            # Match on is_ipd flag, OR fallback: widebody INTL category with IPD destinations
            if seq.get("is_ipd", False):
                return True
            cat = (seq.get("category") or "").upper()
            if "INTL" in cat and ("777" in cat or "787" in cat):
                # Check destinations for IPD regions (Europe, Asia, Deep South America)
                layover = seq.get("layover_cities", [])
                all_stations = set(layover)
                for dp in dps:
                    for lg in dp.get("legs", []):
                        arr = lg.get("arrival_station", "")
                        if arr:
                            all_stations.add(arr)
                if all_stations & _IPD_STATIONS:
                    return True
            return False
        elif v == "nipd":
            return seq.get("is_nipd", False)
        elif v == "odan":
            return seq.get("is_odan", False)
        elif v == "redeye":
            return seq.get("is_redeye", False)
        elif v == "regular":
            return not any([
                seq.get("is_ipd"), seq.get("is_nipd"), seq.get("is_odan"), seq.get("is_redeye"),
            ])
        return True

    elif prop_key == "prefer_pairing_length":
        duty_days = totals.get("duty_days", 0)
        return duty_days == int(value) if value is not None else True

    elif prop_key == "prefer_duty_period":
        dp_count = len(dps)
        return dp_count == int(value) if value is not None else True

    elif prop_key == "prefer_aircraft":
        eq_code = str(value).upper()
        for dp in dps:
            for leg in dp.get("legs", []):
                if eq_code in str(leg.get("equipment", "")).upper():
                    return True
        return False if dps else True

    elif prop_key == "avoid_aircraft":
        eq_code = str(value).upper()
        for dp in dps:
            for leg in dp.get("legs", []):
                if eq_code in str(leg.get("equipment", "")).upper():
                    return False
        return True

    elif prop_key == "prefer_deadheads":
        return seq.get("has_deadhead", False) if value else True

    elif prop_key == "avoid_deadheads":
        return not seq.get("has_deadhead", False) if value else True

    elif prop_key == "layover_at_city":
        city = str(value).upper()
        return city in [c.upper() for c in seq.get("layover_cities", [])]

    elif prop_key == "avoid_layover_at_city":
        city = str(value).upper()
        return city not in [c.upper() for c in seq.get("layover_cities", [])]

    elif prop_key == "max_landings_per_duty":
        max_val = int(value) if value is not None else 999
        for dp in dps:
            if len(dp.get("legs", [])) > max_val:
                return False
        return True

    elif prop_key == "min_avg_credit_per_duty":
        if not dps:
            return True
        min_min = int(value) if isinstance(value, (int, float)) else 0
        avg = totals.get("tpay_minutes", 0) / len(dps) if dps else 0
        return avg >= min_min

    elif prop_key == "max_tafb_credit_ratio":
        max_ratio = float(value) if value is not None else 999.0
        tpay = totals.get("tpay_minutes", 1) or 1
        tafb = totals.get("tafb_minutes", 0)
        return (tafb / tpay) <= max_ratio

    elif prop_key == "prefer_landing_at_city":
        city = str(value).upper()
        for dp in dps:
            for leg in dp.get("legs", []):
                if leg.get("arrival_station", "").upper() == city:
                    return True
        return False if dps else True

    elif prop_key == "avoid_landing_at_city":
        city = str(value).upper()
        for dp in dps:
            for leg in dp.get("legs", []):
                if leg.get("arrival_station", "").upper() == city:
                    return False
        return True

    elif prop_key == "prefer_one_landing_first_duty":
        if not dps or not value:
            return True
        return len(dps[0].get("legs", [])) == 1

    elif prop_key == "prefer_one_landing_last_duty":
        if not dps or not value:
            return True
        return len(dps[-1].get("legs", [])) == 1

    elif prop_key == "mid_pairing_report_after":
        if len(dps) <= 2:
            return True
        min_min = int(value) if isinstance(value, (int, float)) else 0
        for dp in dps[1:-1]:
            report = _hhmm_to_minutes(dp.get("report_base", "00:00"))
            if report < min_min:
                return False
        return True

    elif prop_key == "mid_pairing_release_before":
        if len(dps) <= 2:
            return True
        max_min = int(value) if isinstance(value, (int, float)) else 1440
        for dp in dps[1:-1]:
            release = _hhmm_to_minutes(dp.get("release_base", "23:59"))
            if release > max_min:
                return False
        return True

    elif prop_key == "max_duty_time_per_duty":
        max_min = int(value) if isinstance(value, (int, float)) else 9999
        for dp in dps:
            if (dp.get("duty_minutes") or 0) > max_min:
                return False
        return True

    elif prop_key == "max_block_per_duty":
        max_min = int(value) if isinstance(value, (int, float)) else 9999
        for dp in dps:
            dp_block = sum(leg.get("block_minutes", 0) for leg in dp.get("legs", []))
            if dp_block > max_min:
                return False
        return True

    elif prop_key == "min_connection_time":
        min_min = int(value) if isinstance(value, (int, float)) else 0
        for dp in dps:
            for leg in dp.get("legs", []):
                gt = leg.get("ground_minutes")
                if gt is not None and leg.get("is_connection") and gt < min_min:
                    return False
        return True

    elif prop_key == "max_connection_time":
        max_min = int(value) if isinstance(value, (int, float)) else 9999
        for dp in dps:
            for leg in dp.get("legs", []):
                gt = leg.get("ground_minutes")
                if gt is not None and leg.get("is_connection") and gt > max_min:
                    return False
        return True

    elif prop_key == "co_terminal_satellite_airport":
        airport = str(value).upper()
        if not dps:
            return True
        first_dep = dps[0].get("legs", [{}])[0].get("departure_station", "").upper() if dps[0].get("legs") else ""
        return first_dep == airport

    elif prop_key == "prefer_language":
        lang = str(value).upper()
        seq_lang = (seq.get("language") or "").upper()
        return seq_lang == lang if seq_lang else True

    # Unknown properties pass through (don't filter)
    return True


def score_sequence_from_properties(
    seq: dict,
    properties: list[dict],
    layer: int,
) -> float:
    """Score how well a sequence matches the user's bid properties for a layer.

    Returns 0.0-1.0.

    Scoring components:
    - Pairing properties: 1.0 if matched, 0.0 if not (filter already removes
      non-matching, so this differentiates in edge cases).
    - Line properties: maximize_credit scores by TPAY, target_credit_range by
      proximity to range.
    - Days Off properties: scoring via days-off impact.
    - Quality tiebreaker: since all filtered sequences match pairing properties
      identically (1.0), a TPAY-based quality signal is blended in at low weight
      to differentiate among equal matches. Higher credit-per-duty-day is better.

    Returns weighted average across components.
    If no properties, returns 0.5 (neutral).
    """
    active = [
        p for p in properties
        if p.get("is_enabled", True) and layer in p.get("layers", [])
    ]

    if not active:
        return 0.5

    scores: list[float] = []

    has_maximize_credit = False

    for prop in active:
        key = prop["property_key"]
        value = prop.get("value")
        cat = prop.get("category", "")

        if cat == "pairing":
            scores.append(1.0 if _matches_property(seq, key, value) else 0.0)

        elif cat == "line":
            if key == "maximize_credit":
                has_maximize_credit = True
                tpay = seq.get("totals", {}).get("tpay_minutes", 0)
                # Normalize: assume 200-1500 min range for broad coverage
                scores.append(min(1.0, max(0.0, (tpay - 200) / 1300)))
            elif key == "target_credit_range":
                tpay = seq.get("totals", {}).get("tpay_minutes", 0)
                if isinstance(value, dict):
                    lo = value.get("start", 0)
                    hi = value.get("end", 9999)
                    if lo <= tpay <= hi:
                        scores.append(1.0)
                    else:
                        spread = max(hi - lo, 1)
                        dist = min(abs(tpay - lo), abs(tpay - hi))
                        scores.append(max(0.0, 1.0 - dist / spread))
                else:
                    scores.append(0.5)
            else:
                scores.append(0.5)  # Line props not directly scoring sequences

        elif cat == "days_off":
            if key == "maximize_total_days_off":
                # Fewer duty days = higher score
                dd = seq.get("totals", {}).get("duty_days", 1) or 1
                scores.append(max(0.0, 1.0 - (dd - 1) / 5.0))
            elif key in ("string_days_off_starting", "string_days_off_ending"):
                # Penalize if sequence operates on the blocked date
                blocked_day = int(value) if isinstance(value, (int, float)) else 0
                if blocked_day in seq.get("operating_dates", []):
                    scores.append(0.0)
                else:
                    scores.append(1.0)
            elif key == "maximize_weekend_days_off":
                # Penalize sequences operating on weekends (approx: days 6,7,13,14,20,21,27,28)
                weekends = {6, 7, 13, 14, 20, 21, 27, 28}
                ops = set(seq.get("operating_dates", []))
                overlap = len(ops & weekends)
                scores.append(max(0.0, 1.0 - overlap / max(len(ops), 1)))
            else:
                scores.append(0.5)

        else:
            scores.append(0.5)

    # Quality tiebreaker: credit-per-duty-day efficiency.
    # This ensures that among sequences matching the same pairing filters,
    # those with higher credit efficiency rank above lower ones.
    # Weighted at 1/3 of a regular property to avoid overriding explicit prefs.
    if not has_maximize_credit:
        tpay = seq.get("totals", {}).get("tpay_minutes", 0)
        dd = seq.get("totals", {}).get("duty_days", 1) or 1
        cpd = tpay / dd  # credit per duty day
        # Normalize: ~150-400 min/day is typical range
        quality = min(1.0, max(0.0, (cpd - 100) / 400))
        # Add at 1/3 weight (equivalent to 0.33 of a property score)
        scores.append(quality * 0.33)
        # Adjust denominator: this counts as 0.33 of a property
        total = sum(scores)
        count = len(scores) - 1 + 0.33
        return round(total / count, 4) if count > 0 else 0.5

    return round(sum(scores) / len(scores), 4) if scores else 0.5


def compute_layer_summaries(
    sequences: list[dict],
    properties: list[dict],
    num_layers: int = 7,
) -> list[dict]:
    """Compute pairing counts per layer matching PBS Layer tab display.

    For each layer: filter sequences using filter_sequences_for_layer,
    track cumulative IDs across layers, compute total_pairings (cumulative),
    pairings_by_layer (unique to that layer), and properties_count.
    """
    summaries = []
    cumulative_ids: set = set()

    for layer_num in range(1, num_layers + 1):
        layer_props = [
            p for p in properties
            if p.get("is_enabled", True) and layer_num in p.get("layers", [])
        ]
        filtered = filter_sequences_for_layer(sequences, properties, layer_num)
        filtered_ids = {s.get("_id") or s.get("id") or s.get("seq_number") for s in filtered}

        new_ids = filtered_ids - cumulative_ids
        cumulative_ids |= filtered_ids

        summaries.append({
            "layer_number": layer_num,
            "total_pairings": len(cumulative_ids),
            "pairings_by_layer": len(new_ids),
            "properties_count": len(layer_props),
        })

    return summaries


def _get_days_off_exclusion(properties: list[dict], layer_number: int) -> tuple:
    """Extract days-off boundary exclusion dates from properties.

    Returns (off_start_day, off_end_day) where:
      - off_start_day: day-of-month from which days off begin (sequences operating on >= this day are excluded)
      - off_end_day: day-of-month on which days off end (sequences operating on <= this day are excluded)
    Either may be None if the property is not set.
    """
    off_start_day = None
    off_end_day = None
    for p in properties:
        if not p.get("is_enabled", True):
            continue
        if layer_number not in p.get("layers", []):
            continue
        key = p.get("property_key", "")
        val = p.get("value")
        if key == "string_days_off_starting" and val is not None:
            # Value is a day-of-month integer or a date string; extract the day
            off_start_day = _extract_day(val)
        elif key == "string_days_off_ending" and val is not None:
            off_end_day = _extract_day(val)
    return off_start_day, off_end_day


def _extract_day(val) -> int | None:
    """Extract day-of-month from a property value (int, str date, or str int)."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        # Could be "2026-01-16" or just "16"
        if "-" in val:
            try:
                return int(val.split("-")[-1])
            except (ValueError, IndexError):
                return None
        try:
            return int(val)
        except ValueError:
            return None
    return None


def _seq_overlaps_exclusion(seq: dict, off_start_day: int | None, off_end_day: int | None) -> bool:
    """Check if a sequence's operating dates overlap the days-off exclusion zone."""
    op_dates = seq.get("operating_dates", [])
    duty_days = seq.get("totals", {}).get("duty_days", 1)

    for d in op_dates:
        # The sequence spans from day d through d + duty_days - 1
        seq_end = d + duty_days - 1
        if off_start_day is not None:
            # Any date >= off_start_day is excluded
            if seq_end >= off_start_day:
                return True
        if off_end_day is not None:
            # Any date <= off_end_day is excluded
            if d <= off_end_day:
                return True
    return False


def filter_sequences_for_layer(
    sequences: list[dict],
    properties: list[dict],
    layer_number: int,
) -> list[dict]:
    """Filter sequences for a layer using PBS AND/OR logic.

    Same property_key with different values = OR (union).
    Different property_keys = AND (intersection).
    Only applies pairing-category properties that are enabled and assigned
    to the given layer.

    Also enforces days-off boundary exclusions as hard filters:
    - string_days_off_starting: excludes sequences operating on/after the given date
    - string_days_off_ending: excludes sequences operating on/before the given date
    """
    # Apply days-off boundary exclusion (hard filter)
    off_start, off_end = _get_days_off_exclusion(properties, layer_number)
    if off_start is not None or off_end is not None:
        sequences = [
            s for s in sequences
            if not _seq_overlaps_exclusion(s, off_start, off_end)
        ]

    # Collect active pairing properties for this layer
    layer_props = [
        p for p in properties
        if p.get("is_enabled", True)
        and layer_number in p.get("layers", [])
        and p.get("category") == "pairing"
    ]

    if not layer_props:
        return list(sequences)

    # Group by property_key for OR logic
    groups: dict[str, list] = {}
    for p in layer_props:
        key = p["property_key"]
        if key not in groups:
            groups[key] = []
        groups[key].append(p.get("value"))

    # For each sequence: must match ALL groups (AND).
    # Within each group: must match ANY value (OR).
    result = []
    for seq in sequences:
        match_all = True
        for prop_key, values in groups.items():
            match_any = any(_matches_property(seq, prop_key, v) for v in values)
            if not match_any:
                match_all = False
                break
        if match_all:
            result.append(seq)

    return result
