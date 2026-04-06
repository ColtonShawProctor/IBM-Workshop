from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.db import get_collection
from app.models.schemas import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    User,
    Profile,
    Preferences,
)
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=201, response_model=AuthResponse)
async def register(body: RegisterRequest):
    users = get_collection("users")
    existing = users.find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "_id": user_id,
        "email": body.email,
        "password_hash": hash_password(body.password),
        "profile": body.profile.model_dump(),
        "default_preferences": Preferences().model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    users.insert_one(doc)

    access_token, expires_in = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    user_out = _doc_to_user(doc)
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=user_out,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    users = get_collection("users")
    doc = users.find_one({"email": body.email})
    if not doc or not verify_password(body.password, doc["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user_id = doc["_id"]
    access_token, expires_in = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    user_out = _doc_to_user(doc)
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=user_out,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(body: dict):
    """Exchange a valid refresh token for a new access + refresh token pair (rotation)."""
    token = body.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="refresh_token required")

    user_id = decode_refresh_token(token)

    users = get_collection("users")
    doc = users.find_one({"_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access, expires_in = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    return AuthResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=expires_in,
        user=_doc_to_user(doc),
    )


@router.post("/auto-setup", response_model=AuthResponse)
async def auto_setup():
    """Auto-create or login the default user with Katya's profile.

    Zero-config endpoint: creates the default account on first call,
    logs in on subsequent calls. No password required.
    """
    default_email = "katya@bidpilot.local"
    default_password = "auto-setup-default-2026"

    users = get_collection("users")
    doc = users.find_one({"email": default_email})

    if doc:
        # Already exists — just log in
        user_id = doc["_id"]
    else:
        # First time — create with Katya's profile
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "_id": user_id,
            "email": default_email,
            "password_hash": hash_password(default_password),
            "profile": {
                "display_name": "Katya Johansen",
                "base_city": "ORD",
                "commute_from": "DCA",
                "seniority_number": 1170,
                "total_base_fas": 2323,
                "seniority_percentage": 50.3,
                "position_min": 1,
                "position_max": 9,
                "language_qualifications": [],
                "years_of_service": 15,
                "is_reserve": False,
                "is_purser_qualified": False,
                "line_option": "standard",
            },
            "default_preferences": {
                "preferred_days_off": [],
                "preferred_layover_cities": ["SFO", "DEN", "BOS", "SAN"],
                "avoided_layover_cities": ["CLT", "RDU"],
                "tpay_min_minutes": 5100,     # 85 hours
                "tpay_max_minutes": 5400,     # 90 hours
                "preferred_equipment": [],
                "report_earliest_minutes": None,    # no hard cutoff — hotel model handles it
                "report_latest_minutes": None,
                "release_earliest_minutes": None,
                "release_latest_minutes": None,    # no hard cutoff — hotel model handles it
                "avoid_redeyes": True,
                "prefer_turns": None,
                "prefer_high_ops": True,
                "cluster_trips": True,
                "weights": {
                    "days_off": 5,
                    "tpay": 5,
                    "layover_city": 4,
                    "equipment": 3,
                    "report_time": 8,     # HIGH for commuter
                    "release_time": 7,    # HIGH for commuter
                    "redeye": 8,
                    "trip_length": 5,
                    "clustering": 6,
                },
            },
            "created_at": now,
            "updated_at": now,
        }
        users.insert_one(doc)

    access_token, expires_in = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=_doc_to_user(doc),
    )


def _doc_to_user(doc: dict) -> User:
    return User(
        id=doc["_id"],
        email=doc["email"],
        profile=Profile(**doc.get("profile", {})),
        default_preferences=Preferences(**doc.get("default_preferences", {})),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )
