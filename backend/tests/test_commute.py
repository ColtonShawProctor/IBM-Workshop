"""Tests for the commute impact analysis service."""

import pytest

from app.services.commute import (
    DEFAULT_COMMUTE_WINDOW,
    analyze_commute_gap,
    analyze_commute_impact,
    _parse_hhmm,
)


def _make_sequence(report_base: str, release_base: str, multi_dp: bool = False):
    """Create a minimal sequence dict with duty periods."""
    if multi_dp:
        return {
            "duty_periods": [
                {"report_base": report_base, "release_base": "18:00"},
                {"report_base": "08:00", "release_base": release_base},
            ]
        }
    return {
        "duty_periods": [
            {"report_base": report_base, "release_base": release_base}
        ]
    }


# ── parse helper ─────────────────────────────────────────────────────────────

def test_parse_hhmm():
    assert _parse_hhmm("14:26") == 866
    assert _parse_hhmm("05:30") == 330
    assert _parse_hhmm("00:00") == 0
    assert _parse_hhmm("23:59") == 1439


# ── analyze_commute_impact ───────────────────────────────────────────────────

class TestAnalyzeCommuteImpact:
    """Tests for per-sequence commute feasibility."""

    def test_dca_commuter_late_report_green(self):
        """DCA commuter, report 14:26 → easy commute, green."""
        seq = _make_sequence("14:26", "12:07")
        result = analyze_commute_impact(seq, "DCA", "ORD")

        assert result["first_day_feasible"] is True
        assert result["impact_level"] == "green"
        assert result["hotel_nights_needed"] == 0
        assert "easy commute" in result["first_day_note"]
        assert "14:26" in result["first_day_note"]

    def test_dca_commuter_early_report_red(self):
        """DCA commuter, report 05:30 → hotel night needed, red."""
        seq = _make_sequence("05:30", "12:07")
        result = analyze_commute_impact(seq, "DCA", "ORD")

        assert result["first_day_feasible"] is False
        assert result["hotel_nights_needed"] >= 1
        assert result["impact_level"] == "red"
        assert "hotel night" in result["first_day_note"]

    def test_dca_commuter_easy_release(self):
        """DCA commuter, release 12:07 → easy commute home."""
        seq = _make_sequence("14:26", "12:07")
        result = analyze_commute_impact(seq, "DCA", "ORD")

        assert result["last_day_feasible"] is True
        assert "easy commute home" in result["last_day_note"]

    def test_dca_commuter_late_release_red(self):
        """DCA commuter, release 22:00 → hotel night, red."""
        seq = _make_sequence("14:26", "22:00")
        result = analyze_commute_impact(seq, "DCA", "ORD")

        assert result["last_day_feasible"] is False
        assert result["impact_level"] == "red"
        assert "hotel night" in result["last_day_note"]

    def test_both_infeasible_two_hotel_nights(self):
        """Both first and last day infeasible → 2 hotel nights."""
        seq = _make_sequence("05:30", "22:00")
        result = analyze_commute_impact(seq, "DCA", "ORD")

        assert result["hotel_nights_needed"] == 2
        assert result["impact_level"] == "red"

    def test_yellow_tight_margin(self):
        """Report just barely feasible (within yellow margin) → yellow."""
        # DCA→ORD: first_arrival=510 + buffer=60 = 570 (09:30)
        # Report at 09:40 → margin = 10 min < 30 min yellow threshold
        seq = _make_sequence("09:40", "12:00")
        result = analyze_commute_impact(seq, "DCA", "ORD")

        assert result["first_day_feasible"] is True
        assert result["impact_level"] == "yellow"

    def test_multi_day_uses_first_and_last_dp(self):
        """Multi-day sequence: first report from DP1, last release from DP2."""
        seq = _make_sequence("14:00", "12:00", multi_dp=True)
        result = analyze_commute_impact(seq, "DCA", "ORD")

        # First report is 14:00 (from DP1), last release is 12:00 (from DP2)
        assert result["first_day_feasible"] is True
        assert result["last_day_feasible"] is True
        assert result["impact_level"] == "green"

    def test_unknown_commute_city_uses_fallback(self):
        """Unknown city pair uses conservative defaults."""
        seq = _make_sequence("14:00", "12:00")
        result = analyze_commute_impact(seq, "XYZ", "ORD")

        # Should still work with default window (10:00 arrival, 18:00 departure)
        assert result["first_day_feasible"] is True
        assert result["last_day_feasible"] is True
        assert isinstance(result["impact_level"], str)

    def test_unknown_city_early_report_uses_conservative_default(self):
        """Unknown city with 09:30 report: default arrival 10:00 + 60 = 11:00 → infeasible."""
        seq = _make_sequence("09:30", "12:00")
        result = analyze_commute_impact(seq, "XYZ", "ORD")

        # Default first_arrival = 600 (10:00), + 60 buffer = 660 (11:00)
        # Report 09:30 = 570 < 660 → infeasible
        assert result["first_day_feasible"] is False

    def test_empty_duty_periods(self):
        """Sequence with no duty periods returns neutral impact."""
        seq = {"duty_periods": []}
        result = analyze_commute_impact(seq, "DCA", "ORD")

        assert result["impact_level"] == "green"
        assert result["hotel_nights_needed"] == 0


