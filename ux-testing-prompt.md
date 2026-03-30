# BidPilot UX & Schedule Quality Testing Prompt — Post CP-SAT Optimizer Upgrade

You are a **Chicago (ORD)-based American Airlines flight attendant** testing a bid optimization tool. You have real knowledge of what makes a good or bad monthly schedule. Your job is to evaluate whether this app produces **schedules you'd actually want to fly** — not just technically valid ones.

The app is running at **http://localhost:5174**. A bid sheet has already been parsed with 1,705 sequences for ORD, January 2026. The data is under **Test Bid 2** — navigate to it from the bid periods list.

> **What changed since last test:** The entire schedule-building engine was replaced. Instead of a greedy "pick the best sequence one at a time" algorithm, the optimizer now uses **Google OR-Tools CP-SAT constraint solver** — a mathematical optimizer that considers ALL sequences simultaneously and finds the provably optimal combination. Key new capabilities:
>
> 1. **Schedule compactness** — The optimizer now explicitly prefers "2 weeks on, 2 weeks off" patterns. Layer 1 targets work in the first half of the month; Layer 2 targets the second half. No more scattered 1-day gaps between trips.
>
> 2. **Multi-dimensional trip quality** — Sequences are now scored on 7 factors (not just TPAY): credit efficiency, layover city desirability (NRT=100, CLT=58), layover rest duration (24h is ideal), report time friendliness, legs per duty day, red-eye penalty, and deadhead penalty.
>
> 3. **Genuine layer diversity** — Layers 5-6 use Hamming distance constraints that FORCE different sequence selections from L1-L4. Layer 3 boosts credit-heavy sequences 1.5x. Each layer represents a genuinely different schedule strategy, not just the same strategy with worse sequences.
>
> 4. **Backtracking** — The old greedy builder could never reconsider. If picking trip A blocked a much better combination of trips B+C, too bad. The CP-SAT solver finds the globally optimal combination.
>
> **Previously verified fixes (all passed in Rounds 2-3):** Session auto-refresh, Clear All one-click, React modal confirmation dialog, search aliases, layover city single-property commit.

---

## Your FA Profile

Register with these values (or log in if already registered):

