# Scheduling App — Implementation Tasks

> Phases 1–7 (backend + initial frontend) are complete. Phases 8–12 cover gaps identified against design.md, requirements.md, and openapi.yaml. Phases 13–14 integrate the AA/APFA 2024 CBA.
>
> **Rule: Complete and fully test each task before starting the next.**

## Phase 1–7: Core Build ✅

All 28 original tasks complete — FastAPI backend (35 endpoints), PDF parser, 5-phase optimizer, Astra DB integration, 16 test files, and React frontend with 11 pages.

---

## Phase 8: Frontend Feature Gaps ✅

- [x] **Task 29** — Sequence comparison page (SequenceComparisonPage.tsx) with multi-select checkboxes and side-by-side diff highlighting.
- [x] **Task 30** — Filter presets UI: save/load/delete presets in SequenceBrowserPage filter sidebar.
- [x] **Task 31** — Bookmark/favorites integration: star toggles, favorites filter button, count badge.
- [x] **Task 32** — Export preview page (ExportPage.tsx): ranked list preview, format selection, confirm-and-download.
- [x] **Task 33** — Bid history view (BidHistoryPage.tsx): past bid periods with summary stats and drill-down links.
- [x] **Task 34** — Glossary page (GlossaryPage.tsx) + GlossaryTooltip component with keyboard-accessible hover tooltips.
- [x] **Task 35** — Onboarding wizard: 3-step registration (Account → Profile → Preferences) in RegisterPage.tsx.

## Phase 9: Frontend UX Polish ✅

- [x] **Task 36** — Bid builder enhancements: coverage progress bar, conflict group labels, rationale tooltips, coverage warnings.
- [x] **Task 37** — Calendar view enhancements: category color-coding, red diagonal hatch on uncovered dates, conflict indicators, click-to-navigate.
- [x] **Task 38** — Sequence browser enhancements: eligibility badges, collapsible debounced filters, multi-select checkboxes.
- [x] **Task 39** — Awarded schedule analysis: attainability accuracy bars, surprise sequence highlighting, recalibration suggestions.

## Phase 10: Backend Hardening ✅

- [x] **Task 40** — Refresh token rotation: `POST /auth/refresh` endpoint with token type validation and separate decode function.
- [x] **Task 41** — Rate limiting: RateLimitMiddleware (100/min standard, 5/min heavy), TESTING env bypass, 429 responses with X-RateLimit-Remaining header.
- [x] **Task 42** — Request validation: Pydantic models cover all OpenAPI spec payloads with field validators.
- [x] **Task 43** — PDF file storage: uploaded PDFs saved to `uploads/{user_id}/{bid_period_id}.pdf` with source_filename tracking.
- [x] **Task 44** — Input sanitization: Pydantic `@field_validator` decorators strip HTML tags and null bytes on ProfileInput and FilterPresetInput.

## Phase 11: Non-Functional Requirements ✅

- [x] **Task 45** — Offline support (REQ-027): localStorage caching in API interceptor, mutation queue for offline writes, OnlineStatus component with aria-live, integrated into Layout navbar.
- [x] **Task 46** — Accessibility audit (REQ-026): skip-to-content link, ARIA labels on all icon buttons, scope attributes on table headers, keyboard-navigable sort headers, role="status" on OnlineStatus, role="tooltip" on glossary terms, role="tab" on bid tabs, role="grid" on calendar, role="list" on bid entries.
- [x] **Task 47** — Responsive design audit: mobile hamburger menu in Layout, responsive grids (1-col mobile → multi-col desktop), responsive calendar (4-col mobile → 7-col desktop), responsive comparison table padding, step indicator mobile labels hidden, filter grid 1-col mobile.
- [x] **Task 48** — Multi-airline adaptability (REQ-028): AirlineConfig dataclass with all regex patterns + scheduling rules, configurable parser via `airline_code` parameter, config registry with register/list/get, `GET /airlines` endpoint, `airline_code` form parameter on bid period creation.

## Phase 12: Testing & Quality

- [x] **Task 49** — Frontend tests: vitest + @testing-library/react + jsdom setup. 26 tests across 4 test files (offline utilities, OnlineStatus, GlossaryTooltip, GlossaryPage). Backend: 255 tests (7 new airline config tests).
- [ ] **Task 50** — End-to-end tests: full user flows (register → upload PDF → browse → optimize → export) using Playwright or Cypress.
- [x] **Task 51** — PDF parser validation: tested against real ORDSEQ2601.pdf (447 pages, 1705 sequences). Fixed U+2212 minus sign handling — operating dates extraction improved from 16% to 80%. Layover cities now extracted. Added x_tolerance/y_tolerance optimization.
- [ ] **Task 52** — Performance testing: PDF parsing currently ~67s for 447 pages (target: <30s for 500 pages per REQ-022). Bottleneck is pdfplumber text extraction. Text parsing itself is 0.14s. Optimization < 15s for 1,000 sequences not yet measured.

---

## Phase 13: CBA Data Model & Backend (AA/APFA 2024)

> Integration of American Airlines / APFA 2024 Collective Bargaining Agreement rules. All CBA section references correspond to the agreement effective Sept 12, 2024 through Sept 11, 2029.
>
> Each task is atomic. Complete it, write tests, run the full test suite, and confirm green before moving on.

### Task 53 — Add CBA profile fields to User model ✅

Add four new fields to `Profile` in `app/models/schemas.py`:
- `years_of_service: Optional[int] = None` — for CBA §3.A pay rate lookup (1–13+)
- `is_reserve: bool = False` — Reserve vs Lineholder status
- `is_purser_qualified: bool = False` — Purser qualification per CBA §14.L
- `line_option: str = "standard"` — enum: standard | high | low per CBA §2.EE

**Files:** `app/models/schemas.py`
**Test:** Add tests in `tests/test_models.py` that:
1. Validate a Profile with all 4 new fields set
2. Validate defaults (is_reserve=False, line_option="standard", etc.)
3. Validate line_option rejects invalid values
**Verify:** `cd backend && python -m pytest tests/test_models.py -v`

---

### Task 54 — Add CBA profile fields to user API routes ✅

Update `app/routes/users.py` so `PUT /users/me` accepts and persists the 4 new profile fields. Update `POST /auth/register` so `ProfileInput` includes the new fields.

**Files:** `app/routes/users.py`, `app/routes/auth.py`
**Test:** Add tests in `tests/test_users.py` that:
1. Register a user with `years_of_service=5, is_reserve=True, line_option="high"`
2. Update profile to change `is_purser_qualified=True`
3. GET `/users/me` returns all new fields
**Verify:** `cd backend && python -m pytest tests/test_users.py tests/test_auth.py -v`

---

### Task 55 — Add CBA classification fields to Sequence model ✅

Add six new fields to `Sequence` in `app/models/schemas.py`:
- `is_odan: bool = False` — On-Duty All-Nighter (CBA §2.II)
- `international_duty_type: Optional[str] = None` — enum: non_long_range | mid_range | long_range | extended_long_range (CBA §14.B)
- `is_ipd: bool = False` — International Premium Destination (CBA §14.B)
- `is_nipd: bool = False` — Non-International Premium Destination
- `has_holiday: bool = False` — operates on CBA §3.K holiday
- `is_speaker_sequence: bool = False` — requires Foreign Language Speaker (CBA §15)

**Files:** `app/models/schemas.py`
**Test:** Add tests in `tests/test_models.py` that:
1. Validate a Sequence with all 6 new fields set
2. Validate defaults are all False/None
3. Validate international_duty_type rejects invalid enum values
**Verify:** `cd backend && python -m pytest tests/test_models.py -v`

---

### Task 56 — Add pay/rig fields to SequenceTotals model ✅

Add three new fields to `SequenceTotals` in `app/models/schemas.py`:
- `duty_rig_minutes: int = 0` — Duty Rig guarantee (1hr per 2hr on-duty, CBA §2.P)
- `trip_rig_minutes: int = 0` — Trip Rig guarantee (1hr per 3:30 TAFB, CBA §2.AAA)
- `estimated_pay_cents: int = 0` — estimated total compensation in cents

**Files:** `app/models/schemas.py`
**Test:** Add tests in `tests/test_models.py` that:
1. Validate SequenceTotals with the 3 new fields
2. Validate defaults are 0
**Verify:** `cd backend && python -m pytest tests/test_models.py -v`

---

### Task 57 — Add CBA summary fields to BidSummary model ✅

