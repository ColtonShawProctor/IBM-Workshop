from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db import get_collection
from pydantic import BaseModel, Field as PydanticField

from app.models.schemas import (
    CommuteImpact,
    Sequence,
    SequenceComparison,
    SequenceInput,
    SequenceList,
    SequenceTotals,
    DutyPeriod,
    Leg,
    Layover,
)
from app.services.auth import get_current_user_id
from app.services.commute import analyze_commute_impact

router = APIRouter(
    prefix="/bid-periods/{bid_period_id}/sequences",
    tags=["Sequences"],
)


def _doc_to_sequence(doc: dict) -> Sequence:
    duty_periods = []
    for dp_raw in doc.get("duty_periods", []):
        legs = [Leg(**lg) for lg in dp_raw.get("legs", [])]
        layover = Layover(**dp_raw["layover"]) if dp_raw.get("layover") else None
        dp = DutyPeriod(
            dp_number=dp_raw["dp_number"],
            day_of_seq=dp_raw.get("day_of_seq"),
            day_of_seq_total=dp_raw.get("day_of_seq_total"),
            report_local=dp_raw.get("report_local", ""),
            report_base=dp_raw.get("report_base", ""),
            release_local=dp_raw.get("release_local", ""),
            release_base=dp_raw.get("release_base", ""),
            duty_minutes=dp_raw.get("duty_minutes"),
            legs=legs,
            layover=layover,
        )
        duty_periods.append(dp)

    totals_raw = doc.get("totals", {})
    totals = SequenceTotals(**totals_raw) if totals_raw else SequenceTotals()

    return Sequence(
        id=doc["_id"],
        bid_period_id=doc["bid_period_id"],
        seq_number=doc["seq_number"],
        category=doc.get("category"),
        ops_count=doc.get("ops_count", 1),
        position_min=doc.get("position_min", 1),
        position_max=doc.get("position_max", 9),
        language=doc.get("language"),
        language_count=doc.get("language_count"),
        operating_dates=doc.get("operating_dates", []),
        is_turn=doc.get("is_turn", False),
        has_deadhead=doc.get("has_deadhead", False),
        is_redeye=doc.get("is_redeye", False),
        totals=totals,
        layover_cities=doc.get("layover_cities", []),
        duty_periods=duty_periods,
        source=doc.get("source", "parsed"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


def _hhmm_to_minutes(t: str) -> int:
    """Convert 'HH:MM' to minutes from midnight."""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _get_sort_key(doc: dict, sort_by: str):
    """Extract a sort key from a sequence document."""
    mapping = {
        "seq_number": lambda d: d.get("seq_number", 0),
        "tpay": lambda d: d.get("totals", {}).get("tpay_minutes", 0),
        "block": lambda d: d.get("totals", {}).get("block_minutes", 0),
        "tafb": lambda d: d.get("totals", {}).get("tafb_minutes", 0),
        "ops_count": lambda d: d.get("ops_count", 0),
        "duty_days": lambda d: d.get("totals", {}).get("duty_days", 0),
        "leg_count": lambda d: d.get("totals", {}).get("leg_count", 0),
        "report_time": lambda d: _report_time_minutes(d),
    }
    fn = mapping.get(sort_by, mapping["seq_number"])
    return fn(doc)


def _report_time_minutes(doc: dict) -> int:
    """Get report time of first duty period in minutes from midnight."""
    dps = doc.get("duty_periods", [])
    if dps and dps[0].get("report_base"):
        return _hhmm_to_minutes(dps[0]["report_base"])
    return 0


def _matches_filters(doc: dict, filters: dict) -> bool:
    """Check if a sequence document matches all provided filters."""
    if filters.get("seq_number") is not None:
        if doc.get("seq_number") != filters["seq_number"]:
            return False

    if filters.get("category"):
        doc_cat = (doc.get("category") or "").upper()
        filter_cat = filters["category"].upper()
        # Support both exact match ("ORD 777 INTL") and substring ("777 INTL")
        if doc_cat != filter_cat and filter_cat not in doc_cat:
            return False

    if filters.get("equipment"):
        eq = filters["equipment"]
        dps = doc.get("duty_periods", [])
        has_eq = any(
            lg.get("equipment") == eq
            for dp in dps
            for lg in dp.get("legs", [])
        )
        if not has_eq:
            return False

    if filters.get("layover_city"):
        if filters["layover_city"] not in doc.get("layover_cities", []):
            return False

    if filters.get("language"):
        if doc.get("language") != filters["language"]:
            return False

    totals = doc.get("totals", {})

    if filters.get("duty_days_min") is not None:
        if totals.get("duty_days", 0) < filters["duty_days_min"]:
            return False
    if filters.get("duty_days_max") is not None:
        if totals.get("duty_days", 0) > filters["duty_days_max"]:
            return False

    if filters.get("tpay_min") is not None:
        if totals.get("tpay_minutes", 0) < filters["tpay_min"]:
            return False
    if filters.get("tpay_max") is not None:
        if totals.get("tpay_minutes", 0) > filters["tpay_max"]:
            return False

    if filters.get("tafb_min") is not None:
        if totals.get("tafb_minutes", 0) < filters["tafb_min"]:
            return False
    if filters.get("tafb_max") is not None:
        if totals.get("tafb_minutes", 0) > filters["tafb_max"]:
            return False

    if filters.get("block_min") is not None:
        if totals.get("block_minutes", 0) < filters["block_min"]:
            return False
    if filters.get("block_max") is not None:
        if totals.get("block_minutes", 0) > filters["block_max"]:
            return False

    if filters.get("operating_date") is not None:
        if filters["operating_date"] not in doc.get("operating_dates", []):
            return False

    if filters.get("is_turn") is not None:
        if doc.get("is_turn", False) != filters["is_turn"]:
            return False

    if filters.get("has_deadhead") is not None:
        if doc.get("has_deadhead", False) != filters["has_deadhead"]:
            return False

    if filters.get("is_redeye") is not None:
        if doc.get("is_redeye", False) != filters["is_redeye"]:
            return False

    if filters.get("position_min") is not None:
        if doc.get("position_max", 9) < filters["position_min"]:
            return False
    if filters.get("position_max") is not None:
        if doc.get("position_min", 1) > filters["position_max"]:
            return False

    dps = doc.get("duty_periods", [])
    if dps:
        rpt_mins = _report_time_minutes(doc)
        if filters.get("report_earliest") is not None:
            if rpt_mins < filters["report_earliest"]:
                return False
        if filters.get("report_latest") is not None:
            if rpt_mins > filters["report_latest"]:
                return False

        last_dp = dps[-1]
        if last_dp.get("release_base"):
            rls_mins = _hhmm_to_minutes(last_dp["release_base"])
            if filters.get("release_earliest") is not None:
                if rls_mins < filters["release_earliest"]:
                    return False
            if filters.get("release_latest") is not None:
                if rls_mins > filters["release_latest"]:
                    return False

    return True


def _check_eligibility(doc: dict, user_doc: dict) -> bool:
    """Check if user is eligible for this sequence based on position and language."""
    return _compute_eligibility(doc, user_doc) != "ineligible"


def _compute_eligibility(doc: dict, user_doc: dict) -> str:
    """Compute eligibility status: 'eligible', 'language_advantaged', or 'ineligible'."""
    profile = user_doc.get("profile", {})
    user_pos_min = profile.get("position_min", 1)
    user_pos_max = profile.get("position_max", 9)
    seq_pos_min = doc.get("position_min", 1)
    seq_pos_max = doc.get("position_max", 9)

    # User must have at least one position in the sequence's range
    if user_pos_max < seq_pos_min or user_pos_min > seq_pos_max:
        return "ineligible"

    # If sequence requires a language, user must have it
    seq_lang = doc.get("language")
    user_langs = profile.get("language_qualifications", [])
    if seq_lang:
        if seq_lang not in user_langs:
            return "ineligible"
        return "language_advantaged"

    return "eligible"


@router.get("", response_model=SequenceList)
async def list_sequences(
    bid_period_id: str,
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, le=200),
    page_state: Optional[str] = None,
    sort_by: str = Query(default="seq_number"),
    sort_order: str = Query(default="asc"),
    category: Optional[str] = None,
    equipment: Optional[str] = None,
    layover_city: Optional[str] = None,
    language: Optional[str] = None,
    duty_days_min: Optional[int] = None,
    duty_days_max: Optional[int] = None,
    tpay_min: Optional[int] = None,
    tpay_max: Optional[int] = None,
    tafb_min: Optional[int] = None,
    tafb_max: Optional[int] = None,
    block_min: Optional[int] = None,
    block_max: Optional[int] = None,
    operating_date: Optional[int] = None,
    is_turn: Optional[bool] = None,
    has_deadhead: Optional[bool] = None,
    is_redeye: Optional[bool] = None,
    report_earliest: Optional[int] = None,
    report_latest: Optional[int] = None,
    release_earliest: Optional[int] = None,
    release_latest: Optional[int] = None,
    position_min: Optional[int] = None,
    position_max: Optional[int] = None,
    seq_number: Optional[int] = None,
    commutable_only: bool = False,
    eligible_only: bool = False,
):
    # Verify bid period belongs to user
    bp_coll = get_collection("bid_periods")
    bp_doc = bp_coll.find_one({"_id": bid_period_id, "user_id": user_id})
    if not bp_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")

    # Fetch all sequences for this bid period
    seq_coll = get_collection("sequences")
    docs = seq_coll.find({"bid_period_id": bid_period_id})

    # Build filter dict
    filters = {
        "seq_number": seq_number,
        "category": category,
        "equipment": equipment,
        "layover_city": layover_city,
        "language": language,
        "duty_days_min": duty_days_min,
        "duty_days_max": duty_days_max,
        "tpay_min": tpay_min,
        "tpay_max": tpay_max,
        "tafb_min": tafb_min,
        "tafb_max": tafb_max,
        "block_min": block_min,
        "block_max": block_max,
        "operating_date": operating_date,
        "is_turn": is_turn,
        "has_deadhead": has_deadhead,
        "is_redeye": is_redeye,
        "report_earliest": report_earliest,
        "report_latest": report_latest,
        "release_earliest": release_earliest,
        "release_latest": release_latest,
        "position_min": position_min,
        "position_max": position_max,
    }

    # Apply filters
    filtered = [d for d in docs if _matches_filters(d, filters)]

    # Get user doc for eligibility computation
    users_coll = get_collection("users")
    user_doc = users_coll.find_one({"_id": user_id})

    # Apply eligibility filter
    if eligible_only and user_doc:
        filtered = [d for d in filtered if _check_eligibility(d, user_doc)]

    total_count = len(filtered)

    # Sort
    reverse = sort_order == "desc"
    filtered.sort(key=lambda d: _get_sort_key(d, sort_by), reverse=reverse)

    # Pagination via page_state (offset-based for simplicity)
    offset = int(page_state) if page_state else 0
    page = filtered[offset : offset + limit]
    next_state = str(offset + limit) if offset + limit < total_count else None

    data = [_doc_to_sequence(d) for d in page]

    # Attach eligibility status and commute impact to each sequence
    if user_doc:
        commute_from = user_doc.get("profile", {}).get("commute_from")
        base_city = user_doc.get("profile", {}).get("base_city")
        for seq, doc in zip(data, page):
            seq.eligibility = _compute_eligibility(doc, user_doc)
            if commute_from and base_city:
                impact = analyze_commute_impact(seq, commute_from, base_city)
                seq.commute_impact = CommuteImpact(**impact)

    # Post-filter by commutability if requested
    if commutable_only:
        data = [s for s in data if s.commute_impact and s.commute_impact.impact_level in ("green", "yellow")]
        total_count = len(data)
        next_state = None  # Pagination is invalidated by post-filter

    return SequenceList(data=data, page_state=next_state, total_count=total_count)


def _verify_bid_period(bid_period_id: str, user_id: str):
    """Verify bid period exists and belongs to user. Returns doc or raises 404."""
    bp_coll = get_collection("bid_periods")
    bp_doc = bp_coll.find_one({"_id": bid_period_id, "user_id": user_id})
    if not bp_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")
    return bp_doc


@router.get("/search/{seq_number}", response_model=Sequence)
async def search_sequence_by_number(
    bid_period_id: str,
    seq_number: int,
    user_id: str = Depends(get_current_user_id),
):
    """Find a single sequence by its SEQ number."""
    _verify_bid_period(bid_period_id, user_id)
    seq_coll = get_collection("sequences")
    doc = seq_coll.find_one({"bid_period_id": bid_period_id, "seq_number": seq_number})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
    seq = _doc_to_sequence(doc)
    users_coll = get_collection("users")
    user_doc = users_coll.find_one({"_id": user_id})
    if user_doc:
        seq.eligibility = _compute_eligibility(doc, user_doc)
        commute_from = user_doc.get("profile", {}).get("commute_from")
        base_city = user_doc.get("profile", {}).get("base_city")
        if commute_from and base_city:
            impact = analyze_commute_impact(seq, commute_from, base_city)
            seq.commute_impact = CommuteImpact(**impact)
    return seq


class CompareRequest(BaseModel):
    sequence_ids: list[str] = PydanticField(min_length=2, max_length=5)


def _compute_differences(sequences: list[Sequence]) -> list[dict]:
    """Compute attribute differences across sequences for comparison."""
    diffs = []
    attrs = [
        ("ops_count", "ops_count"),
        ("tpay_minutes", "totals.tpay_minutes"),
        ("block_minutes", "totals.block_minutes"),
        ("tafb_minutes", "totals.tafb_minutes"),
        ("synth_minutes", "totals.synth_minutes"),
        ("duty_days", "totals.duty_days"),
        ("leg_count", "totals.leg_count"),
        ("deadhead_count", "totals.deadhead_count"),
        ("is_turn", "is_turn"),
        ("has_deadhead", "has_deadhead"),
        ("is_redeye", "is_redeye"),
        ("language", "language"),
        ("position_min", "position_min"),
        ("position_max", "position_max"),
    ]
    for label, path in attrs:
        values = []
        for seq in sequences:
            obj = seq
            for part in path.split("."):
                obj = getattr(obj, part, None)
                if obj is None:
                    break
            values.append(obj)
        if len(set(str(v) for v in values)) > 1:
            diffs.append({
                "attribute": label,
                "values": {str(seq.seq_number): v for seq, v in zip(sequences, values)},
            })

    # Compare layover cities
    cities = [tuple(seq.layover_cities) for seq in sequences]
    if len(set(cities)) > 1:
        diffs.append({
            "attribute": "layover_cities",
            "values": {str(seq.seq_number): seq.layover_cities for seq in sequences},
        })

    # Compare operating dates
    dates = [tuple(seq.operating_dates) for seq in sequences]
    if len(set(dates)) > 1:
        diffs.append({
            "attribute": "operating_dates",
            "values": {str(seq.seq_number): seq.operating_dates for seq in sequences},
        })

    return diffs


@router.post("/compare", response_model=SequenceComparison)
async def compare_sequences(
    bid_period_id: str,
    body: CompareRequest,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    seq_coll = get_collection("sequences")
    sequences = []
    for sid in body.sequence_ids:
        doc = seq_coll.find_one({"_id": sid, "bid_period_id": bid_period_id})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sequence {sid} not found",
            )
        sequences.append(_doc_to_sequence(doc))

    differences = _compute_differences(sequences)
    return SequenceComparison(sequences=sequences, differences=differences)


def _compute_derived(body: SequenceInput) -> dict:
    """Compute derived fields from a SequenceInput."""
    dps = body.duty_periods
    all_legs = [lg for dp in dps for lg in dp.legs]

    block_minutes = sum(lg.block_minutes for lg in all_legs if not lg.is_deadhead)
    leg_count = len(all_legs)
    deadhead_count = sum(1 for lg in all_legs if lg.is_deadhead)
    has_deadhead = deadhead_count > 0
    duty_days = len(dps)
    is_turn = duty_days == 1 and not any(dp.layover for dp in dps)

    layover_cities = []
    for dp in dps:
        if dp.layover and dp.layover.city and dp.layover.city not in layover_cities:
            layover_cities.append(dp.layover.city)

    # Redeye: any leg departs after 21:00 local and arrives before 06:00 local
    is_redeye = False
    for lg in all_legs:
        dep_h, dep_m = map(int, lg.departure_local.split(":"))
        arr_h, arr_m = map(int, lg.arrival_local.split(":"))
        dep_mins = dep_h * 60 + dep_m
        arr_mins = arr_h * 60 + arr_m
        if dep_mins >= 1260 and arr_mins < 360:  # 21:00 and 06:00
            is_redeye = True
            break

    return {
        "is_turn": is_turn,
        "has_deadhead": has_deadhead,
        "is_redeye": is_redeye,
        "layover_cities": layover_cities,
        "totals": {
            "block_minutes": block_minutes,
            "synth_minutes": 0,
            "tpay_minutes": block_minutes,
            "tafb_minutes": 0,
            "duty_days": duty_days,
            "leg_count": leg_count,
            "deadhead_count": deadhead_count,
        },
    }


def _input_to_doc(body: SequenceInput, bid_period_id: str) -> dict:
    """Convert a SequenceInput to a DB document dict (without _id or timestamps)."""
    derived = _compute_derived(body)

    dp_dicts = []
    for i, dp in enumerate(body.duty_periods):
        leg_dicts = []
        for j, lg in enumerate(dp.legs):
            ld = lg.model_dump()
            ld["leg_index"] = j + 1
            leg_dicts.append(ld)
        dp_dict = dp.model_dump()
        dp_dict["legs"] = leg_dicts
        if dp.layover:
            dp_dict["layover"] = dp.layover.model_dump()
        else:
            dp_dict["layover"] = None
        dp_dicts.append(dp_dict)

    return {
        "bid_period_id": bid_period_id,
        "seq_number": body.seq_number,
        "category": body.category,
        "ops_count": body.ops_count,
        "position_min": body.position_min,
        "position_max": body.position_max,
        "language": body.language,
        "language_count": body.language_count,
        "operating_dates": body.operating_dates,
        "is_turn": derived["is_turn"],
        "has_deadhead": derived["has_deadhead"],
        "is_redeye": derived["is_redeye"],
        "layover_cities": derived["layover_cities"],
        "totals": derived["totals"],
        "duty_periods": dp_dicts,
        "source": "manual",
    }


@router.get("/{sequence_id}", response_model=Sequence)
async def get_sequence(
    bid_period_id: str,
    sequence_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)
    seq_coll = get_collection("sequences")
    doc = seq_coll.find_one({"_id": sequence_id, "bid_period_id": bid_period_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
    seq = _doc_to_sequence(doc)
    users_coll = get_collection("users")
    user_doc = users_coll.find_one({"_id": user_id})
    if user_doc:
        seq.eligibility = _compute_eligibility(doc, user_doc)
        commute_from = user_doc.get("profile", {}).get("commute_from")
        base_city = user_doc.get("profile", {}).get("base_city")
        if commute_from and base_city:
            impact = analyze_commute_impact(seq, commute_from, base_city)
            seq.commute_impact = CommuteImpact(**impact)
    return seq


@router.post("", status_code=201, response_model=Sequence)
async def create_sequence(
    bid_period_id: str,
    body: SequenceInput,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    seq_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = _input_to_doc(body, bid_period_id)
    doc["_id"] = seq_id
    doc["created_at"] = now
    doc["updated_at"] = now

    seq_coll = get_collection("sequences")
    seq_coll.insert_one(doc)

    return _doc_to_sequence(doc)


@router.put("/{sequence_id}", response_model=Sequence)
async def update_sequence(
    bid_period_id: str,
    sequence_id: str,
    body: SequenceInput,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    seq_coll = get_collection("sequences")
    existing = seq_coll.find_one({"_id": sequence_id, "bid_period_id": bid_period_id})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    now = datetime.now(timezone.utc).isoformat()
    updates = _input_to_doc(body, bid_period_id)
    updates["updated_at"] = now

    seq_coll.update_one({"_id": sequence_id}, {"$set": updates})
    updated = seq_coll.find_one({"_id": sequence_id})
    return _doc_to_sequence(updated)


@router.delete("/{sequence_id}", status_code=204)
async def delete_sequence(
    bid_period_id: str,
    sequence_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    seq_coll = get_collection("sequences")
    existing = seq_coll.find_one({"_id": sequence_id, "bid_period_id": bid_period_id})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    seq_coll.delete_one({"_id": sequence_id})
    return None
