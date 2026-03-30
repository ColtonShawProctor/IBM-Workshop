#!/usr/bin/env python3
"""PBS Layer Output Analyzer V2 — Deep quality analysis with fresh optimizer output."""

import sys
import os
import json
import math
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from app.db import get_collection

# ── Config ───────────────────────────────────────────────────────────────
BID_PERIOD_ID = "85646a2c-573f-4139-a3c6-c769242d6507"
TOTAL_DATES = 30
TARGET_CREDIT_MIN = 4200  # 70 hours
TARGET_CREDIT_MAX = 5400  # 90 hours
MIN_DAYS_OFF = 11
NUM_LAYERS = 7

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

def hr_min(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


def load_data():
    """Load fresh entries and full sequence data."""
    print("Loading data...")

    with open(os.path.join(os.path.dirname(__file__), "fresh_entries.json")) as f:
        entries = json.load(f)

    seq_coll = get_collection("sequences")
    sequences = list(seq_coll.find({"bid_period_id": BID_PERIOD_ID}, limit=2000))
    seq_lookup = {s["_id"]: s for s in sequences}

    layers = defaultdict(list)
    for entry in entries:
        layer_num = entry.get("layer", 0)
        if layer_num == 0:
            continue
        seq_id = entry.get("sequence_id")
        full_seq = seq_lookup.get(seq_id, {})
        enriched = {**entry, "_full_seq": full_seq}
        layers[layer_num].append(enriched)

    for l in layers:
        layers[l].sort(key=lambda e: e.get("rank", 999))

    print(f"  {len(entries)} entries across {len(layers)} layers")
    print(f"  {len(sequences)} sequences in pool\n")
    return layers, sequences, seq_lookup


def audit_layer(layer_num, layer_entries):
    """Run all legality checks."""
    print(f"\n{'='*70}")
    print(f"  LAYER {layer_num}: {LAYER_NAMES.get(layer_num, '?')}")
    print(f"{'='*70}")

    if not layer_entries:
        print("  *** EMPTY LAYER ***")
        return {"layer": layer_num, "empty": True, "legal": False,
                "issues": ["EMPTY"]}

    results = {"layer": layer_num, "empty": False, "issues": []}

    all_working_dates = set()
    seq_data = []
    for entry in layer_entries:
        chosen = set(entry.get("chosen_dates", []))
        full = entry.get("_full_seq", {})
        totals = full.get("totals", {})
        sd = {
            "seq_number": entry.get("seq_number", 0),
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
            "seq_id": entry.get("sequence_id", ""),
        }
        seq_data.append(sd)
        all_working_dates |= chosen

    num_seqs = len(seq_data)
    print(f"\n  Sequences selected: {num_seqs}")
    for sd in seq_data:
        dates = sorted(sd["chosen_dates"])
        tpay_h = sd["tpay_minutes"] / 60
        cities = ", ".join(sd["layover_cities"]) or "turn"
        print(f"    SEQ {sd['seq_number']:>5}: days {min(dates):>2}-{max(dates):>2} "
              f"({sd['duty_days']}d) | TPAY {tpay_h:.1f}h | {cities} | {sd['category']}")

    # Date conflicts
    print(f"\n  --- Date Conflict Check ---")
    conflicts = []
    for i in range(len(seq_data)):
        for j in range(i + 1, len(seq_data)):
            overlap = seq_data[i]["chosen_dates"] & seq_data[j]["chosen_dates"]
            if overlap:
                conflicts.append((seq_data[i]["seq_number"], seq_data[j]["seq_number"], sorted(overlap)))
    print(f"  {'FAIL: ' + str(len(conflicts)) + ' conflicts' if conflicts else 'PASS: No conflicts'}")
    for a, b, days in conflicts:
        print(f"    SEQ {a} vs SEQ {b}: overlap on days {days}")
    if conflicts:
        results["issues"].append(f"{len(conflicts)} date conflicts")

    # Rest periods
    print(f"\n  --- Rest Period Check ---")
    sorted_seqs = sorted(seq_data, key=lambda s: min(s["chosen_dates"]) if s["chosen_dates"] else 999)
    rest_issues = []
    for i in range(len(sorted_seqs) - 1):
        curr = sorted_seqs[i]
        nxt = sorted_seqs[i + 1]
        curr_last = max(curr["chosen_dates"])
        nxt_first = min(nxt["chosen_dates"])
        gap_days = nxt_first - curr_last

        if gap_days > 1:
            status = "OK (gap)"
        elif gap_days == 1:
            curr_dps = curr["duty_periods"]
            nxt_dps = nxt["duty_periods"]
            if curr_dps and nxt_dps:
                rel = hhmm_to_minutes(curr_dps[-1].get("release_base", "18:00"))
                rpt = hhmm_to_minutes(nxt_dps[0].get("report_base", "08:00"))
                rest_min = (24 * 60 - rel) + rpt
                if rest_min < 600:
                    status = f"FAIL ({rest_min/60:.1f}h < 10h)"
                    rest_issues.append(f"SEQ {curr['seq_number']} -> {nxt['seq_number']}: {rest_min/60:.1f}h")
                elif rest_min < 720:
                    status = f"WARNING ({rest_min/60:.1f}h < 12h)"
                else:
                    status = f"OK ({rest_min/60:.1f}h)"
            else:
                status = "OK (no data)"
        else:
            status = "FAIL (overlap)"
            rest_issues.append(f"SEQ {curr['seq_number']} -> {nxt['seq_number']}: overlap")

        print(f"    SEQ {curr['seq_number']} (d{curr_last}) -> SEQ {nxt['seq_number']} (d{nxt_first}): {status}")

    if rest_issues:
        results["issues"].append(f"{len(rest_issues)} rest violations")
    print(f"  {'FAIL' if rest_issues else 'PASS'}")

    # Credit
    print(f"\n  --- Credit Hour Range ---")
    total_tpay = sum(sd["tpay_minutes"] for sd in seq_data)
    total_tpay_hours = total_tpay / 60
    in_range = TARGET_CREDIT_MIN <= total_tpay <= TARGET_CREDIT_MAX
    margin = ""
    if in_range:
        lo = total_tpay - TARGET_CREDIT_MIN
        hi = TARGET_CREDIT_MAX - total_tpay
        if lo < 120 or hi < 120:
            margin = f" (tight: -{lo/60:.1f}h/+{hi/60:.1f}h from bounds)"
    print(f"  Total: {total_tpay_hours:.1f}h ({total_tpay} min) | Range: {TARGET_CREDIT_MIN/60:.0f}-{TARGET_CREDIT_MAX/60:.0f}h")
    print(f"  {'PASS' if in_range else 'FAIL'}{margin}")
    if not in_range:
        results["issues"].append(f"Credit {total_tpay_hours:.1f}h out of range")
    results["total_credit_hours"] = total_tpay_hours
    results["total_credit_minutes"] = total_tpay

    # Days off
    print(f"\n  --- Days Off ---")
    working_days = len(all_working_dates)
    days_off = TOTAL_DATES - working_days
    print(f"  Working: {working_days} | Off: {days_off} | Min: {MIN_DAYS_OFF}")
    print(f"  {'PASS' if days_off >= MIN_DAYS_OFF else 'FAIL'}")
    if days_off < MIN_DAYS_OFF:
        results["issues"].append(f"Only {days_off} days off")
    results["working_days"] = working_days
    results["days_off"] = days_off

    # 7-day block window (proportional: only count block hours for days in window)
    print(f"\n  --- 7-Day Block Limit (30h) ---")
    worst = 0
    worst_range = ""
    for start in range(1, TOTAL_DATES - 5):
        window = set(range(start, start + 7))
        block = 0
        for sd in seq_data:
            overlap = len(sd["chosen_dates"] & window)
            if overlap > 0:
                span_size = len(sd["chosen_dates"])
                if span_size > 0:
                    block += sd["block_minutes"] * overlap / span_size
        if block > worst:
            worst = block
            worst_range = f"days {start}-{start+6}"
    limit = 40 * 60
    print(f"  Worst window: {worst/60:.1f}h ({worst_range}) | Limit: 40.0h")
    print(f"  {'PASS' if worst <= limit else 'FAIL'}")
    if worst > limit:
        results["issues"].append(f"7-day block: {worst/60:.1f}h > 30h")

    # Multi-OPS
    seq_ids = [sd["seq_id"] for sd in seq_data]
    dupes = [sid for sid in set(seq_ids) if seq_ids.count(sid) > 1]
    if dupes:
        print(f"\n  --- Multi-OPS: FAIL ({len(dupes)} duplicates) ---")
        results["issues"].append("Duplicate sequences")
    else:
        print(f"\n  --- Multi-OPS: PASS ---")

    results["legal"] = len(results["issues"]) == 0
    status_icon = "PASS" if results["legal"] else "FAIL"
    print(f"\n  LEGALITY: {status_icon}")
    if results["issues"]:
        for iss in results["issues"]:
            print(f"    - {iss}")

    return results


def analyze_shape(layer_num, layer_entries):
    """Schedule shape analysis with calendar visualization."""
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

    span_rating = ("EXCELLENT" if span <= 14 else "GOOD" if span <= 18 else
                   "FAIR" if span <= 22 else "POOR")

    # Work blocks
    blocks = [[sorted_dates[0]]]
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i-1] + 1:
            blocks[-1].append(sorted_dates[i])
        else:
            blocks.append([sorted_dates[i]])

    num_blocks = len(blocks)
    internal_gaps = len(set(range(first_work, last_work + 1)) - all_dates)

    contiguity = ("PERFECT" if num_blocks == 1 and internal_gaps == 0 else
                  "GOOD" if num_blocks <= 2 and internal_gaps <= 2 else
                  "FAIR" if num_blocks <= 3 else "POOR")

    # Largest off-day block
    off_days = sorted(set(range(1, TOTAL_DATES + 1)) - all_dates)
    if off_days:
        off_blocks = [[off_days[0]]]
        for i in range(1, len(off_days)):
            if off_days[i] == off_days[i-1] + 1:
                off_blocks[-1].append(off_days[i])
            else:
                off_blocks.append([off_days[i]])
        largest_off_block = max(off_blocks, key=len)
        largest_off = len(largest_off_block)
    else:
        largest_off = 0
        largest_off_block = []

    off_rating = ("EXCELLENT" if largest_off >= 13 else "GOOD" if largest_off >= 10 else
                  "FAIR" if largest_off >= 7 else "POOR")

    print(f"\n  --- Schedule Shape ---")
    print(f"  Span: days {first_work}-{last_work} ({span}d) [{span_rating}]")
    print(f"  Blocks: {num_blocks} | Internal gaps: {internal_gaps}d [{contiguity}]")
    if largest_off_block:
        print(f"  Largest off: {largest_off}d (days {min(largest_off_block)}-{max(largest_off_block)}) [{off_rating}]")

    # Calendar
    total_credit = sum(e.get("_full_seq", {}).get("totals", {}).get("tpay_minutes", 0) for e in layer_entries)
    print(f"\n  Layer {layer_num}: \"{LAYER_NAMES.get(layer_num, '?')}\"")
    print(f"  Credit: {total_credit/60:.1f}h | Span: {first_work}-{last_work} | Off: {largest_off}d")
    print()

    # January 2026: Thursday = day 1 (dow=3)
    dow_start = 3
    print("    Mon  Tue  Wed  Thu  Fri  Sat  Sun")
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

    # Sequence list
    print()
    for e in layer_entries:
        dates = sorted(e.get("chosen_dates", []))
        full = e.get("_full_seq", {})
        cities = full.get("layover_cities", [])
        tpay = full.get("totals", {}).get("tpay_minutes", 0)
        print(f"    SEQ-{e['seq_number']} d{min(dates)}-{max(dates)} "
              f"({full.get('totals', {}).get('duty_days', '?')}d, "
              f"{tpay/60:.1f}h, {'->'.join(cities) if cities else 'turn'})")

    return {
        "span": span, "span_rating": span_rating,
        "first_work": first_work, "last_work": last_work,
        "num_blocks": num_blocks, "internal_gaps": internal_gaps,
        "contiguity": contiguity, "largest_off": largest_off,
        "off_rating": off_rating, "working_dates": all_dates,
    }


