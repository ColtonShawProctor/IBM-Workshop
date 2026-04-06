from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, EmailStr, field_validator


def _sanitize_str(v: str) -> str:
    """Strip HTML tags and null bytes from user-provided strings."""
    v = re.sub(r"\x00", "", v)
    v = re.sub(r"<[^>]+>", "", v)
    return v


# ── Error ───────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


# ── Auth ────────────────────────────────────────────────────────────────────

VALID_LINE_OPTIONS = {"standard", "high", "low"}
VALID_INTL_DUTY_TYPES = {"non_long_range", "mid_range", "long_range", "extended_long_range"}

# ── PBS Constants ──────────────────────────────────────────────────────────

NUM_LAYERS = 7

VALID_PROPERTY_CATEGORIES = {"days_off", "line", "pairing", "reserve"}

VALID_PAIRING_TYPES = {
    "regular", "nipd", "ipd", "premium_transcon", "odan", "redeye", "satellite",
}

VALID_EQUIPMENT_CODES = {
    "320", "321", "A21", "737", "38K", "38M", "777", "77W", "787", "788", "789", "78P",
}

VALID_VALUE_TYPES = {
    "toggle", "integer", "decimal", "time", "time_range", "int_range",
    "date", "date_range", "pairing_type", "equipment", "airport",
    "airport_date", "days_of_week", "position_list", "text", "selection",
    "time_range_date", "int_date",
}

FAVORITE_PROPERTIES = {
    "target_credit_range",        # line
    "report_between",             # pairing
    "release_between",            # pairing
    "prefer_pairing_type",        # pairing
    "co_terminal_satellite_airport",  # pairing
    "prefer_positions_order",     # pairing
}

