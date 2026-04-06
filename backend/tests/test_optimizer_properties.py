"""Tests for PBS property-based sequence filtering (Task 95)."""

from __future__ import annotations

from app.services.optimizer import (
    _matches_property,
    filter_sequences_for_layer,
    compute_layer_summaries,
    compute_projected_schedule,
    score_sequence_from_properties,
    optimize_bid,
)


def _seq(
    seq_number=100,
    report_base="06:00",
    release_base="18:00",
    is_ipd=False,
    is_nipd=False,
    is_odan=False,
    is_redeye=False,
    has_deadhead=False,
    duty_days=3,
    tpay_minutes=600,
    tafb_minutes=2000,
    layover_cities=None,
    equipment="777",
    legs_per_dp=2,
    dp_count=1,
    duty_minutes=480,
    language=None,
):
    """Build a minimal sequence dict for property matching tests."""
    legs = [
        {
            "equipment": equipment,
            "arrival_station": (layover_cities or ["LHR"])[0] if layover_cities else "LHR",
            "departure_station": "ORD",
            "block_minutes": 300,
            "ground_minutes": 60,
            "is_connection": True,
        }
    ] * legs_per_dp
    dps = [
        {
            "report_base": report_base,
            "release_base": release_base,
            "duty_minutes": duty_minutes,
            "legs": legs,
        }
    ] * dp_count
    return {
        "seq_number": seq_number,
        "is_ipd": is_ipd,
        "is_nipd": is_nipd,
        "is_odan": is_odan,
        "is_redeye": is_redeye,
        "has_deadhead": has_deadhead,
        "language": language,
        "layover_cities": layover_cities or [],
        "operating_dates": [1, 2, 3],
        "totals": {
            "duty_days": duty_days,
            "tpay_minutes": tpay_minutes,
            "tafb_minutes": tafb_minutes,
            "block_minutes": 500,
            "leg_count": legs_per_dp * dp_count,
            "deadhead_count": 0,
        },
        "duty_periods": dps,
    }


def _prop(key, value, layers=None, category="pairing"):
    return {
        "id": f"p-{key}-{value}",
        "property_key": key,
        "category": category,
        "value": value,
        "layers": layers or [1],
        "is_enabled": True,
    }


# ── _matches_property tests ──────────────────────────────────────────────


class TestMatchesProperty:
    def test_report_between_match(self):
        seq = _seq(report_base="07:00")
        assert _matches_property(seq, "report_between", {"start": 360, "end": 480}) is True

    def test_report_between_no_match(self):
        seq = _seq(report_base="10:00")
        assert _matches_property(seq, "report_between", {"start": 360, "end": 480}) is False

    def test_prefer_pairing_type_ipd(self):
        seq = _seq(is_ipd=True)
        assert _matches_property(seq, "prefer_pairing_type", "ipd") is True

    def test_prefer_pairing_type_mismatch(self):
        seq = _seq(is_ipd=False, is_nipd=False)
        assert _matches_property(seq, "prefer_pairing_type", "ipd") is False

    def test_prefer_pairing_length(self):
        seq = _seq(duty_days=3)
        assert _matches_property(seq, "prefer_pairing_length", 3) is True
        assert _matches_property(seq, "prefer_pairing_length", 2) is False

    def test_prefer_aircraft_match(self):
        seq = _seq(equipment="777")
        assert _matches_property(seq, "prefer_aircraft", "777") is True

    def test_avoid_aircraft(self):
        seq = _seq(equipment="777")
        assert _matches_property(seq, "avoid_aircraft", "737") is True
        assert _matches_property(seq, "avoid_aircraft", "777") is False

    def test_layover_at_city(self):
        seq = _seq(layover_cities=["LHR", "NRT"])
        assert _matches_property(seq, "layover_at_city", "LHR") is True
        assert _matches_property(seq, "layover_at_city", "CDG") is False

    def test_avoid_layover_at_city(self):
        seq = _seq(layover_cities=["LHR"])
        assert _matches_property(seq, "avoid_layover_at_city", "CDG") is True
        assert _matches_property(seq, "avoid_layover_at_city", "LHR") is False

    def test_max_landings_per_duty(self):
        seq = _seq(legs_per_dp=3)
        assert _matches_property(seq, "max_landings_per_duty", 4) is True
        assert _matches_property(seq, "max_landings_per_duty", 2) is False

    def test_prefer_one_landing_first_duty(self):
        seq1 = _seq(legs_per_dp=1)
        seq2 = _seq(legs_per_dp=3)
        assert _matches_property(seq1, "prefer_one_landing_first_duty", True) is True
        assert _matches_property(seq2, "prefer_one_landing_first_duty", True) is False

    def test_mid_pairing_report_after(self):
        seq = {
            **_seq(dp_count=3),
            "duty_periods": [
                {"report_base": "05:00", "release_base": "18:00", "legs": [], "duty_minutes": 480},
                {"report_base": "08:00", "release_base": "18:00", "legs": [], "duty_minutes": 480},
                {"report_base": "06:00", "release_base": "18:00", "legs": [], "duty_minutes": 480},
            ],
        }
        assert _matches_property(seq, "mid_pairing_report_after", 420) is True  # 08:00 >= 07:00
        assert _matches_property(seq, "mid_pairing_report_after", 540) is False  # 08:00 < 09:00

    def test_unknown_property_passes(self):
        seq = _seq()
        assert _matches_property(seq, "some_future_property", "anything") is True


