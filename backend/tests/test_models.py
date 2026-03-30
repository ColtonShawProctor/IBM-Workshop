from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    RegisterRequest,
    LoginRequest,
    User,
    Profile,
    Preferences,
    PreferenceWeights,
    BidPeriod,
    Sequence,
    SequenceTotals,
    Bid,
    BidEntry,
    BidSummary,
    DateCoverage,
    Bookmark,
    FilterPreset,
    FilterSet,
    AwardedSchedule,
    AwardAnalysis,
    ErrorResponse,
    ProfileInput,
    SequenceInput,
    DutyPeriodInput,
    LegInput,
    CreateBidRequest,
    UpdateBidRequest,
    CBAViolation,
    CBAValidationResult,
    CreditHourSummary,
    DaysOffSummary,
    PROPERTY_DEFINITIONS,
    FAVORITE_PROPERTIES,
    VALID_VALUE_TYPES,
    NUM_LAYERS,
    BidProperty,
    BidPropertyInput,
    LayerSummary,
)


def test_register_request_validates_email():
    with pytest.raises(ValidationError):
        RegisterRequest(email="bad", password="12345678", profile=_profile())


def test_register_request_validates_password_length():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.com", password="short", profile=_profile())


def test_register_request_valid():
    r = RegisterRequest(email="a@b.com", password="12345678", profile=_profile())
    assert r.email == "a@b.com"


def test_preference_weights_bounds():
    with pytest.raises(ValidationError):
        PreferenceWeights(days_off=0)
    with pytest.raises(ValidationError):
        PreferenceWeights(tpay=11)
    w = PreferenceWeights()
    assert w.days_off == 5


def test_user_defaults():
    u = User(id="u1", email="a@b.com")
    assert u.default_preferences.weights.days_off == 5
    assert u.profile.language_qualifications == []


def test_bid_period_defaults():
    bp = BidPeriod(id="bp1", name="Jan", effective_start="2026-01-01", effective_end="2026-01-30")
    assert bp.parse_status == "pending"
    assert bp.total_sequences == 0


def test_sequence_totals():
    t = SequenceTotals(block_minutes=600, tpay_minutes=700, tafb_minutes=3000, duty_days=4, leg_count=8)
    assert t.block_minutes == 600


def test_bid_entry_defaults():
    e = BidEntry(rank=1, sequence_id="s1")
    assert e.is_pinned is False
    assert e.attainability == "unknown"


def test_date_coverage():
    dc = DateCoverage(covered_dates=[1, 2, 3], uncovered_dates=[4, 5], coverage_rate=0.6)
    assert dc.coverage_rate == 0.6


def test_bid_summary():
    s = BidSummary()
    assert s.total_entries == 0
    assert s.conflict_groups == 0


def test_bid_full():
    b = Bid(id="b1", bid_period_id="bp1", name="My bid")
    assert b.status == "draft"
    assert b.entries == []


def test_bookmark():
    bk = Bookmark(id="bk1", sequence_id="s1", seq_number=663)
    assert bk.seq_number == 663


def test_filter_preset():
    fp = FilterPreset(id="fp1", name="Intl only", filters=FilterSet(categories=["777 INTL"]))
    assert fp.filters.categories == ["777 INTL"]


def test_awarded_schedule():
    a = AwardedSchedule(id="a1", bid_period_id="bp1")
    assert a.awarded_sequences == []


def test_award_analysis():
    aa = AwardAnalysis(bid_id="b1", awarded_schedule_id="a1", match_count=5, match_rate=0.5)
    assert aa.top_10_match_count == 0


def test_error_response():
    e = ErrorResponse(code="NOT_FOUND", message="nope")
    assert e.details == {}


def test_sequence_input():
    si = SequenceInput(
        seq_number=100,
        operating_dates=[1, 2, 3],
        duty_periods=[
            DutyPeriodInput(
                dp_number=1,
                report_local="05:00",
                report_base="05:00",
                release_local="15:00",
                release_base="15:00",
                legs=[
                    LegInput(
                        flight_number="100",
                        equipment="777",
                        departure_station="ORD",
                        departure_local="06:00",
                        departure_base="06:00",
                        arrival_station="NRT",
                        arrival_local="10:00",
                        arrival_base="19:00",
                        block_minutes=780,
                    )
                ],
            )
        ],
    )
    assert si.seq_number == 100


def test_profile_cba_fields_with_all_set():
    """Task 53: Profile with all 4 CBA fields set."""
    p = Profile(
        display_name="Test",
        base_city="ORD",
        seniority_number=500,
        total_base_fas=3000,
        position_min=1,
        position_max=4,
        years_of_service=5,
        is_reserve=True,
        is_purser_qualified=True,
        line_option="high",
    )
    assert p.years_of_service == 5
    assert p.is_reserve is True
    assert p.is_purser_qualified is True
    assert p.line_option == "high"


def test_profile_cba_fields_defaults():
    """Task 53: CBA field defaults."""
    p = Profile()
    assert p.years_of_service is None
    assert p.is_reserve is False
    assert p.is_purser_qualified is False
    assert p.line_option == "standard"