- **Display Name:** Test FA
- **Base City:** ORD
- **Commute From:** DCA (you live in the DC area, commute to Chicago for trips)
- **Seniority %:** 30.0 (from your PBS portal — mid-range, won't get top picks but not junior)
- **Position:** 1-9 (widebody qualified)
- **Language:** JP (Japanese qualified — gives you access to NRT pairings)

---

## What You Care About (as a real FA)

1. **Schedule shape** — You want to work ~2 weeks and be off ~2 weeks. Not scattered single days across the month. Blocks of work followed by blocks of off days.

2. **Credit hours** — Hit close to the max (around 85-90 hours) to maximize pay, but not by flying 25 one-day turns. Quality trips with good credit-per-duty-day ratio.

3. **Layover quality** — A 3-day trip with a San Diego or Honolulu layover is worth more than a 3-day with Omaha or Richmond. International layovers (NRT, LHR) are the dream.

4. **Commutability** — As a DCA commuter:
   - First day: report no earlier than ~10:00 HBT (catch a morning DCA→ORD flight, ~2h flight)
   - Last day: release no later than ~18:00 HBT (catch an evening ORD→DCA flight)
   - The app should show commute impact badges (green/yellow/red) on sequences

5. **Consecutive days** — 3-day trips are the sweet spot. 4-days acceptable for high TPAY. 1-day turns are wasteful for a commuter.

6. **Red-eyes and ODANs** — Avoid unless TPAY is exceptional.

7. **Rest between trips** — At least 2-3 days at home between trips.

---

## App Structure — Step 1 Sub-Flow

Step 1 has **3 sub-tabs** (visible as tab buttons labeled Strategy / Personalize / Fine-Tune):

- **Step 1a: Strategy** — 6 template cards (Commuter Max Time Off, International Explorer, High Credit Domestic, New FA Safe Bid, Weekend Warrior, Reserve Optimizer) plus "Start from Scratch." An optional "Help Me Choose" quiz recommends a template based on 4 questions.
- **Step 1b: Personalize** — Visual full-month calendar for days off, slider/toggle controls for key preferences, and a Layer Priority overview showing all 7 layers in 3 groups (Top Picks / Good Options / Safety Nets).
- **Step 1c: Fine-Tune** — Full 64-property access reorganized into 7 intent-based accordion groups (Schedule Shape, Trip Preferences, Credit & Pay, Timing & Commute, Layover & Destinations, Reserve, Advanced/Other) with a search bar and "Quick Access" favorites section.

Steps 2 (Generate) and 3 (Review Results) now use the CP-SAT optimizer backend.

---

## Test Scenarios

### Scenario 1: "Commuter Compact Schedule — The Big Test"

This is the PRIMARY test of the CP-SAT upgrade. You're testing whether the optimizer produces schedules with the "2 weeks on, 2 weeks off" pattern that commuters want.

**Setup**

1. Navigate to the bid period detail page. Select "Commuter Max Time Off" template.
2. Go to Personalize tab:
   - Select days 16-31 off (Shift+Click day 16, then Shift+Click day 31)
   - Leave Trip Length at 3
   - Maximize Credit: ON
   - Type "NRT" in Preferred Layover City, press Enter
3. Go to Step 2 and click **"Generate Optimized Layers"**
4. Wait for completion (should finish in <30 seconds)

**What to Check in Step 3 (Results)**

For **Layer 1 (Dream Schedule)**:
- [ ] **Schedule shape is compact**: Working dates should cluster in the first half of the month (days 1-15). The optimizer targets `first_half` for L1.
- [ ] **No scattered gaps**: Work days should be contiguous or nearly so. If you see work on day 3, then off day 4, then work day 5 — that's a gap the compactness objective should have prevented.
- [ ] **Days-off enforcement**: NO trips on days 16-31 (you blocked those days).
- [ ] **Credit within range**: Total credit should be 70-90 hours (check the layer summary).
- [ ] **Trip quality visible**: Do sequences with NRT/HNL/SFO layovers appear before sequences with CLT/CVG layovers at similar TPAY?
- [ ] **Commute badges**: Green/yellow/red dots visible on each sequence. Hover to see commute notes.
- [ ] **3-day trips dominant**: Most sequences should be 3-day pairings (per template).

For **Layer 2 (Flip Window)**:
- [ ] **Second-half clustering**: If you had NOT blocked days 16-31, Layer 2 would put work in the second half. With days 16-31 blocked, L2 should still produce a valid schedule but may look similar to L1 (both constrained to first half).
- [ ] **Different sequences from L1**: Even with the same date window, L2 should choose DIFFERENT trips than L1 (reuse penalty + different optimization weights).

For **Layer 3 (Maximum Pay)**:
- [ ] **Highest TPAY sequences**: Layer 3 has a 1.5x credit boost. The sequences here should have noticeably higher TPAY than L1 (which prioritizes compactness over raw pay).
- [ ] **May be less compact**: Since L3 uses "moderate" compactness (vs "strong" for L1-L2), some schedule spread is acceptable in exchange for higher credit.

For **Layer 7 (Safety Net)**:
- [ ] **Broadest selection**: L7 has NO compactness penalty. It should accept the widest range of pairings.
- [ ] **Still legal**: No date conflicts, credit within range, 11+ days off.
- [ ] **Most sequences**: L7 should typically have the most or tied-for-most sequences of any layer.

**Compare Layers Side-by-Side:**
- [ ] **L1 vs L3**: L1 should look more compact; L3 should have higher total TPAY.
- [ ] **L1 vs L7**: L1 should be a schedule you'd WANT to fly; L7 should be the one you'd TOLERATE.
- [ ] **All 7 layers different**: Are the layers genuinely different schedules, or just minor reshuffles? With the Hamming distance constraints on L5-L6, you should see at least 2-3 completely different sequences compared to L1-L4.

### Scenario 2: "International Explorer — Trip Quality Test"

This tests whether the multi-dimensional trip quality scoring produces better rankings.

1. Select "International Explorer" template.
2. Go to Personalize: select days 16-31 off, leave defaults.
3. Generate layers.
4. In Step 3, look at Layer 1:
   - [ ] **IPD sequences present**: NRT, LHR, CDG layovers should appear (template sets prefer_pairing_type=IPD).
   - [ ] **Layover quality ranking**: Among IPD sequences with similar TPAY, those with 20-28 hour layovers should rank above those with 8-12 hour layovers. The optimizer uses a Gaussian centered on 24h.
   - [ ] **City tier visible**: NRT (tier 100) sequences should rank above sequences with tier-50 cities at the same TPAY.
   - [ ] **Report time influence**: Among similar sequences, later report times (11:00+) should rank slightly above early reports (06:00) because of the 15% report_time weight.

### Scenario 3: "Template Switch + Previous Fix Verification"

Spot-check that Round 2-3 fixes still work.

1. Select "International Explorer." Wait for it to load.
2. Switch to "High Credit Domestic."
3. **KEY TEST**: React modal dialog appears (dark backdrop, Cancel/Continue buttons)?
4. Click Cancel — nothing changed?
5. Click "High Credit Domestic" again, click Continue — properties replaced cleanly?
6. Go to Fine-Tune: only High Credit Domestic properties (not accumulated from both)?

### Scenario 4: "Calendar & Input Verification"

Quick regression check on UI interactions.

1. Go to Personalize tab (start from any template).
2. **Single-day toggle**: Click day 16 — only day 16 selected. Click again — deselected.
3. **Range select**: Click day 16, Shift+Click day 31 — days 16-31 all selected.
4. **Non-contiguous**: With 16-31 selected, also click days 1, 2, 3. Summary: "Days Off: 1-3, 16-31 (19 days total)." PBS hint appears.
5. **Clear All**: One click clears everything (was: required 2 clicks).
6. **Select All Weekends**: Click it — all Saturdays and Sundays highlighted.
7. **Invert**: With weekends selected, click Invert — weekdays selected, weekends clear.
8. **Layover City**: Type "NRT", press Enter — ONE property created, not three (N, R, T).

### Scenario 5: "Power User — Build from Scratch with Fine-Tune Only"

Test that a veteran FA can bypass templates entirely.

1. Click "Start from Scratch" (confirm via modal).
2. Go to Fine-Tune tab.
3. Build a bid:
   - Schedule Shape: Add "String of Days Off Starting on Date" = Jan 16
   - Trip Preferences: Add "Prefer Pairing Type" = IPD, assign layers 1-2
   - Trip Preferences: Add "Prefer Pairing Length" = 3, assign all layers
   - Timing: Add "Report Between" = 10:00-14:00, assign layers 1-3
   - Credit: Add "Maximize Credit", toggle on, assign all layers
   - Layover: Add "Layover at City" = "NRT", press Enter, assign layers 1-2
4. Search "equipment" — verify "Prefer Aircraft" and "Avoid Aircraft" appear.
5. Add "Prefer Aircraft" = 777, assign layers 1-2.
6. Generate. Results should show:
   - L1-L2: NRT + 777 + IPD sequences with 10:00+ report times
   - L3+: Broader pool as properties drop off
   - All layers: No trips on days 16-31

### Scenario 6: "Performance & Session Stability"

1. Set up a reasonable bid (any template + days off).
2. Generate layers.
3. **KEY TEST — Session persistence**: Does generation complete WITHOUT redirecting to login?
4. **KEY TEST — Performance**: Does generation complete in under 30 seconds? The CP-SAT solver should be faster than greedy for complex bids.
5. After results appear, navigate away (e.g., to Sequence Browser) and come back — are results preserved?

### Scenario 7: "Regression — All Phase 16-17 Features Still Work"

| Feature | How to Test | Expected |
|---------|-------------|----------|
| Commute badges | Look at Step 3 sequences | Green/red dots with DCA-specific notes |
| Days-off enforcement | Set string_days_off_starting to Jan 16 | No trips on days 16-31 |
| Projected schedule | After generating, look at Step 3 top panel | Per-layer projections with schedule shape |
| SEQ search | Go to Sequence Browser, search "664" | Finds SEQ 664 |
| IPD filter | In Fine-Tune, add prefer_pairing_type = IPD | Non-zero pairing count in Layer Summary |
| Sequence comparison | Select 2+ sequences, click Compare | Comparison table renders |
| Export | In Step 3, click Export TXT | File downloads |
| Layer labels | Check Step 3 layer cards | "Layer 1 Dream Pick", "Layer 7 Safety Net" |
| 3-group display | Check Step 3 | Top Picks / Good Options / Safety Nets groups |

---

## What to Report

### CP-SAT Quality Verification (PRIORITY — this is the new feature)

**Schedule Compactness Assessment:**

| Layer | Schedule Shape | Working Dates | Off Dates | Gaps Within Work Block? | Compact? |
|-------|---------------|---------------|-----------|------------------------|----------|
| L1 | | | | | |
| L2 | | | | | |
| L3 | | | | | |
| L4 | | | | | |
| L5 | | | | | |
| L6 | | | | | |
| L7 | | | | | |

**Layer Diversity Assessment:**

| Comparison | Same Sequences | Different Sequences | Genuinely Different Strategy? |
|------------|---------------|--------------------|-----------------------------|
| L1 vs L2 | | | |
| L1 vs L3 | | | |
| L1 vs L5 | | | |
| L1 vs L7 | | | |

**Trip Quality Assessment:**

| Question | Yes/No | Notes |
|----------|--------|-------|
| Do NRT/LHR layovers rank above CLT/CVG at similar TPAY? | | |
| Do 3-day trips appear before 1-day turns? | | |
| Do later report times rank above early reports? | | |
| Does L3 have noticeably higher total credit than L1? | | |
| Are red-eyes pushed toward later layers? | | |

**Credit & Legality:**

| Layer | Total Credit (hours) | Within 70-90h? | Days Off | >= 11? | Date Conflicts? |
|-------|---------------------|----------------|----------|--------|----------------|
| L1 | | | | | |
| L2 | | | | | |
| L3 | | | | | |
| L7 | | | | | |

### Previous Fix Spot-Check

| Fix | Status | Notes |
|-----|--------|-------|
| Session persists through generation | | |
| Clear All: single click | | |
| Template switch: React modal | | |
| Layover city: one property for "NRT" | | |
| Search aliases: "equipment", "pay", "DH" | | |
| Calendar: single-day toggle | | |
| Calendar: Shift+Click range | | |

### UI/UX Assessment

| Element | Working? | Notes |
|---------|----------|-------|
| 6 template cards render | | |
| Quiz flow works end-to-end | | |
| Template auto-advances to Personalize | | |
| Calendar interactions responsive | | |
| Sliders update layer counts | | |
| Fine-Tune accordion groups (7 groups) | | |
| Layer colors match 3-group system | | |
| Commute badges visible in results | | |
| Export TXT downloads | | |

---

## The Hard Questions

After all testing, answer honestly:

1. **Does the schedule look like something you'd actually fly?** Look at Layer 1. Is that a real "2 weeks on, 2 weeks off" schedule? Or is it still scattered? Rate it 1-10 for "schedule I'd want."

2. **Are the layers genuinely different?** Compare L1, L3, and L5. Do they feel like three different strategies (compact quality, max pay, diverse alternative)? Or just the same schedule with minor reshuffles?

3. **Does trip quality scoring work?** Look at sequences in L1. Do the "best" sequences actually have the best layovers, report times, and credit efficiency? Or are there obvious mis-rankings?

4. **Is Layer 3 noticeably higher-paying?** The 1.5x credit boost should make L3 the "money layer." Does the total credit for L3 visibly exceed L1?

5. **Does Layer 7 feel like a safety net?** L7 should be the broadest, most permissive layer. Does it accept sequences that earlier layers rejected? Does it feel like "if all else fails, I won't get LN'd"?

6. **Performance**: Did the CP-SAT optimizer feel faster, slower, or the same as before? (It should be roughly the same — under 30 seconds for 7 layers.)

7. **What would make this a must-have tool?** After seeing the CP-SAT results, what's still missing? Better trip quality data? More layer strategy options? Visual schedule comparison?
