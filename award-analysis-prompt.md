# Award File Analysis & Optimizer Calibration — Claude Code Prompt

You have 3 base-wide PBS award PDFs for ORD (Chicago O'Hare), one per month:

- `ORD-JAN26.pdf` — January 2026 awards
- `ORD-FEB26.pdf` — February 2026 awards
- `ORD-MAR26.pdf` — March 2026 awards

These are **APFA PBS Award Files** — they show the awarded schedule for **every single FA at the ORD base** (roughly 400 lines/people). This is the most valuable data we can get: it tells us exactly which trips were awarded, at what seniority, from which bid layer.

The user's mom is the FA. Her seniority is approximately 30% (she's around line 120 of 400). The app is a PBS bid optimizer in `backend/` (FastAPI) + `frontend/` (React/Vite).

## Step 1: Understand the Award PDF Format

Read the first ~200 lines of `ORD-JAN26.pdf` (it converts to text with pdfplumber). Each FA's award block looks like this:

```
LINE 1   PAY 78:17   1 2 | 3 4| 5 6 7 8 9 |10 11| ...
061765   TAFB 122:03 TH FR |SA SU| MO TU WE TH FR |SA SU| ...
LN CR.   78:17        5338 5338 | | 0667 5279 5281 5292 | | 5276 |
OFF 21   DH 0:00      * * ORD * ORD * * * * * * * HNL - ORD ...
PRIORITY               P1   P1   P1   P1   P1   P1   P1
POSITION               01   01   01   01   01   01   01
DTY 078:17 BLK 78:17  05338=/0713/1945/1022, 00667=/0900/...
```

Key fields per line/FA:
- **LINE number** — their seniority rank (1 = most senior, ~400 = most junior)
- **Employee number** (e.g., 061765)
- **LN/L1-L7** — which layer was primarily used (LN = line number holder, L1-L7 = which PBS layer)
- **PAY** — total credit hours awarded (HH:MM)
- **TAFB** — time away from base
- **OFF** — days off
- **Sequence numbers** scattered across calendar days (e.g., 5338, 0667, 5279)
- **PRIORITY** row — P1-P7 or PN for each pairing (which layer it was awarded from)
- **POSITION** row — position number for each pairing (01-09, PUR for purser)
- **DTY/BLK** row — pairing details: `SEQNUM=/REPORT/RELEASE/BLOCK`

Page breaks have `-- N of 400 --` markers. Some lines say `NO PAIRINGS AWARDED` (leave/training). Lines are separated by dashed rows.

## Step 2: Build the Award Parser

Create a new file `backend/app/services/award_parser.py` that parses these award PDFs. The parser should extract, for each FA line:

```python
@dataclass
class AwardedLine:
    line_number: int               # 1-400
    employee_id: str               # "061765"
    layer_label: str               # "LN", "L1", "L2", etc.
    pay_minutes: int               # total credit in minutes
    tafb_minutes: int              # total TAFB in minutes
    days_off: int                  # OFF count
    deadhead_minutes: int          # DH time
    pairings: list[AwardedPairing] # individual pairings awarded

@dataclass
class AwardedPairing:
    seq_number: int                # e.g. 5338
    priority: str                  # "P1" through "P7" or "PN"
    position: str                  # "01", "02", ..., "PUR"
    report_time: str               # "0713" (HHMM)
    release_time: str              # "1945" (HHMM)
    block_minutes: int             # block time
    operating_dates: list[int]     # calendar days this instance covers

@dataclass
class MonthAward:
    month: str                     # "2026-01"
    base: str                      # "ORD"
    total_lines: int               # ~400
    lines: list[AwardedLine]
```

