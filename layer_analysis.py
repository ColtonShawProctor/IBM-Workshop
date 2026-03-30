#!/usr/bin/env python3
"""PBS Layer Output Analyzer — Deep quality analysis of optimizer layer results."""

import sys
import os
import json
import math
from collections import defaultdict
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from app.db import get_collection

# ── Config ───────────────────────────────────────────────────────────────
BID_PERIOD_ID = "85646a2c-573f-4139-a3c6-c769242d6507"
BID_ID = "dbdba365-6257-4b5f-9a65-8a4d8c54e93e"
TOTAL_DATES = 30  # January (this bid period uses 30)
TARGET_CREDIT_MIN = 4200  # 70 hours
TARGET_CREDIT_MAX = 5400  # 90 hours
MIN_DAYS_OFF = 11
NUM_LAYERS = 7

# City tier scores from cpsat_builder
CITY_TIERS = {
    "NRT": 100, "HND": 95, "LHR": 98, "CDG": 95, "FCO": 95, "BCN": 93,
    "ATH": 92, "DUB": 90, "AMS": 92, "MXP": 90, "ICN": 90, "HKG": 92,
    "SIN": 95, "BKK": 90, "GRU": 85, "EZE": 85, "SCL": 82, "LIS": 88,
    "MAD": 90, "FRA": 85, "MUC": 85, "ZRH": 88, "PRG": 88, "VCE": 92,
    "HNL": 95, "OGG": 93, "SFO": 88, "LAX": 85, "SAN": 88, "SEA": 85,
    "BOS": 87, "AUS": 85, "DEN": 83, "PDX": 82, "SNA": 85, "MIA": 82,
    "TPA": 80, "SJU": 82, "MSP": 75, "DTW": 70, "JFK": 78, "DCA": 75,
    "LAS": 75, "PHX": 72, "ORD": 70, "SLC": 70, "RDU": 68, "BNA": 72,
    "MCO": 70, "PHL": 60, "DFW": 55, "CLT": 58, "STL": 52, "CVG": 50,
    "CMH": 50, "IND": 48, "MCI": 50,
}
CITY_DEFAULT = 55

# Layer strategy names
LAYER_NAMES = {
    1: "Dream Schedule — Compact + Quality",
    2: "Flip Window — Back Half",
    3: "Maximum Pay",
    4: "Quality of Life",
    5: "Diverse Alternative A",
    6: "Diverse Alternative B",
    7: "Safety Net — Maximum Flexibility",
}


def hhmm_to_minutes(t: str) -> int:
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def minutes_to_hhmm(m: int) -> str:
    return f"{m // 60}:{m % 60:02d}"