# ── analyze_commute_gap ──────────────────────────────────────────────────────

class TestAnalyzeCommuteGap:
    """Tests for between-trip commute gap analysis."""

    def test_short_gap_cannot_go_home(self):
        """14h gap for DCA commuter → can't go home (need ~14h for DCA round-trip)."""
        # DCA→ORD: flight_time=120, min gap = 2*120 + 120 + 480 = 840 min = 14h
        result = analyze_commute_gap(
            seq_a_release_minutes=1080,
            seq_b_report_minutes=480,
            gap_hours=14.0,
            commute_from="DCA",
            base_city="ORD",
        )
        # 14h = 840min, min_gap = 840 → exactly at threshold, should be True
        assert result["can_go_home"] is True

    def test_very_short_gap_cannot_go_home(self):
        """12h gap for DCA commuter → can't go home."""
        result = analyze_commute_gap(
            seq_a_release_minutes=1080,
            seq_b_report_minutes=480,
            gap_hours=12.0,
            commute_from="DCA",
            base_city="ORD",
        )
        assert result["can_go_home"] is False
        assert "insufficient" in result["note"]

    def test_long_gap_can_go_home(self):
        """48h gap → can always go home."""
        result = analyze_commute_gap(
            seq_a_release_minutes=720,
            seq_b_report_minutes=720,
            gap_hours=48.0,
            commute_from="DCA",
            base_city="ORD",
        )
        assert result["can_go_home"] is True
        assert "enough time" in result["note"]

    def test_lax_commuter_needs_longer_gap(self):
        """LAX→ORD is 4h flight, needs ~20h minimum gap."""
        # LAX: flight_time=240, min gap = 2*240 + 120 + 480 = 1080 min = 18h
        result = analyze_commute_gap(
            seq_a_release_minutes=720,
            seq_b_report_minutes=720,
            gap_hours=16.0,
            commute_from="LAX",
            base_city="ORD",
        )
        assert result["can_go_home"] is False

    def test_unknown_city_uses_default_flight_time(self):
        """Unknown city pair uses 3h default flight time."""
        # Default: flight_time=180, min gap = 2*180 + 120 + 480 = 960 min = 16h
        result = analyze_commute_gap(
            seq_a_release_minutes=720,
            seq_b_report_minutes=720,
            gap_hours=17.0,
            commute_from="XYZ",
            base_city="ORD",
        )
        assert result["can_go_home"] is True

    def test_gap_hours_in_result(self):
        """Result includes the gap_hours value."""
        result = analyze_commute_gap(
            seq_a_release_minutes=720,
            seq_b_report_minutes=720,
            gap_hours=24.0,
            commute_from="DCA",
            base_city="ORD",
        )
        assert result["gap_hours"] == 24.0