Use `pdfplumber` (already a dependency) to extract text. The parser needs to handle:
- Page breaks (`-- N of 400 --` markers between blocks)
- Multi-line blocks per FA (each is ~6-7 lines between dashed separators)
- The sequence numbers on the calendar row may be concatenated without spaces when multiple sequences start on adjacent days (e.g., `52810667` = seq 5281 + seq 0667). Cross-reference against the DTY/BLK row which lists all sequence numbers cleanly as `SEQNUM=/RPT/RLS/BLK`.
- "NO PAIRINGS AWARDED" lines (leave/training — skip or mark)
- Position "PUR" = purser (special case)

The DTY/BLK row is the most reliable source for sequence identification — it lists each pairing as `SEQNUM=/REPORT/RELEASE/BLOCK` separated by commas. The PRIORITY and POSITION rows have one entry per pairing in the same left-to-right order as the sequences appear on the calendar.

## Step 3: Build Survival Curves (Implement Level 3 Holdability)

The file `backend/app/services/holdability.py` already has a **stub** for Level 3:

```python
def build_survival_curves(award_file_data: list[dict]) -> dict:
    """Build empirical survival curves from APFA award file data.
    ... For now, returns empty dict. Will be implemented when FA provides
    APFA award file data."""
```

**Implement this.** The key insight: if a pairing with sequence number X was awarded to LINE 50 (seniority position 50 of 400), that means it "survived" past seniority position 49 — the top 49 people didn't take it (or couldn't). So for a user at seniority ~120, we can compute: what fraction of similar pairings survived past position 120?

Build survival analysis by pairing characteristics (not individual sequence numbers, since sequences change monthly):

1. **By credit band**: low (<12h), mid (12-20h), high (>20h)
2. **By layover city tier**: premium international (NRT, LHR, CDG, etc.), premium domestic (HNL, SFO, etc.), standard
3. **By duty days**: turns (1-day), 2-day, 3-day, 4-day, 5+ day
4. **By report time**: early (<06:00), morning (06:00-10:00), midday (10:00-14:00), afternoon (14:00+)
5. **By day-of-week pattern**: touches weekend, weekday-only
6. **By priority layer**: what fraction of each trait-bucket came from P1-P3 (early layers) vs P4-P7 (late layers)?

For each trait combination, compute:
- `survival_to_pct(X)` = fraction of pairings with that trait that were awarded to someone at seniority >= X%
- This is basically an empirical CDF: at each seniority percentile, what fraction of this trait-category is still available?

Average across the 3 months to smooth out noise.

The result should be a dict like:
```python
{
    "high_credit|intl_premium|3day": [(0.1, 0.95), (0.2, 0.80), (0.3, 0.55), ...],
    "mid_credit|dom_standard|turn": [(0.1, 1.0), (0.2, 0.98), (0.3, 0.95), ...],
    ...
}
```

Where each entry is a list of `(seniority_percentile, survival_rate)` tuples.

## Step 4: Wire Survival Curves into the Optimizer

Currently, `estimate_attainability()` in `optimizer.py` uses `compute_attainability()` from holdability.py — a pure heuristic (Level 1). Update it to:

