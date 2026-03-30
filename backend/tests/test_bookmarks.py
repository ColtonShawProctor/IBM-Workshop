"""Tests for bookmarks CRUD with duplicate prevention."""
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


def _seed(user_id: str):
    bp_coll = get_mock_collection("bid_periods")
    bp_coll.insert_one({
        "_id": "bp-001", "user_id": user_id, "name": "Jan 2026",
        "effective_start": "2026-01-01", "effective_end": "2026-01-30",
        "base_city": "ORD", "parse_status": "completed",
        "total_sequences": 2, "total_dates": 30, "categories": [],
    })
    seq_coll = get_mock_collection("sequences")
    seq_coll.insert_one({
        "_id": "seq-001", "bid_period_id": "bp-001", "seq_number": 663,
        "category": "777 INTL", "ops_count": 5,
        "position_min": 1, "position_max": 9,
        "operating_dates": [6, 7, 8], "totals": {}, "duty_periods": [],
    })
    seq_coll.insert_one({
        "_id": "seq-002", "bid_period_id": "bp-001", "seq_number": 664,
        "category": "NBD DOM", "ops_count": 25,
        "position_min": 1, "position_max": 4,
        "operating_dates": [10, 11], "totals": {}, "duty_periods": [],
    })


@pytest.fixture(autouse=True)
def _clean_db():
    reset_mock_db()
    with patch("app.routes.auth.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.users.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bid_periods.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.sequences.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bids.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bookmarks.get_collection", side_effect=get_mock_collection):
        yield
    reset_mock_db()


async def _register(client):
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, user_id


@pytest.mark.anyio
async def test_create_bookmark(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.post(
        "/bid-periods/bp-001/bookmarks",
        json={"sequence_id": "seq-001"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["sequence_id"] == "seq-001"
    assert data["seq_number"] == 663
    assert data["id"]


@pytest.mark.anyio
async def test_duplicate_bookmark_returns_409(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.post(
        "/bid-periods/bp-001/bookmarks",
        json={"sequence_id": "seq-001"},
        headers=headers,
    )
    assert resp.status_code == 201

    resp = await client.post(
        "/bid-periods/bp-001/bookmarks",
        json={"sequence_id": "seq-001"},
        headers=headers,
    )
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_bookmark_nonexistent_sequence(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.post(
        "/bid-periods/bp-001/bookmarks",
        json={"sequence_id": "nonexistent"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_list_bookmarks(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    await client.post("/bid-periods/bp-001/bookmarks", json={"sequence_id": "seq-001"}, headers=headers)
    await client.post("/bid-periods/bp-001/bookmarks", json={"sequence_id": "seq-002"}, headers=headers)

    resp = await client.get("/bid-periods/bp-001/bookmarks", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 2


@pytest.mark.anyio
async def test_list_bookmarks_empty(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.get("/bid-periods/bp-001/bookmarks", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0


@pytest.mark.anyio
async def test_delete_bookmark(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    create_resp = await client.post(
        "/bid-periods/bp-001/bookmarks",
        json={"sequence_id": "seq-001"},
        headers=headers,
    )
    bm_id = create_resp.json()["id"]

    resp = await client.delete(f"/bid-periods/bp-001/bookmarks/{bm_id}", headers=headers)
    assert resp.status_code == 204

    # Confirm gone
    resp = await client.get("/bid-periods/bp-001/bookmarks", headers=headers)
    assert len(resp.json()["data"]) == 0


@pytest.mark.anyio
async def test_delete_bookmark_not_found(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.delete("/bid-periods/bp-001/bookmarks/nonexistent", headers=headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_bookmark_bid_period_not_found(client):
    headers, _ = await _register(client)

    resp = await client.post(
        "/bid-periods/nonexistent/bookmarks",
        json={"sequence_id": "seq-001"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_can_rebookmark_after_delete(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    create_resp = await client.post(
        "/bid-periods/bp-001/bookmarks",
        json={"sequence_id": "seq-001"},
        headers=headers,
    )
    bm_id = create_resp.json()["id"]

    await client.delete(f"/bid-periods/bp-001/bookmarks/{bm_id}", headers=headers)

    # Should be able to bookmark again
    resp = await client.post(
        "/bid-periods/bp-001/bookmarks",
        json={"sequence_id": "seq-001"},
        headers=headers,
    )
    assert resp.status_code == 201