# ── filter_sequences_for_layer tests ─────────────────────────────────────


class TestFilterSequencesForLayer:
    def test_no_properties_returns_all(self):
        seqs = [_seq(seq_number=1), _seq(seq_number=2), _seq(seq_number=3)]
        result = filter_sequences_for_layer(seqs, [], 1)
        assert len(result) == 3

    def test_single_filter(self):
        seqs = [
            _seq(seq_number=1, is_ipd=True),
            _seq(seq_number=2, is_ipd=False),
            _seq(seq_number=3, is_ipd=True),
        ]
        props = [_prop("prefer_pairing_type", "ipd", layers=[1])]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 2
        assert all(s["is_ipd"] for s in result)

    def test_or_logic_same_key(self):
        """Same property_key with different values = OR (union)."""
        seqs = [
            _seq(seq_number=1, layover_cities=["LHR"]),
            _seq(seq_number=2, layover_cities=["NRT"]),
            _seq(seq_number=3, layover_cities=["CDG"]),
        ]
        props = [
            _prop("layover_at_city", "LHR", layers=[1]),
            _prop("layover_at_city", "NRT", layers=[1]),
        ]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 2  # LHR or NRT

    def test_and_logic_different_keys(self):
        """Different property_keys = AND (intersection)."""
        seqs = [
            _seq(seq_number=1, layover_cities=["LHR"], duty_days=3),
            _seq(seq_number=2, layover_cities=["LHR"], duty_days=2),
            _seq(seq_number=3, layover_cities=["CDG"], duty_days=3),
        ]
        props = [
            _prop("layover_at_city", "LHR", layers=[1]),
            _prop("prefer_pairing_length", 3, layers=[1]),
        ]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 1
        assert result[0]["seq_number"] == 1

    def test_layer_filtering(self):
        """Properties on different layers don't affect other layers."""
        seqs = [_seq(seq_number=1, is_ipd=True), _seq(seq_number=2, is_ipd=False)]
        props = [_prop("prefer_pairing_type", "ipd", layers=[1])]
        # Layer 1: only IPD
        assert len(filter_sequences_for_layer(seqs, props, 1)) == 1
        # Layer 2: no properties → all sequences
        assert len(filter_sequences_for_layer(seqs, props, 2)) == 2

    def test_disabled_property_ignored(self):
        seqs = [_seq(seq_number=1, is_ipd=True), _seq(seq_number=2, is_ipd=False)]
        props = [{**_prop("prefer_pairing_type", "ipd", layers=[1]), "is_enabled": False}]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 2  # disabled, so no filtering