# Full catalog of all 63 PBS properties matching AA PBS at fapbs.aa.com
# Each entry: category, label, value_type
PROPERTY_DEFINITIONS: dict[str, dict] = {
    # ── Days Off (7) ──────────────────────────────────────────────────────
    "maximize_total_days_off":          {"category": "days_off", "label": "Maximize Total Days Off", "value_type": "toggle"},
    "minimize_days_off_between_blocks": {"category": "days_off", "label": "Minimize Days Off between Work Blocks", "value_type": "integer"},
    "maximize_weekend_days_off":        {"category": "days_off", "label": "Maximize Weekend Days Off", "value_type": "toggle"},
    "maximize_block_of_days_off":       {"category": "days_off", "label": "Maximize Block of Days Off", "value_type": "toggle"},
    "string_days_off_starting":         {"category": "days_off", "label": "String of Days Off Starting on Date", "value_type": "date"},
    "string_days_off_ending":           {"category": "days_off", "label": "String of Days Off Ending on Date", "value_type": "date"},
    "waive_minimum_days_off":           {"category": "days_off", "label": "Waive Minimum Days Off", "value_type": "toggle"},
    # ── Line (18) ─────────────────────────────────────────────────────────
    "target_credit_range":              {"category": "line", "label": "Target Credit Range", "value_type": "time_range"},
    "maximize_credit":                  {"category": "line", "label": "Maximize Credit", "value_type": "toggle"},
    "work_block_size":                  {"category": "line", "label": "Work Block Size", "value_type": "int_range"},
    "prefer_cadence_day_of_week":       {"category": "line", "label": "Prefer Cadence on Day-of-Week", "value_type": "days_of_week"},
    "commutable_work_block":            {"category": "line", "label": "Commutable Work Block", "value_type": "toggle"},
    "pairing_mix_in_work_block":        {"category": "line", "label": "Pairing Mix in a Work Block", "value_type": "selection"},
    "allow_double_up_on_date":          {"category": "line", "label": "Allow Double-Up on Date", "value_type": "date"},
    "allow_double_up_by_range":         {"category": "line", "label": "Allow Double-Up by Range", "value_type": "date_range"},
    "allow_multiple_pairings":          {"category": "line", "label": "Allow Multiple Pairings", "value_type": "toggle"},
    "allow_multiple_pairings_on_date":  {"category": "line", "label": "Allow Multiple Pairings on Date", "value_type": "date"},
    "allow_co_terminal_mix":            {"category": "line", "label": "Allow Co-Terminal Mix in Work Block", "value_type": "toggle"},
    "clear_bids":                       {"category": "line", "label": "Clear Bids", "value_type": "toggle"},
    "waive_carry_over_credit":          {"category": "line", "label": "Waive Carry-Over Credit", "value_type": "toggle"},
    "avoid_person":                     {"category": "line", "label": "Avoid Person", "value_type": "text"},
    "buddy_with":                       {"category": "line", "label": "Buddy With", "value_type": "text"},
    "waive_24hrs_rest_in_domicile":     {"category": "line", "label": "Waive 24 hrs rest in Domicile", "value_type": "toggle"},
    "waive_30hrs_in_7_days":            {"category": "line", "label": "Waive 30 hrs in 7 Days", "value_type": "toggle"},
    "waive_minimum_domicile_rest":      {"category": "line", "label": "Waive Minimum Domicile Rest", "value_type": "toggle"},
    # ── Pairing (34 + 1 search-only = 35) ─────────────────────────────────
    "report_between":                   {"category": "pairing", "label": "Report Between", "value_type": "time_range"},
    "release_between":                  {"category": "pairing", "label": "Release Between", "value_type": "time_range"},
    "prefer_pairing_type":              {"category": "pairing", "label": "Prefer Pairing Type", "value_type": "pairing_type"},
    "co_terminal_satellite_airport":    {"category": "pairing", "label": "Co-Terminal/Satellite Airport", "value_type": "airport"},
    "prefer_positions_order":           {"category": "pairing", "label": "Prefer Positions Order", "value_type": "position_list"},
    "prefer_pairing_length":            {"category": "pairing", "label": "Prefer Pairing Length", "value_type": "integer"},
    "prefer_pairing_length_on_date":    {"category": "pairing", "label": "Prefer Pairing Length on Date", "value_type": "int_date"},
    "prefer_duty_period":               {"category": "pairing", "label": "Prefer Duty Period", "value_type": "integer"},
    "report_between_on_date":           {"category": "pairing", "label": "Report Between on Date", "value_type": "time_range_date"},
    "release_between_on_date":          {"category": "pairing", "label": "Release Between on Date", "value_type": "time_range_date"},
    "mid_pairing_report_after":         {"category": "pairing", "label": "Mid-Pairing Report After", "value_type": "time"},
    "mid_pairing_release_before":       {"category": "pairing", "label": "Mid-Pairing Release Before", "value_type": "time"},
    "max_tafb_credit_ratio":            {"category": "pairing", "label": "Maximum TAFB-credit ratio", "value_type": "decimal"},
    "min_avg_credit_per_duty":          {"category": "pairing", "label": "Minimum Avg Credit per Duty", "value_type": "time"},
    "max_duty_time_per_duty":           {"category": "pairing", "label": "Maximum Duty Time per Duty", "value_type": "time"},
    "max_block_per_duty":               {"category": "pairing", "label": "Maximum Block per Duty", "value_type": "time"},
    "min_connection_time":              {"category": "pairing", "label": "Minimum Connection Time", "value_type": "time"},
    "max_connection_time":              {"category": "pairing", "label": "Maximum Connection Time", "value_type": "time"},
    "prefer_deadheads":                 {"category": "pairing", "label": "Prefer Deadheads", "value_type": "toggle"},
    "avoid_deadheads":                  {"category": "pairing", "label": "Avoid Deadheads", "value_type": "toggle"},
    "layover_at_city":                  {"category": "pairing", "label": "Layover at City", "value_type": "airport"},
    "avoid_layover_at_city":            {"category": "pairing", "label": "Avoid Layover at City", "value_type": "airport"},
    "layover_at_city_on_date":          {"category": "pairing", "label": "Layover at City on Date", "value_type": "airport_date"},
    "min_layover_time":                 {"category": "pairing", "label": "Minimum Layover Time", "value_type": "integer"},
    "max_layover_time":                 {"category": "pairing", "label": "Maximum Layover Time", "value_type": "integer"},
    "prefer_landing_at_city":           {"category": "pairing", "label": "Prefer Landing at City", "value_type": "airport"},
    "avoid_landing_at_city":            {"category": "pairing", "label": "Avoid Landing at City", "value_type": "airport"},
    "prefer_one_landing_first_duty":    {"category": "pairing", "label": "Prefer One Landing on First Duty", "value_type": "toggle"},
    "prefer_one_landing_last_duty":     {"category": "pairing", "label": "Prefer One Landing on Last Duty", "value_type": "toggle"},
    "max_landings_per_duty":            {"category": "pairing", "label": "Maximum Landing per Duty", "value_type": "integer"},
    "prefer_aircraft":                  {"category": "pairing", "label": "Prefer Aircraft", "value_type": "equipment"},
    "avoid_aircraft":                   {"category": "pairing", "label": "Avoid Aircraft", "value_type": "equipment"},
    "prefer_language":                  {"category": "pairing", "label": "Prefer Language", "value_type": "text"},
    "prefer_positions_order_per_aircraft": {"category": "pairing", "label": "Prefer Positions Order per Aircraft", "value_type": "text"},
    "pairing_id":                       {"category": "pairing", "label": "Pairing ID", "value_type": "text"},
    # ── Reserve (4) ───────────────────────────────────────────────────────
    "waive_carryover_days_off":         {"category": "reserve", "label": "Waive Carryover Days Off", "value_type": "toggle"},
    "block_of_reserve_days_off":        {"category": "reserve", "label": "Block of Reserve Days Off", "value_type": "integer"},
    "reserve_day_of_week_off":          {"category": "reserve", "label": "Reserve Day of Week Off", "value_type": "days_of_week"},
    "reserve_work_block_size":          {"category": "reserve", "label": "Reserve Work Block Size", "value_type": "int_range"},
}


