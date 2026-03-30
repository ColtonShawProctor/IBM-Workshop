"""Tests for the PDF parser service."""
from __future__ import annotations

import pytest

from app.services.pdf_parser import (
    _extract_calendar_dates,
    _format_time,
    _hmm_to_minutes,
    _parse_date,
    _parse_leg_line,
    parse_bid_sheet_text,
)


# ── Fixtures: real PDF text samples ─────────────────────────────────────────

MULTI_DAY_INTL_PAGE = """\
                                                                  MO TU WE TH FR SA SU
ORD 777
SEQ 663 4 OPS POSN 1 THRU 9 LANG JP 3                            -- -- -- -- -- -- --
RPT 1350/1350                                                     -- -- -- -- -- -- --
1 1/1 45 1105D ORD 1450/1450     LAS 1658/1858 QLF AA 4.08       -- 6 7 8 9 -- --
RLS 1713/1913                            0.00 4.08 5.23           -- 6 7 8 9 -- --
LAS SAHARA HOTEL 702-761-7000              17.27
SKYHOP GLOBAL 954-400-0412
RPT 1040/1240                                                     -- 6 7 8 9 -- --
2 2/3 77 35 LAS 1140/1340       NRT 1510/0410 QLF 11.30          -- 7 8 9 10 -- --
RLS 1540/0440                            0.00 11.30 13.00         -- 7 8 9 10 -- --
NRT HILTON NARITA 011-81-476-33-1121       42.50
LIMOUSINE BUS 011-81-476-32-1021
RPT 1030/2330                                                     -- 9 10 11 12 -- --
3 4/3 77 36 NRT 1130/0030       LAS 0810/1010 QLF 9.40           -- 9 10 11 12 -- --
RLS 0840/1040                            0.00 9.40 11.10          -- 9 10 11 12 -- --
LAS SAHARA HOTEL 702-761-7000              14.32
SKYHOP GLOBAL 954-400-0412
RPT 2312/0112                                                     -- 9 10 11 12 -- --
4 5/3 25 2218 LAS 0012/0212     ORD 0552/0552 QLF 3.40           -- 10 11 12 13 -- --
RLS 0622/0622                            0.00 3.40 4.10           -- 10 11 12 13 -- --
TTL 21.45 7.51 29.36 96.08
----------------------------------------------------------------------
F/A ISSUED 08DEC2025 EFF 01JAN2026 ORD 777 INTL PAGE 726
"""

TURN_PAGE = """\
                                                                  MO TU WE TH FR SA SU
SEQ 5256 17 OPS POSN 1 THRU 4                                    -- -- -- -- -- -- --
RPT 0600/0600                                                     -- -- -- -- -- -- --
1 1/1 25 1907 ORD 0700/0700     CUN 1149/1049 *BF 3.49           5 6 7 8 9 10 --
1 1/1 25 2016 CUN 1253/1153     ORD 1552/1552 QLF 3.59           5 6 7 8 9 10 --
RLS 1622/1622                    7.48 0.00 10.22                  5 6 7 8 9 10 --
TTL 7.48 0.00 7.48 10.22
----------------------------------------------------------------------
F/A ISSUED 08DEC2025 EFF 01JAN2026 ORD NBD DOM PAGE 200
"""

REDEYE_PAGE = """\
                                                                  MO TU WE TH FR SA SU
SEQ 900 2 OPS POSN 1 THRU 9                                      -- -- -- -- -- -- --
RPT 2030/2030                                                     -- -- -- -- -- -- --
1 1/1 77 500 ORD 2130/2130      HNL 0145/0345 QLF 8.15           -- -- 14 -- -- -- --
RLS 0215/0415                            0.00 8.15 8.45           -- -- 14 -- -- -- --
TTL 8.15 0.00 8.15 8.45
----------------------------------------------------------------------
F/A ISSUED 08DEC2025 EFF 01JAN2026 ORD 777 INTL PAGE 100
"""


