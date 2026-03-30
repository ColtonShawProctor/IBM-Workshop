# Scheduling App — Technical Design Document

## 1. Architecture Overview

The Scheduling App is a personal planning tool that sits between the airline's published bid sheet PDF and the airline's bid submission system. It does **not** interact with the airline directly. Its job is to help a flight attendant produce the best possible rank-ordered bid list.

The system follows a client-server architecture: a single-page frontend communicates with a RESTful backend API. The backend persists data in DataStax Astra DB (JSON Data API), runs an asynchronous PDF parsing pipeline, and hosts the optimization engine that generates strategically ranked bids.

### System Context

```
  ┌─────────────────────┐
  │  Airline publishes   │
  │  bid sheet PDF       │
  └─────────┬───────────┘
            │ (manual download by FA)
            ▼
  ┌──────────────────────────────────────────────────────────┐
  │                   Scheduling App                         │
  │                                                          │
  │  ┌────────────────────────────────────────────────────┐  │
  │  │                    Frontend                        │  │
  │  │  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐  │  │
  │  │  │ Sequence  │ │   Bid    │ │Calendar│ │Profile │  │  │
  │  │  │ Browser   │ │ Builder  │ │  View  │ │& Prefs │  │  │
  │  │  └──────────┘ └──────────┘ └────────┘ └────────┘  │  │
  │  └───────────────────────┬────────────────────────────┘  │
  │                          │ HTTPS / REST                  │
  │  ┌───────────────────────┴────────────────────────────┐  │
  │  │                   Backend API                      │  │
  │  │  ┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐  │  │
  │  │  │  Auth  │ │  CRUD  │ │  Parser  │ │Optimizer │  │  │
  │  │  │Service │ │Service │ │ Service  │ │ Engine   │  │  │
  │  │  └────────┘ └────────┘ └──────────┘ └──────────┘  │  │
  │  └───────────────────────┬────────────────────────────┘  │
  │                          │ Data API (JSON)               │
  │  ┌───────────────────────┴────────────────────────────┐  │
  │  │                   Astra DB                         │  │
  │  │   users · bid_periods · sequences · bids           │  │
  │  │   bookmarks · filter_presets · awarded_schedules   │  │
  │  └────────────────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────────┘
            │
            │ (FA manually enters ranked list)
            ▼
  ┌─────────────────────┐
  │  Airline's bid       │
  │  submission system   │
  └─────────────────────┘
```

### Core Domain Concepts Driving the Design

Per requirements Section 1.1, the design must account for:

1. **Seniority-based awarding** — The airline awards sequences in strict seniority order. The app's optimizer must understand that a junior FA's top picks are likely taken by senior FAs, and strategically place attainable sequences higher.

2. **Date conflict exclusivity** — An FA can only be awarded one sequence per operating date. Sequences with overlapping dates compete with each other. The optimizer must group date-conflicting sequences and rank the preferred one higher with alternatives as fallbacks.

3. **Depth of coverage** — A bid that doesn't cover enough dates across the month leaves the FA at risk of falling to reserve. The optimizer must ensure the ranked list provides sufficient date coverage for the full bid period.

4. **The app is a rank-ordering tool** — It outputs a numbered list of SEQ preferences. It does not assign schedules or interact with the airline. All intelligence is in producing the best possible ordering.

5. **CBA compliance** — The app is built specifically for American Airlines flight attendants governed by the 2024 AA/APFA Collective Bargaining Agreement (CBA). All scheduling constraints, pay rules, duty time limits, and rest requirements reference specific CBA sections. The optimizer must validate sequences against CBA duty time charts, rest minimums, credit hour limits, and other contractual constraints.

---

## 2. Data Model — Astra DB Collections

Astra DB's JSON Data API stores documents in collections (schemaless JSON). Below is the logical schema for each collection with field names, types, nesting, indexing strategy, and how the seniority-based bidding logic is represented in the data.

### 2.1 `users`

One document per user. Stores profile, authentication, and default scheduling preferences.

```json
{
  "_id":                "uuid",
  "email":              "string",
  "password_hash":      "string",
  "created_at":         "iso-datetime",
  "updated_at":         "iso-datetime",
  "profile": {
    "display_name":             "string",
    "base_city":                "string  (IATA code, e.g. 'ORD')",
    "seniority_number":         "integer (lower = more senior)",
    "total_base_fas":           "integer (total FAs at this base, for percentile calculation)",
    "position_min":             "integer (e.g. 1)",
    "position_max":             "integer (e.g. 4 or 9)",
    "language_qualifications":  ["string (e.g. 'JP', 'SP')"],
    "commute_from":             "string | null (IATA code, e.g. 'DCA' — city FA commutes from for commute impact analysis)",
    "years_of_service":         "integer (for pay rate lookup per CBA §3.A)",
    "is_reserve":               "boolean (Reserve vs Lineholder status)",
    "is_purser_qualified":      "boolean (CBA §14.L)",
    "line_option":              "string (enum: standard | high | low — CBA §2.EE)"
  },
  "default_preferences": {
    "preferred_days_off":       ["integer (day-of-month)"],
    "preferred_layover_cities": ["string (IATA code)"],
    "avoided_layover_cities":   ["string (IATA code)"],
    "tpay_min_minutes":         "integer",
    "tpay_max_minutes":         "integer",
    "preferred_equipment":      ["string (e.g. '777', '787')"],
    "report_earliest_minutes":  "integer (minutes from midnight)",
    "report_latest_minutes":    "integer",
    "release_earliest_minutes": "integer",
    "release_latest_minutes":   "integer",
    "avoid_redeyes":            "boolean",
    "prefer_turns":             "boolean | null (null = no preference)",
    "prefer_high_ops":          "boolean | null",
    "prefer_holidays":          "boolean | null (preference for holiday premium sequences)",
    "prefer_speaker_sequences": "boolean | null (for language-qualified FAs)",
    "cluster_trips":            "boolean",
    "weights": {
      "days_off":       "integer (1-10)",
      "tpay":           "integer (1-10)",
      "layover_city":   "integer (1-10)",
      "equipment":      "integer (1-10)",
      "report_time":    "integer (1-10)",
      "release_time":   "integer (1-10)",
      "redeye":         "integer (1-10)",
      "trip_length":    "integer (1-10)",
      "clustering":     "integer (1-10)"
    }
  }
}
```

`seniority_number` and `total_base_fas` are central to the optimization strategy. The optimizer uses the ratio to estimate which percentile of sequences the FA can realistically attain.

**Indexes:** `email` (unique), `profile.base_city`

**REQ mapping:** REQ-008, REQ-009, REQ-010, REQ-025

---

### 2.2 `bid_periods`

One document per imported bid sheet. Holds metadata, parsing state, the source file reference, and per-period preference overrides.

```json
{
  "_id":              "uuid",
  "user_id":          "uuid (ref → users)",
  "name":             "string (e.g. 'January 2026')",
  "effective_start":  "iso-date (e.g. '2026-01-01')",
  "effective_end":    "iso-date (e.g. '2026-01-30')",
  "base_city":        "string (IATA code)",
  "source_filename":  "string",
  "source_file_url":  "string (object-store URL)",
  "parse_status":     "string (enum: pending | processing | completed | failed)",
  "parse_error":      "string | null",
  "total_sequences":  "integer",
  "total_dates":      "integer (number of days in the bid period, e.g. 30)",
  "categories":       ["string (e.g. '777 INTL', '787 INTL', 'NBI INTL', 'NBD DOM')"],
  "issued_date":      "iso-date",
  "created_at":       "iso-datetime",
  "updated_at":       "iso-datetime",
  "preference_overrides": {
    "// same shape as default_preferences in users — only fields that differ"
  }
}
```