class ProfileInput(BaseModel):
    display_name: str
    base_city: str
    commute_from: Optional[str] = None  # IATA code of city FA commutes from (e.g. DEN)
    seniority_number: Optional[int] = None
    total_base_fas: Optional[int] = None
    seniority_percentage: Optional[float] = None  # 0.0-100.0, from PBS portal
    position_min: int

    @field_validator("display_name", "base_city", mode="before")
    @classmethod
    def sanitize_strings(cls, v: str) -> str:
        return _sanitize_str(v) if isinstance(v, str) else v
    position_max: int
    language_qualifications: List[str] = Field(default_factory=list)
    years_of_service: Optional[int] = None
    is_reserve: bool = False
    is_purser_qualified: bool = False
    line_option: str = "standard"

    @field_validator("line_option", mode="before")
    @classmethod
    def validate_line_option(cls, v: str) -> str:
        if v not in VALID_LINE_OPTIONS:
            raise ValueError(f"line_option must be one of {VALID_LINE_OPTIONS}")
        return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    profile: ProfileInput


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Profile(BaseModel):
    display_name: Optional[str] = None
    base_city: Optional[str] = None
    commute_from: Optional[str] = None  # IATA code of city FA commutes from
    seniority_number: Optional[int] = None
    total_base_fas: Optional[int] = None
    seniority_percentage: Optional[float] = None  # 0.0-100.0, from PBS portal
    position_min: Optional[int] = None
    position_max: Optional[int] = None
    language_qualifications: List[str] = Field(default_factory=list)
    years_of_service: Optional[int] = None
    is_reserve: bool = False
    is_purser_qualified: bool = False
    line_option: str = "standard"

    @field_validator("line_option", mode="before")
    @classmethod
    def validate_line_option(cls, v: str) -> str:
        if v not in VALID_LINE_OPTIONS:
            raise ValueError(f"line_option must be one of {VALID_LINE_OPTIONS}")
        return v


