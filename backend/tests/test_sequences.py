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
        "language_qualifications": ["JP"],
    },
}


def _make_seq(seq_id, bp_id, seq_number, **overrides):
    doc = {
        "_id": seq_id,
        "bid_period_id": bp_id,
        "seq_number": seq_number,
        "category": "777 INTL",
        "ops_count": 5,
        "position_min": 1,
        "position_max": 9,
        "language": None,
        "language_count": None,
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
        "duty_periods": [
            {
                "dp_number": 1,
                "day_of_seq": 1,
                "day_of_seq_total": 3,
                "report_local": "17:10",
                "report_base": "17:10",
                "release_local": "08:45",
                "release_base": "02:45",
                "legs": [
                    {
                        "leg_index": 1,
                        "flight_number": "86",
                        "is_deadhead": False,
                        "equipment": "97",
                        "departure_station": "ORD",
                        "departure_local": "18:25",
                        "departure_base": "18:25",
                        "arrival_station": "LHR",
                        "arrival_local": "08:15",
                        "arrival_base": "02:15",
                        "pax_service": "QDB",
                        "block_minutes": 470,
                    }
                ],
                "layover": {
                    "city": "LHR",
                    "hotel_name": "DOUBLETREE HILTON",
                    "hotel_phone": "44 20 7834 8123",
                    "rest_minutes": 1595,
                },
            },
            {
                "dp_number": 2,
                "day_of_seq": 3,
                "day_of_seq_total": 3,
                "report_local": "11:20",
                "report_base": "05:20",
                "release_local": "15:55",
                "release_base": "15:55",
                "legs": [
                    {
                        "leg_index": 1,
                        "flight_number": "87",
                        "is_deadhead": False,
                        "equipment": "97",
                        "departure_station": "LHR",
                        "departure_local": "12:35",
                        "departure_base": "06:35",
                        "arrival_station": "ORD",
                        "arrival_local": "15:25",
                        "arrival_base": "15:25",
                        "pax_service": "QLS",
                        "block_minutes": 530,
                    }
                ],
            },
        ],
        "source": "parsed",
    }
    doc.update(overrides)
    return doc


@pytest.fixture(autouse=True)
def _clean_db():
    reset_mock_db()
    with patch("app.routes.auth.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bid_periods.get_collection", side_effect=get_mock_collection), \
         patch("app.routes.bid_periods.run_parse"), \
         patch("app.routes.bid_periods.os.makedirs"), \
         patch("app.routes.sequences.get_collection", side_effect=get_mock_collection), \
         patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__ = lambda s: io.BytesIO()
        mock_open.return_value.__exit__ = lambda s, *a: None
        yield


async def _setup(client):
    """Register, create bid period, insert test sequences. Returns (token, bp_id)."""
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]

    resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "name": (None, "January 2026"),
            "effective_start": (None, "2026-01-01"),
            "effective_end": (None, "2026-01-31"),
            "file": ("bid.pdf", b"%PDF-fake", "application/pdf"),
        },
    )
    bp_id = resp.json()["id"]

    # Insert test sequences directly
    seq_coll = get_mock_collection("sequences")
    seq_coll.insert_one(_make_seq("s1", bp_id, 671, ops_count=20, layover_cities=["LHR"],
                                   totals={"block_minutes": 1000, "synth_minutes": 0,
                                           "tpay_minutes": 1000, "tafb_minutes": 2800,
                                           "duty_days": 3, "leg_count": 2, "deadhead_count": 0},
                                   operating_dates=[6, 7, 8]))
    seq_coll.insert_one(_make_seq("s2", bp_id, 672, ops_count=5, category="787 INTL",
                                   layover_cities=["NRT"],
                                   totals={"block_minutes": 1200, "synth_minutes": 100,
                                           "tpay_minutes": 1300, "tafb_minutes": 3500,
                                           "duty_days": 4, "leg_count": 4, "deadhead_count": 1},
                                   has_deadhead=True, language="JP", language_count=3,
                                   operating_dates=[10, 11, 12, 13]))
    seq_coll.insert_one(_make_seq("s3", bp_id, 5256, ops_count=17, category="NBI INTL",
                                   is_turn=True, layover_cities=[],
                                   totals={"block_minutes": 468, "synth_minutes": 0,
                                           "tpay_minutes": 468, "tafb_minutes": 622,
                                           "duty_days": 1, "leg_count": 2, "deadhead_count": 0},
                                   position_min=1, position_max=4,
                                   operating_dates=[8, 9, 10, 15, 16, 17]))
    seq_coll.insert_one(_make_seq("s4", bp_id, 5262, ops_count=3, category="NBI INTL",
                                   language="SP", language_count=1,
                                   is_turn=True, layover_cities=[],
                                   totals={"block_minutes": 589, "synth_minutes": 0,
                                           "tpay_minutes": 589, "tafb_minutes": 744,
                                           "duty_days": 1, "leg_count": 2, "deadhead_count": 0},
                                   position_min=1, position_max=4,
                                   operating_dates=[1, 3, 5]))
    seq_coll.insert_one(_make_seq("s5", bp_id, 663, ops_count=4, category="777 INTL",
                                   has_deadhead=True, is_redeye=True,
                                   language="JP", language_count=3,
                                   layover_cities=["LAS", "NRT"],
                                   totals={"block_minutes": 1305, "synth_minutes": 471,
                                           "tpay_minutes": 1776, "tafb_minutes": 5768,
                                           "duty_days": 5, "leg_count": 4, "deadhead_count": 2},
                                   operating_dates=[6, 7, 8, 9, 10]))

    return token, bp_id