Add seven new fields to `BidSummary` in `app/models/schemas.py`:
- `total_credit_hours: float = 0.0`
- `line_option: str = "standard"`
- `line_min_hours: int = 70`
- `line_max_hours: int = 90`
- `credit_hour_utilization: float = 0.0`
- `estimated_total_pay_cents: int = 0`
- `cba_violations: List[str] = []`

**Files:** `app/models/schemas.py`
**Test:** Add tests in `tests/test_models.py` that:
1. Validate BidSummary with all 7 new fields
2. Validate line_min/max defaults to 70/90
3. Validate cba_violations is an empty list by default
**Verify:** `cd backend && python -m pytest tests/test_models.py -v`

---

### Task 58 — Add CBAViolation and CBAValidationResult models ✅

Create new Pydantic models in `app/models/schemas.py`:
- `CBAViolation(rule: str, severity: str, message: str, affected_dates: List[int], affected_sequences: List[int])`
- `CreditHourSummary(estimated_credit_hours: float, line_min: int, line_max: int, within_range: bool)`
- `DaysOffSummary(total_days_off: int, minimum_required: int, meets_requirement: bool)`
- `CBAValidationResult(is_valid: bool, violations: List[CBAViolation], credit_hour_summary: CreditHourSummary, days_off_summary: DaysOffSummary)`

**Files:** `app/models/schemas.py`
**Test:** Add tests in `tests/test_models.py` that:
1. Construct a CBAValidationResult with 0 violations → is_valid=True
2. Construct one with 2 violations → verify serialization
3. Validate severity accepts only "error" or "warning"
**Verify:** `cd backend && python -m pytest tests/test_models.py -v`

---

### Task 59 — Implement CBA pay rate lookup table ✅

Create `app/services/cba_pay.py` with a single function:
- `get_hourly_rate(years_of_service: int, effective_date: date) -> float` — returns the hourly rate in dollars from the CBA §3.A pay scale (13 tiers × 5 effective dates: 10/1/2024, 10/1/2025, 10/1/2026, 10/1/2027, 10/1/2028)

Store the full pay table as a constant dict. The function selects the correct rate based on years and the most recent effective date ≤ the given date.

**Files:** `app/services/cba_pay.py` (new)
**Test:** Create `tests/test_cba_pay.py` with tests:
1. 1st year FA on 10/1/2024 → $35.82
2. 13th year FA on 10/1/2028 → $92.79
3. 5th year FA on 10/1/2026 → $50.15
4. Date before 10/1/2024 → uses 10/1/2024 rates (floor)
5. Years > 13 → uses 13th year rate
**Verify:** `cd backend && python -m pytest tests/test_cba_pay.py -v`

---

### Task 60 — Implement Duty Rig and Trip Rig calculators ✅

Add to `app/services/cba_pay.py`:
- `calc_duty_rig(on_duty_minutes: int) -> int` — returns credited minutes: 1 hour per 2 hours on-duty, prorated minute-by-minute (CBA §2.P). Formula: `on_duty_minutes / 2`.
- `calc_trip_rig(tafb_minutes: int) -> int` — returns credited minutes: 1 hour per 3 hours 30 minutes TAFB, prorated (CBA §2.AAA). Formula: `tafb_minutes / 3.5`.
- `calc_sit_rig(sit_minutes: int) -> int` — returns credited minutes for sit times >150min (2:30): 1 min per 2 min in excess of 150. Returns 0 if sit_minutes ≤ 150 (CBA §11.D.5).
- `calc_sequence_guarantee(block_minutes: int, duty_rig_minutes: int, trip_rig_minutes: int, duty_period_count: int) -> int` — returns the greatest of: block, duty rig, trip rig, or 5h × duty periods (with min 3h/DP for multi-DP sequences) per CBA §11.D.

**Files:** `app/services/cba_pay.py`
**Test:** Add to `tests/test_cba_pay.py`:
1. Duty rig: 600min on-duty → 300min credited
2. Trip rig: 2100min TAFB (35h) → 600min (10h)
3. Sit rig: 180min → 15min; 120min → 0min
4. Guarantee: block=400, duty_rig=350, trip_rig=420, 2 DPs → max(400, 350, 420, 600) = 600
5. Guarantee: block=700, duty_rig=500, trip_rig=600, 1 DP → max(700, 500, 600, 300) = 700
**Verify:** `cd backend && python -m pytest tests/test_cba_pay.py -v`

---

### Task 61 — Implement position and international premium calculators ✅

Add to `app/services/cba_pay.py`:
- `get_position_premium(position: str, aircraft_type: str, is_international: bool, is_ipd: bool) -> float` — returns hourly premium in dollars for Lead/Purser/Galley by aircraft type per CBA §3.C table. `position` is one of: "lead", "purser", "galley". Returns 0.0 for non-premium positions.
- `get_international_premium(is_ipd: bool, is_nipd: bool) -> float` — returns $3.75/hr for IPD, $3.00/hr for NIPD, $0 for domestic per CBA §3.G.
- `get_speaker_premium(is_international: bool, is_ipd: bool) -> float` — returns $2.00/hr domestic, $5.00/hr international (NIPD), $5.75/hr international (IPD) per CBA §3.J.

**Files:** `app/services/cba_pay.py`
**Test:** Add to `tests/test_cba_pay.py`:
1. Lead on B777 domestic → $3.25/hr
2. Purser on B777 IPD → $7.50/hr
3. Galley on B787 IPD → $2.00/hr
4. NIPD international premium → $3.00
5. IPD international premium → $3.75
6. Domestic speaker premium → $2.00; IPD speaker → $5.75
**Verify:** `cd backend && python -m pytest tests/test_cba_pay.py -v`

---

### Task 62 — Implement holiday date detection ✅

Add to `app/services/cba_pay.py`:
- `get_holiday_dates(year: int, month: int) -> List[int]` — returns day-of-month integers that are CBA §3.K holidays within the given month. Holidays: Wed before Thanksgiving, Thanksgiving Day, Sun after Thanksgiving, Mon after Thanksgiving, Dec 24, Dec 25, Dec 26, Dec 31, Jan 1.
- `is_holiday(year: int, month: int, day: int) -> bool` — convenience wrapper.

**Files:** `app/services/cba_pay.py`
**Test:** Add to `tests/test_cba_pay.py`:
1. November 2025: Thanksgiving is Nov 27 → holidays = [26, 27, 30] (Wed=26, Thu=27, Sun=30, Mon Dec 1 not in Nov)
2. December 2025: holidays = [1, 24, 25, 26, 31] (Mon after Thanksgiving=Dec 1)
3. January 2026: holidays = [1]
4. July 2025: holidays = [] (no holidays)
**Verify:** `cd backend && python -m pytest tests/test_cba_pay.py -v`

---

### Task 63 — Implement full sequence pay estimator ✅

Add to `app/services/cba_pay.py`:
- `estimate_sequence_pay(sequence: Sequence, years_of_service: int, effective_date: date, position: Optional[str] = None, is_speaker: bool = False) -> dict` — returns `{"base_pay_cents": int, "duty_rig_cents": int, "trip_rig_cents": int, "guarantee_cents": int, "international_premium_cents": int, "speaker_premium_cents": int, "position_premium_cents": int, "holiday_premium_cents": int, "total_cents": int}`.

Uses the functions from Tasks 59–62. The `total_cents` is the sum of all premiums applied on top of the guarantee value.

**Files:** `app/services/cba_pay.py`
**Test:** Add to `tests/test_cba_pay.py`:
1. Simple domestic turn: 1 DP, 5h block, 1st year FA → base = 5h × $35.82 = $179.10 = 17910 cents
2. International IPD sequence: 2 DP, 8h block, 5th year FA, Purser → verify international + Purser premiums applied
3. Speaker sequence on holiday: verify all premiums stack
4. Duty rig > block: 2h block, 6h on-duty → rig = 3h, rig wins
**Verify:** `cd backend && python -m pytest tests/test_cba_pay.py -v`

---

### Task 64 — Implement domestic duty time chart lookup ✅

Create `app/services/cba_rules.py` with:
- `DOMESTIC_DUTY_CHART: dict` — the CBA §11.E lookup table mapping (report_time_range, segment_count) → max_scheduled_duty_minutes. Report time ranges: 0000-0359, 0400-0459, 0500-0559, 0600-0659, 0700-1259, 1300-1659, 1700-2159, 2200-2259, 2300-2359. Segment counts: 1 through 7+.
- `get_max_domestic_duty(report_hbt_minutes: int, segment_count: int) -> int` — returns max scheduled duty minutes from the chart.
- `DOMESTIC_ACTUAL_OPS_CHART: dict` — CBA §11.F: report time range → (rescheduled_max_minutes, operational_max_minutes).
- `get_max_domestic_actual_duty(report_hbt_minutes: int) -> tuple[int, int]` — returns (rescheduled_max, operational_max).

