import type { BidProperty } from './api';

// ── Layer Labels ──────────────────────────────────────────────────────

export interface LayerLabel {
  name: string;
  group: string;
  emoji: string;
  color: string;       // Tailwind bg class for badge
  textColor: string;   // Tailwind text class
  lightBg: string;     // Tailwind bg class for row highlight
}

export const LAYER_LABELS: Record<number, LayerLabel> = {
  1: { name: 'Dream Pick', group: 'Top Picks', emoji: '🔥', color: 'bg-amber-500', textColor: 'text-amber-700', lightBg: 'bg-amber-50' },
  2: { name: 'Top Choice', group: 'Top Picks', emoji: '🔥', color: 'bg-orange-500', textColor: 'text-orange-700', lightBg: 'bg-orange-50' },
  3: { name: 'Strong Pick', group: 'Good Options', emoji: '✅', color: 'bg-yellow-500', textColor: 'text-yellow-700', lightBg: 'bg-yellow-50' },
  4: { name: 'Solid Option', group: 'Good Options', emoji: '✅', color: 'bg-green-500', textColor: 'text-green-700', lightBg: 'bg-green-50' },
  5: { name: 'Acceptable', group: 'Good Options', emoji: '✅', color: 'bg-teal-500', textColor: 'text-teal-700', lightBg: 'bg-teal-50' },
  6: { name: 'Backup', group: 'Safety Nets', emoji: '🛡️', color: 'bg-blue-500', textColor: 'text-blue-700', lightBg: 'bg-blue-50' },
  7: { name: 'Safety Net', group: 'Safety Nets', emoji: '🛡️', color: 'bg-gray-400', textColor: 'text-gray-600', lightBg: 'bg-gray-50' },
};

export const LAYER_GROUPS = [
  { name: 'Top Picks', emoji: '🔥', layers: [1, 2] },
  { name: 'Good Options', emoji: '✅', layers: [3, 4, 5] },
  { name: 'Safety Nets', emoji: '🛡️', layers: [6, 7] },
];

// ── Intent-Based Property Groups (for Fine-Tune accordion) ───────────

export interface PropertyGroup {
  id: string;
  label: string;
  description: string;
  propertyKeys: string[];
}

export const INTENT_PROPERTY_GROUPS: PropertyGroup[] = [
  {
    id: 'schedule_shape',
    label: 'Schedule Shape',
    description: 'Days off, work blocks, and on/off patterns',
    propertyKeys: [
      'maximize_total_days_off',
      'maximize_block_of_days_off',
      'string_days_off_starting',
      'string_days_off_ending',
      'minimize_days_off_between_blocks',
      'maximize_weekend_days_off',
      'waive_minimum_days_off',
      'work_block_size',
    ],
  },
  {
    id: 'trip_preferences',
    label: 'Trip Preferences',
    description: 'Pairing length, equipment, domestic/international, deadheads',
    propertyKeys: [
      'prefer_pairing_type',
      'prefer_pairing_length',
      'prefer_pairing_length_on_date',
      'prefer_duty_period',
      'prefer_aircraft',
      'avoid_aircraft',
      'prefer_deadheads',
      'avoid_deadheads',
      'prefer_language',
      'prefer_positions_order',
      'prefer_positions_order_per_aircraft',
      'pairing_id',
    ],
  },
  {
    id: 'credit_pay',
    label: 'Credit & Pay',
    description: 'Credit hours, TPAY targets, credit efficiency',
    propertyKeys: [
      'target_credit_range',
      'maximize_credit',
      'min_avg_credit_per_duty',
      'max_tafb_credit_ratio',
      'max_block_per_duty',
      'max_duty_time_per_duty',
    ],
  },
  {
    id: 'timing_commute',
    label: 'Timing & Commute',
    description: 'Report/release times, connections, commute settings',
    propertyKeys: [
      'report_between',
      'release_between',
      'report_between_on_date',
      'release_between_on_date',
      'mid_pairing_report_after',
      'mid_pairing_release_before',
      'min_connection_time',
      'max_connection_time',
      'commutable_work_block',
    ],
  },
  {
    id: 'layover_destinations',
    label: 'Layover & Destinations',
    description: 'Preferred layover cities, overnight locations',
    propertyKeys: [
      'layover_at_city',
      'avoid_layover_at_city',
      'layover_at_city_on_date',
      'min_layover_time',
      'max_layover_time',
      'prefer_landing_at_city',
      'avoid_landing_at_city',
      'prefer_one_landing_first_duty',
      'prefer_one_landing_last_duty',
      'max_landings_per_duty',
    ],
  },
  {
    id: 'reserve',
    label: 'Reserve',
    description: 'Reserve days, work blocks, and carryover',
    propertyKeys: [
      'waive_carryover_days_off',
      'block_of_reserve_days_off',
      'reserve_day_of_week_off',
      'reserve_work_block_size',
    ],
  },
  {
    id: 'advanced',
    label: 'Advanced / Other',
    description: 'Legal rest, co-terminal, buddy bids, waivers',
    propertyKeys: [
      'co_terminal_satellite_airport',
      'prefer_cadence_day_of_week',
      'pairing_mix_in_work_block',
      'allow_double_up_on_date',
      'allow_double_up_by_range',
      'allow_multiple_pairings',
      'allow_multiple_pairings_on_date',
      'allow_co_terminal_mix',
      'clear_bids',
      'waive_carry_over_credit',
      'avoid_person',
      'buddy_with',
      'waive_24hrs_rest_in_domicile',
      'waive_30hrs_in_7_days',
      'waive_minimum_domicile_rest',
    ],
  },
];

