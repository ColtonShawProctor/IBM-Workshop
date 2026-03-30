// ── Auth ────────────────────────────────────────────────────────────────

export interface Profile {
  display_name?: string;
  base_city?: string;
  commute_from?: string;  // IATA code — city FA commutes from (e.g. DEN)
  seniority_number?: number;
  total_base_fas?: number;
  seniority_percentage?: number;  // 0-100, from PBS portal
  position_min?: number;
  position_max?: number;
  language_qualifications: string[];
}

export interface PreferenceWeights {
  days_off: number;
  tpay: number;
  layover_city: number;
  equipment: number;
  report_time: number;
  release_time: number;
  redeye: number;
  trip_length: number;
  clustering: number;
}

export interface Preferences {
  preferred_days_off: number[];
  preferred_layover_cities: string[];
  avoided_layover_cities: string[];
  tpay_min_minutes?: number;
  tpay_max_minutes?: number;
  preferred_equipment: string[];
  report_earliest_minutes?: number;
  report_latest_minutes?: number;
  release_earliest_minutes?: number;
  release_latest_minutes?: number;
  avoid_redeyes: boolean;
  prefer_turns?: boolean;
  prefer_high_ops?: boolean;
  cluster_trips: boolean;
  weights: PreferenceWeights;
}

export interface User {
  id: string;
  email: string;
  profile: Profile;
  default_preferences: Preferences;
  created_at?: string;
  updated_at?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
}

// ── Commute Impact ─────────────────────────────────────────────────────

export interface CommuteImpact {
  first_day_feasible: boolean;
  first_day_note: string;
  last_day_feasible: boolean;
  last_day_note: string;
  hotel_nights_needed: number;
  impact_level: 'green' | 'yellow' | 'red';
}

// ── Bid Period ──────────────────────────────────────────────────────────

export interface BidPeriod {
  id: string;
  name: string;
  effective_start: string;
  effective_end: string;
  base_city?: string;
  source_filename?: string;
  parse_status: 'pending' | 'processing' | 'completed' | 'failed';
  parse_error?: string;
  total_sequences: number;
  total_dates: number;
  categories: string[];
  issued_date?: string;
  target_credit_min_minutes: number;
  target_credit_max_minutes: number;
  preference_overrides?: Preferences;
  created_at?: string;
  updated_at?: string;
}

// ── Sequence ────────────────────────────────────────────────────────────

export interface Layover {
  city?: string;
  hotel_name?: string;
  hotel_phone?: string;
  transport_company?: string;
  transport_phone?: string;
  rest_minutes?: number;
}

export interface Leg {
  leg_index: number;
  flight_number: string;
  is_deadhead: boolean;
  equipment: string;
  departure_station: string;
  departure_local: string;
  departure_base: string;
  meal_code?: string;
  arrival_station: string;
  arrival_local: string;
  arrival_base: string;
  pax_service?: string;
  block_minutes: number;
  ground_minutes?: number;
  is_connection: boolean;
}

export interface DutyPeriod {
  dp_number: number;
  day_of_seq?: number;
  day_of_seq_total?: number;
  report_local: string;
  report_base: string;
  release_local: string;
  release_base: string;
  duty_minutes?: number;
  legs: Leg[];
  layover?: Layover;
}

export interface SequenceTotals {
  block_minutes: number;
  synth_minutes: number;
  tpay_minutes: number;
  tafb_minutes: number;
  duty_days: number;
  leg_count: number;
  deadhead_count: number;
}

export interface Sequence {
  id: string;
  bid_period_id: string;
  seq_number: number;
  category?: string;
  ops_count: number;
  position_min: number;
  position_max: number;
  language?: string;
  language_count?: number;
  operating_dates: number[];
  is_turn: boolean;
  has_deadhead: boolean;
  is_redeye: boolean;
  totals: SequenceTotals;
  layover_cities: string[];
  duty_periods: DutyPeriod[];
  source: 'parsed' | 'manual';
  eligibility?: string;
  commute_impact?: CommuteImpact | null;
  created_at?: string;
  updated_at?: string;
}

// ── PBS Properties ──────────────────────────────────────────────────────

export const NUM_LAYERS = 7;

export type PropertyCategory = 'days_off' | 'line' | 'pairing' | 'reserve';

export type PairingType = 'regular' | 'nipd' | 'ipd' | 'premium_transcon' | 'odan' | 'redeye' | 'satellite';

export const EQUIPMENT_CODES = [
  '320', '321', 'A21', '737', '38K', '38M', '777', '77W', '787', '788', '789', '78P',
] as const;