# ── Helper function tests ──────────────────────────────────────────────────

class TestHelpers:
    def test_hmm_to_minutes(self):
        assert _hmm_to_minutes("21.45") == 21 * 60 + 45
        assert _hmm_to_minutes("0.00") == 0
        assert _hmm_to_minutes("7.48") == 7 * 60 + 48
        assert _hmm_to_minutes("96.08") == 96 * 60 + 8

    def test_format_time(self):
        assert _format_time("1350") == "13:50"
        assert _format_time("0600") == "06:00"
        assert _format_time("0012") == "00:12"

    def test_parse_date(self):
        assert _parse_date("08DEC2025") == "2025-12-08"
        assert _parse_date("01JAN2026") == "2026-01-01"

    def test_extract_calendar_dates(self):
        line = "1 1/1 25 1907 ORD 0700/0700     CUN 1149/1049 *BF 3.49           5 6 7 8 9 10 --"
        dates = _extract_calendar_dates(line)
        assert dates == [5, 6, 7, 8, 9, 10]

    def test_extract_calendar_dates_with_dashes(self):
        line = "RPT 1350/1350                                                     -- -- -- -- -- -- --"
        dates = _extract_calendar_dates(line)
        assert dates == []

    def test_extract_calendar_dates_mixed(self):
        line = "1 1/1 45 1105D ORD 1450/1450     LAS 1658/1858 QLF AA 4.08       -- 6 7 8 9 -- --"
        dates = _extract_calendar_dates(line)
        assert dates == [6, 7, 8, 9]


# ── Leg line parsing ───────────────────────────────────────────────────────

class TestLegParsing:
    def test_parse_deadhead_leg(self):
        line = "1 1/1 45 1105D ORD 1450/1450     LAS 1658/1858 QLF AA 4.08       -- 6 7 8 9 -- --"
        leg = _parse_leg_line(line)
        assert leg is not None
        assert leg["flight_number"] == "1105"
        assert leg["is_deadhead"] is True
        assert leg["dp_number"] == 1
        assert leg["equipment"] == "45"
        assert leg["departure_station"] == "ORD"
        assert leg["departure_local"] == "14:50"
        assert leg["departure_base"] == "14:50"
        assert leg["arrival_station"] == "LAS"
        assert leg["arrival_local"] == "16:58"
        assert leg["arrival_base"] == "18:58"
        assert leg["block_minutes"] == 4 * 60 + 8

    def test_parse_normal_leg(self):
        line = "1 1/1 25 1907 ORD 0700/0700     CUN 1149/1049 *BF 3.49           5 6 7 8 9 10 --"
        leg = _parse_leg_line(line)
        assert leg is not None
        assert leg["flight_number"] == "1907"
        assert leg["is_deadhead"] is False
        assert leg["meal_code"] == "*BF"
        assert leg["departure_station"] == "ORD"
        assert leg["arrival_station"] == "CUN"
        assert leg["block_minutes"] == 3 * 60 + 49

    def test_parse_leg_with_ground_time(self):
        line = "1 1/1 25 1907 ORD 0700/0700     CUN 1149/1049 *BF 3.49 1.04"
        leg = _parse_leg_line(line)
        assert leg is not None
        assert leg["ground_minutes"] == 64
        assert leg["is_connection"] is False

    def test_parse_leg_with_connection(self):
        line = "1 1/1 25 1907 ORD 0700/0700     CUN 1149/1049 *BF 3.49 1.43X"
        leg = _parse_leg_line(line)
        assert leg is not None
        assert leg["ground_minutes"] == 103
        assert leg["is_connection"] is True


# ── Multi-day international sequence ───────────────────────────────────────