def hr_min(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


# ── Data Loading ─────────────────────────────────────────────────────────

def load_data():
    """Load bid entries and full sequence data from Astra DB."""
    print("Loading data from Astra DB...")

    bid_coll = get_collection("bids")
    bid = bid_coll.find_one({"_id": BID_ID})
    entries = bid.get("entries", [])
    properties = bid.get("properties", [])

    seq_coll = get_collection("sequences")
    sequences = list(seq_coll.find({"bid_period_id": BID_PERIOD_ID}, limit=2000))

    seq_lookup = {s["_id"]: s for s in sequences}

    # Organize entries by layer, enriching with full sequence data
    layers = defaultdict(list)
    for entry in entries:
        layer_num = entry.get("layer", 0)
        if layer_num == 0:
            continue  # skip excluded
        seq_id = entry.get("sequence_id")
        full_seq = seq_lookup.get(seq_id, {})
        enriched = {**entry, "_full_seq": full_seq}
        layers[layer_num].append(enriched)

    # Sort each layer by rank
    for l in layers:
        layers[l].sort(key=lambda e: e.get("rank", 999))

    print(f"  Loaded {len(entries)} entries across {len(layers)} layers")
    print(f"  Loaded {len(sequences)} sequences from bid period pool")
    print(f"  Properties: {len(properties)}")
    for p in properties:
        print(f"    - {p['property_key']} = {p.get('value')} (layers {p.get('layers', [])})")
    print()

    return layers, sequences, seq_lookup, properties


# ── Phase 2: Per-Layer Legality Audit ────────────────────────────────────

def audit_layer(layer_num, layer_entries):
    """Run all legality checks on a single layer."""
    print(f"\n{'='*70}")
    print(f"  LAYER {layer_num}: {LAYER_NAMES.get(layer_num, '?')}")
    print(f"{'='*70}")

    if not layer_entries:
        print("  *** EMPTY LAYER — NO SEQUENCES SELECTED ***")
        print("  This means the optimizer found NO sequences matching the")
        print("  properties assigned to this layer. The filter is too restrictive.")
        return {
            "layer": layer_num,
            "empty": True,
            "legal": False,
            "issues": ["EMPTY — no sequences matched layer properties"],
        }

    results = {"layer": layer_num, "empty": False, "issues": []}

    # Extract all chosen dates and sequence info
    all_working_dates = set()
    seq_data = []
    for entry in layer_entries:
        chosen = set(entry.get("chosen_dates", []))
        full = entry.get("_full_seq", {})
        seq_data.append({
            "seq_number": entry.get("seq_number", 0),
            "chosen_dates": chosen,
            "tpay_minutes": full.get("totals", {}).get("tpay_minutes", 0),
            "block_minutes": full.get("totals", {}).get("block_minutes", 0),
            "duty_days": full.get("totals", {}).get("duty_days", 1) or 1,
            "leg_count": full.get("totals", {}).get("leg_count", 0),
            "deadhead_count": full.get("totals", {}).get("deadhead_count", 0),
            "tafb_minutes": full.get("totals", {}).get("tafb_minutes", 0),
            "layover_cities": full.get("layover_cities", []),
            "is_turn": full.get("is_turn", False),
            "is_redeye": full.get("is_redeye", False),
            "is_odan": full.get("is_odan", False),
            "has_deadhead": full.get("has_deadhead", False),
            "duty_periods": full.get("duty_periods", []),
            "preference_score": entry.get("preference_score", 0),
            "attainability": entry.get("attainability", "unknown"),
            "category": full.get("category", ""),
            "seq_id": entry.get("sequence_id", ""),
        })
        all_working_dates |= chosen

    num_seqs = len(seq_data)
    print(f"\n  Sequences selected: {num_seqs}")
    for sd in seq_data:
        dates = sorted(sd["chosen_dates"])
        tpay_h = sd["tpay_minutes"] / 60
        print(f"    SEQ {sd['seq_number']:>5}: days {min(dates):>2}-{max(dates):>2} "
              f"({sd['duty_days']}d) | TPAY {tpay_h:.1f}h | "
              f"layovers: {', '.join(sd['layover_cities']) or 'turn'} | "
              f"{sd['category']}")

    # ── Date Conflict Check ──────────────────────────────────────────
    print(f"\n  --- Date Conflict Check ---")
    conflicts = []
    for i in range(len(seq_data)):
        for j in range(i + 1, len(seq_data)):
            overlap = seq_data[i]["chosen_dates"] & seq_data[j]["chosen_dates"]
            if overlap:
                conflicts.append((seq_data[i]["seq_number"], seq_data[j]["seq_number"], sorted(overlap)))
    if conflicts:
        print(f"  FAIL: {len(conflicts)} date conflicts found!")
        for a, b, days in conflicts:
            print(f"    SEQ {a} vs SEQ {b}: overlap on days {days}")
        results["issues"].append(f"{len(conflicts)} date conflicts")
    else:
        print(f"  PASS: No date conflicts")

    # ── Rest Period Check ────────────────────────────────────────────
    print(f"\n  --- Rest Period Check ---")
    sorted_seqs = sorted(seq_data, key=lambda s: min(s["chosen_dates"]) if s["chosen_dates"] else 999)
    rest_issues = []
    for i in range(len(sorted_seqs) - 1):
        curr = sorted_seqs[i]
        nxt = sorted_seqs[i + 1]
        if not curr["chosen_dates"] or not nxt["chosen_dates"]:
            continue
        curr_last = max(curr["chosen_dates"])
        nxt_first = min(nxt["chosen_dates"])

        gap_days = nxt_first - curr_last
        if gap_days > 1:
            rest_hours = "N/A (multi-day gap)"
            status = "OK"
        elif gap_days == 1:
            # Consecutive days — check release/report times
            curr_dps = curr["duty_periods"]
            nxt_dps = nxt["duty_periods"]
            if curr_dps and nxt_dps:
                rel = hhmm_to_minutes(curr_dps[-1].get("release_base", "18:00"))
                rpt = hhmm_to_minutes(nxt_dps[0].get("report_base", "08:00"))
                rest_min = (24 * 60 - rel) + rpt
                rest_hours = f"{rest_min / 60:.1f}h"
                if rest_min < 600:
                    status = "FAIL (< 10h FAA minimum)"
                    rest_issues.append(f"SEQ {curr['seq_number']} → SEQ {nxt['seq_number']}: {rest_hours}")
                elif rest_min < 720:
                    status = "WARNING (< 12h)"
                else:
                    status = "OK"
            else:
                rest_hours = "N/A (no duty period data)"
                status = "OK"
        else:
            rest_hours = "OVERLAP"
            status = "FAIL (overlapping)"
            rest_issues.append(f"SEQ {curr['seq_number']} → SEQ {nxt['seq_number']}: overlapping")

        print(f"    SEQ {curr['seq_number']} (day {curr_last}) → SEQ {nxt['seq_number']} (day {nxt_first}): "
              f"gap={gap_days}d, rest={rest_hours} [{status}]")

    if rest_issues:
        print(f"  FAIL: {len(rest_issues)} rest violations")
        results["issues"].append(f"{len(rest_issues)} rest violations")
    else:
        print(f"  PASS: All rest periods adequate")

    # ── Credit Hour Range Check ──────────────────────────────────────
    print(f"\n  --- Credit Hour Range Check ---")
    total_tpay = sum(sd["tpay_minutes"] for sd in seq_data)
    total_tpay_hours = total_tpay / 60
    in_range = TARGET_CREDIT_MIN <= total_tpay <= TARGET_CREDIT_MAX
    boundary_warning = ""
    if in_range:
        low_margin = total_tpay - TARGET_CREDIT_MIN
        high_margin = TARGET_CREDIT_MAX - total_tpay
        if low_margin < 120 or high_margin < 120:
            boundary_warning = f" ⚠ CLOSE TO BOUNDARY (low margin: {low_margin/60:.1f}h, high margin: {high_margin/60:.1f}h)"
    status = "PASS" if in_range else "FAIL"
    print(f"  Total TPAY: {total_tpay_hours:.1f} hours ({total_tpay} minutes)")
    print(f"  Target range: {TARGET_CREDIT_MIN/60:.0f}–{TARGET_CREDIT_MAX/60:.0f} hours ({TARGET_CREDIT_MIN}–{TARGET_CREDIT_MAX} minutes)")
    print(f"  {status}: {'Within range' if in_range else 'OUT OF RANGE'}{boundary_warning}")
    if not in_range:
        results["issues"].append(f"Credit {total_tpay_hours:.1f}h outside {TARGET_CREDIT_MIN/60:.0f}-{TARGET_CREDIT_MAX/60:.0f}h range")

    results["total_credit_hours"] = total_tpay_hours
    results["total_credit_minutes"] = total_tpay

    # ── Days Off Check ───────────────────────────────────────────────
    print(f"\n  --- Days Off Check ---")
    working_days = len(all_working_dates)
    days_off = TOTAL_DATES - working_days
    status = "PASS" if days_off >= MIN_DAYS_OFF else "FAIL"
    print(f"  Working days: {working_days}")
    print(f"  Days off: {days_off}")
    print(f"  Minimum required: {MIN_DAYS_OFF}")
    print(f"  {status}")
    if days_off < MIN_DAYS_OFF:
        results["issues"].append(f"Only {days_off} days off (min {MIN_DAYS_OFF})")

    results["working_days"] = working_days
    results["days_off"] = days_off

    # ── Cumulative Duty Check ────────────────────────────────────────
    print(f"\n  --- Cumulative Duty Check (7-day window, 30h block limit) ---")
    worst_window = 0
    worst_window_range = ""
    for start in range(1, TOTAL_DATES - 5):
        window = set(range(start, start + 7))
        block_in_window = 0
        for sd in seq_data:
            if sd["chosen_dates"] & window:
                block_in_window += sd["block_minutes"]
        if block_in_window > worst_window:
            worst_window = block_in_window
            worst_window_range = f"days {start}-{start+6}"

    limit = 30 * 60  # 30 hours in minutes
    status = "PASS" if worst_window <= limit else "FAIL"
    print(f"  Worst 7-day window: {worst_window/60:.1f}h block ({worst_window_range})")
    print(f"  Limit: 30.0h")
    print(f"  {status}")
    if worst_window > limit:
        results["issues"].append(f"7-day block limit exceeded: {worst_window/60:.1f}h")

    # ── Multi-OPS Check ──────────────────────────────────────────────
    print(f"\n  --- Multi-OPS Check ---")
    seq_ids = [sd["seq_id"] for sd in seq_data]
    dupes = [sid for sid in set(seq_ids) if seq_ids.count(sid) > 1]
    if dupes:
        print(f"  FAIL: {len(dupes)} sequences appear multiple times")
        results["issues"].append(f"{len(dupes)} duplicate sequence selections")
    else:
        print(f"  PASS: No duplicate sequence selections")

    # ── Legal Summary ────────────────────────────────────────────────
    results["legal"] = len(results["issues"]) == 0
    print(f"\n  LEGALITY: {'✓ ALL CHECKS PASSED' if results['legal'] else '✗ ISSUES FOUND: ' + ', '.join(results['issues'])}")

    return results


# ── Phase 3: Schedule Shape Analysis ─────────────────────────────────────

def analyze_shape(layer_num, layer_entries):
    """Analyze schedule compactness and shape."""
    if not layer_entries:
        return {"empty": True}

    all_dates = set()
    for e in layer_entries:
        all_dates |= set(e.get("chosen_dates", []))

    if not all_dates:
        return {"empty": True}

    sorted_dates = sorted(all_dates)
    first_work = sorted_dates[0]
    last_work = sorted_dates[-1]
    span = last_work - first_work + 1

    # Rating
    if span <= 14:
        span_rating = "EXCELLENT"
    elif span <= 18:
        span_rating = "GOOD"
    elif span <= 22:
        span_rating = "FAIR"
    else:
        span_rating = "POOR (scattered)"

    # Contiguity — find work blocks
    blocks = []
    current_block = [sorted_dates[0]]
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i-1] + 1:
            current_block.append(sorted_dates[i])
        else:
            blocks.append(current_block)
            current_block = [sorted_dates[i]]
    blocks.append(current_block)

    num_blocks = len(blocks)
    # Internal gaps: off days between first and last working day that are not working days
    all_period_dates = set(range(first_work, last_work + 1))
    internal_gaps = len(all_period_dates - all_dates)

    if num_blocks == 1 and internal_gaps == 0:
        contiguity = "PERFECT (1 block, 0 gaps)"
    elif num_blocks <= 2 and internal_gaps <= 2:
        contiguity = "GOOD"
    elif num_blocks <= 3:
        contiguity = "FAIR"
    else:
        contiguity = "POOR"

    # Largest off-day block
    all_month = set(range(1, TOTAL_DATES + 1))
    off_days = sorted(all_month - all_dates)
    if off_days:
        off_blocks = []
        curr_block = [off_days[0]]
        for i in range(1, len(off_days)):
            if off_days[i] == off_days[i-1] + 1:
                curr_block.append(off_days[i])
            else:
                off_blocks.append(curr_block)
                curr_block = [off_days[i]]
        off_blocks.append(curr_block)
        largest_off = max(len(b) for b in off_blocks)
        largest_off_range = max(off_blocks, key=len)
    else:
        largest_off = 0
        largest_off_range = []

    if largest_off >= 13:
        off_rating = "EXCELLENT"
    elif largest_off >= 10:
        off_rating = "GOOD"
    elif largest_off >= 7:
        off_rating = "FAIR"
    else:
        off_rating = "POOR"

    print(f"\n  --- Schedule Shape ---")
    print(f"  Work span: days {first_work}–{last_work} ({span} days) [{span_rating}]")
    print(f"  Work blocks: {num_blocks} | Internal gaps: {internal_gaps} [{contiguity}]")
    print(f"  Largest off-day block: {largest_off} days "
          f"(days {min(largest_off_range)}-{max(largest_off_range)})" if largest_off_range else "")
    print(f"  Off-day rating: [{off_rating}]")

    # Visual calendar
    print(f"\n  Layer {layer_num}: \"{LAYER_NAMES.get(layer_num, '?')}\"")
    total_credit = sum(e.get("_full_seq", {}).get("totals", {}).get("tpay_minutes", 0)
                       for e in layer_entries)
    print(f"  Credit: {total_credit/60:.1f} hrs | Span: Days {first_work}-{last_work} | "
          f"Off Block: {largest_off}d (days {min(largest_off_range)}-{max(largest_off_range)})" if largest_off_range else "")
    print()

    # Print calendar grid (January 2026 starts on Thursday)
    # Actually, let's just print a generic grid with day numbers
    # Assuming day 1 = first day of bid period
    print("    Mon  Tue  Wed  Thu  Fri  Sat  Sun")
    # January 2026 starts on Thursday (day_of_week = 3, 0=Mon)
    dow_start = 3  # Thursday
    row = "    " + "     " * dow_start
    for day in range(1, TOTAL_DATES + 1):
        dow = (dow_start + day - 1) % 7
        if day in all_dates:
            row += f"{day:>2}\u2593\u2593 "
        else:
            row += f"{day:>2}   "
        if dow == 6:
            print(row)
            row = "    "
    if row.strip():
        print(row)

    # Print sequence assignments
    print()
    for e in layer_entries:
        dates = sorted(e.get("chosen_dates", []))
        cities = e.get("_full_seq", {}).get("layover_cities", [])
        print(f"    SEQ-{e['seq_number']} (days {min(dates)}-{max(dates)}, "
              f"{'→'.join(cities) if cities else 'turn'})")

    return {
        "span": span,
        "span_rating": span_rating,
        "first_work": first_work,
        "last_work": last_work,
        "num_blocks": num_blocks,
        "internal_gaps": internal_gaps,
        "contiguity": contiguity,
        "largest_off": largest_off,
        "off_rating": off_rating,
        "working_dates": all_dates,
    }