export const PAIRING_TYPES: { value: PairingType; label: string }[] = [
  { value: 'regular', label: 'Regular' },
  { value: 'nipd', label: 'NIPD' },
  { value: 'ipd', label: 'IPD' },
  { value: 'premium_transcon', label: 'Premium Transcon' },
  { value: 'odan', label: 'ODAN' },
  { value: 'redeye', label: 'Red-Eye' },
  { value: 'satellite', label: 'Satellite' },
];

export type ValueType =
  | 'toggle' | 'integer' | 'decimal' | 'time' | 'time_range' | 'int_range'
  | 'date' | 'date_range' | 'pairing_type' | 'equipment' | 'airport'
  | 'airport_date' | 'days_of_week' | 'position_list' | 'text' | 'selection'
  | 'time_range_date' | 'int_date';

export interface PropertyDefinition {
  key: string;
  category: PropertyCategory;
  label: string;
  value_type: ValueType;
  favorite: boolean;
  /** Alternate search terms FAs might use (e.g. "equipment" for aircraft) */
  aliases?: string[];
}

export interface BidProperty {
  id: string;
  property_key: string;
  category: PropertyCategory;
  value: unknown;
  layers: number[];
  is_enabled: boolean;
}

export interface BidPropertyInput {
  property_key: string;
  value: unknown;
  layers: number[];
  is_enabled?: boolean;
}

export interface LayerSummary {
  layer_number: number;
  total_pairings: number;
  pairings_by_layer: number;
  properties_count: number;
}

// ── Bid ─────────────────────────────────────────────────────────────────

export interface BidEntry {
  rank: number;
  sequence_id: string;
  seq_number: number;
  is_pinned: boolean;
  is_excluded: boolean;
  rationale?: string;
  preference_score: number;
  attainability: 'high' | 'medium' | 'low' | 'unknown';
  date_conflict_group?: string;
  layer?: number;
  commute_impact?: CommuteImpact | null;
}

export interface DateCoverage {
  covered_dates: number[];
  uncovered_dates: number[];
  coverage_rate: number;
}

export interface BidSummary {
  total_entries: number;
  total_tpay_minutes: number;
  total_block_minutes: number;
  total_tafb_minutes: number;
  total_days_off: number;
  sequence_count: number;
  leg_count: number;
  deadhead_count: number;
  international_count: number;
  domestic_count: number;
  layover_cities: string[];
  date_coverage: DateCoverage;
  conflict_groups: number;
  commute_warnings?: string[];
}

export interface Bid {
  id: string;
  bid_period_id: string;
  name: string;
  status: 'draft' | 'optimized' | 'finalized' | 'exported';
  entries: BidEntry[];
  properties: BidProperty[];
  summary: BidSummary;
  optimization_config?: {
    preferences_used?: Preferences;
    seniority_number?: number;
    total_base_fas?: number;
    pinned_ids: string[];
    excluded_ids: string[];
  };
  optimization_run_at?: string;
  created_at?: string;
  updated_at?: string;
}

// ── Bookmark ────────────────────────────────────────────────────────────

export interface Bookmark {
  id: string;
  sequence_id: string;
  seq_number: number;
  created_at?: string;
}

// ── Paginated responses ─────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  data: T[];
  page_state?: string;
  total_count?: number;
}

// ── Filter Preset ──────────────────────────────────────────────────────

export interface FilterSet {
  categories: string[];
  equipment_types: string[];
  layover_cities: string[];
  language?: string;
  duty_days_min?: number;
  duty_days_max?: number;
  tpay_min_minutes?: number;
  tpay_max_minutes?: number;
  tafb_min_minutes?: number;
  tafb_max_minutes?: number;
  block_min_minutes?: number;
  block_max_minutes?: number;
  operating_dates: number[];
  position_min?: number;
  position_max?: number;
  include_deadheads?: boolean;
  is_turn?: boolean;
  report_earliest?: number;
  report_latest?: number;
  release_earliest?: number;
  release_latest?: number;
}

export interface FilterPreset {
  id: string;
  name: string;
  filters: FilterSet;
  created_at?: string;
}

// ── Projected Schedule ─────────────────────────────────────────────────

export interface ProjectedScheduleLayer {
  layer_number: number;
  sequences: {
    seq_number: number;
    category: string;
    tpay_minutes: number;
    duty_days: number;
    operating_dates: number[];
  }[];
  total_credit_hours: number;
  total_days_off: number;
  working_dates: number[];
  off_dates: number[];
  schedule_shape: string;
  within_credit_range: boolean;
}

export interface ProjectedScheduleResponse {
  layers: ProjectedScheduleLayer[];
}

// ── Error ───────────────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