class PreferenceWeights(BaseModel):
    days_off: int = Field(default=5, ge=1, le=10)
    tpay: int = Field(default=5, ge=1, le=10)
    layover_city: int = Field(default=5, ge=1, le=10)
    equipment: int = Field(default=5, ge=1, le=10)
    report_time: int = Field(default=5, ge=1, le=10)
    release_time: int = Field(default=5, ge=1, le=10)
    redeye: int = Field(default=5, ge=1, le=10)
    trip_length: int = Field(default=5, ge=1, le=10)
    clustering: int = Field(default=5, ge=1, le=10)


class Preferences(BaseModel):
    preferred_days_off: List[int] = Field(default_factory=list)
    preferred_layover_cities: List[str] = Field(default_factory=list)
    avoided_layover_cities: List[str] = Field(default_factory=list)
    tpay_min_minutes: Optional[int] = None
    tpay_max_minutes: Optional[int] = None
    preferred_equipment: List[str] = Field(default_factory=list)
    report_earliest_minutes: Optional[int] = None
    report_latest_minutes: Optional[int] = None
    release_earliest_minutes: Optional[int] = None
    release_latest_minutes: Optional[int] = None
    avoid_redeyes: bool = False
    prefer_turns: Optional[bool] = None
    prefer_high_ops: Optional[bool] = None
    cluster_trips: bool = False
    weights: PreferenceWeights = Field(default_factory=PreferenceWeights)


class User(BaseModel):
    id: str
    email: str
    profile: Profile = Field(default_factory=Profile)
    default_preferences: Preferences = Field(default_factory=Preferences)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: User


class UpdateUserRequest(BaseModel):
    profile: Optional[ProfileInput] = None
    default_preferences: Optional[Preferences] = None


# ── Bid Period ──────────────────────────────────────────────────────────────

class BidPeriod(BaseModel):
    id: str
    name: str
    effective_start: date
    effective_end: date
    base_city: Optional[str] = None
    source_filename: Optional[str] = None
    parse_status: str = "pending"
    parse_error: Optional[str] = None
    total_sequences: int = 0
    total_dates: int = 0
    categories: List[str] = Field(default_factory=list)
    issued_date: Optional[date] = None
    target_credit_min_minutes: int = 4200    # 70:00 default (CBA §2.EE standard min)
    target_credit_max_minutes: int = 5400    # 90:00 default (CBA §2.EE standard max)
    preference_overrides: Optional[Preferences] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BidPeriodList(BaseModel):
    data: List[BidPeriod]
    page_state: Optional[str] = None


# ── Sequence ────────────────────────────────────────────────────────────────

class Layover(BaseModel):
    city: Optional[str] = None
    hotel_name: Optional[str] = None
    hotel_phone: Optional[str] = None
    transport_company: Optional[str] = None
    transport_phone: Optional[str] = None
    rest_minutes: Optional[int] = None


class LayoverInput(BaseModel):
    city: Optional[str] = None
    hotel_name: Optional[str] = None
    hotel_phone: Optional[str] = None
    transport_company: Optional[str] = None
    transport_phone: Optional[str] = None
    rest_minutes: Optional[int] = None


class Leg(BaseModel):
    leg_index: int
    flight_number: str
    is_deadhead: bool = False
    equipment: str
    departure_station: str
    departure_local: str
    departure_base: str
    meal_code: Optional[str] = None
    arrival_station: str
    arrival_local: str
    arrival_base: str
    pax_service: Optional[str] = None
    block_minutes: int
    ground_minutes: Optional[int] = None
    is_connection: bool = False


class LegInput(BaseModel):
    flight_number: str
    is_deadhead: bool = False
    equipment: str
    departure_station: str
    departure_local: str
    departure_base: str
    meal_code: Optional[str] = None
    arrival_station: str
    arrival_local: str
    arrival_base: str
    pax_service: Optional[str] = None
    block_minutes: int
    ground_minutes: Optional[int] = None
    is_connection: bool = False


