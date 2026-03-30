"""Tests for POST /bid-periods/{id}/bids/{id}/optimize endpoint."""
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
        "position_max": 9,
        "language_qualifications": ["JP"],
    },
}


def _seed_bid_period(user_id: str, parse_status="completed") -> str:
    bp_id = "bp-001"
    coll = get_mock_collection("bid_periods")
    coll.insert_one({
        "_id": bp_id,
        "user_id": user_id,
        "name": "January 2026",
        "effective_start": "2026-01-01",
        "effective_end": "2026-01-30",
        "base_city": "ORD",
        "parse_status": parse_status,
        "total_sequences": 4,
        "total_dates": 30,
        "categories": ["777 INTL", "NBD DOM"],
        "preference_overrides": None,
    })
    return bp_id


def _seed_sequences(bp_id: str):
    coll = get_mock_collection("sequences")
    # High TPAY international with preferred layover
    coll.insert_one({
        "_id": "seq-001",
        "bid_period_id": bp_id,
        "seq_number": 663,
        "category": "777 INTL",
        "ops_count": 5,
        "position_min": 1, "position_max": 9,
        "language": "JP", "language_count": 3,
        "operating_dates": [6, 7, 8, 9],
        "is_turn": False, "has_deadhead": False, "is_redeye": False,
        "totals": {"block_minutes": 1000, "synth_minutes": 100, "tpay_minutes": 1100,
                   "tafb_minutes": 2800, "duty_days": 3, "leg_count": 4, "deadhead_count": 0},
        "layover_cities": ["NRT"],
        "duty_periods": [
            {"report_base": "17:10", "release_base": "08:45",
             "legs": [{"equipment": "97"}]},
        ],
    })
    # Overlaps seq-001 (dates 8,9,10) — same conflict group
    coll.insert_one({
        "_id": "seq-002",
        "bid_period_id": bp_id,
        "seq_number": 664,
        "category": "777 INTL",
        "ops_count": 4,
        "position_min": 1, "position_max": 9,
        "language": None, "language_count": None,
        "operating_dates": [8, 9, 10, 11],
        "is_turn": False, "has_deadhead": False, "is_redeye": False,
        "totals": {"block_minutes": 900, "synth_minutes": 50, "tpay_minutes": 950,
                   "tafb_minutes": 2600, "duty_days": 3, "leg_count": 3, "deadhead_count": 0},
        "layover_cities": ["LHR"],
        "duty_periods": [
            {"report_base": "16:00", "release_base": "09:30",
             "legs": [{"equipment": "83"}]},
        ],
    })
    # Separate dates — domestic turn
    coll.insert_one({
        "_id": "seq-003",
        "bid_period_id": bp_id,
        "seq_number": 800,
        "category": "NBD DOM",
        "ops_count": 25,
        "position_min": 1, "position_max": 4,
        "language": None, "language_count": None,
        "operating_dates": [15, 16],
        "is_turn": True, "has_deadhead": False, "is_redeye": False,
        "totals": {"block_minutes": 400, "synth_minutes": 0, "tpay_minutes": 400,
                   "tafb_minutes": 600, "duty_days": 1, "leg_count": 2, "deadhead_count": 0},
        "layover_cities": [],
        "duty_periods": [
            {"report_base": "06:00", "release_base": "14:00",
             "legs": [{"equipment": "45"}]},
        ],
    })
    # Late-month sequence
    coll.insert_one({
        "_id": "seq-004",
        "bid_period_id": bp_id,
        "seq_number": 900,
        "category": "777 INTL",
        "ops_count": 3,
        "position_min": 1, "position_max": 9,
        "language": None, "language_count": None,
        "operating_dates": [22, 23, 24, 25],
        "is_turn": False, "has_deadhead": False, "is_redeye": True,
        "totals": {"block_minutes": 1100, "synth_minutes": 120, "tpay_minutes": 1220,
                   "tafb_minutes": 3000, "duty_days": 4, "leg_count": 5, "deadhead_count": 1},
        "layover_cities": ["HNL"],
        "duty_periods": [
            {"report_base": "22:00", "release_base": "10:00",
             "legs": [{"equipment": "97"}]},
        ],
    })


@pytest.fixture(autouse=True)
def _clean_db():
    reset_mock_db()
    with patch("app.routes.auth.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.users.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bid_periods.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.sequences.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bids.get_collection", side_effect=get_mock_collection):
        yield
    reset_mock_db()


async def _setup(client):
    """Register, seed data, create empty bid. Returns (headers, bp_id, bid_id)."""
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    # Create empty draft bid
    resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={"name": "Test Bid", "entries": []},
        headers=headers,
    )
    assert resp.status_code == 201
    bid_id = resp.json()["id"]

    return headers, bp_id, bid_id, user_id


