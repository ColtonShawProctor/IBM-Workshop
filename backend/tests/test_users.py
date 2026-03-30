from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.mock_db import get_mock_collection, reset_mock_db


REGISTER_PAYLOAD = {
    "email": "fa@airline.com",
    "password": "securepass",
    "profile": {
        "display_name": "Jane",
        "base_city": "ORD",
        "seniority_number": 500,
        "total_base_fas": 3000,
        "position_min": 1,
        "position_max": 4,
    },
}


@pytest.fixture(autouse=True)
def _clean_db():
    reset_mock_db()
    with patch("app.routes.auth.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.users.get_collection", side_effect=get_mock_collection):
        yield


async def _register_and_get_token(client) -> str:
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.mark.anyio
async def test_get_me(client):
    token = await _register_and_get_token(client)
    resp = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "fa@airline.com"
    assert body["profile"]["base_city"] == "ORD"
    assert body["profile"]["seniority_number"] == 500
    assert "default_preferences" in body


@pytest.mark.anyio
async def test_get_me_unauthorized(client):
    resp = await client.get("/users/me")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_update_profile(client):
    token = await _register_and_get_token(client)
    resp = await client.put(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "profile": {
                "display_name": "Jane Updated",
                "base_city": "LAX",
                "seniority_number": 250,
                "total_base_fas": 2500,
                "position_min": 1,
                "position_max": 9,
            }
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"]["base_city"] == "LAX"
    assert body["profile"]["seniority_number"] == 250
    assert body["profile"]["display_name"] == "Jane Updated"


@pytest.mark.anyio
async def test_update_preferences(client):
    token = await _register_and_get_token(client)
    resp = await client.put(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "default_preferences": {
                "preferred_days_off": [1, 15, 20],
                "preferred_layover_cities": ["NRT", "LHR"],
                "avoid_redeyes": True,
            }
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    prefs = body["default_preferences"]
    assert prefs["preferred_days_off"] == [1, 15, 20]
    assert prefs["preferred_layover_cities"] == ["NRT", "LHR"]
    assert prefs["avoid_redeyes"] is True


@pytest.mark.anyio
async def test_update_both_profile_and_preferences(client):
    token = await _register_and_get_token(client)
    resp = await client.put(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "profile": {
                "display_name": "Jane",
                "base_city": "SFO",
                "seniority_number": 100,
                "total_base_fas": 2000,
                "position_min": 1,
                "position_max": 9,
                "language_qualifications": ["JP"],
            },
            "default_preferences": {
                "preferred_equipment": ["777", "787"],
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"]["base_city"] == "SFO"
    assert body["profile"]["language_qualifications"] == ["JP"]
    assert body["default_preferences"]["preferred_equipment"] == ["777", "787"]


@pytest.mark.anyio
async def test_update_empty_body(client):
    token = await _register_and_get_token(client)
    resp = await client.put(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"]["base_city"] == "ORD"


@pytest.mark.anyio
async def test_get_me_reflects_update(client):
    token = await _register_and_get_token(client)
    await client.put(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "profile": {
                "display_name": "Jane",
                "base_city": "DEN",
                "seniority_number": 500,
                "total_base_fas": 3000,
                "position_min": 1,
                "position_max": 4,
            }
        },
    )
    resp = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["profile"]["base_city"] == "DEN"


@pytest.mark.anyio
async def test_put_preferences_endpoint(client):
    token = await _register_and_get_token(client)
    resp = await client.put(
        "/users/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "preferred_days_off": [5, 10, 25],
            "preferred_layover_cities": ["NRT", "HNL"],
            "avoided_layover_cities": ["EWR"],
            "tpay_min_minutes": 300,
            "tpay_max_minutes": 600,
            "preferred_equipment": ["777"],
            "report_earliest_minutes": 360,
            "report_latest_minutes": 720,
            "avoid_redeyes": True,
            "cluster_trips": True,
            "weights": {"tpay": 9, "days_off": 8},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["preferred_days_off"] == [5, 10, 25]
    assert body["preferred_layover_cities"] == ["NRT", "HNL"]
    assert body["avoided_layover_cities"] == ["EWR"]
    assert body["tpay_min_minutes"] == 300
    assert body["avoid_redeyes"] is True
    assert body["weights"]["tpay"] == 9
    assert body["weights"]["days_off"] == 8


@pytest.mark.anyio
async def test_put_preferences_reflects_in_get_me(client):
    token = await _register_and_get_token(client)
    await client.put(
        "/users/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "preferred_layover_cities": ["LHR"],
            "avoid_redeyes": True,
        },
    )
    resp = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    prefs = resp.json()["default_preferences"]
    assert prefs["preferred_layover_cities"] == ["LHR"]
    assert prefs["avoid_redeyes"] is True


@pytest.mark.anyio
async def test_put_preferences_unauthorized(client):
    resp = await client.put("/users/me/preferences", json={"avoid_redeyes": True})
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_put_preferences_defaults(client):
    token = await _register_and_get_token(client)
    resp = await client.put(
        "/users/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["preferred_days_off"] == []
    assert body["avoid_redeyes"] is False
    assert body["weights"]["tpay"] == 5


# ── Task 54: CBA profile fields through API ─────────────────────────────────


CBA_REGISTER_PAYLOAD = {
    "email": "cba@airline.com",
    "password": "securepass",
    "profile": {
        "display_name": "CBA FA",
        "base_city": "ORD",
        "seniority_number": 500,
        "total_base_fas": 3000,
        "position_min": 1,
        "position_max": 4,
        "years_of_service": 5,
        "is_reserve": True,
        "is_purser_qualified": False,
        "line_option": "high",
    },
}


@pytest.mark.anyio
async def test_register_with_cba_fields(client):
    """Task 54: Register with CBA profile fields."""
    resp = await client.post("/auth/register", json=CBA_REGISTER_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    profile = body["user"]["profile"]
    assert profile["years_of_service"] == 5
    assert profile["is_reserve"] is True
    assert profile["is_purser_qualified"] is False
    assert profile["line_option"] == "high"


@pytest.mark.anyio
async def test_update_profile_cba_fields(client):
    """Task 54: Update profile to set CBA fields."""
    token = await _register_and_get_token(client)
    resp = await client.put(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "profile": {
                "display_name": "Jane",
                "base_city": "ORD",
                "seniority_number": 500,
                "total_base_fas": 3000,
                "position_min": 1,
                "position_max": 4,
                "is_purser_qualified": True,
                "years_of_service": 10,
                "line_option": "low",
            }
        },
    )
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert profile["is_purser_qualified"] is True
    assert profile["years_of_service"] == 10
    assert profile["line_option"] == "low"


@pytest.mark.anyio
async def test_get_me_returns_cba_fields(client):
    """Task 54: GET /users/me returns all CBA fields."""
    resp = await client.post("/auth/register", json=CBA_REGISTER_PAYLOAD)
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    resp = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert profile["years_of_service"] == 5
    assert profile["is_reserve"] is True
    assert profile["line_option"] == "high"