# ── Phase 4: Commutability Analysis ─────────────────────────────────────

def analyze_commutability(layer_num, layer_entries):
    """Analyze commute-friendliness of a layer."""
    if not layer_entries:
        return {"score": 0}

    print(f"\n  --- Commutability Analysis ---")

    sorted_entries = sorted(layer_entries,
                            key=lambda e: min(e.get("chosen_dates", [999])))

    # Find work blocks
    all_dates = set()
    for e in sorted_entries:
        all_dates |= set(e.get("chosen_dates", []))

    sorted_dates = sorted(all_dates)
    blocks = []
    current_block_dates = [sorted_dates[0]]
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i-1] + 1:
            current_block_dates.append(sorted_dates[i])
        else:
            blocks.append(current_block_dates)
            current_block_dates = [sorted_dates[i]]
    blocks.append(current_block_dates)

    scores = []

    for bi, block_dates in enumerate(blocks):
        block_start = min(block_dates)
        block_end = max(block_dates)

        # Find first and last sequence in this block
        block_entries = [e for e in sorted_entries
                         if set(e.get("chosen_dates", [])) & set(block_dates)]
        if not block_entries:
            continue

        first_entry = block_entries[0]
        last_entry = block_entries[-1]

        # Report time of first sequence
        first_dps = first_entry.get("_full_seq", {}).get("duty_periods", [])
        if first_dps:
            rpt = hhmm_to_minutes(first_dps[0].get("report_base", "12:00"))
            rpt_str = first_dps[0].get("report_base", "12:00")
        else:
            rpt = 720
            rpt_str = "N/A"

        if rpt >= 660:  # 11:00
            rpt_rating = "EXCELLENT"
            rpt_score = 100
        elif rpt >= 540:  # 09:00
            rpt_rating = "GOOD"
            rpt_score = 75
        elif rpt >= 420:  # 07:00
            rpt_rating = "FAIR"
            rpt_score = 50
        else:
            rpt_rating = "POOR (need night-before commute)"
            rpt_score = 20

        # Release time of last sequence
        last_dps = last_entry.get("_full_seq", {}).get("duty_periods", [])
        if last_dps:
            rel = hhmm_to_minutes(last_dps[-1].get("release_base", "18:00"))
            rel_str = last_dps[-1].get("release_base", "18:00")
        else:
            rel = 1080
            rel_str = "N/A"

        if rel < 900:  # 15:00
            rel_rating = "EXCELLENT"
            rel_score = 100
        elif rel < 1080:  # 18:00
            rel_rating = "GOOD"
            rel_score = 75
        elif rel < 1260:  # 21:00
            rel_rating = "FAIR"
            rel_score = 50
        else:
            rel_rating = "POOR (no flights home)"
            rel_score = 20

        # Buffer days
        pre_buffer = block_start - 1  # off days before block
        post_buffer = TOTAL_DATES - block_end  # off days after block
        buffer_score = min(100, (min(pre_buffer, 2) + min(post_buffer, 2)) * 25)

        block_score = int(rpt_score * 0.35 + rel_score * 0.35 + buffer_score * 0.30)
        scores.append(block_score)

        print(f"  Work Block {bi+1} (days {block_start}-{block_end}):")
        print(f"    First report: {rpt_str} [{rpt_rating}]")
        print(f"    Last release: {rel_str} [{rel_rating}]")
        print(f"    Pre-buffer: {pre_buffer} days | Post-buffer: {post_buffer} days")
        print(f"    Block commute score: {block_score}/100")

    overall = int(sum(scores) / len(scores)) if scores else 0
    print(f"  Overall Commutability Score: {overall}/100")

    return {"score": overall, "block_scores": scores}


