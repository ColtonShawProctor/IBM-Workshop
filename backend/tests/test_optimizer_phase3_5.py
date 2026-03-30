"""Tests for optimizer Phase 3 (conflict groups), Phase 4 (strategic ordering),
Phase 5 (coverage analysis), rationale generation, and the full optimize_bid pipeline."""
from __future__ import annotations

import pytest

from app.services.optimizer import (
    build_conflict_groups,
    strategic_order,
    analyze_coverage,
    generate_rationale,
    optimize_bid,
    ATTAINABILITY_MULT,
)


def _seq(_id, operating_dates, **overrides):
    base = {
        "_id": _id,
        "seq_number": int(_id.replace("s", "")),
        "ops_count": 5,
        "operating_dates": operating_dates,
        "is_turn": False,
        "is_redeye": False,
        "has_deadhead": False,
        "language": None,
        "layover_cities": [],
        "totals": {"tpay_minutes": 1000, "block_minutes": 900, "tafb_minutes": 2800,
                   "duty_days": 3, "leg_count": 4, "deadhead_count": 0},
        "duty_periods": [{"report_base": "17:10", "release_base": "08:45",
                          "legs": [{"equipment": "97"}]}],
    }
    base.update(overrides)
    return base


# ── Phase 3: Conflict Groups ─────────────────────────────────────────────


class TestBuildConflictGroups:
    def test_no_overlap_separate_groups(self):
        seqs = [_seq("s1", [1, 2, 3]), _seq("s2", [4, 5, 6]), _seq("s3", [7, 8, 9])]
        groups = build_conflict_groups(seqs)
        # All in different groups
        assert len(set(groups.values())) == 3

    def test_overlapping_same_group(self):
        seqs = [_seq("s1", [1, 2, 3]), _seq("s2", [3, 4, 5])]
        groups = build_conflict_groups(seqs)
        assert groups["s1"] == groups["s2"]

    def test_transitive_conflict(self):
        """s1 overlaps s2, s2 overlaps s3 → all in same group."""
        seqs = [_seq("s1", [1, 2]), _seq("s2", [2, 3]), _seq("s3", [3, 4])]
        groups = build_conflict_groups(seqs)
        assert groups["s1"] == groups["s2"] == groups["s3"]

    def test_two_distinct_groups(self):
        seqs = [_seq("s1", [1, 2]), _seq("s2", [2, 3]),
                _seq("s3", [10, 11]), _seq("s4", [11, 12])]
        groups = build_conflict_groups(seqs)
        assert groups["s1"] == groups["s2"]
        assert groups["s3"] == groups["s4"]
        assert groups["s1"] != groups["s3"]

    def test_empty_dates(self):
        seqs = [_seq("s1", []), _seq("s2", [])]
        groups = build_conflict_groups(seqs)
        assert len(set(groups.values())) == 2

    def test_single_sequence(self):
        groups = build_conflict_groups([_seq("s1", [5, 6])])
        assert "s1" in groups

    def test_all_same_date(self):
        seqs = [_seq("s1", [15]), _seq("s2", [15]), _seq("s3", [15])]
        groups = build_conflict_groups(seqs)
        assert len(set(groups.values())) == 1


# ── Phase 4: Strategic Ordering ───────────────────────────────────────────


