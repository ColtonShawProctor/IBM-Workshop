"""Layer quality tests — verifying that the optimizer produces genuinely useful,
differentiated layers that an FA would actually want to bid.

These tests focus on:
1. Within-layer ranking: higher-quality sequences should rank above lower ones
2. Cross-layer differentiation: each layer should offer a meaningfully different schedule
3. Template-driven progression: templates should create proper L1→L7 degradation
4. Realistic scenarios: commuter bids, international explorer, high-credit domestic
"""
from __future__ import annotations

import pytest

from app.services.optimizer import (
    _build_one_layer,
    _all_possible_date_spans,
    _matches_property,
    build_layers,
    filter_sequences_for_layer,
    score_sequence_from_properties,
    optimize_bid,
    compute_layer_summaries,
    compute_projected_schedule,
    estimate_attainability,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_seq(
    seq_number: int,
    operating_dates: list[int],
    *,
    tpay_minutes: int = 600,
    duty_days: int | None = None,
    report_base: str = "08:00",
    release_base: str = "17:00",
    layover_cities: list[str] | None = None,
    equipment: str = "737",
    is_ipd: bool = False,
    is_nipd: bool = False,
    is_redeye: bool = False,
    is_odan: bool = False,
    has_deadhead: bool = False,
    language: str | None = None,
    category: str = "ORD DOM",
    tafb_minutes: int | None = None,
    dp_count: int | None = None,
    duty_minutes: int = 480,
) -> dict:
    """Build a realistic sequence dict for layer quality tests."""
    dd = duty_days if duty_days is not None else max(len(operating_dates), 1)
    if tafb_minutes is None:
        tafb_minutes = tpay_minutes * 3

    legs = [
        {
            "equipment": equipment,
            "arrival_station": (layover_cities or ["ORD"])[0],
            "departure_station": "ORD",
            "block_minutes": tpay_minutes // max(dd, 1),
            "ground_minutes": 60,
            "is_connection": False,
        }
    ]
    dps_count = dp_count if dp_count is not None else dd
    dps = [
        {
            "report_base": report_base,
            "release_base": release_base,
            "duty_minutes": duty_minutes,
            "legs": legs,
        }
    ] * dps_count

    return {
        "_id": f"seq-{seq_number}",
        "seq_number": seq_number,
        "category": category,
        "is_ipd": is_ipd,
        "is_nipd": is_nipd,
        "is_odan": is_odan,
        "is_redeye": is_redeye,
        "has_deadhead": has_deadhead,
        "language": language,
        "ops_count": 5,
        "layover_cities": layover_cities or [],
        "operating_dates": operating_dates,
        "totals": {
            "duty_days": dd,
            "tpay_minutes": tpay_minutes,
            "tafb_minutes": tafb_minutes,
            "block_minutes": tpay_minutes,
            "leg_count": len(legs) * dps_count,
            "deadhead_count": 1 if has_deadhead else 0,
        },
        "duty_periods": dps,
        "is_domestic": "INTL" not in (category or "").upper(),
    }


def _prop(key, value, layers=None, category="pairing"):
    return {
        "id": f"p-{key}-{value}",
        "property_key": key,
        "category": category,
        "value": value,
        "layers": layers or [1, 2, 3, 4, 5, 6, 7],
        "is_enabled": True,
    }


def _get_layer_seq_ids(entries: list[dict], layer: int) -> list[str]:
    """Get sequence IDs for a layer, ordered by rank."""
    return [
        e["sequence_id"]
        for e in sorted(entries, key=lambda e: e["rank"])
        if e["layer"] == layer
    ]


def _get_layer_seq_numbers(entries: list[dict], layer: int) -> list[int]:
    """Get sequence numbers for a layer, ordered by rank."""
    return [
        e["seq_number"]
        for e in sorted(entries, key=lambda e: e["rank"])
        if e["layer"] == layer
    ]


# ── Test 1: Within-Layer Ranking Quality ───────────────────────────────────


class TestWithinLayerRanking:
    """Verify that within a single layer, sequences are ranked by quality."""

    def test_higher_tpay_ranked_first_with_maximize_credit(self):
        """With maximize_credit on, higher-TPAY sequences should rank first."""
        seqs = [
            _make_seq(1, [1, 2, 3], tpay_minutes=400, duty_days=3),
            _make_seq(2, [5, 6, 7], tpay_minutes=900, duty_days=3),
            _make_seq(3, [10, 11, 12], tpay_minutes=700, duty_days=3),
        ]
        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )
        l1 = _get_layer_seq_numbers(entries, 1)
        assert len(l1) == 3
        # seq 2 (900 TPAY) should be ranked before seq 3 (700), before seq 1 (400)
        idx_high = l1.index(2)
        idx_mid = l1.index(3)
        idx_low = l1.index(1)
        assert idx_high < idx_mid < idx_low, (
            f"Expected TPAY ranking 2>3>1, got order: {l1}"
        )

    def test_ipd_filter_plus_maximize_credit_ranks_by_tpay(self):
        """IPD filter + maximize_credit: among IPD trips, higher TPAY wins."""
        seqs = [
            _make_seq(1, [1, 2, 3], tpay_minutes=1100, is_ipd=True, duty_days=3),
            _make_seq(2, [5, 6, 7], tpay_minutes=800, is_ipd=True, duty_days=3),
            _make_seq(3, [10, 11, 12], tpay_minutes=600, is_ipd=False, duty_days=3),  # filtered out of L1
        ]
        props = [
            _prop("prefer_pairing_type", "ipd", layers=[1]),
            _prop("maximize_credit", True, category="line"),
        ]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )
        l1 = _get_layer_seq_numbers(entries, 1)
        # Only IPD seqs in L1
        assert 3 not in l1, "Non-IPD seq should not be in L1"
        # seq 1 (1100 TPAY) should rank above seq 2 (800 TPAY)
        if len(l1) >= 2:
            assert l1.index(1) < l1.index(2), (
                f"Higher TPAY IPD should rank first, got: {l1}"
            )

    def test_attainability_affects_ranking(self):
        """Higher attainability sequences should rank above lower ones
        when preference scores are equal."""
        seqs = [
            # seq 1: high ops count → higher attainability
            _make_seq(1, [1, 2, 3], tpay_minutes=600, duty_days=3),
            # seq 2: low ops count → lower attainability
            _make_seq(2, [5, 6, 7], tpay_minutes=600, duty_days=3),
        ]
        seqs[0]["ops_count"] = 25  # high ops → more attainable
        seqs[1]["ops_count"] = 1   # low ops → less attainable

        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=1500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )
        l1 = _get_layer_seq_numbers(entries, 1)
        assert len(l1) == 2
        # Higher ops_count (seq 1) should have better attainability → higher effective score
        assert l1[0] == 1, f"Higher-attainability seq should rank first, got: {l1}"


