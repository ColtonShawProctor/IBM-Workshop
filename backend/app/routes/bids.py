from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as PydanticBaseModel

from app.db import get_collection
from app.models.schemas import (
    Bid,
    BidEntry,
    BidList,
    BidProperty,
    BidPropertyInput,
    BidSummary,
    CBAValidationResult,
    CommuteImpact,
    CreateBidRequest,
    DateCoverage,
    LayerSummary,
    NUM_LAYERS,
    Preferences,
    PROPERTY_DEFINITIONS,
    UpdateBidRequest,
)
from app.services.auth import get_current_user_id
from app.services.commute import analyze_commute_impact, analyze_commute_gap
from app.services.optimizer import optimize_bid, analyze_coverage, compute_layer_summaries, compute_projected_schedule
from app.services.cba_validator import validate_bid as run_cba_validation

router = APIRouter(
    prefix="/bid-periods/{bid_period_id}/bids",
    tags=["Bids"],
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _verify_bid_period(bid_period_id: str, user_id: str) -> dict:
    bp_coll = get_collection("bid_periods")
    bp_doc = bp_coll.find_one({"_id": bid_period_id, "user_id": user_id})
    if not bp_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")
    return bp_doc


def _verify_bid(bid_period_id: str, bid_id: str, user_id: str) -> dict:
    bids_coll = get_collection("bids")
    doc = bids_coll.find_one({"_id": bid_id, "bid_period_id": bid_period_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")
    return doc


def _compute_summary(entries: list[dict], bid_period_doc: dict) -> dict:
    """Recompute bid summary from entries by looking up their sequences."""
    seq_coll = get_collection("sequences")

    active_entries = [e for e in entries if not e.get("is_excluded", False)]

    total_tpay = 0
    total_block = 0
    total_tafb = 0
    leg_count = 0
    deadhead_count = 0
    international_count = 0
    domestic_count = 0
    layover_cities_set: set[str] = set()
    covered_dates_set: set[int] = set()
    conflict_groups: set[str] = set()

    for entry in active_entries:
        seq_doc = seq_coll.find_one({"_id": entry["sequence_id"]})
        if not seq_doc:
            continue

        totals = seq_doc.get("totals", {})
        total_tpay += totals.get("tpay_minutes", 0)
        total_block += totals.get("block_minutes", 0)
        total_tafb += totals.get("tafb_minutes", 0)
        leg_count += totals.get("leg_count", 0)
        deadhead_count += totals.get("deadhead_count", 0)

        category = (seq_doc.get("category") or "").upper()
        if "DOM" in category:
            domestic_count += 1
        else:
            international_count += 1

        for city in seq_doc.get("layover_cities", []):
            layover_cities_set.add(city)

        for d in seq_doc.get("operating_dates", []):
            covered_dates_set.add(d)

        dcg = entry.get("date_conflict_group")
        if dcg:
            conflict_groups.add(dcg)

    # Compute date coverage
    eff_start = bid_period_doc.get("effective_start", "")
    eff_end = bid_period_doc.get("effective_end", "")
    total_dates = bid_period_doc.get("total_dates", 0)

    # Build full set of period dates if we can
    if total_dates == 0 and eff_start and eff_end:
        try:
            from datetime import date as dt_date
            if isinstance(eff_start, str):
                s = dt_date.fromisoformat(eff_start)
            else:
                s = eff_start
            if isinstance(eff_end, str):
                e = dt_date.fromisoformat(eff_end)
            else:
                e = eff_end
            total_dates = (e - s).days + 1
        except (ValueError, TypeError):
            total_dates = 30

    all_period_dates = set(range(1, total_dates + 1))
    covered = sorted(covered_dates_set & all_period_dates)
    uncovered = sorted(all_period_dates - covered_dates_set)
    coverage_rate = len(covered) / total_dates if total_dates > 0 else 0.0

    total_days_off = len(uncovered)

    return {
        "total_entries": len(active_entries),
        "total_tpay_minutes": total_tpay,
        "total_block_minutes": total_block,
        "total_tafb_minutes": total_tafb,
        "total_days_off": total_days_off,
        "sequence_count": len(active_entries),
        "leg_count": leg_count,
        "deadhead_count": deadhead_count,
        "international_count": international_count,
        "domestic_count": domestic_count,
        "layover_cities": sorted(layover_cities_set),
        "date_coverage": {
            "covered_dates": covered,
            "uncovered_dates": uncovered,
            "coverage_rate": round(coverage_rate, 4),
        },
        "conflict_groups": len(conflict_groups),
    }


def _doc_to_bid(doc: dict) -> Bid:
    entries = []
    for e in doc.get("entries", []):
        ci_raw = e.get("commute_impact")
        ci = CommuteImpact(**ci_raw) if ci_raw else None
        entries.append(BidEntry(
            rank=e.get("rank", 0),
            sequence_id=e.get("sequence_id", ""),
            seq_number=e.get("seq_number", 0),
            is_pinned=e.get("is_pinned", False),
            is_excluded=e.get("is_excluded", False),
            rationale=e.get("rationale"),
            preference_score=e.get("preference_score", 0.0),
            attainability=e.get("attainability", "unknown"),
            date_conflict_group=e.get("date_conflict_group"),
            layer=e.get("layer", 0),
            commute_impact=ci,
        ))

    summary_raw = doc.get("summary", {})
    dc_raw = summary_raw.get("date_coverage", {})
    date_coverage = DateCoverage(
        covered_dates=dc_raw.get("covered_dates", []),
        uncovered_dates=dc_raw.get("uncovered_dates", []),
        coverage_rate=dc_raw.get("coverage_rate", 0.0),
    )
    summary = BidSummary(
        total_entries=summary_raw.get("total_entries", 0),
        total_tpay_minutes=summary_raw.get("total_tpay_minutes", 0),
        total_block_minutes=summary_raw.get("total_block_minutes", 0),
        total_tafb_minutes=summary_raw.get("total_tafb_minutes", 0),
        total_days_off=summary_raw.get("total_days_off", 0),
        sequence_count=summary_raw.get("sequence_count", 0),
        leg_count=summary_raw.get("leg_count", 0),
        deadhead_count=summary_raw.get("deadhead_count", 0),
        international_count=summary_raw.get("international_count", 0),
        domestic_count=summary_raw.get("domestic_count", 0),
        layover_cities=summary_raw.get("layover_cities", []),
        date_coverage=date_coverage,
        conflict_groups=summary_raw.get("conflict_groups", 0),
        commute_warnings=summary_raw.get("commute_warnings", []),
    )

    opt_cfg = doc.get("optimization_config")

    # Parse properties
    properties = []
    for p in doc.get("properties", []):
        try:
            properties.append(BidProperty(**p))
        except Exception:
            pass  # skip malformed properties

    return Bid(
        id=doc["_id"],
        bid_period_id=doc["bid_period_id"],
        name=doc.get("name", ""),
        status=doc.get("status", "draft"),
        entries=entries,
        properties=properties,
        summary=summary,
        optimization_config=opt_cfg,
        optimization_run_at=doc.get("optimization_run_at"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("", status_code=201, response_model=Bid)
async def create_bid(
    bid_period_id: str,
    body: CreateBidRequest,
    user_id: str = Depends(get_current_user_id),
):
    bp_doc = _verify_bid_period(bid_period_id, user_id)

    bid_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Resolve entries — look up seq_number for each sequence_id
    seq_coll = get_collection("sequences")
    entries = []
    for i, raw in enumerate(body.entries):
        sid = raw.get("sequence_id", "")
        seq_doc = seq_coll.find_one({"_id": sid, "bid_period_id": bid_period_id})
        if not seq_doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sequence {sid} not found in this bid period",
            )
        entries.append({
            "rank": raw.get("rank", i + 1),
            "sequence_id": sid,
            "seq_number": seq_doc.get("seq_number", 0),
            "is_pinned": raw.get("is_pinned", False),
            "is_excluded": raw.get("is_excluded", False),
            "rationale": None,
            "preference_score": 0.0,
            "attainability": "unknown",
            "date_conflict_group": None,
        })

    summary = _compute_summary(entries, bp_doc)

    doc = {
        "_id": bid_id,
        "bid_period_id": bid_period_id,
        "user_id": user_id,
        "name": body.name,
        "status": "draft",
        "entries": entries,
        "summary": summary,
        "optimization_config": None,
        "optimization_run_at": None,
        "created_at": now,
        "updated_at": now,
    }

    bids_coll = get_collection("bids")
    bids_coll.insert_one(doc)

    return _doc_to_bid(doc)


@router.get("", response_model=BidList)
async def list_bids(
    bid_period_id: str,
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=20, le=200),
    page_state: Optional[str] = None,
):
    _verify_bid_period(bid_period_id, user_id)

    bids_coll = get_collection("bids")
    docs = list(bids_coll.find({"bid_period_id": bid_period_id, "user_id": user_id}))

    # Sort by created_at descending (newest first)
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)

    offset = int(page_state) if page_state else 0
    page = docs[offset : offset + limit]
    next_state = str(offset + limit) if offset + limit < len(docs) else None

    return BidList(
        data=[_doc_to_bid(d) for d in page],
        page_state=next_state,
    )


@router.get("/{bid_id}", response_model=Bid)
async def get_bid(
    bid_period_id: str,
    bid_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)
    doc = _verify_bid(bid_period_id, bid_id, user_id)
    return _doc_to_bid(doc)


@router.put("/{bid_id}", response_model=Bid)
async def update_bid(
    bid_period_id: str,
    bid_id: str,
    body: UpdateBidRequest,
    user_id: str = Depends(get_current_user_id),
):
    bp_doc = _verify_bid_period(bid_period_id, user_id)
    existing = _verify_bid(bid_period_id, bid_id, user_id)

    now = datetime.now(timezone.utc).isoformat()
    updates: dict = {"updated_at": now}

    if body.name is not None:
        updates["name"] = body.name

    if body.status is not None:
        valid_statuses = {"draft", "optimized", "finalized", "exported"}
        if body.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}",
            )
        updates["status"] = body.status

    if body.entries is not None:
        seq_coll = get_collection("sequences")
        new_entries = []
        for entry_input in body.entries:
            seq_doc = seq_coll.find_one({"_id": entry_input.sequence_id, "bid_period_id": bid_period_id})
            if not seq_doc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sequence {entry_input.sequence_id} not found in this bid period",
                )
            # Preserve existing optimizer data if the entry existed before
            old_entry = next(
                (e for e in existing.get("entries", []) if e["sequence_id"] == entry_input.sequence_id),
                None,
            )
            new_entries.append({
                "rank": entry_input.rank,
                "sequence_id": entry_input.sequence_id,
                "seq_number": seq_doc.get("seq_number", 0),
                "is_pinned": entry_input.is_pinned,
                "is_excluded": entry_input.is_excluded,
                "rationale": old_entry.get("rationale") if old_entry else None,
                "preference_score": old_entry.get("preference_score", 0.0) if old_entry else 0.0,
                "attainability": old_entry.get("attainability", "unknown") if old_entry else "unknown",
                "date_conflict_group": old_entry.get("date_conflict_group") if old_entry else None,
            })

        updates["entries"] = new_entries
        updates["summary"] = _compute_summary(new_entries, bp_doc)

    bids_coll = get_collection("bids")
    bids_coll.update_one({"_id": bid_id}, {"$set": updates})

    updated = bids_coll.find_one({"_id": bid_id})
    return _doc_to_bid(updated)