**Files:** `app/services/cba_rules.py` (new)
**Test:** Create `tests/test_cba_rules.py`:
1. 0730 HBT, 3 segments → 13:15 (795 min)
2. 0530 HBT, 6 segments → 11:15 (675 min)
3. 1800 HBT, 4 segments → 11:15 (675 min)
4. 0100 HBT, 1 segment → 9:15 (555 min)
5. Actual ops: 0600 HBT → rescheduled 13:15, operational 15:00
6. Actual ops: 1800 HBT → rescheduled 12:15, operational 13:00
**Verify:** `cd backend && python -m pytest tests/test_cba_rules.py -v`

---

### Task 65 — Implement international duty type classifier ✅

Add to `app/services/cba_rules.py`:
- `classify_international_duty(max_block_minutes: int, scheduled_duty_minutes: int) -> Optional[str]` — returns one of: `"non_long_range"` (≤720 block, ≤840 duty), `"mid_range"` (≤720 block, 841–900 duty), `"long_range"` (721–855 block, ≤960 duty), `"extended_long_range"` (>855 block, ≤1200 duty), or `None` if not international.
- `get_intl_duty_limits(duty_type: str) -> dict` — returns `{"max_scheduled_minutes": int, "max_actual_minutes": int, "max_block_minutes": int}` per CBA §14.D.

**Files:** `app/services/cba_rules.py`
**Test:** Add to `tests/test_cba_rules.py`:
1. 600min block, 800min duty → non_long_range
2. 700min block, 870min duty → mid_range
3. 780min block, 900min duty → long_range
4. 900min block, 1100min duty → extended_long_range
5. Limits for non_long_range → scheduled=840, actual=960, block=720
6. Limits for long_range → scheduled=960, actual=1080, block=855
**Verify:** `cd backend && python -m pytest tests/test_cba_rules.py -v`

---

### Task 66 — Implement rest requirement lookup ✅

Add to `app/services/cba_rules.py`:
- `get_home_base_rest(is_ipd: bool, is_international: bool, max_block_minutes: int) -> int` — returns minimum home base rest in minutes per CBA §11.I, §14.H:
  - Domestic: 660 (11h)
  - International non-IPD: 720 (12h)
  - IPD: 870 (14:30)
  - Long-range (block >720 and ≤855): 2160 (36h)
  - Extended long-range (block >855): 2880 (48h)
- `get_layover_rest(is_ipd: bool, is_international: bool) -> int` — returns minimum layover rest in minutes per CBA §11.J, §14.I:
  - Domestic: 600 (10h)
  - International non-IPD: 600 (10h)
  - IPD: 840 (14h)

**Files:** `app/services/cba_rules.py`
**Test:** Add to `tests/test_cba_rules.py`:
1. Domestic home base → 660 min
2. International non-IPD home base → 720 min
3. IPD home base → 870 min
4. Long-range (block=780) home base → 2160 min
5. Extended long-range (block=900) home base → 2880 min
6. Domestic layover → 600 min
7. IPD layover → 840 min
**Verify:** `cd backend && python -m pytest tests/test_cba_rules.py -v`

---

### Task 67 — Implement 7-day block hour limit checker ✅

Add to `app/services/cba_rules.py`:
- `check_seven_day_block_limits(sequences: List[Sequence], is_reserve: bool) -> List[CBAViolation]` — given a list of sequences (with operating_dates and totals.block_minutes), checks every rolling 7-day window in the bid period. Returns violations where block hours exceed 30h (Lineholder) or 35h (Reserve). Deadhead block is excluded per CBA §11.B.

**Files:** `app/services/cba_rules.py`
**Test:** Add to `tests/test_cba_rules.py`:
1. 3 sequences totaling 28h block in 7 days → no violation (Lineholder)
2. 4 sequences totaling 32h block in 7 days → violation for Lineholder, ok for Reserve
3. 5 sequences totaling 36h in 7 days → violation for both
4. 30h block + 5h deadhead in 7 days → no violation (deadhead excluded)
**Verify:** `cd backend && python -m pytest tests/test_cba_rules.py -v`

---

### Task 68 — Implement 6-consecutive-day and minimum days off checkers ✅

Add to `app/services/cba_rules.py`:
- `check_six_day_limit(sequences: List[Sequence], bid_period_days: int) -> List[CBAViolation]` — checks that no span of >6 consecutive duty days occurs without 24h off at crew base per CBA §11.C.
- `check_minimum_days_off(sequences: List[Sequence], bid_period_days: int, vacation_days: int = 0) -> List[CBAViolation]` — checks that ≥11 calendar days off per month for Lineholders per CBA §11.H. Applies proration if vacation ≥7 days.

**Files:** `app/services/cba_rules.py`
**Test:** Add to `tests/test_cba_rules.py`:
1. 6 consecutive duty days then 1 off → no violation
2. 7 consecutive duty days → violation
3. 19 duty days in 30-day month → 11 days off, ok
4. 21 duty days in 30-day month → 9 days off, violation
5. 7 vacation days + 16 duty days → prorated minimum, check passes
**Verify:** `cd backend && python -m pytest tests/test_cba_rules.py -v`

---

### Task 69 — Implement credit hour range checker ✅

Add to `app/services/cba_rules.py`:
- `check_credit_hour_range(total_credit_minutes: int, line_option: str) -> List[CBAViolation]` — checks credit hours against Line of Time bounds per CBA §2.EE:
  - standard: 70–90h (4200–5400 min)
  - high: 70–110h (4200–6600 min)
  - low: 40–90h (2400–5400 min)
  Returns a warning if outside range.

**Files:** `app/services/cba_rules.py`
**Test:** Add to `tests/test_cba_rules.py`:
1. 5000 min, standard → within range, no violation
2. 5500 min, standard → exceeds 90h, violation
3. 5500 min, high → within range, no violation
4. 3000 min, standard → below 70h, violation
5. 3000 min, low → within range, no violation
**Verify:** `cd backend && python -m pytest tests/test_cba_rules.py -v`

---

### Task 70 — Implement rest-between-sequences checker ✅

Add to `app/services/cba_rules.py`:
- `check_rest_between_sequences(seq_a: Sequence, seq_b: Sequence) -> Optional[CBAViolation]` — given two consecutive sequences ordered by date, checks that adequate rest exists between seq_a's release and seq_b's report. Uses `get_home_base_rest()` from Task 66 based on seq_a's type. Returns a violation if rest is insufficient.

**Files:** `app/services/cba_rules.py`
**Test:** Add to `tests/test_cba_rules.py`:
1. Domestic seq releasing at 18:00, next reporting at 06:00 next day (12h) → ok (11h min)
2. Domestic seq releasing at 22:00, next reporting at 06:00 (8h) → violation
3. IPD seq releasing at 20:00, next reporting at 12:00 next day (16h) → ok (14:30 min)
4. IPD seq releasing at 20:00, next reporting at 08:00 (12h) → violation
**Verify:** `cd backend && python -m pytest tests/test_cba_rules.py -v`

---

### Task 71 — Create unified CBA validator ✅

Create `app/services/cba_validator.py` that combines all checkers:
- `validate_bid(sequences: List[Sequence], line_option: str, is_reserve: bool, bid_period_days: int, vacation_days: int = 0) -> CBAValidationResult` — runs all checks from Tasks 67–70: 7-day block limits, 6-day consecutive limit, minimum days off, credit hour range, and rest between consecutive sequences. Aggregates violations and computes credit_hour_summary and days_off_summary. Sets `is_valid = len(violations) == 0`.

**Files:** `app/services/cba_validator.py` (new)
**Test:** Create `tests/test_cba_validator.py`:
1. Valid bid (all rules pass) → is_valid=True, empty violations
2. Bid with 7-day block violation → is_valid=False, 1 violation with rule="CBA §11.B"
3. Bid with multiple violations → all listed
4. Credit hour summary reflects line_option correctly
**Verify:** `cd backend && python -m pytest tests/test_cba_validator.py -v`

---

### Task 72 — Add CBA validate endpoint ✅

Add `POST /bid-periods/{bidPeriodId}/bids/{bidId}/validate` to `app/routes/bids.py`. The endpoint:
1. Fetches the bid and its sequences
2. Gets user profile (line_option, is_reserve)
3. Calls `validate_bid()` from Task 71
4. Returns `CBAValidationResult`