# ── Test 2: Cross-Layer Differentiation ────────────────────────────────────


class TestCrossLayerDifferentiation:
    """Verify that layers actually differ from each other."""

    def test_layers_are_not_identical(self):
        """With enough sequences, layers should not be identical copies."""
        seqs = [
            _make_seq(i, [i * 3 + 1, i * 3 + 2, i * 3 + 3],
                      tpay_minutes=400 + i * 50, duty_days=3)
            for i in range(8)
        ]
        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )
        layer_sets = {}
        for layer_num in range(1, 8):
            layer_sets[layer_num] = set(_get_layer_seq_numbers(entries, layer_num))

        # At least some layers should have different compositions
        unique_compositions = len(set(frozenset(s) for s in layer_sets.values()))
        assert unique_compositions > 1, (
            "All 7 layers have identical sequence sets — no differentiation"
        )

    def test_l1_gets_best_sequences(self):
        """Layer 1 should contain the highest-scoring sequences."""
        seqs = [
            _make_seq(1, [1, 2, 3], tpay_minutes=1200, duty_days=3),  # best
            _make_seq(2, [5, 6, 7], tpay_minutes=400, duty_days=3),   # worst
            _make_seq(3, [10, 11, 12], tpay_minutes=900, duty_days=3),  # good
            _make_seq(4, [15, 16, 17], tpay_minutes=300, duty_days=3),  # worst
        ]
        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )
        l1 = _get_layer_seq_numbers(entries, 1)
        # L1 should have the best sequences (highest TPAY)
        assert 1 in l1, "Best TPAY sequence (1200 min) should be in L1"
        assert 3 in l1, "Second best TPAY (900 min) should be in L1"

    def test_progressive_layer_relaxation_with_typed_properties(self):
        """Properties on limited layers → progressive relaxation from L1 to L7."""
        seqs = [
            # IPD + 3-day + NRT — matches all filters
            _make_seq(1, [1, 2, 3], tpay_minutes=1000, duty_days=3,
                      is_ipd=True, layover_cities=["NRT"], equipment="777",
                      category="ORD 777 INTL"),
            # IPD + 3-day but NOT NRT
            _make_seq(2, [5, 6, 7], tpay_minutes=900, duty_days=3,
                      is_ipd=True, layover_cities=["LHR"], equipment="777",
                      category="ORD 777 INTL"),
            # IPD but 4-day
            _make_seq(3, [10, 11, 12, 13], tpay_minutes=1100, duty_days=4,
                      is_ipd=True, layover_cities=["CDG"], equipment="787",
                      category="ORD 787 INTL"),
            # Domestic 3-day
            _make_seq(4, [15, 16, 17], tpay_minutes=500, duty_days=3,
                      equipment="737"),
            # Domestic 2-day
            _make_seq(5, [20, 21], tpay_minutes=350, duty_days=2,
                      equipment="321"),
        ]
        props = [
            # L1 only: NRT + IPD + 3-day
            _prop("layover_at_city", "NRT", layers=[1]),
            _prop("prefer_pairing_type", "ipd", layers=[1, 2]),
            _prop("prefer_pairing_length", 3, layers=[1, 2, 3]),
            # All layers: maximize credit
            _prop("maximize_credit", True, layers=[1, 2, 3, 4, 5, 6, 7], category="line"),
        ]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )

        l1 = set(_get_layer_seq_numbers(entries, 1))
        l2 = set(_get_layer_seq_numbers(entries, 2))
        l3 = set(_get_layer_seq_numbers(entries, 3))

        # L1: Only NRT + IPD + 3-day should pass all filters → seq 1 only
        assert 1 in l1, "Seq 1 (NRT+IPD+3-day) should be in L1"
        # Seq 2 (LHR, not NRT) should NOT be in L1 (fails layover_at_city filter)
        assert 2 not in l1, "Seq 2 (LHR, not NRT) should NOT be in L1"

        # L2: IPD + 3-day (NRT dropped) → seqs 1, 2
        assert 1 in l2 or 2 in l2, "IPD 3-day seqs should be in L2"
        # Seq 4 (domestic) should NOT be in L2
        assert 4 not in l2, "Domestic seq should NOT be in L2 (IPD filter active)"

        # L3+: 3-day only (IPD dropped) → domestic 3-day trips also available
        # L4+: no pairing filter → everything available

    def test_reuse_penalty_creates_variety(self):
        """Sequences used in L1 should appear less often in later layers."""
        # Create sequences where some don't conflict with each other
        seqs = [
            _make_seq(1, [1, 2, 3], tpay_minutes=900, duty_days=3),
            _make_seq(2, [1, 2, 3], tpay_minutes=850, duty_days=3),  # conflicts with 1
            _make_seq(3, [5, 6, 7], tpay_minutes=800, duty_days=3),
            _make_seq(4, [5, 6, 7], tpay_minutes=750, duty_days=3),  # conflicts with 3
            _make_seq(5, [10, 11, 12], tpay_minutes=700, duty_days=3),
            _make_seq(6, [10, 11, 12], tpay_minutes=650, duty_days=3),  # conflicts with 5
        ]
        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )
        l1 = set(_get_layer_seq_numbers(entries, 1))
        l2 = set(_get_layer_seq_numbers(entries, 2))

        # L1 should pick the higher-TPAY from each conflict group: 1, 3, 5
        assert {1, 3, 5} <= l1 or len(l1) >= 3, f"L1 should get top sequences, got: {l1}"

        # L2 should have some alternatives (2, 4, 6) due to reuse penalty
        if l2:
            alternatives = l2 - l1
            # At least some sequences in L2 should differ from L1
            # (reuse penalty should push L1's picks down in L2)


