"""Tests for the APFA PBS award file parser and survival curve computation."""

import pytest
from app.services.award_parser import (
    AwardedLine,
    AwardedPairing,
    MonthAward,
    parse_award_text,
    extract_pairing_award_map,
)
from app.services.holdability import (
    build_survival_curves,
    lookup_survival,
    _interpolate_curve,
)


# ── Synthetic award block text ────────────────────────────────────────────

SINGLE_BLOCK = """\
--------------------------------------------------------------------------------------------------------------------------------------------------------
LINE 1 PAY 78:17 1 2 | 3 4| 5 6 7 8 9 |10 11| 12 13 14 15 16 |17 18| 19 20 21 22 23 |24 25| 26 27 28 29 30 |31 1
061765 TAFB 122:03 TH FR |SA SU| MO TU WE TH FR |SA SU| MO TU WE TH FR |SA SU| MO TU WE TH FR |SA SU| MO TU WE TH FR |SA SU
LN CR. 78:17 5338 5338 | | 0667 5279 5281 5292 | | 5276 |
OFF 21 DH 0:00 * * ORD * ORD * * * * * * * HNL - ORD * ORD * ORD * ORD * * * * * * ORD * *
PRIORITY P1 P1 P1 P1 P1 P1 P1
POSITION 01 01 01 01 01 01 01
DTY 078:17 BLK 78:17 05338=/0713/1945/1022, 00667=/0900/0730/1721, 05279=/0733/2040/1036, 05281=/0735/2030/1015, 05292=/0756/1934/0908, 05276=/0718/2007/1013
--------------------------------------------------------------------------------------------------------------------------------------------------------
"""

TWO_BLOCKS = """\
--------------------------------------------------------------------------------------------------------------------------------------------------------
LINE 50 PAY 90:00 1 2 | 3 4| 5 6 7 8 9 |10 11|
111111 TAFB 150:00 TH FR |SA SU| MO TU WE TH FR |SA SU|
L2 CR. 90:00 0667 | | 5338 |
OFF 18 DH 0:00 HNL - ORD * * * * ORD * ORD
PRIORITY P1 P2
POSITION 04 04
DTY 090:00 BLK 90:00 00667=/0900/0730/1721, 05338=/0713/1945/1022
--------------------------------------------------------------------------------------------------------------------------------------------------------
LINE 100 PAY 70:00 1 2 | 3 4| 5 6 7 8 9 |10 11|
222222 TAFB 120:00 TH FR |SA SU| MO TU WE TH FR |SA SU|
L4 CR. 70:00 4657 | 3907 |
OFF 20 DH 0:00 * RSW ORD * * SAT - ORD *
PRIORITY P4 P4
POSITION 02 02
DTY 070:00 BLK 70:00 24657=/1705/2030/0824, 23907=/1625/1053/0731
--------------------------------------------------------------------------------------------------------------------------------------------------------
"""

NO_PAIRINGS_BLOCK = """\
--------------------------------------------------------------------------------------------------------------------------------------------------------
LINE 18 PAY 0.00 1 2 | 3 4| 5 6 7 8 9 |10 11|
064146 TAFB 0:00 TH FR |SA SU| MO TU WE TH FR |SA SU|
LN CR. 0:00 | | | | | |
OFF 30 DH 0:00 L L L L L L L L L L L L L
NO PAIRINGS AWARDED
--------------------------------------------------------------------------------------------------------------------------------------------------------
"""

PAGE_BREAK_BLOCK = """\
--------------------------------------------------------------------------------------------------------------------------------------------------------
LINE 7 PAY 91:54 1 2 | 3 4| 5 6 7 8 9 |10 11|
010567 TAFB 188:32 TH FR |SA SU| MO TU WE TH FR |SA SU|
L1 CR. 91:54 0678 | | /0667 | |
OFF 19 DH 7:42 * LAS - NRT LAS ORD HNL - ORD * * * * *
PRIORITY P1 P1 P1
POSITION 08 08 08
DTY 056:12 BLK 56:12 00678=/1426/1358/2130, 00667=/0900/0730/1721
--------------------------------------------------------------------------------------------------------------------------------------------------------
"""

DTY_CONTINUATION_BLOCK = """\
--------------------------------------------------------------------------------------------------------------------------------------------------------
LINE 9 PAY 73:57 1 2 | 3 4| 5 6 7 8 9 |10 11|
041836 TAFB 223:34 TH FR |SA SU| MO TU WE TH FR |SA SU|
L2 CR. 73:57 3861 | | 3800 4364 | | 4508 |
OFF 14 DH 0:00 * TPA ORD * * * ORD * MCI - ORD *
PRIORITY P1 P1 P1 P1 P1 P1 P2 P1
POSITION 04 04 04 04 04 04 04 04
DTY 016:44 BLK 54:33 23861=/0600/0920/0553, 23800=/1135/1958/0613, 24364=/2001/0800/0323, 24508=/1830/0045/0640, 23913=/1835/0908/0556, 23901=/1351/2101/0510,
05314=/1410/1934/1157, 00667=/0900/0730/0921
--------------------------------------------------------------------------------------------------------------------------------------------------------
"""