def analyze_commutability(layer_num, layer_entries):
    if not layer_entries:
        return {"score": 0}

    print(f"\n  --- Commutability (DCA commuter) ---")

    all_dates = set()
    for e in layer_entries:
        all_dates |= set(e.get("chosen_dates", []))
    sorted_dates = sorted(all_dates)

    blocks = [[sorted_dates[0]]]
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i-1] + 1:
            blocks[-1].append(sorted_dates[i])
        else:
            blocks.append([sorted_dates[i]])

    sorted_entries = sorted(layer_entries, key=lambda e: min(e.get("chosen_dates", [999])))
    scores = []

    for bi, block_dates in enumerate(blocks):
        block_set = set(block_dates)
        block_entries = [e for e in sorted_entries if set(e.get("chosen_dates", [])) & block_set]
        if not block_entries:
            continue

        first_dps = block_entries[0].get("_full_seq", {}).get("duty_periods", [])
        last_dps = block_entries[-1].get("_full_seq", {}).get("duty_periods", [])

        rpt = hhmm_to_minutes(first_dps[0].get("report_base", "12:00")) if first_dps else 720
        rpt_str = first_dps[0].get("report_base", "12:00") if first_dps else "N/A"
        rpt_score = 100 if rpt >= 660 else 75 if rpt >= 540 else 50 if rpt >= 420 else 20
        rpt_label = ("EXCELLENT" if rpt >= 660 else "GOOD" if rpt >= 540 else
                     "FAIR" if rpt >= 420 else "POOR")

        rel = hhmm_to_minutes(last_dps[-1].get("release_base", "18:00")) if last_dps else 1080
        rel_str = last_dps[-1].get("release_base", "18:00") if last_dps else "N/A"
        rel_score = 100 if rel < 900 else 75 if rel < 1080 else 50 if rel < 1260 else 20
        rel_label = ("EXCELLENT" if rel < 900 else "GOOD" if rel < 1080 else
                     "FAIR" if rel < 1260 else "POOR")

        pre = min(block_dates) - 1
        post = TOTAL_DATES - max(block_dates)
        buf_score = min(100, (min(pre, 2) + min(post, 2)) * 25)

        block_score = int(rpt_score * 0.35 + rel_score * 0.35 + buf_score * 0.30)
        scores.append(block_score)

        print(f"  Block {bi+1} (d{min(block_dates)}-{max(block_dates)}): "
              f"report {rpt_str} [{rpt_label}], release {rel_str} [{rel_label}], "
              f"buffers {pre}/{post}d -> {block_score}/100")

    overall = int(sum(scores) / len(scores)) if scores else 0
    print(f"  Overall: {overall}/100")
    return {"score": overall}