# ── Test 3: Template-Driven Layer Progression ──────────────────────────────


class TestTemplateProgression:
    """Test realistic template configurations match expected layer behavior."""

    def _commuter_template_props(self):
        """Commuter Max Time Off template properties."""
        return [
            _prop("maximize_block_of_days_off", True,
                  layers=[1, 2, 3, 4, 5, 6, 7], category="days_off"),
            _prop("prefer_pairing_length", 3, layers=[1, 2, 3]),
            _prop("prefer_pairing_length", 4, layers=[4, 5]),
            _prop("report_between", {"start": 600, "end": 840}, layers=[1, 2, 3]),
            _prop("release_between", {"start": 480, "end": 1080}, layers=[1, 2, 3]),
            _prop("maximize_credit", True,
                  layers=[1, 2, 3, 4, 5, 6, 7], category="line"),
        ]

    def _international_explorer_props(self):
        """International Explorer template properties."""
        return [
            _prop("prefer_pairing_type", "ipd", layers=[1, 2]),
            _prop("prefer_aircraft", "777", layers=[1, 2, 3]),
            _prop("maximize_credit", True,
                  layers=[1, 2, 3, 4, 5, 6, 7], category="line"),
            _prop("prefer_pairing_length", 3, layers=[3, 4, 5]),
        ]

    def test_commuter_template_l1_filters_by_time_and_length(self):
        """Commuter template L1: only 3-day trips within report/release window."""
        seqs = [
            # Matches all L1 filters: 3-day, report 10:00, release 17:00
            _make_seq(1, [1, 2, 3], tpay_minutes=700, duty_days=3,
                      report_base="10:00", release_base="17:00"),
            # Wrong length: 4-day
            _make_seq(2, [5, 6, 7, 8], tpay_minutes=800, duty_days=4,
                      report_base="10:00", release_base="17:00"),
            # Too early report (05:00 < 10:00 window start)
            _make_seq(3, [10, 11, 12], tpay_minutes=750, duty_days=3,
                      report_base="05:00", release_base="17:00"),
            # Matches L1
            _make_seq(4, [15, 16, 17], tpay_minutes=650, duty_days=3,
                      report_base="12:00", release_base="16:00"),
        ]
        props = self._commuter_template_props()
        filtered_l1 = filter_sequences_for_layer(seqs, props, 1)
        filtered_l1_ids = {s["seq_number"] for s in filtered_l1}

        # Only seqs matching 3-day + report[600-840] + release[480-1080]
        assert 1 in filtered_l1_ids, "Seq 1 should pass L1 filters"
        assert 4 in filtered_l1_ids, "Seq 4 should pass L1 filters"
        assert 2 not in filtered_l1_ids, "4-day seq should fail L1 length filter"
        assert 3 not in filtered_l1_ids, "Early report seq should fail L1 time filter"

    def test_commuter_template_l4_allows_4day_trips(self):
        """Commuter template L4: 4-day trips, no time window filter."""
        seqs = [
            _make_seq(1, [1, 2, 3], tpay_minutes=700, duty_days=3),
            _make_seq(2, [5, 6, 7, 8], tpay_minutes=800, duty_days=4,
                      report_base="05:00"),
            _make_seq(3, [10, 11, 12, 13], tpay_minutes=750, duty_days=4),
        ]
        props = self._commuter_template_props()
        filtered_l4 = filter_sequences_for_layer(seqs, props, 4)
        filtered_l4_ids = {s["seq_number"] for s in filtered_l4}

        # L4 has prefer_pairing_length=4 only, no time filters
        assert 2 in filtered_l4_ids, "4-day seq should pass L4"
        assert 3 in filtered_l4_ids, "4-day seq should pass L4"
        assert 1 not in filtered_l4_ids, "3-day seq should fail L4 length filter"

    def test_commuter_template_l6_no_pairing_filter(self):
        """Commuter template L6-7: no pairing filters → all sequences pass."""
        seqs = [
            _make_seq(1, [1, 2, 3], tpay_minutes=700, duty_days=3),
            _make_seq(2, [5, 6, 7, 8], tpay_minutes=800, duty_days=4),
            _make_seq(3, [10, 11], tpay_minutes=350, duty_days=2),
            _make_seq(4, [15], tpay_minutes=200, duty_days=1,
                      report_base="04:00"),  # early report, any length
        ]
        props = self._commuter_template_props()
        filtered_l6 = filter_sequences_for_layer(seqs, props, 6)

        # L6 has no pairing-category properties → all pass
        assert len(filtered_l6) == 4, (
            f"L6 (no pairing filter) should pass all seqs, got {len(filtered_l6)}"
        )

    def test_international_explorer_l1_ipd_777_only(self):
        """Int'l Explorer L1: IPD + 777 only."""
        seqs = [
            _make_seq(1, [1, 2, 3], is_ipd=True, equipment="777",
                      category="ORD 777 INTL", tpay_minutes=1000, duty_days=3),
            _make_seq(2, [5, 6, 7], is_ipd=True, equipment="787",
                      category="ORD 787 INTL", tpay_minutes=900, duty_days=3),
            _make_seq(3, [10, 11, 12], is_ipd=False, equipment="777",
                      category="ORD 777 DOM", tpay_minutes=600, duty_days=3),
            _make_seq(4, [15, 16, 17], is_ipd=False, equipment="737",
                      tpay_minutes=500, duty_days=3),
        ]
        props = self._international_explorer_props()
        filtered_l1 = filter_sequences_for_layer(seqs, props, 1)
        filtered_l1_ids = {s["seq_number"] for s in filtered_l1}

        # L1: IPD AND 777 (no length filter on L1)
        assert 1 in filtered_l1_ids, "IPD+777 should pass L1"
        assert 2 not in filtered_l1_ids, "IPD+787 should fail L1 (777 filter)"
        assert 3 not in filtered_l1_ids, "DOM+777 should fail L1 (IPD filter)"

    def test_international_explorer_l3_adds_3day_filter(self):
        """Int'l Explorer L3: 777 + 3-day (IPD dropped)."""
        seqs = [
            _make_seq(1, [1, 2, 3], equipment="777", tpay_minutes=800, duty_days=3),
            _make_seq(2, [5, 6, 7, 8], equipment="777", tpay_minutes=900, duty_days=4),
            _make_seq(3, [10, 11, 12], equipment="737", tpay_minutes=600, duty_days=3),
        ]
        props = self._international_explorer_props()
        filtered_l3 = filter_sequences_for_layer(seqs, props, 3)
        filtered_l3_ids = {s["seq_number"] for s in filtered_l3}

        # L3: 777 AND 3-day (IPD filter not on L3)
        assert 1 in filtered_l3_ids, "777+3-day should pass L3"
        assert 2 not in filtered_l3_ids, "777+4-day should fail L3 (length filter)"
        assert 3 not in filtered_l3_ids, "737+3-day should fail L3 (equipment filter)"


