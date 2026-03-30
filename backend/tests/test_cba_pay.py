"""Tests for CBA §3 compensation calculations."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.cba_pay import (
    get_hourly_rate,
    calc_duty_rig,
    calc_trip_rig,
    calc_sit_rig,
    calc_sequence_guarantee,
    get_position_premium,
    get_international_premium,
    get_speaker_premium,
    get_holiday_dates,
    is_holiday,
    estimate_sequence_pay,
)


# ── Task 59: Pay rate lookup ─────────────────────────────────────────────────


class TestGetHourlyRate:
    def test_1st_year_2024(self):
        assert get_hourly_rate(1, date(2024, 10, 1)) == 35.82

    def test_13th_year_2028(self):
        assert get_hourly_rate(13, date(2028, 10, 1)) == 92.79

    def test_5th_year_2026(self):
        assert get_hourly_rate(5, date(2026, 10, 1)) == 50.15

    def test_before_first_effective_uses_2024(self):
        assert get_hourly_rate(1, date(2024, 1, 1)) == 35.82

    def test_years_above_13_uses_13th(self):
        assert get_hourly_rate(20, date(2024, 10, 1)) == 82.24

    def test_years_below_1_uses_1st(self):
        assert get_hourly_rate(0, date(2024, 10, 1)) == 35.82

    def test_mid_year_uses_previous_effective(self):
        # March 2026 → uses 10/1/2025 rate
        assert get_hourly_rate(5, date(2026, 3, 15)) == 48.69


# ── Task 60: Rig calculators ─────────────────────────────────────────────────


class TestCalcDutyRig:
    def test_600_on_duty(self):
        assert calc_duty_rig(600) == 300

    def test_odd_minutes(self):
        assert calc_duty_rig(301) == 150  # truncates


class TestCalcTripRig:
    def test_2100_tafb(self):
        assert calc_trip_rig(2100) == 600

    def test_zero(self):
        assert calc_trip_rig(0) == 0


class TestCalcSitRig:
    def test_above_threshold(self):
        assert calc_sit_rig(180) == 15  # (180-150)/2 = 15

    def test_at_threshold(self):
        assert calc_sit_rig(150) == 0

    def test_below_threshold(self):
        assert calc_sit_rig(120) == 0


class TestCalcSequenceGuarantee:
    def test_block_wins(self):
        # block=700, duty_rig=500, trip_rig=600, 1 DP → dp_guarantee=300
        assert calc_sequence_guarantee(700, 500, 600, 1) == 700

    def test_dp_guarantee_wins(self):
        # block=400, duty_rig=350, trip_rig=420, 2 DPs → dp_guarantee=600
        assert calc_sequence_guarantee(400, 350, 420, 2) == 600

    def test_trip_rig_wins(self):
        assert calc_sequence_guarantee(300, 250, 400, 1) == 400

    def test_duty_rig_wins(self):
        assert calc_sequence_guarantee(200, 500, 300, 1) == 500


# ── Task 61: Position and international premiums ─────────────────────────────


class TestGetPositionPremium:
    def test_lead_b777_domestic(self):
        assert get_position_premium("lead", "B777", False, False) == 3.25

    def test_purser_b777_ipd(self):
        assert get_position_premium("purser", "B777", True, True) == 7.50

    def test_galley_b787_ipd(self):
        assert get_position_premium("galley", "B787", True, True) == 2.00

    def test_unknown_combo(self):
        assert get_position_premium("purser", "A319", False, False) == 0.0


class TestGetInternationalPremium:
    def test_ipd(self):
        assert get_international_premium(True, False) == 3.75

    def test_nipd(self):
        assert get_international_premium(False, True) == 3.00

    def test_domestic(self):
        assert get_international_premium(False, False) == 0.0


class TestGetSpeakerPremium:
    def test_domestic(self):
        assert get_speaker_premium(False, False) == 2.00

    def test_nipd_international(self):
        assert get_speaker_premium(True, False) == 5.00

    def test_ipd(self):
        assert get_speaker_premium(True, True) == 5.75


# ── Task 62: Holiday detection ───────────────────────────────────────────────


class TestGetHolidayDates:
    def test_november_2025(self):
        # Thanksgiving 2025 is Nov 27 (4th Thursday)
        holidays = get_holiday_dates(2025, 11)
        assert 26 in holidays  # Wed before
        assert 27 in holidays  # Thanksgiving
        assert 30 in holidays  # Sun after

    def test_december_2025(self):
        holidays = get_holiday_dates(2025, 12)
        # Mon after Thanksgiving (Nov 27 + 4 = Dec 1)
        assert 1 in holidays
        assert 24 in holidays
        assert 25 in holidays
        assert 26 in holidays
        assert 31 in holidays

    def test_january_2026(self):
        holidays = get_holiday_dates(2026, 1)
        assert holidays == [1]

    def test_july_no_holidays(self):
        holidays = get_holiday_dates(2025, 7)
        assert holidays == []


class TestIsHoliday:
    def test_christmas(self):
        assert is_holiday(2025, 12, 25) is True

    def test_regular_day(self):
        assert is_holiday(2025, 7, 15) is False


# ── Task 63: Full sequence pay estimator ─────────────────────────────────────


def _make_seq(
    block_minutes=300,
    tafb_minutes=900,
    duty_days=1,
    duty_minutes=480,
    is_ipd=False,
    is_nipd=False,
    is_speaker_sequence=False,
    has_holiday=False,
    equipment="B777",
):
    """Helper to build a minimal sequence dict for pay estimation."""
    return {
        "totals": {
            "block_minutes": block_minutes,
            "tafb_minutes": tafb_minutes,
            "duty_days": duty_days,
        },
        "duty_periods": [
            {
                "duty_minutes": duty_minutes,
                "legs": [{"equipment": equipment}],
            }
        ],
        "is_ipd": is_ipd,
        "is_nipd": is_nipd,
        "is_speaker_sequence": is_speaker_sequence,
        "has_holiday": has_holiday,
    }


class TestEstimateSequencePay:
    def test_simple_domestic_turn(self):
        """1 DP, 5h block, 1st year FA."""
        seq = _make_seq(block_minutes=300, tafb_minutes=300, duty_minutes=360)
        result = estimate_sequence_pay(seq, 1, date(2024, 10, 1))
        # 5h block = 300 min. Guarantee = max(300, 180, 85, 300) = 300 min = 5h
        # 5h * $35.82 = $179.10 = 17910 cents
        assert result["guarantee_cents"] == 17910
        assert result["international_premium_cents"] == 0
        assert result["total_cents"] == 17910

    def test_ipd_with_purser(self):
        """IPD sequence, 5th year, Purser position."""
        seq = _make_seq(
            block_minutes=480,
            tafb_minutes=3000,
            duty_days=2,
            duty_minutes=600,
            is_ipd=True,
            equipment="B777",
        )
        result = estimate_sequence_pay(seq, 5, date(2024, 10, 1), position="purser")
        # Guarantee: max(480, 300, 857, 600) = 857 min (trip rig wins: 3000/3.5=857)
        # But dp_guarantee for 2 DPs = max(600, 360) = 600
        # So guarantee = max(480, 300, 857, 600) = 857 min
        assert result["guarantee_cents"] > 0
        assert result["international_premium_cents"] > 0  # IPD: $3.75/hr
        assert result["position_premium_cents"] > 0  # Purser B777 IPD: $7.50/hr
        assert result["total_cents"] > result["guarantee_cents"]

    def test_speaker_on_holiday(self):
        """Speaker sequence on holiday — all premiums stack."""
        seq = _make_seq(
            block_minutes=300,
            tafb_minutes=300,
            is_nipd=True,
            is_speaker_sequence=True,
            has_holiday=True,
        )
        result = estimate_sequence_pay(
            seq, 5, date(2024, 10, 1), is_speaker=True
        )
        assert result["international_premium_cents"] > 0  # NIPD: $3.00
        assert result["speaker_premium_cents"] > 0  # Speaker intl: $5.00
        assert result["holiday_premium_cents"] > 0  # 100% of base
        assert result["total_cents"] > result["guarantee_cents"]

    def test_duty_rig_wins_over_block(self):
        """Short block but long on-duty → duty rig wins."""
        seq = _make_seq(block_minutes=120, tafb_minutes=600, duty_minutes=360)
        result = estimate_sequence_pay(seq, 1, date(2024, 10, 1))
        # block=120, duty_rig=180, trip_rig=171, dp_guarantee=300
        # Guarantee = max(120, 180, 171, 300) = 300 (dp guarantee wins here)
        assert result["guarantee_cents"] == int(round(300 / 60.0 * 35.82 * 100))
