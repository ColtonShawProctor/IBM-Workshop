"""Tests for awarded schedule import, GET, and award analysis (Tasks 21-22)."""
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
        "language_qualifications": [],
    },
}


def _seed(user_id: str):
    """Seed bid period, sequences, and a bid with entries."""
    bp_coll = get_mock_collection("bid_periods")
    bp_coll.insert_one({
        "_id": "bp-001", "user_id": user_id, "name": "Jan 2026",
        "effective_start": "2026-01-01", "effective_end": "2026-01-30",
        "base_city": "ORD", "parse_status": "completed",
        "total_sequences": 3, "total_dates": 30, "categories": [],
    })

    seq_coll = get_mock_collection("sequences")
    seq_coll.insert_one({
        "_id": "seq-001", "bid_period_id": "bp-001", "user_id": user_id,
        "seq_number": 663, "category": "777 INTL", "ops_count": 5,
        "position_min": 1, "position_max": 9,
        "operating_dates": [6, 7, 8],
        "totals": {"tpay_minutes": 1117, "block_minutes": 900, "tafb_minutes": 4500,
                   "synth_minutes": 217, "duty_days": 3, "leg_count": 4, "deadhead_count": 0},
        "duty_periods": [],
    })
    seq_coll.insert_one({
        "_id": "seq-002", "bid_period_id": "bp-001", "user_id": user_id,
        "seq_number": 664, "category": "NBD DOM", "ops_count": 25,
        "position_min": 1, "position_max": 4,
        "operating_dates": [10, 11],
        "totals": {"tpay_minutes": 500, "block_minutes": 400, "tafb_minutes": 2000,
                   "synth_minutes": 100, "duty_days": 2, "leg_count": 3, "deadhead_count": 0},
        "duty_periods": [],
    })
    seq_coll.insert_one({
        "_id": "seq-003", "bid_period_id": "bp-001", "user_id": user_id,
        "seq_number": 700, "category": "787 INTL", "ops_count": 3,
        "position_min": 1, "position_max": 9,
        "operating_dates": [15, 16, 17, 18],
        "totals": {"tpay_minutes": 1500, "block_minutes": 1200, "tafb_minutes": 5800,
                   "synth_minutes": 300, "duty_days": 4, "leg_count": 5, "deadhead_count": 1},
        "duty_periods": [],
    })

    # Create a bid with entries
    bid_coll = get_mock_collection("bids")
    bid_coll.insert_one({
        "_id": "bid-001", "bid_period_id": "bp-001", "user_id": user_id,
        "name": "My Jan Bid", "status": "finalized",
        "entries": [
            {"rank": 1, "sequence_id": "seq-001", "seq_number": 663,
             "is_pinned": False, "is_excluded": False, "attainability": "high",
             "preference_score": 0.9},
            {"rank": 2, "sequence_id": "seq-002", "seq_number": 664,
             "is_pinned": False, "is_excluded": False, "attainability": "high",
             "preference_score": 0.7},
            {"rank": 3, "sequence_id": "seq-003", "seq_number": 700,
             "is_pinned": False, "is_excluded": False, "attainability": "low",
             "preference_score": 0.85},
        ],
        "summary": {},
        "updated_at": "2026-01-10T00:00:00Z",
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
         patch("app.routes.awarded_schedules.get_collection", side_effect=get_mock_collection):
        yield
    reset_mock_db()


async def _register(client):
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, user_id


# ── Task 21: Import & GET ──────────────────────────────────────────────────


@pytest.mark.anyio
async def test_import_awarded_schedule_csv(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    csv_content = "seq_number,operating_dates,tpay_minutes,block_minutes,tafb_minutes\n663,6;7;8,1117,900,4500\n664,10;11,500,400,2000\n"
    resp = await client.post(
        "/bid-periods/bp-001/awarded-schedule",
        files={"file": ("award.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        data={"bid_id": "bid-001"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["bid_period_id"] == "bp-001"
    assert data["bid_id"] == "bid-001"
    assert len(data["awarded_sequences"]) == 2
    assert data["awarded_sequences"][0]["seq_number"] == 663
    assert data["source_filename"] == "award.csv"


@pytest.mark.anyio
async def test_import_awarded_schedule_simple_text(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    text_content = "663\n664\n700\n"
    resp = await client.post(
        "/bid-periods/bp-001/awarded-schedule",
        files={"file": ("award.txt", io.BytesIO(text_content.encode()), "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["awarded_sequences"]) == 3
    # Should be enriched from sequence data
    assert data["awarded_sequences"][0]["sequence_id"] == "seq-001"
    assert data["awarded_sequences"][0]["tpay_minutes"] == 1117


@pytest.mark.anyio
async def test_import_awarded_schedule_empty_file(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.post(
        "/bid-periods/bp-001/awarded-schedule",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_import_awarded_schedule_bad_bid_period(client):
    headers, _ = await _register(client)

    text_content = "663\n"
    resp = await client.post(
        "/bid-periods/nonexistent/awarded-schedule",
        files={"file": ("award.txt", io.BytesIO(text_content.encode()), "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_import_awarded_schedule_bad_bid_id(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    text_content = "663\n"
    resp = await client.post(
        "/bid-periods/bp-001/awarded-schedule",
        files={"file": ("award.txt", io.BytesIO(text_content.encode()), "text/plain")},
        data={"bid_id": "nonexistent"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_get_awarded_schedule(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    # Import first
    text_content = "663\n664\n"
    await client.post(
        "/bid-periods/bp-001/awarded-schedule",
        files={"file": ("award.txt", io.BytesIO(text_content.encode()), "text/plain")},
        headers=headers,
    )

    # GET
    resp = await client.get("/bid-periods/bp-001/awarded-schedule", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["awarded_sequences"]) == 2


@pytest.mark.anyio
async def test_get_awarded_schedule_not_found(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.get("/bid-periods/bp-001/awarded-schedule", headers=headers)
    assert resp.status_code == 404


# ── Task 22: Award Analysis ───────────────────────────────────────────────


@pytest.mark.anyio
async def test_award_analysis(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    # Import awarded schedule: 663 and 664 awarded (seq 700 not awarded)
    csv_content = "seq_number,operating_dates,tpay_minutes,block_minutes,tafb_minutes\n663,6;7;8,1117,900,4500\n664,10;11,500,400,2000\n"
    await client.post(
        "/bid-periods/bp-001/awarded-schedule",
        files={"file": ("award.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        data={"bid_id": "bid-001"},
        headers=headers,
    )

    resp = await client.get(
        "/bid-periods/bp-001/award-analysis",
        params={"bid_id": "bid-001"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["bid_id"] == "bid-001"
    assert data["match_count"] == 2  # 663 and 664 were in bid and awarded
    assert data["top_10_match_count"] == 2  # both in top 10
    assert len(data["matched_entries"]) == 3  # all 3 bid entries
    assert data["unmatched_awards"] == []  # all awards were in bid

    # Attainability: 2 high (663, 664) — both awarded; 1 low (700) — not awarded
    assert data["attainability_accuracy"]["high_awarded"] == 2
    assert data["attainability_accuracy"]["high_total"] == 2
    assert data["attainability_accuracy"]["low_awarded"] == 0
    assert data["attainability_accuracy"]["low_total"] == 1

    assert len(data["insights"]) > 0


@pytest.mark.anyio
async def test_award_analysis_with_unmatched(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    # Award seq 663 and seq 999 (not in bid)
    csv_content = "seq_number\n663\n999\n"
    await client.post(
        "/bid-periods/bp-001/awarded-schedule",
        files={"file": ("award.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=headers,
    )

    resp = await client.get(
        "/bid-periods/bp-001/award-analysis",
        params={"bid_id": "bid-001"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["match_count"] == 1  # only 663
    assert 999 in data["unmatched_awards"]


@pytest.mark.anyio
async def test_award_analysis_defaults_to_finalized_bid(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    text_content = "663\n"
    await client.post(
        "/bid-periods/bp-001/awarded-schedule",
        files={"file": ("award.txt", io.BytesIO(text_content.encode()), "text/plain")},
        headers=headers,
    )

    # No bid_id param — should find the finalized bid
    resp = await client.get("/bid-periods/bp-001/award-analysis", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["bid_id"] == "bid-001"


@pytest.mark.anyio
async def test_award_analysis_no_awarded_schedule(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    resp = await client.get(
        "/bid-periods/bp-001/award-analysis",
        params={"bid_id": "bid-001"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_award_analysis_no_bid(client):
    headers, user_id = await _register(client)
    _seed(user_id)

    # Remove the bid
    bid_coll = get_mock_collection("bids")
    bid_coll.delete_many({"user_id": user_id})

    text_content = "663\n"
    await client.post(
        "/bid-periods/bp-001/awarded-schedule",
        files={"file": ("award.txt", io.BytesIO(text_content.encode()), "text/plain")},
        headers=headers,
    )

    resp = await client.get("/bid-periods/bp-001/award-analysis", headers=headers)
    assert resp.status_code == 404