1. **On startup / when award files are available**: parse the 3 PDFs and build survival curves. Cache the result (don't re-parse on every request).
2. **In `estimate_attainability()`**: if survival curves exist, look up the user's seniority percentage and the pairing's trait profile, then interpolate the empirical survival rate. This replaces the heuristic `compute_attainability()` with real data.
3. **Blend**: if we have empirical data for this trait combo, use 80% empirical + 20% heuristic. If the trait combo is too rare (<5 samples across months), fall back to broader trait matches or pure heuristic.
4. **Store the curves on a module-level cache** or pass them through the optimize_bid call. Don't re-parse PDFs on every API call.

The critical update: `seq["_holdability"]` should now be based on **real award data** instead of pure heuristic when the award files are available. This flows into the CP-SAT objective (in `cpsat_builder.py`) which already uses `_holdability` to blend quality vs attainability.

## Step 5: Add API Endpoint for Award File Upload & Analysis

Add to `backend/app/routes/awards.py`:

```
POST /awards/upload-base-award  — Upload a base-wide award PDF
GET  /awards/survival-curves    — Get the computed survival curves
GET  /awards/accuracy-check     — Compare our predictions vs actual awards
```

The upload endpoint should:
1. Accept a PDF file upload
2. Parse it with the award parser
3. Store the parsed data (MongoDB or file system)
4. Trigger survival curve rebuild

The accuracy-check endpoint should:
1. Take a bid period ID and the user's seniority
2. For each sequence in that bid period's pool, compare our predicted holdability vs whether it was actually awarded to someone at or below the user's seniority
3. Return accuracy metrics: precision, recall, and a confusion matrix for our LIKELY/COMPETITIVE/LONG SHOT categories

## Step 6: Accuracy Report

After implementing, run the analysis on all 3 months and produce a calibration report. For the user's mom at ~30% seniority:

1. What does the old heuristic predict for each trait category?
2. What does the empirical data show?
3. Where are the biggest gaps? (e.g., the heuristic might over-estimate survival for HNL trips or under-estimate for mid-week domestic turns)
4. What specific adjustments did the empirical data make to `DEMAND_MODIFIERS` or `LAYER_OPTIMISM` in holdability.py?

Log the before/after accuracy to `award_calibration_report.md`.

## Step 7: Update DEMAND_MODIFIERS with Empirical Data

After computing survival curves from real data, update the `DEMAND_MODIFIERS` dict in `holdability.py` so that even without the raw curves loaded, the heuristic is closer to reality. For example:

- If HNL trips (premium domestic) actually survive to seniority 40% in the data but the heuristic says they don't survive past 20%, reduce `premium_domestic` from 1.2 toward 1.0
- If redeye trips are actually more available than the heuristic thinks, adjust `redeye_odan` from 0.4 toward a higher value
- If early-report trips are popular (not unpopular like the heuristic assumes), increase `early_report` from 0.8

These should be data-driven adjustments based on the 3 months of empirical evidence.

## Important Context

- The existing sequence pool PDFs (parsed by `pdf_parser.py`) have different format from these award PDFs. Don't mix up the parsers.
- The existing `holdability.py` Level 2 calibration (`calibrate()`) uses per-user award history (one user's awards over time). Level 3 (what you're building) uses **base-wide** data (all FAs' awards for one month). They complement each other.
- The CP-SAT builder in `cpsat_builder.py` already uses `seq["_holdability"]` in its objective function — you don't need to change the solver, just make `_holdability` more accurate.
- The `LAYER_OPTIMISM` dict controls how much each layer prioritizes quality vs attainability. Don't change these values — they're about bid strategy, not prediction accuracy.
- Sequence numbers in the award files (0667, 5338, etc.) should match sequence numbers in the bid pool PDFs. This is how you can cross-reference: parse the award, find seq 0667 was awarded to line 50, then look up seq 0667's characteristics from the bid pool data.
- The award PDFs have `-- N of 400 --` page markers. Total lines varies by month (check each file).
- Some pairings show "PUR" as position (purser) — treat these the same as numbered positions for survival analysis.

## Tests

Add tests in `backend/tests/test_award_parser.py`:
1. Parse a small synthetic award block and verify extraction
2. Verify survival curve computation with known data
3. Verify the blended holdability score uses empirical data when available
4. Edge cases: "NO PAIRINGS AWARDED" lines, concatenated sequence numbers, page breaks

## Summary of Files to Create/Modify

**Create:**
- `backend/app/services/award_parser.py` — Parse base-wide award PDFs
- `backend/tests/test_award_parser.py` — Tests for the parser
- `award_calibration_report.md` — Before/after accuracy analysis

**Modify:**
- `backend/app/services/holdability.py` — Implement `build_survival_curves()`, add curve lookup
- `backend/app/services/optimizer.py` — Wire empirical curves into `estimate_attainability()`
- `backend/app/routes/awards.py` — Add upload and analysis endpoints
- `backend/app/models/schemas.py` — Add schema models for survival curve data if needed