# ── Parser Tests ──────────────────────────────────────────────────────────


class TestParseAwardText:
    def test_single_block_basic_fields(self):
        award = parse_award_text(SINGLE_BLOCK, month="2026-01", base="ORD")
        assert award.total_lines == 1
        assert award.month == "2026-01"
        assert award.base == "ORD"

        ln = award.lines[0]
        assert ln.line_number == 1
        assert ln.employee_id == "061765"
        assert ln.layer_label == "LN"
        assert ln.pay_minutes == 78 * 60 + 17
        assert ln.tafb_minutes == 122 * 60 + 3
        assert ln.days_off == 21
        assert ln.deadhead_minutes == 0
        assert ln.no_pairings is False

    def test_single_block_pairings(self):
        award = parse_award_text(SINGLE_BLOCK)
        ln = award.lines[0]
        assert len(ln.pairings) == 6

        p0 = ln.pairings[0]
        assert p0.seq_number == 5338
        assert p0.priority == "P1"
        assert p0.position == "01"
        assert p0.report_time == "0713"
        assert p0.release_time == "1945"
        assert p0.block_minutes == 622  # 10:22

        p1 = ln.pairings[1]
        assert p1.seq_number == 667
        assert p1.report_time == "0900"
        assert p1.block_minutes == 1041  # 17:21

    def test_two_blocks(self):
        award = parse_award_text(TWO_BLOCKS)
        assert award.total_lines == 2

        ln50 = award.lines[0]
        assert ln50.line_number == 50
        assert ln50.layer_label == "L2"
        assert len(ln50.pairings) == 2
        assert ln50.pairings[0].seq_number == 667
        assert ln50.pairings[0].priority == "P1"
        assert ln50.pairings[1].seq_number == 5338
        assert ln50.pairings[1].priority == "P2"

        ln100 = award.lines[1]
        assert ln100.line_number == 100
        assert ln100.layer_label == "L4"
        assert len(ln100.pairings) == 2
        # 5-digit DTY "24657" → last 4 digits → 4657
        assert ln100.pairings[0].seq_number == 4657
        assert ln100.pairings[1].seq_number == 3907

    def test_no_pairings_awarded(self):
        award = parse_award_text(NO_PAIRINGS_BLOCK)
        assert award.total_lines == 1

        ln = award.lines[0]
        assert ln.line_number == 18
        assert ln.employee_id == "064146"
        assert ln.no_pairings is True
        assert len(ln.pairings) == 0
        assert ln.days_off == 30

    def test_five_digit_seq_prefix_stripped(self):
        """DTY rows use 5-digit seqs; leading digit is a prefix."""
        award = parse_award_text(TWO_BLOCKS)
        ln100 = award.lines[1]
        # DTY has "24657" and "23907" — last 4 digits are 4657, 3907
        assert ln100.pairings[0].seq_number == 4657
        assert ln100.pairings[1].seq_number == 3907

    def test_dty_continuation_line(self):
        """DTY row that wraps to a second line."""
        award = parse_award_text(DTY_CONTINUATION_BLOCK)
        ln = award.lines[0]
        assert ln.line_number == 9
        # Should have 8 pairings from the DTY (continuation included)
        assert len(ln.pairings) == 8
        seq_nums = [p.seq_number for p in ln.pairings]
        assert 3861 in seq_nums
        assert 667 in seq_nums  # from continuation line
        assert 5314 in seq_nums

    def test_page_break_block(self):
        """Block that might span a page break still parses."""
        award = parse_award_text(PAGE_BREAK_BLOCK)
        ln = award.lines[0]
        assert ln.line_number == 7
        assert ln.layer_label == "L1"
        assert len(ln.pairings) == 2
        assert ln.pairings[0].seq_number == 678
        assert ln.pairings[1].seq_number == 667

    def test_empty_text(self):
        award = parse_award_text("")
        assert award.total_lines == 0
        assert award.lines == []


class TestExtractPairingAwardMap:
    def test_basic_mapping(self):
        award = parse_award_text(TWO_BLOCKS)
        award.total_lines = 200  # set for seniority calc
        pmap = extract_pairing_award_map(award)

        # Seq 667 appears in both lines
        assert 667 in pmap
        instances = pmap[667]
        assert len(instances) == 1  # only line 50 has it
        assert instances[0]["line_number"] == 50

        # Seq 5338 in line 50
        assert 5338 in pmap
        assert pmap[5338][0]["line_number"] == 50

    def test_no_pairings_excluded(self):
        text = NO_PAIRINGS_BLOCK + TWO_BLOCKS
        award = parse_award_text(text)
        pmap = extract_pairing_award_map(award)
        # NO PAIRINGS line should not contribute any pairings
        for instances in pmap.values():
            for inst in instances:
                assert inst["line_number"] != 18


# ── Survival Curve Tests ──────────────────────────────────────────────────