def _url(bp_id, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    return f"/bid-periods/{bp_id}/sequences" + (f"?{qs}" if qs else "")


@pytest.mark.anyio
async def test_list_all(client):
    token, bp_id = await _setup(client)
    resp = await client.get(_url(bp_id), headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 5
    assert len(body["data"]) == 5


@pytest.mark.anyio
async def test_sort_by_seq_number_asc(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, sort_by="seq_number", sort_order="asc"),
        headers={"Authorization": f"Bearer {token}"},
    )
    nums = [s["seq_number"] for s in resp.json()["data"]]
    assert nums == sorted(nums)


@pytest.mark.anyio
async def test_sort_by_tpay_desc(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, sort_by="tpay", sort_order="desc"),
        headers={"Authorization": f"Bearer {token}"},
    )
    tpays = [s["totals"]["tpay_minutes"] for s in resp.json()["data"]]
    assert tpays == sorted(tpays, reverse=True)


@pytest.mark.anyio
async def test_filter_category(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, category="787 INTL"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert body["total_count"] == 1
    assert body["data"][0]["seq_number"] == 672


@pytest.mark.anyio
async def test_filter_language(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, language="JP"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert body["total_count"] == 2
    nums = {s["seq_number"] for s in body["data"]}
    assert nums == {663, 672}


@pytest.mark.anyio
async def test_filter_is_turn(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, is_turn="true"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert body["total_count"] == 2
    for s in body["data"]:
        assert s["is_turn"] is True


@pytest.mark.anyio
async def test_filter_has_deadhead(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, has_deadhead="true"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert body["total_count"] == 2
    for s in body["data"]:
        assert s["has_deadhead"] is True


@pytest.mark.anyio
async def test_filter_tpay_range(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, tpay_min=1000, tpay_max=1400),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    for s in body["data"]:
        assert 1000 <= s["totals"]["tpay_minutes"] <= 1400


@pytest.mark.anyio
async def test_filter_operating_date(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, operating_date=10),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    for s in body["data"]:
        assert 10 in s["operating_dates"]


@pytest.mark.anyio
async def test_filter_layover_city(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, layover_city="NRT"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert body["total_count"] == 2  # s2 (672) and s5 (663)


@pytest.mark.anyio
async def test_pagination(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, limit=2, sort_by="seq_number"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["total_count"] == 5
    assert body["page_state"] is not None

    # Fetch next page
    resp2 = await client.get(
        _url(bp_id, limit=2, sort_by="seq_number", page_state=body["page_state"]),
        headers={"Authorization": f"Bearer {token}"},
    )
    body2 = resp2.json()
    assert len(body2["data"]) == 2
    # No overlap
    ids1 = {s["id"] for s in body["data"]}
    ids2 = {s["id"] for s in body2["data"]}
    assert ids1.isdisjoint(ids2)


@pytest.mark.anyio
async def test_eligible_only_excludes_sp_sequences(client):
    """User has JP but not SP, so SP-required sequences should be excluded."""
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, eligible_only="true"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    # s4 (SEQ 5262, LANG SP) should be excluded — user only has JP
    nums = {s["seq_number"] for s in body["data"]}
    assert 5262 not in nums
    assert body["total_count"] == 4


@pytest.mark.anyio
async def test_eligibility_tags_on_list(client):
    """List endpoint should tag each sequence with eligibility status."""
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, sort_by="seq_number"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    by_num = {s["seq_number"]: s["eligibility"] for s in body["data"]}
    # s1 (671): no language req, POSN 1-9, user has POSN 1-4 → eligible
    assert by_num[671] == "eligible"
    # s2 (672): LANG JP, user has JP → language_advantaged
    assert by_num[672] == "language_advantaged"
    # s3 (5256): no language, POSN 1-4 → eligible
    assert by_num[5256] == "eligible"
    # s4 (5262): LANG SP, user doesn't have SP → ineligible
    assert by_num[5262] == "ineligible"
    # s5 (663): LANG JP, user has JP → language_advantaged
    assert by_num[663] == "language_advantaged"


@pytest.mark.anyio
async def test_eligibility_tag_on_detail(client):
    """Detail endpoint should also include eligibility."""
    token, bp_id = await _setup(client)
    # JP language sequence
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences/s2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["eligibility"] == "language_advantaged"

    # SP language sequence — user doesn't have SP
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences/s4",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["eligibility"] == "ineligible"


@pytest.mark.anyio
async def test_eligibility_position_ineligible(client):
    """User with POSN 1-4 should be ineligible for sequences requiring POSN 5-9."""
    token, bp_id = await _setup(client)
    # Insert a sequence that requires POSN 5-9
    seq_coll = get_mock_collection("sequences")
    seq_coll.insert_one(_make_seq("s-posn", bp_id, 9999,
                                   position_min=5, position_max=9,
                                   operating_dates=[20]))
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences/s-posn",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["eligibility"] == "ineligible"


@pytest.mark.anyio
async def test_combined_filters(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        _url(bp_id, language="JP", has_deadhead="true", sort_by="tpay", sort_order="desc"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert body["total_count"] == 2
    tpays = [s["totals"]["tpay_minutes"] for s in body["data"]]
    assert tpays == sorted(tpays, reverse=True)


@pytest.mark.anyio
async def test_bid_period_not_found(client):
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    resp = await client.get(
        "/bid-periods/nonexistent/sequences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_unauthorized(client):
    resp = await client.get("/bid-periods/some-id/sequences")
    assert resp.status_code == 403


# ── Sequence Comparison (POST /compare) ──────────────────────────────────


@pytest.mark.anyio
async def test_compare_two_sequences(client):
    token, bp_id = await _setup(client)
    resp = await client.post(
        f"/bid-periods/{bp_id}/sequences/compare",
        headers={"Authorization": f"Bearer {token}"},
        json={"sequence_ids": ["s1", "s2"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sequences"]) == 2
    assert body["sequences"][0]["seq_number"] == 671
    assert body["sequences"][1]["seq_number"] == 672
    assert len(body["differences"]) > 0
    # Check that differences contain attribute names
    diff_attrs = {d["attribute"] for d in body["differences"]}
    assert "tpay_minutes" in diff_attrs
    assert "layover_cities" in diff_attrs


@pytest.mark.anyio
async def test_compare_highlights_differences(client):
    token, bp_id = await _setup(client)
    resp = await client.post(
        f"/bid-periods/{bp_id}/sequences/compare",
        headers={"Authorization": f"Bearer {token}"},
        json={"sequence_ids": ["s1", "s5"]},
    )
    body = resp.json()
    diff_attrs = {d["attribute"] for d in body["differences"]}
    # s1 has no deadhead, s5 has deadhead
    assert "has_deadhead" in diff_attrs
    # s1 is not redeye, s5 is
    assert "is_redeye" in diff_attrs


@pytest.mark.anyio
async def test_compare_sequence_not_found(client):
    token, bp_id = await _setup(client)
    resp = await client.post(
        f"/bid-periods/{bp_id}/sequences/compare",
        headers={"Authorization": f"Bearer {token}"},
        json={"sequence_ids": ["s1", "nonexistent"]},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_compare_too_few(client):
    token, bp_id = await _setup(client)
    resp = await client.post(
        f"/bid-periods/{bp_id}/sequences/compare",
        headers={"Authorization": f"Bearer {token}"},
        json={"sequence_ids": ["s1"]},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_compare_five_sequences(client):
    token, bp_id = await _setup(client)
    resp = await client.post(
        f"/bid-periods/{bp_id}/sequences/compare",
        headers={"Authorization": f"Bearer {token}"},
        json={"sequence_ids": ["s1", "s2", "s3", "s4", "s5"]},
    )
    assert resp.status_code == 200
    assert len(resp.json()["sequences"]) == 5


# ── Sequence Detail (GET) ────────────────────────────────────────────────


@pytest.mark.anyio
async def test_get_sequence_detail(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences/s1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["seq_number"] == 671
    assert body["id"] == "s1"
    assert len(body["duty_periods"]) == 2
    assert body["duty_periods"][0]["legs"][0]["flight_number"] == "86"
    assert body["layover_cities"] == ["LHR"]


@pytest.mark.anyio
async def test_get_sequence_not_found(client):
    token, bp_id = await _setup(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences/nonexistent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── Create Sequence (POST) ───────────────────────────────────────────────

SEQUENCE_INPUT = {
    "seq_number": 9999,
    "category": "NBD DOM",
    "ops_count": 10,
    "position_min": 1,
    "position_max": 4,
    "operating_dates": [5, 12, 19, 26],
    "duty_periods": [
        {
            "dp_number": 1,
            "report_local": "06:00",
            "report_base": "06:00",
            "release_local": "14:30",
            "release_base": "14:30",
            "legs": [
                {
                    "flight_number": "2222",
                    "is_deadhead": False,
                    "equipment": "45",
                    "departure_station": "ORD",
                    "departure_local": "07:00",
                    "departure_base": "07:00",
                    "arrival_station": "PHX",
                    "arrival_local": "09:04",
                    "arrival_base": "10:04",
                    "pax_service": "QBF",
                    "block_minutes": 244,
                    "ground_minutes": 103,
                    "is_connection": True,
                },
                {
                    "flight_number": "1414",
                    "is_deadhead": False,
                    "equipment": "45",
                    "departure_station": "PHX",
                    "departure_local": "10:47",
                    "departure_base": "11:47",
                    "arrival_station": "ORD",
                    "arrival_local": "14:10",
                    "arrival_base": "14:10",
                    "pax_service": "Q",
                    "block_minutes": 203,
                },
            ],
        },
    ],
}


@pytest.mark.anyio
async def test_create_sequence(client):
    token, bp_id = await _setup(client)
    resp = await client.post(
        f"/bid-periods/{bp_id}/sequences",
        headers={"Authorization": f"Bearer {token}"},
        json=SEQUENCE_INPUT,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["seq_number"] == 9999
    assert body["source"] == "manual"
    assert body["is_turn"] is True
    assert body["has_deadhead"] is False
    assert body["layover_cities"] == []
    assert body["totals"]["block_minutes"] == 447  # 244 + 203
    assert body["totals"]["duty_days"] == 1
    assert body["totals"]["leg_count"] == 2
    assert body["operating_dates"] == [5, 12, 19, 26]
    assert body["id"] is not None


@pytest.mark.anyio
async def test_create_sequence_with_deadhead(client):
    token, bp_id = await _setup(client)
    inp = dict(SEQUENCE_INPUT)
    inp["duty_periods"] = [
        {
            "dp_number": 1,
            "report_local": "13:50",
            "report_base": "13:50",
            "release_local": "19:13",
            "release_base": "19:13",
            "legs": [
                {
                    "flight_number": "1105D",
                    "is_deadhead": True,
                    "equipment": "45",
                    "departure_station": "ORD",
                    "departure_local": "14:50",
                    "departure_base": "14:50",
                    "arrival_station": "LAS",
                    "arrival_local": "16:58",
                    "arrival_base": "18:58",
                    "pax_service": "QLF",
                    "block_minutes": 248,
                },
            ],
            "layover": {
                "city": "LAS",
                "hotel_name": "SAHARA HOTEL",
                "hotel_phone": "702-761-7000",
                "transport_company": "SKYHOP GLOBAL",
                "transport_phone": "954-400-0412",
                "rest_minutes": 1047,
            },
        },
    ]
    inp["operating_dates"] = [6, 7]
    resp = await client.post(
        f"/bid-periods/{bp_id}/sequences",
        headers={"Authorization": f"Bearer {token}"},
        json=inp,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["has_deadhead"] is True
    assert body["is_turn"] is False  # has layover
    assert body["layover_cities"] == ["LAS"]
    assert body["totals"]["deadhead_count"] == 1
    assert body["totals"]["block_minutes"] == 0  # deadhead doesn't count


@pytest.mark.anyio
async def test_create_sequence_bid_period_not_found(client):
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = resp.json()["access_token"]
    resp = await client.post(
        "/bid-periods/nonexistent/sequences",
        headers={"Authorization": f"Bearer {token}"},
        json=SEQUENCE_INPUT,
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_create_shows_in_list(client):
    token, bp_id = await _setup(client)
    await client.post(
        f"/bid-periods/{bp_id}/sequences",
        headers={"Authorization": f"Bearer {token}"},
        json=SEQUENCE_INPUT,
    )
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["total_count"] == 6  # 5 from setup + 1 new


# ── Update Sequence (PUT) ────────────────────────────────────────────────


@pytest.mark.anyio
async def test_update_sequence(client):
    token, bp_id = await _setup(client)
    # Create one first
    create_resp = await client.post(
        f"/bid-periods/{bp_id}/sequences",
        headers={"Authorization": f"Bearer {token}"},
        json=SEQUENCE_INPUT,
    )
    seq_id = create_resp.json()["id"]

    # Update it
    updated_input = dict(SEQUENCE_INPUT)
    updated_input["seq_number"] = 8888
    updated_input["ops_count"] = 20
    resp = await client.put(
        f"/bid-periods/{bp_id}/sequences/{seq_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=updated_input,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["seq_number"] == 8888
    assert body["ops_count"] == 20


@pytest.mark.anyio
async def test_update_sequence_not_found(client):
    token, bp_id = await _setup(client)
    resp = await client.put(
        f"/bid-periods/{bp_id}/sequences/nonexistent",
        headers={"Authorization": f"Bearer {token}"},
        json=SEQUENCE_INPUT,
    )
    assert resp.status_code == 404


# ── Delete Sequence (DELETE) ─────────────────────────────────────────────


@pytest.mark.anyio
async def test_delete_sequence(client):
    token, bp_id = await _setup(client)
    create_resp = await client.post(
        f"/bid-periods/{bp_id}/sequences",
        headers={"Authorization": f"Bearer {token}"},
        json=SEQUENCE_INPUT,
    )
    seq_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/bid-periods/{bp_id}/sequences/{seq_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Verify it's gone
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences/{seq_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_sequence_not_found(client):
    token, bp_id = await _setup(client)
    resp = await client.delete(
        f"/bid-periods/{bp_id}/sequences/nonexistent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── Commute impact & search tests ───────────────────────────────────────────

COMMUTER_REGISTER_PAYLOAD = {
    "email": "commuter@airline.com",
    "password": "securepass",
    "profile": {
        "display_name": "Jordan",
        "base_city": "ORD",
        "commute_from": "DCA",
        "seniority_number": 1000,
        "total_base_fas": 3000,
        "position_min": 1,
        "position_max": 9,
        "language_qualifications": ["JP"],
    },
}


async def _setup_commuter(client):
    """Register a commuter user, create bid period, insert test sequences."""
    resp = await client.post("/auth/register", json=COMMUTER_REGISTER_PAYLOAD)
    token = resp.json()["access_token"]

    resp = await client.post(
        "/bid-periods",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "name": (None, "January 2026"),
            "effective_start": (None, "2026-01-01"),
            "effective_end": (None, "2026-01-31"),
            "file": ("bid.pdf", b"%PDF-fake", "application/pdf"),
        },
    )
    bp_id = resp.json()["id"]

    seq_coll = get_mock_collection("sequences")
    # Sequence with late report (commuter-friendly)
    seq_coll.insert_one(_make_seq("cs1", bp_id, 664, ops_count=4,
                                   duty_periods=[
                                       {"dp_number": 1, "day_of_seq": 1, "day_of_seq_total": 3,
                                        "report_local": "14:26", "report_base": "14:26",
                                        "release_local": "22:00", "release_base": "22:00",
                                        "legs": [], "layover": None},
                                       {"dp_number": 2, "day_of_seq": 3, "day_of_seq_total": 3,
                                        "report_local": "08:00", "report_base": "08:00",
                                        "release_local": "12:07", "release_base": "12:07",
                                        "legs": [], "layover": None},
                                   ]))
    # Sequence with early report (hotel night needed)
    seq_coll.insert_one(_make_seq("cs2", bp_id, 665, ops_count=4,
                                   duty_periods=[
                                       {"dp_number": 1, "day_of_seq": 1, "day_of_seq_total": 1,
                                        "report_local": "05:30", "report_base": "05:30",
                                        "release_local": "14:00", "release_base": "14:00",
                                        "legs": [], "layover": None},
                                   ]))
    return token, bp_id


@pytest.mark.anyio
async def test_commute_impact_on_list_with_commute_from(client):
    """User with commute_from=DCA → sequences include commute_impact."""
    token, bp_id = await _setup_commuter(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    for seq in data:
        assert seq["commute_impact"] is not None
        assert seq["commute_impact"]["impact_level"] in ("green", "yellow", "red")


@pytest.mark.anyio
async def test_commute_impact_green_for_late_report(client):
    """SEQ 664 with report 14:26 → green impact for DCA commuter."""
    token, bp_id = await _setup_commuter(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences?sort_by=seq_number&sort_order=asc",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()["data"]
    seq_664 = next(s for s in data if s["seq_number"] == 664)
    assert seq_664["commute_impact"]["first_day_feasible"] is True
    assert seq_664["commute_impact"]["last_day_feasible"] is True
    assert seq_664["commute_impact"]["impact_level"] == "green"


@pytest.mark.anyio
async def test_commute_impact_red_for_early_report(client):
    """SEQ 665 with report 05:30 → red impact for DCA commuter."""
    token, bp_id = await _setup_commuter(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences?sort_by=seq_number&sort_order=asc",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()["data"]
    seq_665 = next(s for s in data if s["seq_number"] == 665)
    assert seq_665["commute_impact"]["first_day_feasible"] is False
    assert seq_665["commute_impact"]["hotel_nights_needed"] >= 1
    assert seq_665["commute_impact"]["impact_level"] == "red"


@pytest.mark.anyio
async def test_no_commute_impact_without_commute_from(client):
    """User without commute_from → commute_impact is None."""
    token, bp_id = await _setup(client)  # uses REGISTER_PAYLOAD without commute_from
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()["data"]
    for seq in data:
        assert seq["commute_impact"] is None


@pytest.mark.anyio
async def test_commutable_only_filter(client):
    """commutable_only=true → only green/yellow sequences returned."""
    token, bp_id = await _setup_commuter(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences?commutable_only=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()["data"]
    # SEQ 665 (early report, red) should be excluded
    for seq in data:
        assert seq["commute_impact"]["impact_level"] in ("green", "yellow")


@pytest.mark.anyio
async def test_commute_impact_on_detail(client):
    """GET single sequence includes commute_impact for commuter."""
    token, bp_id = await _setup_commuter(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences/cs1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["commute_impact"] is not None
    assert resp.json()["commute_impact"]["impact_level"] == "green"


@pytest.mark.anyio
async def test_search_sequence_by_number(client):
    """GET search/{seqNumber} returns the matching sequence."""
    token, bp_id = await _setup_commuter(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences/search/664",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["seq_number"] == 664


@pytest.mark.anyio
async def test_search_sequence_not_found(client):
    """GET search/{seqNumber} returns 404 for nonexistent sequence."""
    token, bp_id = await _setup_commuter(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences/search/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_filter_by_seq_number(client):
    """List with seq_number filter → single result."""
    token, bp_id = await _setup_commuter(client)
    resp = await client.get(
        f"/bid-periods/{bp_id}/sequences?seq_number=664",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["seq_number"] == 664