# ── Task 96: compute_layer_summaries ─────────────────────────────────────


class TestComputeLayerSummaries:
    def test_no_properties_all_in_layer1(self):
        """No properties → all sequences in every layer, cumulative from L1."""
        seqs = [_seq(seq_number=i) for i in range(100)]
        summaries = compute_layer_summaries(seqs, [], num_layers=7)
        assert len(summaries) == 7
        assert summaries[0]["total_pairings"] == 100
        assert summaries[0]["pairings_by_layer"] == 100
        # Layers 2-7: same cumulative, 0 new
        for s in summaries[1:]:
            assert s["total_pairings"] == 100
            assert s["pairings_by_layer"] == 0

    def test_progressive_filtering(self):
        """L1 restrictive, later layers wider → cumulative grows."""
        seqs = [
            _seq(seq_number=1, is_ipd=True, duty_days=3),
            _seq(seq_number=2, is_ipd=True, duty_days=2),
            _seq(seq_number=3, is_ipd=False, duty_days=3),
            _seq(seq_number=4, is_ipd=False, duty_days=2),
        ]
        props = [
            # L1: IPD AND 3-day → only seq 1
            _prop("prefer_pairing_type", "ipd", layers=[1]),
            _prop("prefer_pairing_length", 3, layers=[1]),
            # L2: IPD only → seq 1 + seq 2
            _prop("prefer_pairing_type", "ipd", layers=[2]),
            # L3-7: no pairing props → all 4
        ]
        summaries = compute_layer_summaries(seqs, props, num_layers=7)
        assert summaries[0]["pairings_by_layer"] == 1  # seq 1
        assert summaries[0]["total_pairings"] == 1
        assert summaries[1]["pairings_by_layer"] == 1  # seq 2 is new
        assert summaries[1]["total_pairings"] == 2
        # L3 onward: all 4 in pool, 2 new
        assert summaries[2]["total_pairings"] == 4
        assert summaries[2]["pairings_by_layer"] == 2

    def test_properties_count(self):
        """Each layer reports its own property count."""
        props = [
            _prop("prefer_aircraft", "777", layers=[1, 2]),
            _prop("layover_at_city", "NRT", layers=[1]),
            _prop("avoid_deadheads", True, layers=[3]),
        ]
        summaries = compute_layer_summaries([], props, num_layers=7)
        assert summaries[0]["properties_count"] == 2  # L1: aircraft + layover
        assert summaries[1]["properties_count"] == 1  # L2: aircraft
        assert summaries[2]["properties_count"] == 1  # L3: deadheads
        assert summaries[3]["properties_count"] == 0  # L4: none


# ── Task 97: score_sequence_from_properties ──────────────────────────────


class TestScoreSequenceFromProperties:
    def test_all_match(self):
        """Sequence matching all 3 active properties → score high (near 1.0).

        Score includes a small quality tiebreaker based on credit-per-duty-day,
        so it won't be exactly 1.0 but should be very close.
        """
        seq = _seq(is_ipd=True, layover_cities=["NRT"], duty_days=3)
        props = [
            _prop("prefer_pairing_type", "ipd", layers=[1]),
            _prop("layover_at_city", "NRT", layers=[1]),
            _prop("prefer_pairing_length", 3, layers=[1]),
        ]
        score = score_sequence_from_properties(seq, props, 1)
        assert score > 0.9, f"All matching should score near 1.0, got {score}"

    def test_partial_match(self):
        """Sequence matching 1 of 3 → score near 0.33 (plus quality tiebreaker)."""
        seq = _seq(is_ipd=True, layover_cities=["CDG"], duty_days=2)
        props = [
            _prop("prefer_pairing_type", "ipd", layers=[1]),
            _prop("layover_at_city", "NRT", layers=[1]),
            _prop("prefer_pairing_length", 3, layers=[1]),
        ]
        score = score_sequence_from_properties(seq, props, 1)
        assert abs(score - 1.0 / 3) < 0.05, f"Partial match should be near 0.33, got {score}"

    def test_no_properties_neutral(self):
        """No properties → 0.5 neutral."""
        seq = _seq()
        score = score_sequence_from_properties(seq, [], 1)
        assert score == 0.5

    def test_maximize_credit(self):
        """Higher TPAY sequences score higher with maximize_credit."""
        seq_high = _seq(tpay_minutes=1000)
        seq_low = _seq(tpay_minutes=350)
        props = [_prop("maximize_credit", True, layers=[1], category="line")]
        score_high = score_sequence_from_properties(seq_high, props, 1)
        score_low = score_sequence_from_properties(seq_low, props, 1)
        assert score_high > score_low

    def test_maximize_days_off(self):
        """Shorter sequences score higher with maximize_total_days_off."""
        seq_short = _seq(duty_days=1)
        seq_long = _seq(duty_days=4)
        props = [_prop("maximize_total_days_off", True, layers=[1], category="days_off")]
        s1 = score_sequence_from_properties(seq_short, props, 1)
        s2 = score_sequence_from_properties(seq_long, props, 1)
        assert s1 > s2


