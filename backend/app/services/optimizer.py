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
) -> str:
    # Use seniority_percentage directly if provided (from PBS portal)
    if seniority_percentage is not None:
        percentile = seniority_percentage / 100.0
    elif total_base_fas and total_base_fas > 0:
        percentile = seniority_number / total_base_fas
    else:
        return "unknown"
    ops = seq.get("ops_count", 1)
    lang = seq.get("language")
    lang_bonus = 0.3 if (lang and lang in user_langs) else 0.0
    ops_factor = min(ops / 25.0, 1.0)
    score = (1.0 - percentile) + ops_factor * 0.5 + lang_bonus
    if score >= 1.0:
        return "high"
    elif score >= 0.6:
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
) -> list[dict]:
    """Run the full optimization pipeline and return layered entries.

    When bid_properties is provided, uses PBS 7-layer property-based logic.
    When None, falls back to existing 9-layer preference-based scoring.
    target_credit_min/max_minutes: per-month range from the bid package.
    seniority_percentage: 0-100 from PBS portal (used instead of number/total if set).
    commute_from: IATA code if FA commutes (used for commute annotations, not schedule changes).
    """
    # Filter out excluded
    eligible = [s for s in sequences if s["_id"] not in excluded_ids]

    # ── PBS property-based path (7 layers, CP-SAT optimised) ────────────
    if bid_properties:
        num_layers = 7

        # Pre-compute trip quality for composite scoring (once, before layer loop)
        from app.services.cpsat_builder import compute_trip_quality, solve_layer_cpsat
        for seq in eligible:
            seq["_trip_quality"] = compute_trip_quality(seq)

        # For each layer: filter, score, then build schedule with CP-SAT
        layers: list[list[dict]] = []
        used_in_prior: set[str] = set()
        previous_solutions: list[set[str]] = []

        for layer_num in range(1, num_layers + 1):
            # Filter sequences for this layer
            filtered = filter_sequences_for_layer(eligible, bid_properties, layer_num)

            # Score using properties and compute date spans
            for seq in filtered:
                seq["preference_score"] = score_sequence_from_properties(
                    seq, bid_properties, layer_num,
                )
                seq["attainability"] = estimate_attainability(
                    seq, seniority_number, total_base_fas, user_langs,
                    seniority_percentage=seniority_percentage,
                )
                # Pre-compute date spans (required by solver)
                if "_all_spans" not in seq:
                    seq["_all_spans"] = _all_possible_date_spans(seq)

            # Filter to sequences with date info
            filtered = [s for s in filtered if s.get("_all_spans")]

            # Penalize reuse from prior layers
            candidates = []
            for seq in filtered:
                if seq["_id"] in used_in_prior:
                    adj = dict(seq)
                    adj["_all_spans"] = seq["_all_spans"]
                    adj["preference_score"] = seq["preference_score"] * 0.6
                    candidates.append(adj)
                else:
                    candidates.append(seq)

            # Use bid-period target credit range, allow property overrides
            max_credit = target_credit_max_minutes
            min_days_off = 11  # CBA §11.H default
            for p in bid_properties:
                if p.get("property_key") == "target_credit_range" and isinstance(p.get("value"), dict):
                    # Property can tighten the range but not exceed bid period max
                    prop_max = p["value"].get("end", target_credit_max_minutes)
                    max_credit = min(prop_max, target_credit_max_minutes)
                if p.get("property_key") == "waive_minimum_days_off" and p.get("value"):
                    min_days_off = 8  # reduced if waived

            # CP-SAT solver (falls back to greedy if ortools unavailable)
            layer = solve_layer_cpsat(
                candidates, total_dates,
                max_credit_minutes=max_credit,
                min_credit_minutes=target_credit_min_minutes,
                min_days_off=min_days_off,
                layer_num=layer_num, previous_solutions=previous_solutions,
            )
            layers.append(layer)

            # Track selections for reuse penalty + Hamming distance
            layer_ids: set[str] = set()
            for seq in layer:
                used_in_prior.add(seq["_id"])
                layer_ids.add(seq["_id"])
            previous_solutions.append(layer_ids)

        # Log
        for i, layer in enumerate(layers, 1):
            logger.info("PBS Layer %d: %d sequences", i, len(layer))

        # Flatten — rank within each layer by effective score (best first)
        entries: list[dict] = []
        rank = 1
        for layer_idx, layer_seqs in enumerate(layers, start=1):
            # Sort by effective score descending so best sequences get lowest rank
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
                        seq, seq["preference_score"], seq.get("attainability", "unknown"), prefs,
                    ),
                    "preference_score": seq["preference_score"],
                    "attainability": seq.get("attainability", "unknown"),
                    "date_conflict_group": f"layer-{layer_idx}",
                    "operating_dates": sorted(chosen) if chosen else seq.get("operating_dates", []),
                    "chosen_dates": sorted(chosen) if chosen else [],
                    "layer": layer_idx,
                })
                rank += 1

    # ── No-properties fallback (7 layers, preference-scored) ────────────
    else:
        num_layers = 7
        cluster_trips = prefs.get("cluster_trips", False)

        # Score and estimate attainability
        for seq in eligible:
            seq["preference_score"] = score_sequence(seq, prefs)
            seq["attainability"] = estimate_attainability(
                seq, seniority_number, total_base_fas, user_langs,
                seniority_percentage=seniority_percentage,
            )

        layers_default = build_layers(eligible, total_dates, cluster_trips,
                                      num_layers=num_layers,
                                      max_credit_minutes=target_credit_max_minutes)

        for i, layer in enumerate(layers_default, 1):
            logger.info("Layer %d: %d sequences", i, len(layer))

        entries = []
        rank = 1
        for layer_idx, layer_seqs in enumerate(layers_default, start=1):
            # Sort by effective score descending so best sequences get lowest rank
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
                    "operating_dates": sorted(chosen) if chosen else seq.get("operating_dates", []),
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

    # Annotate commute info if FA is a commuter
    if commute_from:
        annotate_commute(entries, sequences, commute_from)

    return entries


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
