# Full Application Testing Prompt

You are testing a flight attendant bid optimization web application for American Airlines. The app helps FAs build PBS (Preferential Bidding System) bids by parsing bid sheet PDFs, configuring properties across 7 layers, and generating optimized rank-ordered bid lists.

## How to Start the App

### Terminal 1 — Backend (FastAPI)
```bash
cd "/Users/crus/Desktop/IBM Workshop/backend"
pip install -r requirements.txt   # first time only
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Backend runs on http://localhost:8000. Health check: `GET /` returns `{"status":"ok"}`.

### Terminal 2 — Frontend (React/Vite)
```bash
cd "/Users/crus/Desktop/IBM Workshop/frontend"
npm install   # first time only
npm run dev
```
Frontend runs on http://localhost:5173. Proxies `/api/*` to the backend.

### Test Data
- **Real bid sheet PDF:** `/Users/crus/Desktop/IBM Workshop/ORDSEQ2601.pdf` (447 pages, ~1705 sequences, ORD base, January 2026)
- **Database:** AstraDB (credentials in `backend/.env` — already configured)

---

## What to Test (Full Workflow)

Test the **complete user journey** end-to-end, in this exact order. For each step, verify both the UI behavior AND the API responses. Report any errors, broken UI, missing functionality, or deviations from expected behavior.

### Phase 1: Registration & Authentication

1. **Open** http://localhost:5173 — should redirect to `/login`
2. **Navigate** to `/register`
3. **Register** a new account with these exact values:
   - Email: `testfa@aa.com`
   - Password: `TestPassword123`
   - Display Name: `Test FA`
   - Base City: `ORD`
   - Seniority Number: `1500`
   - Total FAs at Base: `5000`
   - Position Min: `1`
   - Position Max: `9`
   - Language Qualifications: `JP` (Japanese)
4. **Verify** the app redirects to the dashboard after registration
5. **Verify** the user profile is accessible at `/profile` and shows all entered data
6. **Test logout** and **re-login** with the same credentials — verify it works

### Phase 2: Bid Period Setup & PDF Parsing

7. **Navigate** to `/bid-periods`
8. **Upload** the bid sheet PDF:
   - File: Select `ORDSEQ2601.pdf` from the file system
   - Name: `January 2026`
   - Effective Start: `2026-01-01`
   - Effective End: `2026-01-30`
9. **Verify** the upload succeeds and shows `parse_status: "processing"`
10. **Poll/refresh** until parsing completes — verify `parse_status: "completed"`
11. **Verify** the bid period shows:
    - `total_sequences` > 1000 (expect ~1705)
    - `categories` list includes entries like "777 INTL", "787 INTL", "NBI INTL", "NBD DOM"
    - `total_dates` = 30

### Phase 3: Sequence Browsing & Filtering

12. **Navigate** to the sequence browser for this bid period
13. **Verify** sequences are displayed in a paginated table with columns: SEQ number, category, OPS count, TPAY, block, TAFB, duty days, layover cities
14. **Test filtering:**
    - Filter by category = "777 INTL" → should show only widebody international sequences
    - Filter by `is_turn = true` → should show only single-day turns
    - Filter by layover city = "NRT" → should show sequences with Tokyo layovers
    - Filter by TPAY range (min=500, max=1200) → should narrow results
    - Filter by `eligible_only = true` → should show sequences matching user's position (1-9) and language (JP)
    - Clear all filters → should return to full list
15. **Test sorting:** Sort by TPAY descending → highest-pay sequences first
16. **Click** on a specific sequence to view its detail page — verify it shows:
    - Full duty period breakdown with legs
    - Report/release times (local and base)
    - Layover hotel/transport info (if applicable)
    - Totals (block, SYNTH, TPAY, TAFB)
    - Operating dates calendar
    - CBA classification fields: is_ipd, is_nipd, is_odan, international_duty_type (if applicable)

### Phase 4: PBS Property-Based Bid Configuration (THE CORE WORKFLOW)

This is the main feature to test thoroughly. The workflow should be a **3-step process** matching the real AA PBS system at fapbs.aa.com.

17. **Navigate** to the bid period detail page (`/bid-periods/{id}`)
18. **Verify** the page shows a 3-step workflow indicator: "Configure Properties" → "Generate Bid" → "Review Results"

#### Step 1: Configure Properties

19. **Verify** Step 1 shows two panels:
    - **Left (main area):** PropertyCatalog component with 4 category tabs (Days Off, Pairing, Line, Reserve)
    - **Right (sidebar):** LayerSummaryPanel showing 7 layers with pairing counts

20. **Test the Pairing tab:**
    - Click "Add Property" → verify Favorites section shows: Report Between, Release Between, Prefer Pairing Type, Co-Terminal/Satellite Airport, Prefer Positions Order
    - Click "Report Between" → verify it appears in the active properties list with a time range input (two time pickers)
    - Set Report Between to **05:00 – 08:00** on layers **1, 2**
    - Click "Add Property" again → add "Prefer Pairing Type" → select **IPD** → assign to layer **1**
    - Click "Add Property" → add "Layover at City" → type **NRT** → assign to layers **1, 2, 3**
    - Click "Add Property" → add another "Layover at City" → type **LHR** → assign to layers **1, 2, 3**
    - **Verify OR logic:** Since two "Layover at City" values are on the same layers, they should expand the pool (NRT OR LHR)

21. **Test the Days Off tab:**
    - Switch to Days Off tab
    - Add "Maximize Total Days Off" → toggle On → assign to layers **1-7**
    - Add "String of Days Off Starting on Date" → set date to **2026-01-15** → assign to layer **1**

22. **Test the Line tab:**
    - Switch to Line tab
    - Add "Target Credit Range" → set to **70:00 – 85:00** → assign to layers **1-7**
    - Add "Maximize Credit" → toggle On → assign to layers **1-7**

23. **Verify Layer Summary Panel updates** after each property change:
    - Layer 1 should show the most restrictive pairing count (IPD + Report 05:00-08:00 + NRT or LHR layover)
    - Layer 2 should show slightly more (Report 05:00-08:00 + NRT or LHR, but no IPD restriction)
    - Layers 4-7 should show higher counts (fewer restrictions)
    - The pairing counts should increase progressively from L1 → L7

24. **Click a layer number** in the sidebar → verify the **LayerDetailView** opens showing all properties assigned to that layer, grouped by category

25. **Test property management:**
    - Toggle a property's **enable/disable** checkbox → verify layer counts update
    - Change a property's **layer assignment** (click layer buttons 1-7) → verify counts update
    - **Remove** a property (click X) → verify it disappears and counts update
    - Re-add it → verify it comes back

#### Step 2: Generate Bid

26. **Click Step 2** ("Generate Bid") in the step indicator
27. **Verify** it shows:
    - Configuration summary: count of active properties by category
    - A warning if no properties are configured (suggesting to go back to Step 1)
    - "Generate Optimized Layers" button
    - Previous bids selector (if any exist)
28. **Click "Generate Optimized Layers"**
29. **Verify** the loading spinner shows while the optimizer runs
30. **Verify** the app transitions to Step 3 after generation completes

#### Step 3: Review Results

31. **Verify** the results display shows:
    - Summary bar: Total sequences ranked, Total TPAY, Days Off, Conflict Groups, Date Coverage %
    - **7 layer cards** (not 9) — labeled "Layer 1" through "Layer 7"
    - Each layer card shows: layer number, sequence count, property description, average match score
32. **Expand Layer 1** → verify:
    - It contains IPD sequences with NRT or LHR layovers and report times between 05:00-08:00
    - Each entry shows: rank, SEQ number, TPAY, layovers, match %, attainability (high/medium/low)
    - "Copy to clipboard" button works
    - Instruction text references fapbs.aa.com
33. **Expand Layer 7** → verify it has the most sequences (widest pool, fewest restrictions)
34. **Verify** the portal submission instructions are shown at the bottom

#### Export

35. **Click** Export TXT → verify a file downloads with 7 layers and sequence numbers
36. **Click** Export CSV → verify a CSV downloads with rank, SEQ, layer, scores
37. **Verify** the TXT export includes a "PBS Properties Summary" header section listing properties per layer

### Phase 5: CBA Validation

38. **Navigate** to the bid's validate endpoint (either via UI button or direct API call):
    ```
    POST /bid-periods/{id}/bids/{bidId}/validate
    ```
39. **Verify** the response includes:
    - `is_valid`: boolean
    - `violations`: array (may be empty if bid is valid)
    - `credit_hour_summary`: with estimated_credit_hours, line_min, line_max, within_range
    - `days_off_summary`: with total_days_off, minimum_required (11), meets_requirement

### Phase 6: Backward Compatibility

40. **Test legacy 9-layer mode:** Create a bid with NO PBS properties, then optimize it:
    ```
    POST /bid-periods/{id}/bids  (name: "Legacy Test")
    POST /bid-periods/{id}/bids/{id}/optimize
    ```
    Verify entries have `layer` values 1-9 (not 1-7) since no PBS properties trigger the legacy path.

### Phase 7: API-Level Verification

Test these API calls directly (via curl, Postman, or the browser console) to verify the backend independently of the frontend:

41. **Property CRUD:**
    ```bash
    # Add a property
    curl -X POST http://localhost:8000/bid-periods/{bpId}/bids/{bidId}/properties \
      -H "Authorization: Bearer {token}" \
      -H "Content-Type: application/json" \
      -d '{"property_key":"prefer_aircraft","value":"777","layers":[1,2]}'

    # List properties
    curl http://localhost:8000/bid-periods/{bpId}/bids/{bidId}/properties \
      -H "Authorization: Bearer {token}"

    # Update property
    curl -X PUT http://localhost:8000/bid-periods/{bpId}/bids/{bidId}/properties/{propId} \
      -H "Authorization: Bearer {token}" \
      -H "Content-Type: application/json" \
      -d '{"property_key":"prefer_aircraft","value":"787","layers":[1,2,3]}'

    # Delete property
    curl -X DELETE http://localhost:8000/bid-periods/{bpId}/bids/{bidId}/properties/{propId} \
      -H "Authorization: Bearer {token}"
    ```

42. **Layer summaries:**
    ```bash
    curl http://localhost:8000/bid-periods/{bpId}/bids/{bidId}/layers \
      -H "Authorization: Bearer {token}"
    ```
    Verify: returns 7 LayerSummary objects with `layer_number`, `total_pairings`, `pairings_by_layer`, `properties_count`. Total pairings should increase from L1→L7 when properties are restrictive on lower layers.

43. **Validation errors:**
    - Add a property with `property_key: "nonexistent"` → expect 400 or 422
    - Add a property with `layers: [8]` → expect 400 or 422
    - Add a property with `category: "invalid"` → expect 400 or 422

---

## What to Report

For each test step, report:

1. **PASS / FAIL / PARTIAL** — did it work as expected?
2. **Screenshot or response** — what did you actually see?
3. **Error details** — if failed, exact error message, HTTP status code, console errors
4. **UI issues** — layout broken, missing elements, wrong labels, bad styling
5. **Data issues** — wrong counts, missing fields, incorrect calculations

### Critical Success Criteria

The app **passes** if:
- [ ] Registration and login work end-to-end
- [ ] PDF upload and parsing complete successfully with ~1705 sequences
- [ ] Sequence browser loads, filters, sorts, and paginates correctly
- [ ] The 3-step PBS property workflow is functional (not the old flat-preference UI)
- [ ] Properties can be added, edited, toggled, layer-assigned, and removed
- [ ] Layer summary panel shows real pairing counts that change when properties change
- [ ] Optimizer produces 7-layer results when PBS properties are configured
- [ ] Optimizer produces 9-layer results when NO properties exist (backward compat)
- [ ] Export produces correct TXT/CSV with layer structure
- [ ] CBA validation endpoint returns structured results
- [ ] No JavaScript console errors during normal operation
- [ ] No 500 errors from the backend during normal operation

### Known Limitations (Don't Report as Bugs)

- Pre-existing TypeScript build errors in `SequenceBrowserPage.tsx`, `SequenceComparisonPage.tsx`, and `vite.config.ts` (these are from before Phase 15)
- Pre-existing test failures in `test_optimizer_phase3_5.py`, `test_optimize_endpoint.py`, `test_export.py`, `test_optimizer_phase1_2.py` (pre-existing, unrelated to our changes)
- Days Off and Line properties affect scoring but not hard schedule constraints yet (planned for future phase)
- Standing Bids feature is not implemented (out of scope)
- Reserve-specific properties only apply when user `is_reserve=true`
