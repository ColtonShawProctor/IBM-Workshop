# Research Prompt: Best Practices for PBS Layer Construction & Bid Optimization

You are a **systems researcher** investigating how airline Preferential Bidding Systems (PBS) build optimal monthly schedules for flight attendants. Your goal is to identify the best algorithms, scoring models, and constraint-satisfaction patterns used in production PBS systems — then produce actionable recommendations for improving our implementation.

---

## Context: What We're Building

We have a bid optimization tool for American Airlines flight attendants (FAs) using the PBS system at `fapbs.aa.com`. An FA's monthly bid consists of **7 priority layers**, where:

- **Layer 1 (Dream Pick)**: Most restrictive preferences — the ideal schedule
- **Layers 2-5**: Progressively relaxed constraints
- **Layer 7 (Safety Net)**: Broadest possible preferences to avoid company-assigned leftovers

Each layer must produce a **complete, valid monthly schedule** — a set of non-conflicting flight sequences (pairings) that:
- Has no overlapping duty dates
- Respects FAA 10-hour minimum rest between consecutive sequences
- Stays within the Line of Time credit range (typically 70-90 hours/month)
- Guarantees minimum 11 days off per CBA
- Can only use one operating date instance per multi-OPS sequence

### How It Currently Works

1. **Filter**: Each layer has PBS properties (e.g., "prefer IPD pairings," "3-day trips only," "report after 10:00"). Sequences not matching the layer's AND/OR property filters are removed.

2. **Score**: Remaining sequences are scored 0.0-1.0 based on:
   - Pairing property match: binary 1.0 (match) or 0.0 (no match)
   - `maximize_credit`: TPAY normalized to a range
   - Quality tiebreaker: credit-per-duty-day when no explicit credit property is set
   - Attainability multiplier: based on seniority, ops count, language qualification

3. **Build**: A greedy algorithm selects the highest-effective-score sequence, adds it to the schedule if it doesn't conflict, then moves to the next. Sequences used in prior layers get a 0.6x score penalty to encourage variety.

4. **Repeat**: For all 7 layers.

### The Problem

The layers work, but the schedules don't always feel like what a real FA would want. Specific concerns:

- **Greedy selection is score-blind to schedule shape**: The algorithm picks the highest-scoring sequences one at a time, but doesn't consider how they fit together as a monthly schedule. You might get a scattered schedule with work days spread across the month instead of a clean "2 weeks on, 2 weeks off" pattern.

- **No consideration of trip quality beyond TPAY**: Two 3-day trips with the same TPAY score identically, even if one has an NRT layover with 24 hours off and the other has a CLT connection with 8 hours. Real FAs care deeply about layover quality, duty-day intensity, and trip "feel."

- **Credit-per-duty-day is a weak proxy**: We use credit/duty-day as a tiebreaker, but it doesn't capture what FAs actually optimize for — "best schedule shape with maximum pay and minimum wear."

- **No backtracking**: The greedy algorithm never reconsiders choices. If picking sequence A blocks a much better combination of B+C, it doesn't know.

- **Layer variety is only from reuse penalty**: When properties span all 7 layers (common with templates), the only thing making layers different is the 0.6x penalty on already-used sequences. This sometimes produces layers that are minor shuffles of each other rather than genuinely different strategies.

---

## What to Research

### 1. How Do Production PBS Systems Build Schedules?

