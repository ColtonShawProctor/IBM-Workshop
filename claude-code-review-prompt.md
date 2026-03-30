# Claude Code Review Prompt — Phase 15 Plan Audit

## Context

You are reviewing `todo.md` Phase 15 (Tasks 91–105) before implementing anything. This phase adds PBS-style property-based bidding to a flight attendant scheduling app.

**Do NOT implement any code. Your job is to review, identify gaps, and propose corrections to the plan.**

## What this app does

This is a personal planning tool for American Airlines flight attendants. It sits between the airline's published bid sheet PDF and the airline's PBS (Preferential Bidding System) portal at fapbs.aa.com. The app does NOT interact with the airline directly. Its job:

1. **Parse** — User uploads a bid sheet PDF → backend parses it into sequences (pairings) with full flight data (legs, duty periods, layovers, times, equipment, etc.)
2. **Configure** — User sets bid properties matching the real PBS interface: 63 properties across 4 categories (Days Off, Line, Pairing, Reserve), each assigned to layers 1-7
3. **Optimize** — Backend filters sequences per layer using property AND/OR logic, scores them, and builds 7 valid non-conflicting schedule layers
4. **Export** — User gets a ranked 7-layer bid they copy into the real PBS portal

## Files to read

Read these files to understand the current codebase and the proposed plan:

1. `todo.md` — Full task list. Phases 1-14 are existing work. **Focus on Phase 15 (Tasks 91-105).**
2. `pbs-system-reference.md` — Complete documentation of the live AA PBS system (63 properties, 7 layers, AND/OR logic, equipment codes, pairing types, strategic notes). This is the source of truth for what we're modeling.
3. `design.md` — Technical architecture of the app
4. `requirements.md` — Original requirements
5. `backend/app/models/schemas.py` — Current Pydantic models (FilterSet, Sequence, Bid, BidEntry, etc.)
6. `backend/app/services/optimizer.py` — Current optimizer (9-layer, preference-based scoring)
7. `backend/app/routes/bids.py` — Current bid API routes
8. `frontend/src/types/api.ts` — Current TypeScript interfaces
9. `frontend/src/lib/api.ts` — Current API client functions
10. `frontend/src/pages/BidPeriodDetailPage.tsx` — Current bid period detail page (3-step workflow with flat preferences)
11. `frontend/src/pages/SequenceBrowserPage.tsx` — Current sequence browser with FilterSet-based filtering
12. `frontend/src/pages/BidsPage.tsx` — Current advanced bid editor

## What to review

### 1. Backend task completeness
- Do Tasks 91-98 fully cover the backend changes needed?
- Is the property data model (Task 92) complete? Does it handle all 63 property value types from pbs-system-reference.md?
- Is the filter logic (Task 95) covering enough property matchers? Are any critical ones missing?
- Does the optimizer update (Task 98) properly handle the transition from 9 layers to 7 while keeping backward compat?
- Are there missing backend tasks? (e.g., property persistence endpoints, standing bid support, property CRUD routes)

### 2. Frontend task completeness
- Do Tasks 99-103 cover all the UI components needed?
- Does the BidPeriodDetailPage rewrite (Task 103) fully replace the current flat-preference workflow?
- Is there a gap between the current SequenceBrowserPage (FilterSet-based) and the new property system? Should the sequence browser also understand PBS properties, or do they stay separate?
- Are there missing frontend tasks? (e.g., updating the existing BidsPage, updating the onboarding flow to ask about base/fleet/position, standing bid UI)

### 3. Data flow alignment
- Does the frontend property state flow cleanly to the backend optimize endpoint?
- How are properties persisted? Task 94 adds API functions for property CRUD, but there are no backend route tasks for those endpoints. Is that a gap?
- The current BidEntry has a `layer` field (1-9). After Phase 15, this becomes 1-7. Are all consumers of this field updated?

### 4. Migration / backward compatibility
- What happens to existing bids that have 9 layers?
- What happens to the existing Preferences/PreferenceWeights system? Is it deprecated or do both coexist?
- Does the existing test suite (255 backend tests) need updates for the 9→7 layer change?

### 5. Missing pieces
- The real PBS system has "standing bids" (persistent templates across months). Is that in scope?
- The real PBS has pairing search (by ID). Is that covered?
- The LayerSummaryPanel shows pairing counts, but the backend compute_layer_summaries (Task 96) needs access to the actual sequence data to filter. How does this work in practice — does the frontend call the backend for layer counts, or compute locally?
- Is there a task for updating the export format (TXT/CSV) to work with the new 7-layer structure? (Task 104 exists but verify it's sufficient)

## Output format

Produce a revised/annotated version of Phase 15 that:

1. **Lists any gaps** you found (missing tasks, incomplete coverage, data flow issues)
2. **Proposes specific new tasks** or modifications to existing tasks to fill those gaps
3. **Confirms or corrects** the task ordering (dependencies must be respected)
4. **Flags any risks** (breaking changes, test regressions, backward compat issues)
5. **Validates the frontend-backend contract** — for every backend endpoint change, verify there's a corresponding frontend update, and vice versa

Write the output as proposed changes to `todo.md` Phase 15, following the exact same task format (task number, description, files, test, verify). Do NOT implement any code.