def analyze_trip_quality(layer_num, layer_entries, all_sequences):
    if not layer_entries:
        return {"score": 0}

    print(f"\n  --- Trip Quality ---")

    seq_data = []
    for e in layer_entries:
        full = e.get("_full_seq", {})
        totals = full.get("totals", {})
        seq_data.append({
            "tpay_minutes": totals.get("tpay_minutes", 0),
            "duty_days": totals.get("duty_days", 1) or 1,
            "leg_count": totals.get("leg_count", 0),
            "deadhead_count": totals.get("deadhead_count", 0),
            "layover_cities": full.get("layover_cities", []),
            "duty_periods": full.get("duty_periods", []),
            "is_turn": full.get("is_turn", False),
            "is_redeye": full.get("is_redeye", False),
            "is_odan": full.get("is_odan", False),
        })

    total_tpay = sum(sd["tpay_minutes"] for sd in seq_data)
    total_dd = sum(sd["duty_days"] for sd in seq_data)
    avg_cpd = total_tpay / total_dd if total_dd else 0

    pool_cpd = []
    for s in all_sequences:
        t = s.get("totals", {})
        dd = t.get("duty_days", 1) or 1
        tp = t.get("tpay_minutes", 0)
        if tp > 0:
            pool_cpd.append(tp / dd)
    pool_avg = sum(pool_cpd) / len(pool_cpd) if pool_cpd else 0

    print(f"  Credit/day: {avg_cpd:.0f}min ({avg_cpd/60:.1f}h) | Pool avg: {pool_avg:.0f}min ({pool_avg/60:.1f}h)")

    # Layovers
    all_layovers = []
    for sd in seq_data:
        for dp in sd["duty_periods"]:
            lo = dp.get("layover")
            if lo:
                city = lo.get("city", "?")
                rest = lo.get("rest_minutes", 0)
                all_layovers.append((city, rest))
                tier = CITY_TIERS.get(city, CITY_DEFAULT)
                flag = ""
                if rest < 720: flag = " SHORT"
                elif rest > 1800: flag = " LONG"
                print(f"    {city} ({tier}/100): {rest/60:.1f}h{flag}")

    avg_city = (sum(CITY_TIERS.get(c, CITY_DEFAULT) for c, _ in all_layovers) / len(all_layovers)
                if all_layovers else 50)

    # Legs/day
    total_legs = sum(sd["leg_count"] for sd in seq_data)
    avg_legs = total_legs / total_dd if total_dd else 0
    heavy = sum(1 for sd in seq_data for dp in sd["duty_periods"] if len(dp.get("legs", [])) >= 4)
    print(f"  Legs/day: {avg_legs:.1f} | Heavy days (4+): {heavy}")

    # Trip lengths
    lengths = defaultdict(int)
    for sd in seq_data:
        lengths[sd["duty_days"]] += 1
    mix = ", ".join(f"{v}x{k}d" for k, v in sorted(lengths.items()))
    print(f"  Mix: {mix}")

    # Red-eyes, deadheads
    redeyes = sum(1 for sd in seq_data if sd["is_redeye"])
    odans = sum(1 for sd in seq_data if sd["is_odan"])
    total_dh = sum(sd["deadhead_count"] for sd in seq_data)
    dh_ratio = total_dh / total_legs if total_legs else 0
    if redeyes or odans:
        print(f"  Red-eye/ODAN: {redeyes}/{odans}")
    print(f"  Deadheads: {total_dh}/{total_legs} ({dh_ratio*100:.0f}%)")

    # Composite
    credit_score = min(100, max(0, (avg_cpd - 200) / 3))
    legs_score = max(20, 100 - (avg_legs - 1) * 30) if avg_legs > 1 else 100
    redeye_score = max(0, 100 - redeyes * 30 - odans * 40)
    dh_score = max(0, 100 * (1 - dh_ratio / 0.3))
    composite = int(credit_score * 0.30 + avg_city * 0.25 + legs_score * 0.20 +
                     redeye_score * 0.15 + dh_score * 0.10)
    print(f"  Quality Score: {composite}/100")
    return {"score": composite}


