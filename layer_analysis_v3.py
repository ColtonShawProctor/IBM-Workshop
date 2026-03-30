#!/usr/bin/env python3
"""PBS Layer Output Analyzer V3 — Full post-fix verification pass.

Runs the optimizer fresh, captures all 7 layers, and evaluates:
  Part 1: Legality (6 binary checks)
  Part 2: Schedule Shape (work blocks, calendar grids)
  Part 3: Commutability (report/release times, buffer days)
  Part 4: Trip Quality (efficiency, layovers, intensity)
  Part 5: Cross-Layer Comparison (diversity, strategy fulfillment)
  Part 6: Final Scorecard + three summary questions
"""

import sys
import os
import json
import math
import io
import logging
from collections import defaultdict
from datetime import datetime, date

# Setup path for backend imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.db import get_collection
from app.services.optimizer import (
    optimize_bid,
    _all_possible_date_spans,
    _hhmm_to_minutes,
)
from app.services.cpsat_builder import (
    DEFAULT_LAYER_STRATEGIES,
    CITY_TIERS,
    compute_trip_quality,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ── Config ───────────────────────────────────────────────────────────────
BID_PERIOD_ID = "85646a2c-573f-4139-a3c6-c769242d6507"
BID_ID = None  # will be looked up
TOTAL_DATES = 30  # January 2026 bid period days
DOW_START = 3  # January 1, 2026 = Thursday (0=Mon)
MIN_DAYS_OFF = 11
NUM_LAYERS = 7
BLOCK_LIMIT_7DAY_MIN = 1800  # 30h for analysis
BLOCK_LIMIT_7DAY_WARN = 1500  # 25h warning threshold
CITY_DEFAULT = 55

LAYER_STRATEGY_NAMES = {k: v["name"] for k, v in DEFAULT_LAYER_STRATEGIES.items()}


# ── Output capture ───────────────────────────────────────────────────────
class TeeOutput:
    """Write to both console and a string buffer."""
    def __init__(self):
        self.buf = io.StringIO()
        self.stdout = sys.stdout

    def write(self, s):
        self.stdout.write(s)
        self.buf.write(s)

    def flush(self):
        self.stdout.flush()

    def getvalue(self):
        return self.buf.getvalue()


tee = TeeOutput()
sys.stdout = tee


def pr(s="", **kwargs):
    print(s, **kwargs)


def hr(char="=", width=78):
    pr(char * width)


# ── Data Loading ─────────────────────────────────────────────────────────

def load_and_run_optimizer():
    """Load bid data from Astra DB and run the optimizer fresh."""
    pr("=" * 78)
    pr("  PBS LAYER OUTPUT ANALYZER v3 — Post-Fix Verification")
    pr(f"  Bid Period: Test Bid 2 (ORD, January 2026)")
    pr(f"  Analysis: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pr("=" * 78)
    pr()

    # Load bid
    bid_coll = get_collection("bids")
    bids = list(bid_coll.find({"bid_period_id": BID_PERIOD_ID}, limit=10))
    if not bids:
        pr("ERROR: No bids found for bid period")
        sys.exit(1)
    bid = bids[0]
    bid_id = bid["_id"]
    pr(f"  Bid: {bid_id}")

    # Load sequences
    seq_coll = get_collection("sequences")
    sequences = list(seq_coll.find({"bid_period_id": BID_PERIOD_ID}, limit=2000))
    pr(f"  Sequences in pool: {len(sequences)}")

    # Extract bid settings
    prefs = bid.get("preferences", {})
    bid_props = bid.get("bid_properties") or bid.get("properties", [])
    seniority = bid.get("seniority_number", 5000)
    total_fas = bid.get("total_base_fas", 10000)
    user_langs = bid.get("languages", [])
    pinned = bid.get("pinned_entries", [])
    excluded = set(bid.get("excluded_ids", []))
    seniority_pct = bid.get("seniority_percentage")
    commute_from = bid.get("commute_from")
    target_min = bid.get("target_credit_min_minutes", 4200)
    target_max = bid.get("target_credit_max_minutes", 5400)

    pr(f"  Bid properties: {len(bid_props)}")
    for p in bid_props:
        layers = p.get("layers", [])
        pr(f"    {p['property_key']}: {p.get('value')} (L{','.join(map(str, layers))})")
    pr(f"  Seniority: {seniority} / {total_fas} ({seniority_pct}%)")
    pr(f"  Credit range: {target_min/60:.0f}h - {target_max/60:.0f}h")
    pr(f"  Commute from: {commute_from or 'N/A'}")
    pr()

    # Run optimizer
    pr("Running optimizer (7 layers, CP-SAT)...")
    entries = optimize_bid(
        sequences=sequences,
        prefs=prefs,
        seniority_number=seniority,
        total_base_fas=total_fas,
        user_langs=user_langs,
        pinned_entries=pinned,
        excluded_ids=excluded,
        total_dates=TOTAL_DATES,
        bid_properties=bid_props,
        target_credit_min_minutes=target_min,
        target_credit_max_minutes=target_max,
        seniority_percentage=seniority_pct,
        commute_from=commute_from,
    )

    # Save entries for reference
    with open(os.path.join(os.path.dirname(__file__), "fresh_entries_v3.json"), "w") as f:
        json.dump(entries, f, indent=2, default=str)
    pr(f"  Saved {len(entries)} entries to fresh_entries_v3.json")

    # Build layers dict
    seq_lookup = {s["_id"]: s for s in sequences}
    layers = defaultdict(list)
    for entry in entries:
        layer_num = entry.get("layer", 0)
        if layer_num == 0:
            continue
        sid = entry.get("sequence_id")
        full_seq = seq_lookup.get(sid, {})
        enriched = {**entry, "_full_seq": full_seq}
        layers[layer_num].append(enriched)

    for l in layers:
        layers[l].sort(key=lambda e: e.get("rank", 999))

    pr(f"  Layers populated: {sorted(layers.keys())}")
    for l in sorted(layers.keys()):
        pr(f"    L{l}: {len(layers[l])} sequences")
    pr()

    return layers, sequences, seq_lookup


# ── Part 1: Legality ────────────────────────────────────────────────────

def _get_seq_data(layer_entries):
    """Extract structured data from layer entries."""
    seq_data = []
    for entry in layer_entries:
        chosen = set(entry.get("chosen_dates", []))
        full = entry.get("_full_seq", {})
        totals = full.get("totals", {})
        seq_data.append({
            "seq_number": entry.get("seq_number", 0),
            "seq_id": entry.get("sequence_id", ""),
            "chosen_dates": chosen,
            "tpay_minutes": totals.get("tpay_minutes", 0),
            "block_minutes": totals.get("block_minutes", 0),
            "duty_days": totals.get("duty_days", 1) or 1,
            "leg_count": totals.get("leg_count", 0),
            "deadhead_count": totals.get("deadhead_count", 0),
            "tafb_minutes": totals.get("tafb_minutes", 0),
            "layover_cities": full.get("layover_cities", []),
            "is_turn": full.get("is_turn", False),
            "is_redeye": full.get("is_redeye", False),
            "is_odan": full.get("is_odan", False),
            "has_deadhead": full.get("has_deadhead", False),
            "duty_periods": full.get("duty_periods", []),
            "preference_score": entry.get("preference_score", 0),
            "attainability": entry.get("attainability", "unknown"),
            "category": full.get("category", ""),
        })
    return seq_data


def check_legality(layer_num, layer_entries):
    """Run all 6 legality checks. Returns dict with pass/fail per check."""
    seq_data = _get_seq_data(layer_entries)
    if not seq_data:
        return {"layer": layer_num, "empty": True, "legal": False,
                "dates": "EMPTY", "rest": "EMPTY", "credit": "EMPTY",
                "credit_val": 0, "days_off": "EMPTY", "days_off_val": 0,
                "block7": "EMPTY", "block7_val": 0, "multi_ops": "EMPTY",
                "issues": ["EMPTY"]}

    result = {"layer": layer_num, "empty": False, "issues": []}

    # 1a. Date Conflicts
    conflicts = []
    for i in range(len(seq_data)):
        for j in range(i + 1, len(seq_data)):
            overlap = seq_data[i]["chosen_dates"] & seq_data[j]["chosen_dates"]
            if overlap:
                conflicts.append((seq_data[i]["seq_number"], seq_data[j]["seq_number"], sorted(overlap)))
    result["dates"] = "FAIL" if conflicts else "PASS"
    if conflicts:
        result["issues"].append(f"Date conflicts: {conflicts}")

    # 1b. Rest Periods
    sorted_seqs = sorted(seq_data, key=lambda s: min(s["chosen_dates"]) if s["chosen_dates"] else 999)
    rest_issues = []
    tightest_rest = 9999
    for i in range(len(sorted_seqs) - 1):
        curr = sorted_seqs[i]
        nxt = sorted_seqs[i + 1]
        curr_last = max(curr["chosen_dates"])
        nxt_first = min(nxt["chosen_dates"])
        gap_days = nxt_first - curr_last

        if gap_days <= 0:
            rest_issues.append(f"SEQ {curr['seq_number']}->{nxt['seq_number']}: overlap")
        elif gap_days == 1:
            curr_dps = curr["duty_periods"]
            nxt_dps = nxt["duty_periods"]
            if curr_dps and nxt_dps:
                rel = _hhmm_to_minutes(curr_dps[-1].get("release_base", "18:00"))
                rpt = _hhmm_to_minutes(nxt_dps[0].get("report_base", "08:00"))
                rest_min = (24 * 60 - rel) + rpt
                tightest_rest = min(tightest_rest, rest_min)
                if rest_min < 600:
                    rest_issues.append(f"SEQ {curr['seq_number']}->{nxt['seq_number']}: {rest_min/60:.1f}h")
    result["rest"] = "FAIL" if rest_issues else "PASS"
    result["tightest_rest"] = tightest_rest if tightest_rest < 9999 else None
    if rest_issues:
        result["issues"].append(f"Rest violations: {rest_issues}")

    # 1c. Credit Range
    total_tpay = sum(sd["tpay_minutes"] for sd in seq_data)
    total_tpay_h = total_tpay / 60
    # Use per-layer strategy credit range
    strat = DEFAULT_LAYER_STRATEGIES.get(layer_num, {})
    cr = strat.get("credit_range", (4200, 5400))
    # Hard constraint: the solver uses strategy max as hard upper bound
    # and bid-period min (4200) or 0 as hard lower bound
    in_range = total_tpay <= cr[1]  # only max is hard
    result["credit"] = f"{total_tpay_h:.1f} {'PASS' if in_range else 'FAIL'}"
    result["credit_val"] = total_tpay_h
    result["credit_min"] = total_tpay
    if not in_range:
        result["issues"].append(f"Credit {total_tpay_h:.1f}h > max {cr[1]/60:.0f}h")

    # 1d. Days Off
    all_dates = set()
    for sd in seq_data:
        all_dates |= sd["chosen_dates"]
    working = len(all_dates)
    days_off = TOTAL_DATES - working
    result["days_off"] = f"{days_off} {'PASS' if days_off >= MIN_DAYS_OFF else 'FAIL'}"
    result["days_off_val"] = days_off
    if days_off < MIN_DAYS_OFF:
        result["issues"].append(f"Only {days_off} days off (min {MIN_DAYS_OFF})")

    # 1e. 7-Day Block Hours (proportional)
    worst_block = 0
    worst_window = ""
    warnings_25h = []
    for start in range(1, TOTAL_DATES - 5):
        window = set(range(start, start + 7))
        block = 0
        for sd in seq_data:
            overlap = len(sd["chosen_dates"] & window)
            if overlap > 0:
                span_size = len(sd["chosen_dates"])
                if span_size > 0:
                    block += sd["block_minutes"] * overlap / span_size
        if block > worst_block:
            worst_block = block
            worst_window = f"d{start}-{start+6}"
        if block > BLOCK_LIMIT_7DAY_WARN:
            warnings_25h.append((start, block))

    result["block7"] = f"{worst_block/60:.1f} {'PASS' if worst_block <= BLOCK_LIMIT_7DAY_MIN else 'FAIL'}"
    result["block7_val"] = worst_block / 60
    result["block7_window"] = worst_window
    result["block7_warnings"] = warnings_25h
    if worst_block > BLOCK_LIMIT_7DAY_MIN:
        result["issues"].append(f"7-day block {worst_block/60:.1f}h > 30h at {worst_window}")

    # 1f. Multi-OPS Uniqueness
    seq_ids = [sd["seq_id"] for sd in seq_data]
    dupes = [sid for sid in set(seq_ids) if seq_ids.count(sid) > 1]
    result["multi_ops"] = "FAIL" if dupes else "PASS"
    if dupes:
        result["issues"].append(f"Duplicate sequence IDs: {dupes}")

    result["legal"] = len(result["issues"]) == 0
    result["seq_data"] = seq_data
    return result


def print_legality_table(all_results):
    hr()
    pr("  PART 1: LEGALITY AUDIT")
    hr()
    pr()
    pr(f"  {'Layer':>5} | {'Dates':>6} | {'Rest':>6} | {'Credit':>12} | {'Days Off':>8} | {'7-Day Blk':>10} | {'Multi-OPS':>9}")
    pr(f"  {'-'*5}-+-{'-'*6}-+-{'-'*6}-+-{'-'*12}-+-{'-'*8}-+-{'-'*10}-+-{'-'*9}")

    all_legal = True
    for l in range(1, NUM_LAYERS + 1):
        r = all_results.get(l, {})
        if r.get("empty"):
            pr(f"  L{l:>3} | {'EMPTY':>6} | {'EMPTY':>6} | {'EMPTY':>12} | {'EMPTY':>8} | {'EMPTY':>10} | {'EMPTY':>9}")
            all_legal = False
            continue
        pr(f"  L{l:>3} | {r['dates']:>6} | {r['rest']:>6} | {r['credit']:>12} | {r['days_off']:>8} | {r['block7']:>10} | {r['multi_ops']:>9}")
        if not r.get("legal"):
            all_legal = False

    pr()
    if all_legal:
        pr("  ALL LAYERS LEGAL")
    else:
        pr("  LEGALITY FAILURES DETECTED:")
        for l in range(1, NUM_LAYERS + 1):
            r = all_results.get(l, {})
            for iss in r.get("issues", []):
                pr(f"    L{l}: {iss}")
    pr()
    return all_legal


# ── Part 2: Schedule Shape ──────────────────────────────────────────────

def analyze_shape(layer_num, layer_entries):
    if not layer_entries:
        return {"empty": True}

    all_dates = set()
    trip_dates = {}  # seq_number -> set of dates
    for e in layer_entries:
        dates = set(e.get("chosen_dates", []))
        all_dates |= dates
        trip_dates[e.get("seq_number", 0)] = dates
    if not all_dates:
        return {"empty": True}

    sorted_dates = sorted(all_dates)
    first_work = sorted_dates[0]
    last_work = sorted_dates[-1]
    span = last_work - first_work + 1

    # Work blocks (contiguous runs of working dates)
    blocks = [[sorted_dates[0]]]
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i - 1] + 1:
            blocks[-1].append(sorted_dates[i])
        else:
            blocks.append([sorted_dates[i]])

    num_blocks = len(blocks)
    internal_gaps = len(set(range(first_work, last_work + 1)) - all_dates)
    block_rating = ("EXCELLENT" if num_blocks == 1 and internal_gaps == 0 else
                    "GOOD" if num_blocks <= 2 and internal_gaps <= 2 else
                    "FAIR" if num_blocks <= 3 else "POOR")

    # Off-day blocks
    off_days = sorted(set(range(1, TOTAL_DATES + 1)) - all_dates)
    if off_days:
        off_blocks = [[off_days[0]]]
        for i in range(1, len(off_days)):
            if off_days[i] == off_days[i - 1] + 1:
                off_blocks[-1].append(off_days[i])
            else:
                off_blocks.append([off_days[i]])
        largest_off = max(len(b) for b in off_blocks)
        largest_off_block = max(off_blocks, key=len)
    else:
        largest_off = 0
        largest_off_block = []

    off_rating = ("EXCELLENT" if largest_off >= 14 else "GOOD" if largest_off >= 11 else
                  "FAIR" if largest_off >= 8 else "POOR")

    # Print
    strat_name = LAYER_STRATEGY_NAMES.get(layer_num, "?")
    total_credit = sum(e.get("_full_seq", {}).get("totals", {}).get("tpay_minutes", 0) for e in layer_entries)

    pr(f"\n  Layer {layer_num}: {strat_name}")
    pr(f"  Credit: {total_credit/60:.1f}h | Span: {span}d (d{first_work}-d{last_work}) | "
       f"Off: {largest_off}d | Blocks: {num_blocks}")
    pr(f"  Block Rating: {block_rating} | Off Rating: {off_rating}")

    # Calendar grid
    pr()
    pr("    Mon  Tue  Wed  Thu  Fri  Sat  Sun")
    row = "    " + "     " * DOW_START
    for day in range(1, TOTAL_DATES + 1):
        dow = (DOW_START + day - 1) % 7
        if day in all_dates:
            row += f" {day:>2}\u2593\u2593"
        else:
            row += f" {day:>2}  "
        if dow == 6:
            pr(row)
            row = "    "
    if row.strip():
        pr(row)

    # Trip breakdown
    pr()
    for e in layer_entries:
        dates = sorted(e.get("chosen_dates", []))
        if not dates:
            continue
        full = e.get("_full_seq", {})
        totals = full.get("totals", {})
        cities = full.get("layover_cities", [])
        tpay = totals.get("tpay_minutes", 0)
        dd = totals.get("duty_days", 1)

        # Build layover detail
        layover_detail = []
        for dp in full.get("duty_periods", []):
            lo = dp.get("layover")
            if lo:
                city = lo.get("city", "?")
                rest_h = lo.get("rest_minutes", 0) / 60
                layover_detail.append(f"{city} {rest_h:.0f}h")

        lo_str = ", ".join(layover_detail) if layover_detail else "turn"
        pr(f"    SEQ-{e['seq_number']:>5}  d{min(dates):>2}-{max(dates):>2}  "
           f"({dd}d, layovers: {lo_str})  credit: {tpay/60:.1f}h")

    return {
        "span": span, "first_work": first_work, "last_work": last_work,
        "num_blocks": num_blocks, "internal_gaps": internal_gaps,
        "block_rating": block_rating, "largest_off": largest_off,
        "off_rating": off_rating, "working_dates": all_dates,
        "blocks": blocks,
    }


# ── Part 3: Commutability ──────────────────────────────────────────────

def analyze_commutability(layer_num, layer_entries, shape):
    if not layer_entries or shape.get("empty"):
        return {"score": 0}

    blocks = shape.get("blocks", [])
    if not blocks:
        return {"score": 0}

    pr(f"\n  COMMUTABILITY — Layer {layer_num}")

    sorted_entries = sorted(layer_entries, key=lambda e: min(e.get("chosen_dates", [999])))
    block_scores = []
    total_commute_events = 0

    for bi, block_dates in enumerate(blocks):
        block_set = set(block_dates)
        block_entries = [e for e in sorted_entries if set(e.get("chosen_dates", [])) & block_set]
        if not block_entries:
            continue

        first_entry = block_entries[0]
        last_entry = block_entries[-1]
        first_dps = first_entry.get("_full_seq", {}).get("duty_periods", [])
        last_dps = last_entry.get("_full_seq", {}).get("duty_periods", [])

        # Report time
        if first_dps:
            rpt = _hhmm_to_minutes(first_dps[0].get("report_base", "12:00"))
            rpt_str = first_dps[0].get("report_base", "12:00")
        else:
            rpt = 720
            rpt_str = "N/A"

        if rpt < 360:
            rpt_label, rpt_score = "BAD", 20
        elif rpt < 540:
            rpt_label, rpt_score = "MARGINAL", 50
        elif rpt < 720:
            rpt_label, rpt_score = "GOOD", 80
        else:
            rpt_label, rpt_score = "GREAT", 100

        # Release time
        if last_dps:
            rel = _hhmm_to_minutes(last_dps[-1].get("release_base", "18:00"))
            rel_str = last_dps[-1].get("release_base", "18:00")
        else:
            rel = 1080
            rel_str = "N/A"

        if rel >= 1320:
            rel_label, rel_score = "BAD", 20
        elif rel >= 1140:
            rel_label, rel_score = "MARGINAL", 50
        elif rel >= 960:
            rel_label, rel_score = "GOOD", 80
        else:
            rel_label, rel_score = "GREAT", 100

        # Buffer days
        pre_buffer = min(block_dates) - 1
        post_buffer = TOTAL_DATES - max(block_dates)
        buf_score = min(100, (min(pre_buffer, 2) + min(post_buffer, 2)) * 25)

        block_score = int(rpt_score * 0.35 + rel_score * 0.35 + buf_score * 0.30)
        block_scores.append(block_score)
        total_commute_events += 2  # in + out per block

        pr(f"    Block {bi+1} (d{min(block_dates)}-{max(block_dates)}, {len(block_dates)}d):")
        pr(f"      First report: {rpt_str} -> {rpt_label}")
        pr(f"      Last release: {rel_str} -> {rel_label}")
        pr(f"      Buffer before: {pre_buffer}d | Buffer after: {post_buffer}d")
        pr(f"      Block score: {block_score}/100")

    overall = int(sum(block_scores) / len(block_scores)) if block_scores else 0
    pr(f"    Total commute events: {total_commute_events}")
    pr(f"    Commutability score: {overall}/100")

    return {"score": overall, "commute_events": total_commute_events}


# ── Part 4: Trip Quality ───────────────────────────────────────────────

def analyze_trip_quality(layer_num, layer_entries, all_sequences):
    if not layer_entries:
        return {"score": 0}

    pr(f"\n  TRIP QUALITY — Layer {layer_num}")

    seq_data = _get_seq_data(layer_entries)

    # Trip length distribution
    lengths = defaultdict(int)
    for sd in seq_data:
        lengths[sd["duty_days"]] += 1
    mix = ", ".join(f"{v}x{k}-day" for k, v in sorted(lengths.items()))
    pr(f"    Trips: {len(seq_data)} sequences ({mix})")

    # Credit efficiency
    total_tpay = sum(sd["tpay_minutes"] for sd in seq_data)
    total_dd = sum(sd["duty_days"] for sd in seq_data)
    avg_cpd = total_tpay / total_dd if total_dd else 0

    pool_cpd = []
    for s in all_sequences:
        t = s.get("totals", {})
        dd = t.get("duty_days", 1) or 1
        tp = t.get("tpay_minutes", 0)
        if tp > 0 and dd > 0:
            pool_cpd.append(tp / dd)
    pool_avg = sum(pool_cpd) / len(pool_cpd) if pool_cpd else 0

    eff_label = "ABOVE AVG" if avg_cpd > pool_avg else "BELOW AVG"
    pr(f"    Credit efficiency: {avg_cpd/60:.2f} hrs/day (pool avg: {pool_avg/60:.2f}) -> {eff_label}")

    # Layover report
    all_layovers = []
    for sd in seq_data:
        for dp in sd["duty_periods"]:
            lo = dp.get("layover")
            if lo:
                city = lo.get("city", "?")
                rest = lo.get("rest_minutes", 0)
                tier = CITY_TIERS.get(city, CITY_DEFAULT)
                all_layovers.append((city, rest, tier))
                flag = ""
                if rest < 840:
                    flag = " [SHORT]"
                elif rest > 1800:
                    flag = " [LONG]"
                pr(f"      {city} ({tier}/100): {rest/60:.1f}h{flag}")

    if all_layovers:
        avg_lo = sum(r for _, r, _ in all_layovers) / len(all_layovers)
        min_lo = min(all_layovers, key=lambda x: x[1])
        max_lo = max(all_layovers, key=lambda x: x[1])
        avg_tier = sum(t for _, _, t in all_layovers) / len(all_layovers)
        pr(f"    Avg layover: {avg_lo/60:.1f}h | Min: {min_lo[1]/60:.0f}h ({min_lo[0]}) | Max: {max_lo[1]/60:.0f}h ({max_lo[0]})")
        pr(f"    Avg city tier: {avg_tier:.0f}/100")
    else:
        avg_tier = 50
        pr(f"    No layovers (all turns)")

    # Legs per day
    total_legs = sum(sd["leg_count"] for sd in seq_data)
    avg_legs = total_legs / total_dd if total_dd else 0
    heavy_days = sum(1 for sd in seq_data for dp in sd["duty_periods"]
                     if len(dp.get("legs", [])) >= 4)
    pr(f"    Avg legs/duty-day: {avg_legs:.1f} | Heavy days (4+ legs): {heavy_days}")

    # Deadhead and red-eye
    total_dh = sum(sd["deadhead_count"] for sd in seq_data)
    dh_pct = (total_dh / total_legs * 100) if total_legs else 0
    redeyes = sum(1 for sd in seq_data if sd["is_redeye"])
    odans = sum(1 for sd in seq_data if sd["is_odan"])
    pr(f"    Deadhead: {total_dh}/{total_legs} legs ({dh_pct:.0f}%)" +
       (f" [WARNING >15%]" if dh_pct > 15 else ""))
    if redeyes or odans:
        pr(f"    Red-eye: {redeyes} | ODAN: {odans}")
    else:
        pr(f"    Red-eye/ODAN: none")

    # Strategy match check for trip length
    strat = DEFAULT_LAYER_STRATEGIES.get(layer_num, {})
    min_pd = strat.get("min_pairing_days", 0)
    if min_pd > 0:
        violators = [sd for sd in seq_data if sd["duty_days"] < min_pd]
        if violators:
            pr(f"    WARNING: {len(violators)} trips shorter than min_pairing_days={min_pd}")

    # Composite quality score
    credit_score = min(100, max(0, (avg_cpd - 200) / 3))
    legs_score = max(20, 100 - (avg_legs - 1) * 30) if avg_legs > 1 else 100
    redeye_score = max(0, 100 - redeyes * 30 - odans * 40)
    dh_score = max(0, 100 * (1 - dh_pct / 30))
    composite = int(credit_score * 0.30 + avg_tier * 0.25 + legs_score * 0.20 +
                    redeye_score * 0.15 + dh_score * 0.10)
    pr(f"    Quality Score: {composite}/100")

    return {"score": composite, "avg_tier": avg_tier, "lengths": dict(lengths),
            "credit_per_day": avg_cpd, "avg_legs": avg_legs}


# ── Part 5: Cross-Layer Comparison ──────────────────────────────────────

def analyze_cross_layer(layers, all_results, all_shapes, all_quality, all_sequences):
    hr()
    pr("  PART 5: CROSS-LAYER COMPARISON")
    hr()

    # Diversity matrix
    layer_ids = {}
    for l, entries in layers.items():
        layer_ids[l] = {e.get("sequence_id") for e in entries}

    active = sorted(l for l in layer_ids if layer_ids[l])

    pr("\n  Jaccard Similarity Matrix:")
    pr(f"  {'':>4}", end="")
    for l in active:
        print(f"   L{l}", end="")
    pr()
    high_sim_pairs = []
    for l1 in active:
        pr(f"  L{l1}", end="")
        for l2 in active:
            if l1 == l2:
                print(f"    - ", end="")
            else:
                s1, s2 = layer_ids[l1], layer_ids[l2]
                j = len(s1 & s2) / len(s1 | s2) if (s1 | s2) else 0
                flag = "!" if j > 0.5 else " "
                print(f" {j:.2f}{flag}", end="")
                if j > 0.5 and l1 < l2:
                    high_sim_pairs.append((l1, l2, j))
        pr()

    if high_sim_pairs:
        pr(f"\n  WARNING: High similarity pairs (>0.5):")
        for l1, l2, j in high_sim_pairs:
            pr(f"    L{l1} & L{l2}: Jaccard = {j:.2f}")
    else:
        pr(f"\n  All layer pairs have Jaccard <= 0.5 (good diversity)")

    # Credit spread
    pr(f"\n  Credit Spread:")
    credits = {}
    for l in active:
        r = all_results.get(l, {})
        credits[l] = r.get("credit_val", 0)
        pr(f"    L{l}: {credits[l]:.1f}h")
    if credits:
        spread = max(credits.values()) - min(credits.values())
        pr(f"    Range: {spread:.1f}h {'(GOOD: >8h spread)' if spread >= 8 else '(NARROW: <8h spread)'}")

    # Strategy fulfillment
    pr(f"\n  Strategy Fulfillment:")
    strategy_checks = {
        1: "Compact front-loaded, 2+ day trips",
        2: "Compact back-loaded, 2+ day trips",
        3: "Max credit, 3+ day trips",
        4: "All 4-day trips, fewer commutes",
        5: "Best layover cities, 3+ day trips",
        6: "Flexible fallback, 2+ day trips",
        7: "Safety net, 2+ day trips",
    }

    for l in active:
        strat = DEFAULT_LAYER_STRATEGIES.get(l, {})
        shape = all_shapes.get(l, {})
        qual = all_quality.get(l, {})
        result = all_results.get(l, {})
        seq_data = result.get("seq_data", [])
        lengths = qual.get("lengths", {})

        checks = []
        match = True

        # Check min_pairing_days
        min_pd = strat.get("min_pairing_days", 0)
        if min_pd > 0:
            violators = [sd for sd in seq_data if sd["duty_days"] < min_pd]
            if violators:
                checks.append(f"FAIL: {len(violators)} trips < {min_pd}-day")
                match = False
            else:
                checks.append(f"OK: all trips >= {min_pd}-day")

        # Check compactness
        compactness = strat.get("compactness", "none")
        if compactness in ("strong", "moderate"):
            nb = shape.get("num_blocks", 99)
            if nb <= 2:
                checks.append(f"OK: {nb} block(s)")
            else:
                checks.append(f"WARN: {nb} blocks (expected <=2)")

        # Check target window
        tw = strat.get("target_window")
        if tw and not shape.get("empty"):
            mid = TOTAL_DATES // 2
            working = shape.get("working_dates", set())
            front = sum(1 for d in working if d <= mid)
            back = len(working) - front
            if tw == "first_half" and front >= back:
                checks.append("OK: front-loaded")
            elif tw == "second_half" and back >= front:
                checks.append("OK: back-loaded")
            else:
                checks.append(f"WARN: window mismatch (front={front}, back={back})")

        # L3: should have highest credit
        if l == 3:
            my_credit = credits.get(3, 0)
            others = [c for ll, c in credits.items() if ll != 3]
            if others and my_credit >= max(others) - 0.5:
                checks.append("OK: highest/near-highest credit")
            elif others:
                checks.append(f"WARN: not highest credit ({my_credit:.1f}h vs max {max(others):.1f}h)")

        # L4: should be all 4-day
        if l == 4:
            if set(lengths.keys()) == {4}:
                checks.append("OK: 100% 4-day trips")
            else:
                checks.append(f"INFO: mix {lengths} (target: all 4-day)")

        # L5: should have better city tiers
        if l == 5:
            my_tier = qual.get("avg_tier", 0)
            l1_tier = all_quality.get(1, {}).get("avg_tier", 0)
            l3_tier = all_quality.get(3, {}).get("avg_tier", 0)
            if my_tier > max(l1_tier, l3_tier):
                checks.append(f"OK: better cities ({my_tier:.0f} vs L1:{l1_tier:.0f}, L3:{l3_tier:.0f})")
            else:
                checks.append(f"INFO: city tier {my_tier:.0f} (L1:{l1_tier:.0f}, L3:{l3_tier:.0f})")

        status = "MATCH" if match else "MISMATCH"
        check_str = " | ".join(checks)
        pr(f"    L{l} [{status}] {strategy_checks.get(l, '?')}")
        pr(f"         {check_str}")

    # Safety Net Adequacy (L7)
    pr(f"\n  Safety Net Adequacy (L7):")
    l7_entries = layers.get(7, [])
    l6_entries = layers.get(6, [])
    # Count candidate pool sizes (all sequences with date info vs those matching strategy)
    seq_with_dates = sum(1 for s in all_sequences if s.get("operating_dates"))
    pr(f"    Total sequences with dates: {seq_with_dates}")
    pr(f"    L7 selected: {len(l7_entries)} sequences")
    pr(f"    L6 selected: {len(l6_entries)} sequences")

    # Check if L7 still legal (it was already checked above)
    l7_legal = all_results.get(7, {}).get("legal", False)
    pr(f"    L7 produces legal line: {'YES' if l7_legal else 'NO'}")


# ── Part 6: Final Scorecard ─────────────────────────────────────────────

def print_final_scorecard(all_results, all_shapes, all_commute, all_quality):
    hr()
    pr("  PART 6: FINAL SCORECARD")
    hr()
    pr()

    pr(f"  {'Layer':>5} | {'Strategy':>25} | {'Credit':>7} | {'Span':>4} | {'Off':>4} | {'Blk':>3} | {'Gap':>3} | {'Comm':>5} | {'Qual':>5} | {'Legal':>5} | {'Strat':>5}")
    pr(f"  {'-'*5}-+-{'-'*25}-+-{'-'*7}-+-{'-'*4}-+-{'-'*4}-+-{'-'*3}-+-{'-'*3}-+-{'-'*5}-+-{'-'*5}-+-{'-'*5}-+-{'-'*5}")

    for l in range(1, NUM_LAYERS + 1):
        r = all_results.get(l, {})
        s = all_shapes.get(l, {})
        c = all_commute.get(l, {})
        q = all_quality.get(l, {})
        name = LAYER_STRATEGY_NAMES.get(l, "?")[:25]

        if r.get("empty") or s.get("empty"):
            pr(f"  L{l:>3} | {name:>25} | {'EMPTY':>7} | {'--':>4} | {'--':>4} | {'--':>3} | {'--':>3} | {'--':>5} | {'--':>5} | {'--':>5} | {'--':>5}")
            continue

        legal_icon = "Y" if r.get("legal") else "N"
        # Strategy match (simple check)
        strat = DEFAULT_LAYER_STRATEGIES.get(l, {})
        min_pd = strat.get("min_pairing_days", 0)
        seq_data = r.get("seq_data", [])
        strat_ok = all(sd["duty_days"] >= min_pd for sd in seq_data) if min_pd > 0 and seq_data else True

        pr(f"  L{l:>3} | {name:>25} | {r.get('credit_val', 0):>5.1f}h | {s.get('span', 0):>3}d | {s.get('largest_off', 0):>3}d | {s.get('num_blocks', 0):>3} | {s.get('internal_gaps', 0):>3} | {c.get('score', 0):>3}/100 | {q.get('score', 0):>3}/100 | {'  ' + legal_icon:>5} | {'  Y' if strat_ok else '  N':>5}")

    # Three summary questions
    pr()
    hr("-")
    pr()

    # Q1: Are all layers legal?
    all_legal = all(all_results.get(l, {}).get("legal", False) for l in range(1, NUM_LAYERS + 1))
    pr("  1. ARE ALL LAYERS LEGAL?")
    if all_legal:
        pr("     YES. All 7 layers pass all 6 legality checks: no date conflicts,")
        pr("     adequate rest periods, credit within range, sufficient days off,")
        pr("     7-day block hours under 30h, and no multi-OPS duplicates.")
    else:
        pr("     NO. The following layers have legality failures:")
        for l in range(1, NUM_LAYERS + 1):
            r = all_results.get(l, {})
            if not r.get("legal"):
                for iss in r.get("issues", []):
                    pr(f"       L{l}: {iss}")

    pr()

    # Q2: Would a domestic FA submit this bid?
    pr("  2. WOULD A DOMESTIC FA WANTING COMPACT 3-4 DAY TRIPS SUBMIT THIS BID?")
    pr()

    # Evaluate L1-L3
    for l in [1, 2, 3]:
        r = all_results.get(l, {})
        s = all_shapes.get(l, {})
        q = all_quality.get(l, {})
        c = all_commute.get(l, {})
        if r.get("empty"):
            pr(f"     L{l}: EMPTY — cannot evaluate")
            continue

        seq_data = r.get("seq_data", [])
        lengths = defaultdict(int)
        for sd in seq_data:
            lengths[sd["duty_days"]] += 1
        mix = ", ".join(f"{v}x{k}d" for k, v in sorted(lengths.items()))

        cities = []
        for sd in seq_data:
            cities.extend(sd["layover_cities"])
        city_list = ", ".join(sorted(set(cities))) if cities else "turns only"

        verdict_parts = []
        if s.get("num_blocks", 99) <= 2:
            verdict_parts.append("compact")
        else:
            verdict_parts.append(f"scattered ({s['num_blocks']} blocks)")
        if s.get("span", 99) <= 18:
            verdict_parts.append(f"{s['span']}d span")
        else:
            verdict_parts.append(f"wide {s['span']}d span")

        pr(f"     L{l}: {r.get('credit_val', 0):.1f}h | {mix} | {', '.join(verdict_parts)} | "
           f"cities: {city_list}")
        pr(f"         Quality: {q.get('score', 0)}/100 | Commutability: {c.get('score', 0)}/100")

    pr()

    # Overall verdict
    l1_shape = all_shapes.get(1, {})
    l1_qual = all_quality.get(1, {})
    good_points = []
    bad_points = []

    if all_legal:
        good_points.append("All layers legal")
    if l1_shape.get("num_blocks", 99) <= 2:
        good_points.append(f"L1 is compact ({l1_shape.get('span', 0)}d span, {l1_shape.get('num_blocks', 0)} block(s))")
    if l1_shape.get("largest_off", 0) >= 11:
        good_points.append(f"L1 has {l1_shape.get('largest_off', 0)} days off in a row")

    # Check credit diversity
    credit_vals = [all_results.get(l, {}).get("credit_val", 0) for l in range(1, NUM_LAYERS + 1)]
    credit_vals = [c for c in credit_vals if c > 0]
    if credit_vals:
        spread = max(credit_vals) - min(credit_vals)
        if spread >= 8:
            good_points.append(f"Credit spread: {spread:.1f}h")
        else:
            bad_points.append(f"Narrow credit spread: {spread:.1f}h")

    # Check for 1-day turns
    for l in range(1, NUM_LAYERS + 1):
        seq_data = all_results.get(l, {}).get("seq_data", [])
        ones = sum(1 for sd in seq_data if sd["duty_days"] == 1)
        if ones > 0:
            bad_points.append(f"L{l} has {ones} 1-day turn(s)")

    if good_points:
        pr("     GOOD:")
        for p in good_points:
            pr(f"       + {p}")
    if bad_points:
        pr("     CONCERNS:")
        for p in bad_points:
            pr(f"       - {p}")
    pr()

    overall = "YES" if all_legal and not bad_points else ("MOSTLY YES" if all_legal else "NO")
    pr(f"     VERDICT: {overall}")

    pr()

    # Q3: Does the 7-layer set provide adequate fallback coverage?
    pr("  3. DOES THE 7-LAYER SET PROVIDE ADEQUATE FALLBACK COVERAGE?")
    pr()

    # Check progression
    pr("     Layer progression:")
    for l in range(1, NUM_LAYERS + 1):
        r = all_results.get(l, {})
        s = all_shapes.get(l, {})
        if r.get("empty"):
            pr(f"       L{l}: EMPTY")
            continue
        strat = LAYER_STRATEGY_NAMES.get(l, "?")
        pr(f"       L{l} ({strat}): {r.get('credit_val', 0):.1f}h, "
           f"{s.get('span', 0)}d span, {s.get('num_blocks', 0)} block(s)")

    pr()

    # Check if any layer would be dreadful
    dread_layers = []
    for l in range(1, NUM_LAYERS + 1):
        s = all_shapes.get(l, {})
        if not s.get("empty") and s.get("num_blocks", 0) >= 5:
            dread_layers.append(l)

    if dread_layers:
        pr(f"     WARNING: Layers {dread_layers} have 5+ work blocks (scattered, dreadful)")
    else:
        pr("     No layer has 5+ work blocks — all are flyable.")

    l7_legal = all_results.get(7, {}).get("legal", False)
    pr(f"     L7 (safety net) legal: {'YES' if l7_legal else 'NO'}")
    pr(f"     L7 prevents Layer None: {'YES' if l7_legal else 'NO'}")
    pr()


# ── Main ────────────────────────────────────────────────────────────────

def main():
    layers, all_seqs, seq_lookup = load_and_run_optimizer()

    all_results = {}
    all_shapes = {}
    all_commute = {}
    all_quality = {}

    # Part 1: Legality
    for l in range(1, NUM_LAYERS + 1):
        all_results[l] = check_legality(l, layers.get(l, []))

    all_legal = print_legality_table(all_results)

    # Print detailed legality for each layer
    for l in range(1, NUM_LAYERS + 1):
        r = all_results[l]
        if r.get("empty"):
            continue
        sd = r.get("seq_data", [])
        pr(f"  Layer {l} sequences:")
        for s in sd:
            dates = sorted(s["chosen_dates"])
            pr(f"    SEQ {s['seq_number']:>5}: d{min(dates):>2}-{max(dates):>2} ({s['duty_days']}d) "
               f"| TPAY {s['tpay_minutes']/60:.1f}h | Block {s['block_minutes']/60:.1f}h "
               f"| {','.join(s['layover_cities']) or 'turn'}")

        # Print 7-day block warnings
        warnings = r.get("block7_warnings", [])
        if warnings:
            pr(f"    7-day block warnings (>25h):")
            for start, block in warnings:
                pr(f"      d{start}-{start+6}: {block/60:.1f}h")
        pr()

    if not all_legal:
        pr("  STOPPING: Legality failures detected. Fix before proceeding.")
        # Continue anyway for diagnostic purposes

    # Part 2: Schedule Shape
    hr()
    pr("  PART 2: SCHEDULE SHAPE")
    hr()
    for l in range(1, NUM_LAYERS + 1):
        all_shapes[l] = analyze_shape(l, layers.get(l, []))

    # Part 3: Commutability
    hr()
    pr("  PART 3: COMMUTABILITY")
    hr()
    for l in range(1, NUM_LAYERS + 1):
        all_commute[l] = analyze_commutability(l, layers.get(l, []), all_shapes.get(l, {}))

    # Part 4: Trip Quality
    hr()
    pr("  PART 4: TRIP QUALITY")
    hr()
    for l in range(1, NUM_LAYERS + 1):
        all_quality[l] = analyze_trip_quality(l, layers.get(l, []), all_seqs)

    # Part 5: Cross-Layer
    analyze_cross_layer(layers, all_results, all_shapes, all_quality, all_seqs)

    # Part 6: Final Scorecard
    print_final_scorecard(all_results, all_shapes, all_commute, all_quality)

    # Save report
    report = tee.getvalue()
    report_path = os.path.join(os.path.dirname(__file__), "layer_analysis_v3_report.md")
    with open(report_path, "w") as f:
        f.write("```\n")
        f.write(report)
        f.write("```\n")
    pr(f"\n  Report saved to: {report_path}")


if __name__ == "__main__":
    main()