@router.delete("/{bid_id}", status_code=204)
async def delete_bid(
    bid_period_id: str,
    bid_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)
    _verify_bid(bid_period_id, bid_id, user_id)
    bids_coll = get_collection("bids")
    bids_coll.delete_one({"_id": bid_id})
    return None


@router.get("/{bid_id}/summary", response_model=BidSummary)
async def get_bid_summary(
    bid_period_id: str,
    bid_id: str,
    user_id: str = Depends(get_current_user_id),
):
    bp_doc = _verify_bid_period(bid_period_id, user_id)
    bid_doc = _verify_bid(bid_period_id, bid_id, user_id)

    # Recompute fresh summary
    summary = _compute_summary(bid_doc.get("entries", []), bp_doc)

    dc_raw = summary.get("date_coverage", {})
    return BidSummary(
        total_entries=summary["total_entries"],
        total_tpay_minutes=summary["total_tpay_minutes"],
        total_block_minutes=summary["total_block_minutes"],
        total_tafb_minutes=summary["total_tafb_minutes"],
        total_days_off=summary["total_days_off"],
        sequence_count=summary["sequence_count"],
        leg_count=summary["leg_count"],
        deadhead_count=summary["deadhead_count"],
        international_count=summary["international_count"],
        domestic_count=summary["domestic_count"],
        layover_cities=summary["layover_cities"],
        date_coverage=DateCoverage(
            covered_dates=dc_raw.get("covered_dates", []),
            uncovered_dates=dc_raw.get("uncovered_dates", []),
            coverage_rate=dc_raw.get("coverage_rate", 0.0),
        ),
        conflict_groups=summary["conflict_groups"],
    )


