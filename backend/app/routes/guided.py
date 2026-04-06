"""Guided bid-building flow — 3-step: criteria → pick trips → build bid.

Endpoints:
  POST /pool-count      — live matching count as user changes criteria
  POST /ranked-trips    — score & rank pairings against criteria
  POST /check-conflicts — detect date overlaps among selected trips
  POST /build           — build 7-layer bid with selected trips as L2
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.db import get_collection
from app.services.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/bid-periods/{bid_period_id}/guided",
    tags=["guided"],
)


# ── Request / Response Models ────────────────────────────────────────────


class GuidedCriteria(BaseModel):
    """Clickable criteria from Step 1."""
    trip_lengths: list[int] = Field(default_factory=lambda: [3, 4])
    preferred_cities: list[str] = Field(default_factory=list)
    avoided_cities: list[str] = Field(default_factory=list)
    report_earliest_minutes: Optional[int] = None   # e.g., 540 = 9:00 AM
    release_latest_minutes: Optional[int] = None     # e.g., 1260 = 9:00 PM
    credit_min_minutes: int = 4200   # 70h
    credit_max_minutes: int = 5400   # 90h
    days_off: list[int] = Field(default_factory=list)  # day-of-month numbers
    avoid_redeyes: bool = True
    schedule_preference: str = "best"  # "first_half", "second_half", "best"


class PoolCountResponse(BaseModel):
    total_matching: int
    by_trip_length: dict[str, int] = Field(default_factory=dict)
    by_city_top10: list[dict] = Field(default_factory=list)


class RankedTripsRequest(GuidedCriteria):
    sort_by: str = "best_match"  # best_match, credit, date, report_time
    limit: int = 50
    offset: int = 0


class RankedTrip(BaseModel):
    sequence_id: str
    seq_number: int
    category: str = ""
    duty_days: int = 0
    tpay_minutes: int = 0
    credit_hours: float = 0.0
    operating_dates: list[int] = Field(default_factory=list)
    layover_cities: list[str] = Field(default_factory=list)
    report_time: str = ""
    release_time: str = ""
    equipment: list[str] = Field(default_factory=list)
    is_redeye: bool = False
    is_odan: bool = False
    match_score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)
    holdability_pct: float = 50.0
    holdability_label: str = "UNKNOWN"
    commute_impact: str = "green"  # green, yellow, red


class RankedTripsResponse(BaseModel):
    trips: list[RankedTrip]
    total_matching: int
    showing: int


class ConflictCheckRequest(BaseModel):
    selected_sequence_ids: list[str]


class ConflictPair(BaseModel):
    seq_a_id: str
    seq_a_number: int
    seq_b_id: str
    seq_b_number: int
    overlap_dates: list[int]


class ConflictCheckResponse(BaseModel):
    conflicts: list[ConflictPair]
    total_conflicts: int


class GuidedBuildRequest(BaseModel):
    selected_sequence_ids: list[str]
    criteria: Optional[GuidedCriteria] = None
    bid_id: Optional[str] = None  # existing bid to update, or None to create


# ── Helpers ──────────────────────────────────────────────────────────────


def _hhmm_to_minutes(t: str) -> int:
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _matches_criteria(seq: dict, criteria: GuidedCriteria) -> bool:
    """Check if a sequence matches the guided criteria filters."""
    totals = seq.get("totals", {})
    dps = seq.get("duty_periods", [])

    # Trip length
    if criteria.trip_lengths:
        dd = totals.get("duty_days", 1) or 1
        if dd not in criteria.trip_lengths:
            return False

    # Avoided cities
    if criteria.avoided_cities:
        cities = seq.get("layover_cities", [])
        if any(c in criteria.avoided_cities for c in cities):
            return False

    # Preferred cities (at least one match, or turns with no layovers pass)
    if criteria.preferred_cities:
        cities = seq.get("layover_cities", [])
        if cities and not any(c in criteria.preferred_cities for c in cities):
            return False

    # Report time
    if criteria.report_earliest_minutes is not None and dps:
        rpt = _hhmm_to_minutes(dps[0].get("report_base", "12:00"))
        if rpt < criteria.report_earliest_minutes:
            return False

    # Release time
    if criteria.release_latest_minutes is not None and dps:
        rel = _hhmm_to_minutes(dps[-1].get("release_base", "18:00"))
        if rel > criteria.release_latest_minutes:
            return False

    # Avoid redeyes
    if criteria.avoid_redeyes:
        if seq.get("is_redeye") or seq.get("is_odan"):
            return False

    # Days off (exclude sequences operating on requested off days)
    if criteria.days_off:
        off_set = set(criteria.days_off)
        duty_days = totals.get("duty_days", 1) or 1
        for start in seq.get("operating_dates", []):
            span = set(range(start, start + duty_days))
            if span & off_set:
                return False

    return True


def _score_trip(seq: dict, criteria: GuidedCriteria, is_commuter: bool) -> tuple[float, list[str]]:
    """Score a sequence against guided criteria. Returns (score, reasons)."""
    score = 0.0
    reasons: list[str] = []
    totals = seq.get("totals", {})
    dps = seq.get("duty_periods", [])

    # Credit efficiency (0-30 points)
    tpay = totals.get("tpay_minutes", 0)
    dd = totals.get("duty_days", 1) or 1
    cpd = tpay / dd  # credit per duty day
    credit_score = min(30.0, max(0.0, (cpd - 100) / 400 * 30))
    score += credit_score
    if cpd > 350:
        reasons.append(f"{round(tpay/60, 1)}h credit in {dd} days = {round(cpd/60, 1)}h/day (above average)")

    # Preferred city match (0-25 points)
    cities = seq.get("layover_cities", [])
    if criteria.preferred_cities and cities:
        matched = [c for c in cities if c in criteria.preferred_cities]
        if matched:
            city_score = min(25.0, len(matched) / len(cities) * 25)
            score += city_score
            if len(matched) == 1:
                reasons.append(f"{matched[0]} — your favorite city")
            else:
                reasons.append(f"{', '.join(matched)} — cities you love")

    # Report time (0-20 points, commuter-weighted)
    if dps:
        rpt_min = _hhmm_to_minutes(dps[0].get("report_base", "12:00"))
        if is_commuter:
            if rpt_min >= 720:
                rpt_score = 20.0
                reasons.append(f"Reports at {dps[0].get('report_base', '')} — easy same-day commute")
            elif rpt_min >= 540:
                rpt_score = 16.0
                reasons.append(f"Reports at {dps[0].get('report_base', '')} — comfortable morning commute")
            elif rpt_min >= 420:
                rpt_score = 8.0
            else:
                rpt_score = 2.0
        else:
            rpt_score = min(20.0, max(0.0, (rpt_min - 300) / 420 * 20))
        score += rpt_score

    # Release time (0-15 points, commuter-weighted)
    if dps:
        rel_min = _hhmm_to_minutes(dps[-1].get("release_base", "18:00"))
        if is_commuter:
            if rel_min <= 960:
                rel_score = 15.0
                reasons.append(f"Releases at {dps[-1].get('release_base', '')} — plenty of flights home")
            elif rel_min <= 1140:
                rel_score = 10.0
            elif rel_min <= 1260:
                rel_score = 5.0
            else:
                rel_score = 0.0
        else:
            if rel_min <= 960:
                rel_score = 15.0
            elif rel_min <= 1140:
                rel_score = 15.0 - (rel_min - 960) / 180 * 9
            else:
                rel_score = max(0.0, 6.0 - (rel_min - 1140) / 180 * 6)
        score += rel_score

    # Layover quality (0-10 points)
    layover_scores = []
    for dp in dps:
        lo = dp.get("layover")
        if lo and lo.get("rest_minutes"):
            hours = lo["rest_minutes"] / 60.0
            # Gaussian centered on 24h
            import math
            ls = 10.0 * math.exp(-((hours - 24) ** 2) / (2 * 64))
            layover_scores.append(ls)
    if layover_scores:
        avg_lo = sum(layover_scores) / len(layover_scores)
        score += avg_lo
        avg_hours = sum(
            dp.get("layover", {}).get("rest_minutes", 0) / 60
            for dp in dps if dp.get("layover", {}).get("rest_minutes")
        ) / max(len(layover_scores), 1)
        if avg_hours >= 20:
            reasons.append(f"{round(avg_hours, 0):.0f}h layovers — great rest time")

    # Fewer legs bonus (0-5 points)
    total_legs = totals.get("leg_count", 0) or 0
    avg_legs = total_legs / dd if dd > 0 else 2.0
    legs_score = max(0.0, 5.0 - (avg_legs - 1.0) * 2.5)
    score += legs_score
    if avg_legs <= 2.0:
        reasons.append(f"Max {int(avg_legs)} legs per day")

    return round(score, 1), reasons


# ── Endpoints ────────────────────────────────────────────────────────────


@router.post("/pool-count", response_model=PoolCountResponse)
async def pool_count(
    bid_period_id: str,
    criteria: GuidedCriteria,
    user_id: str = Depends(get_current_user_id),
):
    """Live pool count as user changes criteria in Step 1."""
    seq_coll = get_collection("sequences")
    all_seqs = list(seq_coll.find({"bid_period_id": bid_period_id}))

    matching = [s for s in all_seqs if _matches_criteria(s, criteria)]

    # Breakdown by trip length
    from collections import Counter
    length_counts: Counter = Counter()
    for s in matching:
        dd = s.get("totals", {}).get("duty_days", 1) or 1
        length_counts[str(dd)] += 1

    # Top 10 layover cities
    city_counts: Counter = Counter()
    for s in matching:
        for c in s.get("layover_cities", []):
            city_counts[c] += 1
    top_cities = [
        {"city": c, "count": n}
        for c, n in city_counts.most_common(10)
    ]

    return PoolCountResponse(
        total_matching=len(matching),
        by_trip_length=dict(length_counts),
        by_city_top10=top_cities,
    )


@router.post("/ranked-trips", response_model=RankedTripsResponse)
async def ranked_trips(
    bid_period_id: str,
    body: RankedTripsRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Score and rank pairings against criteria for Step 2."""
    seq_coll = get_collection("sequences")
    all_seqs = list(seq_coll.find({"bid_period_id": bid_period_id}))

    # Detect commuter from profile
    users_coll = get_collection("users")
    user_doc = users_coll.find_one({"_id": user_id})
    profile = (user_doc or {}).get("profile", {})
    is_commuter = bool(profile.get("commute_from"))

    # Holdability setup
    seniority = profile.get("seniority_number") or 1
    total_fas = profile.get("total_base_fas") or 1
    sen_pct = profile.get("seniority_percentage")

    from app.services.optimizer import estimate_attainability

    # Filter
    matching = [s for s in all_seqs if _matches_criteria(s, body)]

    # Score
    scored: list[tuple[float, dict, list[str]]] = []
    for seq in matching:
        match_score, reasons = _score_trip(seq, body, is_commuter)

        # Compute holdability
        att = estimate_attainability(
            seq, seniority, total_fas,
            profile.get("language_qualifications", []),
            seniority_percentage=sen_pct,
            all_sequences=all_seqs,
        )
        hold_val = seq.get("_holdability", 0.5)
        if hold_val >= 0.70:
            hold_label = "LIKELY"
        elif hold_val >= 0.40:
            hold_label = "COMPETITIVE"
        else:
            hold_label = "LONG SHOT"

        # Commute impact
        dps = seq.get("duty_periods", [])
        impact = "green"
        if dps and is_commuter:
            rpt = _hhmm_to_minutes(dps[0].get("report_base", "12:00"))
            rel = _hhmm_to_minutes(dps[-1].get("release_base", "18:00"))
            if rpt < 420:
                impact = "red"
            elif rpt < 540:
                impact = "yellow"
            if rel > 1260:
                impact = "red"
            elif rel > 1140 and impact != "red":
                impact = "yellow"

        # Equipment
        equip: list[str] = []
        for dp in dps:
            for lg in dp.get("legs", []):
                eq = lg.get("equipment")
                if eq and eq not in equip:
                    equip.append(eq)

        scored.append((match_score, seq, reasons, hold_val, hold_label, impact, equip))

    # Sort
    if body.sort_by == "credit":
        scored.sort(key=lambda x: x[1].get("totals", {}).get("tpay_minutes", 0), reverse=True)
    elif body.sort_by == "date":
        scored.sort(key=lambda x: min(x[1].get("operating_dates", [999])))
    elif body.sort_by == "report_time":
        def _rpt(x):
            dps = x[1].get("duty_periods", [])
            return _hhmm_to_minutes(dps[0].get("report_base", "12:00")) if dps else 0
        scored.sort(key=_rpt, reverse=True)
    else:  # best_match
        scored.sort(key=lambda x: x[0], reverse=True)

    total = len(scored)
    page = scored[body.offset:body.offset + body.limit]

    trips = []
    for match_score, seq, reasons, hold_val, hold_label, impact, equip in page:
        totals = seq.get("totals", {})
        dps = seq.get("duty_periods", [])
        trips.append(RankedTrip(
            sequence_id=seq["_id"],
            seq_number=seq.get("seq_number", 0),
            category=seq.get("category", ""),
            duty_days=totals.get("duty_days", 0),
            tpay_minutes=totals.get("tpay_minutes", 0),
            credit_hours=round(totals.get("tpay_minutes", 0) / 60, 1),
            operating_dates=seq.get("operating_dates", []),
            layover_cities=seq.get("layover_cities", []),
            report_time=dps[0].get("report_base", "") if dps else "",
            release_time=dps[-1].get("release_base", "") if dps else "",
            equipment=equip,
            is_redeye=seq.get("is_redeye", False),
            is_odan=seq.get("is_odan", False),
            match_score=match_score,
            match_reasons=reasons,
            holdability_pct=round(hold_val * 100, 0),
            holdability_label=hold_label,
            commute_impact=impact,
        ))

    return RankedTripsResponse(
        trips=trips,
        total_matching=total,
        showing=len(trips),
    )