# ── Task 98: optimize_bid with bid_properties ────────────────────────────


def _full_seq(seq_number, operating_dates, is_ipd=False, tpay=600, equipment="777"):
    """Build a sequence with _id for optimize_bid."""
    return {
        "_id": f"seq-{seq_number}",
        "seq_number": seq_number,
        "is_ipd": is_ipd,
        "is_nipd": False,
        "is_odan": False,
        "is_redeye": False,
        "has_deadhead": False,
        "language": None,
        "layover_cities": ["LHR"] if is_ipd else [],
        "operating_dates": operating_dates,
        "totals": {
            "duty_days": len(operating_dates),
            "tpay_minutes": tpay,
            "tafb_minutes": tpay * 3,
            "block_minutes": tpay,
            "leg_count": 2,
            "deadhead_count": 0,
        },
        "duty_periods": [
            {
                "report_base": "06:00",
                "release_base": "18:00",
                "duty_minutes": 480,
                "legs": [{"equipment": equipment, "arrival_station": "LHR",
                          "departure_station": "ORD", "block_minutes": 300,
                          "ground_minutes": 60, "is_connection": False}],
            }
        ],
    }


class TestOptimizeBidWithProperties:
    def test_no_properties_uses_7_layers(self):
        """bid_properties=None → still 7 layers (no more 9-layer legacy)."""
        seqs = [_full_seq(i, [i * 3 + 1, i * 3 + 2]) for i in range(5)]
        entries, _ = optimize_bid(
            sequences=seqs,
            prefs={},
            seniority_number=500,
            total_base_fas=3000,
            user_langs=[],
            pinned_entries=[],
            excluded_ids=set(),
            total_dates=30,
            bid_properties=None,
        )
        max_layer = max(e["layer"] for e in entries) if entries else 0
        assert max_layer <= 7

    def test_with_properties_uses_7_layers(self):
        """bid_properties=[...] → max layer is 7."""
        seqs = [_full_seq(i, [i * 3 + 1, i * 3 + 2]) for i in range(5)]
        props = [_prop("prefer_pairing_length", 2, layers=[1, 2, 3, 4, 5, 6, 7])]
        entries, _ = optimize_bid(
            sequences=seqs,
            prefs={},
            seniority_number=500,
            total_base_fas=3000,
            user_langs=[],
            pinned_entries=[],
            excluded_ids=set(),
            total_dates=30,
            bid_properties=props,
        )
        max_layer = max(e["layer"] for e in entries) if entries else 0
        assert max_layer <= 7

    def test_properties_restrict_l1(self):
        """IPD-only property on L1 → L1 entries are all IPD."""
        seqs = [
            _full_seq(1, [1, 2, 3], is_ipd=True),
            _full_seq(2, [5, 6, 7], is_ipd=False),
            _full_seq(3, [10, 11, 12], is_ipd=True),
        ]
        props = [_prop("prefer_pairing_type", "ipd", layers=[1])]
        entries, _ = optimize_bid(
            sequences=seqs,
            prefs={},
            seniority_number=500,
            total_base_fas=3000,
            user_langs=[],
            pinned_entries=[],
            excluded_ids=set(),
            total_dates=30,
            bid_properties=props,
        )
        l1 = [e for e in entries if e["layer"] == 1]
        # All L1 entries should be IPD sequences
        ipd_seq_ids = {"seq-1", "seq-3"}
        for entry in l1:
            assert entry["sequence_id"] in ipd_seq_ids