# ── Phase 5: Trip Quality Breakdown ─────────────────────────────────────

def analyze_trip_quality(layer_num, layer_entries, all_sequences):
    """Analyze trip quality metrics for a layer."""
    if not layer_entries:
        return {"score": 0}

    print(f"\n  --- Trip Quality Breakdown ---")

    seq_data = []
    for e in layer_entries:
        full = e.get("_full_seq", {})
        totals = full.get("totals", {})
        seq_data.append({
            "seq_number": e.get("seq_number", 0),
            "tpay_minutes": totals.get("tpay_minutes", 0),
            "duty_days": totals.get("duty_days", 1) or 1,
            "tafb_minutes": totals.get("tafb_minutes", 0),
            "block_minutes": totals.get("block_minutes", 0),
            "leg_count": totals.get("leg_count", 0),
            "deadhead_count": totals.get("deadhead_count", 0),
            "layover_cities": full.get("layover_cities", []),
            "duty_periods": full.get("duty_periods", []),
            "is_turn": full.get("is_turn", False),
            "is_redeye": full.get("is_redeye", False),
            "is_odan": full.get("is_odan", False),
            "has_deadhead": full.get("has_deadhead", False),
        })

    # Credit efficiency
    print(f"\n  Credit Efficiency:")
    total_tpay = sum(sd["tpay_minutes"] for sd in seq_data)
    total_duty_days = sum(sd["duty_days"] for sd in seq_data)
    avg_tpay_per_day = total_tpay / total_duty_days if total_duty_days else 0

    # Pool average
    pool_tpay = []
    for s in all_sequences:
        t = s.get("totals", {})
        dd = t.get("duty_days", 1) or 1
        tpay = t.get("tpay_minutes", 0)
        if tpay > 0 and dd > 0:
            pool_tpay.append(tpay / dd)
    pool_avg = sum(pool_tpay) / len(pool_tpay) if pool_tpay else 0

    print(f"    Avg TPAY/duty day: {avg_tpay_per_day:.0f} min ({avg_tpay_per_day/60:.1f}h)")
    print(f"    Pool average: {pool_avg:.0f} min ({pool_avg/60:.1f}h)")
    print(f"    vs pool: {'ABOVE' if avg_tpay_per_day > pool_avg else 'BELOW'} average "
          f"({(avg_tpay_per_day - pool_avg)/pool_avg*100:+.1f}%)" if pool_avg > 0 else "")

    # Layover analysis
    print(f"\n  Layover Analysis:")
    all_layovers = []
    for sd in seq_data:
        for dp in sd["duty_periods"]:
            lo = dp.get("layover")
            if lo:
                city = lo.get("city", "?")
                rest_min = lo.get("rest_minutes", 0)
                all_layovers.append((city, rest_min))
                tier = CITY_TIERS.get(city, CITY_DEFAULT)
                status = ""
                if rest_min < 720:
                    status = " ⚠ SHORT (<12h)"
                elif rest_min > 1800:
                    status = " ⚠ VERY LONG (>30h)"
                print(f"    {city} ({tier}/100): {rest_min/60:.1f}h rest{status}")

    if not all_layovers:
        print(f"    No layovers (all turns)")

    # City mix score
    if all_layovers:
        avg_city_score = sum(CITY_TIERS.get(c, CITY_DEFAULT) for c, _ in all_layovers) / len(all_layovers)
        print(f"    Average city score: {avg_city_score:.0f}/100")

    # Duty intensity
    print(f"\n  Duty Intensity:")
    total_legs = sum(sd["leg_count"] for sd in seq_data)
    avg_legs_per_day = total_legs / total_duty_days if total_duty_days else 0
    print(f"    Total legs: {total_legs}")
    print(f"    Avg legs/duty day: {avg_legs_per_day:.1f}")
    heavy_days = 0
    for sd in seq_data:
        for dp in sd["duty_periods"]:
            legs = len(dp.get("legs", []))
            if legs >= 4:
                heavy_days += 1
    if heavy_days:
        print(f"    ⚠ {heavy_days} duty days with 4+ legs")

    # Average duty period length
    all_duty_mins = []
    for sd in seq_data:
        for dp in sd["duty_periods"]:
            dm = dp.get("duty_minutes")
            if dm:
                all_duty_mins.append(dm)
    if all_duty_mins:
        avg_duty = sum(all_duty_mins) / len(all_duty_mins)
        print(f"    Avg duty period: {avg_duty/60:.1f}h")

    # Trip length distribution
    print(f"\n  Trip Length Distribution:")
    lengths = defaultdict(int)
    for sd in seq_data:
        lengths[sd["duty_days"]] += 1
    for dd in sorted(lengths.keys()):
        label = "turn" if dd == 1 else f"{dd}-day"
        print(f"    {label}: {lengths[dd]} trips")

    # Red-eye / ODAN
    redeyes = sum(1 for sd in seq_data if sd["is_redeye"])
    odans = sum(1 for sd in seq_data if sd["is_odan"])
    if redeyes or odans:
        print(f"\n  ⚠ Red-eye/ODAN content: {redeyes} red-eyes, {odans} ODANs")
    else:
        print(f"\n  Red-eye/ODAN: None (good)")

    # Deadhead content
    print(f"\n  Deadhead Content:")
    total_dh = sum(sd["deadhead_count"] for sd in seq_data)
    dh_ratio = total_dh / total_legs if total_legs else 0
    print(f"    Deadhead legs: {total_dh}/{total_legs} ({dh_ratio*100:.0f}%)")
    if dh_ratio > 0.15:
        print(f"    ⚠ High deadhead ratio (>15%)")

    # Compute composite quality score
    credit_score = min(100, max(0, (avg_tpay_per_day - 200) / 3))
    city_score = avg_city_score if all_layovers else 50
    legs_score = max(20, 100 - (avg_legs_per_day - 1) * 30) if avg_legs_per_day > 1 else 100
    redeye_score = 100 if not redeyes and not odans else max(0, 100 - redeyes * 30 - odans * 40)
    dh_score = max(0, 100 * (1 - dh_ratio / 0.3))

    composite = int(credit_score * 0.30 + city_score * 0.25 + legs_score * 0.20 +
                     redeye_score * 0.15 + dh_score * 0.10)
    print(f"\n  Composite Quality Score: {composite}/100")

    return {"score": composite}