@router.get("/{bid_id}/projected")
async def get_projected_schedules(
    bid_period_id: str,
    bid_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get projected 'best case' schedules for all 7 layers."""
    bp_doc = _verify_bid_period(bid_period_id, user_id)
    bid_doc = _verify_bid(bid_period_id, bid_id, user_id)

    # Load sequences
    seq_coll = get_collection("sequences")
    all_seqs = list(seq_coll.find({"bid_period_id": bid_period_id}))

    entries = bid_doc.get("entries", [])

    total_dates = bp_doc.get("total_dates", 30)
    if total_dates == 0:
        total_dates = 30

    # Get credit limits from user profile
    users_coll = get_collection("users")
    user_doc = users_coll.find_one({"_id": user_id})
    line_option = (user_doc or {}).get("profile", {}).get("line_option", "standard")
    if line_option == "high":
        credit_min, credit_max = 4200, 6600
    elif line_option == "low":
        credit_min, credit_max = 2400, 5400
    else:
        credit_min, credit_max = 4200, 5400

    # Compute projections for all 7 layers
    layers = []
    for layer_num in range(1, NUM_LAYERS + 1):
        proj = compute_projected_schedule(
            entries=entries,
            sequences=all_seqs,
            layer=layer_num,
            total_dates=total_dates,
            credit_min_minutes=credit_min,
            credit_max_minutes=credit_max,
        )
        layers.append(proj)

    return {"layers": layers}


class OptimizeRequest(PydanticBaseModel):
    preferences: Optional[Preferences] = None


@router.post("/{bid_id}/optimize", response_model=Bid)
async def optimize(
    bid_period_id: str,
    bid_id: str,
    body: Optional[OptimizeRequest] = None,
    user_id: str = Depends(get_current_user_id),
):
    bp_doc = _verify_bid_period(bid_period_id, user_id)
    bid_doc = _verify_bid(bid_period_id, bid_id, user_id)

    # Bid period must be fully parsed
    if bp_doc.get("parse_status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bid period parsing is not yet complete",
        )

    # Load user profile for seniority and language info
    users_coll = get_collection("users")
    user_doc = users_coll.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile = user_doc.get("profile", {})
    seniority_number = profile.get("seniority_number") or 1
    total_base_fas = profile.get("total_base_fas") or 1
    seniority_percentage = profile.get("seniority_percentage")
    commute_from = profile.get("commute_from")
    user_langs = profile.get("language_qualifications", [])

    # Use bid-specific preferences if provided, otherwise fall back to user defaults
    if body and body.preferences:
        merged_prefs = body.preferences.model_dump()
    else:
        default_prefs = user_doc.get("default_preferences", {})
        period_overrides = bp_doc.get("preference_overrides") or {}
        merged_prefs = {**default_prefs}
        for k, v in period_overrides.items():
            if v is not None:
                merged_prefs[k] = v

    # Load all sequences for this bid period
    seq_coll = get_collection("sequences")
    all_seqs = list(seq_coll.find({"bid_period_id": bid_period_id}))

    # Identify pinned and excluded entries from existing bid
    existing_entries = bid_doc.get("entries", [])
    pinned_entries = [
        {"sequence_id": e["sequence_id"], "rank": e["rank"]}
        for e in existing_entries if e.get("is_pinned")
    ]
    excluded_ids = {e["sequence_id"] for e in existing_entries if e.get("is_excluded")}

    # Compute total_dates
    total_dates = bp_doc.get("total_dates", 0)
    if total_dates == 0:
        eff_start = bp_doc.get("effective_start", "")
        eff_end = bp_doc.get("effective_end", "")
        if eff_start and eff_end:
            try:
                from datetime import date as dt_date
                s = dt_date.fromisoformat(eff_start) if isinstance(eff_start, str) else eff_start
                e = dt_date.fromisoformat(eff_end) if isinstance(eff_end, str) else eff_end
                total_dates = (e - s).days + 1
            except (ValueError, TypeError):
                total_dates = 30

    # Run optimizer
    MAX_BID_ENTRIES = 200  # Astra DB array limit is 1000; keep top entries only

    # Read PBS properties from the bid document (if any)
    bid_props = bid_doc.get("properties", [])
    active_props = [p for p in bid_props if p.get("is_enabled", True)]

    # Target credit range from bid period (set by user from bid package)
    target_credit_min = bp_doc.get("target_credit_min_minutes", 4200)
    target_credit_max = bp_doc.get("target_credit_max_minutes", 5400)

    optimized_entries = optimize_bid(
        sequences=all_seqs,
        prefs=merged_prefs,
        seniority_number=seniority_number,
        total_base_fas=total_base_fas,
        user_langs=user_langs,
        pinned_entries=pinned_entries,
        excluded_ids=excluded_ids,
        total_dates=total_dates,
        bid_properties=active_props if active_props else None,
        target_credit_min_minutes=target_credit_min,
        target_credit_max_minutes=target_credit_max,
        seniority_percentage=seniority_percentage,
        commute_from=commute_from,
    )

    # Trim to top N active entries + any excluded entries
    active = [e for e in optimized_entries if not e.get("is_excluded")]
    excluded = [e for e in optimized_entries if e.get("is_excluded")]
    if len(active) > MAX_BID_ENTRIES:
        active = active[:MAX_BID_ENTRIES]
    optimized_entries = active + excluded[:max(0, MAX_BID_ENTRIES - len(active))]
    # Re-rank
    for i, e in enumerate(optimized_entries):
        e["rank"] = i + 1

    # Build optimization config snapshot
    opt_config = {
        "preferences_used": merged_prefs,
        "seniority_number": seniority_number,
        "total_base_fas": total_base_fas,
        "pinned_ids": [pe["sequence_id"] for pe in pinned_entries],
        "excluded_ids": list(excluded_ids),
    }

    now = datetime.now(timezone.utc).isoformat()

    # Recompute summary
    summary = _compute_summary(optimized_entries, bp_doc)

    # Add commute impact annotations if user has commute_from
    base_city = profile.get("base_city")
    if commute_from and base_city:
        seq_lookup = {s["_id"]: s for s in all_seqs}
        commute_warnings = []
        for entry in optimized_entries:
            seq_doc = seq_lookup.get(entry.get("sequence_id"))
            if seq_doc:
                impact = analyze_commute_impact(seq_doc, commute_from, base_city)
                entry["commute_impact"] = impact
            # Collect commute_notes from optimizer's annotate_commute
            for note in entry.get("commute_notes", []):
                if "Back-to-back" in note or "Tight turnaround" in note or "Hotel night" in note:
                    seq_num = entry.get("seq_number", "?")
                    commute_warnings.append(f"SEQ {seq_num}: {note}")
        summary["commute_warnings"] = commute_warnings

    updates = {
        "entries": optimized_entries,
        "summary": summary,
        "status": "optimized",
        "optimization_config": opt_config,
        "optimization_run_at": now,
        "updated_at": now,
    }

    bids_coll = get_collection("bids")
    bids_coll.update_one({"_id": bid_id}, {"$set": updates})

    updated = bids_coll.find_one({"_id": bid_id})
    return _doc_to_bid(updated)


# ── PBS Property CRUD ─────────────────────────────────────────────────────


@router.get("/{bid_id}/properties", response_model=list[BidProperty])
async def list_bid_properties(
    bid_period_id: str,
    bid_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """List all properties on this bid."""
    _verify_bid_period(bid_period_id, user_id)
    doc = _verify_bid(bid_period_id, bid_id, user_id)
    props = []
    for p in doc.get("properties", []):
        try:
            props.append(BidProperty(**p))
        except Exception:
            pass
    return props


@router.post("/{bid_id}/properties", status_code=201, response_model=BidProperty)
async def add_bid_property(
    bid_period_id: str,
    bid_id: str,
    body: BidPropertyInput,
    user_id: str = Depends(get_current_user_id),
):
    """Add a PBS property to this bid."""
    _verify_bid_period(bid_period_id, user_id)
    _verify_bid(bid_period_id, bid_id, user_id)

    defn = PROPERTY_DEFINITIONS.get(body.property_key)
    if not defn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown property_key: {body.property_key}",
        )

    prop_id = str(uuid.uuid4())
    prop_doc = {
        "id": prop_id,
        "property_key": body.property_key,
        "category": defn["category"],
        "value": body.value,
        "layers": body.layers,
        "is_enabled": body.is_enabled,
    }

    bids_coll = get_collection("bids")
    # Get current properties and append
    bid_doc = bids_coll.find_one({"_id": bid_id})
    props = bid_doc.get("properties", [])
    props.append(prop_doc)
    now = datetime.now(timezone.utc).isoformat()
    bids_coll.update_one({"_id": bid_id}, {"$set": {"properties": props, "updated_at": now}})

    return BidProperty(**prop_doc)


@router.put("/{bid_id}/properties/{property_id}", response_model=BidProperty)
async def update_bid_property(
    bid_period_id: str,
    bid_id: str,
    property_id: str,
    body: BidPropertyInput,
    user_id: str = Depends(get_current_user_id),
):
    """Update a PBS property on this bid."""
    _verify_bid_period(bid_period_id, user_id)
    bid_doc = _verify_bid(bid_period_id, bid_id, user_id)

    props = bid_doc.get("properties", [])
    found = False
    for i, p in enumerate(props):
        if p.get("id") == property_id:
            defn = PROPERTY_DEFINITIONS.get(body.property_key, PROPERTY_DEFINITIONS.get(p["property_key"], {}))
            props[i] = {
                "id": property_id,
                "property_key": body.property_key,
                "category": defn.get("category", p.get("category", "")),
                "value": body.value,
                "layers": body.layers,
                "is_enabled": body.is_enabled,
            }
            found = True
            break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    bids_coll = get_collection("bids")
    now = datetime.now(timezone.utc).isoformat()
    bids_coll.update_one({"_id": bid_id}, {"$set": {"properties": props, "updated_at": now}})

    return BidProperty(**props[i])


@router.delete("/{bid_id}/properties/{property_id}", status_code=204)
async def delete_bid_property(
    bid_period_id: str,
    bid_id: str,
    property_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Remove a PBS property from this bid."""
    _verify_bid_period(bid_period_id, user_id)
    bid_doc = _verify_bid(bid_period_id, bid_id, user_id)

    props = bid_doc.get("properties", [])
    new_props = [p for p in props if p.get("id") != property_id]

    if len(new_props) == len(props):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    bids_coll = get_collection("bids")
    now = datetime.now(timezone.utc).isoformat()
    bids_coll.update_one({"_id": bid_id}, {"$set": {"properties": new_props, "updated_at": now}})
    return None


@router.get("/{bid_id}/layers", response_model=list[LayerSummary])
async def get_layer_summaries(
    bid_period_id: str,
    bid_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Compute pairing counts per layer based on current bid properties."""
    _verify_bid_period(bid_period_id, user_id)
    bid_doc = _verify_bid(bid_period_id, bid_id, user_id)

    properties = bid_doc.get("properties", [])

    # Load all sequences for the bid period
    seq_coll = get_collection("sequences")
    all_seqs = list(seq_coll.find({"bid_period_id": bid_period_id}))

    raw_summaries = compute_layer_summaries(all_seqs, properties, NUM_LAYERS)
    return [LayerSummary(**s) for s in raw_summaries]


@router.post("/{bid_id}/validate", response_model=CBAValidationResult)
async def validate_bid_cba(
    bid_period_id: str,
    bid_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Validate bid against AA/APFA CBA constraints."""
    bp_doc = _verify_bid_period(bid_period_id, user_id)
    bid_doc = _verify_bid(bid_period_id, bid_id, user_id)

    # Load user profile
    users_coll = get_collection("users")
    user_doc = users_coll.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile = user_doc.get("profile", {})
    is_reserve = profile.get("is_reserve", False)
    line_option = profile.get("line_option", "standard")

    # Load sequences for active bid entries
    seq_coll = get_collection("sequences")
    entries = bid_doc.get("entries", [])
    active_entries = [e for e in entries if not e.get("is_excluded", False)]

    sequence_dicts = []
    for entry in active_entries:
        seq_doc = seq_coll.find_one({"_id": entry["sequence_id"]})
        if seq_doc:
            sequence_dicts.append(seq_doc)

    # Compute bid period days
    total_dates = bp_doc.get("total_dates", 30)
    if total_dates == 0:
        total_dates = 30

    result = run_cba_validation(
        sequences=sequence_dicts,
        line_option=line_option,
        is_reserve=is_reserve,
        bid_period_days=total_dates,
    )

    return result


class ExportRequest(PydanticBaseModel):
    format: str = "txt"


@router.post("/{bid_id}/export")
async def export_bid(
    bid_period_id: str,
    bid_id: str,
    body: Optional[ExportRequest] = None,
    user_id: str = Depends(get_current_user_id),
):
    bp_doc = _verify_bid_period(bid_period_id, user_id)
    bid_doc = _verify_bid(bid_period_id, bid_id, user_id)

    fmt = (body.format if body else "txt").lower()
    if fmt not in ("txt", "csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported export format. Use 'txt' or 'csv'.",
        )

    entries = bid_doc.get("entries", [])
    active = [e for e in entries if not e.get("is_excluded", False)]
    active.sort(key=lambda e: e.get("rank", 0))

    bid_name = bid_doc.get("name", "bid")
    period_name = bp_doc.get("name", "period")

    if fmt == "txt":
        lines = [f"# Bid Export: {bid_name}", f"# Period: {period_name}", ""]

        # Detect 7 vs 9 layer mode
        max_layer = max((e.get("layer", 1) for e in active), default=1)
        is_pbs_mode = max_layer <= NUM_LAYERS

        layer_names_9 = [
            "Dream Schedule", "Strong Alternative", "Preferred Backup",
            "Solid Option", "Mid-Tier", "Fallback Plan",
            "Safety Net", "Deep Reserve", "Last Resort",
        ]
        num_layers_export = NUM_LAYERS if is_pbs_mode else 9

        # Include property summary for PBS bids
        bid_props = bid_doc.get("properties", [])
        if bid_props and is_pbs_mode:
            lines.append("# PBS Properties Summary")
            for li in range(1, num_layers_export + 1):
                layer_props = [p for p in bid_props if li in p.get("layers", []) and p.get("is_enabled", True)]
                if layer_props:
                    prop_labels = [p.get("property_key", "").replace("_", " ") for p in layer_props]
                    lines.append(f"#   Layer {li}: {', '.join(prop_labels)}")
            lines.append("")

        # Group by layer field
        from collections import defaultdict
        by_layer: dict[int, list] = defaultdict(list)
        for e in active:
            by_layer[e.get("layer", 0)].append(e)

        for li in range(1, num_layers_export + 1):
            layer_entries = by_layer.get(li, [])
            if not layer_entries:
                continue
            if is_pbs_mode:
                label = f"Layer {li}"
            else:
                label = layer_names_9[li - 1] if li <= 9 else f"Layer {li}"
            lines.append(f"=== LAYER {li}: {label} ({len(layer_entries)} sequences) ===")
            for e in layer_entries:
                lines.append(f"  SEQ {e.get('seq_number', '')}")
            lines.append("")

        lines.append(f"Total sequences: {len(active)}")
        content = "\n".join(lines)

        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="text/plain",
            headers={"Content-Disposition": 'attachment; filename="bid-export.txt"'},
        )

    # CSV format
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Layer", "Rank", "SEQ Number", "Pinned", "Attainability", "Preference Score", "Conflict Group", "Rationale"])
    for e in active:
        writer.writerow([
            e.get("layer", ""),
            e["rank"],
            e.get("seq_number", ""),
            "Yes" if e.get("is_pinned") else "No",
            e.get("attainability", "unknown"),
            f"{e.get('preference_score', 0):.4f}",
            e.get("date_conflict_group", ""),
            e.get("rationale", ""),
        ])

    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bid-export.csv"'},
    )