Research how real PBS systems work at major airlines:
- **SITA PBS** (used by many carriers)
- **Navblue (Airbus) N-PBS** (used by Delta, others)
- **FLICA** (United's system)
- **AA's PBS** at fapbs.aa.com

Specific questions:
- How do they handle the layer/round structure? Is it truly greedy, or do they use constraint programming, ILP, or heuristic search?
- How do they handle "schedule shape" — do they explicitly optimize for contiguous blocks of work/off days?
- How do they score sequences within a layer? Binary match vs. gradient scoring?
- How do they ensure layers offer genuinely different schedules, not just reshuffled versions?
- What role does the "award simulation" play — do they simulate the seniority-based award process?

### 2. Schedule Shape Optimization

This is the biggest gap in our system. Research:
- **Block scheduling algorithms**: How to prefer contiguous work blocks (e.g., work days 1-14, off days 15-31) over scattered trips
- **Gap minimization**: Algorithms that minimize isolated off-days between trips
- **Work-block size constraints**: How to enforce "3-5 day work blocks separated by 3+ day breaks"
- **Commuter-aware scheduling**: For FAs who commute (live in a different city), the schedule needs commute-friendly gaps — not just any 2 days off, but 2+ days that allow flying home and back
- Is there a well-known optimization formulation for "maximize contiguous off-day blocks"?

### 3. Multi-Objective Scoring

Our scoring is too simple. Research better models:
- **What do FAs actually optimize for?** Talk to PBS forums, union guidance, bid strategy guides. What are the real priority stacks?
- **Layover quality scoring**: Is there a standard way to value layover cities? (NRT >> CLT). Rest time at layover? Hotel quality?
- **Fatigue modeling**: Do any systems use fatigue risk management (FRMS) scores to penalize back-to-back red-eyes or short-rest patterns?
- **Duty intensity**: Legs-per-duty, ground time, sit time — how do these factor into "trip quality"?
- **Composite scoring models**: How to combine TPAY, schedule shape, trip quality, and commutability into one effective score without one dimension dominating?
- **Pareto-optimal scheduling**: Should we present multiple Pareto-optimal schedules (max credit vs. max days off vs. best layovers) rather than one ranked list?

### 4. Algorithms Beyond Greedy

Research better algorithms for building valid schedules:
- **Constraint programming (CP)**: Can we model the schedule as a CP problem? (tools: OR-Tools, MiniZinc)
- **Integer Linear Programming (ILP)**: Formulate as 0-1 knapsack with conflict constraints
- **Beam search**: Keep top-K partial schedules instead of committing to one greedily
- **Simulated annealing / genetic algorithms**: For exploring the schedule space
- **Column generation**: Used in airline crew scheduling — applicable here?
- What's the right tradeoff between solution quality and speed? (We need to generate 7 layers in <10 seconds for UX)

### 5. Layer Differentiation Strategies

How to make each layer genuinely different:
- **Diverse portfolio approach**: Each layer should represent a different "strategy" — not just the same strategy with worse sequences
- **What-if analysis**: "Layer 2 = what if I couldn't get my dream NRT trip? Here's the best alternative."
- **Complementary schedules**: Layer 1 front-loads work; Layer 2 back-loads it; Layer 3 splits evenly
- **Seniority-aware layering**: Layer 1 assumes you get everything; Layer 4 assumes 60th percentile outcomes; Layer 7 assumes worst case
- Do any PBS systems use fundamentally different optimization strategies per layer rather than just loosening filters?

### 6. Real FA Bidding Strategy Patterns

Research what experienced FAs actually do when bidding:
- What are the common bid strategies? ("commuter block," "international chase," "credit maximizer," "weekend warrior")
- How do senior vs. junior FAs bid differently?
- What does "a good schedule" actually mean to an FA? (Not just hours — quality of life)
- Are there published PBS bidding guides or union resources that describe optimal patterns?
- What are common mistakes FAs make in PBS bids?

---

## Output Format

Structure your findings as:

### Part 1: Industry Analysis
How production PBS systems work, with specific details on SITA, Navblue, and AA's system.

### Part 2: Algorithm Recommendations
Ranked list of algorithmic improvements, each with:
- **What**: The technique
- **Why**: What quality problem it solves
- **How**: Implementation sketch (pseudocode or formulation)
- **Complexity**: Runtime/memory implications
- **Priority**: High/Medium/Low based on impact vs. effort

### Part 3: Scoring Model Redesign
A proposed multi-factor scoring model that captures what FAs actually care about. Include specific formulas, weights, and normalization approaches.

### Part 4: Schedule Shape Optimization
Specific algorithms for ensuring good schedule shape — contiguous work blocks, commuter-friendly gaps, balanced credit distribution.

### Part 5: Layer Strategy
How to make each of the 7 layers represent a genuinely different and useful schedule option.

### Part 6: Quick Wins
Things we can implement in <1 day that would meaningfully improve layer quality.

---

## Constraints

- The system runs on a Python FastAPI backend. Performance matters — generation should complete in <10 seconds for a pool of ~1,700 sequences across 7 layers.
- We have full sequence data: duty periods, legs, times, equipment, layover cities, credit, TAFB, operating dates.
- The user has already configured properties (filters) via the PBS property catalog — the optimizer should respect those as hard constraints.
- The output format is fixed: 7 layers, each containing a ranked list of non-conflicting sequences with scores and rationale.
- We cannot change how AA's actual PBS system works — we're building a bid *preparation* tool that helps FAs construct optimal bids to submit to the real system.

Focus on **practical, implementable improvements** — not theoretical ideals. What would make an FA look at the generated layers and say "Yes, I would actually fly this schedule"?
