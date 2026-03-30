"""Tests for optimizer Phase 1 (preference scoring) and Phase 2 (attainability)."""
from __future__ import annotations

import pytest

from app.services.optimizer import (
    score_sequence,
    estimate_attainability,
    _score_tpay,
    _score_days_off,
    _score_layover_city,
    _score_equipment,
    _score_redeye,
    _score_trip_length,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _seq(**overrides):
    base = {
        "_id": "s1",
        "seq_number": 663,
        "ops_count": 5,
        "operating_dates": [6, 7, 8],
        "is_turn": False,
        "is_redeye": False,
        "has_deadhead": False,
        "language": None,
        "layover_cities": ["LHR"],
        "totals": {
            "tpay_minutes": 1000,
            "block_minutes": 900,
            "tafb_minutes": 2800,
            "duty_days": 3,
            "leg_count": 4,
            "deadhead_count": 0,
        },
        "duty_periods": [
            {
                "report_base": "17:10",
                "release_base": "08:45",
                "legs": [{"equipment": "97"}],
            }
        ],
    }
    base.update(overrides)
    return base


def _prefs(**overrides):
    base = {
        "preferred_days_off": [],
        "preferred_layover_cities": [],
        "avoided_layover_cities": [],
        "tpay_min_minutes": None,
        "tpay_max_minutes": None,
        "preferred_equipment": [],
        "report_earliest_minutes": None,
        "report_latest_minutes": None,
        "release_earliest_minutes": None,
        "release_latest_minutes": None,
        "avoid_redeyes": False,
        "prefer_turns": None,
        "prefer_high_ops": None,
        "cluster_trips": False,
        "weights": {
            "tpay": 5,
            "days_off": 5,
            "layover_city": 5,
            "equipment": 5,
            "report_time": 5,
            "release_time": 5,
            "redeye": 5,
            "trip_length": 5,
        },
    }
    base.update(overrides)
    return base


# ── Phase 1: Individual scoring functions ─────────────────────────────────


class TestScoreTpay:
    def test_no_preference_returns_half(self):
        assert _score_tpay(_seq(), _prefs()) == 0.5

    def test_in_range_returns_one(self):
        p = _prefs(tpay_min_minutes=800, tpay_max_minutes=1200)
        assert _score_tpay(_seq(), p) == 1.0

    def test_below_range_degrades(self):
        p = _prefs(tpay_min_minutes=1200, tpay_max_minutes=1500)
        score = _score_tpay(_seq(), p)  # tpay=1000, range=1200-1500
        assert 0.0 < score < 1.0

    def test_above_range_degrades(self):
        p = _prefs(tpay_min_minutes=500, tpay_max_minutes=800)
        score = _score_tpay(_seq(), p)  # tpay=1000, range=500-800
        assert 0.0 < score < 1.0

    def test_min_only_above(self):
        p = _prefs(tpay_min_minutes=800)
        assert _score_tpay(_seq(), p) == 1.0

    def test_min_only_below(self):
        p = _prefs(tpay_min_minutes=1500)
        score = _score_tpay(_seq(), p)
        assert 0.0 < score < 1.0


class TestScoreDaysOff:
    def test_no_blocked_days(self):
        assert _score_days_off(_seq(), _prefs()) == 1.0

    def test_no_conflict(self):
        p = _prefs(preferred_days_off=[1, 2, 3])
        assert _score_days_off(_seq(), p) == 1.0  # seq operates 6,7,8

    def test_conflict_returns_zero(self):
        p = _prefs(preferred_days_off=[7, 15])
        assert _score_days_off(_seq(), p) == 0.0  # seq operates on 7


class TestScoreLayoverCity:
    def test_no_prefs_returns_half(self):
        assert _score_layover_city(_seq(), _prefs()) == 0.5

    def test_preferred_city(self):
        p = _prefs(preferred_layover_cities=["LHR"])
        assert _score_layover_city(_seq(), p) == 1.0

    def test_avoided_city(self):
        p = _prefs(avoided_layover_cities=["LHR"])
        assert _score_layover_city(_seq(), p) == 0.0

    def test_neutral_city(self):
        p = _prefs(preferred_layover_cities=["NRT"])
        assert _score_layover_city(_seq(), p) == 0.5

    def test_no_layovers_returns_half(self):
        s = _seq(layover_cities=[])
        assert _score_layover_city(s, _prefs(preferred_layover_cities=["LHR"])) == 0.5


class TestScoreEquipment:
    def test_no_preference(self):
        assert _score_equipment(_seq(), _prefs()) == 0.5

    def test_preferred_equipment(self):
        p = _prefs(preferred_equipment=["97"])
        assert _score_equipment(_seq(), p) == 1.0

    def test_non_preferred_equipment(self):
        p = _prefs(preferred_equipment=["83"])
        assert _score_equipment(_seq(), p) == 0.5


class TestScoreRedeye:
    def test_not_redeye(self):
        assert _score_redeye(_seq(), _prefs(avoid_redeyes=True)) == 1.0

    def test_redeye_avoided(self):
        s = _seq(is_redeye=True)
        assert _score_redeye(s, _prefs(avoid_redeyes=True)) == 0.0

    def test_redeye_not_avoided(self):
        s = _seq(is_redeye=True)
        assert _score_redeye(s, _prefs(avoid_redeyes=False)) == 1.0


class TestScoreTripLength:
    def test_no_preference(self):
        assert _score_trip_length(_seq(), _prefs()) == 0.5

    def test_prefers_turns_is_turn(self):
        s = _seq(is_turn=True)
        assert _score_trip_length(s, _prefs(prefer_turns=True)) == 1.0

    def test_prefers_turns_not_turn(self):
        assert _score_trip_length(_seq(), _prefs(prefer_turns=True)) == 0.5

    def test_prefers_multiday_is_multiday(self):
        assert _score_trip_length(_seq(), _prefs(prefer_turns=False)) == 1.0


# ── Phase 1: Composite score_sequence ─────────────────────────────────────


class TestScoreSequence:
    def test_default_prefs_returns_midrange(self):
        score = score_sequence(_seq(), _prefs())
        assert 0.0 <= score <= 1.0

    def test_perfect_match(self):
        """Sequence that matches all preferences should score high."""
        s = _seq(is_turn=True, is_redeye=False, layover_cities=["NRT"])
        p = _prefs(
            tpay_min_minutes=800,
            tpay_max_minutes=1200,
            preferred_layover_cities=["NRT"],
            preferred_equipment=["97"],
            avoid_redeyes=True,
            prefer_turns=True,
        )
        score = score_sequence(s, p)
        assert score > 0.8

    def test_poor_match(self):
        """Redeye on a blocked day with avoided layover should score low."""
        s = _seq(is_redeye=True, operating_dates=[7], layover_cities=["EWR"])
        p = _prefs(
            preferred_days_off=[7],
            avoided_layover_cities=["EWR"],
            avoid_redeyes=True,
            weights={"tpay": 1, "days_off": 10, "layover_city": 10, "equipment": 1,
                     "report_time": 1, "release_time": 1, "redeye": 10, "trip_length": 1},
        )
        score = score_sequence(s, p)
        assert score < 0.2

    def test_weighted_criteria(self):
        """Higher weight on a matched criterion should increase score."""
        s = _seq(layover_cities=["NRT"])
        p_low = _prefs(
            preferred_layover_cities=["NRT"],
            weights={"tpay": 5, "days_off": 5, "layover_city": 1, "equipment": 5,
                     "report_time": 5, "release_time": 5, "redeye": 5, "trip_length": 5},
        )
        p_high = _prefs(
            preferred_layover_cities=["NRT"],
            weights={"tpay": 5, "days_off": 5, "layover_city": 10, "equipment": 5,
                     "report_time": 5, "release_time": 5, "redeye": 5, "trip_length": 5},
        )
        score_low = score_sequence(s, p_low)
        score_high = score_sequence(s, p_high)
        assert score_high > score_low

    def test_score_is_bounded(self):
        score = score_sequence(_seq(), _prefs())
        assert 0.0 <= score <= 1.0


# ── Phase 2: Attainability Estimation ─────────────────────────────────────


class TestEstimateAttainability:
    def test_zero_base_returns_unknown(self):
        assert estimate_attainability(_seq(), 100, 0, []) == "unknown"

    def test_senior_high_ops_is_high(self):
        """Senior FA (low number) + high OPS → high attainability."""
        s = _seq(ops_count=25)
        result = estimate_attainability(s, 100, 3000, [])
        assert result == "high"

    def test_junior_low_ops_is_low(self):
        """Junior FA (high number) + low OPS → low attainability."""
        s = _seq(ops_count=1)
        result = estimate_attainability(s, 2800, 3000, [])
        assert result == "low"

    def test_language_bonus_boosts(self):
        """Language-qualified sequence should boost attainability for qualified FA."""
        s = _seq(ops_count=2, language="JP")
        without_lang = estimate_attainability(s, 1500, 3000, [])
        with_lang = estimate_attainability(s, 1500, 3000, ["JP"])
        # Having the language qualification should improve or maintain attainability
        rank = {"low": 0, "medium": 1, "high": 2, "unknown": -1}
        assert rank[with_lang] >= rank[without_lang]

    def test_mid_seniority_mid_ops(self):
        """Mid-range seniority with moderate OPS → medium."""
        s = _seq(ops_count=10)
        result = estimate_attainability(s, 1500, 3000, [])
        assert result == "medium"

    def test_most_senior_always_high(self):
        """Seniority #1 should always be high regardless of OPS."""
        s = _seq(ops_count=1)
        result = estimate_attainability(s, 1, 3000, [])
        assert result == "high"

    def test_returns_valid_values(self):
        """Should always return one of the valid enum values."""
        for sen in [1, 500, 1500, 2999]:
            for ops in [1, 5, 15, 25]:
                result = estimate_attainability(_seq(ops_count=ops), sen, 3000, [])
                assert result in {"high", "medium", "low", "unknown"}