def test_profile_invalid_line_option():
    """Task 53: Invalid line_option rejected."""
    with pytest.raises(ValidationError):
        Profile(line_option="invalid")


def test_profile_input_cba_fields():
    """Task 53: ProfileInput with CBA fields."""
    p = ProfileInput(
        display_name="Test",
        base_city="ORD",
        seniority_number=500,
        total_base_fas=3000,
        position_min=1,
        position_max=4,
        years_of_service=10,
        is_reserve=False,
        is_purser_qualified=True,
        line_option="low",
    )
    assert p.years_of_service == 10
    assert p.line_option == "low"


def test_profile_input_invalid_line_option():
    """Task 53: ProfileInput rejects invalid line_option."""
    with pytest.raises(ValidationError):
        ProfileInput(
            display_name="Test",
            base_city="ORD",
            seniority_number=500,
            total_base_fas=3000,
            position_min=1,
            position_max=4,
            line_option="ultra",
        )


# ── Task 55: Sequence CBA classification fields ─────────────────────────────


def test_sequence_cba_fields_set():
    """Task 55: Sequence with all 6 CBA fields set."""
    s = Sequence(
        id="s1",
        bid_period_id="bp1",
        seq_number=100,
        is_odan=True,
        international_duty_type="long_range",
        is_ipd=True,
        is_nipd=False,
        has_holiday=True,
        is_speaker_sequence=True,
    )
    assert s.is_odan is True
    assert s.international_duty_type == "long_range"
    assert s.is_ipd is True
    assert s.is_nipd is False
    assert s.has_holiday is True
    assert s.is_speaker_sequence is True


def test_sequence_cba_fields_defaults():
    """Task 55: CBA field defaults are all False/None."""
    s = Sequence(id="s1", bid_period_id="bp1", seq_number=100)
    assert s.is_odan is False
    assert s.international_duty_type is None
    assert s.is_ipd is False
    assert s.is_nipd is False
    assert s.has_holiday is False
    assert s.is_speaker_sequence is False


def test_sequence_invalid_intl_duty_type():
    """Task 55: Invalid international_duty_type rejected."""
    with pytest.raises(ValidationError):
        Sequence(
            id="s1",
            bid_period_id="bp1",
            seq_number=100,
            international_duty_type="invalid_type",
        )


# ── Task 56: SequenceTotals pay/rig fields ───────────────────────────────────


def test_sequence_totals_rig_fields():
    """Task 56: SequenceTotals with rig and pay fields."""
    t = SequenceTotals(
        block_minutes=600,
        duty_rig_minutes=300,
        trip_rig_minutes=400,
        estimated_pay_cents=50000,
    )
    assert t.duty_rig_minutes == 300
    assert t.trip_rig_minutes == 400
    assert t.estimated_pay_cents == 50000


def test_sequence_totals_rig_defaults():
    """Task 56: Rig/pay fields default to 0."""
    t = SequenceTotals()
    assert t.duty_rig_minutes == 0
    assert t.trip_rig_minutes == 0
    assert t.estimated_pay_cents == 0


# ── Task 57: BidSummary CBA fields ──────────────────────────────────────────


def test_bid_summary_cba_fields():
    """Task 57: BidSummary with CBA fields."""
    s = BidSummary(
        total_credit_hours=82.5,
        line_option="high",
        line_min_hours=70,
        line_max_hours=110,
        credit_hour_utilization=0.75,
        estimated_total_pay_cents=1200000,
        cba_violations=["7-day block limit exceeded"],
    )
    assert s.total_credit_hours == 82.5
    assert s.line_option == "high"
    assert s.line_max_hours == 110
    assert len(s.cba_violations) == 1


def test_bid_summary_cba_defaults():
    """Task 57: CBA field defaults."""
    s = BidSummary()
    assert s.total_credit_hours == 0.0
    assert s.line_option == "standard"
    assert s.line_min_hours == 70
    assert s.line_max_hours == 90
    assert s.credit_hour_utilization == 0.0
    assert s.estimated_total_pay_cents == 0
    assert s.cba_violations == []


# ── Task 58: CBA Validation models ──────────────────────────────────────────


def test_cba_validation_result_no_violations():
    """Task 58: Valid result with 0 violations."""
    r = CBAValidationResult()
    assert r.is_valid is True
    assert r.violations == []


def test_cba_validation_result_with_violations():
    """Task 58: Result with 2 violations serializes correctly."""
    v1 = CBAViolation(
        rule="CBA §11.B",
        severity="error",
        message="7-day block limit exceeded",
        affected_dates=[12, 13, 14, 15, 16, 17, 18],
        affected_sequences=[100, 101, 102],
    )
    v2 = CBAViolation(
        rule="CBA §11.H",
        severity="warning",
        message="Only 9 days off, minimum is 11",
        affected_dates=[],
        affected_sequences=[],
    )
    r = CBAValidationResult(
        is_valid=False,
        violations=[v1, v2],
        credit_hour_summary=CreditHourSummary(
            estimated_credit_hours=85.0, line_min=70, line_max=90, within_range=True
        ),
        days_off_summary=DaysOffSummary(
            total_days_off=9, minimum_required=11, meets_requirement=False
        ),
    )
    assert r.is_valid is False
    assert len(r.violations) == 2
    assert r.violations[0].rule == "CBA §11.B"
    assert r.days_off_summary.meets_requirement is False
    data = r.model_dump()
    assert data["violations"][1]["severity"] == "warning"