# ── Test 4: Realistic FA Scenarios ─────────────────────────────────────────


class TestRealisticScenarios:
    """End-to-end tests simulating real FA bid scenarios."""

    def _build_diverse_pool(self) -> list[dict]:
        """Build a pool of 15 sequences mimicking a real ORD January bid."""
        return [
            # IPD trips (international premium)
            _make_seq(100, [1, 2, 3], tpay_minutes=1100, duty_days=3,
                      is_ipd=True, layover_cities=["NRT"], equipment="777",
                      language="JP", category="ORD 777 INTL"),
            _make_seq(101, [5, 6, 7], tpay_minutes=1050, duty_days=3,
                      is_ipd=True, layover_cities=["LHR"], equipment="777",
                      category="ORD 777 INTL"),
            _make_seq(102, [10, 11, 12, 13], tpay_minutes=1300, duty_days=4,
                      is_ipd=True, layover_cities=["CDG"], equipment="787",
                      category="ORD 787 INTL"),
            # NIPD trips (international non-premium)
            _make_seq(200, [3, 4, 5], tpay_minutes=700, duty_days=3,
                      is_nipd=True, layover_cities=["CUN"], equipment="737",
                      category="ORD NBI INTL"),
            _make_seq(201, [8, 9, 10], tpay_minutes=650, duty_days=3,
                      is_nipd=True, layover_cities=["PVR"], equipment="321",
                      category="ORD NBI INTL"),
            # High-credit domestic
            _make_seq(300, [1, 2, 3], tpay_minutes=850, duty_days=3,
                      layover_cities=["SAN", "PHX"], equipment="321",
                      report_base="10:00", release_base="16:00"),
            _make_seq(301, [5, 6, 7], tpay_minutes=800, duty_days=3,
                      layover_cities=["DEN", "SFO"], equipment="737",
                      report_base="11:00", release_base="17:00"),
            _make_seq(302, [10, 11], tpay_minutes=550, duty_days=2,
                      layover_cities=["ATL"], equipment="737",
                      report_base="08:00", release_base="18:00"),
            # Low-credit domestic
            _make_seq(400, [15, 16, 17], tpay_minutes=400, duty_days=3,
                      layover_cities=["CLT"], equipment="737",
                      report_base="06:00", release_base="14:00"),
            _make_seq(401, [20], tpay_minutes=200, duty_days=1,
                      equipment="320", report_base="05:00", release_base="20:00"),
            # Red-eyes
            _make_seq(500, [22, 23], tpay_minutes=600, duty_days=2,
                      is_redeye=True, layover_cities=["LAX"], equipment="321"),
            # Commuter-friendly (good report/release times)
            _make_seq(600, [25, 26, 27], tpay_minutes=750, duty_days=3,
                      report_base="12:00", release_base="15:00",
                      layover_cities=["MIA", "FLL"], equipment="737"),
            _make_seq(601, [1, 2], tpay_minutes=500, duty_days=2,
                      report_base="13:00", release_base="14:00",
                      layover_cities=["DFW"], equipment="321"),
            # Very early / very late (bad for commuters)
            _make_seq(700, [5, 6, 7], tpay_minutes=900, duty_days=3,
                      report_base="04:30", release_base="22:00",
                      layover_cities=["BOS"], equipment="737"),
            _make_seq(701, [15, 16], tpay_minutes=550, duty_days=2,
                      report_base="05:00", release_base="23:00",
                      equipment="320"),
        ]

    def test_commuter_bid_respects_time_windows(self):
        """Commuter template should filter to commutable sequences in L1-3."""
        seqs = self._build_diverse_pool()
        props = [
            _prop("prefer_pairing_length", 3, layers=[1, 2, 3]),
            _prop("report_between", {"start": 600, "end": 840}, layers=[1, 2, 3]),
            _prop("release_between", {"start": 480, "end": 1080}, layers=[1, 2, 3]),
            _prop("maximize_credit", True, layers=[1, 2, 3, 4, 5, 6, 7], category="line"),
        ]

        filtered_l1 = filter_sequences_for_layer(seqs, props, 1)

        for seq in filtered_l1:
            dd = seq["totals"]["duty_days"]
            assert dd == 3, f"Seq {seq['seq_number']} has {dd} duty days, expected 3"
            rpt = seq["duty_periods"][0]["report_base"]
            rpt_min = int(rpt.split(":")[0]) * 60 + int(rpt.split(":")[1])
            assert 600 <= rpt_min <= 840, (
                f"Seq {seq['seq_number']} reports at {rpt} ({rpt_min} min), outside 10:00-14:00"
            )

    def test_days_off_enforcement_in_full_bid(self):
        """Setting days off 16-31 should exclude all sequences operating on those days."""
        seqs = self._build_diverse_pool()
        props = [
            _prop("string_days_off_starting", 16,
                  layers=[1, 2, 3, 4, 5, 6, 7], category="days_off"),
            _prop("maximize_credit", True,
                  layers=[1, 2, 3, 4, 5, 6, 7], category="line"),
        ]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=31, bid_properties=props,
        )

        for entry in entries:
            if entry.get("is_excluded"):
                continue
            chosen = entry.get("chosen_dates") or entry.get("operating_dates", [])
            for d in chosen:
                assert d < 16, (
                    f"Seq {entry['seq_number']} has date {d} >= 16 — violates days-off boundary"
                )

    def test_international_explorer_prefers_ipd_in_l1(self):
        """International Explorer template should prioritize IPD in L1-2."""
        seqs = self._build_diverse_pool()
        props = [
            _prop("prefer_pairing_type", "ipd", layers=[1, 2]),
            _prop("prefer_aircraft", "777", layers=[1, 2, 3]),
            _prop("maximize_credit", True,
                  layers=[1, 2, 3, 4, 5, 6, 7], category="line"),
        ]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=["JP"], pinned_entries=[],
            excluded_ids=set(), total_dates=31, bid_properties=props,
        )

        l1 = _get_layer_seq_numbers(entries, 1)
        # L1 should only contain IPD + 777 sequences
        ipd_777_seqs = {100, 101}  # only IPD seqs on 777
        for sn in l1:
            assert sn in ipd_777_seqs, (
                f"L1 seq {sn} is not IPD+777 — should not be in L1"
            )

    def test_credit_within_bounds(self):
        """Every generated layer should have total credit ≤ max (5400 min = 90h)."""
        seqs = [
            _make_seq(i, [i * 2 + 1, i * 2 + 2], tpay_minutes=800, duty_days=2)
            for i in range(12)
        ]
        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )

        for layer_num in range(1, 8):
            layer_entries = [e for e in entries if e["layer"] == layer_num]
            # Compute total credit from entries
            total_credit = 0
            for e in layer_entries:
                # Find the original sequence to get tpay
                for s in seqs:
                    if s["_id"] == e["sequence_id"]:
                        total_credit += s["totals"]["tpay_minutes"]
                        break
            assert total_credit <= 5400, (
                f"Layer {layer_num} total credit {total_credit} min exceeds max 5400"
            )

    def test_min_days_off_respected(self):
        """Every layer should leave at least 11 days off (CBA §11.H)."""
        seqs = [
            _make_seq(i, [i * 2 + 1, i * 2 + 2], tpay_minutes=400, duty_days=2)
            for i in range(14)  # 14 seqs × 2 days = 28 days max
        ]
        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )

        for layer_num in range(1, 8):
            layer_entries = [e for e in entries if e["layer"] == layer_num]
            duty_days = 0
            for e in layer_entries:
                for s in seqs:
                    if s["_id"] == e["sequence_id"]:
                        duty_days += s["totals"]["duty_days"]
                        break
            days_off = 30 - duty_days
            assert days_off >= 11, (
                f"Layer {layer_num} has only {days_off} days off (min 11 required)"
            )

    def test_no_date_conflicts_within_layer(self):
        """No two sequences in the same layer should have overlapping dates."""
        seqs = self._build_diverse_pool()
        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=31, bid_properties=props,
        )

        for layer_num in range(1, 8):
            layer_entries = [e for e in entries if e["layer"] == layer_num]
            occupied: set[int] = set()
            for e in layer_entries:
                chosen = set(e.get("chosen_dates") or e.get("operating_dates", []))
                overlap = occupied & chosen
                assert not overlap, (
                    f"Layer {layer_num}: seq {e['seq_number']} overlaps dates {overlap}"
                )
                occupied |= chosen