class DutyPeriod(BaseModel):
    dp_number: int
    day_of_seq: Optional[int] = None
    day_of_seq_total: Optional[int] = None
    report_local: str
    report_base: str
    release_local: str
    release_base: str
    duty_minutes: Optional[int] = None
    legs: List[Leg] = Field(default_factory=list)
    layover: Optional[Layover] = None


class DutyPeriodInput(BaseModel):
    dp_number: int
    day_of_seq: Optional[int] = None
    day_of_seq_total: Optional[int] = None
    report_local: str
    report_base: str
    release_local: str
    release_base: str
    legs: List[LegInput] = Field(default_factory=list)
    layover: Optional[LayoverInput] = None


class SequenceTotals(BaseModel):
    block_minutes: int = 0
    synth_minutes: int = 0
    tpay_minutes: int = 0
    tafb_minutes: int = 0
    duty_days: int = 0
    leg_count: int = 0
    deadhead_count: int = 0
    duty_rig_minutes: int = 0
    trip_rig_minutes: int = 0
    estimated_pay_cents: int = 0


class CommuteImpact(BaseModel):
    first_day_feasible: bool = True
    first_day_note: str = ""
    last_day_feasible: bool = True
    last_day_note: str = ""
    hotel_nights_needed: int = 0
    impact_level: str = "green"


class Sequence(BaseModel):
    id: str
    bid_period_id: str
    seq_number: int
    category: Optional[str] = None
    ops_count: int = 1
    position_min: int = 1
    position_max: int = 9
    language: Optional[str] = None
    language_count: Optional[int] = None
    operating_dates: List[int] = Field(default_factory=list)
    is_turn: bool = False
    has_deadhead: bool = False
    is_redeye: bool = False
    is_odan: bool = False
    international_duty_type: Optional[str] = None
    is_ipd: bool = False
    is_nipd: bool = False
    has_holiday: bool = False
    is_speaker_sequence: bool = False
    totals: SequenceTotals = Field(default_factory=SequenceTotals)

    @field_validator("international_duty_type", mode="before")
    @classmethod
    def validate_intl_duty_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_INTL_DUTY_TYPES:
            raise ValueError(f"international_duty_type must be one of {VALID_INTL_DUTY_TYPES}")
        return v
    layover_cities: List[str] = Field(default_factory=list)
    duty_periods: List[DutyPeriod] = Field(default_factory=list)
    source: str = "parsed"
    eligibility: Optional[str] = None
    commute_impact: Optional[CommuteImpact] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SequenceInput(BaseModel):
    seq_number: int
    category: Optional[str] = None
    ops_count: int = 1
    position_min: int = 1
    position_max: int = 9
    language: Optional[str] = None
    language_count: Optional[int] = None
    operating_dates: List[int]
    duty_periods: List[DutyPeriodInput]


class SequenceList(BaseModel):
    data: List[Sequence]
    page_state: Optional[str] = None
    total_count: int = 0


class SequenceComparison(BaseModel):
    sequences: List[Sequence]
    differences: List[dict[str, Any]] = Field(default_factory=list)


# ── Bid ─────────────────────────────────────────────────────────────────────

class BidEntry(BaseModel):
    rank: int
    sequence_id: str
    seq_number: int = 0
    is_pinned: bool = False
    is_excluded: bool = False
    rationale: Optional[str] = None
    preference_score: float = 0.0
    attainability: str = "unknown"
    date_conflict_group: Optional[str] = None
    layer: int = 0
    commute_impact: Optional[CommuteImpact] = None


class DateCoverage(BaseModel):
    covered_dates: List[int] = Field(default_factory=list)
    uncovered_dates: List[int] = Field(default_factory=list)
    coverage_rate: float = 0.0


