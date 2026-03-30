# Claude Desktop Browser Exploration Prompt

Copy and paste the prompt below into Claude Desktop with the browser extension enabled.

---

You are helping me build a flight attendant bid optimization app for American Airlines. I need you to explore the AA PBS (Preferential Bidding System) bidding interface to discover and document every filter, option, preference, and configuration that a flight attendant can set when creating a bid package.

**Your task:**

1. Navigate to the American Airlines flight attendant crew portal / PBS bidding system. The URL is typically accessed via:
   - jetnet.aa.com (AA's internal employee portal)
   - The PBS vendor site (likely Navtech/Navblue or similar PBS provider used by AA)
   - If direct access is unavailable, search for "American Airlines PBS bidding system", "AA APFA PBS tutorial", "AA flight attendant PBS bid guide", or "American Airlines preferential bidding system walkthrough" to find screenshots, training materials, union guides, or video walkthroughs that show the actual interface

2. For each screen/page in the bidding flow, document:
   - **Screen name / step in the workflow**
   - **Every filter or option available** (dropdowns, checkboxes, sliders, text inputs, toggles)
   - **The possible values** for each filter (e.g., equipment types: 777, 787, 737, etc.)
   - **Whether the filter is per-layer or global** (applies to one bid group vs. the entire bid)
   - **How filters interact** (AND vs OR logic, mutual exclusivity)

3. Specifically look for and document:

   **Bid Structure:**
   - How many bid groups / layers can a user create? (I believe up to 9+)
   - What is the hierarchy — do layers have priority order?
   - Can each layer have independent filter criteria?
   - Is there a "prefer" vs "avoid" vs "require" distinction for filters?
   - Are there "award preferences" like High Time, Low Time, Days Off, etc.?

   **Sequence/Trip Filters:**
   - Equipment type (777, 787, 738, 321, etc.)
   - Route type (Domestic, International, IPD, NIPD)
   - Specific destinations / layover cities
   - Number of duty days (turns, 2-day, 3-day, 4-day)
   - TPAY / credit hour ranges
   - TAFB ranges
   - Block time ranges
   - Number of legs per duty day
   - Deadhead inclusion/exclusion
   - Red-eye inclusion/exclusion
   - Report time windows (earliest/latest)
   - Release time windows (earliest/latest)
   - Language qualification requirements
   - Position requirements
   - Specific sequence numbers (SEQ)
   - Operating date ranges or specific dates
   - Category (e.g., "777 INTL", "787 INTL", "NBI INTL", "NBD DOM")

   **Schedule Preferences:**
   - Days off preferences (specific dates, weekends, clusters)
   - High Option / Low Option / Standard line selection
   - Credit hour target (min/max)
   - Trip clustering preferences
   - Commuter-friendly options
   - Avoid specific dates
   - Prefer/avoid specific equipment
   - Prefer/avoid specific bases or stations

   **PBS-Specific Bid Options:**
   - "Award me anything" fallback option
   - Reserve willingness
   - Carry-over / change-over preferences
   - Mutual trading preferences
   - Golden Days / Flex Days (for Reserves)
   - Any "If not awarded X, then prefer Y" conditional logic

4. Also document:
   - The **order/sequence of screens** in the bid submission workflow
   - Any **validation rules** shown in the UI (warnings, errors)
   - Any **bid summary or preview** functionality
   - How the final bid is **submitted** (format, confirmation)
   - Any **bid templates or presets** functionality
   - How **bid groups/layers interact** with each other during PBS processing

5. If you cannot access the actual system, look for:
   - APFA (Association of Professional Flight Attendants) training materials on PBS
   - YouTube tutorials showing AA PBS bidding
   - Union newsletters or guides explaining bid group strategy
   - Screenshots from crew forums (flightattendantcrew.com, airlinepilotforums.com crew sections, etc.)
   - The Navtech/Navblue PBS user guide for AA

**Output Format:**

Create a structured document with:
1. A flowchart of the bidding workflow (screen by screen)
2. A complete filter catalog organized by category, with:
   - Filter name
   - Type (dropdown, checkbox, range, text, etc.)
   - Possible values
   - Scope (per-layer vs global)
   - Required vs optional
   - Default value (if visible)
3. A description of how bid groups/layers work and interact
4. Any strategic notes about how experienced FAs use these filters
5. Screenshots or descriptions of each key screen

This information will be used to redesign our app's frontend to match the real PBS workflow, with customizable filter selection per bid layer (1-9).
