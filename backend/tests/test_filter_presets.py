"""Tests for filter presets CRUD."""
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
        "language_qualifications": [],
    },
}

SAMPLE_FILTERS = {
    "categories": ["777 INTL"],
    "equipment_types": ["97"],
    "layover_cities": ["NRT"],
    "language": "JP",
    "tpay_min_minutes": 800,
    "tpay_max_minutes": 1200,
    "is_turn": False,
}


def _seed(user_id: str):
    bp_coll = get_mock_collection("bid_periods")
    bp_coll.insert_one({
        "_id": "bp-001", "user_id": user_id, "name": "Jan 2026",
        "effective_start": "2026-01-01", "effective_end": "2026-01-30",
        "base_city": "ORD", "parse_status": "completed",
        "total_sequences": 0, "total_dates": 30, "categories": [],
    })


@pytest.fixture(autouse=True)
def _clean_db():
    reset_mock_db()
    with patch("app.routes.auth.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.users.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bid_periods.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.sequences.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bids.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bookmarks.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.filter_presets.get_collection", side_effect=get_mock_collection):
        yield
    reset_mock_db()


async def _register(client):
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, user_id


@pytest.mark.anyio
async def test_create_filter_preset(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.post(
        "/bid-periods/bp-001/filter-presets",
        json={"name": "International High Pay", "filters": SAMPLE_FILTERS},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "International High Pay"
    assert data["filters"]["language"] == "JP"
    assert data["filters"]["tpay_min_minutes"] == 800
    assert data["id"]


@pytest.mark.anyio
async def test_list_filter_presets(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    await client.post(
        "/bid-periods/bp-001/filter-presets",
        json={"name": "Preset 1", "filters": SAMPLE_FILTERS},
        headers=headers,
    )
    await client.post(
        "/bid-periods/bp-001/filter-presets",
        json={"name": "Preset 2", "filters": {"is_turn": True}},
        headers=headers,
    )

    resp = await client.get("/bid-periods/bp-001/filter-presets", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


@pytest.mark.anyio
async def test_list_filter_presets_empty(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.get("/bid-periods/bp-001/filter-presets", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0


@pytest.mark.anyio
async def test_delete_filter_preset(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    create_resp = await client.post(
        "/bid-periods/bp-001/filter-presets",
        json={"name": "To Delete", "filters": {}},
        headers=headers,
    )
    preset_id = create_resp.json()["id"]

    resp = await client.delete(f"/bid-periods/bp-001/filter-presets/{preset_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get("/bid-periods/bp-001/filter-presets", headers=headers)
    assert len(resp.json()["data"]) == 0


@pytest.mark.anyio
async def test_delete_preset_not_found(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.delete("/bid-periods/bp-001/filter-presets/nonexistent", headers=headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_preset_bid_period_not_found(client):
    headers, _ = await _register(client)

    resp = await client.post(
        "/bid-periods/nonexistent/filter-presets",
        json={"name": "Test", "filters": {}},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_preset_preserves_all_filter_fields(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    full_filters = {
        "categories": ["NBD DOM"],
        "equipment_types": ["45"],
        "layover_cities": [],
        "language": None,
        "duty_days_min": 1,
        "duty_days_max": 3,
        "tpay_min_minutes": 500,
        "tpay_max_minutes": 1500,
        "tafb_min_minutes": 100,
        "tafb_max_minutes": 3000,
        "block_min_minutes": 200,
        "block_max_minutes": 2000,
        "operating_dates": [15, 16],
        "position_min": 1,
        "position_max": 4,
        "include_deadheads": False,
        "is_turn": True,
        "report_earliest": 360,
        "report_latest": 720,
        "release_earliest": 600,
        "release_latest": 1080,
    }

    resp = await client.post(
        "/bid-periods/bp-001/filter-presets",
        json={"name": "Full", "filters": full_filters},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()["filters"]
    assert data["duty_days_min"] == 1
    assert data["operating_dates"] == [15, 16]
    assert data["is_turn"] is True
    assert data["report_earliest"] == 360
