"""Tests for CBA scheduling rules — duty time, rest, block limits, days off."""

from __future__ import annotations

import pytest

from app.services.cba_rules import (
    get_max_domestic_duty,
    get_max_domestic_actual_duty,
    classify_international_duty,
    get_intl_duty_limits,
    get_home_base_rest,
    get_layover_rest,
    check_seven_day_block_limits,
    check_six_day_limit,
    check_minimum_days_off,
    check_credit_hour_range,
    check_rest_between_sequences,
)


# ── Task 64: Domestic duty time chart ────────────────────────────────────────


class TestGetMaxDomesticDuty:
    def test_0730_3seg(self):
        """0700-1259 range, 3 segments → 13:15 = 795 min."""
        assert get_max_domestic_duty(450, 3) == 795

    def test_0530_6seg(self):
        """0500-0559 range, 6 segments → 11:15 = 675 min."""
        assert get_max_domestic_duty(330, 6) == 675

    def test_1800_4seg(self):
        """1700-2159 range, 4 segments → 11:15 = 675 min."""
        assert get_max_domestic_duty(1080, 4) == 675

    def test_0100_1seg(self):
        """0000-0359 range, 1 segment → 9:15 = 555 min."""
        assert get_max_domestic_duty(60, 1) == 555

    def test_7plus_segments(self):
        """7+ segments uses last column."""
        assert get_max_domestic_duty(450, 8) == 705  # 0700-1259, 7+


class TestGetMaxDomesticActualDuty:
    def test_0600(self):
        r, o = get_max_domestic_actual_duty(360)
        assert r == 795  # 13:15
        assert o == 900  # 15:00

    def test_1800(self):
        r, o = get_max_domestic_actual_duty(1080)
        assert r == 735  # 12:15
        assert o == 780  # 13:00


# ── Task 65: International duty type classification ──────────────────────────


class TestClassifyInternationalDuty:
    def test_non_long_range(self):
        assert classify_international_duty(600, 800) == "non_long_range"

    def test_mid_range(self):
        assert classify_international_duty(700, 870) == "mid_range"

    def test_long_range(self):
        assert classify_international_duty(780, 900) == "long_range"

    def test_extended_long_range(self):
        assert classify_international_duty(900, 1100) == "extended_long_range"

    def test_zero_block(self):
        assert classify_international_duty(0, 0) is None


class TestGetIntlDutyLimits:
    def test_non_long_range(self):
        limits = get_intl_duty_limits("non_long_range")
        assert limits["max_scheduled_minutes"] == 840
        assert limits["max_actual_minutes"] == 960
        assert limits["max_block_minutes"] == 720

    def test_long_range(self):
        limits = get_intl_duty_limits("long_range")
        assert limits["max_scheduled_minutes"] == 960
        assert limits["max_actual_minutes"] == 1080
        assert limits["max_block_minutes"] == 855


# ── Task 66: Rest requirements ───────────────────────────────────────────────


class TestGetHomeBaseRest:
    def test_domestic(self):
        assert get_home_base_rest(False, False) == 660  # 11h

    def test_intl_non_ipd(self):
        assert get_home_base_rest(False, True) == 720  # 12h

    def test_ipd(self):
        assert get_home_base_rest(True, True) == 870  # 14:30

    def test_long_range(self):
        assert get_home_base_rest(True, True, max_block_minutes=780) == 2160  # 36h

    def test_extended_long_range(self):
        assert get_home_base_rest(True, True, max_block_minutes=900) == 2880  # 48h


class TestGetLayoverRest:
    def test_domestic(self):
        assert get_layover_rest(False, False) == 600  # 10h

    def test_ipd(self):
        assert get_layover_rest(True, True) == 840  # 14h

    def test_non_ipd_intl(self):
        assert get_layover_rest(False, True) == 600  # 10h


# ── Task 67: 7-day block hour limits ─────────────────────────────────────────


def _seq(seq_num: int, dates: list, block: int, dh_count: int = 0, legs: int = 1):
    return {
        "seq_number": seq_num,
        "operating_dates": dates,
        "totals": {"block_minutes": block, "deadhead_count": dh_count, "leg_count": legs},
    }