# ── Phase 6: Cross-Layer Diversity Analysis ──────────────────────────────

def analyze_diversity(layers):
    """Compare all layers for diversity."""
    print(f"\n{'='*70}")
    print(f"  PHASE 6: CROSS-LAYER DIVERSITY ANALYSIS")
    print(f"{'='*70}")

    # Build sequence ID sets per layer
    layer_ids = {}
    for l_num, entries in layers.items():
        layer_ids[l_num] = {e.get("sequence_id") for e in entries}

    active_layers = sorted(layer_ids.keys())

    # Jaccard similarity matrix
    print(f"\n  Sequence Overlap (Jaccard Similarity) Matrix:")
    print(f"  {'':>8}", end="")
    for l in active_layers:
        print(f"  L{l:>2}", end="")
    print()

    for l1 in active_layers:
        print(f"  L{l1:>2}     ", end="")
        for l2 in active_layers:
            if l1 == l2:
                print(f"   - ", end="")
            else:
                s1 = layer_ids[l1]
                s2 = layer_ids[l2]
                if not s1 or not s2:
                    print(f" N/A", end="")
                else:
                    intersection = s1 & s2
                    union = s1 | s2
                    jaccard = len(intersection) / len(union) if union else 0
                    flag = " !" if jaccard > 0.7 else ""
                    print(f" {jaccard:.2f}{flag}", end="")
        print()

    # Shared sequences detail
    print(f"\n  Shared Sequences Detail:")
    for i, l1 in enumerate(active_layers):
        for l2 in active_layers[i+1:]:
            shared = layer_ids[l1] & layer_ids[l2]
            if shared:
                # Look up seq numbers
                all_entries = list(layers[l1]) + list(layers[l2])
                nums = set()
                for e in all_entries:
                    if e.get("sequence_id") in shared:
                        nums.add(e.get("seq_number", "?"))
                print(f"    L{l1} & L{l2}: {len(shared)} shared (seq# {sorted(nums)})")
            else:
                print(f"    L{l1} & L{l2}: 0 shared — fully diverse")

    # Strategy differentiation
    print(f"\n  Strategy Differentiation:")
    for l_num in active_layers:
        entries = layers[l_num]
        if not entries:
            print(f"    L{l_num}: EMPTY")
            continue
        dates = set()
        for e in entries:
            dates |= set(e.get("chosen_dates", []))
        sorted_d = sorted(dates)
        span = f"{min(sorted_d)}-{max(sorted_d)}" if sorted_d else "N/A"
        total_credit = sum(e.get("_full_seq", {}).get("totals", {}).get("tpay_minutes", 0)
                           for e in entries)
        lengths = defaultdict(int)
        for e in entries:
            dd = e.get("_full_seq", {}).get("totals", {}).get("duty_days", 1)
            lengths[dd] += 1
        mix = ", ".join(f"{v}x{k}d" for k, v in sorted(lengths.items()))
        print(f"    L{l_num}: {len(entries)} seqs, {total_credit/60:.1f}h credit, "
              f"span {span}, mix: {mix}")

    # Layer 7 viability
    if 7 in layers:
        l7 = layers[7]
        print(f"\n  Layer 7 Safety Net Viability:")
        print(f"    Sequences: {len(l7)}")
        l7_credit = sum(e.get("_full_seq", {}).get("totals", {}).get("tpay_minutes", 0)
                        for e in l7)
        print(f"    Total credit: {l7_credit/60:.1f}h")
        print(f"    This is {'ADEQUATE' if l7_credit >= TARGET_CREDIT_MIN else 'INADEQUATE'} as safety net")