# ── Days-off boundary enforcement tests (Task 110) ──────────────────────


class TestDaysOffBoundary:
    """Tests for string_days_off_starting / string_days_off_ending as hard exclusions."""

    def _off_prop(self, key, value, layers=None):
        return {
            "id": f"p-{key}",
            "property_key": key,
            "category": "days_off",
            "value": value,
            "layers": layers or [1],
            "is_enabled": True,
        }

    def test_starting_excludes_sequences_after_date(self):
        """string_days_off_starting=16 → sequences with ops on day 17 excluded."""
        seqs = [
            _seq(seq_number=1, tpay_minutes=500),  # default ops [1,2,3]
            _seq(seq_number=2, tpay_minutes=600),
        ]
        seqs[0]["operating_dates"] = [5, 10]
        seqs[1]["operating_dates"] = [17, 18]

        props = [self._off_prop("string_days_off_starting", 16)]
        result = filter_sequences_for_layer(seqs, props, 1)

        assert len(result) == 1
        assert result[0]["seq_number"] == 1

    def test_starting_keeps_sequences_before_date(self):
        """string_days_off_starting=16, ops only on day 5, 10 → included."""
        seqs = [_seq(seq_number=1)]
        seqs[0]["operating_dates"] = [5, 10]

        props = [self._off_prop("string_days_off_starting", 16)]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 1

    def test_ending_excludes_sequences_before_date(self):
        """string_days_off_ending=5 → sequences with ops on day 3 excluded."""
        seqs = [
            _seq(seq_number=1),
            _seq(seq_number=2),
        ]
        seqs[0]["operating_dates"] = [3, 4]
        seqs[1]["operating_dates"] = [10, 15]

        props = [self._off_prop("string_days_off_ending", 5)]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 1
        assert result[0]["seq_number"] == 2

    def test_both_boundaries_create_window(self):
        """starting=16, ending=5 → only sequences on days 6-15 pass."""
        seqs = [
            _seq(seq_number=1),  # ops [3] — excluded by ending=5
            _seq(seq_number=2),  # ops [10] — included
            _seq(seq_number=3),  # ops [20] — excluded by starting=16
        ]
        seqs[0]["operating_dates"] = [3]
        seqs[0]["totals"]["duty_days"] = 1
        seqs[1]["operating_dates"] = [10]
        seqs[1]["totals"]["duty_days"] = 1
        seqs[2]["operating_dates"] = [20]
        seqs[2]["totals"]["duty_days"] = 1

        props = [
            self._off_prop("string_days_off_starting", 16),
            self._off_prop("string_days_off_ending", 5),
        ]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 1
        assert result[0]["seq_number"] == 2

    def test_all_layers_with_starting(self):
        """Property on all 7 layers → all layers exclude post-date sequences."""
        seqs = [
            _seq(seq_number=1),
            _seq(seq_number=2),
        ]
        seqs[0]["operating_dates"] = [5]
        seqs[0]["totals"]["duty_days"] = 1
        seqs[1]["operating_dates"] = [20]
        seqs[1]["totals"]["duty_days"] = 1

        props = [self._off_prop("string_days_off_starting", 16, layers=[1, 2, 3, 4, 5, 6, 7])]

        for layer in range(1, 8):
            result = filter_sequences_for_layer(seqs, props, layer)
            assert len(result) == 1
            assert result[0]["seq_number"] == 1

    def test_multi_day_sequence_spanning_boundary_excluded(self):
        """3-day sequence starting day 14 spans to day 16 → excluded by starting=16."""
        seqs = [_seq(seq_number=1)]
        seqs[0]["operating_dates"] = [14]
        seqs[0]["totals"]["duty_days"] = 3  # spans days 14-16

        props = [self._off_prop("string_days_off_starting", 16)]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 0

    def test_date_string_value_parsed(self):
        """Property value as date string '2026-01-16' → parsed as day 16."""
        seqs = [
            _seq(seq_number=1),
            _seq(seq_number=2),
        ]
        seqs[0]["operating_dates"] = [5]
        seqs[0]["totals"]["duty_days"] = 1
        seqs[1]["operating_dates"] = [20]
        seqs[1]["totals"]["duty_days"] = 1

        props = [self._off_prop("string_days_off_starting", "2026-01-16")]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 1
        assert result[0]["seq_number"] == 1

    def test_disabled_property_ignored(self):
        """Disabled days-off property is ignored."""
        seqs = [_seq(seq_number=1)]
        seqs[0]["operating_dates"] = [20]
        seqs[0]["totals"]["duty_days"] = 1

        props = [{
            "id": "p-off",
            "property_key": "string_days_off_starting",
            "category": "days_off",
            "value": 16,
            "layers": [1],
            "is_enabled": False,
        }]
        result = filter_sequences_for_layer(seqs, props, 1)
        assert len(result) == 1  # disabled property should not filter