`total_dates` is used by the optimizer to calculate date coverage percentage.

**Indexes:** `user_id`, `parse_status`

**REQ mapping:** REQ-001, REQ-002, REQ-009, REQ-019, REQ-022

---

### 2.3 `sequences`

One document per sequence extracted from a bid sheet. The largest collection. Each document embeds its full itinerary (duty periods → legs → layovers) so a single read returns everything needed for display and optimization.

```json
{
  "_id":              "uuid",
  "bid_period_id":    "uuid (ref → bid_periods)",
  "user_id":          "uuid (ref → users)",

  "seq_number":       "integer (e.g. 663)",
  "category":         "string (e.g. '777 INTL', 'NBD DOM')",
  "ops_count":        "integer",
  "position_min":     "integer",
  "position_max":     "integer",
  "language":         "string | null (e.g. 'JP', 'SP')",
  "language_count":   "integer | null (e.g. 3)",

  "operating_dates":  ["integer (day-of-month, e.g. [6,7,8,9,10,11])"],

  "is_turn":          "boolean (true if single duty day, no layover)",
  "has_deadhead":     "boolean",
  "is_redeye":        "boolean",
  "is_odan":          "boolean (On-Duty All-Nighter per CBA §2.II — all on-duty hours between 0100-0500 HBT)",
  "international_duty_type": "string | null (enum: 'non_long_range' | 'mid_range' | 'long_range' | 'extended_long_range' — per CBA §14.B)",
  "is_ipd":           "boolean (International Premium Destination per CBA §14.B)",
  "is_nipd":          "boolean (Non-International Premium Destination)",
  "has_holiday":       "boolean (sequence operates on a CBA §3.K holiday day)",
  "is_speaker_sequence": "boolean (requires foreign language speaker per CBA §15)",

  "totals": {
    "block_minutes":    "integer",
    "synth_minutes":    "integer",
    "tpay_minutes":     "integer",
    "tafb_minutes":     "integer",
    "duty_days":        "integer",
    "leg_count":        "integer",
    "deadhead_count":   "integer",
    "duty_rig_minutes":  "integer (Duty Rig guarantee: 1hr per 2hr on-duty, CBA §2.P)",
    "trip_rig_minutes":  "integer (Trip Rig guarantee: 1hr per 3:30 TAFB, CBA §2.AAA)",
    "estimated_pay_cents": "integer (estimated total compensation in cents, including premiums)"
  },

  "layover_cities":   ["string (IATA codes of overnight layover cities)"],

  "duty_periods": [
    {
      "dp_number":          "integer (1-based)",
      "day_of_seq":         "integer",
      "day_of_seq_total":   "integer",
      "report_local":       "string ('HH:MM')",
      "report_base":        "string ('HH:MM')",
      "release_local":      "string ('HH:MM')",
      "release_base":       "string ('HH:MM')",
      "duty_minutes":       "integer",
      "legs": [
        {
          "leg_index":          "integer (1-based within DP)",
          "flight_number":      "string (e.g. '1105' or '1105D')",
          "is_deadhead":        "boolean",
          "equipment":          "string (e.g. '45', '83', '97')",
          "departure_station":  "string (IATA)",
          "departure_local":    "string ('HH:MM')",
          "departure_base":     "string ('HH:MM')",
          "meal_code":          "string | null (e.g. '*BF', 'L')",
          "arrival_station":    "string (IATA)",
          "arrival_local":      "string ('HH:MM')",
          "arrival_base":       "string ('HH:MM')",
          "pax_service":        "string (e.g. 'QLF', 'QDB')",
          "block_minutes":      "integer",
          "ground_minutes":     "integer | null",
          "is_connection":      "boolean"
        }
      ],
      "layover": {
        "city":                 "string (IATA) | null",
        "hotel_name":           "string | null",
        "hotel_phone":          "string | null",
        "transport_company":    "string | null",
        "transport_phone":      "string | null",
        "rest_minutes":         "integer | null"
      }
    }
  ],

  "source":           "string (enum: 'parsed' | 'manual')",
  "created_at":       "iso-datetime",
  "updated_at":       "iso-datetime",

  "// Computed at response time (not persisted) when user has commute_from set:":
  "commute_impact": {
    "first_day_feasible":  "boolean (can FA commute in same-day for first report?)",
    "first_day_note":      "string (e.g. 'Report 14:26 — easy commute (earliest DCA→ORD arrives 08:30)')",
    "last_day_feasible":   "boolean (can FA commute home same-day after last release?)",
    "last_day_note":       "string (e.g. 'Release 12:07 — easy commute home')",
    "hotel_nights_needed": "integer (0, 1, or 2)",
    "impact_level":        "string (enum: 'green' | 'yellow' | 'red')"
  }
}
```

`operating_dates` is the critical field for date-conflict analysis. The optimizer compares `operating_dates` across sequences to identify mutually exclusive groups — sequences that share any date cannot both be awarded.

**Indexes:** `bid_period_id`, `user_id`, `seq_number`, `category`, `totals.tpay_minutes`, `totals.tafb_minutes`, `totals.block_minutes`, `language`, `is_turn`, `has_deadhead`, `is_redeye`

**REQ mapping:** REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-010

---

### 2.4 `bids`

One document per bid the user creates within a bid period. This is the **core output** of the app — a rank-ordered list of sequence preferences. The document tracks the strategic optimization state: which sequences are pinned/excluded, the rationale for each ranking, date conflict grouping, and a coverage analysis of the bid.

```json
{
  "_id":              "uuid",
  "bid_period_id":    "uuid (ref → bid_periods)",
  "user_id":          "uuid (ref → users)",
  "name":             "string (e.g. 'My January Bid v2')",
  "status":           "string (enum: draft | optimized | finalized | exported)",

  "entries": [
    {
      "rank":               "integer (1-based position in the bid)",
      "sequence_id":        "uuid (ref → sequences)",
      "seq_number":         "integer (denormalized for display)",
      "is_pinned":          "boolean",
      "is_excluded":        "boolean",
      "rationale":          "string | null (e.g. 'High TPAY + preferred layover; low competition (LANG JP)')",
      "preference_score":   "number (0.0–1.0, how well it matches preferences)",
      "attainability":      "string (enum: high | medium | low | unknown)",
      "date_conflict_group":"string | null (ID grouping sequences with overlapping dates)"
    }
  ],

  "summary": {
    "total_entries":          "integer",
    "total_tpay_minutes":     "integer (sum of all ranked sequences)",
    "total_block_minutes":    "integer",
    "total_tafb_minutes":     "integer",
    "total_days_off":         "integer",
    "sequence_count":         "integer",
    "leg_count":              "integer",
    "deadhead_count":         "integer",
    "international_count":    "integer",
    "domestic_count":         "integer",
    "layover_cities":         ["string"],
    "date_coverage": {
      "covered_dates":        ["integer (days-of-month covered by at least one ranked sequence)"],
      "uncovered_dates":      ["integer (days-of-month with no ranked sequence)"],
      "coverage_rate":        "number (0.0–1.0, covered / total period days)"
    },
    "conflict_groups":        "integer (number of distinct date-conflict groups)",
    "total_credit_hours":       "number (estimated credited hours for line value calculation)",
    "line_option":              "string (standard | high | low)",
    "line_min_hours":           "integer (40, 70, or per option)",
    "line_max_hours":           "integer (90, 110, or per option)",
    "credit_hour_utilization":  "number (0.0–1.0, credit hours / line max)",
    "estimated_total_pay_cents":"integer (sum of estimated_pay_cents for realistic award projection)",
    "cba_violations":           ["string (list of CBA constraint violations detected, e.g., '7-day block limit exceeded on dates 12-18')"],
    "commute_warnings":         ["string (commute-related warnings, e.g., 'Back-to-back trips SEQ 664→SEQ 512 with 14h gap — insufficient time to commute home to DCA')"]
  },

  "projected_schedules": {
    "// Computed per layer after optimization — shows what the FA's month would look like if top picks are awarded":
    "1": {
      "sequences":           ["{ seq_number, category, tpay_minutes, duty_days, operating_dates }"],
      "total_credit_hours":  "number",
      "total_days_off":      "integer",
      "working_dates":       ["integer (days-of-month with trips)"],
      "off_dates":           ["integer (days-of-month without trips)"],
      "schedule_shape":      "string (e.g. '5 trips, 82.5 credit hours, 14 days off, front-loaded')",
      "within_credit_range": "boolean"
    }
  },

  "optimization_config": {
    "preferences_used":       "object (snapshot of merged preferences at optimization time)",
    "seniority_number":       "integer (snapshot)",
    "total_base_fas":         "integer (snapshot)",
    "pinned_ids":             ["uuid"],
    "excluded_ids":           ["uuid"]
  },

  "optimization_run_at":  "iso-datetime | null",
  "created_at":           "iso-datetime",
  "updated_at":           "iso-datetime"
}
```