**Files:** `app/routes/bids.py`
**Test:** Add tests in `tests/test_bids.py`:
1. POST validate on a valid bid → 200, is_valid=True
2. POST validate on a bid with violations → 200, is_valid=False with violations list
3. POST validate on nonexistent bid → 404
**Verify:** `cd backend && python -m pytest tests/test_bids.py -v`

---

### Task 73 — Update PDF parser: ODAN detection

Update `app/services/pdf_parser.py` in the `_derive_sequence_fields()` function to set `is_odan=True` when a sequence has exactly 1 duty period and all on-duty time falls between 0100–0500 HBT. Use `report_base` and `release_base` times from the duty period.

**Files:** `app/services/pdf_parser.py`
**Test:** Add to `tests/test_pdf_parser.py`:
1. Single DP with report 00:30, release 05:30 (all duty 0100-0500) → is_odan=True
2. Single DP with report 06:00, release 14:00 → is_odan=False
3. Two DPs even if touching 0100-0500 → is_odan=False (must be single DP)
**Verify:** `cd backend && python -m pytest tests/test_pdf_parser.py -v`

---

### Task 74 — Update PDF parser: red-eye per CBA definition

Update `app/services/pdf_parser.py` to change red-eye detection from the current generic heuristic (departs after 21:00 local, arrives before 06:00 local) to the CBA §11.K definition: a duty period that touches 0100–0101 HBT. Check if any portion of the duty period (from report_base to release_base) spans 0100 HBT.

**Files:** `app/services/pdf_parser.py`
**Test:** Update tests in `tests/test_pdf_parser.py`:
1. DP from 23:00 to 05:00 HBT → is_redeye=True (touches 0100)
2. DP from 06:00 to 14:00 HBT → is_redeye=False
3. DP from 01:00 to 01:01 HBT → is_redeye=True (exactly touches)
4. DP from 02:00 to 10:00 HBT → is_redeye=False (does not touch 0100-0101)
**Verify:** `cd backend && python -m pytest tests/test_pdf_parser.py -v`

---

### Task 75 — Update PDF parser: IPD/NIPD classification

Update `app/services/pdf_parser.py` to classify sequences:
- `is_ipd=True` if category contains "INTL" and destinations include Europe, Asia, or Deep South America airports (maintain a set of IPD station codes), OR if category footer indicates IPD (e.g., "777 INTL", "787 INTL").
- `is_nipd=True` if international but not IPD.
- Set `is_speaker_sequence=True` if `language` field is not None.
- Set `has_holiday` by cross-referencing `operating_dates` with `get_holiday_dates()` from Task 62.

**Files:** `app/services/pdf_parser.py`
**Test:** Add to `tests/test_pdf_parser.py`:
1. Category "777 INTL" with NRT destination → is_ipd=True
2. Category "NBI INTL" with CUN destination → is_nipd=True
3. Sequence with language="JP" → is_speaker_sequence=True
4. Sequence operating on Dec 25 → has_holiday=True
5. Domestic sequence → is_ipd=False, is_nipd=False
**Verify:** `cd backend && python -m pytest tests/test_pdf_parser.py -v`

---

### Task 76 — Update PDF parser: international duty type classification

Update `app/services/pdf_parser.py` to call `classify_international_duty()` from Task 65 for international sequences. Set `international_duty_type` on each sequence based on the maximum block time in any single DP and the maximum scheduled duty time.

**Files:** `app/services/pdf_parser.py`
**Test:** Add to `tests/test_pdf_parser.py`:
1. International sequence with 10h block, 13h duty → non_long_range
2. International sequence with 13h block, 15h duty → long_range
3. Domestic sequence → international_duty_type=None
**Verify:** `cd backend && python -m pytest tests/test_pdf_parser.py -v`

---

### Task 77 — Update PDF parser: compute pay/rig fields

Update `app/services/pdf_parser.py` in `_derive_sequence_fields()` to compute:
- `totals.duty_rig_minutes` using `calc_duty_rig()` from Task 60
- `totals.trip_rig_minutes` using `calc_trip_rig()` from Task 60

Note: `estimated_pay_cents` requires user context (years_of_service) so is NOT computed at parse time. It stays at 0 until the API layer fills it in.

**Files:** `app/services/pdf_parser.py`
**Test:** Add to `tests/test_pdf_parser.py`:
1. Sequence with 480 on-duty minutes → duty_rig = 240 min
2. Sequence with 2100 TAFB minutes → trip_rig = 600 min
**Verify:** `cd backend && python -m pytest tests/test_pdf_parser.py -v`

---

### Task 78 — Add CBA filter parameters to sequence list endpoint

Update `app/routes/sequences.py` to accept new query parameters on `GET .../sequences`:
- `is_odan: Optional[bool]`
- `is_ipd: Optional[bool]`
- `has_holiday: Optional[bool]`
- `is_speaker_sequence: Optional[bool]`
- `international_duty_type: Optional[str]`

Apply these as filters on the database query.

**Files:** `app/routes/sequences.py`
**Test:** Add to `tests/test_sequences.py`:
1. Filter `is_ipd=true` → returns only IPD sequences
2. Filter `is_odan=true` → returns only ODANs
3. Filter `has_holiday=true` → returns only holiday sequences
4. Filter `international_duty_type=long_range` → returns only long-range sequences
**Verify:** `cd backend && python -m pytest tests/test_sequences.py -v`

---

### Task 79 — Integrate CBA validation into optimizer

Update `app/services/optimizer.py` to add Phase 4.5 (CBA Constraint Validation) after the existing strategic ordering phase. After ordering:
1. Call `validate_bid()` from Task 71 with the ranked sequences
2. Store violations in `summary.cba_violations`
3. Compute and store `summary.total_credit_hours`, `summary.credit_hour_utilization`
4. Set `summary.line_option`, `summary.line_min_hours`, `summary.line_max_hours` from user profile

Also update Phase 2 (attainability) to boost attainability for Speaker-qualified users on Speaker sequences, and for Purser-qualified users on IPD sequences.

**Files:** `app/services/optimizer.py`
**Test:** Add to `tests/test_optimizer_phase1_2.py` (or new file `tests/test_optimizer_cba.py`):
1. Optimize a bid → summary includes total_credit_hours and cba_violations
2. Bid exceeding 7-day block limit → cba_violations contains violation
3. Speaker-qualified user on Speaker sequence → attainability boosted
**Verify:** `cd backend && python -m pytest tests/ -v`

---

### Task 80 — Frontend: update TypeScript types for CBA fields

Update `frontend/src/types/api.ts` to add all new CBA fields to the TypeScript interfaces:
- `Profile`: add `years_of_service`, `is_reserve`, `is_purser_qualified`, `line_option`
- `Sequence`: add `is_odan`, `international_duty_type`, `is_ipd`, `is_nipd`, `has_holiday`, `is_speaker_sequence`
- `SequenceTotals`: add `duty_rig_minutes`, `trip_rig_minutes`, `estimated_pay_cents`
- `BidSummary`: add `total_credit_hours`, `line_option`, `line_min_hours`, `line_max_hours`, `credit_hour_utilization`, `estimated_total_pay_cents`, `cba_violations`
- Add new interfaces: `CBAViolation`, `CBAValidationResult`, `CreditHourSummary`, `DaysOffSummary`

**Files:** `frontend/src/types/api.ts`
**Test:** `cd frontend && npm run build` — verify TypeScript compilation succeeds with no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 81 — Frontend: update onboarding wizard with CBA profile fields

Update `frontend/src/pages/RegisterPage.tsx` to add step 2 fields:
- Years of service (number input, 1–30)
- Reserve / Lineholder toggle
- Purser qualified checkbox
- Line option selector (Standard / High / Low) with explanatory text showing hour ranges

**Files:** `frontend/src/pages/RegisterPage.tsx`
**Test:** `cd frontend && npm run build` — no errors. Manual verification: form renders, validates, and submits new fields.
**Verify:** `cd frontend && npm run test`

---

### Task 82 — Frontend: add CBA badges to sequence browser

Update `frontend/src/pages/SequenceBrowserPage.tsx` to display new badges in the sequence list rows:
- IPD badge (blue) / NIPD badge (teal) for international sequences
- ODAN badge (purple) for all-nighter sequences
- Holiday badge (gold star) for sequences on CBA holidays
- Speaker badge (green globe) for language-required sequences
- International duty type label (NLR/MR/LR/ELR) for international sequences

Also add the new filter controls: is_ipd, is_odan, has_holiday, is_speaker_sequence, international_duty_type dropdown.