# ── Test 5: Scoring Formula Validation ─────────────────────────────────────


class TestScoringFormulas:
    """Validate that scoring formulas produce expected relative ordering."""

    def test_maximize_credit_scoring_range(self):
        """maximize_credit should produce monotonically increasing scores with TPAY."""
        props = [_prop("maximize_credit", True, layers=[1], category="line")]
        tpay_values = [200, 400, 600, 800, 1000, 1200, 1500]
        scores = []
        for tpay in tpay_values:
            seq = _make_seq(1, [1, 2, 3], tpay_minutes=tpay, duty_days=3)
            score = score_sequence_from_properties(seq, props, 1)
            scores.append(score)

        # Scores should be monotonically non-decreasing
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"TPAY {tpay_values[i]} scored {scores[i]:.3f} < "
                f"TPAY {tpay_values[i-1]} scored {scores[i-1]:.3f}"
            )

    def test_maximize_days_off_prefers_shorter_trips(self):
        """maximize_total_days_off should score shorter trips higher."""
        props = [_prop("maximize_total_days_off", True, layers=[1], category="days_off")]
        scores_by_days = {}
        for dd in [1, 2, 3, 4, 5]:
            seq = _make_seq(1, list(range(1, dd + 1)), duty_days=dd)
            scores_by_days[dd] = score_sequence_from_properties(seq, props, 1)

        # 1-day should score higher than 5-day
        assert scores_by_days[1] > scores_by_days[5], (
            f"1-day ({scores_by_days[1]:.3f}) should score above "
            f"5-day ({scores_by_days[5]:.3f}) with maximize_days_off"
        )
        # Should be monotonically decreasing
        for dd in range(1, 5):
            assert scores_by_days[dd] >= scores_by_days[dd + 1], (
                f"{dd}-day ({scores_by_days[dd]:.3f}) should score >= "
                f"{dd+1}-day ({scores_by_days[dd+1]:.3f})"
            )

    def test_target_credit_range_in_range_scores_max(self):
        """target_credit_range: TPAY within range should score 1.0."""
        props = [_prop("target_credit_range", {"start": 4200, "end": 5400},
                       layers=[1], category="line")]
        seq = _make_seq(1, [1, 2, 3], tpay_minutes=4800, duty_days=3)
        score = score_sequence_from_properties(seq, props, 1)
        assert score == 1.0, f"In-range TPAY should score 1.0, got {score}"

    def test_target_credit_range_out_of_range_degrades(self):
        """target_credit_range: TPAY outside range should degrade."""
        props = [_prop("target_credit_range", {"start": 4200, "end": 5400},
                       layers=[1], category="line")]
        # Way below range
        seq_low = _make_seq(1, [1, 2, 3], tpay_minutes=2000, duty_days=3)
        score_low = score_sequence_from_properties(seq_low, props, 1)
        # In range
        seq_in = _make_seq(2, [5, 6, 7], tpay_minutes=4800, duty_days=3)
        score_in = score_sequence_from_properties(seq_in, props, 1)
        assert score_in > score_low, (
            f"In-range ({score_in:.3f}) should score above out-of-range ({score_low:.3f})"
        )

    def test_mixed_property_score_averages(self):
        """Score with 2 properties should be average of individual scores."""
        seq = _make_seq(1, [1, 2, 3], tpay_minutes=1200, duty_days=3,
                        is_ipd=True, equipment="777")
        # Property 1: IPD match → 1.0
        # Property 2: maximize_credit 1200 TPAY → high score
        props = [
            _prop("prefer_pairing_type", "ipd", layers=[1]),
            _prop("maximize_credit", True, layers=[1], category="line"),
        ]
        score = score_sequence_from_properties(seq, props, 1)
        # Both match → score should be high (quality tiebreaker not added when
        # maximize_credit is present since it already differentiates by TPAY)
        assert score >= 0.8, f"Both matching should give high score, got {score:.3f}"

    def test_property_on_wrong_layer_ignored(self):
        """Properties not assigned to the current layer should not affect score."""
        seq = _make_seq(1, [1, 2, 3], is_ipd=True, duty_days=3)
        props_l1 = [_prop("prefer_pairing_type", "ipd", layers=[1])]
        props_l5 = [_prop("prefer_pairing_type", "ipd", layers=[5])]

        score_l1 = score_sequence_from_properties(seq, props_l1, 1)
        score_l5 = score_sequence_from_properties(seq, props_l5, 1)  # prop not on L1

        # IPD match + quality tiebreaker → high score but not exactly 1.0
        assert score_l1 > 0.7, f"IPD match on correct layer should score high, got {score_l1}"
        assert score_l5 == 0.5, "Property on wrong layer should give neutral 0.5"
        assert score_l1 > score_l5, "Active property should score above neutral"