class TestStrategicOrder:
    def _scored(self, _id, pref, attain, dates, **kw):
        return {"_id": _id, "preference_score": pref, "attainability": attain,
                "operating_dates": dates, **kw}

    def test_higher_effective_score_first(self):
        seqs = [
            self._scored("s1", 0.5, "high", [1, 2]),
            self._scored("s2", 0.9, "high", [3, 4]),
        ]
        groups = {"s1": "g1", "s2": "g2"}
        result = strategic_order(seqs, groups, set(), False)
        assert result[0]["_id"] == "s2"

    def test_attainability_affects_ranking(self):
        """Same pref score but different attainability should affect order."""
        seqs = [
            self._scored("s1", 0.8, "low", [1, 2]),   # effective: 0.8*0.5=0.4
            self._scored("s2", 0.8, "high", [3, 4]),   # effective: 0.8*1.0=0.8
        ]
        groups = {"s1": "g1", "s2": "g2"}
        result = strategic_order(seqs, groups, set(), False)
        assert result[0]["_id"] == "s2"

    def test_conflict_group_kept_together(self):
        """Sequences in same conflict group should stay together."""
        seqs = [
            self._scored("s1", 0.9, "high", [1, 2]),
            self._scored("s2", 0.7, "high", [1, 2]),  # same dates = same group
            self._scored("s3", 0.8, "high", [5, 6]),
        ]
        groups = {"s1": "g1", "s2": "g1", "s3": "g2"}
        result = strategic_order(seqs, groups, set(), False)
        ids = [r["_id"] for r in result]
        # s1 and s2 should be adjacent (same group)
        idx1, idx2 = ids.index("s1"), ids.index("s2")
        assert abs(idx1 - idx2) == 1

    def test_pinned_entry_at_fixed_rank(self):
        seqs = [
            self._scored("s1", 0.9, "high", [1, 2]),
            self._scored("s2", 0.5, "high", [3, 4], pinned_rank=1),
            self._scored("s3", 0.7, "high", [5, 6]),
        ]
        groups = {"s1": "g1", "s2": "g2", "s3": "g3"}
        result = strategic_order(seqs, groups, {"s2"}, False)
        assert result[0]["_id"] == "s2"  # pinned at rank 1

    def test_cluster_trips_sorts_by_date(self):
        seqs = [
            self._scored("s1", 0.8, "high", [20, 21]),
            self._scored("s2", 0.8, "high", [1, 2]),
            self._scored("s3", 0.8, "high", [10, 11]),
        ]
        groups = {"s1": "g1", "s2": "g2", "s3": "g3"}
        result = strategic_order(seqs, groups, set(), cluster_trips=True)
        dates = [min(r["operating_dates"]) for r in result]
        assert dates == sorted(dates)


# ── Phase 5: Coverage Analysis ────────────────────────────────────────────


class TestAnalyzeCoverage:
    def test_full_coverage(self):
        entries = [
            {"operating_dates": [1, 2, 3, 4, 5]},
            {"operating_dates": [6, 7, 8, 9, 10]},
        ]
        result = analyze_coverage(entries, 10)
        assert result["coverage_rate"] == 1.0
        assert result["uncovered_dates"] == []
        assert len(result["covered_dates"]) == 10

    def test_partial_coverage(self):
        entries = [{"operating_dates": [1, 2, 3]}]
        result = analyze_coverage(entries, 10)
        assert result["coverage_rate"] == 0.3
        assert result["covered_dates"] == [1, 2, 3]
        assert result["uncovered_dates"] == [4, 5, 6, 7, 8, 9, 10]

    def test_excluded_entries_ignored(self):
        entries = [
            {"operating_dates": [1, 2, 3]},
            {"operating_dates": [4, 5, 6], "is_excluded": True},
        ]
        result = analyze_coverage(entries, 10)
        assert result["covered_dates"] == [1, 2, 3]

    def test_zero_dates(self):
        result = analyze_coverage([], 0)
        assert result["coverage_rate"] == 0.0

    def test_empty_entries(self):
        result = analyze_coverage([], 30)
        assert result["coverage_rate"] == 0.0
        assert len(result["uncovered_dates"]) == 30

    def test_overlapping_dates_deduped(self):
        entries = [
            {"operating_dates": [1, 2, 3]},
            {"operating_dates": [2, 3, 4]},
        ]
        result = analyze_coverage(entries, 5)
        assert result["covered_dates"] == [1, 2, 3, 4]
        assert result["coverage_rate"] == 0.8


# ── Rationale Generation ─────────────────────────────────────────────────


class TestGenerateRationale:
    def test_basic_rationale(self):
        seq = _seq("s1", [1, 2], layover_cities=["LHR"])
        text = generate_rationale(seq, 0.85, "high", {})
        assert "TPAY" in text
        assert "high" in text
        assert "85%" in text

    def test_preferred_layover_mentioned(self):
        seq = _seq("s1", [1], layover_cities=["NRT"])
        prefs = {"preferred_layover_cities": ["NRT"]}
        text = generate_rationale(seq, 0.9, "high", prefs)
        assert "NRT" in text
        assert "preferred" in text

    def test_language_mentioned(self):
        seq = _seq("s1", [1], language="JP")
        text = generate_rationale(seq, 0.7, "medium", {})
        assert "LANG JP" in text