Key fields added for strategic bidding:

- **`preference_score`** — How well the sequence matches the FA's weighted preferences, independent of attainability. A 1.0 is a perfect match.
- **`attainability`** — An estimate of whether this sequence is realistically available at the user's seniority level. Derived from OPS count (fewer OPS = more contested), language requirements (restricts competition), and seniority percentile.
- **`date_conflict_group`** — Groups sequences whose `operating_dates` overlap. Within a conflict group, only the highest-ranked one can be awarded; the rest are fallbacks. The frontend uses this to visually cluster alternatives.
- **`summary.date_coverage`** — Tracks which dates in the bid period are covered by at least one ranked sequence and which are not. An `uncovered_dates` list alerts the FA to reserve risk.
- **`optimization_config`** — A snapshot of the inputs used for the last optimization run, so the FA can understand and reproduce results.

**Indexes:** `bid_period_id`, `user_id`, `status`

**REQ mapping:** REQ-011, REQ-012, REQ-013, REQ-015, REQ-016, REQ-020

---

### 2.5 `bookmarks`

Lightweight documents linking a user to a favorited sequence within a bid period.

```json
{
  "_id":              "uuid",
  "user_id":          "uuid (ref → users)",
  "bid_period_id":    "uuid (ref → bid_periods)",
  "sequence_id":      "uuid (ref → sequences)",
  "seq_number":       "integer (denormalized)",
  "created_at":       "iso-datetime"
}
```

**Indexes:** compound `(user_id, bid_period_id)`

**REQ mapping:** REQ-021

---

### 2.6 `filter_presets`

Saved filter configurations for reuse across sessions.

```json
{
  "_id":              "uuid",
  "user_id":          "uuid (ref → users)",
  "bid_period_id":    "uuid (ref → bid_periods) | null (global preset)",
  "name":             "string",
  "filters": {
    "categories":           ["string"],
    "equipment_types":      ["string"],
    "layover_cities":       ["string"],
    "language":             "string | null",
    "duty_days_min":        "integer | null",
    "duty_days_max":        "integer | null",
    "tpay_min_minutes":     "integer | null",
    "tpay_max_minutes":     "integer | null",
    "tafb_min_minutes":     "integer | null",
    "tafb_max_minutes":     "integer | null",
    "block_min_minutes":    "integer | null",
    "block_max_minutes":    "integer | null",
    "operating_dates":      ["integer (day-of-month)"],
    "position_min":         "integer | null",
    "position_max":         "integer | null",
    "include_deadheads":    "boolean | null",
    "is_turn":              "boolean | null",
    "report_earliest":      "integer | null (minutes from midnight)",
    "report_latest":        "integer | null",
    "release_earliest":     "integer | null",
    "release_latest":       "integer | null"
  },
  "created_at":       "iso-datetime"
}
```

**Indexes:** `user_id`

**REQ mapping:** REQ-006

---

### 2.7 `awarded_schedules`

One document per awarded schedule import. Stores awarded sequences and the bid-vs-award analysis results that help the FA refine future strategy.

```json
{
  "_id":              "uuid",
  "bid_period_id":    "uuid (ref → bid_periods)",
  "user_id":          "uuid (ref → users)",
  "bid_id":           "uuid (ref → bids) | null",
  "source_filename":  "string",
  "imported_at":      "iso-datetime",
  "awarded_sequences": [
    {
      "seq_number":       "integer",
      "sequence_id":      "uuid (ref → sequences) | null",
      "operating_dates":  ["integer"],
      "tpay_minutes":     "integer",
      "block_minutes":    "integer",
      "tafb_minutes":     "integer"
    }
  ],
  "analysis": {
    "match_count":          "integer (sequences in bid that were awarded)",
    "match_rate":           "number (0.0–1.0)",
    "top_10_match_count":   "integer",
    "top_10_match_rate":    "number (0.0–1.0)",
    "unmatched_awards":     ["integer (seq_numbers awarded but not in bid)"],
    "attainability_accuracy": {
      "high_awarded":     "integer (sequences marked 'high' attainability that were awarded)",
      "high_total":       "integer (total sequences marked 'high')",
      "low_awarded":      "integer (sequences marked 'low' that were awarded — surprises)",
      "low_total":        "integer"
    },
    "insights":             ["string"]
  }
}
```

The `attainability_accuracy` sub-object provides feedback on how well the optimizer's seniority estimates performed. If sequences marked "low attainability" were frequently awarded, the seniority model may need recalibration for next month.

**Indexes:** `bid_period_id`, `user_id`

**REQ mapping:** REQ-017, REQ-018, REQ-019

---

## 3. Collection Relationship Diagram

```
users ──────────┐
   │            │
   │ 1:N        │ 1:N
   ▼            ▼
bid_periods   bookmarks
   │
   │ 1:N
   ├──────────────┬──────────────┬──────────────┐
   ▼              ▼              ▼              ▼
sequences       bids       filter_presets  awarded_schedules
                 │
                 │ entries[].sequence_id ──→ sequences
                 │
                 │ bid_id (nullable) ←── awarded_schedules
```

- **users → bid_periods**: One user has many bid periods (one per month they bid).
- **bid_periods → sequences**: One bid period contains hundreds of parsed sequences.
- **bid_periods → bids**: A user may create multiple bid drafts per period; typically one is finalized.
- **bids.entries[] → sequences**: Each ranked entry references a sequence by ID.
- **awarded_schedules → bids**: An award is compared against a specific bid for analysis.
- **users → bookmarks → sequences**: Many-to-many favorites within a bid period.
- **bid_periods → filter_presets**: Saved filters scoped to a period or global.

---

## 4. Endpoint-to-Requirement Mapping

Every endpoint in `openapi.yaml` mapped to the requirement(s) it fulfills.