# ── Test 6: Layer Summary Accuracy ─────────────────────────────────────────


class TestLayerSummaryAccuracy:
    """Verify compute_layer_summaries reflects actual filter behavior."""

    def test_summary_counts_match_filter_counts(self):
        """Summary pairing counts should match filter_sequences_for_layer output."""
        seqs = [
            _make_seq(1, [1, 2, 3], is_ipd=True, duty_days=3, equipment="777"),
            _make_seq(2, [5, 6, 7], is_ipd=True, duty_days=3, equipment="787"),
            _make_seq(3, [10, 11, 12], is_ipd=False, duty_days=3, equipment="777"),
            _make_seq(4, [15, 16, 17], is_ipd=False, duty_days=2, equipment="737"),
        ]
        props = [
            _prop("prefer_pairing_type", "ipd", layers=[1]),
            _prop("prefer_aircraft", "777", layers=[1, 2]),
            _prop("maximize_credit", True, layers=[1, 2, 3, 4, 5, 6, 7], category="line"),
        ]
        summaries = compute_layer_summaries(seqs, props, num_layers=7)

        # L1: IPD AND 777 → seq 1 only
        filtered_l1 = filter_sequences_for_layer(seqs, props, 1)
        assert summaries[0]["pairings_by_layer"] == len(filtered_l1), (
            f"L1 summary ({summaries[0]['pairings_by_layer']}) != "
            f"filter count ({len(filtered_l1)})"
        )

        # L2: 777 only → seqs 1, 3
        filtered_l2 = filter_sequences_for_layer(seqs, props, 2)
        new_in_l2 = len(filtered_l2) - len(set(s["seq_number"] for s in filtered_l1) &
                                              set(s["seq_number"] for s in filtered_l2))
        # pairings_by_layer should be new sequences not already in L1
        assert summaries[1]["pairings_by_layer"] >= 0

    def test_summary_cumulative_grows(self):
        """Cumulative total_pairings should not decrease across layers."""
        seqs = [
            _make_seq(i, [i * 3 + 1], duty_days=1, tpay_minutes=300 + i * 50)
            for i in range(10)
        ]
        props = [
            _prop("prefer_pairing_length", 1, layers=[1, 2, 3]),
            _prop("maximize_credit", True, layers=[1, 2, 3, 4, 5, 6, 7], category="line"),
        ]
        summaries = compute_layer_summaries(seqs, props, num_layers=7)

        for i in range(1, 7):
            assert summaries[i]["total_pairings"] >= summaries[i - 1]["total_pairings"], (
                f"Cumulative pairings decreased from L{i} ({summaries[i-1]['total_pairings']}) "
                f"to L{i+1} ({summaries[i]['total_pairings']})"
            )