class BidSummary(BaseModel):
    total_entries: int = 0
    total_tpay_minutes: int = 0
    total_block_minutes: int = 0
    total_tafb_minutes: int = 0
    total_days_off: int = 0
    sequence_count: int = 0
    leg_count: int = 0
    deadhead_count: int = 0
    international_count: int = 0
    domestic_count: int = 0
    layover_cities: List[str] = Field(default_factory=list)
    date_coverage: DateCoverage = Field(default_factory=DateCoverage)
    conflict_groups: int = 0
    total_credit_hours: float = 0.0
    line_option: str = "standard"
    line_min_hours: int = 70
    line_max_hours: int = 90
    credit_hour_utilization: float = 0.0
    estimated_total_pay_cents: int = 0
    cba_violations: List[str] = Field(default_factory=list)
    commute_warnings: List[str] = Field(default_factory=list)


class OptimizationConfig(BaseModel):
    preferences_used: Optional[Preferences] = None
    seniority_number: Optional[int] = None
    total_base_fas: Optional[int] = None
    pinned_ids: List[str] = Field(default_factory=list)
    excluded_ids: List[str] = Field(default_factory=list)


# ── PBS Bid Properties ─────────────────────────────────────────────────────


class BidProperty(BaseModel):
    id: str
    property_key: str
    category: str
    value: Any = None
    layers: List[int] = Field(default_factory=lambda: [1])
    is_enabled: bool = True

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_PROPERTY_CATEGORIES:
            raise ValueError(f"category must be one of {VALID_PROPERTY_CATEGORIES}")
        return v

    @field_validator("layers", mode="before")
    @classmethod
    def validate_layers(cls, v: List[int]) -> List[int]:
        for layer in v:
            if not (1 <= layer <= NUM_LAYERS):
                raise ValueError(f"Each layer must be between 1 and {NUM_LAYERS}, got {layer}")
        return v

    @field_validator("property_key", mode="before")
    @classmethod
    def validate_property_key(cls, v: str) -> str:
        if v not in PROPERTY_DEFINITIONS:
            raise ValueError(f"Unknown property_key: {v}")
        return v


class BidPropertyInput(BaseModel):
    property_key: str
    value: Any = None
    layers: List[int] = Field(default_factory=lambda: [1])
    is_enabled: bool = True

    @field_validator("layers", mode="before")
    @classmethod
    def validate_layers(cls, v: List[int]) -> List[int]:
        for layer in v:
            if not (1 <= layer <= NUM_LAYERS):
                raise ValueError(f"Each layer must be between 1 and {NUM_LAYERS}, got {layer}")
        return v

    @field_validator("property_key", mode="before")
    @classmethod
    def validate_property_key(cls, v: str) -> str:
        if v not in PROPERTY_DEFINITIONS:
            raise ValueError(f"Unknown property_key: {v}")
        return v


class LayerSummary(BaseModel):
    layer_number: int
    total_pairings: int = 0
    pairings_by_layer: int = 0
    properties_count: int = 0


class Bid(BaseModel):
    id: str
    bid_period_id: str
    name: str
    status: str = "draft"
    entries: List[BidEntry] = Field(default_factory=list)
    properties: List[BidProperty] = Field(default_factory=list)
    summary: BidSummary = Field(default_factory=BidSummary)
    optimization_config: Optional[OptimizationConfig] = None
    optimization_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreateBidRequest(BaseModel):
    name: str
    entries: List[dict[str, Any]] = Field(default_factory=list)


class UpdateBidEntryInput(BaseModel):
    sequence_id: str
    rank: int
    is_pinned: bool = False
    is_excluded: bool = False


class UpdateBidRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    entries: Optional[List[UpdateBidEntryInput]] = None


class BidList(BaseModel):
    data: List[Bid]
    page_state: Optional[str] = None


# ── Bookmark ────────────────────────────────────────────────────────────────

class Bookmark(BaseModel):
    id: str
    sequence_id: str
    seq_number: int = 0
    created_at: Optional[datetime] = None