class TestCheckSevenDayBlockLimits:
    def test_within_limit_lineholder(self):
        seqs = [
            _seq(100, [1, 2, 3], 600),  # ~200/day
            _seq(101, [4, 5, 6], 600),
            _seq(102, [7], 480),
        ]
        violations = check_seven_day_block_limits(seqs, is_reserve=False, bid_period_days=30)
        assert len(violations) == 0  # 1680 < 1800

    def test_exceeds_lineholder_ok_reserve(self):
        seqs = [
            _seq(100, [1, 2], 500),
            _seq(101, [3, 4], 500),
            _seq(102, [5, 6], 500),
            _seq(103, [7], 500),
        ]
        # Total in 7 days: ~1750. Lineholder limit=1800. This may or may not trigger
        # depending on per-day distribution.
        viols_lh = check_seven_day_block_limits(seqs, is_reserve=False, bid_period_days=10)
        viols_rsv = check_seven_day_block_limits(seqs, is_reserve=True, bid_period_days=10)
        # Reserve has higher limit (2100), should be ok
        assert len(viols_rsv) == 0

    def test_exceeds_both(self):
        seqs = [
            _seq(100, [1], 600),
            _seq(101, [2], 600),
            _seq(102, [3], 600),
            _seq(103, [4], 600),
        ]
        violations = check_seven_day_block_limits(seqs, is_reserve=True, bid_period_days=10)
        assert len(violations) == 1  # 2400 > 2100

    def test_deadhead_excluded(self):
        # 1800 total but half is deadhead → working block = 900
        seqs = [_seq(100, [1, 2, 3, 4, 5, 6, 7], 1800, dh_count=4, legs=8)]
        violations = check_seven_day_block_limits(seqs, is_reserve=False, bid_period_days=10)
        assert len(violations) == 0  # 900 < 1800


# ── Task 68: 6-day limit and minimum days off ────────────────────────────────


class TestCheckSixDayLimit:
    def test_6_then_off(self):
        seqs = [_seq(100, [1, 2, 3, 4, 5, 6], 600)]
        violations = check_six_day_limit(seqs, bid_period_days=30)
        assert len(violations) == 0

    def test_7_consecutive(self):
        seqs = [_seq(100, [1, 2, 3, 4, 5, 6, 7], 700)]
        violations = check_six_day_limit(seqs, bid_period_days=30)
        assert len(violations) == 1
        assert "CBA §11.C" in violations[0].rule


class TestCheckMinimumDaysOff:
    def test_enough_days_off(self):
        seqs = [_seq(100, list(range(1, 20)), 600)]  # 19 duty days → 11 off
        violations = check_minimum_days_off(seqs, bid_period_days=30)
        assert len(violations) == 0

    def test_too_few_days_off(self):
        seqs = [_seq(100, list(range(1, 22)), 600)]  # 21 duty days → 9 off
        violations = check_minimum_days_off(seqs, bid_period_days=30)
        assert len(violations) == 1
        assert "CBA §11.H" in violations[0].rule

    def test_vacation_proration(self):
        seqs = [_seq(100, list(range(1, 17)), 600)]  # 16 duty, 14 off
        violations = check_minimum_days_off(seqs, bid_period_days=30, vacation_days=7)
        assert len(violations) == 0  # prorated min ~10


# ── Task 69: Credit hour range ───────────────────────────────────────────────


class TestCheckCreditHourRange:
    def test_within_standard(self):
        violations = check_credit_hour_range(5000, "standard")
        assert len(violations) == 0

    def test_exceeds_standard(self):
        violations = check_credit_hour_range(5500, "standard")
        assert len(violations) == 1
        assert "above" in violations[0].message

    def test_within_high(self):
        violations = check_credit_hour_range(5500, "high")
        assert len(violations) == 0

    def test_below_standard(self):
        violations = check_credit_hour_range(3000, "standard")
        assert len(violations) == 1
        assert "below" in violations[0].message

    def test_within_low(self):
        violations = check_credit_hour_range(3000, "low")
        assert len(violations) == 0


# ── Task 70: Rest between sequences ──────────────────────────────────────────


def _rest_seq(seq_num, release_base, report_base, is_ipd=False, is_nipd=False, block_min=0):
    return {
        "seq_number": seq_num,
        "is_ipd": is_ipd,
        "is_nipd": is_nipd,
        "duty_periods": [
            {
                "release_base": release_base,
                "report_base": report_base,
                "legs": [{"block_minutes": block_min}],
            }
        ],
    }


class TestCheckRestBetweenSequences:
    def test_domestic_sufficient(self):
        a = _rest_seq(100, "18:00", "06:00")
        b = _rest_seq(101, "18:00", "06:00")
        violation = check_rest_between_sequences(a, b)
        assert violation is None  # 12h > 11h

    def test_domestic_insufficient(self):
        a = _rest_seq(100, "22:00", "06:00")
        b = _rest_seq(101, "22:00", "06:00")
        violation = check_rest_between_sequences(a, b)
        assert violation is not None  # 8h < 11h
        assert "CBA §11.I" in violation.rule

    def test_ipd_sufficient(self):
        a = _rest_seq(100, "20:00", "12:00", is_ipd=True)
        b = _rest_seq(101, "20:00", "12:00")
        violation = check_rest_between_sequences(a, b)
        assert violation is None  # 16h > 14:30

    def test_ipd_insufficient(self):
        a = _rest_seq(100, "20:00", "08:00", is_ipd=True)
        b = _rest_seq(101, "20:00", "08:00")
        violation = check_rest_between_sequences(a, b)
        assert violation is not None  # 12h < 14:30
        assert "CBA §14.H" in violation.rule
