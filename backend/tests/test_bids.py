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
        "language_qualifications": ["JP"],
    },
}


def _seed_bid_period(user_id: str) -> str:
    bp_id = "bp-001"
    coll = get_mock_collection("bid_periods")
    coll.insert_one({
        "_id": bp_id,
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
    return bp_id


def _seed_sequences(bp_id: str):
    coll = get_mock_collection("sequences")
    coll.insert_one({
        "_id": "seq-001",
        "bid_period_id": bp_id,
        "seq_number": 663,
        "category": "777 INTL",
        "ops_count": 5,
        "position_min": 1,
        "position_max": 9,
        "language": None,
        "operating_dates": [6, 7, 8],
        "is_turn": False,
        "has_deadhead": False,
        "is_redeye": False,
        "totals": {
            "block_minutes": 1000,
            "synth_minutes": 0,
            "tpay_minutes": 1000,
            "tafb_minutes": 2800,
            "duty_days": 3,
            "leg_count": 4,
            "deadhead_count": 0,
        },
        "layover_cities": ["LHR"],
        "duty_periods": [],
    })
    coll.insert_one({
        "_id": "seq-002",
        "bid_period_id": bp_id,
        "seq_number": 664,
        "category": "NBD DOM",
        "ops_count": 25,
        "position_min": 1,
        "position_max": 4,
        "language": None,
        "operating_dates": [10, 11],
        "is_turn": True,
        "has_deadhead": False,
        "is_redeye": False,
        "totals": {
            "block_minutes": 400,
            "synth_minutes": 0,
            "tpay_minutes": 400,
            "tafb_minutes": 600,
            "duty_days": 1,
            "leg_count": 2,
            "deadhead_count": 0,
        },
        "layover_cities": [],
        "duty_periods": [],
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


async def _register(client):
    """Register user and return (token, user_id, headers)."""
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return token, user_id, headers


@pytest.mark.anyio
async def test_create_bid(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={
            "name": "My January Bid",
            "entries": [
                {"sequence_id": "seq-001", "rank": 1},
                {"sequence_id": "seq-002", "rank": 2},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My January Bid"
    assert data["status"] == "draft"
    assert len(data["entries"]) == 2
    assert data["entries"][0]["seq_number"] == 663
    assert data["entries"][1]["seq_number"] == 664

    summary = data["summary"]
    assert summary["total_entries"] == 2
    assert summary["total_tpay_minutes"] == 1400
    assert summary["total_block_minutes"] == 1400
    assert summary["international_count"] == 1
    assert summary["domestic_count"] == 1
    assert "LHR" in summary["layover_cities"]


@pytest.mark.anyio
async def test_list_bids(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)

    await client.post(f"/bid-periods/{bp_id}/bids", json={"name": "Bid 1", "entries": []}, headers=headers)
    await client.post(f"/bid-periods/{bp_id}/bids", json={"name": "Bid 2", "entries": []}, headers=headers)

    resp = await client.get(f"/bid-periods/{bp_id}/bids", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


@pytest.mark.anyio
async def test_get_bid(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    create_resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={"name": "Test Bid", "entries": [{"sequence_id": "seq-001", "rank": 1}]},
        headers=headers,
    )
    bid_id = create_resp.json()["id"]

    resp = await client.get(f"/bid-periods/{bp_id}/bids/{bid_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Bid"
    assert len(resp.json()["entries"]) == 1


@pytest.mark.anyio
async def test_update_bid_entries(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    create_resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={"name": "My Bid", "entries": [{"sequence_id": "seq-001", "rank": 1}]},
        headers=headers,
    )
    bid_id = create_resp.json()["id"]

    resp = await client.put(
        f"/bid-periods/{bp_id}/bids/{bid_id}",
        json={
            "name": "Updated Bid",
            "entries": [
                {"sequence_id": "seq-002", "rank": 1, "is_pinned": True},
                {"sequence_id": "seq-001", "rank": 2},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Bid"
    assert data["entries"][0]["seq_number"] == 664
    assert data["entries"][0]["is_pinned"] is True
    assert data["entries"][1]["seq_number"] == 663
    assert data["summary"]["total_entries"] == 2


@pytest.mark.anyio
async def test_update_bid_status(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)

    create_resp = await client.post(
        f"/bid-periods/{bp_id}/bids", json={"name": "Bid", "entries": []}, headers=headers,
    )
    bid_id = create_resp.json()["id"]

    resp = await client.put(
        f"/bid-periods/{bp_id}/bids/{bid_id}",
        json={"status": "finalized"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "finalized"

    resp = await client.put(
        f"/bid-periods/{bp_id}/bids/{bid_id}",
        json={"status": "invalid"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_delete_bid(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)

    create_resp = await client.post(
        f"/bid-periods/{bp_id}/bids", json={"name": "To Delete", "entries": []}, headers=headers,
    )
    bid_id = create_resp.json()["id"]

    resp = await client.delete(f"/bid-periods/{bp_id}/bids/{bid_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/bid-periods/{bp_id}/bids/{bid_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_bid_summary(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    create_resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={
            "name": "Summary Bid",
            "entries": [
                {"sequence_id": "seq-001", "rank": 1},
                {"sequence_id": "seq-002", "rank": 2},
            ],
        },
        headers=headers,
    )
    bid_id = create_resp.json()["id"]

    resp = await client.get(f"/bid-periods/{bp_id}/bids/{bid_id}/summary", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total_entries"] == 2
    assert summary["total_tpay_minutes"] == 1400
    assert summary["date_coverage"]["coverage_rate"] > 0
    assert len(summary["date_coverage"]["covered_dates"]) == 5
    assert len(summary["date_coverage"]["uncovered_dates"]) == 25


@pytest.mark.anyio
async def test_create_bid_invalid_sequence(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)

    resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={"name": "Bad Bid", "entries": [{"sequence_id": "nonexistent", "rank": 1}]},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_bid_not_found(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)

    resp = await client.get(f"/bid-periods/{bp_id}/bids/nonexistent", headers=headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_excluded_entries_not_in_summary(client):
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    create_resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={
            "name": "Exclusion Test",
            "entries": [
                {"sequence_id": "seq-001", "rank": 1},
                {"sequence_id": "seq-002", "rank": 2, "is_excluded": True},
            ],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    summary = create_resp.json()["summary"]
    assert summary["total_entries"] == 1
    assert summary["total_tpay_minutes"] == 1000


# ── Task 72: CBA validation endpoint ─────────────────────────────────────────


@pytest.mark.anyio
async def test_validate_bid_returns_result(client):
    """POST validate returns CBA validation result."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    create_resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={
            "name": "Validate Test",
            "entries": [
                {"sequence_id": "seq-001", "rank": 1},
                {"sequence_id": "seq-002", "rank": 2},
            ],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    bid_id = create_resp.json()["id"]

    resp = await client.post(
        f"/bid-periods/{bp_id}/bids/{bid_id}/validate",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "is_valid" in data
    assert "violations" in data
    assert "credit_hour_summary" in data
    assert "days_off_summary" in data
    assert data["credit_hour_summary"]["line_min"] == 70
    assert data["days_off_summary"]["minimum_required"] == 11


@pytest.mark.anyio
async def test_validate_bid_not_found(client):
    """POST validate on nonexistent bid returns 404."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)

    resp = await client.post(
        f"/bid-periods/{bp_id}/bids/nonexistent/validate",
        headers=headers,
    )
    assert resp.status_code == 404


# ── Task 93: PBS Property CRUD + Layer Summaries ─────────────────────────────


async def _create_bid_with_seqs(client, bp_id, headers):
    """Helper: create a bid with 2 sequences."""
    resp = await client.post(
        f"/bid-periods/{bp_id}/bids",
        json={
            "name": "Props Test",
            "entries": [
                {"sequence_id": "seq-001", "rank": 1},
                {"sequence_id": "seq-002", "rank": 2},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.anyio
async def test_add_property(client):
    """POST property → 201, property appears in bid."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)
    bid_id = await _create_bid_with_seqs(client, bp_id, headers)

    resp = await client.post(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties",
        json={
            "property_key": "report_between",
            "value": {"start": 300, "end": 480},
            "layers": [1, 2],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["property_key"] == "report_between"
    assert data["category"] == "pairing"
    assert data["layers"] == [1, 2]
    assert "id" in data


@pytest.mark.anyio
async def test_list_properties(client):
    """GET properties → returns list."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)
    bid_id = await _create_bid_with_seqs(client, bp_id, headers)

    # Add two properties
    await client.post(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties",
        json={"property_key": "report_between", "value": {"start": 300, "end": 480}, "layers": [1]},
        headers=headers,
    )
    await client.post(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties",
        json={"property_key": "prefer_pairing_type", "value": "ipd", "layers": [1, 2]},
        headers=headers,
    )

    resp = await client.get(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.anyio
async def test_update_property(client):
    """PUT property → updates value and layers."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)
    bid_id = await _create_bid_with_seqs(client, bp_id, headers)

    add_resp = await client.post(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties",
        json={"property_key": "report_between", "value": {"start": 300, "end": 480}, "layers": [1]},
        headers=headers,
    )
    prop_id = add_resp.json()["id"]

    resp = await client.put(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties/{prop_id}",
        json={"property_key": "report_between", "value": {"start": 360, "end": 540}, "layers": [1, 2, 3]},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["value"] == {"start": 360, "end": 540}
    assert data["layers"] == [1, 2, 3]


@pytest.mark.anyio
async def test_delete_property(client):
    """DELETE property → removed from list."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)
    bid_id = await _create_bid_with_seqs(client, bp_id, headers)

    add_resp = await client.post(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties",
        json={"property_key": "prefer_aircraft", "value": "777", "layers": [1]},
        headers=headers,
    )
    prop_id = add_resp.json()["id"]

    del_resp = await client.delete(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties/{prop_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties",
        headers=headers,
    )
    assert len(list_resp.json()) == 0


@pytest.mark.anyio
async def test_get_layer_summaries(client):
    """GET layers → returns 7 LayerSummary objects."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)
    bid_id = await _create_bid_with_seqs(client, bp_id, headers)

    resp = await client.get(
        f"/bid-periods/{bp_id}/bids/{bid_id}/layers",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7
    assert data[0]["layer_number"] == 1
    assert data[6]["layer_number"] == 7
    assert data[0]["total_pairings"] == 2  # 2 sequences seeded


@pytest.mark.anyio
async def test_add_property_invalid_key(client):
    """POST property with invalid key → 400."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)
    bid_id = await _create_bid_with_seqs(client, bp_id, headers)

    resp = await client.post(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties",
        json={"property_key": "nonexistent_property", "value": True, "layers": [1]},
        headers=headers,
    )
    assert resp.status_code == 400 or resp.status_code == 422


@pytest.mark.anyio
async def test_add_property_invalid_layer(client):
    """POST property with layer=8 → 400/422."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)
    bid_id = await _create_bid_with_seqs(client, bp_id, headers)

    resp = await client.post(
        f"/bid-periods/{bp_id}/bids/{bid_id}/properties",
        json={"property_key": "prefer_aircraft", "value": "777", "layers": [8]},
        headers=headers,
    )
    assert resp.status_code == 400 or resp.status_code == 422


# ── Task 104: Export 7-layer and 9-layer bids ────────────────────────────────


@pytest.mark.anyio
async def test_export_7_layer_bid(client):
    """Export a bid with max layer <=7 → uses 'Layer N' labels."""
    _, user_id, headers = await _register(client)
    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)
    bid_id = await _create_bid_with_seqs(client, bp_id, headers)

    # Manually set entries with layer 1 (simulating PBS 7-layer output)
    bids_coll = get_mock_collection("bids")
    bids_coll.update_one({"_id": bid_id}, {"$set": {
        "entries": [
            {"rank": 1, "sequence_id": "seq-001", "seq_number": 663, "layer": 1, "is_excluded": False,
             "preference_score": 0.9, "attainability": "high", "rationale": "Test"},
            {"rank": 2, "sequence_id": "seq-002", "seq_number": 664, "layer": 2, "is_excluded": False,
             "preference_score": 0.7, "attainability": "medium", "rationale": "Test"},
        ],
    }})

    resp = await client.post(
        f"/bid-periods/{bp_id}/bids/{bid_id}/export",
        json={"format": "txt"},
        headers=headers,
    )
    assert resp.status_code == 200
    text = resp.text
    assert "Layer 1" in text or "LAYER 1" in text
    assert "663" in text


# ── Commute annotations in bid results ───────────────────────────────────


@pytest.mark.anyio
async def test_bid_entry_with_commute_impact(client):
    """Bid entries with commute_impact data are returned correctly."""
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = resp.json()["user"]["id"]

    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    # Create a bid with commute_impact in entries
    bids_coll = get_mock_collection("bids")
    bid_id = "bid-commute"
    bids_coll.insert_one({
        "_id": bid_id,
        "bid_period_id": bp_id,
        "user_id": user_id,
        "name": "Commute Test",
        "status": "optimized",
        "entries": [
            {
                "rank": 1, "sequence_id": "seq-001", "seq_number": 663,
                "is_pinned": False, "is_excluded": False,
                "preference_score": 0.9, "attainability": "high",
                "layer": 1,
                "commute_impact": {
                    "first_day_feasible": True,
                    "first_day_note": "Report 14:26 — easy commute",
                    "last_day_feasible": True,
                    "last_day_note": "Release 12:07 — easy commute home",
                    "hotel_nights_needed": 0,
                    "impact_level": "green",
                },
            },
        ],
        "summary": {
            "total_entries": 1, "total_tpay_minutes": 1000,
            "commute_warnings": ["SEQ 663: Back-to-back: no time to commute home"],
        },
    })

    resp = await client.get(f"/bid-periods/{bp_id}/bids/{bid_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Verify commute_impact on entry
    entry = data["entries"][0]
    assert entry["commute_impact"] is not None
    assert entry["commute_impact"]["impact_level"] == "green"
    assert entry["commute_impact"]["hotel_nights_needed"] == 0

    # Verify commute_warnings in summary
    assert len(data["summary"]["commute_warnings"]) == 1
    assert "Back-to-back" in data["summary"]["commute_warnings"][0]


@pytest.mark.anyio
async def test_bid_entry_without_commute_impact(client):
    """Bid entries without commute_impact return None."""
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = resp.json()["user"]["id"]

    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    bids_coll = get_mock_collection("bids")
    bid_id = "bid-no-commute"
    bids_coll.insert_one({
        "_id": bid_id,
        "bid_period_id": bp_id,
        "user_id": user_id,
        "name": "No Commute Test",
        "status": "draft",
        "entries": [
            {"rank": 1, "sequence_id": "seq-001", "seq_number": 663,
             "is_pinned": False, "is_excluded": False,
             "preference_score": 0.9, "attainability": "high", "layer": 1},
        ],
        "summary": {"total_entries": 1, "total_tpay_minutes": 1000},
    })

    resp = await client.get(f"/bid-periods/{bp_id}/bids/{bid_id}", headers=headers)
    assert resp.status_code == 200
    entry = resp.json()["entries"][0]
    assert entry["commute_impact"] is None
    assert resp.json()["summary"]["commute_warnings"] == []


# ── Projected schedule tests ─────────────────────────────────────────────


@pytest.mark.anyio
async def test_projected_schedule_endpoint(client):
    """GET .../bids/{bidId}/projected returns 7 layers."""
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = resp.json()["user"]["id"]

    bp_id = _seed_bid_period(user_id)
    _seed_sequences(bp_id)

    bids_coll = get_mock_collection("bids")
    bid_id = "bid-proj"
    bids_coll.insert_one({
        "_id": bid_id,
        "bid_period_id": bp_id,
        "user_id": user_id,
        "name": "Projected Test",
        "status": "optimized",
        "entries": [
            {"rank": 1, "sequence_id": "seq-001", "seq_number": 663,
             "layer": 1, "is_excluded": False},
            {"rank": 2, "sequence_id": "seq-002", "seq_number": 664,
             "layer": 1, "is_excluded": False},
            {"rank": 3, "sequence_id": "seq-001", "seq_number": 663,
             "layer": 2, "is_excluded": False},
        ],
        "summary": {},
    })

    resp = await client.get(
        f"/bid-periods/{bp_id}/bids/{bid_id}/projected",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "layers" in data
    assert len(data["layers"]) == 7

    # Layer 1 should have sequences
    l1 = data["layers"][0]
    assert l1["layer_number"] == 1
    assert isinstance(l1["total_credit_hours"], (int, float))
    assert isinstance(l1["total_days_off"], int)
    assert isinstance(l1["working_dates"], list)
    assert isinstance(l1["off_dates"], list)
    assert isinstance(l1["schedule_shape"], str)
    assert isinstance(l1["within_credit_range"], bool)

    # working_dates + off_dates should cover all period dates
    all_dates = set(l1["working_dates"]) | set(l1["off_dates"])
    assert all_dates == set(range(1, 31))


@pytest.mark.anyio
async def test_projected_schedule_not_found(client):
    """GET projected on nonexistent bid returns 404."""
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = resp.json()["user"]["id"]
    bp_id = _seed_bid_period(user_id)

    resp = await client.get(
        f"/bid-periods/{bp_id}/bids/nonexistent/projected",
        headers=headers,
    )
    assert resp.status_code == 404