**Files:** `frontend/src/pages/SequenceBrowserPage.tsx`
**Test:** `cd frontend && npm run build` — no errors. Manual verification: badges render, filters work.
**Verify:** `cd frontend && npm run test`

---

### Task 83 — Frontend: add CBA indicators to sequence detail page

Update `frontend/src/pages/SequenceDetailPage.tsx` to display:
- International duty type classification with max duty limits
- IPD/NIPD status with rest requirements shown
- ODAN status with constraint summary (max 14h duty, max 2 segments, etc.)
- Holiday indicator with premium note (100% premium)
- Speaker requirement with staffing details
- Duty Rig and Trip Rig values alongside the existing block/TPAY/TAFB totals
- Estimated pay (if available) with breakdown tooltip

**Files:** `frontend/src/pages/SequenceDetailPage.tsx`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 84 — Frontend: credit hour meter in bid builder

Update `frontend/src/pages/BidsPage.tsx` to add a credit hour meter at the top of the bid builder:
- Progress bar showing `total_credit_hours` vs `line_min_hours`–`line_max_hours` range
- Color-coded: green (within range), yellow (within 5h of boundary), red (outside range)
- Line option selector dropdown (standard/high/low) that updates min/max
- Text showing "X.X / 70–90 credit hours" (or applicable range)

**Files:** `frontend/src/pages/BidsPage.tsx`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 85 — Frontend: CBA violations panel in bid builder

Update `frontend/src/pages/BidsPage.tsx` to add a collapsible violations panel below the credit hour meter:
- Shows each violation from `summary.cba_violations` as a card
- Each card shows: CBA section reference, severity icon (red X for error, yellow ! for warning), plain-language message
- Panel header shows violation count badge
- Panel is collapsed by default if no violations

Also add an API call to `POST .../bids/{bidId}/validate` triggered by a "Check CBA Rules" button, and display the full `CBAValidationResult`.

**Files:** `frontend/src/pages/BidsPage.tsx`, `frontend/src/lib/api.ts`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 86 — Frontend: update glossary with CBA terms

Update `frontend/src/pages/GlossaryPage.tsx` to add all 22 CBA-defined terms from the updated requirements.md glossary: PBS, Lineholder, Line of Time, Duty Rig, Trip Rig, Credit Window, Golden Days, Flex Days, RAP, TTS, ETB, IPD, NIPD, ODAN, Purser, HBT, Double Up Sequences, Multiple Sequences, Speaker, UBL, Pay No Credit, Carry Over.

**Files:** `frontend/src/pages/GlossaryPage.tsx`
**Test:** `cd frontend && npm run build && npm run test` — glossary tests still pass, new terms render.
**Verify:** `cd frontend && npm run test`

---

### Task 87 — Run full test suite and fix any regressions

Run the complete backend and frontend test suites end-to-end. Fix any failures introduced by Tasks 53–86. Ensure all existing tests still pass alongside new tests.

**Verify:**
```
cd backend && python -m pytest tests/ -v --tb=short
cd frontend && npm run test
cd frontend && npm run build
```

All tests green, zero regressions.

---

## Phase 14: CBA End-to-End Validation

### Task 88 — Parse real bid sheet with CBA fields

Run the PDF parser against `ORDSEQ2601.pdf` and verify all new CBA fields are populated:
- Count sequences where is_ipd=True, is_nipd=True, is_odan=True
- Verify international_duty_type is set on international sequences
- Verify has_holiday is set for relevant operating dates
- Verify is_speaker_sequence matches sequences with LANG field
- Verify duty_rig_minutes and trip_rig_minutes are computed

**Test:** Create `tests/test_cba_parser_integration.py` that parses the real PDF and asserts field distributions.
**Verify:** `cd backend && python -m pytest tests/test_cba_parser_integration.py -v`

---

### Task 89 — CBA validation integration test with real data

Create an integration test that:
1. Parses ORDSEQ2601.pdf
2. Builds a mock bid from a realistic subset of sequences
3. Runs CBA validation
4. Verifies the validation result is structurally complete (credit hours, days off, violations all populated)

**Test:** Add to `tests/test_cba_validator.py` or create `tests/test_cba_integration.py`.
**Verify:** `cd backend && python -m pytest tests/test_cba_integration.py -v`

---

### Task 90 — Final full-suite verification

Run the complete test suite one final time. Verify all backend tests pass, all frontend tests pass, frontend builds cleanly, and the app starts without errors.

**Verify:**
```
cd backend && python -m pytest tests/ -v --tb=short
cd frontend && npm run test
cd frontend && npm run build
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 &
# Smoke test: curl http://localhost:8000/health
```

---

## Phase 15: PBS Property-Based Bidding System

> Replaces the current flat-preference optimizer with a PBS-style property system matching the real AA PBS bidding interface at fapbs.aa.com. Users configure properties across 4 categories (Days Off, Line, Pairing, Reserve) with per-layer assignments (1-7). The optimizer filters and scores sequences per layer using AND/OR logic.
>
> **Reference:** `pbs-system-reference.md` contains the complete AA PBS system documentation (63 properties, 7 layers, AND/OR logic, pairing types, equipment codes, strategic notes).
>
> Each task is atomic. Complete it, write tests, run the full test suite, and confirm green before moving on.

### Task 91 — Add PBS property constants and PROPERTY_DEFINITIONS to backend schemas ✅

Add to `app/models/schemas.py`:
- `NUM_LAYERS = 7`
- `VALID_PROPERTY_CATEGORIES = {"days_off", "line", "pairing", "reserve"}`
- `VALID_PAIRING_TYPES = {"regular", "nipd", "ipd", "premium_transcon", "odan", "redeye", "satellite"}`
- `VALID_EQUIPMENT_CODES` set with all AA equipment codes (320, 321, A21, 737, 38K, 38M, 777, 77W, 787, 788, 789, 78P)
- `PROPERTY_DEFINITIONS: dict[str, dict]` — a catalog of all 63 PBS properties. Each entry has keys: `category`, `label`, `value_type`, `favorite`. Categories: days_off (7), line (18), pairing (34), reserve (4). See `pbs-system-reference.md` §2 for the full list.

**Files:** `app/models/schemas.py`
**Test:** Add tests in `tests/test_models.py` that:
1. Verify PROPERTY_DEFINITIONS has exactly 63 entries
2. Verify each entry has required keys (category, label, value_type, favorite)
3. Verify category counts: 7 days_off, 18 line, 34 pairing, 4 reserve
4. Verify pairing favorites count is 5, line favorites count is 1
**Verify:** `cd backend && python -m pytest tests/test_models.py -v`

---

### Task 92 — Add BidProperty Pydantic models to backend schemas ✅

Add to `app/models/schemas.py`:
- `BidProperty(BaseModel)` — fields: `id: str`, `property_key: str`, `category: str`, `value: Any`, `layers: List[int]` (default [1]), `priority: int` (default 0), `is_enabled: bool` (default True). Add validators: category must be in VALID_PROPERTY_CATEGORIES, each layer must be 1-7.
- `BidPropertyInput(BaseModel)` — same fields minus `id`.
- `LayerSummary(BaseModel)` — fields: `layer_number: int`, `total_pairings: int`, `pairings_by_layer: int`, `properties_count: int`.
- `BidConfiguration(BaseModel)` — fields: `bid_period_id: str`, `properties: List[BidProperty]`, `layer_summaries: List[LayerSummary]`.

**Files:** `app/models/schemas.py`
**Test:** Add tests in `tests/test_models.py` that:
1. Construct a BidProperty with valid category and layers → OK
2. BidProperty with invalid category → ValidationError
3. BidProperty with layer=0 or layer=8 → ValidationError
4. LayerSummary and BidConfiguration construct with defaults
**Verify:** `cd backend && python -m pytest tests/test_models.py -v`

---

### Task 93 — Backend routes for property CRUD and layer summaries ✅

Added to `app/routes/bids.py`:
- `GET .../bids/{bidId}/properties` — list properties
- `POST .../bids/{bidId}/properties` — add property (validates key against catalog)
- `PUT .../bids/{bidId}/properties/{propertyId}` — update property
- `DELETE .../bids/{bidId}/properties/{propertyId}` — remove property
- `GET .../bids/{bidId}/layers` — compute 7 layer summaries with pairing counts
Properties stored on the Bid document (`properties` field). 7 new tests.

---

### Task 93b — Add PBS property types to frontend TypeScript ✅

