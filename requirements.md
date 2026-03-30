# Scheduling App — Requirements Document

## 1. Overview

The Scheduling App helps airline flight attendants build the best possible bidding schedule from their airline's monthly bid sheet. A bid sheet is a dense, multi-hundred-page document listing every available sequence (pairing) for a given base city and bid period. Each sequence contains one or more duty days with individual flight legs, layover details, report/release times, block hours, and operating dates.

Today, flight attendants manually sift through hundreds of sequences, mentally cross-referencing their preferences, seniority standing, language qualifications, and position eligibility to rank their choices. This process is tedious, error-prone, and time-consuming. The Scheduling App automates this by parsing the bid sheet, letting users define preferences and constraints, and generating an optimized rank-ordered bid.

> **Note:** This app is specifically built for **American Airlines flight attendants** governed by the **2024 AA/APFA Collective Bargaining Agreement** (effective September 12, 2024 through September 11, 2029). The bidding system is the **Preferential Bidding System (PBS)** as defined in CBA Section 10. All scheduling rules, pay provisions, duty limitations, and rest requirements referenced throughout this document are derived from or aligned with this agreement.

---

## 1.1 How Airline Bidding Works

At American Airlines, flight attendant scheduling operates on a **monthly seniority-based bidding cycle** using the **Preferential Bidding System (PBS)** per CBA Section 10.C. FAs are either **Lineholders** (awarded a Line of Time through PBS) or **Reserves** (on-call FAs assigned trips as needed). Understanding this process is essential to understanding what the app does and why.

A **Line of Time** contains a minimum of 70 credit hours and a maximum of 90 credit hours per bid period (CBA Section 2.EE). The Company may flex these limits by up to ±25 hours annually, with no more than 5 hours in any single month. FAs may also elect **High Option** (up to 110 credit hours) or **Low Option** (down to 40 credit hours) to tailor their monthly workload. The monthly minimum guarantee is 71 hours for Lineholders and 75 hours for Reserves (CBA Section 3.B).

### The Monthly Cycle

1. **Bid sheet published** — Approximately 2–3 weeks before the start of the next month, American Airlines publishes a bid sheet for each crew base. This document lists every available sequence (trip/pairing) that will operate during the upcoming bid period. A single bid sheet can be hundreds of pages long and contain 500–1,000+ sequences.

2. **PBS bidding window opens** — Flight attendants have a limited window (typically 3–5 days) to review the bid sheet and submit their bid into the PBS system. A bid is a **rank-ordered list of sequence preferences** — the FA's #1 most-wanted sequence first, #2 second, and so on, for as many sequences as they wish to rank.

3. **PBS seniority-based awarding** — After the bidding window closes, the PBS system awards Lines of Time strictly by seniority. The most senior FA at the base gets their highest-ranked sequence that is still available and doesn't conflict with their other awards. Then the second-most-senior FA, and so on down the seniority list. Each FA can only be awarded **one sequence per operating date** (no date conflicts). FAs whose bids are not successfully awarded are placed on the **Unsuccessful Bidder's List (UBL)**.

4. **Award published & post-award trading** — The airline publishes each FA's awarded schedule (Line of Time) for the month. After PBS awards, the **Trip Trade System (TTS)** allows seniority-based daily trading of sequences, and the **Electronic Trade Board (ETB)** allows first-come/first-served trades, pick-ups, and drops. These systems give FAs ongoing flexibility to adjust their monthly schedule.

5. **Fly the schedule** — The FA flies their awarded sequences for the month. The cycle then repeats.

### What Makes a "Good" Bid

A good bid is not simply "rank my favorite trips first." It requires strategy:

- **Seniority awareness**: A junior FA who ranks the most desirable sequences first is wasting those ranks — senior FAs will take them. A strategic bid accounts for what is realistically attainable at your seniority level.
- **Date conflict management**: Sequences that operate on overlapping dates are mutually exclusive. A good bid considers which date clusters to target and ranks alternatives for the same date slots.
- **Depth of coverage**: A bid should rank enough sequences to cover the entire month. If the bid is too short or too narrow, the FA risks falling to reserve for uncovered dates.
- **Preference balancing**: FAs must weigh competing goals — high pay (TPAY) vs. days off, preferred layovers vs. favorable report times, international vs. domestic — and decide what matters most for each bid period.

### Where the App Fits

The Scheduling App sits between the published bid sheet and the airline's bid submission system:

```
Airline publishes       ┌──────────────────────┐       FA submits
  bid sheet PDF    ──→  │   Scheduling App      │  ──→  rank-ordered
  (raw data)            │                      │       bid list
                        │  1. Parse bid sheet   │
                        │  2. Browse & filter   │
                        │  3. Set preferences   │
                        │  4. Optimize ranking  │
                        │  5. Adjust & finalize │
                        │  6. Export for submit │
                        └──────────────────────┘
```

The app **does not** interact with the airline's scheduling system or award sequences. It is a **personal planning tool** that helps the FA make smarter bidding decisions by:

- Digitizing the bid sheet so it can be searched, filtered, and sorted
- Letting the FA express their preferences and constraints in structured form
- Generating a strategically optimized rank-ordering that accounts for preference weights, date conflicts, eligibility rules, and schedule constraints
- Providing calendar and comparison views to visualize and validate the bid before submission

After the award is published, the FA can import their awarded schedule into the app to analyze how well their bid performed and refine their strategy for next month.

---

## 2. Glossary

