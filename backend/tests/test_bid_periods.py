from __future__ import annotations

import io
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
def _clean_db(tmp_path):
    reset_mock_db()
    with patch("app.routes.auth.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bid_periods.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bid_periods.run_parse"), \
         patch("app.routes.bid_periods.os.makedirs"), \
         patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__ = lambda s: io.BytesIO()
        mock_open.return_value.__exit__ = lambda s, *a: None
        yield


async def _register_and_get_token(client) -> str:
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _multipart_bid_period(name="January 2026", start="2026-01-01", end="2026-01-31"):
    return {
        "name": (None, name),
        "effective_start": (None, start),
        "effective_end": (None, end),
        "file": ("bidsheet.pdf", b"%PDF-fake-content", "application/pdf"),
    }


@pytest.mark.anyio
async def test_create_bid_period(client):
    token = await _register_and_get_token(client)
    resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period(),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["name"] == "January 2026"
    assert body["effective_start"] == "2026-01-01"
    assert body["effective_end"] == "2026-01-31"
    assert body["parse_status"] == "processing"
    assert body["source_filename"] == "bidsheet.pdf"
    assert body["id"] is not None


@pytest.mark.anyio
async def test_create_bid_period_invalid_dates(client):
    token = await _register_and_get_token(client)
    resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period(start="2026-02-01", end="2026-01-01"),
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_list_bid_periods(client):
    token = await _register_and_get_token(client)
    # Create two bid periods
    await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period("January 2026", "2026-01-01", "2026-01-31"),
    )
    await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period("February 2026", "2026-02-01", "2026-02-28"),
    )

    resp = await client.get(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    names = {bp["name"] for bp in body["data"]}
    assert names == {"January 2026", "February 2026"}


@pytest.mark.anyio
async def test_list_bid_periods_empty(client):
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.anyio
async def test_get_bid_period(client):
    token = await _register_and_get_token(client)
    create_resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period(),
    )
    bp_id = create_resp.json()["id"]

    resp = await client.get(
        f"/bid-periods/{bp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == bp_id
    assert resp.json()["name"] == "January 2026"


@pytest.mark.anyio
async def test_get_bid_period_not_found(client):
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/bid-periods/nonexistent-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_bid_period(client):
    token = await _register_and_get_token(client)
    create_resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period(),
    )
    bp_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/bid-periods/{bp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Verify it's gone
    resp = await client.get(
        f"/bid-periods/{bp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_bid_period_not_found(client):
    token = await _register_and_get_token(client)
    resp = await client.delete(
        "/bid-periods/nonexistent-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_cascade(client):
    token = await _register_and_get_token(client)
    create_resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period(),
    )
    bp_id = create_resp.json()["id"]

    # Insert associated data directly into mock collections
    sequences_coll = get_mock_collection("sequences")
    sequences_coll.insert_one({"_id": "seq-1", "bid_period_id": bp_id, "seq_number": 100})
    sequences_coll.insert_one({"_id": "seq-2", "bid_period_id": bp_id, "seq_number": 200})
    sequences_coll.insert_one({"_id": "seq-other", "bid_period_id": "other-bp", "seq_number": 300})

    bids_coll = get_mock_collection("bids")
    bids_coll.insert_one({"_id": "bid-1", "bid_period_id": bp_id, "name": "My Bid"})

    bookmarks_coll = get_mock_collection("bookmarks")
    bookmarks_coll.insert_one({"_id": "bm-1", "bid_period_id": bp_id, "sequence_id": "seq-1"})

    awarded_coll = get_mock_collection("awarded_schedules")
    awarded_coll.insert_one({"_id": "award-1", "bid_period_id": bp_id})

    # Delete the bid period
    resp = await client.delete(
        f"/bid-periods/{bp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Verify cascade: associated data is deleted
    assert sequences_coll.count_documents({"bid_period_id": bp_id}) == 0
    assert bids_coll.count_documents({"bid_period_id": bp_id}) == 0
    assert bookmarks_coll.count_documents({"bid_period_id": bp_id}) == 0
    assert awarded_coll.count_documents({"bid_period_id": bp_id}) == 0

    # Verify data from other bid periods is untouched
    assert sequences_coll.count_documents({"bid_period_id": "other-bp"}) == 1


@pytest.mark.anyio
async def test_user_isolation(client):
    """One user cannot see another user's bid periods."""
    token1 = await _register_and_get_token(client)

    # Create bid period as user 1
    create_resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token1}"},
        files=_multipart_bid_period(),
    )
    bp_id = create_resp.json()["id"]

    # Register user 2
    resp2 = await client.post("/auth/register", json={
        "email": "other@airline.com",
        "password": "securepass",
        "profile": {
            "display_name": "Bob",
            "base_city": "LAX",
            "seniority_number": 100,
            "total_base_fas": 2000,
            "position_min": 1,
            "position_max": 4,
        },
    })
    token2 = resp2.json()["access_token"]

    # User 2 should not see user 1's bid periods
    resp = await client.get(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0

    # User 2 should not access user 1's bid period by ID
    resp = await client.get(
        f"/bid-periods/{bp_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_unauthorized(client):
    resp = await client.get("/bid-periods")
    assert resp.status_code == 403


# ── Per-period preference overrides ──────────────────────────────────────


@pytest.mark.anyio
async def test_put_period_preferences(client):
    token = await _register_and_get_token(client)
    create_resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period(),
    )
    bp_id = create_resp.json()["id"]

    resp = await client.put(
        f"/bid-periods/{bp_id}/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "preferred_days_off": [1, 15],
            "preferred_layover_cities": ["NRT"],
            "avoid_redeyes": True,
            "weights": {"tpay": 9, "days_off": 7},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["preferred_days_off"] == [1, 15]
    assert body["preferred_layover_cities"] == ["NRT"]
    assert body["avoid_redeyes"] is True
    assert body["weights"]["tpay"] == 9


@pytest.mark.anyio
async def test_period_preferences_reflected_in_get(client):
    token = await _register_and_get_token(client)
    create_resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period(),
    )
    bp_id = create_resp.json()["id"]

    await client.put(
        f"/bid-periods/{bp_id}/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "preferred_equipment": ["777"],
            "cluster_trips": True,
        },
    )

    resp = await client.get(
        f"/bid-periods/{bp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    overrides = resp.json()["preference_overrides"]
    assert overrides["preferred_equipment"] == ["777"]
    assert overrides["cluster_trips"] is True


@pytest.mark.anyio
async def test_period_preferences_not_found(client):
    token = await _register_and_get_token(client)
    resp = await client.put(
        "/bid-periods/nonexistent/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={"avoid_redeyes": True},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_period_preferences_defaults(client):
    token = await _register_and_get_token(client)
    create_resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files=_multipart_bid_period(),
    )
    bp_id = create_resp.json()["id"]

    resp = await client.put(
        f"/bid-periods/{bp_id}/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["preferred_days_off"] == []
    assert body["avoid_redeyes"] is False
    assert body["weights"]["tpay"] == 5