class BookmarkList(BaseModel):
    data: List[Bookmark]
    page_state: Optional[str] = None


# ── Filter Preset ───────────────────────────────────────────────────────────

class FilterSet(BaseModel):
    categories: List[str] = Field(default_factory=list)
    equipment_types: List[str] = Field(default_factory=list)
    layover_cities: List[str] = Field(default_factory=list)
    language: Optional[str] = None
    duty_days_min: Optional[int] = None
    duty_days_max: Optional[int] = None
    tpay_min_minutes: Optional[int] = None
    tpay_max_minutes: Optional[int] = None
    tafb_min_minutes: Optional[int] = None
    tafb_max_minutes: Optional[int] = None
    block_min_minutes: Optional[int] = None
    block_max_minutes: Optional[int] = None
    operating_dates: List[int] = Field(default_factory=list)
    position_min: Optional[int] = None
    position_max: Optional[int] = None
    include_deadheads: Optional[bool] = None
    is_turn: Optional[bool] = None
    report_earliest: Optional[int] = None
    report_latest: Optional[int] = None
    release_earliest: Optional[int] = None
    release_latest: Optional[int] = None


class FilterPreset(BaseModel):
    id: str
    name: str
    filters: FilterSet = Field(default_factory=FilterSet)
    created_at: Optional[datetime] = None


class FilterPresetInput(BaseModel):
    name: str
    filters: FilterSet

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return _sanitize_str(v) if isinstance(v, str) else v


VALID_CBA_SEVERITIES = {"error", "warning"}


# ── CBA Validation ─────────────────────────────────────────────────────────


class CBAViolation(BaseModel):
    rule: str
    severity: str = "warning"
    message: str
    affected_dates: List[int] = Field(default_factory=list)
    affected_sequences: List[int] = Field(default_factory=list)

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in VALID_CBA_SEVERITIES:
            raise ValueError(f"severity must be one of {VALID_CBA_SEVERITIES}")
        return v


class CreditHourSummary(BaseModel):
    estimated_credit_hours: float = 0.0
    line_min: int = 70
    line_max: int = 90
    within_range: bool = True


class DaysOffSummary(BaseModel):
    total_days_off: int = 0
    minimum_required: int = 11
    meets_requirement: bool = True


class CBAValidationResult(BaseModel):
    is_valid: bool = True
    violations: List[CBAViolation] = Field(default_factory=list)
    credit_hour_summary: CreditHourSummary = Field(default_factory=CreditHourSummary)
    days_off_summary: DaysOffSummary = Field(default_factory=DaysOffSummary)


# ── Awarded Schedule ────────────────────────────────────────────────────────

class AwardedSequenceEntry(BaseModel):
    seq_number: int
    sequence_id: Optional[str] = None
    operating_dates: List[int] = Field(default_factory=list)
    tpay_minutes: int = 0
    block_minutes: int = 0
    tafb_minutes: int = 0


class AwardedSchedule(BaseModel):
    id: str
    bid_period_id: str
    bid_id: Optional[str] = None
    source_filename: Optional[str] = None
    imported_at: Optional[datetime] = None
    awarded_sequences: List[AwardedSequenceEntry] = Field(default_factory=list)


class AttainabilityAccuracy(BaseModel):
    high_awarded: int = 0
    high_total: int = 0
    low_awarded: int = 0
    low_total: int = 0


class MatchedEntry(BaseModel):
    seq_number: int
    bid_rank: int
    was_awarded: bool
    attainability: str = "unknown"


class AwardAnalysis(BaseModel):
    bid_id: str
    awarded_schedule_id: str
    match_count: int = 0
    match_rate: float = 0.0
    top_10_match_count: int = 0
    top_10_match_rate: float = 0.0
    matched_entries: List[MatchedEntry] = Field(default_factory=list)
    unmatched_awards: List[int] = Field(default_factory=list)
    attainability_accuracy: AttainabilityAccuracy = Field(default_factory=AttainabilityAccuracy)
    insights: List[str] = Field(default_factory=list)