| Term | Definition |
|------|-----------|
| **Sequence (SEQ)** | A numbered pairing of flights that starts and ends at the base city, spanning one or more duty days. The fundamental unit flight attendants bid on. |
| **Leg** | A single flight within a sequence, from one station to another. |
| **Duty Period (DP)** | A working day within a sequence, which may contain one or more legs. |
| **Block Time** | The time from pushback to gate arrival for a flight leg; the primary unit of flight time. |
| **TAFB (Time Away From Base)** | Total elapsed time from report at base to release at base for the entire sequence. |
| **TPAY (Total Pay)** | The total credited pay time for the sequence, which may include synthetic credit. |
| **Synthetic (SYNTH)** | Additional credited time beyond actual block time, per contractual rules. |
| **Report Time (RPT)** | The time a flight attendant must check in before the first leg of a duty period, shown as local/home-base time. |
| **Release Time (RLS)** | The time a flight attendant is released after the last leg of a duty period, shown as local/home-base time. |
| **Deadhead (DH)** | A positioning flight where the flight attendant rides as a passenger (indicated by a "D" suffix on the flight number, e.g., "1105D"). Deadhead legs do not count as working block time. |
| **OPS** | The number of times a sequence operates within the bid period (e.g., "25 OPS" means it runs 25 times that month). |
| **POSN** | The crew position range for the sequence (e.g., "1 THRU 9" for widebody, "1 THRU 4" for narrowbody). |
| **LANG** | Language qualification required for the sequence (e.g., "LANG JP 3" means 3 positions require Japanese; "LANG SP 1" means 1 position requires Spanish). |
| **Equipment (EQ)** | The aircraft type for a given leg (e.g., 777, 787, narrowbody variants). |
| **Station (STA)** | An airport code (e.g., ORD, LHR, NRT, LAS). |
| **PAX SVC** | Passenger service code indicating the cabin service level for a leg (e.g., QLF, QDB, QLS). |
| **Red-eye** | A flight that departs late at night and arrives early the next morning. |
| **Turn / Day Trip** | A single-day sequence that departs and returns to base the same day with no overnight layover. |
| **Layover** | An overnight rest stop at a city away from base between duty periods, including hotel and ground transportation details. |
| **Ground Time** | Time between legs on the same duty day (connections); marked with "X" when it is a connection. |
| **Rest** | Minimum off-duty time between duty periods at a layover city. |
| **Calendar Column** | The column in the bid sheet showing which specific dates in the month a sequence operates. |
| **Base City** | The flight attendant's home airport where all sequences originate and terminate (e.g., ORD). |
| **Bid Period** | The month for which the bid sheet is effective (e.g., January 1–30). |
| **PBS (Preferential Bidding System)** | Electronic system used to create Lineholder and Reserve lines of flying (CBA §2.PP). |
| **Lineholder** | An FA awarded a Line of Time through PBS, as opposed to a Reserve. |
| **Line of Time** | A monthly unit of FA flying containing 70–90 credit hours per bid period, flexable via High Option (≤110h) or Low Option (≥40h) (CBA §2.EE). |
| **Duty Rig** | Pay guarantee of 1 hour for every 2 hours of actual on-duty time, prorated minute-by-minute (CBA §2.P). |
| **Trip Rig** | Pay guarantee of 1 hour for every 3 hours 30 minutes of TAFB, prorated (CBA §2.AAA). |
| **Credit Window** | Difference between the monthly PBS awarded line value and the TTS Maximum; TTS drops/pick-ups/trades affect this window (CBA §2.G). |
| **Golden Days** | Scheduled days off in Reserve lines that cannot be moved without mutual consent (CBA §2.V). |
| **Flex Days** | Scheduled days off in a Reserve line on which a Reserve can be assigned a trip per CBA §12.B.3. |
| **RAP (Reserve Availability Period)** | A 12-hour window during which a Reserve must be contactable and available for assignment. Up to 4 RAPs (A, B, C, D) exist (CBA §12.G). |
| **TTS (Trip Trade System)** | Seniority-based automated daily bidding system that allows FAs to adjust their monthly schedule (CBA §2.DDD). |
| **ETB (Electronic Trade Board)** | Real-time electronic method of picking up, dropping, and trading sequences on a first-come/first-served basis (CBA §2.Q). |
| **IPD (International Premium Destination)** | International flights to/from Europe, Asia, and Deep South America with premium service level (CBA §14.B). |
| **NIPD (Non-International Premium Destination)** | International flying that does not meet the IPD definition (CBA §14.B). |
| **ODAN (On-Duty All-Nighter)** | A single duty period sequence that includes all on-duty hours between 0100 and 0500 HBT (CBA §2.II). |
| **Purser** | Lead/Number 1 position FA on IPD flights, requiring 18 months service and qualification (CBA §14.L). |
| **Home Base Time (HBT)** | The actual time of day in the crew base to which a FA is assigned (CBA §2.X). |
| **Double Up Sequences** | Two sequences within the same duty day with min 30 minutes between release and report (CBA §2.N). |
| **Multiple Sequences** | Multiple sequences terminating and beginning same calendar day, separated by legal crew base rest plus 45 minutes (CBA §2.HH). |
| **Speaker / Foreign Language Speaker** | FA who has passed a Company-approved language proficiency test and is designated to fill language-qualified positions (CBA §2.U, §15). |
| **UBL (Unsuccessful Bidder's List)** | Lineholders whose PBS bid was not awarded in TTS, passed to Daily Scheduling for open time processing (CBA §2.GGG). |
| **Pay No Credit** | Pay above the minimum monthly guarantee that does not count toward credited hours or monthly maximum (CBA §2.LL). |
| **Carry Over/Change Over** | A replacement sequence that modifies an awarded sequence, reporting in one month and releasing in the following month (CBA §2.E). |

---

## 3. Personas

### Persona 1: Junior Flight Attendant ("Alex")

- **Seniority**: Low (1–3 years)
- **Base**: ORD
- **Position**: Narrowbody domestic (POSN 1 THRU 4)
- **Goal**: Maximize days off, avoid red-eyes, and build a livable schedule knowing they are unlikely to get top picks
- **Pain points**: Overwhelmed by a 447-page bid sheet; does not know how to strategically order hundreds of sequences; frequently lands on reserve when their bid is poor; wastes hours manually scanning pages
- **Behavior**: Wants the app to surface "best available" sequences after senior FAs take top picks; needs guidance on which sequences to rank and in what order given their low seniority

### Persona 2: Senior Flight Attendant ("Morgan")

- **Seniority**: High (15+ years)
- **Base**: ORD
- **Position**: Widebody international (POSN 1 THRU 9), holds Japanese language qualification
- **Goal**: Maximize TPAY and credit hours on preferred international routes (NRT, LHR, HNL) while maintaining specific days off and a predictable lifestyle
- **Pain points**: Manually comparing subtle differences across 25+ similar sequences (e.g., SEQ 663 vs. SEQ 664 differ only by report time and operating dates) is tedious; wants fine-grained control to lock favored sequences and rank the rest around them
- **Behavior**: Has strong, specific preferences; wants to filter by equipment (777, 787), layover city, TPAY range, and language-qualified sequences; wants to pin top sequences and let the optimizer fill in the rest

### Persona 3: Commuter Flight Attendant ("Jordan")

- **Seniority**: Mid-range (5–10 years)
- **Base**: ORD (commutes from another city)
- **Position**: Narrowbody international (NBI, POSN 1 THRU 4)
- **Goal**: Build a schedule that clusters trips together to minimize the number of commuting days to ORD, and align report/release times with available commuter flights
- **Pain points**: Scattered single-day turns across the month force expensive and exhausting commutes; needs sequences whose report times are not too early and release times are not too late; hard to visually assess schedule density from a raw bid sheet
- **Behavior**: Prioritizes schedule compactness (back-to-back sequences or multi-day sequences), favorable report/release windows, and wants a calendar visualization to see how trips cluster

### Persona 4: Language-Qualified Flight Attendant ("Yuki")

- **Seniority**: Mid-range (7 years)
- **Base**: ORD
- **Position**: Widebody international (POSN 1 THRU 9), holds Japanese language qualification
- **Goal**: Leverage language qualification to access premium international sequences (NRT routes with "LANG JP" requirement) that fewer FAs can bid on, maximizing both desirable layovers and credit hours
- **Pain points**: Needs to quickly identify which sequences require their language and how many language-qualified positions are available; some LANG JP sequences have only 3 qualified spots out of 9 positions
- **Behavior**: Filters sequences by language requirement first, then ranks by layover quality and TPAY; wants to see how many OPS each language-qualified sequence has to judge competition

---

## 4. User Flows

### Flow 1: First-Time Setup

1. User opens the app for the first time
2. User creates a profile: base city (e.g., ORD), seniority number, position range, and language qualifications (e.g., Japanese, Spanish, or none)
3. User sets default scheduling preferences: preferred days off, min/max TPAY targets, preferred and avoided layover cities, preferred equipment types, report time windows, and red-eye avoidance
4. User saves profile and is taken to the main dashboard

### Flow 2: Import Bid Sheet & Browse Sequences

1. User navigates to "New Bid Period"
2. User uploads the bid sheet file (a PDF document, typically hundreds of pages)
3. App parses the file and extracts all sequences with their complete data: SEQ number, OPS count, position range, language requirements, all legs per duty period (flight number, equipment, departure/arrival stations, local and home-base times, block time, deadhead status, meal codes, PAX service codes, ground/connection times), report/release times, layover hotel and transportation details, totals (block, SYNTH, TPAY, TAFB), and the calendar of operating dates
4. App displays the total number of sequences extracted and organizes them by category (e.g., widebody international, narrowbody international, narrowbody domestic)
5. User reviews a sample of parsed sequences against the original bid sheet to confirm accuracy
6. User confirms the import

### Flow 3: Filter, Sort & Explore Sequences

1. User opens the sequence browser for the imported bid period
2. User applies filters: equipment type, layover city, language requirement, number of duty days, TPAY range, TAFB range, specific operating dates, turn vs. layover, deadhead inclusion
3. User sorts results by any attribute (TPAY, block time, TAFB, number of legs, report time, OPS count)
4. User taps a sequence to see its full detail view: all legs laid out by duty day, layover info, times in both local and home-base, and the month calendar with operating dates highlighted
5. User bookmarks sequences of interest for later inclusion in their bid

### Flow 4: Generate Optimized Bid

1. User navigates to the bid builder and confirms or adjusts their preferences for this period
2. User optionally pins specific sequences to fixed positions in the bid (e.g., "SEQ 675 must be my #1 choice")
3. User optionally excludes specific sequences from consideration
4. User initiates optimization
5. App generates a rank-ordered bid list that maximizes alignment with the user's preferences while respecting constraints (no date conflicts between sequences the FA could realistically be awarded, position eligibility, language qualification match)
6. User reviews the generated list with a summary explaining why each sequence was ranked where it is
7. User manually adjusts the order if desired (drag to reorder, pin, or remove)
8. User re-runs optimization if needed — pinned and excluded items are preserved
9. User finalizes and exports the bid

### Flow 5: Compare Sequences Side by Side

1. User selects two or more sequences from the browser or bid list
2. App displays them in a side-by-side comparison showing: TPAY, block time, TAFB, number of legs, number of duty days, layover cities and hotels, report/release times, operating dates, deadhead legs, equipment types, and language requirements
3. Differences between the sequences are highlighted
4. User can directly promote or demote sequences in the bid list from the comparison view

### Flow 6: Calendar Visualization

1. User opens the calendar view for the current bid period (e.g., January 1–30)
2. The calendar displays all sequences in the current bid list overlaid on the month
3. Each sequence spans its operating dates, colored or labeled by category
4. User can identify gaps (days off), clusters, conflicts, and red-eye legs at a glance
5. User taps any sequence on the calendar to see its full detail
6. User drags sequences on/off the calendar to adjust the bid

### Flow 7: Review & Adjust After Award

1. After the airline publishes the awarded schedule, the user imports the award
2. App displays the awarded sequences on the calendar
3. App compares the award against the submitted bid: which bid preferences were honored, which were not, and any sequences awarded that were not in the bid
4. App displays a match rate and summary statistics
5. User saves this data and uses it to refine preferences for future bid periods

---

## 5. Functional Requirements

### Bid Sheet Parsing

**REQ-001: Import Bid Sheet from PDF**
The system shall allow users to import a bid sheet from a PDF file and extract all sequence data.

_Acceptance Criteria:_
- Given a user on the "New Bid Period" screen, when they upload a bid sheet PDF, then the system extracts all sequences with zero data loss compared to the source document
- Given the parsed bid sheet, then each sequence contains: SEQ number, OPS count, position range (POSN), language qualification (LANG type and count if applicable), and the operating date calendar
- Given each sequence, then every duty period contains: duty period number, day count (D/A), and all legs with equipment type (EQ), flight number (including deadhead designation), departure station, departure local and home-base times, meal code, arrival station, arrival local and home-base times, PAX service code, block time, and ground/connection time
- Given each sequence, then report and release times are extracted for every duty period in both local and home-base time
- Given each sequence with layovers, then hotel name, hotel phone number, ground transportation company, and ground transportation phone number are extracted
- Given each sequence, then totals are extracted: total block, total SYNTH, total TPAY, and total TAFB
- Given a malformed or unsupported PDF, then the system displays a clear error indicating the problem

**REQ-002: Sequence Category Detection**
The system shall automatically detect and categorize sequences by fleet type and route category.

_Acceptance Criteria:_
- Given a parsed bid sheet, then each sequence is categorized by its fleet/route section as it appears in the bid sheet (e.g., widebody 777, widebody 787, narrowbody international, narrowbody domestic)
- Given the footer of each page (e.g., "ORD 777 INTL", "ORD NBD DOM"), then the system uses this to assign the correct category
- Given the categorized sequences, when the user views the sequence list, then they can filter and group by category

**REQ-003: Deadhead Leg Identification**
The system shall identify and flag deadhead legs within sequences.

_Acceptance Criteria:_
- Given a leg with a "D" suffix on the flight number (e.g., "1105D"), then the system marks it as a deadhead
- Given a deadhead leg, then the system does not count its block time toward the sequence's working block total
- Given a sequence containing deadhead legs, when displayed in any view, then deadhead legs are visually distinct from working legs

**REQ-004: Manual Sequence Entry and Editing**
The system shall allow users to manually add or correct individual sequence data.

_Acceptance Criteria:_
- Given the sequence browser, when the user chooses to add a sequence manually, then the system presents a form capturing all fields from REQ-001
- Given an imported sequence with a parsing error, when the user edits any field, then the correction is saved and reflected across all views
- Given a manually entered sequence, then it behaves identically to an imported sequence in all features

### Sequence Browsing & Filtering

**REQ-005: Sequence List View**
The system shall display all sequences for the current bid period in a sortable, filterable list.

_Acceptance Criteria:_
- Given a bid period with imported sequences, when the user opens the sequence list, then each row shows: SEQ number, category, OPS count, number of duty days, number of legs, TPAY, block time, TAFB, layover city/cities, language requirement (if any), and operating date summary
- Given the list, when the user sorts by any column, then the list reorders correctly
- Given the list, when the user applies multiple simultaneous filters, then only matching sequences are shown

**REQ-006: Advanced Filtering**
The system shall support filtering sequences by domain-specific attributes.

_Acceptance Criteria:_
- Given the filter panel, then the user can filter by: equipment type (e.g., 777, 787, narrowbody), layover city, language requirement (JP, SP, or none), number of duty days (1-day turns vs. multi-day trips), TPAY range (min/max), TAFB range (min/max), block time range, specific operating dates (e.g., "only sequences that operate on January 15"), position range, deadhead inclusion, and report/release time window
- Given applied filters, then the result count updates immediately
- Given applied filters, then the user can save a filter preset for reuse

**REQ-007: Sequence Detail View**
The system shall display the full detail of any individual sequence.

_Acceptance Criteria:_
- Given a selected sequence, then the detail view shows the complete itinerary: every duty period with its legs laid out in order, showing flight numbers, equipment, stations, local and home-base times, block time, meal codes, PAX service, ground/connection times, and deadhead status
- Given a sequence with layovers, then each layover shows the hotel name, phone number, ground transportation provider, phone number, and rest duration
- Given the detail view, then report and release times are shown for each duty period in both local and home-base time
- Given the detail view, then totals (block, SYNTH, TPAY, TAFB) are displayed prominently
- Given the detail view, then a mini-calendar highlights which dates in the month this sequence operates

### User Profile & Preferences

**REQ-008: User Profile**
The system shall allow users to create and maintain a profile with scheduling-relevant information.

_Acceptance Criteria:_
- Given a new user, when they complete the profile form, then the system stores: base city, seniority number, position range, and language qualifications held
- Given a saved profile, when the user returns to the app, then their profile is retained and pre-populated
- Given a profile with language qualifications, then the system uses this to identify which language-required sequences the user is eligible for

**REQ-009: Scheduling Preferences**
The system shall allow users to define weighted scheduling preferences that drive optimization.

_Acceptance Criteria:_
- Given the preferences screen, the user can configure: preferred days off (specific dates), preferred and avoided layover cities, minimum and maximum TPAY target for the month, preferred equipment types, preferred report time window (earliest/latest acceptable report), preferred release time window (earliest/latest acceptable release), red-eye avoidance (on/off), preference for turns vs. multi-day trips, preference for high-OPS sequences vs. low-OPS sequences, and trip clustering preference (compact vs. spread out)
- Given each preference, the user can assign a relative weight or priority (e.g., "days off matter more than TPAY")
- Given saved preferences, when starting a new bid period, then defaults are pre-loaded but editable for that period without altering the saved defaults

**REQ-010: Language & Position Eligibility Filtering**
The system shall automatically filter sequences based on the user's profile eligibility.

_Acceptance Criteria:_
- Given a user with position range "1 THRU 4", then sequences requiring "POSN 1 THRU 9" are still shown (the user qualifies for positions 1–4 within that range), but sequences requiring a position outside their range are flagged
- Given a user without a Japanese qualification, then sequences with "LANG JP" are either hidden or clearly marked as ineligible
- Given a user with a Spanish qualification, then sequences with "LANG SP" are highlighted as advantageous opportunities

### Bid Optimization

**REQ-011: Generate Optimized Bid**
The system shall generate a strategically rank-ordered bid list that maximizes the likelihood of a desirable awarded schedule given the user's preferences, constraints, and seniority position.

_Acceptance Criteria:_
- Given a bid period with parsed sequences and defined preferences, when the user initiates optimization, then the system produces a complete ranked bid list
- Given the generated bid, then higher-ranked sequences align more closely with the user's weighted preferences
- Given date-conflicting sequences (sequences operating on the same dates), then the optimizer ranks the user's preferred option higher and places alternatives lower as fallbacks, so the airline's seniority-based award system encounters the user's best choice first
- Given sequences with very high OPS counts (meaning many FAs compete for them) and the user's relatively low seniority number, then the optimizer may strategically deprioritize those sequences in favor of less contested alternatives that the user is more likely to actually be awarded
- Given the optimization result, then each sequence's ranking includes a brief rationale explaining why it was placed at that rank (e.g., "high TPAY, preferred layover city, avoids your blocked days")
- Given the optimized bid, then the total number of ranked sequences provides sufficient date coverage across the bid period to minimize the risk of falling to reserve

**REQ-012: Constraint Enforcement**
The system shall enforce scheduling constraints during optimization.

_Acceptance Criteria:_
- Given the user's blocked days off, then no sequence operating on those dates is ranked in a top position unless the user explicitly overrides
- Given the user's position range and language qualifications, then ineligible sequences are excluded from the optimized bid
- Given contractual maximum monthly credit hour limits, then the optimizer flags if a combination of sequences would exceed the limit
- Given minimum rest requirements between sequential pairings, then the optimizer does not recommend back-to-back sequences that violate rest rules

**REQ-013: Manual Bid Adjustment**
The system shall allow users to manually adjust the generated bid list.

_Acceptance Criteria:_
- Given the generated bid list, when the user drags a sequence to a new rank, then the list updates and any conflicts are recalculated
- Given a sequence the user pins to a specific rank, then re-optimization preserves that pin
- Given a sequence the user excludes, then it is removed and re-optimization ignores it
- Given manual adjustments, when the user re-runs optimization, then only unpinned and non-excluded sequences are reordered

### Sequence Comparison

**REQ-014: Side-by-Side Sequence Comparison**
The system shall allow users to compare two or more sequences in a structured side-by-side view.

_Acceptance Criteria:_
- Given two or more selected sequences, when the user chooses "Compare," then the system displays all key attributes in aligned columns: SEQ number, OPS, TPAY, block time, SYNTH, TAFB, number of duty days, number of legs, layover cities and hotels, report/release times, equipment types, language requirements, deadhead legs, and operating dates
- Given the comparison view, then attributes where the sequences differ are visually highlighted
- Given the comparison view, then the user can promote or demote any sequence in the bid list directly from this screen

### Calendar & Schedule Views

**REQ-015: Monthly Calendar View**
The system shall display sequences on an interactive monthly calendar.

_Acceptance Criteria:_
- Given a bid period (e.g., January 1–30), when the user opens the calendar view, then sequences from the current bid list are shown on their operating dates, each spanning from report to release
- Given multi-day sequences, then they span across the correct range of days on the calendar
- Given the calendar, then days off (no sequence operating) are clearly visible
- Given the calendar, when the user taps a sequence, then the full sequence detail view opens
- Given overlapping sequences (date conflicts), then they are visually distinguished with a conflict indicator

**REQ-016: Monthly Summary Dashboard**
The system shall display aggregate statistics for the user's current bid list.

_Acceptance Criteria:_
- Given a finalized or in-progress bid, then the dashboard shows: total estimated TPAY, total block time, total TAFB, total days off, number of sequences, number of legs, number of deadhead legs, number of international vs. domestic sequences, and number of layover cities
- Given any change to the bid list (add, remove, reorder), then the dashboard updates in real time

### Awarded Schedule

**REQ-017: Import Awarded Schedule**
The system shall allow users to import their awarded schedule after the airline publishes results.

_Acceptance Criteria:_
- Given an awarded schedule document, when the user imports it, then awarded sequences are parsed and displayed on the calendar
- Given the import, then awarded sequences match the data format and fields of bid sheet sequences

**REQ-018: Bid vs. Award Analysis**
The system shall compare the submitted bid against the awarded schedule.

_Acceptance Criteria:_
- Given a submitted bid and an awarded schedule, when the user views the analysis, then each awarded sequence is matched to its rank in the original bid
- Given the analysis, then a match rate is displayed (e.g., "4 of your top 10 preferences were awarded")
- Given the analysis, then sequences awarded that were not in the original bid are identified
- Given the analysis, then the system provides insights (e.g., "Sequences with TPAY above X were mostly awarded to more senior FAs")

### Data Management

**REQ-019: Bid History**
The system shall retain a history of all past bid periods.

_Acceptance Criteria:_
- Given a completed bid period, then the system stores the imported bid sheet data, the user's preferences, the final bid list with rankings, and the awarded schedule (if imported)
- Given the history screen, then past bid periods are listed with effective dates and summary statistics
- Given a past bid period, then the user can view all stored data for reference when building future bids

**REQ-020: Export Bid**
The system shall allow users to export their finalized bid for submission.

_Acceptance Criteria:_
- Given a finalized bid list, when the user exports, then a file is generated containing the rank-ordered list of SEQ numbers
- Given the export, then the user can choose the format appropriate for their airline's submission system
- Given the export, then the user is prompted to review and confirm before generating the file

**REQ-021: Bookmark / Favorites**
The system shall allow users to bookmark individual sequences for quick access.

_Acceptance Criteria:_
- Given any sequence in the browser or detail view, when the user bookmarks it, then it appears in a dedicated "Favorites" list
- Given the favorites list, then the user can quickly add all favorites to the bid list or use them as a starting point for optimization

---

## 6. Non-Functional Requirements

**REQ-022: Performance — Parsing**
The system shall parse large bid sheet documents within a reasonable time.

_Acceptance Criteria:_
- Given a bid sheet PDF of up to 500 pages containing up to 1,000 sequences, then parsing completes within 30 seconds
- Given the parsing process, then a progress indicator shows estimated completion

**REQ-023: Performance — Optimization**
The system shall generate an optimized bid within a reasonable time.

_Acceptance Criteria:_
- Given up to 1,000 sequences with the user's full preference set, when the user initiates optimization, then results are returned within 15 seconds
- Given any user interaction (sorting, filtering, navigation), then the interface responds within 1 second

**REQ-024: Usability**
The system shall be usable by flight attendants with no technical background.

_Acceptance Criteria:_
- Given a first-time user, when they complete the onboarding flow, then they can import a bid sheet and generate their first optimized bid without external help
- Given any screen, then all airline-specific terminology (SEQ, TPAY, TAFB, SYNTH, PAX SVC, etc.) is accompanied by tooltips or a glossary link
- Given the optimization results, then the reasoning behind each ranking is explained in plain language

**REQ-025: Data Privacy**
The system shall protect user data and not share personal scheduling information.

_Acceptance Criteria:_
- Given a user's profile, bid data, and preferences, then they are accessible only to that user
- Given any data storage, then personal information is encrypted at rest
- Given the app, then no user data is shared with third parties without explicit consent

**REQ-026: Accessibility**
The system shall be accessible to users with disabilities.

_Acceptance Criteria:_
- Given any screen, then it is fully navigable via keyboard
- Given all visual elements, then they meet WCAG 2.1 AA contrast requirements
- Given all interactive elements, then they have appropriate labels for screen readers
- Given the dense data tables (sequence lists, comparisons), then screen readers can navigate by row and column

**REQ-027: Offline Capability**
The system shall allow core functionality without an active internet connection.

_Acceptance Criteria:_
- Given a previously imported bid sheet, when the user loses connectivity, then they can still browse sequences, adjust preferences, and generate a bid
- Given offline changes, when connectivity is restored, then data syncs without loss

**REQ-028: Multi-Airline Adaptability**
The system shall be adaptable to bid sheet formats from different airlines.

_Acceptance Criteria:_
- Given a user who works for a different carrier, when they configure the app, then they can specify their airline's bid sheet format and scheduling rules
- Given different airline rule sets, then the optimizer enforces the correct constraints for the selected airline
- Given a new airline format, then the parsing engine can be extended without disrupting existing users

---

## 7. CBA-Specific Functional Requirements

The following requirements implement scheduling rules, duty limitations, pay provisions, and bidding constraints defined in the 2024 AA/APFA Collective Bargaining Agreement.

---

**REQ-029: Line of Time Credit Hour Limits (CBA §2.EE, §10)**
The system shall enforce and display credit hour limits when building bids.

_Acceptance Criteria:_
- Given a bid period, then the dashboard displays estimated credit hours for the bid against the Line of Time range (70–90 credit hours standard)
- Given a user who selects High Option, then the line maximum increases to 110 credit hours
- Given a user who selects Low Option, then the line minimum decreases to 40 credit hours
- Given a bid that would result in credit hours outside the applicable range, then the system displays a warning

---

**REQ-030: Domestic Duty Time Limitation Validation (CBA §11.E, §11.F)**
The system shall classify and display domestic duty period legality per the CBA duty time chart.

_Acceptance Criteria:_
- Given a domestic sequence, then each duty period displays its maximum scheduled duty time based on report time (HBT) and number of segments per the Section 11.E chart
- Given a duty period with block time exceeding 8:59, then the system flags it as a long-block duty period and notes the 11-hour minimum home base rest requirement
- Given the duty chart data, then the system can identify sequences near or at duty time limits
- Given actual operations maximum values (13:15, 12:15, or 11:15 based on report time), then these are displayed for reference

---

**REQ-031: International Duty Type Classification (CBA §14.B, §14.D)**
The system shall classify international duty periods by range type and enforce corresponding limits.

_Acceptance Criteria:_
- Given an international duty period, then the system classifies it as Non-Long Range (≤12h block, ≤14h duty), Mid-Range (≤12h block, 14–15h duty), Long Range (12–14:15h block, ≤16h duty), or Extended Long Range (>14:15h block, ≤20h duty)
- Given each classification, then the corresponding maximum scheduled and actual duty times are displayed
- Given IPD duty periods, then the system validates they contain only IPD flying or IPD plus one additional segment (CBA §14.G)
- Given mid-range duty periods, then the system notes the 5% system-wide cap

---

**REQ-032: Rest Requirement Display and Validation (CBA §11.I, §11.J, §14.H, §14.I)**
The system shall display and validate rest requirements for sequences.

_Acceptance Criteria:_
- Given a domestic sequence, then minimum home base rest (11h scheduled, 10h actual ops) is displayed
- Given a domestic layover, then minimum layover rest (10h scheduled, 8h behind-the-door) is validated
- Given an international non-IPD sequence, then minimum home base rest (12h, reducible 2h) is displayed
- Given an IPD sequence, then minimum home base rest (14:30) is displayed
- Given a long-range sequence (>12h block, ≤14:15h), then 36-hour home base rest is noted
- Given an extended long-range sequence (>14:15h block), then 48-hour home base rest is noted (waivable to 24h)
- Given an international IPD layover, then 14-hour minimum rest is validated
- Given back-to-back sequences in the bid, then the system checks that adequate rest exists between them

---

**REQ-033: Minimum Days Off Enforcement (CBA §11.H)**
The system shall track and enforce minimum days off per month.

_Acceptance Criteria:_
- Given a Lineholder, then the dashboard displays a minimum of 11 calendar days off per contractual month
- Given a bid list, then the total days off is calculated and compared against the 11-day minimum
- Given a prorated month (vacation ≥7 days or less than full month available), then the prorated minimum is applied per the CBA chart
- Given a bid that would result in fewer than the minimum days off, then the system displays a warning

---

**REQ-034: Seven-Day Block Hour Limits (CBA §11.B)**
The system shall validate cumulative block hours within rolling 7-day windows.

_Acceptance Criteria:_
- Given a Lineholder, then no 7-consecutive-day window in the bid shall exceed 30 scheduled block hours
- Given a Reserve, then no 7-consecutive-day window shall exceed 35 block hours
- Given a bid that would exceed these limits, then the system flags the conflict
- Given that deadhead time does not count toward 7-day block limits, then deadhead block is excluded from this calculation

---

**REQ-035: Six-Consecutive-Day Limit (CBA §11.C)**
The system shall enforce the requirement for 24 hours off within every 7 consecutive days.

_Acceptance Criteria:_
- Given a bid, then the system validates that no span of more than 6 consecutive duty days occurs without a 24-hour rest period at the FA's crew base
- Given a violation, then the system warns the user and identifies the affected date range

---

**REQ-036: Reserve-Specific Features (CBA §12)**
The system shall support Reserve-specific scheduling concepts.

_Acceptance Criteria:_
- Given a user who identifies as a Reserve, then the system displays Reserve-specific fields: RAP structure, Golden Days, Flex Days
- Given Reserve crew base rest requirements (12 hours), then the system applies the Reserve rest minimum instead of the Lineholder minimum (11 hours)
- Given the Reserve monthly guarantee (75 hours), then the system uses this value for credit projections
- Given the Reserve rotation schedule, then the system displays the user's Reserve/Lineholder rotation status for planning purposes

---

**REQ-037: ODAN Identification and Display (CBA §2.II, §11.L)**
The system shall identify and specially flag ODAN sequences.

_Acceptance Criteria:_
- Given a sequence where all on-duty hours fall between 0100 and 0500 HBT with a single duty period, then the system flags it as an ODAN
- Given an ODAN, then the system displays: max 14h scheduled duty (15h actual), max 2 segments, max 2:30 block per segment, 5h minimum break between segments
- Given an ODAN in the bid list, then it is visually distinguished from standard sequences

---

**REQ-038: Foreign Language Speaker Bidding Rules (CBA §15)**
The system shall enforce language-specific bidding constraints per the CBA.

_Acceptance Criteria:_
- Given a user with a language qualification, then Speaker sequences in that language are highlighted as advantageous
- Given Speaker sequences, then the system displays staffing requirements by aircraft type (1 Speaker for narrowbody, up to 2–3 for widebody per CBA §15.A)
- Given the language cascade for open time (Speaker→Speaker ROTA/ROTD→non-Speaker UBL→non-Speaker ROTA/ROTD), then the system notes Speaker sequences have reduced competition
- Given a user without the required language qualification, then Speaker sequences are marked as ineligible

---

**REQ-039: Purser Qualification Tracking (CBA §14.L)**
The system shall support Purser qualification as a bidding factor.

_Acceptance Criteria:_
- Given the user profile, then Purser qualification status can be recorded (qualified / not qualified)
- Given a Purser-qualified FA, then IPD sequences with Purser positions are highlighted
- Given the 150 paid Purser hours/year minimum, then the system tracks Purser hours toward this threshold if awarded schedule data is available

---

**REQ-040: Compensation Estimation (CBA §3)**
The system shall estimate pay value for sequences based on CBA pay rules.

_Acceptance Criteria:_
- Given the user's years of service, then the system uses the correct hourly rate from the CBA §3.A pay scale
- Given a sequence, then estimated compensation includes: base pay (credit hours × hourly rate), Duty Rig guarantee (1:2), Trip Rig guarantee (1:3.50), and the greater of these values
- Given international sequences, then international premium pay ($3.00/hr NIPD, $3.75/hr IPD) is included in estimates
- Given Speaker sequences, then language premium ($2.00/hr domestic, $5.00–$5.75/hr international) is included
- Given sequences operating on CBA-defined holidays (Thanksgiving week, Christmas week, New Year's), then the 100% holiday premium is noted
- Given position premiums (Lead, Purser, Galley), then these are factored into pay estimates based on position and aircraft type per CBA §3.C

---

**REQ-041: Holiday and Incentive Day Awareness (CBA §3.K)**
The system shall identify sequences that operate on holiday or incentive days.

_Acceptance Criteria:_
- Given the CBA holiday list (Wed before Thanksgiving through Mon after, Dec 24–26, Dec 31, Jan 1), then sequences touching these dates are flagged
- Given a holiday sequence, then the 100% pay premium is noted in the sequence detail and comparison views
- Given incentive days (designated by the Company), then sequences touching those dates are flagged with the 50% or 100% premium notation

---

**REQ-042: Red-Eye Definition per CBA (CBA §11.K)**
The system shall use the CBA-specific red-eye definition.

_Acceptance Criteria:_
- Given the CBA definition, then a duty period is classified as a red-eye if it touches 0100–0101 HBT (not the generic depart-after-21:00 definition)
- Given a red-eye duty period, then the system notes the max 2 scheduled segments and max 1 aircraft connection constraints
- Given a sequence containing a segment touching 0300 HBT, then the system notes the FA will be released for legal rest at termination of that segment

---

**REQ-043: Report and Release Time Accuracy (CBA §11.N, §14.E)**
The system shall display correct report and release times per CBA rules.

_Acceptance Criteria:_
- Given a domestic duty period, then report time is 1 hour prior to departure and release time is 15 minutes after block-in (CBA §11.N)
- Given an IPD duty period, then report time is 1 hour 15 minutes prior and release time is 30 minutes after block-in (CBA §14.E)
- Given an NIPD duty period, then report time is 1 hour and release time is 30 minutes after block-in
- Given mixed duty periods (e.g., domestic originating leg to IPD), then the applicable report time rules are applied correctly

---

**REQ-044: Sequence Construction Rule Awareness (CBA §10.B)**
The system shall validate parsed sequences against CBA construction rules.

_Acceptance Criteria:_
- Given domestic/NIPD sequences, then the system validates max 4 duty periods over 4 calendar days
- Given IPD sequences, then the system allows up to 6 duty periods and 6 calendar days
- Given 4-day domestic/NIPD sequences at a base, then the system notes these are capped at 30% of total sequences
- Given a sequence, then the system validates that the FA will not be required to work a different position number within the sequence (CBA §10.B)

---

**REQ-045: Deadhead Leg Pay and Credit (CBA §16.A)**
The system shall correctly account for deadhead compensation in all calculations.

_Acceptance Criteria:_
- Given a deadhead leg, then full pay and credit is applied based on scheduled block or actual time (whichever greater)
- Given a deadhead leg, then all applicable premiums (international, speaker, holiday) apply
- Given a deadhead leg, then it is excluded from working block time totals but included in pay calculations

---

**REQ-046: Monthly Maximum Credit Hours (CBA §11)**
The system shall enforce monthly maximum credit hour limits.

_Acceptance Criteria:_
- Given the standard line maximum (90 credit hours, or up to 110 with High Option), then the optimizer flags if a combination of sequences would exceed the limit
- Given sequences added via TTS/ETB post-award, then the system tracks cumulative credit toward the monthly maximum
- Given the monthly maximum, then the system displays remaining credit capacity in the dashboard

---

## 8. UX Testing Upgrade Requirements

> The following requirements address critical gaps and usability issues identified during hands-on UX testing by a simulated ORD-based commuter FA (30% seniority, JP-qualified, DCA commuter). Testing was conducted against a parsed January 2026 bid sheet (1,705 sequences). These requirements are prioritized by impact on real-world bidding decisions.

---

### Commute Impact

**REQ-047: Per-Trip Commute Impact Annotations (Critical)**
The system shall analyze each sequence against the user's commute city and display actionable commute warnings.

_Acceptance Criteria:_
- Given a user with `commute_from` set (e.g., DCA), then every sequence in the browser, detail page, calendar, and bid results displays a commute impact indicator: green (easy commute), yellow (tight/early), or red (hotel night needed)
- Given a sequence's first-day report time and the user's commute city, then the system calculates whether a same-day commute is feasible based on typical first-flight arrival times (e.g., DCA→ORD first flight arrives ~08:30 local, so report times before ~09:30 require a hotel night)
- Given a sequence's last-day release time, then the system calculates whether a same-day return commute is feasible (e.g., last ORD→DCA flight departs ~20:00, so release after ~19:00 requires a hotel night)
- Given back-to-back sequences in a bid with less than 18 hours between release and next report, then the system warns "insufficient time to commute home between trips"
- Given the commute analysis, then each sequence detail page shows a commute summary: "First day: commute feasible (report 14:26)" or "First day: hotel night needed (report 05:30, earliest DCA→ORD arrives 08:30)"
- Given the user's profile page, then the `commute_from` field is visible, editable, and clearly labeled

**REQ-048: Commutable Work Block Enforcement**
The system shall use commute data when the "Commutable Work Block" property is enabled.

_Acceptance Criteria:_
- Given the "Commutable Work Block" toggle enabled on a layer, then the optimizer filters to sequences where first-day report and last-day release times are compatible with the user's commute
- Given this property, then the optimizer uses configurable commute windows: earliest feasible report (based on commute city) and latest feasible release
- Given this property in combination with other pairing filters, then commutability acts as an AND filter

---

### Schedule Shape & Days Off

**REQ-049: Days-Off Boundary Enforcement**
The "String of Days Off Starting on Date" and "String of Days Off Ending on Date" properties shall reliably shape the schedule by preventing sequences from being placed in the requested off-period.

_Acceptance Criteria:_
- Given "String of Days Off Starting on Date" set to January 16 on a layer, then no sequence whose operating dates overlap January 16–31 is included in that layer's schedule
- Given "String of Days Off Ending on Date" set to January 15, then no sequence whose operating dates overlap January 1–15 is included in that layer's schedule
- Given both properties combined, then they define a hard exclusion zone where no trips are placed
- Given the calendar view after generation, then the days-off block is visually distinct and contiguous
- Given this property set across all layers (L1-7), then the exclusion applies globally — no layer places trips in the off-period
- Given a conflict between days-off boundaries and minimum credit requirements, then the system warns the user rather than silently overriding the boundary

**REQ-050: Projected Schedule Preview**
The system shall display a "best case" projected schedule showing what the FA's month would look like if top-ranked sequences are awarded.

_Acceptance Criteria:_
- Given a generated bid with ranked sequences across layers, then the system computes and displays a projected schedule for each layer: which specific sequences would form the line, total credit hours, total days off, and the calendar shape
- Given the projected schedule for Layer 1, then the display shows: "5 trips, 82.5 credit hours, 14 days off, days 1-15 working / days 16-30 off" (or equivalent summary)
- Given the projected schedule, then a mini-calendar shows the month with working days filled and off days clear
- Given the projected schedule, then the system highlights whether credit hours fall within the Line of Time range
- Given changes to bid properties or manual adjustments, then the projected schedule updates after re-generation

---

### Sequence Search & Browser

**REQ-051: Sequence Number Direct Search**
The system shall allow users to search for a specific sequence by its SEQ number.

_Acceptance Criteria:_
- Given the sequence browser, then a search box accepts a SEQ number (e.g., "5349") and immediately navigates to or highlights that sequence
- Given a valid SEQ number, then the sequence detail page opens directly
- Given an invalid SEQ number, then the system displays "Sequence not found"
- Given the search box, then it is accessible from the sequence browser, bid builder, and calendar views

**REQ-052: Layer Pairing Browser**
The system shall allow users to browse the specific pairings matched by each layer's filters before generating a bid.

_Acceptance Criteria:_
- Given a layer with configured pairing properties, then a "Browse Pairings" button opens a filtered sequence list showing exactly which sequences match that layer's filters
- Given the layer pairing browser, then it displays the same columns as the main sequence browser (SEQ number, category, TPAY, duty days, layover cities, etc.)
- Given the layer pairing browser, then the user can bookmark, compare, or view detail for any listed sequence
- Given a layer with zero matching pairings, then the browser shows an empty state with suggestions (e.g., "No IPD sequences found — try removing the Pairing Type filter")

---

### Usability & Input Fixes

**REQ-053: Form Input Usability**
All form inputs shall accept direct keyboard entry without requiring workarounds.

_Acceptance Criteria:_
- Given number inputs (credit range min/max, seniority, etc.), then the user can click the field, clear it, and type a new value directly — arrow keys are optional, not required
- Given time inputs (report between, release between), then the user can type times directly (e.g., "10:00") or use a time picker — both methods work
- Given date inputs, then the user can type dates directly or use a date picker
- Given any input field, then tab navigation moves between fields in logical order

**REQ-054: Bulk Layer Assignment**
The system shall provide a shortcut to assign a property to all layers at once.

_Acceptance Criteria:_
- Given a property in the PropertyCatalog, then a "Select All Layers" button or "All" toggle assigns the property to layers 1-7 in one click
- Given a property assigned to all layers, then a "Deselect All" button removes all layer assignments in one click
- Given the layer toggle buttons (1-7), then shift-click or range selection assigns multiple consecutive layers

---

### Pairing Type Classification

**REQ-055: IPD Pairing Type Filter Accuracy**
The system shall correctly classify sequences as IPD so that pairing type filters return expected results.

_Acceptance Criteria:_
- Given sequences categorized as "ORD 777 INTL" or "ORD 787 INTL" with destinations in Europe, Asia, or Deep South America, then they are classified as IPD and match the "Prefer Pairing Type: IPD" filter
- Given the "Prefer Pairing Type: IPD" filter on any layer, then the pairing count is non-zero when IPD sequences exist in the bid sheet
- Given the sequence browser with an IPD filter applied, then the same sequences appear as when filtering by the IPD badge
- Given a mismatch between category classification and pairing type filter, then the system logs a warning for debugging