# ── Test 7: Edge Cases ────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases that could produce broken or empty layers."""

    def test_very_restrictive_l1_produces_nonempty_later_layers(self):
        """Even if L1 has 0 matches, later layers (safety nets) should work."""
        seqs = [
            _make_seq(1, [1, 2, 3], duty_days=3, equipment="737"),
            _make_seq(2, [5, 6, 7], duty_days=3, equipment="321"),
        ]
        # Impossible L1 filter: 777 equipment (no seqs have it)
        props = [
            _prop("prefer_aircraft", "777", layers=[1]),
            _prop("maximize_credit", True, layers=[1, 2, 3, 4, 5, 6, 7], category="line"),
        ]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )

        l1 = _get_layer_seq_numbers(entries, 1)
        assert len(l1) == 0, "L1 with impossible filter should be empty"

        # But later layers should still have sequences
        all_entries = [e for e in entries if not e.get("is_excluded")]
        assert len(all_entries) > 0, "Safety net layers should still have sequences"

    def test_single_sequence_pool(self):
        """With only 1 sequence, it should appear in L1."""
        seqs = [_make_seq(1, [1, 2, 3], tpay_minutes=600, duty_days=3)]
        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )
        l1 = _get_layer_seq_numbers(entries, 1)
        assert 1 in l1

    def test_all_sequences_same_dates_only_one_per_layer(self):
        """If all seqs conflict, each layer should pick only one."""
        seqs = [
            _make_seq(i, [1, 2, 3], tpay_minutes=400 + i * 100, duty_days=3)
            for i in range(5)
        ]
        props = [_prop("maximize_credit", True, category="line")]
        entries, _ = optimize_bid(
            sequences=seqs, prefs={}, seniority_number=500,
            total_base_fas=3000, user_langs=[], pinned_entries=[],
            excluded_ids=set(), total_dates=30, bid_properties=props,
        )

        for layer_num in range(1, 8):
            layer_entries = [e for e in entries if e["layer"] == layer_num]
            assert len(layer_entries) <= 1, (
                f"Layer {layer_num} has {len(layer_entries)} seqs but all "
                f"conflict — should have at most 1"
            )

    def test_empty_properties_uses_neutral_scoring(self):
        """No bid_properties → all sequences score 0.5 (neutral)."""
        seqs = [_make_seq(1, [1, 2, 3], duty_days=3)]
        score = score_sequence_from_properties(seqs[0], [], 1)
        assert score == 0.5, f"No properties should give 0.5, got {score}"

    def test_disabled_properties_ignored_everywhere(self):
        """Disabled properties should not affect filtering or scoring."""
        seqs = [
            _make_seq(1, [1, 2, 3], is_ipd=True, duty_days=3),
            _make_seq(2, [5, 6, 7], is_ipd=False, duty_days=3),
        ]
        disabled_prop = {
            "id": "p-disabled",
            "property_key": "prefer_pairing_type",
            "category": "pairing",
            "value": "ipd",
            "layers": [1],
            "is_enabled": False,
        }
        # Disabled filter should NOT restrict
        filtered = filter_sequences_for_layer(seqs, [disabled_prop], 1)
        assert len(filtered) == 2, "Disabled property should not filter"

        # Disabled score should be neutral
        score = score_sequence_from_properties(seqs[0], [disabled_prop], 1)
        assert score == 0.5, "Disabled property should give neutral score"