class TestBuildSurvivalCurves:
    def _make_award_data(self, pairings, total_lines=100):
        return [{"total_lines": total_lines, "pairings": pairings}]

    def test_empty_data(self):
        assert build_survival_curves([]) == {}

    def test_basic_curve_shape(self):
        """Pairings awarded to senior lines should have low survival at high percentiles."""
        # All pairings awarded to top 10% (lines 1-10 of 100)
        pairings = [
            {"line_number": i, "block_minutes": 1300, "report_time": "0800"}
            for i in range(1, 11)
        ]
        curves = build_survival_curves(self._make_award_data(pairings))
        assert len(curves) > 0

        # The combined key should exist
        key = "high_credit|morning"
        assert key in curves

        curve = curves[key]
        early = dict(curve)
        # All pairings at lines 1-10 of 100 (pcts 0.01-0.10)
        # At 15% seniority, all were taken (0 survive past line 15)
        assert early[0.15] == 0.0
        # At 5% seniority, half survive (lines 5-10 are >= 5%)
        assert early[0.05] > 0.0

    def test_spread_distribution(self):
        """Pairings spread evenly should show gradual survival decline."""
        pairings = [
            {"line_number": i * 10, "block_minutes": 900, "report_time": "1100"}
            for i in range(1, 11)
        ]
        curves = build_survival_curves(self._make_award_data(pairings))
        key = "mid_credit|midday"
        assert key in curves
        curve_dict = dict(curves[key])
        # Should show gradual decline
        assert curve_dict[0.10] > curve_dict[0.50]
        assert curve_dict[0.50] > curve_dict[0.90]

    def test_minimum_sample_filter(self):
        """Buckets with fewer than 5 samples are excluded."""
        pairings = [
            {"line_number": i, "block_minutes": 1300, "report_time": "0800"}
            for i in range(1, 4)  # only 3 samples
        ]
        curves = build_survival_curves(self._make_award_data(pairings))
        # Combined key should be excluded (< 5 samples)
        assert "high_credit|morning" not in curves

    def test_multi_month_averaging(self):
        """Curves from multiple months should be combined."""
        month1 = {
            "total_lines": 100,
            "pairings": [
                {"line_number": 10, "block_minutes": 600, "report_time": "1500"}
                for _ in range(10)
            ],
        }
        month2 = {
            "total_lines": 100,
            "pairings": [
                {"line_number": 90, "block_minutes": 600, "report_time": "1500"}
                for _ in range(10)
            ],
        }
        curves = build_survival_curves([month1, month2])
        key = "low_credit|afternoon"
        assert key in curves
        # Mixed seniority should show moderate survival at 50%
        curve_dict = dict(curves[key])
        assert 0.3 < curve_dict[0.50] < 0.7


class TestLookupSurvival:
    def test_lookup_with_matching_key(self):
        curves = {
            "high_credit|morning": [
                (0.10, 0.95), (0.20, 0.85), (0.30, 0.75), (0.50, 0.50),
            ],
        }
        result = lookup_survival(curves, 0.30, block_minutes=1300, report_time="0800")
        assert result == 0.75

    def test_lookup_interpolation(self):
        curves = {
            "mid_credit|midday": [
                (0.10, 1.0), (0.30, 0.80), (0.50, 0.60),
            ],
        }
        result = lookup_survival(curves, 0.20, block_minutes=900, report_time="1100")
        assert result is not None
        assert 0.85 < result < 0.95  # interpolated between 1.0 and 0.80

    def test_lookup_fallback_to_single_trait(self):
        curves = {
            "high_credit": [
                (0.10, 0.90), (0.30, 0.70), (0.50, 0.50),
            ],
        }
        # No combined key exists, should fall back to "high_credit"
        result = lookup_survival(curves, 0.30, block_minutes=1300, report_time="0800")
        assert result == 0.70

    def test_lookup_no_data(self):
        result = lookup_survival({}, 0.30, block_minutes=1300, report_time="0800")
        assert result is None

    def test_lookup_empty_curves(self):
        result = lookup_survival(None, 0.30, block_minutes=1300, report_time="0800")
        assert result is None


class TestInterpolateCurve:
    def test_exact_match(self):
        curve = [(0.10, 0.90), (0.20, 0.80), (0.30, 0.70)]
        assert _interpolate_curve(curve, 0.20) == 0.80

    def test_between_points(self):
        curve = [(0.10, 1.0), (0.30, 0.80)]
        result = _interpolate_curve(curve, 0.20)
        assert abs(result - 0.90) < 0.01  # midpoint

    def test_below_range(self):
        curve = [(0.10, 0.90), (0.30, 0.70)]
        assert _interpolate_curve(curve, 0.05) == 0.90

    def test_above_range(self):
        curve = [(0.10, 0.90), (0.30, 0.70)]
        assert _interpolate_curve(curve, 0.50) == 0.70

    def test_empty_curve(self):
        assert _interpolate_curve([], 0.30) == 0.5