class TestMultiDaySequence:
    @pytest.fixture
    def parsed(self):
        return parse_bid_sheet_text(MULTI_DAY_INTL_PAGE)

    def test_sequence_count(self, parsed):
        assert parsed["total_sequences"] == 1

    def test_category_detection(self, parsed):
        assert "ORD 777 INTL" in parsed["categories"]

    def test_issued_date(self, parsed):
        assert parsed["issued_date"] == "2025-12-08"

    def test_effective_start(self, parsed):
        assert parsed["effective_start"] == "2026-01-01"

    def test_base_city(self, parsed):
        assert parsed["base_city"] == "ORD"

    def test_seq_header(self, parsed):
        seq = parsed["sequences"][0]
        assert seq["seq_number"] == 663
        assert seq["ops_count"] == 4
        assert seq["position_min"] == 1
        assert seq["position_max"] == 9
        assert seq["language"] == "JP"
        assert seq["language_count"] == 3

    def test_category_assigned(self, parsed):
        seq = parsed["sequences"][0]
        assert seq["category"] == "ORD 777 INTL"

    def test_has_deadhead(self, parsed):
        seq = parsed["sequences"][0]
        assert seq["has_deadhead"] is True

    def test_is_not_turn(self, parsed):
        seq = parsed["sequences"][0]
        assert seq["is_turn"] is False

    def test_is_not_redeye(self, parsed):
        seq = parsed["sequences"][0]
        # The deadhead departs 14:50, not a redeye
        assert seq["is_redeye"] is False

    def test_layover_cities(self, parsed):
        seq = parsed["sequences"][0]
        assert "LAS" in seq["layover_cities"]
        assert "NRT" in seq["layover_cities"]

    def test_duty_period_count(self, parsed):
        seq = parsed["sequences"][0]
        assert len(seq["duty_periods"]) == 4

    def test_totals(self, parsed):
        seq = parsed["sequences"][0]
        totals = seq["totals"]
        assert totals["block_minutes"] == 21 * 60 + 45
        assert totals["synth_minutes"] == 7 * 60 + 51
        assert totals["tpay_minutes"] == 29 * 60 + 36
        assert totals["tafb_minutes"] == 96 * 60 + 8
        assert totals["duty_days"] == 4
        assert totals["leg_count"] == 4
        assert totals["deadhead_count"] == 1

    def test_first_dp_report_release(self, parsed):
        dp1 = parsed["sequences"][0]["duty_periods"][0]
        assert dp1["report_local"] == "13:50"
        assert dp1["report_base"] == "13:50"
        assert dp1["release_local"] == "17:13"
        assert dp1["release_base"] == "19:13"

    def test_layover_hotel_info(self, parsed):
        dp1 = parsed["sequences"][0]["duty_periods"][0]
        lay = dp1["layover"]
        assert lay is not None
        assert lay["city"] == "LAS"
        assert lay["hotel_name"] == "SAHARA HOTEL"
        assert lay["hotel_phone"] == "702-761-7000"
        assert lay["rest_minutes"] == 17 * 60 + 27
        assert lay["transport_company"] == "SKYHOP GLOBAL"
        assert lay["transport_phone"] == "954-400-0412"

    def test_operating_dates(self, parsed):
        seq = parsed["sequences"][0]
        dates = seq["operating_dates"]
        assert len(dates) > 0
        # Should contain dates from the calendar columns
        assert 6 in dates
        assert 7 in dates
        assert 8 in dates
        assert 9 in dates


# ── Turn / single-day sequence ─────────────────────────────────────────────