@pytest.mark.anyio
async def test_optimize_basic(client):
    headers, bp_id, bid_id, _ = await _setup(client)

    resp = await client.post(f"/bid-periods/{bp_id}/bids/{bid_id}/optimize", headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "optimized"
    assert len(data["entries"]) == 4  # all 4 sequences ranked
    assert data["optimization_run_at"] is not None
    assert data["optimization_config"] is not None

    # All entries have required optimizer fields
    for entry in data["entries"]:
        assert entry["rationale"] is not None
        assert entry["preference_score"] >= 0.0
        assert entry["attainability"] in ("high", "medium", "low", "unknown")
        assert entry["date_conflict_group"] is not None


@pytest.mark.anyio
async def test_optimize_ranks_sequential(client):
    headers, bp_id, bid_id, _ = await _setup(client)

    resp = await client.post(f"/bid-periods/{bp_id}/bids/{bid_id}/optimize", headers=headers)
    data = resp.json()

    ranks = [e["rank"] for e in data["entries"]]
    assert ranks == [1, 2, 3, 4]


@pytest.mark.anyio
async def test_optimize_conflict_groups(client):
    headers, bp_id, bid_id, _ = await _setup(client)

    resp = await client.post(f"/bid-periods/{bp_id}/bids/{bid_id}/optimize", headers=headers)
    data = resp.json()

    groups = {e["seq_number"]: e["date_conflict_group"] for e in data["entries"]}
    # seq 663 and 664 overlap on dates 8,9 — same conflict group
    assert groups[663] == groups[664]
    # seq 800 is on different dates — different group
    assert groups[800] != groups[663]


@pytest.mark.anyio
async def test_optimize_summary_recomputed(client):
    headers, bp_id, bid_id, _ = await _setup(client)

    resp = await client.post(f"/bid-periods/{bp_id}/bids/{bid_id}/optimize", headers=headers)
    data = resp.json()

    summary = data["summary"]
    assert summary["total_entries"] == 4
    assert summary["total_tpay_minutes"] > 0
    assert summary["total_block_minutes"] > 0
    assert len(summary["date_coverage"]["covered_dates"]) > 0


@pytest.mark.anyio
async def test_optimize_preserves_pinned(client):
    headers, bp_id, bid_id, _ = await _setup(client)

    # First add entries with seq-003 pinned at rank 1
    resp = await client.put(
        f"/bid-periods/{bp_id}/bids/{bid_id}",
        json={
            "entries": [
                {"sequence_id": "seq-003", "rank": 1, "is_pinned": True},
                {"sequence_id": "seq-001", "rank": 2},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # Run optimize
    resp = await client.post(f"/bid-periods/{bp_id}/bids/{bid_id}/optimize", headers=headers)
    data = resp.json()

    # seq-003 should still be at rank 1
    first = data["entries"][0]
    assert first["sequence_id"] == "seq-003"
    assert first["is_pinned"] is True


@pytest.mark.anyio
async def test_optimize_excludes_entries(client):
    headers, bp_id, bid_id, _ = await _setup(client)

    # Mark seq-004 as excluded
    resp = await client.put(
        f"/bid-periods/{bp_id}/bids/{bid_id}",
        json={
            "entries": [
                {"sequence_id": "seq-001", "rank": 1},
                {"sequence_id": "seq-004", "rank": 2, "is_excluded": True},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.post(f"/bid-periods/{bp_id}/bids/{bid_id}/optimize", headers=headers)
    data = resp.json()

    excluded = [e for e in data["entries"] if e["is_excluded"]]
    assert len(excluded) == 1
    assert excluded[0]["sequence_id"] == "seq-004"
    # Excluded should be last
    assert excluded[0]["rank"] == len(data["entries"])


@pytest.mark.anyio
async def test_optimize_config_snapshot(client):
    headers, bp_id, bid_id, _ = await _setup(client)

    resp = await client.post(f"/bid-periods/{bp_id}/bids/{bid_id}/optimize", headers=headers)
    data = resp.json()

    config = data["optimization_config"]
    assert config["seniority_number"] == 500
    assert config["total_base_fas"] == 3000


@pytest.mark.anyio
async def test_optimize_fails_when_not_parsed(client):
    """Optimize should return 409 if bid period is still parsing."""
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    bp_id = _seed_bid_period(user_id, parse_status="processing")

    resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={"name": "Bid", "entries": []},
        headers=headers,
    )
    bid_id = resp.json()["id"]

    resp = await client.post(f"/bid-periods/{bp_id}/bids/{bid_id}/optimize", headers=headers)
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_optimize_bid_not_found(client):
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    bp_id = _seed_bid_period(user_id)

    resp = await client.post(f"/bid-periods/{bp_id}/bids/nonexistent/optimize", headers=headers)
    assert resp.status_code == 404