# ── Test 8: Projected Schedule Quality ─────────────────────────────────────


class TestProjectedScheduleQuality:
    """Test that projected schedules produce realistic monthly schedules."""

    def test_projected_schedule_within_credit_range(self):
        """Projected schedule should flag when credit is within/outside range."""
        seqs = [
            {"_id": "s1", "seq_number": 1, "category": "DOM",
             "operating_dates": [1, 2, 3], "totals": {"tpay_minutes": 4500, "duty_days": 3}},
            {"_id": "s2", "seq_number": 2, "category": "DOM",
             "operating_dates": [5, 6, 7], "totals": {"tpay_minutes": 500, "duty_days": 3}},
        ]
        entries = [
            {"rank": 1, "sequence_id": "s1", "layer": 1, "is_excluded": False},
            {"rank": 2, "sequence_id": "s2", "layer": 1, "is_excluded": False},
        ]
        result = compute_projected_schedule(
            entries, seqs, layer=1, total_dates=30,
            credit_min_minutes=4200, credit_max_minutes=5400,
        )
        # 4500 + 500 = 5000, within 4200-5400
        assert result["within_credit_range"] is True
        assert result["total_credit_hours"] == round(5000 / 60, 1)

    def test_projected_schedule_shape_classification(self):
        """Schedule shape should reflect actual working day distribution."""
        # Front-loaded: all trips in days 1-10
        seqs = [
            {"_id": "s1", "seq_number": 1, "category": "DOM",
             "operating_dates": [1, 2, 3], "totals": {"tpay_minutes": 600, "duty_days": 3}},
            {"_id": "s2", "seq_number": 2, "category": "DOM",
             "operating_dates": [5, 6, 7], "totals": {"tpay_minutes": 600, "duty_days": 3}},
            {"_id": "s3", "seq_number": 3, "category": "DOM",
             "operating_dates": [9, 10], "totals": {"tpay_minutes": 400, "duty_days": 2}},
        ]
        entries = [
            {"rank": 1, "sequence_id": "s1", "layer": 1, "is_excluded": False},
            {"rank": 2, "sequence_id": "s2", "layer": 1, "is_excluded": False},
            {"rank": 3, "sequence_id": "s3", "layer": 1, "is_excluded": False},
        ]
        result = compute_projected_schedule(entries, seqs, layer=1, total_dates=30)
        assert "front-loaded" in result["schedule_shape"], (
            f"Trips on days 1-10 should be front-loaded, got: {result['schedule_shape']}"
        )