| Method | Endpoint | REQ IDs | Purpose |
|--------|----------|---------|---------|
| POST | `/auth/register` | REQ-008, REQ-025 | Create account with profile |
| POST | `/auth/login` | REQ-008, REQ-025 | Authenticate |
| GET | `/users/me` | REQ-008 | Retrieve profile + preferences |
| PUT | `/users/me` | REQ-008, REQ-009, REQ-010 | Update profile, seniority, languages |
| PUT | `/users/me/preferences` | REQ-009 | Update default scheduling preferences |
| POST | `/bid-periods` | REQ-001, REQ-002, REQ-022 | Upload bid sheet PDF, start async parse |
| GET | `/bid-periods` | REQ-019 | List all bid periods (history) |
| GET | `/bid-periods/{bidPeriodId}` | REQ-019, REQ-022 | Get bid period with parse status |
| DELETE | `/bid-periods/{bidPeriodId}` | REQ-019 | Delete bid period and all child data |
| PUT | `/bid-periods/{bidPeriodId}/preferences` | REQ-009 | Set per-period preference overrides |
| GET | `.../sequences` | REQ-005, REQ-006, REQ-010, REQ-047, REQ-051 | List/filter/sort sequences; commute_impact annotation; seq_number filter; commutable_only filter |
| POST | `.../sequences` | REQ-004 | Manually add a sequence |
| GET | `.../sequences/{sequenceId}` | REQ-007, REQ-003 | Full sequence detail (deadheads flagged) |
| PUT | `.../sequences/{sequenceId}` | REQ-004 | Edit a sequence |
| DELETE | `.../sequences/{sequenceId}` | REQ-004 | Delete a sequence |
| POST | `.../sequences/compare` | REQ-014 | Compare 2–5 sequences side by side |
| POST | `.../bids` | REQ-011, REQ-013 | Create a new bid (draft) |
| GET | `.../bids` | REQ-019 | List bids for this period |
| GET | `.../bids/{bidId}` | REQ-011, REQ-016 | Get bid with entries + summary |
| PUT | `.../bids/{bidId}` | REQ-013 | Reorder, pin, exclude entries |
| POST | `.../bids/{bidId}/optimize` | REQ-011, REQ-012, REQ-023 | Run strategic optimization |
| POST | `.../bids/{bidId}/export` | REQ-020 | Export ranked SEQ list as file |
| GET | `.../bids/{bidId}/summary` | REQ-016 | Get aggregate stats + date coverage |
| POST | `.../bookmarks` | REQ-021 | Bookmark a sequence |
| GET | `.../bookmarks` | REQ-021 | List bookmarks |
| DELETE | `.../bookmarks/{bookmarkId}` | REQ-021 | Remove a bookmark |
| POST | `.../filter-presets` | REQ-006 | Save a filter preset |
| GET | `.../filter-presets` | REQ-006 | List filter presets |
| DELETE | `.../filter-presets/{presetId}` | REQ-006 | Delete a filter preset |
| POST | `.../awarded-schedule` | REQ-017 | Import awarded schedule |
| GET | `.../awarded-schedule` | REQ-017 | Get awarded schedule |
| GET | `.../award-analysis` | REQ-018 | Bid-vs-award analysis |
| GET | `.../sequences/search/{seqNumber}` | REQ-051 | Find a single sequence by SEQ number |
| GET | `.../bids/{bidId}/projected` | REQ-050 | Projected schedules for all 7 layers |

All `.../` prefixes expand to `/bid-periods/{bidPeriodId}/`.

---

## 5. Technical Requirements

### 5.1 Backend

#### 5.1.1 API Layer

- RESTful HTTP API following OpenAPI 3.1 specification (see `openapi.yaml`)
- All endpoints return JSON; errors use a standard `{ code, message, details }` envelope
- Authentication via short-lived access tokens (JWT) with refresh token rotation
- All endpoints require authentication; every data query is scoped to the authenticated user's `user_id`
- Rate limiting: 100 requests/minute per user for standard endpoints; 5 requests/minute for PDF parsing and optimization (heavy compute)
- Request validation: all incoming payloads validated against JSON Schema before processing
- Pagination: list endpoints use cursor-based pagination (`page_state` token from Astra DB) with configurable `limit` (default 50, max 200)
- Sorting: list endpoints accept `sort_by` and `sort_order` query parameters
- Filtering: the sequence list endpoint accepts all filter parameters from REQ-006 as query parameters

#### 5.1.2 PDF Parsing Service

Handles REQ-001, REQ-002, REQ-003, REQ-022.

- Accepts multipart file upload of the bid sheet PDF
- Parsing runs **asynchronously**: upload returns immediately with `parse_status: "processing"`; the client polls `GET /bid-periods/{id}` to check progress
- The parser extracts all fields defined in the `sequences` collection schema:
  - Header: SEQ number, OPS count, POSN range, LANG type and count
  - Per duty period: DP number, D/A day counts, report/release times (local + base)
  - Per leg: flight number (with deadhead "D" suffix detection), equipment type, departure/arrival stations and times (local + base), meal code, PAX SVC code, block time, ground/connection time
  - Layovers: hotel name, hotel phone, transport company, transport phone, rest duration
  - Totals: block, SYNTH, TPAY, TAFB
  - Calendar: operating dates for the month
- **Category detection** reads page footer text (e.g., "ORD 777 INTL", "ORD NBD DOM") and assigns the `category` field
- **Deadhead detection** checks for "D" suffix on flight numbers; sets `is_deadhead` on legs and `has_deadhead` on sequences
- **Red-eye detection**: flags duty periods that touch 0100-0101 HBT per CBA §11.K (replacing the generic departure-time heuristic)
- **ODAN detection**: Flag sequences where all on-duty hours fall between 0100-0500 HBT with a single duty period
- **IPD/NIPD classification**: Based on destination stations and category footer (flights to/from Europe, Asia, Deep South America = IPD; other international = NIPD)
- **International duty type**: Classify by block time and duty period length per CBA §14.B
- **Holiday detection**: Cross-reference operating dates against CBA §3.K holiday list
- **Speaker sequence detection**: Flag sequences with LANG requirements
- **Turn detection**: sequences with exactly one duty period and no layover are flagged `is_turn`
- Performance: parse a 500-page PDF with up to 1,000 sequences within 30 seconds
- On failure: sets `parse_status: "failed"` with a human-readable `parse_error`

#### 5.1.3 Optimization Engine

The optimization engine is the core intelligence of the app. It does **not** simply sort sequences by preference score. It produces a **strategically ordered bid** that accounts for seniority competition, date conflicts, and coverage — per requirements Section 1.1 and REQ-011/REQ-012.