class TestTurnSequence:
    @pytest.fixture
    def parsed(self):
        return parse_bid_sheet_text(TURN_PAGE)

    def test_sequence_count(self, parsed):
        assert parsed["total_sequences"] == 1

    def test_is_turn(self, parsed):
        seq = parsed["sequences"][0]
        assert seq["is_turn"] is True

    def test_no_deadhead(self, parsed):
        seq = parsed["sequences"][0]
        assert seq["has_deadhead"] is False

    def test_no_layover(self, parsed):
        seq = parsed["sequences"][0]
        assert seq["layover_cities"] == []

    def test_seq_header(self, parsed):
        seq = parsed["sequences"][0]
        assert seq["seq_number"] == 5256
        assert seq["ops_count"] == 17
        assert seq["position_min"] == 1
        assert seq["position_max"] == 4
        assert seq["language"] is None

    def test_single_duty_period(self, parsed):
        seq = parsed["sequences"][0]
        assert len(seq["duty_periods"]) == 1

    def test_two_legs(self, parsed):
        seq = parsed["sequences"][0]
        dp = seq["duty_periods"][0]
        assert len(dp["legs"]) == 2

    def test_first_leg_meal_code(self, parsed):
        seq = parsed["sequences"][0]
        dp = seq["duty_periods"][0]
        assert dp["legs"][0]["meal_code"] == "*BF"

    def test_totals(self, parsed):
        seq = parsed["sequences"][0]
        totals = seq["totals"]
        assert totals["block_minutes"] == 7 * 60 + 48
        assert totals["synth_minutes"] == 0
        assert totals["tpay_minutes"] == 7 * 60 + 48
        assert totals["tafb_minutes"] == 10 * 60 + 22
        assert totals["duty_days"] == 1
        assert totals["leg_count"] == 2
        assert totals["deadhead_count"] == 0

    def test_operating_dates(self, parsed):
        seq = parsed["sequences"][0]
        dates = seq["operating_dates"]
        assert 5 in dates
        assert 6 in dates
        assert 10 in dates

    def test_category_dom(self, parsed):
        assert "ORD NBD DOM" in parsed["categories"]


# ── Redeye detection ───────────────────────────────────────────────────────

class TestRedeyeDetection:
    @pytest.fixture
    def parsed(self):
        return parse_bid_sheet_text(REDEYE_PAGE)

    def test_is_redeye(self, parsed):
        seq = parsed["sequences"][0]
        assert seq["is_redeye"] is True

    def test_is_not_turn(self, parsed):
        seq = parsed["sequences"][0]
        # Single DP, no layover = turn, but still a redeye
        assert seq["is_turn"] is True

    def test_operating_dates(self, parsed):
        seq = parsed["sequences"][0]
        assert 14 in seq["operating_dates"]


# ── Category detection from footer ─────────────────────────────────────────

class TestCategoryDetection:
    def test_intl_category(self):
        text = "F/A ISSUED 08DEC2025 EFF 01JAN2026 ORD 777 INTL PAGE 726"
        result = parse_bid_sheet_text(text)
        assert "ORD 777 INTL" in result["categories"]

    def test_dom_category(self):
        text = "F/A ISSUED 08DEC2025 EFF 01JAN2026 ORD NBD DOM PAGE 200"
        result = parse_bid_sheet_text(text)
        assert "ORD NBD DOM" in result["categories"]

    def test_msp_category(self):
        text = "F/A ISSUED 08DEC2025 EFF 01JAN2026 ORD MSP NBD DOM PAGE 300"
        result = parse_bid_sheet_text(text)
        assert "ORD MSP NBD DOM" in result["categories"]

    def test_787_category(self):
        text = "F/A ISSUED 08DEC2025 EFF 01JAN2026 ORD 787 INTL PAGE 400"
        result = parse_bid_sheet_text(text)
        assert "ORD 787 INTL" in result["categories"]


# ── Edge cases ─────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_text(self):
        result = parse_bid_sheet_text("")
        assert result["total_sequences"] == 0
        assert result["sequences"] == []

    def test_footer_only(self):
        text = "F/A ISSUED 08DEC2025 EFF 01JAN2026 ORD NBI INTL PAGE 1"
        result = parse_bid_sheet_text(text)
        assert result["total_sequences"] == 0
        assert result["issued_date"] == "2025-12-08"
        assert result["base_city"] == "ORD"