# ── Projected schedule tests (Task 111) ──────────────────────────────────


class TestComputeProjectedSchedule:
    """Tests for best-case projected schedule computation."""

    def test_selects_non_conflicting_sequences(self):
        """Layer 1 with 2 non-conflicting sequences → both selected."""
        seqs = [
            {"_id": "s1", "seq_number": 1, "category": "777 INTL",
             "operating_dates": [1, 2, 3], "totals": {"tpay_minutes": 1000, "duty_days": 3}},
            {"_id": "s2", "seq_number": 2, "category": "787 INTL",
             "operating_dates": [5, 6, 7], "totals": {"tpay_minutes": 800, "duty_days": 3}},
        ]
        entries = [
            {"rank": 1, "sequence_id": "s1", "layer": 1, "is_excluded": False},
            {"rank": 2, "sequence_id": "s2", "layer": 1, "is_excluded": False},
        ]
        result = compute_projected_schedule(entries, seqs, layer=1, total_dates=30)
        assert len(result["sequences"]) == 2
        assert result["total_credit_hours"] == 30.0  # (1000+800)/60
        assert set(result["working_dates"]) == {1, 2, 3, 5, 6, 7}
        assert len(result["off_dates"]) == 24

    def test_skips_conflicting_sequences(self):
        """Sequences with overlapping dates → only first selected."""
        seqs = [
            {"_id": "s1", "seq_number": 1, "category": "777",
             "operating_dates": [1, 2, 3], "totals": {"tpay_minutes": 1000, "duty_days": 3}},
            {"_id": "s2", "seq_number": 2, "category": "787",
             "operating_dates": [2, 3, 4], "totals": {"tpay_minutes": 800, "duty_days": 3}},
        ]
        entries = [
            {"rank": 1, "sequence_id": "s1", "layer": 1, "is_excluded": False},
            {"rank": 2, "sequence_id": "s2", "layer": 1, "is_excluded": False},
        ]
        result = compute_projected_schedule(entries, seqs, layer=1, total_dates=30)
        assert len(result["sequences"]) == 1
        assert result["sequences"][0]["seq_number"] == 1

    def test_working_plus_off_equals_total(self):
        """working_dates + off_dates = all bid period dates."""
        seqs = [
            {"_id": "s1", "seq_number": 1, "category": "DOM",
             "operating_dates": [10, 11], "totals": {"tpay_minutes": 500, "duty_days": 2}},
        ]
        entries = [
            {"rank": 1, "sequence_id": "s1", "layer": 1, "is_excluded": False},
        ]
        result = compute_projected_schedule(entries, seqs, layer=1, total_dates=30)
        all_dates = set(result["working_dates"]) | set(result["off_dates"])
        assert all_dates == set(range(1, 31))

    def test_within_credit_range(self):
        """Total credit within range → within_credit_range=True."""
        seqs = [
            {"_id": "s1", "seq_number": 1, "category": "777",
             "operating_dates": [1, 2, 3], "totals": {"tpay_minutes": 4500, "duty_days": 3}},
        ]
        entries = [
            {"rank": 1, "sequence_id": "s1", "layer": 1, "is_excluded": False},
        ]
        result = compute_projected_schedule(
            entries, seqs, layer=1, total_dates=30,
            credit_min_minutes=4200, credit_max_minutes=5400,
        )
        assert result["within_credit_range"] is True

    def test_schedule_shape_in_output(self):
        """Shape string contains trip count and credit hours."""
        seqs = [
            {"_id": "s1", "seq_number": 1, "category": "DOM",
             "operating_dates": [1], "totals": {"tpay_minutes": 300, "duty_days": 1}},
        ]
        entries = [
            {"rank": 1, "sequence_id": "s1", "layer": 1, "is_excluded": False},
        ]
        result = compute_projected_schedule(entries, seqs, layer=1, total_dates=30)
        assert "1 trips" in result["schedule_shape"]
        assert "5.0 credit hours" in result["schedule_shape"]