// ── Bid Templates ─────────────────────────────────────────────────────

export interface TemplatePropertyDefault {
  property_key: string;
  value: unknown;
  layers: number[];
}

export interface BidTemplate {
  id: string;
  name: string;
  description: string;
  seniorityRange: [number, number];
  stats: {
    targetTripLength: string;
    daysOffPattern: string;
    creditRange: string;
  };
  icon: string;
  propertyDefaults: TemplatePropertyDefault[];
  favoriteProperties: string[];
}

export const BID_TEMPLATES: BidTemplate[] = [
  {
    id: 'commuter_max_time_off',
    name: 'Commuter Max Time Off',
    description: 'Minimize trips to base. Consecutive days off, multi-day pairings.',
    seniorityRange: [15, 60],
    stats: {
      targetTripLength: '3-4 day trips',
      daysOffPattern: 'Blocked days off',
      creditRange: '75-90 hours',
    },
    icon: '✈️',
    propertyDefaults: [
      { property_key: 'maximize_block_of_days_off', value: true, layers: [1, 2, 3, 4, 5, 6, 7] },
      { property_key: 'prefer_pairing_length', value: 3, layers: [1, 2, 3] },
      { property_key: 'prefer_pairing_length', value: 4, layers: [4, 5] },
      { property_key: 'report_between', value: { start: 600, end: 840 }, layers: [1, 2, 3] },
      { property_key: 'release_between', value: { start: 480, end: 1080 }, layers: [1, 2, 3] },
      { property_key: 'maximize_credit', value: true, layers: [1, 2, 3, 4, 5, 6, 7] },
    ],
    favoriteProperties: [
      'maximize_block_of_days_off', 'string_days_off_starting', 'prefer_pairing_length',
      'report_between', 'release_between', 'maximize_credit', 'layover_at_city',
      'commutable_work_block',
    ],
  },
  {
    id: 'international_explorer',
    name: 'International Explorer',
    description: 'Chase premium routes and great layover cities.',
    seniorityRange: [10, 45],
    stats: {
      targetTripLength: '3-5 day trips',
      daysOffPattern: 'Flexible',
      creditRange: '80-95 hours',
    },
    icon: '🌏',
    propertyDefaults: [
      { property_key: 'prefer_pairing_type', value: 'ipd', layers: [1, 2] },
      { property_key: 'prefer_aircraft', value: '777', layers: [1, 2, 3] },
      { property_key: 'maximize_credit', value: true, layers: [1, 2, 3, 4, 5, 6, 7] },
      { property_key: 'prefer_pairing_length', value: 3, layers: [3, 4, 5] },
    ],
    favoriteProperties: [
      'prefer_pairing_type', 'prefer_aircraft', 'layover_at_city', 'prefer_pairing_length',
      'maximize_credit', 'prefer_language', 'report_between', 'release_between',
    ],
  },
  {
    id: 'high_credit_domestic',
    name: 'High Credit Domestic',
    description: 'Maximize pay with efficient domestic trips.',
    seniorityRange: [20, 70],
    stats: {
      targetTripLength: '2-4 day trips',
      daysOffPattern: 'Flexible',
      creditRange: '85-95 hours',
    },
    icon: '💰',
    propertyDefaults: [
      { property_key: 'maximize_credit', value: true, layers: [1, 2, 3, 4, 5, 6, 7] },
      { property_key: 'prefer_pairing_length', value: 3, layers: [1, 2, 3] },
      { property_key: 'prefer_pairing_length', value: 2, layers: [4, 5] },
    ],
    favoriteProperties: [
      'maximize_credit', 'min_avg_credit_per_duty', 'prefer_pairing_length',
      'report_between', 'release_between', 'layover_at_city', 'prefer_aircraft',
      'max_tafb_credit_ratio',
    ],
  },
  {
    id: 'new_fa_safe_bid',
    name: 'New FA Safe Bid',
    description: 'Broad preferences to avoid company-assigned leftovers.',
    seniorityRange: [50, 100],
    stats: {
      targetTripLength: 'Any length',
      daysOffPattern: 'Maximize days off',
      creditRange: '70-85 hours',
    },
    icon: '🛡️',
    propertyDefaults: [
      { property_key: 'maximize_total_days_off', value: true, layers: [1, 2, 3, 4, 5, 6, 7] },
      { property_key: 'maximize_credit', value: true, layers: [1, 2, 3, 4, 5, 6, 7] },
    ],
    favoriteProperties: [
      'maximize_total_days_off', 'maximize_credit', 'report_between', 'release_between',
      'prefer_pairing_length', 'layover_at_city', 'avoid_layover_at_city', 'maximize_block_of_days_off',
    ],
  },
  {
    id: 'weekend_warrior',
    name: 'Weekend Warrior',
    description: 'Saturdays and Sundays off, flexible on everything else.',
    seniorityRange: [10, 50],
    stats: {
      targetTripLength: '2-3 day trips',
      daysOffPattern: 'Weekends off',
      creditRange: '75-90 hours',
    },
    icon: '🏖️',
    propertyDefaults: [
      { property_key: 'maximize_weekend_days_off', value: true, layers: [1, 2, 3, 4, 5, 6, 7] },
      { property_key: 'maximize_credit', value: true, layers: [1, 2, 3, 4, 5, 6, 7] },
      { property_key: 'prefer_pairing_length', value: 3, layers: [1, 2, 3] },
    ],
    favoriteProperties: [
      'maximize_weekend_days_off', 'maximize_credit', 'prefer_pairing_length',
      'report_between', 'release_between', 'layover_at_city', 'prefer_cadence_day_of_week',
      'work_block_size',
    ],
  },
  {
    id: 'reserve_optimizer',
    name: 'Reserve Optimizer',
    description: 'Make reserve work for you.',
    seniorityRange: [60, 100],
    stats: {
      targetTripLength: 'Reserve days',
      daysOffPattern: 'Block reserve off-days',
      creditRange: 'Per reserve rules',
    },
    icon: '📋',
    propertyDefaults: [
      { property_key: 'block_of_reserve_days_off', value: 4, layers: [1, 2, 3, 4, 5, 6, 7] },
      { property_key: 'maximize_total_days_off', value: true, layers: [1, 2, 3, 4, 5, 6, 7] },
    ],
    favoriteProperties: [
      'block_of_reserve_days_off', 'reserve_day_of_week_off', 'reserve_work_block_size',
      'waive_carryover_days_off', 'maximize_total_days_off', 'maximize_block_of_days_off',
      'report_between', 'release_between',
    ],
  },
];
