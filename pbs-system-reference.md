# American Airlines PBS Bidding System — Complete Interface Documentation

Source: Live system at fapbs.aa.com/aospbs2 (April 2026 ORD bid package, V.7 — 15 MAR 2026), plus APFA training materials at apfa.org

---

## 1. BIDDING WORKFLOW (Screen-by-Screen)

The PBS application has 8 main tabs in a fixed navigation bar. The workflow is non-linear but the logical build flow is:

**Dashboard → LH Days Off → Pairing → Line → RSV Days Off → Layer → (Submit/Save) → Award → Standing Bid**

### Tab 1: DASHBOARD
Read-only context: Bid Package Information (bid window open/close dates in DFW time), Targeted Line count, Targeted Reserve count, Total Bidders, User Information (Base, Fleet, Position, Seniority #/%, Status, Language, Existing Credit, Training Month), Last Login, Message Board.

### Tab 2: LH DAYS OFF (Lineholder Days Off)
Days-off preferences. Shows existing Days Off Properties with layer assignments, "Add Days Off Properties" panel with Favorites and Other Properties.

### Tab 3: PAIRING
Pairing filter criteria that build pairing pools. Shows existing Pairing Properties, "Add More Properties" button, "Search Pairings" button (opens searchable pairing browser). April 2026 ORD: 2043 pairing IDs, 14383 total positions.

### Tab 4: LINE
Line construction preferences (how PBS arranges pairings on schedule). Shows existing Line Properties and "Add Line Properties" panel.

### Tab 5: RSV DAYS OFF (Reserve Days Off)
Reserve-specific bidding. Layer selector, carryover waivers, Block of Reserve Days Off (2-8).

### Tab 6: LAYER
Central management view. Table with all 7 layers: Total Pairings count, Pairings By Layer count, progress bar. Ordered list of all bid items with priority order, bid type, layer assignments (1-7 toggle buttons). "View Pairing Set" button opens detailed pairing browser per layer.

### Tab 7: AWARD
Post-processing results. Awarded layer, Off days, Credit, Premium hours. Pairing details. "View Reason Report" button.

### Tab 8: STANDING BID
Persistent bid template across months. "Import from Current Bid" and "Export to Current Bid". Lists ALL available bid properties.

---

## 2. COMPLETE PROPERTY CATALOG

### 2A. DAYS OFF PROPERTIES (7 total)

| # | Property | Type | Values | Description |
|---|----------|------|--------|-------------|
| 1 | Maximize Total Days Off | Toggle | On/Off | Maximize total days off |
| 2 | Minimize Days Off between Work Blocks | Numeric | Integer (min days) | Min gap between work blocks |
| 3 | Maximize Weekend Days Off | Toggle | On/Off | Prioritize Sat/Sun off |
| 4 | Maximize Block of Days Off | Toggle | On/Off | Cluster days off together |
| 5 | String of Days Off Starting on Date | Date picker | Calendar date | Days-off block starting on date |
| 6 | String of Days Off Ending on Date | Date picker | Calendar date | Days-off block ending on date |
| 7 | Waive Minimum Days Off | Toggle | On/Off | Allow PBS below contractual minimum |

### 2B. LINE PROPERTIES (18 total, 1 Favorite)

| # | Property | Type | Values | Favorite | Description |
|---|----------|------|--------|----------|-------------|
| 1 | Target Credit Range | Range | HH:MM – HH:MM | YES | Desired credit hour range |
| 2 | Maximize Credit | Toggle | On/Off | | Maximize credit hours |
| 3 | Work Block Size | Range | Min 1-9, Max 1-9 | | Consecutive working days (MUST expand in later layers) |
| 4 | Prefer Cadence on Day-of-Week | Day selector | Days of week | | Regular work pattern |
| 5 | Commutable Work Block | Toggle+config | On/Off with params | | Commuter-friendly blocks |
| 6 | Pairing Mix in a Work Block | Selection | Mix options | | Control pairing type mixing |
| 7 | Allow Double-Up on Date | Date picker | Calendar date | | Two pairings touching on date |
| 8 | Allow Double-Up by Range | Date range | Start – End | | Double-ups across date range |
| 9 | Allow Multiple Pairings | Toggle | On/Off | | Multiple pairings in work block |
| 10 | Allow Multiple Pairings on Date | Date picker | Calendar date | | Multiple pairings on specific date |
| 11 | Allow Co-Terminal Mix in Work Block | Toggle | On/Off | | Mix satellite airport pairings |
| 12 | Clear Bids | Toggle | On/Off | | Clear all bids for layer |
| 13 | Waive Carry-Over Credit | Toggle | On/Off | | Waive carry-over credit |
| 14 | Avoid Person | Text/ID | Employee ID | | Avoid specific crew member |
| 15 | Buddy With | Text/ID | Employee ID | | Fly with specific crew member |
| 16 | Waive 24 hrs rest in Domicile | Toggle | On/Off | | Waive 24hr rest at base |
| 17 | Waive 30 hrs in 7 Days | Toggle | On/Off | | Waive 30hr-in-7-days rest |
| 18 | Waive Minimum Domicile Rest | Toggle | On/Off | | Waive minimum domicile rest |

### 2C. PAIRING PROPERTIES (34 total, 5 Favorites)

**Favorites:**

| # | Property | Type | Values | Description |
|---|----------|------|--------|-------------|
| 1 | Report Between | Time range | HH:MM – HH:MM | Filter by report time window |
| 2 | Release Between | Time range | HH:MM – HH:MM | Filter by release time window |
| 3 | Prefer Pairing Type | Dropdown | Regular, NIPD, IPD, Premium Transcon, ODAN, Red-Eye, Satellite | Filter by trip category |
| 4 | Co-Terminal/Satellite Airport | Dropdown/text | Airport codes | Filter for satellite base pairings |
| 5 | Prefer Positions Order | Ordered list | Position numbers (e.g., "03,04,01,02") | Seat/position preference order |

**Other Properties:**

| # | Property | Type | Values | Description |
|---|----------|------|--------|-------------|
| 6 | Prefer Pairing Length | Integer | 1-5 (calendar days) | Filter by trip length |
| 7 | Prefer Pairing Length on Date | Int + Date | Length + date | Trip length for specific departure |
| 8 | Prefer Duty Period | Integer | 1-5 | Filter by duty period count |
| 9 | Report Between on Date | Time + Date | HH:MM–HH:MM + date | Report time for specific date |
| 10 | Release Between on Date | Time + Date | HH:MM–HH:MM + date | Release time for specific date |
| 11 | Mid-Pairing Report After | Time | HH:MM | Min report on middle days |
| 12 | Mid-Pairing Release Before | Time | HH:MM | Max release on middle days |
| 13 | Maximum TAFB-credit ratio | Numeric | Decimal (e.g., 2.5) | Max TAFB-to-credit ratio |
| 14 | Minimum Avg Credit per Duty | Time | HH:MM (e.g., 05:00–08:00) | Min avg credit per duty period |
| 15 | Maximum Duty Time per Duty | Time | HH:MM | Max duty period length |
| 16 | Maximum Block per Duty | Time | HH:MM | Max block time per duty |
| 17 | Minimum Connection Time | Time | HH:MM | Min connection time |
| 18 | Maximum Connection Time | Time | HH:MM | Max connection time |
| 19 | Prefer Deadheads | Toggle | On/Off | Prefer pairings with DH legs |
| 20 | Avoid Deadheads | Toggle | On/Off | Exclude pairings with DH legs |
| 21 | Layover at City | Text/dropdown | 3-letter airport code | Require layover at city |
| 22 | Avoid Layover at City | Text/dropdown | 3-letter airport code | Exclude layovers at city |
| 23 | Layover at City on Date | Airport + Date | Code + calendar date | Layover at city on specific date |
| 24 | Minimum Layover Time | Numeric | Minutes | Min layover duration |
| 25 | Maximum Layover Time | Numeric | Minutes | Max layover duration |
| 26 | Prefer Landing at City | Text/dropdown | 3-letter airport code | Prefer flights landing at city |
| 27 | Avoid Landing at City | Text/dropdown | 3-letter airport code | Exclude flights landing at city |
| 28 | Prefer One Landing on First Duty | Toggle | On/Off | Single-leg first duty (commuter) |
| 29 | Prefer One Landing on Last Duty | Toggle | On/Off | Single-leg last duty (commuter) |
| 30 | Maximum Landing per Duty | Integer | 1-5+ | Max legs per duty period |
| 31 | Prefer Aircraft | Dropdown | 320, 321/A21, 737/38K, 38M, 777/77W, 787/788, 789, 78P | Filter for aircraft type |
| 32 | Avoid Aircraft | Dropdown | Same codes | Exclude aircraft type |
| 33 | Prefer Language | Dropdown | Language qualifications | Filter language-required pairings |
| 34 | Prefer Positions Order per Aircraft | List + Aircraft | Positions per equipment | Position prefs by aircraft |

**Search-only:**

| 35 | Pairing ID | Text | Pairing sequence number (e.g., R00555) | Search specific pairing |

### 2D. RESERVE PROPERTIES (4 total)

| # | Property | Type | Values | Description |
|---|----------|------|--------|-------------|
| 1 | Waive Carryover Days Off | Toggle + Waiver | On/Off | Carry-over as days off |
| 2 | Block of Reserve Days Off | Dropdown | 2-8 | Consecutive reserve days off |
| 3 | Reserve Day of Week Off | Day selector | Day of week | Prefer specific day(s) off |
| 4 | Reserve Work Block Size | Range | Integer range | Reserve work block size |

---

## 3. LAYER MECHANICS

- **7 layers** (L1 = highest priority, L7 = lowest)
- Each property instance can be toggled onto multiple layers (buttons 1-7)
- Same property type + different values = **OR** (expands pool)
- Different property types = **AND** (restricts pool)
- Pairings within the same layer are treated as **equal** (no internal priority)
- To prioritize one pairing over another, put preferred in a **higher layer** (lower number)
- **Work Block Size is cumulative** — can only expand in later layers, never restrict
- Beyond Layer 7, PBS uses default pairing pool (all base pairings) as fallback

### Example Pairing Counts (ORD, April 2026)

| Layer | Total Pairings | Pairings By Layer |
|-------|---------------|-------------------|
| 1 | 435 | 435 |
| 2 | 451 | 16 |
| 3 | 467 | 16 |
| 4 | 504 | 37 |
| 5 | 619 | 115 |
| 6 | 840 | 221 |
| 7 | 1,942 | 1,102 |
| Full package | 14,383 | — |

---

## 4. EQUIPMENT CODES

| Code | Aircraft | Category |
|------|----------|----------|
| 320 | Airbus A320 | Narrowbody Domestic |
| 321 / A21 | Airbus A321 | Narrowbody Domestic |
| 737 / 38K | Boeing 737-800 | Narrowbody Domestic |
| 38M | Boeing 737 MAX 8 | Narrowbody Domestic |
| 777 / 77W | Boeing 777-300ER | Widebody International |
| 787 / 788 | Boeing 787-8 | Widebody International |
| 789 | Boeing 787-9 | Widebody International |
| 78P | Boeing 787 variant | Widebody International |

---

## 5. PAIRING TYPES

| Value | Description |
|-------|-------------|
| Regular | Standard domestic or international pairings |
| NIPD | Non-International Per Diem |
| IPD | International Per Diem |
| ODAN | Over-night/Day-And-Night |
| Red-Eye | Overnight flights |
| Satellite | Co-terminal airport pairings |
| Premium Transcon | Premium transcontinental routes |

---

## 6. STRATEGIC NOTES

1. Start with most restrictive preferences in Layer 1, progressively relax in later layers
2. Always check Layer tab pairing counts after every change
3. Pairing Length (calendar days) != Duty Period count — use both strategically
4. Work Block Size: can only expand in later layers (cumulative rule)
5. Min Avg Credit per Duty: default ~5:00, raising to 7:00-8:00 dramatically reduces pool
6. Commuter tips: "One Landing on First/Last Duty" + Report/Release Between
7. No explicit "Award Me Anything" — if 7 layers insufficient, PBS uses default pool
