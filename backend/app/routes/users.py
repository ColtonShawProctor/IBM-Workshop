from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_collection
from app.models.schemas import (
    UpdateUserRequest,
    User,
    Profile,
    Preferences,
)
from app.services.auth import get_current_user_id

router = APIRouter(prefix="/users", tags=["Users"])


def _doc_to_user(doc: dict) -> User:
    return User(
        id=doc["_id"],
        email=doc["email"],
        profile=Profile(**doc.get("profile", {})),
        default_preferences=Preferences(**doc.get("default_preferences", {})),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


@router.get("/me", response_model=User)
async def get_current_user(user_id: str = Depends(get_current_user_id)):
    users = get_collection("users")
    doc = users.find_one({"_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _doc_to_user(doc)


@router.put("/me", response_model=User)
async def update_current_user(
    body: UpdateUserRequest,
    user_id: str = Depends(get_current_user_id),
):
    users = get_collection("users")
    doc = users.find_one({"_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates: dict = {}
    now = datetime.now(timezone.utc).isoformat()

    if body.profile is not None:
        updates["profile"] = body.profile.model_dump()

    if body.default_preferences is not None:
        updates["default_preferences"] = body.default_preferences.model_dump()

    if not updates:
        return _doc_to_user(doc)

    updates["updated_at"] = now
    users.update_one({"_id": user_id}, {"$set": updates})

    updated_doc = users.find_one({"_id": user_id})
    return _doc_to_user(updated_doc)


@router.put("/me/preferences", response_model=Preferences)
async def update_default_preferences(
    body: Preferences,
    user_id: str = Depends(get_current_user_id),
):
    users = get_collection("users")
    doc = users.find_one({"_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    now = datetime.now(timezone.utc).isoformat()
    users.update_one(
        {"_id": user_id},
        {"$set": {"default_preferences": body.model_dump(), "updated_at": now}},
    )
    return body