Add to `frontend/src/types/api.ts`:
- `NUM_LAYERS = 7` constant
- `PropertyCategory` type: `'days_off' | 'line' | 'pairing' | 'reserve'`
- `PairingType` type with all 7 values
- `EQUIPMENT_CODES` const array
- `PAIRING_TYPES` array of `{ value, label }` objects
- `PropertyDefinition` interface: `key, category, label, value_type, favorite`
- `BidProperty` interface: `id, property_key, category, value, layers, priority, is_enabled`
- `BidPropertyInput` interface (same minus id)
- `LayerSummary` interface: `layer_number, total_pairings, pairings_by_layer, properties_count`
- `PROPERTY_CATALOG: PropertyDefinition[]` — all 63 properties matching backend PROPERTY_DEFINITIONS

**Files:** `frontend/src/types/api.ts`
**Test:** `cd frontend && npm run build` — verify TypeScript compilation succeeds with no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 94 — Add PBS property API functions to frontend ✅

Add to `frontend/src/lib/api.ts`:
- `listBidProperties(bidPeriodId, bidId)` → GET `.../bids/{bidId}/properties`
- `addBidProperty(bidPeriodId, bidId, property)` → POST `.../bids/{bidId}/properties`
- `updateBidProperty(bidPeriodId, bidId, propertyId, updates)` → PUT `.../bids/{bidId}/properties/{propertyId}`
- `deleteBidProperty(bidPeriodId, bidId, propertyId)` → DELETE `.../bids/{bidId}/properties/{propertyId}`
- `getLayerSummaries(bidPeriodId, bidId)` → GET `.../bids/{bidId}/layers`
- `optimizeBidWithProperties(bidPeriodId, bidId)` → POST `.../bids/{bidId}/optimize`

Import the new types from `api.ts`.

**Files:** `frontend/src/lib/api.ts`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 95 — Implement property-based sequence filtering in optimizer ✅