# ── Monthly Award Records (Holdability Calibration) ────────────────────────


class AwardedPairingRecord(BaseModel):
    """One pairing from a monthly PBS award — used for holdability calibration."""
    seq_number: int
    award_code: str             # P1-P7, PN, CN
    credit_minutes: int = 0
    layover_cities: List[str] = Field(default_factory=list)
    duty_days: int = 0


class MonthlyAwardInput(BaseModel):
    """Input for recording one month's PBS award results."""
    month: str                  # "2026-04"
    total_credit_minutes: int = 0
    line_label: str = ""        # "P3" or "L3"
    pairings: List[AwardedPairingRecord] = Field(default_factory=list)
    lost_seq_numbers: List[int] = Field(default_factory=list)  # wanted but didn't get
    notes: Optional[str] = None

    @field_validator("month", mode="before")
    @classmethod
    def validate_month(cls, v: str) -> str:
        if not v or len(v) < 7:
            raise ValueError("month must be YYYY-MM format (e.g., '2026-04')")
        return v


class MonthlyAwardRecord(BaseModel):
    """Stored monthly award record with metadata."""
    id: str
    user_id: str
    bid_period_id: Optional[str] = None
    month: str
    seniority_number: Optional[int] = None
    total_base_fas: Optional[int] = None
    total_credit_minutes: int = 0
    line_label: str = ""
    pairings: List[AwardedPairingRecord] = Field(default_factory=list)
    lost_seq_numbers: List[int] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


# ── Holdability & Explanation Models ───────────────────────────────────────


class PairingRationaleModel(BaseModel):
    """Per-pairing explanation returned in API responses."""
    sequence_id: str
    seq_number: int = 0
    layer: int = 0
    reasons_selected: List[str] = Field(default_factory=list)
    reasons_not_alternatives: List[str] = Field(default_factory=list)
    holdability: str = "UNKNOWN"
    holdability_pct: float = 50.0
    trade_offs: List[str] = Field(default_factory=list)


class LayerExplanation(BaseModel):
    """Per-layer explanation with narrative, calendar, rationales, PBS translation."""
    layer_num: int
    narrative: str = ""
    calendar_grid: str = ""
    rationales: List[PairingRationaleModel] = Field(default_factory=list)
    pbs_translation: str = ""
    holdability_pct: float = 50.0
    tips: List[str] = Field(default_factory=list)


class HoldabilityLayerReport(BaseModel):
    """Per-layer holdability assessment."""
    layer_num: int
    strategy_name: str = ""
    credit_hours: float = 0.0
    holdability_pct: float = 50.0
    holdability_category: str = "UNKNOWN"
    verdict: str = ""
    most_contested_seq: Optional[int] = None
    pool_size: int = 0


class HoldabilityReport(BaseModel):
    """Overall seniority-aware holdability assessment."""
    seniority_label: str = ""
    seniority_pct: float = 0.5
    seniority_display: str = ""
    layers: List[HoldabilityLayerReport] = Field(default_factory=list)
    best_realistic_layers: List[int] = Field(default_factory=list)
    recommendation: str = ""
    trend: Optional[str] = None
    calibration_months: int = 0


class CrossLayerSummary(BaseModel):
    """Cross-layer comparison data."""
    credit_spread: List[dict[str, Any]] = Field(default_factory=list)
    diversity_matrix: List[dict[str, Any]] = Field(default_factory=list)
    strategy_fulfillment: List[dict[str, Any]] = Field(default_factory=list)


class OptimizationExplanation(BaseModel):
    """Complete explanation output attached to optimization results."""
    holdability_report: Optional[HoldabilityReport] = None
    layers: List[LayerExplanation] = Field(default_factory=list)
    cross_layer_summary: Optional[CrossLayerSummary] = None
    recommendation: str = ""
    monthly_prompt: str = ""
