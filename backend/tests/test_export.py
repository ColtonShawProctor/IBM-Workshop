"""Tests for POST /bid-periods/{id}/bids/{id}/export endpoint."""
from __future__ import annotations

import csv
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
        "position_max": 9,
        "language_qualifications": ["JP"],
    },
}


def _seed(user_id: str):
    bp_coll = get_mock_collection("bid_periods")
    bp_coll.insert_one({
        "_id": "bp-001",
        "user_id": user_id,
        "name": "January 2026",
        "effective_start": "2026-01-01",
        "effective_end": "2026-01-30",
        "base_city": "ORD",
        "parse_status": "completed",
        "total_sequences": 2,
        "total_dates": 30,
        "categories": ["777 INTL"],
    })

    seq_coll = get_mock_collection("sequences")
    seq_coll.insert_one({
        "_id": "seq-001", "bid_period_id": "bp-001", "seq_number": 663,
        "category": "777 INTL", "ops_count": 5,
        "position_min": 1, "position_max": 9,
        "language": None, "operating_dates": [6, 7, 8],
        "is_turn": False, "has_deadhead": False, "is_redeye": False,
        "totals": {"block_minutes": 1000, "synth_minutes": 0, "tpay_minutes": 1000,
                   "tafb_minutes": 2800, "duty_days": 3, "leg_count": 4, "deadhead_count": 0},
        "layover_cities": ["LHR"], "duty_periods": [],
    })
    seq_coll.insert_one({
        "_id": "seq-002", "bid_period_id": "bp-001", "seq_number": 664,
        "category": "NBD DOM", "ops_count": 25,
        "position_min": 1, "position_max": 4,
        "language": None, "operating_dates": [10, 11],
        "is_turn": True, "has_deadhead": False, "is_redeye": False,
        "totals": {"block_minutes": 400, "synth_minutes": 0, "tpay_minutes": 400,
                   "tafb_minutes": 600, "duty_days": 1, "leg_count": 2, "deadhead_count": 0},
        "layover_cities": [], "duty_periods": [],
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
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    _seed(user_id)

    resp = await client.post(
        "/bid-periods/bp-001/bids",
        json={
            "name": "My Bid",
            "entries": [
                {"sequence_id": "seq-001", "rank": 1},
                {"sequence_id": "seq-002", "rank": 2},
            ],
        },
        headers=headers,
    )
    bid_id = resp.json()["id"]
    return headers, bid_id


@pytest.mark.anyio
async def test_export_txt_default(client):
    headers, bid_id = await _setup(client)

    resp = await client.post(f"/bid-periods/bp-001/bids/{bid_id}/export", headers=headers)
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "bid-export.txt" in resp.headers["content-disposition"]

    text = resp.text
    assert "My Bid" in text
    assert "663" in text
    assert "664" in text
    assert "Total sequences: 2" in text


@pytest.mark.anyio
async def test_export_txt_explicit(client):
    headers, bid_id = await _setup(client)

    resp = await client.post(
        f"/bid-periods/bp-001/bids/{bid_id}/export",
        json={"format": "txt"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


@pytest.mark.anyio
async def test_export_csv(client):
    headers, bid_id = await _setup(client)

    resp = await client.post(
        f"/bid-periods/bp-001/bids/{bid_id}/export",
        json={"format": "csv"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "bid-export.csv" in resp.headers["content-disposition"]

    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    header = rows[0]
    assert "Rank" in header
    assert "SEQ Number" in header
    assert len(rows) == 3  # header + 2 entries


@pytest.mark.anyio
async def test_export_excludes_excluded_entries(client):
    headers, bid_id = await _setup(client)

    # Exclude seq-002
    await client.put(
        f"/bid-periods/bp-001/bids/{bid_id}",
        json={
            "entries": [
                {"sequence_id": "seq-001", "rank": 1},
                {"sequence_id": "seq-002", "rank": 2, "is_excluded": True},
            ],
        },
        headers=headers,
    )

    resp = await client.post(
        f"/bid-periods/bp-001/bids/{bid_id}/export",
        json={"format": "csv"},
        headers=headers,
    )
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 2  # header + 1 active entry


@pytest.mark.anyio
async def test_export_invalid_format(client):
    headers, bid_id = await _setup(client)

    resp = await client.post(
        f"/bid-periods/bp-001/bids/{bid_id}/export",
        json={"format": "pdf"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_export_bid_not_found(client):
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    _seed(user_id)

    resp = await client.post(
        "/bid-periods/bp-001/bids/nonexistent/export",
        headers=headers,
    )
    assert resp.status_code == 404