# ── IPD pairing type fix tests (Task 117) ────────────────────────────────


class TestIPDPairingTypeFix:
    """Tests for improved IPD pairing type matching."""

    def test_ipd_flag_matches(self):
        """Sequence with is_ipd=True matches prefer_pairing_type: ipd."""
        seq = _seq(is_ipd=True)
        assert _matches_property(seq, "prefer_pairing_type", "ipd") is True

    def test_777_intl_nrt_matches_ipd(self):
        """ORD 777 INTL with NRT destination matches IPD via fallback."""
        seq = _seq(is_ipd=False, layover_cities=["NRT"])
        seq["category"] = "ORD 777 INTL"
        # Add NRT as arrival station in legs
        seq["duty_periods"][0]["legs"] = [
            {"equipment": "777", "arrival_station": "NRT", "departure_station": "ORD",
             "block_minutes": 700, "is_connection": False},
        ]
        assert _matches_property(seq, "prefer_pairing_type", "ipd") is True

    def test_787_intl_lhr_matches_ipd(self):
        """787 INTL with LHR destination matches IPD."""
        seq = _seq(is_ipd=False, layover_cities=["LHR"])
        seq["category"] = "ORD 787 INTL"
        seq["duty_periods"][0]["legs"] = [
            {"equipment": "787", "arrival_station": "LHR", "departure_station": "ORD",
             "block_minutes": 500, "is_connection": False},
        ]
        assert _matches_property(seq, "prefer_pairing_type", "ipd") is True

    def test_nbi_intl_cun_does_not_match_ipd(self):
        """NBI INTL with CUN (not IPD destination) does not match IPD."""
        seq = _seq(is_ipd=False, layover_cities=["CUN"])
        seq["category"] = "ORD NBI INTL"
        seq["duty_periods"][0]["legs"] = [
            {"equipment": "737", "arrival_station": "CUN", "departure_station": "ORD",
             "block_minutes": 300, "is_connection": False},
        ]
        assert _matches_property(seq, "prefer_pairing_type", "ipd") is False

    def test_nbi_intl_cun_matches_nipd(self):
        """NBI INTL CUN matches NIPD."""
        seq = _seq(is_nipd=True)
        assert _matches_property(seq, "prefer_pairing_type", "nipd") is True

    def test_domestic_does_not_match_ipd(self):
        """Domestic sequence does not match IPD."""
        seq = _seq(is_ipd=False)
        seq["category"] = "ORD NBD DOM"
        assert _matches_property(seq, "prefer_pairing_type", "ipd") is False
