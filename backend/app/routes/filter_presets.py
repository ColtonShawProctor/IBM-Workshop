from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_collection
from app.models.schemas import FilterPreset, FilterPresetInput
from app.services.auth import get_current_user_id

router = APIRouter(
    prefix="/bid-periods/{bid_period_id}/filter-presets",
    tags=["Filter Presets"],
)


def _verify_bid_period(bid_period_id: str, user_id: str) -> dict:
    bp_coll = get_collection("bid_periods")
    doc = bp_coll.find_one({"_id": bid_period_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")
    return doc


def _doc_to_preset(doc: dict) -> FilterPreset:
    return FilterPreset(
        id=doc["_id"],
        name=doc.get("name", ""),
        filters=doc.get("filters", {}),
        created_at=doc.get("created_at"),
    )


@router.post("", status_code=201, response_model=FilterPreset)
async def create_filter_preset(
    bid_period_id: str,
    body: FilterPresetInput,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    preset_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "_id": preset_id,
        "user_id": user_id,
        "bid_period_id": bid_period_id,
        "name": body.name,
        "filters": body.filters.model_dump(),
        "created_at": now,
    }

    coll = get_collection("filter_presets")
    coll.insert_one(doc)

    return _doc_to_preset(doc)


@router.get("")
async def list_filter_presets(
    bid_period_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    coll = get_collection("filter_presets")
    docs = list(coll.find({"user_id": user_id, "bid_period_id": bid_period_id}))
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)

    return {"data": [_doc_to_preset(d) for d in docs]}


@router.delete("/{preset_id}", status_code=204)
async def delete_filter_preset(
    bid_period_id: str,
    preset_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    coll = get_collection("filter_presets")
    doc = coll.find_one({"_id": preset_id, "user_id": user_id, "bid_period_id": bid_period_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filter preset not found")

    coll.delete_one({"_id": preset_id})
    return None