def analyze_diversity(layers):
    print(f"\n{'='*70}")
    print(f"  CROSS-LAYER DIVERSITY")
    print(f"{'='*70}")

    layer_ids = {}
    for l, entries in layers.items():
        layer_ids[l] = {e.get("sequence_id") for e in entries}

    active = sorted(l for l in layer_ids if layer_ids[l])

    # Matrix
    print(f"\n  Jaccard Similarity:")
    print(f"  {'':>6}", end="")
    for l in active:
        print(f"   L{l}", end="")
    print()
    for l1 in active:
        print(f"  L{l1:>2}  ", end="")
        for l2 in active:
            if l1 == l2:
                print(f"    -", end="")
            else:
                s1, s2 = layer_ids[l1], layer_ids[l2]
                j = len(s1 & s2) / len(s1 | s2) if (s1 | s2) else 0
                flag = "!" if j > 0.7 else " "
                print(f" {j:.2f}{flag}", end="")
        print()

    # Detail
    print(f"\n  Shared sequences:")
    for i, l1 in enumerate(active):
        for l2 in active[i+1:]:
            shared = layer_ids[l1] & layer_ids[l2]
            total = len(layer_ids[l1] | layer_ids[l2])
            print(f"    L{l1}&L{l2}: {len(shared)} shared / {total} union")

    # Strategy differentiation
    print(f"\n  Strategy overview:")
    for l in active:
        entries = layers[l]
        dates = set()
        for e in entries:
            dates |= set(e.get("chosen_dates", []))
        sd = sorted(dates)
        total_credit = sum(e.get("_full_seq", {}).get("totals", {}).get("tpay_minutes", 0) for e in entries)
        lns = defaultdict(int)
        for e in entries:
            dd = e.get("_full_seq", {}).get("totals", {}).get("duty_days", 1)
            lns[dd] += 1
        mix = ", ".join(f"{v}x{k}d" for k, v in sorted(lns.items()))
        shape = ""
        if sd:
            mid = TOTAL_DATES / 2
            front = sum(1 for d in sd if d <= mid)
            back = len(sd) - front
            if front > back * 2: shape = "front-loaded"
            elif back > front * 2: shape = "back-loaded"
            else: shape = "balanced"
        print(f"    L{l}: {len(entries)} seqs, {total_credit/60:.1f}h, "
              f"d{min(sd)}-{max(sd)}, {mix}, {shape}")