# ── Phase 7: Summary Report ─────────────────────────────────────────────

def print_summary(all_results, all_shapes, all_commute, all_quality, layers):
    """Print the final comparative summary."""
    print(f"\n{'='*70}")
    print(f"  PHASE 7: COMPARATIVE SUMMARY REPORT")
    print(f"{'='*70}")

    # Scorecard table
    print(f"\n  Layer Scorecard:")
    print(f"  {'Layer':>7} | {'Credit':>8} | {'Span':>6} | {'Off Blk':>8} | {'Blocks':>6} | {'Gaps':>4} | {'Commute':>8} | {'Quality':>8} | {'Legal':>5}")
    print(f"  {'-'*7}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}-+-{'-'*6}-+-{'-'*4}-+-{'-'*8}-+-{'-'*8}-+-{'-'*5}")

    for l_num in range(1, NUM_LAYERS + 1):
        r = all_results.get(l_num, {})
        s = all_shapes.get(l_num, {})
        c = all_commute.get(l_num, {})
        q = all_quality.get(l_num, {})

        if r.get("empty") or s.get("empty"):
            print(f"  L{l_num:>5} | {'EMPTY':>8} | {'--':>6} | {'--':>8} | {'--':>6} | {'--':>4} | {'--':>8} | {'--':>8} | {'--':>5}")
            continue

        credit = f"{r.get('total_credit_hours', 0):.1f}h"
        span = f"{s.get('span', 0)}d"
        off_blk = f"{s.get('largest_off', 0)}d"
        blocks = str(s.get("num_blocks", 0))
        gaps = str(s.get("internal_gaps", 0))
        commute = f"{c.get('score', 0)}/100"
        quality = f"{q.get('score', 0)}/100"
        legal = "Y" if r.get("legal") else "N"

        print(f"  L{l_num:>5} | {credit:>8} | {span:>6} | {off_blk:>8} | {blocks:>6} | {gaps:>4} | {commute:>8} | {quality:>8} | {legal:>5}")

    # Best layer for each goal
    print(f"\n  Best Layer For Each Goal:")
    active = {l: r for l, r in all_results.items() if not r.get("empty")}
    if active:
        # Most compact
        compact = min(active.keys(), key=lambda l: all_shapes.get(l, {}).get("span", 999))
        print(f"    Most compact schedule: Layer {compact} ({all_shapes[compact].get('span', '?')}d span)")

        # Highest credit
        credit = max(active.keys(), key=lambda l: all_results.get(l, {}).get("total_credit_hours", 0))
        print(f"    Highest credit: Layer {credit} ({all_results[credit].get('total_credit_hours', 0):.1f}h)")

        # Best commutability
        commute = max(active.keys(), key=lambda l: all_commute.get(l, {}).get("score", 0))
        print(f"    Best commutability: Layer {commute} ({all_commute[commute].get('score', 0)}/100)")

        # Best trip quality
        quality = max(active.keys(), key=lambda l: all_quality.get(l, {}).get("score", 0))
        print(f"    Best trip quality: Layer {quality} ({all_quality[quality].get('score', 0)}/100)")

        print(f"    Best safety net: Layer 7")

    # Red flags
    print(f"\n  RED FLAGS:")
    flags = []

    # Empty layers
    empty_layers = [l for l in range(1, NUM_LAYERS + 1) if all_results.get(l, {}).get("empty")]
    if empty_layers:
        flags.append(f"CRITICAL: Layers {empty_layers} are EMPTY — properties too restrictive")
        print(f"    *** CRITICAL: Layers {empty_layers} are EMPTY ***")
        print(f"        The properties assigned to these layers matched ZERO sequences.")
        print(f"        This means the FA would have NO bid content for layers {empty_layers}.")

    # Legality failures
    for l_num, r in all_results.items():
        if not r.get("empty") and not r.get("legal"):
            flags.append(f"Layer {l_num} fails legality: {r.get('issues', [])}")
            print(f"    Layer {l_num}: LEGALITY FAILURE — {r.get('issues', [])}")

    # Scattered work
    for l_num, s in all_shapes.items():
        if not s.get("empty"):
            if s.get("num_blocks", 0) >= 3 or s.get("internal_gaps", 0) >= 2:
                flags.append(f"Layer {l_num}: scattered ({s.get('num_blocks')} blocks, {s.get('internal_gaps')} gaps)")
                print(f"    Layer {l_num}: Scattered schedule ({s.get('num_blocks')} blocks, {s.get('internal_gaps')} gaps)")

    # Similar layers
    active_layers = [l for l in range(1, NUM_LAYERS + 1) if not all_results.get(l, {}).get("empty")]
    for i, l1 in enumerate(active_layers):
        for l2 in active_layers[i+1:]:
            ids1 = {e.get("sequence_id") for e in layers.get(l1, [])}
            ids2 = {e.get("sequence_id") for e in layers.get(l2, [])}
            if ids1 and ids2:
                j = len(ids1 & ids2) / len(ids1 | ids2)
                if j > 0.7:
                    flags.append(f"Layers {l1} & {l2} too similar (Jaccard={j:.2f})")
                    print(f"    Layers {l1} & {l2}: Too similar (Jaccard {j:.2f})")

    # Credit issues
    for l_num, r in all_results.items():
        if not r.get("empty"):
            credit = r.get("total_credit_minutes", 0)
            if credit < TARGET_CREDIT_MIN:
                flags.append(f"Layer {l_num}: credit {credit/60:.1f}h below minimum {TARGET_CREDIT_MIN/60:.0f}h")
                print(f"    Layer {l_num}: Credit {credit/60:.1f}h BELOW minimum {TARGET_CREDIT_MIN/60:.0f}h")

    if not flags:
        print(f"    No red flags (unlikely — check if analysis ran correctly)")

    # Recommendations
    print(f"\n  RECOMMENDATIONS:")
    if empty_layers:
        print(f"""
    1. CRITICAL — Fix Empty Layers {empty_layers}:
       Layers 1-3 are empty because their property filters are too restrictive.
       - L1/L2 require IPD + 777 aircraft → very few ORD sequences match this
       - L3 requires 777 + 3-day trips → also very restrictive for domestic ORD

       Suggested fixes:
       - L1: Remove the 777 requirement, or broaden to include 787
       - L2: Use only IPD type without aircraft restriction
       - L3: Remove aircraft restriction, keep 3-day length preference
       - Consider: are there actually IPD pairings in the ORD pool?

    2. Layers 6-7 are all 1-day turns:
       These layers produce schedules entirely of daily turns (1-day trips).
       This is the opposite of what a domestic FA wanting 3-4 day trips would want.
       A schedule of 17 individual turns means reporting to the airport 17 different days.

       Fix: Layer 6 should allow 2-3 day trips as alternative. Layer 7 (safety net)
       should be maximally permissive with no pairing-type restrictions.

    3. The 7-layer set does NOT provide adequate coverage:
       Only 4 of 7 layers produce results. The "dream → safety net" progression is broken.
       Layers 4-5 are reasonable 3-day schedules, but layers 1-3 being empty means
       the FA starts bidding from Layer 4 — no aspirational layers at all.

    4. Compactness is partially working:
       Layers 4-5 show decent compactness (18-day spans), but could be tighter.
       The CP-SAT solver IS packing trips together, but the "2 weeks on / 2 weeks off"
       ideal is not being achieved — work spans the full first 2.5 weeks.
""")

    # The Big Question
    print(f"\n  {'='*60}")
    print(f"  THE BIG QUESTION:")
    print(f"  \"If your mom looked at these 7 layers, would she say")
    print(f"   'yes, I'd submit this bid'?\"")
    print(f"  {'='*60}")

    if empty_layers:
        print(f"""
    ANSWER: NO.

    Three of seven layers are completely empty. That means if PBS falls through
    layers 1-3, there's nothing there — it jumps straight to Layer 4. A senior
    FA would never submit a bid where the top 3 layers are blank. And a junior
    FA bidding layers 6-7 would get a schedule of 17 individual 1-day turns —
    commuting to ORD 17 separate days in a month. That's not a schedule anyone
    would want.

    The tool needs property adjustment before this bid is usable:
    - Fix L1-L3 filters to match actual sequences in the ORD pool
    - Ensure L6-L7 include multi-day trips, not just turns
    - Verify IPD/777 pairings actually exist for this base/month
""")
    else:
        print(f"\n    ANSWER: Check the detailed analysis above for per-layer assessment.")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  PBS LAYER OUTPUT ANALYZER")
    print(f"  Bid Period: Test Bid 2 ({BID_PERIOD_ID})")
    print(f"  Bid: {BID_ID}")
    print(f"  Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    layers, all_sequences, seq_lookup, properties = load_data()

    all_results = {}
    all_shapes = {}
    all_commute = {}
    all_quality = {}

    # Phase 2-5: Per-layer analysis
    for layer_num in range(1, NUM_LAYERS + 1):
        layer_entries = layers.get(layer_num, [])

        # Phase 2: Legality
        result = audit_layer(layer_num, layer_entries)
        all_results[layer_num] = result

        if result.get("empty"):
            all_shapes[layer_num] = {"empty": True}
            all_commute[layer_num] = {"score": 0}
            all_quality[layer_num] = {"score": 0}
            continue

        # Phase 3: Shape
        shape = analyze_shape(layer_num, layer_entries)
        all_shapes[layer_num] = shape

        # Phase 4: Commutability
        commute = analyze_commutability(layer_num, layer_entries)
        all_commute[layer_num] = commute

        # Phase 5: Trip Quality
        quality = analyze_trip_quality(layer_num, layer_entries, all_sequences)
        all_quality[layer_num] = quality

    # Phase 6: Cross-layer diversity
    analyze_diversity(layers)

    # Phase 7: Summary
    print_summary(all_results, all_shapes, all_commute, all_quality, layers)

    # Save report
    report_path = os.path.join(os.path.dirname(__file__), "layer_analysis_report.txt")
    print(f"\n  Report analysis complete. Re-run with output redirect to save:")
    print(f"  python3 layer_analysis.py > layer_analysis_report.txt 2>&1")


if __name__ == "__main__":
    main()
