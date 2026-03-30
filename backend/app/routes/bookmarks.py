from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.db import get_collection
from app.models.schemas import Bookmark, BookmarkList
from app.services.auth import get_current_user_id

router = APIRouter(
    prefix="/bid-periods/{bid_period_id}/bookmarks",
    tags=["Bookmarks"],
)


def _verify_bid_period(bid_period_id: str, user_id: str) -> dict:
    bp_coll = get_collection("bid_periods")
    doc = bp_coll.find_one({"_id": bid_period_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")
    return doc


class CreateBookmarkRequest(BaseModel):
    sequence_id: str


@router.post("", status_code=201, response_model=Bookmark)
async def create_bookmark(
    bid_period_id: str,
    body: CreateBookmarkRequest,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    # Verify sequence exists in this bid period
    seq_coll = get_collection("sequences")
    seq_doc = seq_coll.find_one({"_id": body.sequence_id, "bid_period_id": bid_period_id})
    if not seq_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sequence not found in this bid period",
        )

    # Duplicate prevention
    bm_coll = get_collection("bookmarks")
    existing = bm_coll.find_one({
        "user_id": user_id,
        "bid_period_id": bid_period_id,
        "sequence_id": body.sequence_id,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sequence is already bookmarked",
        )

    bm_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "_id": bm_id,
        "user_id": user_id,
        "bid_period_id": bid_period_id,
        "sequence_id": body.sequence_id,
        "seq_number": seq_doc.get("seq_number", 0),
        "created_at": now,
    }
    bm_coll.insert_one(doc)

    return Bookmark(
        id=doc["_id"],
        sequence_id=doc["sequence_id"],
        seq_number=doc["seq_number"],
        created_at=doc["created_at"],
    )


@router.get("", response_model=BookmarkList)
async def list_bookmarks(
    bid_period_id: str,
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, le=200),
    page_state: Optional[str] = None,
):
    _verify_bid_period(bid_period_id, user_id)

    bm_coll = get_collection("bookmarks")
    docs = list(bm_coll.find({"user_id": user_id, "bid_period_id": bid_period_id}))
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)

    offset = int(page_state) if page_state else 0
    page = docs[offset : offset + limit]
    next_state = str(offset + limit) if offset + limit < len(docs) else None

    data = [
        Bookmark(
            id=d["_id"],
            sequence_id=d["sequence_id"],
            seq_number=d.get("seq_number", 0),
            created_at=d.get("created_at"),
        )
        for d in page
    ]

    return BookmarkList(data=data, page_state=next_state)


@router.delete("/{bookmark_id}", status_code=204)
async def delete_bookmark(
    bid_period_id: str,
    bookmark_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    bm_coll = get_collection("bookmarks")
    doc = bm_coll.find_one({"_id": bookmark_id, "user_id": user_id, "bid_period_id": bid_period_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")

    bm_coll.delete_one({"_id": bookmark_id})
    return None