def test_cba_violation_invalid_severity():
    """Task 58: Severity must be error or warning."""
    with pytest.raises(ValidationError):
        CBAViolation(rule="CBA §11.B", severity="info", message="test")


# ── Task 91: PBS property constants ──────────────────────────────────────────


def test_property_definitions_count():
    """Task 91: 64 properties in the catalog (63 bidding + 1 search-only pairing_id)."""
    assert len(PROPERTY_DEFINITIONS) == 64


def test_property_definitions_required_keys():
    """Task 91: Each entry has category, label, value_type."""
    for key, defn in PROPERTY_DEFINITIONS.items():
        assert "category" in defn, f"{key} missing category"
        assert "label" in defn, f"{key} missing label"
        assert "value_type" in defn, f"{key} missing value_type"


def test_property_category_counts():
    """Task 91: 7 days_off, 18 line, 35 pairing (incl search), 4 reserve."""
    cats = {}
    for defn in PROPERTY_DEFINITIONS.values():
        c = defn["category"]
        cats[c] = cats.get(c, 0) + 1
    assert cats["days_off"] == 7
    assert cats["line"] == 18
    assert cats["pairing"] == 35  # 34 filter + 1 search-only (pairing_id)
    assert cats["reserve"] == 4


def test_property_value_types_valid():
    """Task 91: All value_type values are in VALID_VALUE_TYPES."""
    for key, defn in PROPERTY_DEFINITIONS.items():
        assert defn["value_type"] in VALID_VALUE_TYPES, f"{key} has invalid value_type: {defn['value_type']}"


def test_valid_value_types_count():
    """Task 91: 18 distinct value types."""
    assert len(VALID_VALUE_TYPES) == 18


def test_favorite_properties_count():
    """Task 91: 6 favorites (5 pairing + 1 line)."""
    assert len(FAVORITE_PROPERTIES) == 6
    # All favorites must exist in definitions
    for fav in FAVORITE_PROPERTIES:
        assert fav in PROPERTY_DEFINITIONS, f"Favorite {fav} not in PROPERTY_DEFINITIONS"


def test_num_layers():
    """Task 91: NUM_LAYERS is 7."""
    assert NUM_LAYERS == 7


# ── Task 92: BidProperty models ──────────────────────────────────────────────


def test_bid_property_valid():
    """Task 92: BidProperty with valid category and layers."""
    p = BidProperty(
        id="p1",
        property_key="report_between",
        category="pairing",
        value={"start": 300, "end": 480},
        layers=[1, 2, 3],
        is_enabled=True,
    )
    assert p.property_key == "report_between"
    assert p.layers == [1, 2, 3]


def test_bid_property_invalid_category():
    """Task 92: Invalid category rejected."""
    with pytest.raises(ValidationError):
        BidProperty(
            id="p1",
            property_key="report_between",
            category="invalid",
            layers=[1],
        )


def test_bid_property_layer_out_of_range():
    """Task 92: Layer 0 and 8 rejected."""
    with pytest.raises(ValidationError):
        BidProperty(
            id="p1",
            property_key="report_between",
            category="pairing",
            layers=[0],
        )
    with pytest.raises(ValidationError):
        BidProperty(
            id="p1",
            property_key="report_between",
            category="pairing",
            layers=[8],
        )


def test_bid_property_invalid_key():
    """Task 92: Unknown property_key rejected."""
    with pytest.raises(ValidationError):
        BidProperty(
            id="p1",
            property_key="nonexistent_prop",
            category="pairing",
            layers=[1],
        )


def test_bid_property_input_valid():
    """Task 92: BidPropertyInput constructs OK."""
    inp = BidPropertyInput(
        property_key="prefer_pairing_type",
        value="ipd",
        layers=[1, 2],
    )
    assert inp.property_key == "prefer_pairing_type"


def test_layer_summary():
    """Task 92: LayerSummary constructs with defaults."""
    ls = LayerSummary(layer_number=1)
    assert ls.total_pairings == 0
    assert ls.pairings_by_layer == 0


def test_bid_with_properties():
    """Task 92: Bid model includes properties field."""
    b = Bid(id="b1", bid_period_id="bp1", name="Test Bid")
    assert b.properties == []

    prop = BidProperty(
        id="p1",
        property_key="prefer_aircraft",
        category="pairing",
        value="777",
        layers=[1],
    )
    b2 = Bid(
        id="b2",
        bid_period_id="bp1",
        name="With Props",
        properties=[prop],
    )
    assert len(b2.properties) == 1
    assert b2.properties[0].property_key == "prefer_aircraft"


def _profile():
    return ProfileInput(
        display_name="Test",
        base_city="ORD",
        seniority_number=500,
        total_base_fas=3000,
        position_min=1,
        position_max=4,
    )