Add to `app/services/optimizer.py`:
- `filter_sequences_for_layer(sequences, properties, layer_number)` — filters the sequence pool for a layer using pairing properties. Same property_key with different values = OR (union). Different property_keys = AND (intersection). Only applies pairing-category properties that are enabled and assigned to the given layer.
- `_matches_property(seq, prop_key, value)` — tests whether a single sequence matches a single pairing property. Implement matchers for at minimum: `report_between`, `release_between`, `prefer_pairing_type`, `prefer_pairing_length`, `prefer_duty_period`, `prefer_aircraft`, `avoid_aircraft`, `prefer_deadheads`, `avoid_deadheads`, `layover_at_city`, `avoid_layover_at_city`, `max_landings_per_duty`, `min_avg_credit_per_duty`, `max_tafb_credit_ratio`. Unknown properties pass through (don't filter).

**Files:** `app/services/optimizer.py`
**Test:** Create `tests/test_optimizer_properties.py`:
1. filter with `report_between` {start: 360, end: 720} → only sequences with first report in range
2. filter with `prefer_pairing_type: "ipd"` → only IPD sequences
3. filter with two `layover_at_city` properties (LHR, NRT) → OR: sequences with either
4. filter with `layover_at_city: LHR` AND `prefer_pairing_length: 3` → AND: must match both
5. filter with no properties → returns all sequences
6. `_matches_property` with unknown key → returns True
**Verify:** `cd backend && python -m pytest tests/test_optimizer_properties.py -v`

---

### Task 96 — Add compute_layer_summaries to optimizer ✅

Add to `app/services/optimizer.py`:
- `compute_layer_summaries(sequences, properties)` — computes pairing counts per layer (1-7), matching the PBS Layer tab display. For each layer: filter sequences using `filter_sequences_for_layer`, track cumulative IDs across layers, compute `total_pairings` (cumulative), `pairings_by_layer` (unique to that layer), and `properties_count`.

**Files:** `app/services/optimizer.py`
**Test:** Add to `tests/test_optimizer_properties.py`:
1. 100 sequences, no properties → all 7 layers show 100 total, 100/0/0/.../0 by-layer
2. 100 sequences, `prefer_pairing_length: 3` on layers 1-3, no filter on 4-7 → layers 1-3 show filtered count, layers 4-7 show full 100
3. Properties on layer 1 only → layers 2-7 pairings_by_layer = 0 (no new ones beyond L1's pool)
**Verify:** `cd backend && python -m pytest tests/test_optimizer_properties.py -v`

---

### Task 97 — Add property-based scoring to optimizer ✅

Add to `app/services/optimizer.py`:
- `score_sequence_from_properties(seq, properties, layer)` — scores how well a sequence matches the user's bid properties for a given layer (0.0-1.0). Pairing properties: 1.0 if matched, 0.0 if not. Days Off properties: score based on days-off optimization goals. Line properties: score based on credit maximization, etc. Returns average across all active properties for that layer.

**Files:** `app/services/optimizer.py`
**Test:** Add to `tests/test_optimizer_properties.py`:
1. Sequence matching all 3 active properties → score ~1.0
2. Sequence matching 1 of 3 → score ~0.33
3. No properties → score 0.5 (neutral)
4. `maximize_credit` property → higher-TPAY sequences score higher
**Verify:** `cd backend && python -m pytest tests/test_optimizer_properties.py -v`

---

### Task 98 — Update optimize_bid to accept and use bid_properties ✅

Update `optimize_bid()` in `app/services/optimizer.py` to accept an optional `bid_properties: list[dict] | None` parameter. When provided:
- Change from 9 layers to 7
- For each layer: filter sequences using `filter_sequences_for_layer`, score using `score_sequence_from_properties`, then build the layer schedule
- When `bid_properties` is None or empty, fall back to existing preference-based scoring (no behavioral change for current callers)

Update `app/routes/bids.py`:
- Add `bid_properties: Optional[list[dict]] = None` to `OptimizeRequest`
- Pass `bid_properties` through to `optimize_bid()`

**Files:** `app/services/optimizer.py`, `app/routes/bids.py`
**Test:** Add to `tests/test_optimizer_properties.py`:
1. `optimize_bid` with bid_properties=None → same behavior as before (9 layers)
2. `optimize_bid` with bid_properties=[...] → returns entries with layers 1-7
3. Properties restricting L1 to IPD only → L1 entries are all IPD sequences
**Verify:** `cd backend && python -m pytest tests/ -v --tb=short`

---

### Task 99 — Build PropertyValueEditor frontend component ✅

Create `frontend/src/components/PropertyValueEditor.tsx` — a component that renders the correct input control for each `value_type`:
- `toggle` → switch
- `integer` → number input
- `decimal` → number input with step=0.1
- `time` → time input (stored as minutes)
- `time_range` → two time inputs (start/end)
- `int_range` → two number inputs (min/max)
- `date` → date picker
- `date_range` → two date pickers
- `pairing_type` → dropdown with PAIRING_TYPES
- `equipment` → dropdown with EQUIPMENT_CODES
- `airport` / `airport_date` → 3-letter text input (+ optional date)
- `days_of_week` → 7 toggle buttons (Mon-Sun)
- `position_list` → text input for comma-separated position numbers
- `text` / `selection` → text input
- `time_range_date` → two time inputs + date
- `int_date` → number + date

Props: `definition: PropertyDefinition`, `value: unknown`, `onChange: (value) => void`

**Files:** `frontend/src/components/PropertyValueEditor.tsx`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 100 — Build PropertyCatalog frontend component ✅

Create `frontend/src/components/PropertyCatalog.tsx` — the main property configuration UI:
- 4 category tabs (Days Off, Line, Pairing, Reserve) with property counts
- Lists active properties for the selected tab with: enable/disable checkbox, label, PropertyValueEditor, layer toggle buttons (1-7), remove button
- "Add Property" expandable panel at bottom showing available properties from PROPERTY_CATALOG, split into Favorites and Other, disabled if already added
- Props: `properties: BidProperty[]`, `onAdd`, `onUpdate`, `onRemove` callbacks

**Files:** `frontend/src/components/PropertyCatalog.tsx`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 101 — Build LayerSummaryPanel frontend component ✅

Create `frontend/src/components/LayerSummaryPanel.tsx`:
- Shows all 7 layers with: layer number badge (colored), label, properties count, total pairings (cumulative), pairings by layer (unique), progress bar
- Click a layer to select it (for detail view)
- Legend explaining total vs by-layer counts
- Props: `summaries: LayerSummary[]`, `totalSequences: number`, `selectedLayer`, `onSelectLayer`

**Files:** `frontend/src/components/LayerSummaryPanel.tsx`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 102 — Build LayerDetailView frontend component ✅

Create `frontend/src/components/LayerDetailView.tsx`:
- Shows all properties assigned to a specific layer, grouped by category
- Displays formatted values for each property
- Shows layer assignment overview (how many properties per layer)
- Props: `layerNumber: number`, `properties: BidProperty[]`, `onClose`

**Files:** `frontend/src/components/LayerDetailView.tsx`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 103 — Rewrite BidPeriodDetailPage with 3-step property workflow ✅

Rewrite `frontend/src/pages/BidPeriodDetailPage.tsx` to use a 3-step workflow:
- **Step 1: Configure Properties** — PropertyCatalog (main area) + LayerSummaryPanel (sidebar) + LayerDetailView (on layer click) + strategy tips. Local state for properties array.
- **Step 2: Generate Bid** — Configuration review (property counts by category), generate button that sends properties to backend via optimizeBid, previous bids selector.
- **Step 3: Review Results** — 7-layer results display (keep existing layer card UI but change from 9 to 7 layers), summary stats, export buttons, PBS portal instructions.
- Workflow step indicator (clickable pills) at top.
- Keep backward compatibility: if no properties configured, the generate step warns and falls back to default scoring.

**Files:** `frontend/src/pages/BidPeriodDetailPage.tsx`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 104 — Update export to support 7-layer output ✅

Update `app/routes/bids.py` export endpoint to handle both 7-layer and 9-layer bids:
- If bid entries have max layer ≤ 7, use 7-layer labels
- If bid entries have layers up to 9, use 9-layer labels (backward compat)
- Update layer_names list to include both sets

**Files:** `app/routes/bids.py`
**Test:** Add to `tests/test_bids.py`:
1. Export a 7-layer bid → TXT output shows layers 1-7 with correct labels
2. Export a 9-layer bid → TXT output shows layers 1-9 (backward compat)
**Verify:** `cd backend && python -m pytest tests/test_bids.py -v`

---

### Task 105 — Run full test suite and fix regressions ✅

Run the complete backend and frontend test suites. Fix any failures introduced by Tasks 91-104. Ensure all existing tests still pass.

**Verify:**
```
cd backend && python -m pytest tests/ -v --tb=short
cd frontend && npm run test
cd frontend && npm run build
```

All tests green, zero regressions.

---

## Phase 16: UX Testing Upgrades

> Addresses critical gaps and usability issues identified during hands-on UX testing by a simulated ORD commuter FA (30% seniority, JP-qualified, DCA commuter) against a parsed January 2026 bid sheet (1,705 sequences). Prioritized by impact on real-world bidding decisions.
>
> **Source:** UX Testing Report (Scenarios 1-3). **New Requirements:** REQ-047 through REQ-055.
>
> Each task is atomic. Complete it, write tests, run the full test suite, and confirm green before moving on.

### Task 106 — Backend: Commute impact analysis service (REQ-047) ✅

Create `app/services/commute.py` with:
- `COMMUTE_WINDOWS: dict[str, dict]` — lookup table mapping commute_from IATA codes to feasible arrival/departure windows at major bases. Each entry: `{ "first_arrival_minutes": int, "last_departure_minutes": int, "flight_time_minutes": int }`. Seed with common commuter city pairs (DCA→ORD, DEN→ORD, LAX→ORD, ATL→ORD, etc.). Include a default conservative fallback for unknown city pairs.
- `analyze_commute_impact(sequence: Sequence, commute_from: str, base_city: str) -> dict` — returns:
  - `first_day_feasible: bool` — True if first-day report time ≥ commute first_arrival + 60min buffer
  - `first_day_note: str` — e.g., "Report 14:26 — easy commute (earliest DCA→ORD arrives 08:30)"
  - `last_day_feasible: bool` — True if last-day release time ≤ commute last_departure - 90min buffer
  - `last_day_note: str` — e.g., "Release 12:07 — easy commute home"
  - `hotel_nights_needed: int` — 0, 1, or 2 based on first/last day feasibility
  - `impact_level: str` — "green" | "yellow" | "red" based on hotel_nights_needed and timing tightness
- `analyze_commute_gap(seq_a_release_minutes: int, seq_b_report_minutes: int, gap_hours: float, commute_from: str, base_city: str) -> dict` — returns whether there's time to commute home and back between two consecutive sequences. Returns `{ "can_go_home": bool, "gap_hours": float, "note": str }`.

**Files:** `app/services/commute.py` (new)
**Test:** Create `tests/test_commute.py`:
1. DCA commuter, report 14:26 → first_day_feasible=True, impact_level="green"
2. DCA commuter, report 05:30 → first_day_feasible=False, hotel_nights_needed≥1, impact_level="red"
3. DCA commuter, release 12:07 → last_day_feasible=True
4. DCA commuter, release 22:00 → last_day_feasible=False, impact_level="red" or "yellow"
5. Gap of 14h between sequences for DCA commuter → can_go_home=False
6. Gap of 48h → can_go_home=True
7. Unknown commute city → uses conservative fallback
**Verify:** `cd backend && python -m pytest tests/test_commute.py -v`

---

### Task 107 — Backend: Add commute annotations to sequence API (REQ-047) ✅

Update `app/routes/sequences.py`:
- On `GET .../sequences` (list) and `GET .../sequences/{sequenceId}` (detail): if the authenticated user has `commute_from` set in their profile, compute commute impact for each returned sequence using `analyze_commute_impact()` from Task 106. Add a `commute_impact` field to the response.
- Add optional query parameter `commutable_only: bool = False` — when True, filter to sequences where `impact_level` is "green" or "yellow".

Update `app/models/schemas.py`:
- Add `CommuteImpact(BaseModel)` — fields: `first_day_feasible`, `first_day_note`, `last_day_feasible`, `last_day_note`, `hotel_nights_needed`, `impact_level`.
- Add `commute_impact: Optional[CommuteImpact] = None` to the sequence response model.

**Files:** `app/routes/sequences.py`, `app/models/schemas.py`
**Test:** Add to `tests/test_sequences.py`:
1. User with commute_from=DCA → sequences include commute_impact field
2. User without commute_from → commute_impact is None
3. `commutable_only=true` → only green/yellow sequences returned
**Verify:** `cd backend && python -m pytest tests/test_sequences.py -v`

---

### Task 108 — Backend: Add commute annotations to bid results (REQ-047) ✅

Update `app/routes/bids.py` and `app/services/optimizer.py`:
- After optimization, compute commute impact for each bid entry's sequence.
- Add commute gap analysis between consecutive sequences in each layer.
- Include `commute_impact` in bid entry response and `commute_warnings: List[str]` in bid summary.

**Files:** `app/routes/bids.py`, `app/services/optimizer.py`, `app/models/schemas.py`
**Test:** Add to `tests/test_bids.py`:
1. Optimize bid for user with commute_from → entries include commute_impact
2. Back-to-back sequences with 14h gap → commute_warnings includes gap warning
3. User without commute_from → no commute data in response
**Verify:** `cd backend && python -m pytest tests/test_bids.py -v`

---

### Task 109 — Frontend: Commute impact badges and detail (REQ-047) ✅

Update frontend to display commute annotations:

**SequenceBrowserPage.tsx:**
- Add commute impact badge (green/yellow/red circle) in each sequence row
- Tooltip on hover shows first_day_note and last_day_note
- Add "Commutable Only" toggle filter

**SequenceDetailPage.tsx:**
- Add "Commute Impact" section showing full commute analysis
- Display first_day_note, last_day_note, hotel_nights_needed
- Color-coded impact level banner

**CalendarPage.tsx:**
- Add commute indicator dot on each sequence's first and last day

**BidPeriodDetailPage.tsx (Step 3: Results):**
- Show commute_impact badge on each bid entry
- Display commute_warnings in summary panel

**ProfilePage.tsx:**
- Ensure `commute_from` field is visible and editable (fix the reported missing field)

**Files:** `frontend/src/pages/SequenceBrowserPage.tsx`, `frontend/src/pages/SequenceDetailPage.tsx`, `frontend/src/pages/CalendarPage.tsx`, `frontend/src/pages/BidPeriodDetailPage.tsx`, `frontend/src/pages/ProfilePage.tsx`, `frontend/src/types/api.ts`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 110 — Backend: Enforce days-off boundaries in optimizer (REQ-049) ✅

Update `app/services/optimizer.py`:
- In `filter_sequences_for_layer()`, add handling for `string_days_off_starting` and `string_days_off_ending` properties:
  - `string_days_off_starting` with value date D: exclude any sequence whose `operating_dates` contain any date ≥ D
  - `string_days_off_ending` with value date D: exclude any sequence whose `operating_dates` contain any date ≤ D
- These act as **hard exclusion filters**, not soft preferences. Sequences overlapping the off-period are removed from the candidate pool for that layer entirely.
- In `_build_layer_schedule()` (or equivalent backtracking function), add a secondary check: if a sequence's date span (first operating date through last operating date + duty days) overlaps the exclusion zone, skip it.
- If the remaining sequences after exclusion cannot meet the target credit range, add a warning to `summary.cba_violations`: "Days-off boundary (Jan 16-31) limits available sequences — credit target may not be met."

**Files:** `app/services/optimizer.py`
**Test:** Add to `tests/test_optimizer_properties.py`:
1. `string_days_off_starting` = Jan 16, sequences with ops on Jan 17 → excluded from layer
2. `string_days_off_starting` = Jan 16, sequence with ops only on Jan 5, 10 → included
3. Both properties: starting=Jan 16, ending=Jan 5 → only sequences on Jan 6-15 pass
4. All layers with starting=Jan 16 → no layer has trips after Jan 15
5. Insufficient sequences after exclusion → warning generated
**Verify:** `cd backend && python -m pytest tests/test_optimizer_properties.py -v`

---

### Task 111 — Backend: Projected schedule computation (REQ-050) ✅

Add to `app/services/optimizer.py`:
- `compute_projected_schedule(entries: List[dict], sequences: List[Sequence], layer: int) -> dict` — for a given layer, selects the top-ranked non-conflicting sequences that form a valid line and returns:
  - `sequences: List[dict]` — the projected sequences with seq_number, category, tpay_minutes, duty_days, operating_dates
  - `total_credit_hours: float`
  - `total_days_off: int`
  - `working_dates: List[int]` — dates with trips
  - `off_dates: List[int]` — dates without trips
  - `schedule_shape: str` — human-readable summary (e.g., "5 trips, 82.5 credit hours, 14 days off, front-loaded")
  - `within_credit_range: bool`

Update `app/routes/bids.py`:
- Add `GET .../bids/{bidId}/projected` endpoint that returns projected schedules for all 7 layers.
- Add `projected_schedules` to the optimize response.

**Files:** `app/services/optimizer.py`, `app/routes/bids.py`, `app/models/schemas.py`
**Test:** Add to `tests/test_optimizer_properties.py`:
1. Layer 1 with 5 non-conflicting sequences → projected schedule shows 5 trips
2. Projected schedule working_dates + off_dates = all bid period dates
3. total_credit_hours computed correctly
4. within_credit_range reflects line_option limits
**Verify:** `cd backend && python -m pytest tests/ -v --tb=short`

---

### Task 112 — Frontend: Projected schedule display (REQ-050) ✅

Update `frontend/src/pages/BidPeriodDetailPage.tsx` (Step 3: Results):
- Add a "Projected Schedule" tab/section above the layer cards
- For the selected layer, display:
  - Summary line: "5 trips, 82.5 credit hours, 14 days off"
  - Mini-calendar showing working days (filled) and off days (clear)
  - Credit hour indicator (green/yellow/red vs. line range)
  - List of projected sequences with key stats
- Layer selector to switch between projected schedules for L1-L7

Add to `frontend/src/lib/api.ts`:
- `getProjectedSchedule(bidPeriodId, bidId)` → GET `.../bids/{bidId}/projected`

**Files:** `frontend/src/pages/BidPeriodDetailPage.tsx`, `frontend/src/lib/api.ts`, `frontend/src/types/api.ts`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 113 — Backend: Sequence number search endpoint (REQ-051) ✅

Update `app/routes/sequences.py`:
- Add query parameter `seq_number: Optional[int]` to `GET .../sequences`. When provided, filter to exact match on `seq_number` field.
- Add `GET .../sequences/search/{seqNumber}` convenience endpoint that returns a single sequence by number (or 404).

**Files:** `app/routes/sequences.py`
**Test:** Add to `tests/test_sequences.py`:
1. Search seq_number=664 → returns exactly SEQ 664
2. Search seq_number=99999 → returns empty list / 404
3. List with seq_number filter → single result
**Verify:** `cd backend && python -m pytest tests/test_sequences.py -v`

---

### Task 114 — Frontend: Sequence number search box (REQ-051) ✅

Update `frontend/src/pages/SequenceBrowserPage.tsx`:
- Add a prominent search box at the top of the filter panel labeled "Find Sequence #"
- On enter/submit, fetch the sequence by number and either scroll to it in the list or navigate to its detail page
- Show "Sequence not found" inline if no match
- Also add a global search shortcut accessible from BidsPage and CalendarPage (e.g., a search icon in the header that opens a quick-find modal)

**Files:** `frontend/src/pages/SequenceBrowserPage.tsx`, `frontend/src/components/Layout.tsx`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 115 — Frontend: Layer pairing browser (REQ-052) ✅

Update `frontend/src/pages/BidPeriodDetailPage.tsx` (Step 1: Configure Properties):
- Add a "Browse Pairings" button on each layer in the LayerSummaryPanel
- Clicking opens a modal/drawer showing the filtered sequence list for that layer (uses the existing SequenceBrowser component or a lightweight version)
- The browser shows sequences that match the layer's current pairing properties
- Empty state shows suggestions when zero pairings match
- User can bookmark or view detail from within the browser

Add to `frontend/src/lib/api.ts`:
- `getLayerPairings(bidPeriodId, bidId, layerNumber)` → fetches sequences filtered by that layer's properties (can reuse the existing sequence list endpoint with filter params derived from properties)

**Files:** `frontend/src/pages/BidPeriodDetailPage.tsx`, `frontend/src/components/LayerSummaryPanel.tsx`, `frontend/src/lib/api.ts`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 116 — Frontend: Bulk layer assignment and input fixes (REQ-053, REQ-054) ✅

Update `frontend/src/components/PropertyCatalog.tsx`:
- Add "All" toggle button next to the layer buttons (1-7) for each property. Clicking assigns the property to all 7 layers. Clicking again deselects all.
- Support shift-click on layer buttons: clicking layer 1 then shift-clicking layer 5 selects layers 1-5.

Update `frontend/src/components/PropertyValueEditor.tsx`:
- **Number inputs**: Replace arrow-only inputs with standard `<input type="number">` that accepts direct keyboard entry. Remove any `onKeyDown` handlers that prevent typing. Ensure the field clears on focus and accepts typed values.
- **Time inputs**: Use `<input type="time">` with direct typing support. Remove any JavaScript workarounds that override native input behavior. Ensure `onChange` fires on both typing and picker selection.
- **Date inputs**: Ensure `<input type="date">` accepts typed dates.

**Files:** `frontend/src/components/PropertyCatalog.tsx`, `frontend/src/components/PropertyValueEditor.tsx`
**Test:** `cd frontend && npm run build` — no errors.
**Verify:** `cd frontend && npm run test`

---

### Task 117 — Backend: Fix IPD pairing type classification (REQ-055) ✅

Update `app/services/optimizer.py` in `_matches_property()`:
- For `prefer_pairing_type: "ipd"`: match sequences where `is_ipd == True` OR category contains "INTL" with widebody equipment (777, 787) AND international destinations. Currently NRT trips on 777 show as "ORD 777 INTL" but don't match the IPD filter.

Update `app/services/pdf_parser.py` in IPD classification:
- Ensure all 777/787 INTL sequences with destinations in Europe (LHR, CDG, FCO, etc.), Asia (NRT, HND, ICN, PVG, HKG, etc.), or Deep South America (GRU, EZE, SCL, etc.) are classified as `is_ipd=True`.
- Add logging when a sequence has "INTL" in category but is classified as NIPD rather than IPD, to aid debugging.

**Files:** `app/services/optimizer.py`, `app/services/pdf_parser.py`
**Test:** Add to `tests/test_optimizer_properties.py`:
1. Sequence with category "ORD 777 INTL", destination NRT → matches `prefer_pairing_type: "ipd"`
2. Sequence with category "ORD NBI INTL", destination CUN → matches `prefer_pairing_type: "nipd"` but NOT "ipd"
3. Filter layer with `prefer_pairing_type: "ipd"` on real data → non-zero count
**Verify:** `cd backend && python -m pytest tests/ -v --tb=short`

---

### Task 118 — Run full test suite and fix regressions ✅

Run the complete backend and frontend test suites end-to-end. Fix any failures introduced by Tasks 106–117. Ensure all existing tests still pass alongside new tests.

**Verify:**
```
cd backend && python -m pytest tests/ -v --tb=short
cd frontend && npm run test
cd frontend && npm run build
```

All tests green, zero regressions.