**Inputs:**
- All eligible sequences for the bid period (filtered by user's position and language qualifications)
- Merged preferences (user defaults + period overrides)
- User's seniority number and total FAs at base
- Pinned sequence IDs (with fixed ranks) and excluded sequence IDs
- Bid period date range

**Processing Phases:**

**Phase 1 — Preference Scoring**
Score each eligible, non-excluded sequence on a 0.0–1.0 scale using the user's weighted preferences:

| Criterion | Weight Source | Scoring Logic |
|-----------|-------------|---------------|
| TPAY alignment | `weights.tpay` | 1.0 if within target range; degrades proportionally outside |
| Days-off conflict | `weights.days_off` | 0.0 if sequence operates on a blocked day; 1.0 otherwise |
| Layover city | `weights.layover_city` | 1.0 for preferred city; 0.0 for avoided; 0.5 for neutral |
| Equipment | `weights.equipment` | 1.0 if preferred type; 0.5 otherwise |
| Report time | `weights.report_time` | 1.0 if within window; degrades by minutes outside |
| Release time | `weights.release_time` | Same as report |
| Red-eye | `weights.redeye` | 0.0 if is_redeye and avoid_redeyes enabled; 1.0 otherwise |
| Trip length | `weights.trip_length` | 1.0 if matches turn/multi-day preference; 0.5 otherwise |
| Clustering | `weights.clustering` | Evaluated in Phase 4 across the full bid |

Each criterion contributes `weight × score` to a weighted average. The result is `preference_score`.

**Phase 2 — Attainability Estimation**
Estimate how likely the FA is to be awarded each sequence, given their seniority standing:

- **Seniority percentile**: `seniority_number / total_base_fas` (e.g., 0.80 means 80th percentile, bottom 20%)
- **Competition proxy**: sequences with high OPS counts operate frequently and have more available slots, so they're easier to obtain. Sequences with low OPS (e.g., 1–2 OPS) are scarce and go to the most senior FAs.
- **Language restriction**: sequences requiring a specific language qualification (e.g., LANG JP) have a smaller pool of eligible bidders, increasing attainability for qualified FAs regardless of seniority.
- **Speaker sequence advantage**: for sequences requiring a Foreign Language Speaker (CBA §15), only Speaker-qualified FAs in that language can bid — significantly reduced competition pool. The attainability estimate is boosted for qualified Speakers.
- **Purser qualification**: IPD sequences with Purser positions have a restricted bidder pool (CBA §14.L — requires 18 months service, training, and 150h/year minimum). Purser-qualified FAs get an attainability boost.
- Output: each sequence is tagged `high`, `medium`, or `low` attainability.

A junior FA (high percentile number) bidding on a 1-OPS widebody international sequence with no language requirement would get `low`. The same FA bidding on a 25-OPS narrowbody domestic turn would get `high`.

**Phase 3 — Date Conflict Grouping**
Build conflict groups from `operating_dates`:

- Two sequences conflict if their `operating_dates` arrays share any element.
- Construct conflict groups: sets of mutually conflicting sequences that cover the same date slots.
- Assign each sequence a `date_conflict_group` ID.

Within each conflict group, the airline will award at most one sequence to the FA. The bid must rank the preferred option highest, with alternatives below it as fallbacks.

**Phase 4 — Strategic Ordering**
Combine preference score, attainability, and conflict groups into a final rank:

1. For each date conflict group, sort sequences by `preference_score × attainability_multiplier` (where high=1.0, medium=0.8, low=0.5).
2. Place the top sequence from each group in the bid. Group the rest as fallbacks immediately below.
3. Within the full bid, order groups by:
   - Highest preference score of the top sequence in each group
   - Attainability (prefer groups where the top pick is attainable)
4. Apply clustering optimization: if `cluster_trips` is enabled, reorder to minimize gaps between operating date blocks.
5. Preserve all pinned entries at their fixed ranks; weave optimized entries around them.

**Phase 4.5 — CBA Constraint Validation**
Before finalizing the ordering, validate the entire bid against CBA constraints:
1. Check that no 7-day window exceeds 30 block hours (Lineholder) or 35 block hours (Reserve), excluding deadhead time (CBA §11.B).
2. Check that no span exceeds 6 consecutive duty days without a 24-hour rest period (CBA §11.C).
3. Verify that the total credit hours fall within the Line of Time range (70–90h standard, or High/Low option bounds) (CBA §2.EE).
4. Verify minimum 11 calendar days off per month (CBA §11.H).
5. For each pair of consecutive sequences in a realistic award scenario, verify adequate rest between them (domestic: 11h home base; international: 12–48h depending on duty type per CBA §14.H).
6. Flag any violations in `summary.cba_violations[]` with human-readable descriptions referencing the CBA section.

**Phase 5 — Coverage Analysis**
After ordering, analyze date coverage:

- Compute `covered_dates`: union of `operating_dates` across all ranked (non-excluded) sequences.
- Compute `uncovered_dates`: bid period dates not in any ranked sequence.
- Compute `coverage_rate`: `|covered_dates| / total_dates`.
- If `coverage_rate` < 1.0, attach a warning: "Your bid does not cover dates [X, Y, Z]. You may be assigned reserve on those days. Consider adding sequences that operate on those dates."

**Output:**
- Ranked `entries[]` array with `rank`, `preference_score`, `attainability`, `date_conflict_group`, and `rationale` per entry
- Updated `summary` with date coverage stats
- Snapshot of `optimization_config`

**Performance target:** Optimize up to 1,000 sequences within 15 seconds (REQ-023).

#### 5.1.4 Data Access Layer

- All database operations go through the Astra DB JSON Data API (HTTP-based, document-oriented)
- Write operations use `insertOne`, `updateOne`, `deleteOne`
- Read operations use `find` with filter expressions, projection, sorting, and pagination via `page_state`
- Sequence list queries translate frontend filter parameters into Astra DB `$and`/`$or`/`$gte`/`$lte` filter expressions
- Denormalized fields (e.g., `seq_number` in bid entries, `layover_cities` at sequence root) avoid cross-collection joins at read time
- Bulk inserts for parsed sequences use batched `insertMany` (max 20 documents per batch per Astra DB limits)

#### 5.1.5 File Storage

- Uploaded bid sheet PDFs stored in an object store (S3-compatible)
- `bid_periods.source_file_url` references the stored file for re-parsing or download
- Exported bid files are generated on-demand and streamed; not persisted

#### 5.1.6 Security

- Passwords hashed with bcrypt or argon2 (REQ-025)
- All data access scoped to authenticated `user_id` — no cross-user data leakage
- Astra DB credentials stored in environment variables, never in code
- All traffic over HTTPS/TLS
- Input sanitization on all user-provided strings

#### 5.1.7 CBA Constraint Engine

A dedicated module that validates sequences and bid combinations against the American Airlines / APFA 2024 CBA rules. This engine is invoked during optimization (Phase 2.5) and can also be called independently for real-time validation as the user builds their bid.

**Duty Time Validation (CBA §11.E, §11.F, §14.D)**

- Domestic duty periods validated against the Section 11.E chart by report time (HBT) and segment count:
  - 0700-1259 HBT, 1-4 segments: max 13:15 scheduled
  - 0500-0559 / 1300-1659 HBT: max 12:15
  - 1700-2159 HBT: max 12:15 (2 seg) / 11:15 (3+ seg)
  - Block time capped at 8:59 per duty period (except single-DP, ≤2 live segments: max 14h duty)
- International duty periods classified and validated per CBA §14.D:
  - Non-Long Range: ≤14h scheduled, ≤16h actual, ≤12h block
  - Mid-Range: ≤15h scheduled, ≤17h actual, ≤12h block
  - Long Range: ≤16h scheduled, ≤18h actual, ≤14:15 block
  - Extended Long Range: ≤20h scheduled, 1 non-stop segment only

**Rest Validation (CBA §11.I, §11.J, §14.H, §14.I)**

- Domestic home base rest: ≥11h scheduled (10h actual ops)
- Domestic layover rest: ≥10h scheduled (8h behind-the-door minimum)
- International non-IPD home base rest: ≥12h (reducible 2h)
- IPD home base rest: ≥14:30
- Post long-range (>12h, ≤14:15 block): ≥36h home base rest
- Post extended long-range (>14:15 block): ≥48h home base rest (waivable to 24h)
- International non-IPD layover rest: ≥10h (8h behind-the-door)
- IPD layover rest: ≥14h

**Monthly Limits Validation (CBA §11.B, §11.C, §11.H, §2.EE)**

- 7-day rolling block hour check: ≤30h (Lineholder) / ≤35h (Reserve); deadhead excluded
- 6-consecutive-day check: 24h off required within every 7 consecutive days at crew base
- Minimum days off: ≥11 calendar days per month (Lineholder), prorated for partial months
- Credit hour range: 70–90h standard, 40–110h with High/Low Option per CBA §2.EE

**Compensation Estimation (CBA §3)**

- Base hourly rate by years of service (13-tier pay scale, effective dates 10/1/2024 through 10/1/2028)
- Guarantee calculation: greatest of actual flight time, duty rig (1:2), trip rig (1:3.50), or 5h × duty periods
- International premium: $3.00/hr (NIPD), $3.75/hr (IPD) per CBA §3.G
- Language speaker premium: $2.00/hr domestic, $5.00-$5.75/hr international per CBA §3.J
- Position premiums: Lead ($3.25-$6.50/hr), Purser ($5.75-$7.50/hr), Galley ($1.00-$2.00/hr) by aircraft type per CBA §3.C
- Holiday premium: 100% over base rate for CBA-defined holidays (Thanksgiving week, Christmas week, New Year's) per CBA §3.K
- Boarding pay: 50% of hourly rate, pay no credit per CBA §3.D

**ODAN Detection (CBA §2.II, §11.L)**

- Identifies ODAN sequences: single DP, all on-duty hours between 0100-0500 HBT
- Validates: max 14h scheduled duty, max 2 segments, max 2:30 block per segment, 5-9:59h pure rest break

**Red-Eye Classification (CBA §11.K)**

- CBA definition: duty period touching 0100-0101 HBT (replaces generic departure-time heuristic)
- Constraints: max 2 scheduled segments, max 1 aircraft connection in a red-eye DP
- Segment touching 0300 HBT triggers mandatory release for legal rest

#### 5.1.8 Commute Impact Analysis Service

A dedicated module (`commute.py`) that analyzes the feasibility of commuting to/from trips based on the FA's commute city. This is a critical feature for the ~40% of FAs who commute to their base.

**Commute Window Lookup**

A seed table of common commuter city-pair windows maps `(commute_from, base_city)` to:
- `first_arrival_minutes`: earliest feasible arrival at base on a first-available morning flight (e.g., DCA→ORD earliest arrival = 08:30 = 510min)
- `last_departure_minutes`: latest feasible departure from base to commute home (e.g., ORD→DCA last departure = 20:00 = 1200min)
- `flight_time_minutes`: approximate one-way flight time for gap calculations

Seeded for common pairs: DCA→ORD, DEN→ORD, LAX→ORD, ATL→ORD, SFO→ORD, BOS→ORD, MIA→ORD, etc. Unknown pairs use a conservative fallback (arrival 10:00, departure 18:00, 3h flight).

**Per-Sequence Analysis**

`analyze_commute_impact(sequence, commute_from, base_city)` computes:
- **First day**: Is first-day report time ≥ `first_arrival + 60min buffer`? If yes, same-day commute feasible. If not, hotel night required.
- **Last day**: Is last-day release time ≤ `last_departure - 90min buffer`? If yes, same-day return feasible. If not, hotel night required.
- **Impact level**: "green" (both feasible, comfortable margins), "yellow" (feasible but tight — within 30min of threshold), "red" (one or both require hotel night).
- Human-readable notes for both first and last day.

**Between-Trip Gap Analysis**

`analyze_commute_gap(release_minutes, report_minutes, gap_hours, commute_from, base_city)` determines whether there's time to commute home and back between consecutive sequences:
- Minimum viable gap = `2 × flight_time + 2h buffer + 8h sleep` (e.g., DCA→ORD: 2×2h + 2h + 8h = 14h)
- Returns `can_go_home: bool`, `gap_hours`, and a human-readable note.

**Integration Points**
- Sequence list/detail API: annotates each sequence with `commute_impact` when user has `commute_from` set
- Optimizer: after building each layer's schedule, runs gap analysis between consecutive sequences and populates `commute_warnings` in bid summary
- "Commutable Work Block" PBS property: uses commute windows to hard-filter sequences where first report and last release are within commute thresholds
- `commutable_only` query parameter on sequence list: pre-filters to green/yellow impact only

**REQ mapping:** REQ-047, REQ-048

#### 5.1.9 Projected Schedule Computation

After optimization, the system computes a "best case" projected schedule for each of the 7 layers. This answers the FA's core question: "If I get my top picks, what does my month look like?"

**Algorithm:**
1. For a given layer, take the bid entries sorted by rank.
2. Greedily select the highest-ranked sequence, then the next-highest that doesn't conflict on dates, and so on until adding more would exceed the credit hour maximum or no non-conflicting sequences remain.
3. Compute aggregate stats: total credit hours, working dates, off dates, days off count.
4. Classify schedule shape: "front-loaded" (trips concentrated in first half), "back-loaded" (second half), "balanced" (spread), or "block" (contiguous work block followed by contiguous off block).

**Output per layer:**
- Projected sequence list with key stats
- Total credit hours and within-range indicator
- Working vs. off date lists for calendar rendering
- Human-readable shape summary

**Endpoint:** `GET .../bids/{bidId}/projected` returns all 7 layers' projections. Also included in the optimize response payload.

**REQ mapping:** REQ-050

#### 5.1.10 Days-Off Boundary Enforcement

The `string_days_off_starting` and `string_days_off_ending` properties are treated as **hard exclusion filters** in the optimizer, not soft preferences.

**Behavior:**
- `string_days_off_starting` with value date D: any sequence whose `operating_dates` contains a date ≥ D is excluded from the candidate pool for that layer.
- `string_days_off_ending` with value date D: any sequence whose `operating_dates` contains a date ≤ D is excluded.
- The exclusion also considers date span: if a multi-day sequence starts before D but its duty days extend past D, it is excluded.
- If the remaining candidate pool after exclusion is insufficient to meet the target credit range, a warning is added to `summary.cba_violations`.

This ensures that when an FA says "days off starting Jan 16," no trips leak into the off-period.

**REQ mapping:** REQ-049

---

### 5.2 Frontend

#### 5.2.1 Core Views

| View | Description | REQ IDs |
|------|-------------|---------|
| **Onboarding / Profile Setup** | First-run wizard: base city, seniority number, total FAs at base, position, language quals, default preferences | REQ-008, REQ-009, REQ-024 |
| **Dashboard** | Active bid period summary, date coverage meter, days-off count, total TPAY, quick links to bid builder and calendar | REQ-016, REQ-019 |
| **Bid Period Manager** | Upload bid sheet, parsing progress bar, list past bid periods with stats | REQ-001, REQ-002, REQ-019, REQ-022 |
| **Sequence Browser** | Paginated sortable filterable table; advanced filter sidebar; filter preset save/load; eligibility badges; **SEQ # search box**; **commute impact badges** (green/yellow/red); **"Commutable Only" toggle** | REQ-005, REQ-006, REQ-010, REQ-047, REQ-051 |
| **Sequence Detail** | Full itinerary by duty day; legs with deadhead flags; layover hotel/transport; totals; mini-calendar of operating dates; **commute impact section** (first/last day feasibility, hotel nights, color-coded banner) | REQ-007, REQ-003, REQ-047 |
| **Sequence Comparison** | Side-by-side 2–5 sequences; highlighted diffs; inline bid rank adjustment | REQ-014 |
| **Bid Builder** | The primary screen. Ranked drag-and-drop list with: pin/exclude controls, preference score bar, attainability badge (high/med/low), date conflict group indicators, rationale tooltip per entry. Date coverage meter at top. "Optimize" button. Excluded sequences section. **Projected Schedule panel** (per-layer best-case line with mini-calendar, credit hours, days off). **Commute warnings** in summary. **Layer pairing browser** ("Browse Pairings" button per layer in Step 1). **Bulk layer assignment** ("All" toggle, shift-click range). | REQ-011, REQ-012, REQ-013, REQ-047, REQ-050, REQ-052, REQ-054 |
| **Calendar View** | Monthly calendar; sequences as date-spanning bars; color-coded by category; conflict indicators; uncovered dates highlighted in red; tap-to-detail; **commute indicator dots** on first/last day of each sequence | REQ-015, REQ-047 |
| **Export** | Preview ranked SEQ list; choose format; confirm and download | REQ-020 |
| **Awarded Schedule** | Import award; calendar view of awarded sequences; bid-vs-award analysis: match rate, attainability accuracy, insights | REQ-017, REQ-018 |
| **Bid History** | Past bid periods listed by date; drill into any past bid, preferences, and award analysis | REQ-019 |
| **Glossary** | Searchable airline terminology definitions; linked via tooltips throughout the app | REQ-024 |

#### 5.2.2 Interaction Patterns

**Sequence Browser**
- **SEQ # search box** at the top of the filter panel: type a sequence number, hit Enter, and navigate directly to that sequence's detail page (or show "Sequence not found" inline). Also accessible as a global quick-find modal from the header search icon (available on Bid Builder and Calendar pages too).
- Collapsible filter sidebar; changing any filter triggers a debounced (200ms) API call; result count badge updates immediately
- Each row shows an eligibility indicator: green check (eligible), yellow warning (eligible but no language advantage), red X (ineligible by position or language)
- **Commute impact badge** (green/yellow/red circle) in each row when user has `commute_from` set; tooltip shows first_day_note and last_day_note. "Commutable Only" toggle filter at top of filter panel.
- Star icon toggles bookmark; checkbox enables multi-select for comparison

**Bid Builder (central screen)**
- **Date coverage meter** at the top: a progress bar showing what percentage of the bid period's dates are covered by ranked sequences. Uncovered dates listed below with a warning.
- **Ranked list**: drag handle to reorder; lock icon to pin; X to exclude; each entry shows SEQ number, key stats (TPAY, TAFB, layover), preference score bar (0–100%), attainability badge, and date conflict group color.
- **Date conflict grouping**: sequences sharing a conflict group have a matching colored sidebar stripe. Within a group, the highest-ranked is the "primary pick" and lower ones show "fallback" labels. This makes it clear that these are alternatives for the same dates.
- **Rationale tooltip**: hovering or tapping an entry shows the optimizer's explanation (e.g., "Ranked #3: TPAY 18:37 in target range, NRT layover preferred, LANG JP restricts competition — attainability high").
- **Optimize button**: triggers the optimization engine; shows loading state; on completion the list animates to new order with changes highlighted.
- **Coverage warning**: if uncovered dates exist after optimization, a banner suggests sequences that fill the gaps.
- **Projected Schedule panel**: after optimization, a tab/section above layer cards shows the "best case" projected line for the selected layer. Includes: summary line ("5 trips, 82.5 credit hours, 14 days off"), mini-calendar with working days filled and off days clear, credit hour indicator (green/yellow/red vs. line range), and a list of projected sequences. Layer selector (L1-L7) to switch projections.
- **Commute warnings**: if user has `commute_from` set, commute impact badges (green/yellow/red) appear on each bid entry. Back-to-back trip gaps too short for commuting are flagged in summary.
- **Layer pairing browser**: in Step 1 (Configure Properties), each layer in the LayerSummaryPanel has a "Browse Pairings" button. Clicking opens a modal showing the filtered sequence list for that layer's pairing properties. Empty state includes suggestions (e.g., "No IPD sequences matched — try removing the Pairing Type filter").
- **Bulk layer assignment**: each property row in the PropertyCatalog has an "All" toggle next to the layer buttons (1-7) that assigns/deassigns all 7 layers in one click. Shift-click on layer buttons selects a range (e.g., click 1 then shift-click 5 selects 1-5).

**Calendar View**
- Sequences rendered as horizontal bars on their operating dates
- Color-coded by category (international = blue, domestic = green, turns = gray)
- Uncovered dates highlighted with a red diagonal hatch pattern
- Overlapping sequences (date conflicts) stacked with a conflict icon
- Tapping a sequence opens its detail; long-press/right-click to pin, exclude, or compare
- Drag a sequence off the calendar to exclude it

**Tooltips / Glossary**
- Every domain term (SEQ, TPAY, TAFB, SYNTH, POSN, OPS, etc.) is a dotted-underline link; hover shows definition
- Persistent glossary page searchable by keyword

**Awarded Schedule Analysis**
- After importing an award, the analysis view shows:
  - Match rate: "5 of your top 10 picks were awarded"
  - Attainability accuracy: "12 of 15 sequences marked 'high' were awarded" — validates the optimizer
  - Surprises: sequences marked "low" that were awarded, or "high" that weren't
  - Insights: plain-language observations (e.g., "Your seniority was competitive for NBI sequences but not 777 widebody")
- This feedback loop helps the FA calibrate seniority and preferences for next month

#### 5.2.3 Offline Support

- After import, all sequence data for the active bid period is cached locally (REQ-027)
- Preferences and bid list changes made offline are queued and synced on reconnection
- Online/offline indicator in the app header
- Optimization requires connectivity (server-side compute); a clear message is shown if attempted offline

#### 5.2.4 Responsiveness & Accessibility

- Desktop-first layout; tablet-responsive; mobile is read-only browsing (REQ-026)
- All interactive elements keyboard-navigable with visible focus rings
- Data tables support screen-reader row/column navigation via ARIA roles
- Color contrast meets WCAG 2.1 AA; icons and labels supplement all color-coding
- Drag-and-drop bid list also supports keyboard reordering (arrow keys + Enter)

#### 5.2.5 State Management

- **Global state**: authenticated user (with seniority), active bid period, current bid, cached sequence index
- **Sequence browser**: server-driven pagination with local filter/sort UI state
- **Bid builder**: optimistic updates — local reorder/pin/exclude reflected immediately, persisted to server in background
- **Offline queue**: pending mutations stored as ordered operations; replayed sequentially on reconnect with conflict detection

#### 5.2.6 Error Handling

- API errors: user-friendly toast notifications using the `message` from the error envelope
- PDF parsing failures: detailed error screen with guidance on supported formats
- Optimization failures: error displayed in the bid builder with a retry option
- Network errors: offline banner; mutations queued for retry
- Form validation: inline errors next to relevant fields

#### 5.2.7 Form Input Usability (REQ-053, REQ-054)

All form inputs must accept direct keyboard entry without workarounds:

- **Number inputs** (credit range, seniority, etc.): Standard `<input type="number">` that allows click-to-focus, clear, and direct typing. No `onKeyDown` handlers that prevent character input. Arrow keys are optional, not required.
- **Time inputs** (report between, release between): `<input type="time">` with native typing support. No JavaScript `nativeInputValueSetter` workarounds. Both typing and picker selection fire `onChange`.
- **Date inputs**: `<input type="date">` with native typing support.
- **Tab navigation**: logical field order across all forms.

**Bulk layer assignment** in PropertyCatalog:
- "All" toggle button next to layer buttons (1-7): one click assigns property to all layers, another click deselects all.
- Shift-click range selection: click layer 1, then shift-click layer 5 selects 1-5.
- Reduces the 6-click tedium reported in UX testing to 1 click.

---

## 6. Requirement Coverage Matrix

Every REQ-ID from `requirements.md` is covered by at least one collection, endpoint, or frontend view.

| REQ ID | Description | Collections | Endpoints | Frontend Views |
|--------|------------|-------------|-----------|----------------|
| REQ-001 | Import Bid Sheet from PDF | bid_periods, sequences | POST /bid-periods | Bid Period Manager |
| REQ-002 | Sequence Category Detection | sequences | POST /bid-periods | Sequence Browser (category filter) |
| REQ-003 | Deadhead Leg Identification | sequences (is_deadhead) | GET .../sequences/{id} | Sequence Detail |
| REQ-004 | Manual Sequence Entry/Editing | sequences | POST/PUT/DELETE .../sequences | Sequence Detail (edit) |
| REQ-005 | Sequence List View | sequences | GET .../sequences | Sequence Browser |
| REQ-006 | Advanced Filtering | sequences, filter_presets | GET .../sequences, .../filter-presets | Sequence Browser (filter panel) |
| REQ-007 | Sequence Detail View | sequences | GET .../sequences/{id} | Sequence Detail |
| REQ-008 | User Profile | users | /auth/register, /users/me | Onboarding, Profile |
| REQ-009 | Scheduling Preferences | users, bid_periods | PUT /users/me/preferences, PUT .../preferences | Preferences screen |
| REQ-010 | Language & Position Eligibility | users, sequences | GET .../sequences (eligible_only) | Sequence Browser (badges) |
| REQ-011 | Generate Optimized Bid | bids | POST .../bids/{id}/optimize | Bid Builder |
| REQ-012 | Constraint Enforcement | bids | POST .../bids/{id}/optimize | Bid Builder (warnings) |
| REQ-013 | Manual Bid Adjustment | bids | PUT .../bids/{id} | Bid Builder (drag/pin/exclude) |
| REQ-014 | Side-by-Side Comparison | sequences | POST .../sequences/compare | Sequence Comparison |
| REQ-015 | Monthly Calendar View | bids, sequences | GET .../bids/{id} | Calendar View |
| REQ-016 | Monthly Summary Dashboard | bids | GET .../bids/{id}/summary | Dashboard |
| REQ-017 | Import Awarded Schedule | awarded_schedules | POST .../awarded-schedule | Awarded Schedule |
| REQ-018 | Bid vs. Award Analysis | awarded_schedules | GET .../award-analysis | Awarded Schedule (analysis) |
| REQ-019 | Bid History | bid_periods, bids, awarded_schedules | GET /bid-periods | Bid History |
| REQ-020 | Export Bid | bids | POST .../bids/{id}/export | Export |
| REQ-021 | Bookmark / Favorites | bookmarks | POST/GET/DELETE .../bookmarks | Sequence Browser (star) |
| REQ-022 | Performance — Parsing | bid_periods | POST /bid-periods | Bid Period Manager (progress) |
| REQ-023 | Performance — Optimization | bids | POST .../bids/{id}/optimize | Bid Builder (loading) |
| REQ-024 | Usability | — | — | All views (tooltips, glossary) |
| REQ-025 | Data Privacy | users | All authenticated endpoints | — |
| REQ-026 | Accessibility | — | — | All views (ARIA, keyboard, contrast) |
| REQ-027 | Offline Capability | — | — | Offline cache + sync queue |
| REQ-028 | Multi-Airline Adaptability | bid_periods, sequences | POST /bid-periods | Bid Period Manager (airline config) |
| REQ-029 | CBA Duty Time Validation (Domestic) | sequences | POST .../bids/{id}/optimize | Bid Builder (violations) |
| REQ-030 | CBA Duty Time Validation (International) | sequences | POST .../bids/{id}/optimize | Bid Builder (violations) |
| REQ-031 | CBA Domestic Rest Validation | sequences | POST .../bids/{id}/optimize | Bid Builder (violations) |
| REQ-032 | CBA International Rest Validation | sequences | POST .../bids/{id}/optimize | Bid Builder (violations) |
| REQ-033 | 7-Day Rolling Block Hour Check | bids | POST .../bids/{id}/optimize | Bid Builder (violations) |
| REQ-034 | 6-Consecutive-Day Duty Limit | bids | POST .../bids/{id}/optimize | Bid Builder (violations) |
| REQ-035 | Minimum Days Off Per Month | bids | POST .../bids/{id}/optimize | Bid Builder (violations) |
| REQ-036 | Credit Hour Range (Line of Time) | bids, users | POST .../bids/{id}/optimize | Bid Builder (summary) |
| REQ-037 | Compensation Estimation | sequences, bids | POST .../bids/{id}/optimize, GET .../sequences | Sequence Browser, Bid Builder |
| REQ-038 | International Premium Detection (IPD/NIPD) | sequences | POST /bid-periods | Sequence Browser (badges) |
| REQ-039 | ODAN Sequence Detection | sequences | POST /bid-periods | Sequence Browser, Sequence Detail |
| REQ-040 | Red-Eye CBA Classification | sequences | POST /bid-periods | Sequence Browser, Sequence Detail |
| REQ-041 | Holiday Sequence Detection | sequences | POST /bid-periods | Sequence Browser (badges), Calendar View |
| REQ-042 | Speaker Sequence Detection | sequences | POST /bid-periods | Sequence Browser (badges) |
| REQ-043 | Duty Rig / Trip Rig Calculation | sequences | POST /bid-periods | Sequence Detail (totals) |
| REQ-044 | Purser Qualification Attainability | users, sequences | POST .../bids/{id}/optimize | Bid Builder (attainability) |
| REQ-045 | Speaker Attainability Boost | users, sequences | POST .../bids/{id}/optimize | Bid Builder (attainability) |
| REQ-046 | CBA Violation Reporting | bids | POST .../bids/{id}/optimize, GET .../bids/{id}/summary | Bid Builder (violations banner) |
| REQ-047 | Per-Trip Commute Impact Annotations | users (commute_from), sequences (computed) | GET .../sequences, GET .../sequences/{id}, POST .../bids/{id}/optimize | Sequence Browser (commute badges), Sequence Detail (commute section), Calendar (commute dots), Bid Builder (commute warnings), Profile (commute_from field) |
| REQ-048 | Commutable Work Block Enforcement | users (commute_from) | POST .../bids/{id}/optimize | Bid Builder (property-based filtering) |
| REQ-049 | Days-Off Boundary Enforcement | bids (properties) | POST .../bids/{id}/optimize | Bid Builder (hard exclusion in optimizer), Calendar (contiguous off-block) |
| REQ-050 | Projected Schedule Preview | bids (projected_schedules) | GET .../bids/{id}/projected, POST .../bids/{id}/optimize | Bid Builder (projected schedule panel with mini-calendar) |
| REQ-051 | Sequence Number Direct Search | sequences | GET .../sequences (seq_number param), GET .../sequences/search/{seqNumber} | Sequence Browser (search box), Layout (global quick-find) |
| REQ-052 | Layer Pairing Browser | sequences, bids (properties) | GET .../sequences (with layer filter params) | Bid Builder Step 1 (Browse Pairings modal per layer) |
| REQ-053 | Form Input Usability | — | — | PropertyValueEditor (number/time/date inputs accept direct typing) |
| REQ-054 | Bulk Layer Assignment | — | — | PropertyCatalog ("All" toggle, shift-click range selection) |
| REQ-055 | IPD Pairing Type Filter Accuracy | sequences (is_ipd) | GET .../sequences, POST .../bids/{id}/optimize | Sequence Browser (IPD filter), Bid Builder (layer filtering) |