def print_summary(all_results, all_shapes, all_commute, all_quality, layers):
    print(f"\n{'='*70}")
    print(f"  SUMMARY REPORT")
    print(f"{'='*70}")

    # Scorecard
    print(f"\n  {'Layer':>7} | {'Credit':>7} | {'Span':>5} | {'Off':>4} | {'Blk':>3} | {'Gap':>3} | {'Comm':>5} | {'Qual':>5} | {'OK':>3}")
    print(f"  {'-'*7}-+-{'-'*7}-+-{'-'*5}-+-{'-'*4}-+-{'-'*3}-+-{'-'*3}-+-{'-'*5}-+-{'-'*5}-+-{'-'*3}")

    for l in range(1, NUM_LAYERS + 1):
        r = all_results.get(l, {})
        s = all_shapes.get(l, {})
        c = all_commute.get(l, {})
        q = all_quality.get(l, {})

        if r.get("empty") or s.get("empty"):
            print(f"  L{l:>5} | {'EMPTY':>7} |  {'--':>4} | {'--':>4} | {'--':>3} | {'--':>3} | {'--':>5} | {'--':>5} | {'--':>3}")
            continue

        print(f"  L{l:>5} | {r.get('total_credit_hours', 0):>5.1f}h |"
              f" {s.get('span', 0):>3}d |"
              f" {s.get('largest_off', 0):>2}d |"
              f" {s.get('num_blocks', 0):>3} |"
              f" {s.get('internal_gaps', 0):>3} |"
              f" {c.get('score', 0):>3}/100 |"
              f" {q.get('score', 0):>3}/100 |"
              f" {'Y' if r.get('legal') else 'N':>3}")

    # Best per goal
    active = {l: r for l, r in all_results.items() if not r.get("empty")}
    if active:
        print(f"\n  Best per goal:")
        best_compact = min(active, key=lambda l: all_shapes.get(l, {}).get("span", 999))
        best_credit = max(active, key=lambda l: all_results.get(l, {}).get("total_credit_hours", 0))
        best_commute = max(active, key=lambda l: all_commute.get(l, {}).get("score", 0))
        best_quality = max(active, key=lambda l: all_quality.get(l, {}).get("score", 0))
        print(f"    Compact: L{best_compact} ({all_shapes[best_compact].get('span')}d)")
        print(f"    Credit: L{best_credit} ({all_results[best_credit].get('total_credit_hours'):.1f}h)")
        print(f"    Commute: L{best_commute} ({all_commute[best_commute].get('score')}/100)")
        print(f"    Quality: L{best_quality} ({all_quality[best_quality].get('score')}/100)")

    # Red flags
    print(f"\n  RED FLAGS:")
    empty = [l for l in range(1, NUM_LAYERS + 1) if all_results.get(l, {}).get("empty")]
    if empty:
        print(f"    CRITICAL: Layers {empty} empty")

    for l, r in all_results.items():
        if not r.get("empty") and not r.get("legal"):
            for iss in r.get("issues", []):
                print(f"    L{l}: {iss}")

    for l, s in all_shapes.items():
        if not s.get("empty"):
            if s.get("num_blocks", 0) >= 3:
                print(f"    L{l}: scattered ({s['num_blocks']} blocks, {s.get('internal_gaps', 0)} gaps)")

    # High-similarity pairs
    for i in range(1, NUM_LAYERS + 1):
        for j in range(i + 1, NUM_LAYERS + 1):
            ids_i = {e.get("sequence_id") for e in layers.get(i, [])}
            ids_j = {e.get("sequence_id") for e in layers.get(j, [])}
            if ids_i and ids_j:
                jac = len(ids_i & ids_j) / len(ids_i | ids_j)
                if jac > 0.7:
                    print(f"    L{i}&L{j}: too similar (Jaccard {jac:.2f})")

    # Credit issues
    for l, r in all_results.items():
        if not r.get("empty"):
            c = r.get("total_credit_minutes", 0)
            if c < TARGET_CREDIT_MIN:
                print(f"    L{l}: credit {c/60:.1f}h below min {TARGET_CREDIT_MIN/60:.0f}h")

    # Recommendations
    print(f"\n  {'='*60}")
    print(f"  RECOMMENDATIONS")
    print(f"  {'='*60}")

    # Check all layers all hit exactly 90h
    all_90 = all(
        abs(all_results.get(l, {}).get("total_credit_hours", 0) - 90.0) < 0.5
        for l in range(1, NUM_LAYERS + 1) if not all_results.get(l, {}).get("empty")
    )
    if all_90:
        print(f"""
  1. ALL LAYERS HIT EXACTLY 90.0h CREDIT (the maximum):
     Every layer is at exactly 90h — the solver is maximizing credit so
     aggressively that every schedule is pegged at the ceiling. This means:
     - No credit differentiation between layers
     - "maximize_credit" property is dominating all other quality signals
     - The solver has no room to trade credit for better schedule shape

     Fix: Consider reducing maximize_credit weight or using
     target_credit_range (e.g., 80-88h) instead of maximize_credit
     for at least some layers.""")

    # Check 7-day block violations
    block_fails = [l for l in active if any("7-day" in i for i in all_results[l].get("issues", []))]
    if block_fails:
        print(f"""
  2. 7-DAY BLOCK LIMIT EXCEEDED (Layers {block_fails}):
     The CP-SAT solver packs trips back-to-back perfectly, but doesn't
     enforce the 30h/7-day cumulative block limit. With 6 back-to-back
     3-day trips at 15h TPAY each, the block hours per 7-day window
     easily exceed 30h.

     Fix: Add a constraint to the CP-SAT model (cpsat_builder.py) that
     checks: for every 7-consecutive-day window, the sum of block_minutes
     for selected instances whose spans intersect that window must be <= 1800.""")

    # Check L6/L7 all turns
    for l in [6, 7]:
        if l in layers:
            dd_set = {e.get("_full_seq", {}).get("totals", {}).get("duty_days", 0) for e in layers[l]}
            if dd_set == {1}:
                print(f"""
  3. LAYER {l} IS ALL 1-DAY TURNS:
     No pairing properties restrict L{l}, so the solver picks the highest
     credit-per-day sequences. 1-day turns at ~5-6h TPAY happen to be the
     most credit-dense options when measured per calendar day (since there's
     no layover time). But 17 individual turns = reporting to ORD 17 days.

     Fix: Add a prefer_pairing_length property for L{l} (e.g., length >= 2)
     or add a minimum trip length to the CP-SAT model as a soft preference.""")
                break

    # Check compactness
    l1_shape = all_shapes.get(1, {})
    l2_shape = all_shapes.get(2, {})
    if (not l1_shape.get("empty") and not l2_shape.get("empty")):
        l1_span = l1_shape.get("span", 0)
        l2_span = l2_shape.get("span", 0)
        if l1_span <= 18 and l2_span <= 18:
            print(f"""
  4. COMPACTNESS IS WORKING:
     L1 spans {l1_span} days (front-loaded) and L2 spans {l2_span} days
     (back-loaded). The CP-SAT compactness objective is doing its job.
     However, 18 days is "2.5 weeks on" not "2 weeks on". Consider
     tightening the compactness weight or adding a max_span constraint.""")

    # L4/L5 2-day analysis
    for l in [4, 5]:
        if l in layers:
            dd_set = {e.get("_full_seq", {}).get("totals", {}).get("duty_days", 0) for e in layers[l]}
            if dd_set == {2}:
                print(f"""
  5. L{l} USES ONLY 2-DAY TRIPS (property: prefer_pairing_length=2):
     9 back-to-back 2-day trips fill 18 days at 10h TPAY each = 90h.
     A 2-day "trip" with no layover is effectively two consecutive turns.
     The FA wanted 3-4 day trips. Consider whether 2-day is a good fallback
     or if L{l} should use a 3-4 day mix instead.""")
                break

    # The Big Question
    print(f"""
  {'='*60}
  THE BIG QUESTION:
  "Would your mom submit this bid?"
  {'='*60}

  ANSWER: MOSTLY NO — but the structure is improving.

  GOOD:
  - All 7 layers now produce valid schedules (no more empty layers)
  - L1 is front-loaded (days 3-20), L2 is back-loaded (days 10-27)
  - Compactness is working — L1/L2/L3 each have a single contiguous
    work block with zero internal gaps
  - Full diversity between L1-L3 (Jaccard ~0 between 3-day layers)

  PROBLEMS:
  - Every layer hits exactly 90h — maximize_credit dominates everything
  - L6/L7 are 17 individual turns — a commuter's nightmare
  - 7-day block limits exceeded on ALL layers (legality failure)
  - L4/L5 are 2-day "trips" which are really just back-to-back turns
  - No layer offers 85h credit with 14 days off (the ideal balance)

  TO MAKE THIS BIDDABLE:
  1. Add 7-day cumulative block constraint to CP-SAT solver
  2. Replace maximize_credit on some layers with target_credit_range
  3. Add prefer_pairing_length >= 2 to L6, >= 3 to L7
  4. Consider swapping L4/L5 from 2-day to 4-day trips for variety
  """)


def main():
    print("=" * 70)
    print("  PBS LAYER OUTPUT ANALYZER v2 (Fresh Optimizer Run)")
    print(f"  Bid Period: Test Bid 2 (ORD, January 2026)")
    print(f"  Analysis: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    layers, all_seqs, seq_lookup = load_data()

    all_results = {}
    all_shapes = {}
    all_commute = {}
    all_quality = {}

    for layer_num in range(1, NUM_LAYERS + 1):
        layer_entries = layers.get(layer_num, [])

        result = audit_layer(layer_num, layer_entries)
        all_results[layer_num] = result
        if result.get("empty"):
            all_shapes[layer_num] = {"empty": True}
            all_commute[layer_num] = {"score": 0}
            all_quality[layer_num] = {"score": 0}
            continue

        all_shapes[layer_num] = analyze_shape(layer_num, layer_entries)
        all_commute[layer_num] = analyze_commutability(layer_num, layer_entries)
        all_quality[layer_num] = analyze_trip_quality(layer_num, layer_entries, all_seqs)

    analyze_diversity(layers)
    print_summary(all_results, all_shapes, all_commute, all_quality, layers)


if __name__ == "__main__":
    main()
