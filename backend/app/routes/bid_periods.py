from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from pydantic import BaseModel

from app.db import get_collection
from app.models.schemas import BidPeriod, BidPeriodList, Preferences
from app.services.auth import get_current_user_id
from app.services.parse_runner import run_parse

router = APIRouter(prefix="/bid-periods", tags=["Bid Periods"])


def _doc_to_bid_period(doc: dict) -> BidPeriod:
    return BidPeriod(
        id=doc["_id"],
        name=doc["name"],
        effective_start=doc["effective_start"],
        effective_end=doc["effective_end"],
        base_city=doc.get("base_city"),
        source_filename=doc.get("source_filename"),
        parse_status=doc.get("parse_status", "pending"),
        parse_error=doc.get("parse_error"),
        total_sequences=doc.get("total_sequences", 0),
        total_dates=doc.get("total_dates", 0),
        categories=doc.get("categories", []),
        issued_date=doc.get("issued_date"),
        target_credit_min_minutes=doc.get("target_credit_min_minutes", 4200),
        target_credit_max_minutes=doc.get("target_credit_max_minutes", 5400),
        preference_overrides=doc.get("preference_overrides"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


@router.post("", status_code=202, response_model=BidPeriod)
async def create_bid_period(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    effective_start: date = Form(...),
    effective_end: date = Form(...),
    airline_code: Optional[str] = Form(None),
    target_credit_min_minutes: int = Form(4200),
    target_credit_max_minutes: int = Form(5400),
    user_id: str = Depends(get_current_user_id),
):
    if effective_end <= effective_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="effective_end must be after effective_start",
        )

    bid_period_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Save uploaded file
    upload_dir = os.path.join("uploads", user_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{bid_period_id}.pdf")
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = {
        "_id": bid_period_id,
        "user_id": user_id,
        "name": name,
        "effective_start": effective_start.isoformat(),
        "effective_end": effective_end.isoformat(),
        "source_filename": file.filename,
        "parse_status": "processing",
        "parse_error": None,
        "total_sequences": 0,
        "total_dates": 0,
        "categories": [],
        "issued_date": None,
        "target_credit_min_minutes": target_credit_min_minutes,
        "target_credit_max_minutes": target_credit_max_minutes,
        "preference_overrides": None,
        "created_at": now,
        "updated_at": now,
    }

    bid_periods = get_collection("bid_periods")
    bid_periods.insert_one(doc)

    # Launch background PDF parsing
    background_tasks.add_task(run_parse, bid_period_id, user_id, file_path, airline_code)

    return _doc_to_bid_period(doc)


@router.get("", response_model=BidPeriodList)
async def list_bid_periods(
    limit: int = 20,
    page_state: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
):
    bid_periods = get_collection("bid_periods")
    docs = bid_periods.find({"user_id": user_id}, limit=limit)
    data = [_doc_to_bid_period(d) for d in docs]
    return BidPeriodList(data=data, page_state=None)


@router.get("/{bid_period_id}", response_model=BidPeriod)
async def get_bid_period(
    bid_period_id: str,
    user_id: str = Depends(get_current_user_id),
):
    bid_periods = get_collection("bid_periods")
    doc = bid_periods.find_one({"_id": bid_period_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")
    return _doc_to_bid_period(doc)


@router.delete("/{bid_period_id}", status_code=204)
async def delete_bid_period(
    bid_period_id: str,
    user_id: str = Depends(get_current_user_id),
):
    bid_periods = get_collection("bid_periods")
    doc = bid_periods.find_one({"_id": bid_period_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")

    # Cascade delete associated data
    for collection_name in ("sequences", "bids", "bookmarks", "awarded_schedules"):
        coll = get_collection(collection_name)
        coll.delete_many({"bid_period_id": bid_period_id})

    bid_periods.delete_one({"_id": bid_period_id})

    return None


class UpdateTargetCreditRequest(BaseModel):
    target_credit_min_minutes: int
    target_credit_max_minutes: int


@router.put("/{bid_period_id}/target-credit", response_model=BidPeriod)
async def update_target_credit(
    bid_period_id: str,
    body: UpdateTargetCreditRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Set the target credit hour range for this bid period (from the bid package)."""
    bid_periods = get_collection("bid_periods")
    doc = bid_periods.find_one({"_id": bid_period_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")

    if body.target_credit_min_minutes >= body.target_credit_max_minutes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min must be less than max",
        )

    now = datetime.now(timezone.utc).isoformat()
    bid_periods.update_one(
        {"_id": bid_period_id},
        {"$set": {
            "target_credit_min_minutes": body.target_credit_min_minutes,
            "target_credit_max_minutes": body.target_credit_max_minutes,
            "updated_at": now,
        }},
    )
    updated = bid_periods.find_one({"_id": bid_period_id})
    return _doc_to_bid_period(updated)


@router.put("/{bid_period_id}/preferences", response_model=Preferences)
async def update_bid_period_preferences(
    bid_period_id: str,
    body: Preferences,
    user_id: str = Depends(get_current_user_id),
):
    bid_periods = get_collection("bid_periods")
    doc = bid_periods.find_one({"_id": bid_period_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")

    now = datetime.now(timezone.utc).isoformat()
    bid_periods.update_one(
        {"_id": bid_period_id},
        {"$set": {"preference_overrides": body.model_dump(), "updated_at": now}},
    )
    return body
