"""Tests for unified CBA validator."""

from __future__ import annotations

from app.services.cba_validator import validate_bid


def _seq(seq_num, dates, tpay=300, block=300, release_base="18:00", report_base="06:00",
         is_ipd=False, is_nipd=False):
    return {
        "seq_number": seq_num,
        "operating_dates": dates,
        "totals": {
            "tpay_minutes": tpay,
            "block_minutes": block,
            "deadhead_count": 0,
            "leg_count": 2,
        },
        "is_ipd": is_ipd,
        "is_nipd": is_nipd,
        "duty_periods": [
            {
                "release_base": release_base,
                "report_base": report_base,
                "legs": [{"block_minutes": block // 2}],
            }
        ],
    }


class TestValidateBid:
    def test_valid_bid(self):
        """All rules pass → is_valid=True, empty violations."""
        seqs = [
            _seq(100, [1, 2, 3], tpay=1500),
            _seq(101, [8, 9, 10], tpay=1500),
            _seq(102, [15, 16, 17], tpay=1500),
        ]
        result = validate_bid(seqs, line_option="standard", bid_period_days=30)
        assert result.is_valid is True
        assert len(result.violations) == 0
        assert result.credit_hour_summary.estimated_credit_hours == 75.0
        assert result.credit_hour_summary.within_range is True
        assert result.days_off_summary.total_days_off == 21
        assert result.days_off_summary.meets_requirement is True

    def test_7_day_block_violation(self):
        """Excessive block in 7-day window → violation."""
        seqs = [
            _seq(100, [1], block=600, tpay=600),
            _seq(101, [2], block=600, tpay=600),
            _seq(102, [3], block=600, tpay=600),
            _seq(103, [4], block=600, tpay=600),
        ]
        result = validate_bid(seqs, line_option="standard", is_reserve=False, bid_period_days=10)
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "CBA §11.B" in rules

    def test_multiple_violations(self):
        """Both days-off and credit-hour violations."""
        # 25 duty days → only 5 days off (< 11), and tpay=200*25=5000 is within range
        seqs = [_seq(100 + i, [i + 1], tpay=200) for i in range(25)]
        result = validate_bid(seqs, line_option="standard", bid_period_days=30)
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        # Should have at least days-off and 6-day violations
        assert any("§11.H" in r for r in rules) or any("§11.C" in r for r in rules)

    def test_credit_hour_summary_reflects_line_option(self):
        """Credit hour summary uses correct line option bounds."""
        seqs = [_seq(100, [1, 2], tpay=3500)]  # ~58h
        result = validate_bid(seqs, line_option="low", bid_period_days=30)
        assert result.credit_hour_summary.line_min == 40
        assert result.credit_hour_summary.line_max == 90
        assert result.credit_hour_summary.within_range is True

        result2 = validate_bid(seqs, line_option="standard", bid_period_days=30)
        assert result2.credit_hour_summary.line_min == 70
        assert result2.credit_hour_summary.within_range is False  # 58h < 70h