@router.post("/check-conflicts", response_model=ConflictCheckResponse)
async def check_conflicts(
    bid_period_id: str,
    body: ConflictCheckRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Detect date overlaps among selected trips."""
    if len(body.selected_sequence_ids) < 2:
        return ConflictCheckResponse(conflicts=[], total_conflicts=0)

    seq_coll = get_collection("sequences")
    seqs = {
        s["_id"]: s
        for s in seq_coll.find({"bid_period_id": bid_period_id})
        if s["_id"] in set(body.selected_sequence_ids)
    }

    conflicts: list[ConflictPair] = []
    ids = list(body.selected_sequence_ids)

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a = seqs.get(ids[i])
            b = seqs.get(ids[j])
            if not a or not b:
                continue

            dd_a = a.get("totals", {}).get("duty_days", 1) or 1
            dd_b = b.get("totals", {}).get("duty_days", 1) or 1

            dates_a: set[int] = set()
            for start in a.get("operating_dates", []):
                dates_a.update(range(start, start + dd_a))

            dates_b: set[int] = set()
            for start in b.get("operating_dates", []):
                dates_b.update(range(start, start + dd_b))

            overlap = sorted(dates_a & dates_b)
            if overlap:
                conflicts.append(ConflictPair(
                    seq_a_id=ids[i],
                    seq_a_number=a.get("seq_number", 0),
                    seq_b_id=ids[j],
                    seq_b_number=b.get("seq_number", 0),
                    overlap_dates=overlap,
                ))

    return ConflictCheckResponse(
        conflicts=conflicts,
        total_conflicts=len(conflicts),
    )


@router.post("/build")
async def build_guided_bid(
    bid_period_id: str,
    body: GuidedBuildRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Build 7-layer bid with selected trips as L2 pinned entries.

    Uses progressive relaxation: selected trips → L2, derive generic
    properties → L3, progressively widen → L4-L7.
    """
    from app.services.optimizer import optimize_bid

    # Verify bid period
    bp_coll = get_collection("bid_periods")
    bp_doc = bp_coll.find_one({"_id": bid_period_id, "user_id": user_id})
    if not bp_doc:
        raise HTTPException(status_code=404, detail="Bid period not found")
    if bp_doc.get("parse_status") != "completed":
        raise HTTPException(status_code=409, detail="Bid period not fully parsed")

    # Load user profile
    users_coll = get_collection("users")
    user_doc = users_coll.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    profile = user_doc.get("profile", {})
    seniority = profile.get("seniority_number") or 1
    total_fas = profile.get("total_base_fas") or 1
    sen_pct = profile.get("seniority_percentage")
    commute_from = profile.get("commute_from")
    user_langs = profile.get("language_qualifications", [])

    # Load sequences
    seq_coll = get_collection("sequences")
    all_seqs = list(seq_coll.find({"bid_period_id": bid_period_id}))

    # Build pinned entries from selected trip IDs
    pinned_entries = [
        {"sequence_id": sid, "rank": i + 1}
        for i, sid in enumerate(body.selected_sequence_ids)
    ]

    # Convert criteria to preferences + properties
    prefs = user_doc.get("default_preferences", {})
    if body.criteria:
        c = body.criteria
        prefs["preferred_layover_cities"] = c.preferred_cities
        prefs["avoided_layover_cities"] = c.avoided_cities
        prefs["preferred_days_off"] = c.days_off
        if c.report_earliest_minutes is not None:
            prefs["report_earliest_minutes"] = c.report_earliest_minutes
        if c.release_latest_minutes is not None:
            prefs["release_latest_minutes"] = c.release_latest_minutes
        prefs["avoid_redeyes"] = c.avoid_redeyes

    # Compute total dates
    total_dates = bp_doc.get("total_dates", 0)
    if total_dates == 0:
        try:
            from datetime import date as dt_date
            s = dt_date.fromisoformat(bp_doc.get("effective_start", ""))
            e = dt_date.fromisoformat(bp_doc.get("effective_end", ""))
            total_dates = (e - s).days + 1
        except (ValueError, TypeError):
            total_dates = 30

    target_min = bp_doc.get("target_credit_min_minutes", 4200)
    target_max = bp_doc.get("target_credit_max_minutes", 5400)
    if body.criteria:
        target_min = body.criteria.credit_min_minutes
        target_max = body.criteria.credit_max_minutes

    # Build waiver properties from criteria
    bid_properties: list[dict] = []
    # (User can add waivers in step 1 — for now pass empty to use defaults)

    # Run optimizer in progressive mode
    result = optimize_bid(
        sequences=all_seqs,
        prefs=prefs,
        seniority_number=seniority,
        total_base_fas=total_fas,
        user_langs=user_langs,
        pinned_entries=pinned_entries,
        excluded_ids=set(),
        total_dates=total_dates,
        bid_properties=bid_properties or None,
        target_credit_min_minutes=target_min,
        target_credit_max_minutes=target_max,
        seniority_percentage=sen_pct,
        commute_from=commute_from,
        strategy_mode="progressive",
    )

    entries, explanation_data = result

    # Save as bid
    bids_coll = get_collection("bids")
    from datetime import datetime, timezone
    import uuid

    if body.bid_id:
        bid_id = body.bid_id
    else:
        bid_id = str(uuid.uuid4())

    # Trim entries
    MAX_ENTRIES = 200
    active = [e for e in entries if not e.get("is_excluded")]
    excluded = [e for e in entries if e.get("is_excluded")]
    if len(active) > MAX_ENTRIES:
        active = active[:MAX_ENTRIES]
    final_entries = active + excluded[:max(0, MAX_ENTRIES - len(active))]
    for i, e in enumerate(final_entries):
        e["rank"] = i + 1

    now = datetime.now(timezone.utc).isoformat()
    bid_doc = {
        "_id": bid_id,
        "bid_period_id": bid_period_id,
        "user_id": user_id,
        "name": "Guided Bid",
        "status": "optimized",
        "entries": final_entries,
        "properties": bid_properties,
        "optimization_config": {
            "strategy_mode": "progressive",
            "selected_trip_ids": body.selected_sequence_ids,
            "criteria": body.criteria.model_dump() if body.criteria else None,
        },
        "created_at": now,
        "updated_at": now,
    }

    if explanation_data:
        bid_doc["explanation"] = explanation_data

    # Upsert
    existing = bids_coll.find_one({"_id": bid_id})
    if existing:
        bids_coll.find_one_and_update(
            {"_id": bid_id},
            {"$set": bid_doc},
        )
    else:
        bids_coll.insert_one(bid_doc)

    # Build summary response
    layer_summary = []
    for layer_num in range(1, 8):
        layer_entries = [e for e in final_entries if e.get("layer") == layer_num]
        credit = sum(e.get("tpay_minutes", 0) for e in layer_entries)
        # Get pool size from explanation data
        pool_size = 0
        holdability = 50
        if explanation_data and explanation_data.get("layers"):
            for ld in explanation_data["layers"]:
                if ld.get("layer_num") == layer_num:
                    pool_size = ld.get("pool_size", 0)
                    holdability = ld.get("holdability_pct", 50)
                    break

        layer_summary.append({
            "layer": layer_num,
            "sequences": len(layer_entries),
            "pool_size": pool_size,
            "credit_hours": round(credit / 60, 1) if credit else round(
                sum(
                    next(
                        (s.get("totals", {}).get("tpay_minutes", 0) for s in all_seqs if s["_id"] == e.get("sequence_id")),
                        0,
                    )
                    for e in layer_entries
                ) / 60, 1,
            ),
            "holdability_pct": holdability,
        })

    return {
        "bid_id": bid_id,
        "status": "optimized",
        "total_entries": len(final_entries),
        "layer_summary": layer_summary,
        "explanation": explanation_data,
        "entries": final_entries[:50],  # first 50 for display
    }