# ── Full optimize_bid Pipeline ────────────────────────────────────────────


class TestOptimizeBid:
    def _prefs(self, **overrides):
        base = {
            "preferred_days_off": [],
            "preferred_layover_cities": ["NRT"],
            "avoided_layover_cities": [],
            "tpay_min_minutes": 800,
            "tpay_max_minutes": 1200,
            "preferred_equipment": [],
            "report_earliest_minutes": None,
            "report_latest_minutes": None,
            "release_earliest_minutes": None,
            "release_latest_minutes": None,
            "avoid_redeyes": False,
            "prefer_turns": None,
            "cluster_trips": False,
            "weights": {"tpay": 5, "days_off": 5, "layover_city": 5, "equipment": 5,
                        "report_time": 5, "release_time": 5, "redeye": 5, "trip_length": 5},
        }
        base.update(overrides)
        return base

    def test_basic_pipeline(self):
        seqs = [
            _seq("s1", [1, 2, 3], layover_cities=["NRT"]),
            _seq("s2", [4, 5, 6], layover_cities=["EWR"]),
            _seq("s3", [7, 8, 9]),
        ]
        entries = optimize_bid(seqs, self._prefs(), 500, 3000, [], [], set(), 30)
        assert len(entries) == 3
        # All entries have required fields
        for e in entries:
            assert "rank" in e
            assert "preference_score" in e
            assert "attainability" in e
            assert "date_conflict_group" in e
            assert "rationale" in e
            assert e["rationale"]  # not empty

    def test_excluded_sequences_at_end(self):
        seqs = [
            _seq("s1", [1, 2]),
            _seq("s2", [3, 4]),
            _seq("s3", [5, 6]),
        ]
        entries = optimize_bid(seqs, self._prefs(), 500, 3000, [], [], {"s2"}, 30)
        assert len(entries) == 3
        # s2 should be excluded and at the end
        excluded = [e for e in entries if e["is_excluded"]]
        assert len(excluded) == 1
        assert excluded[0]["sequence_id"] == "s2"
        assert excluded[0]["rank"] == 3

    def test_pinned_entries_respected(self):
        seqs = [
            _seq("s1", [1, 2]),
            _seq("s2", [3, 4]),
            _seq("s3", [5, 6]),
        ]
        pinned = [{"sequence_id": "s3", "rank": 1}]
        entries = optimize_bid(seqs, self._prefs(), 500, 3000, [], pinned, set(), 30)
        assert entries[0]["sequence_id"] == "s3"
        assert entries[0]["is_pinned"] is True

    def test_conflict_group_ids_assigned(self):
        seqs = [
            _seq("s1", [1, 2]),
            _seq("s2", [2, 3]),  # overlaps s1
            _seq("s3", [5, 6]),  # separate
        ]
        entries = optimize_bid(seqs, self._prefs(), 500, 3000, [], [], set(), 30)
        groups = {e["sequence_id"]: e["date_conflict_group"] for e in entries}
        assert groups["s1"] == groups["s2"]  # same conflict group
        assert groups["s1"] != groups["s3"]  # different

    def test_ranks_are_sequential(self):
        seqs = [_seq(f"s{i}", [i * 3 + 1, i * 3 + 2]) for i in range(5)]
        entries = optimize_bid(seqs, self._prefs(), 500, 3000, [], [], set(), 30)
        ranks = [e["rank"] for e in entries]
        assert ranks == list(range(1, 6))

    def test_preferred_layover_ranked_higher(self):
        """Sequence with preferred layover (NRT) should rank above neutral ones."""
        seqs = [
            _seq("s1", [1, 2], layover_cities=["EWR"]),
            _seq("s2", [4, 5], layover_cities=["NRT"]),
        ]
        entries = optimize_bid(seqs, self._prefs(), 500, 3000, [], [], set(), 30)
        s2_rank = next(e["rank"] for e in entries if e["sequence_id"] == "s2")
        s1_rank = next(e["rank"] for e in entries if e["sequence_id"] == "s1")
        assert s2_rank < s1_rank
