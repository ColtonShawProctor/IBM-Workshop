"""Transparent decision reasoning for PBS optimization.

Generates human-readable explanations for every optimizer decision:
  - Per-pairing rationale (why this trip was picked)
  - Per-layer narrative (strategy and expectations)
  - PBS property translation (what to enter at fapbs.aa.com)
  - "Why Not" explainer (why an expected trip wasn't picked)
  - Holdability report card (seniority overview)
  - Contextual teaching tips
  - Calendar grid visualization
"""

from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.services.holdability import (
    PREMIUM_INTL,
    PREMIUM_DOMESTIC,
    holdability_category,
)
from app.services.cpsat_builder import CITY_TIERS, _CITY_DEFAULT

logger = logging.getLogger(__name__)


# ── Contextual Tips ─────────────────────────────────────────────────────

CONTEXTUAL_TIPS: dict[str, str] = {
    "progressive_relaxation": (
        "PBS Rule: Each layer must be EQUAL TO or LESS restrictive than "
        "the one above it. If Layer 1 allows 3-day trips, Layer 2 can't limit to "
        "4-day only -- it can ADD 4-day but can't REMOVE 3-day. This is why the "
        "optimizer widens the pool as layers increase."
    ),
    "all_pairings_equal": (
        "PBS Rule: Within a layer, ALL pairings are equally desirable to PBS. "
        "PBS sees no difference between the first and last trip in your pool. "
        "If you want PBS to prefer certain trips, put them in a HIGHER layer."
    ),
    "layer_none": (
        "Layer None means PBS couldn't build a legal schedule from ANY of your "
        "7 layers. You get company-assigned random flying -- the worst outcome. "
        "That's why Layer 7 should be extremely broad."
    ),
    "shuffling": (
        "PBS can 'shuffle' -- if it awards a trip from Layer 1 but then can't "
        "find other trips to complete a legal line, it removes that trip and tries "
        "different combinations. What you 'won' in Layer 1 can still change."
    ),
    "double_up": (
        "Double-up: Two trips can chain with only a 30-minute gap at base "
        "(CBA Section 2.N). This means you can finish a 3-day trip at 14:00 and "
        "start another at 14:30 -- no overnight rest needed between them."
    ),
    "waive_rest": (
        "Home base rest between trips (normally ~11h) can be waived down to "
        "the FAR minimum of 10 hours (CBA Section 11.I). This lets trips chain "
        "tighter -- one more hour of flexibility per transition."
    ),
    "view_pairing_set": (
        "Always use 'View Pairing Set' in PBS to verify your layer has enough "
        "pairings. If the pool is too small, PBS can't build a legal line and "
        "you'll fall to the next layer (or worse, Layer None)."
    ),
    "cn_dates": (
        "Coverage Needed (CN) days are when not enough FAs bid to fly. "
        "If you're junior, PBS may assign you to a CN date even if you didn't "
        "bid for it. Check APFA's monthly CN report to plan around them."
    ),
    "block_limit": (
        "The 30-hour block limit means total flight time in any rolling 7-day "
        "window can't exceed 30 hours. You can waive this to 35 hours in PBS "
        "(CBA Section 11.B) -- but only do it if you need the extra flexibility."
    ),
    "credit_vs_block": (
        "Credit (TPAY) and block time are different. Credit includes duty rigs "
        "and trip rigs -- you often earn more credit than actual flying time. "
        "The 30h block limit counts only actual flight hours, not credit."
    ),
}


def select_tips(
    layer_num: int,
    pool_size: int,
    has_double_up: bool,
    has_waiver: bool,
    seen_tips: set[str] | None = None,
    max_tips: int = 2,
) -> list[str]:
    """Select 0-2 contextual tips relevant to this layer's output."""
    seen = seen_tips or set()
    candidates = []

    if layer_num == 1 and "all_pairings_equal" not in seen:
        candidates.append("all_pairings_equal")

    if layer_num == 7 and "layer_none" not in seen:
        candidates.append("layer_none")

    if layer_num >= 2 and "progressive_relaxation" not in seen:
        candidates.append("progressive_relaxation")

    if pool_size < 15 and "view_pairing_set" not in seen:
        candidates.append("view_pairing_set")

    if has_double_up and "double_up" not in seen:
        candidates.append("double_up")

    if has_waiver and "waive_rest" not in seen:
        candidates.append("waive_rest")

    if layer_num == 1 and "shuffling" not in seen:
        candidates.append("shuffling")

    tips = []
    for key in candidates[:max_tips]:
        if key in CONTEXTUAL_TIPS:
            tips.append(CONTEXTUAL_TIPS[key])
    return tips


# ── Calendar Grid ───────────────────────────────────────────────────────


def format_calendar_grid(
    year: int,
    month: int,
    working_dates: set[int],
    off_dates: set[int] | None = None,
    total_dates: int = 31,
) -> str:
    """Generate a visual month calendar showing work/off days.

    W = working day, . = off day, _ = outside bid period
    """
    cal = calendar.Calendar(firstweekday=6)  # Sunday start
    lines = []
    lines.append(f"  {calendar.month_name[month]} {year}")
    lines.append("  Su Mo Tu We Th Fr Sa")

    for week in cal.monthdayscalendar(year, month):
        row = "  "
        for day in week:
            if day == 0:
                row += "   "
            elif day > total_dates:
                row += " _ "
            elif day in working_dates:
                row += f" W "
            else:
                row += " . "
        lines.append(row)

    return "\n".join(lines)


# ── Per-Pairing Rationale ──────────────────────────────────────────────


@dataclass
class PairingRationale:
    sequence_id: str
    seq_number: int
    layer: int
    reasons_selected: list[str] = field(default_factory=list)
    reasons_not_alternatives: list[str] = field(default_factory=list)
    holdability: str = "UNKNOWN"
    holdability_pct: float = 50.0
    trade_offs: list[str] = field(default_factory=list)


def generate_pairing_rationale(
    seq: dict,
    layer_num: int,
    layer_result: dict,
    pool_sequences: list[dict],
    seniority_number: int = 0,
    total_fas: int = 0,
) -> PairingRationale:
    """Generate human-readable explanation for why a pairing was selected."""
    totals = seq.get("totals", {})
    dps = seq.get("duty_periods", [])
    cities = seq.get("layover_cities", [])
    duty_days = totals.get("duty_days", 1) or 1
    tpay = totals.get("tpay_minutes", 0)
    credit_hours = round(tpay / 60, 1)
    cpd = round(tpay / duty_days / 60, 1) if duty_days else 0
    chosen = seq.get("_chosen_span", set())

    reasons = []

    # Credit contribution
    pool_cpds = []
    for ps in pool_sequences:
        pt = ps.get("totals", {}).get("tpay_minutes", 0)
        pd = ps.get("totals", {}).get("duty_days", 1) or 1
        pool_cpds.append(pt / pd / 60)
    pool_avg_cpd = sum(pool_cpds) / len(pool_cpds) if pool_cpds else 0

    above_below = "above" if cpd > pool_avg_cpd else "below"
    reasons.append(
        f"Contributes {credit_hours}h credit "
        f"({cpd}h per day -- {above_below} pool average of {round(pool_avg_cpd, 1)}h/day)"
    )

    # Schedule fit
    if chosen:
        start_day = min(chosen)
        end_day = max(chosen)
        span = layer_result.get("span_days", 0)
        reasons.append(
            f"Days {start_day}-{end_day} ({duty_days}-day trip) "
            f"-- fits within your work block (span: {span} days)"
        )

    # Layover quality
    for dp in dps:
        lo = dp.get("layover")
        if lo and lo.get("city"):
            city = lo["city"]
            rest_h = round(lo.get("rest_minutes", 0) / 60, 1)
            tier = CITY_TIERS.get(city, _CITY_DEFAULT)
            if rest_h >= 20 and rest_h <= 28:
                quality_note = "great duration for rest and exploring"
            elif rest_h < 14:
                quality_note = "short but legal"
            elif rest_h > 28:
                quality_note = "long layover -- lots of free time"
            else:
                quality_note = ""
            city_note = f"tier {tier}/100" if tier >= 80 else ""
            parts = [f"{city} layover ({rest_h}h)"]
            if quality_note:
                parts.append(quality_note)
            if city_note:
                parts.append(city_note)
            reasons.append(" -- ".join(parts))

    # Holdability
    att = seq.get("_holdability", 0.5)
    hold_cat = holdability_category(att)

    if seniority_number and total_fas:
        if att > 0.7:
            hold_note = f"At your seniority (#{seniority_number}/{total_fas}), this type of trip is LIKELY to still be available"
            if not any(c in PREMIUM_INTL for c in cities):
                hold_note += " -- not a premium destination, so less competition"
            reasons.append(hold_note)
        elif att < 0.3:
            reason = f"This is a LONG SHOT at your seniority"
            if any(c in PREMIUM_INTL for c in cities):
                reason += " -- international premium layovers are extremely popular"
            elif tpay / 60 > 20:
                reason += " -- high-credit trips get taken by senior FAs first"
            reason += f". That's OK in Layer {layer_num} -- PBS tries your dream first."
            reasons.append(reason)

    # Report/release times
    if dps:
        rpt = dps[0].get("report_base", "")
        rel = dps[-1].get("release_base", "")
        if rpt:
            reasons.append(f"Reports {rpt} -- {'commuter-friendly' if _hhmm(rpt) >= 600 else 'early start'}")
        if rel:
            reasons.append(f"Releases {rel} -- {'home same day' if _hhmm(rel) <= 1080 else 'late finish'}")

    # Why not alternatives (top 3 not selected from pool)
    selected_ids = set(s.get("_id") for s in layer_result.get("selected", []))
    alt_reasons = []
    unselected = [s for s in pool_sequences if s.get("_id") not in selected_ids]
    unselected_sorted = sorted(
        unselected,
        key=lambda s: s.get("_trip_quality", 0) * s.get("preference_score", 0.5),
        reverse=True,
    )

    for alt in unselected_sorted[:3]:
        alt_num = alt.get("seq_number", "?")
        alt_dd = alt.get("totals", {}).get("duty_days", 1)
        alt_credit = round(alt.get("totals", {}).get("tpay_minutes", 0) / 60, 1)
        alt_cities = ", ".join(alt.get("layover_cities", [])) or "turn"
        alt_spans = alt.get("_all_spans", [])

        # Check why not selected
        if chosen and alt_spans:
            for alt_span in alt_spans:
                if alt_span & set(chosen):
                    alt_reasons.append(
                        f"SEQ-{alt_num} ({alt_dd}d, {alt_credit}h, {alt_cities}) "
                        f"-- overlaps on day {min(alt_span & set(chosen))}"
                    )
                    break
            else:
                alt_quality = alt.get("_trip_quality", 0)
                seq_quality = seq.get("_trip_quality", 0)
                if alt_quality < seq_quality:
                    alt_reasons.append(
                        f"SEQ-{alt_num} ({alt_dd}d, {alt_credit}h, {alt_cities}) "
                        f"-- lower quality score ({round(alt_quality, 2)} vs {round(seq_quality, 2)})"
                    )

    # Trade-offs
    trade_offs = []
    if duty_days >= 4:
        trade_offs.append(f"Long trip ({duty_days} days) -- more time away from home")
    if tpay / 60 < 15:
        trade_offs.append(f"Modest credit ({credit_hours}h) -- less pay than max-credit options")
    if dps and _hhmm(dps[0].get("report_base", "12:00")) < 420:
        trade_offs.append("Early report -- may need hotel night before if commuting")

    return PairingRationale(
        sequence_id=seq.get("_id", ""),
        seq_number=seq.get("seq_number", 0),
        layer=layer_num,
        reasons_selected=reasons,
        reasons_not_alternatives=alt_reasons,
        holdability=hold_cat,
        holdability_pct=round(att * 100, 0),
        trade_offs=trade_offs,
    )


def _hhmm(t: str) -> int:
    """Convert "HH:MM" to minutes."""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


# ── Per-Layer Narrative ─────────────────────────────────────────────────


def generate_layer_narrative(
    layer_num: int,
    strategy_name: str,
    result: dict,
    seniority_number: int = 0,
    total_fas: int = 0,
    has_calibration: bool = False,
) -> str:
    """Generate plain-English summary for a layer.

    Adapts narrative style based on strategy_mode ("progressive" or "themed").
    Progressive mode explains how each layer relates to L2 picks and why
    pools widen.  Themed mode describes each layer's theme.
    """
    seqs = result.get("selected", [])
    credit_hours = round(result.get("total_credit_minutes", 0) / 60, 1)
    days_off = result.get("days_off", 0)
    span_days = result.get("span_days", 0)
    pool_size = result.get("pool_size", 0)
    holdability_pct = result.get("avg_holdability", 50)
    is_progressive = result.get("strategy_mode") == "progressive"
    pool_health = result.get("pool_health", {})
    pool_notes = result.get("pool_notes", [])

    if not seqs:
        return f"Layer {layer_num}: No feasible schedule found with current constraints."

    first_day = min(min(s.get("_chosen_span", {31})) for s in seqs)
    last_day = max(max(s.get("_chosen_span", {1})) for s in seqs)
    trip_summary = _summarize_trips(seqs)

    # Pool health line
    health_note = pool_health.get("note", "")
    health_status = pool_health.get("status", "ok")
    health_line = ""
    if health_note:
        icon = {"ok": "OK", "warning": "WARNING", "critical": "CRITICAL"}.get(health_status, "")
        health_line = f"Pool health: {icon} — {health_note}\n"

    # Relaxation notes
    relax_line = ""
    if pool_notes:
        relax_line = "How pool was built: " + "; ".join(pool_notes) + "\n"

    # ── Layer 1 ──────────────────────────────────────────────────────
    if layer_num == 1:
        narrative = (
            f"**Layer 1: {strategy_name}**\n\n"
        )
        if is_progressive:
            narrative += (
                "This is your lottery ticket -- the dream schedule assuming "
                "everything is available. PBS tries it first, and if senior "
                "FAs have taken the best trips, it moves to Layer 2.\n\n"
            )
        else:
            narrative += (
                "This is your best-case scenario -- the schedule you'd love "
                "to fly if seniority allows. PBS tries this first.\n\n"
            )
        narrative += (
            f"Working days {first_day}-{last_day} (span: {span_days} days), "
            f"{days_off} days off. Credit: {credit_hours}h.\n"
            f"Trips: {trip_summary}\n"
        )
        if seniority_number and total_fas:
            narrative += (
                f"\nAt your seniority (#{seniority_number} of {total_fas}), "
                f"holdability is ~{holdability_pct:.0f}%. "
            )
            if holdability_pct >= 70:
                narrative += "Strong position -- most of this layer should stick.\n"
            elif holdability_pct >= 45:
                narrative += "Competitive -- some trips may be taken by senior FAs.\n"
            else:
                narrative += "This is a reach -- but that's what Layer 1 is for.\n"
        elif not has_calibration:
            narrative += (
                "\nNo historical data yet for holdability prediction. "
                "After 2-3 months of recording awards, predictions improve.\n"
            )

    # ── Layer 2 (progressive: specific picks) ────────────────────────
    elif layer_num == 2 and is_progressive:
        pick_count = result.get("pool_metadata", {}).get("pick_count", pool_size)
        narrative = (
            f"**Layer 2: {strategy_name}**\n\n"
            f"These are your {pick_count} hand-picked pairings -- the exact "
            f"trips you'd most like to fly. If these specific trips survive "
            f"to your seniority, PBS builds your schedule from them.\n\n"
            f"Working days {first_day}-{last_day} (span: {span_days} days), "
            f"{days_off} days off. Credit: {credit_hours}h.\n"
            f"Trips: {trip_summary}\n\n"
        )
        if pick_count < 20:
            narrative += (
                f"Note: With only {pick_count} pairings, if senior FAs take "
                f"3-4 of these, PBS may not be able to build a legal line "
                f"from what's left. That's exactly why Layer 3 exists -- it "
                f"bids the same TYPE of trip with a much larger pool.\n"
            )
        narrative += health_line

    # ── Layer 3 (progressive: generic version of L2) ──────────────────
    elif layer_num == 3 and is_progressive:
        derived = result.get("derived_properties") or {}
        narrative = (
            f"**Layer 3: {strategy_name}**\n\n"
            f"This layer takes what you like about your L2 picks and bids "
            f"the same TYPE of trip as generic properties, giving PBS "
            f"{pool_size} options instead of just your specific picks.\n\n"
        )
        # Describe derived properties
        if derived:
            prop_desc = []
            if derived.get("trip_lengths"):
                prop_desc.append(f"trip length: {derived['trip_lengths']}-day")
            if derived.get("layover_cities"):
                cities = derived["layover_cities"][:5]
                prop_desc.append(f"layover cities: {', '.join(cities)}")
            if derived.get("report_range"):
                lo, hi = derived["report_range"]
                prop_desc.append(f"report: {lo//60:02d}:{lo%60:02d}-{hi//60:02d}:{hi%60:02d}")
            if prop_desc:
                narrative += (
                    "Derived properties from your picks:\n"
                    + "\n".join(f"  - {p}" for p in prop_desc)
                    + "\n\n"
                )
        narrative += (
            f"Working days {first_day}-{last_day} (span: {span_days} days), "
            f"{days_off} days off. Credit: {credit_hours}h.\n"
            f"Trips: {trip_summary}\n"
            f"Pool: {pool_size} pairings | Holdability: {holdability_pct:.0f}%\n"
        )
        narrative += health_line + relax_line

    # ── Layers 4-5 (progressive: widened) ─────────────────────────────
    elif layer_num in (4, 5) and is_progressive:
        narrative = (
            f"**Layer {layer_num}: {strategy_name}**\n\n"
            f"This layer widens the pool from Layer {layer_num - 1} by "
            f"relaxing filter properties. {pool_size} pairings available -- "
            f"PBS has many more combinations to build a legal schedule.\n\n"
            f"Working days {first_day}-{last_day} (span: {span_days} days), "
            f"{days_off} days off. Credit: {credit_hours}h.\n"
            f"Trips: {trip_summary}\n"
            f"Pool: {pool_size} pairings | Holdability: {holdability_pct:.0f}%\n"
        )
        narrative += health_line + relax_line

    # ── Layer 6 (progressive: broad domestic) ──────────────────────────
    elif layer_num == 6 and is_progressive:
        narrative = (
            f"**Layer 6: {strategy_name}**\n\n"
            f"Broad domestic flying -- all 2-5 day trips. {pool_size} "
            f"pairings. Minimal filters so PBS can always build a legal "
            f"schedule.\n\n"
            f"Working days {first_day}-{last_day} (span: {span_days} days), "
            f"{days_off} days off. Credit: {credit_hours}h.\n"
            f"Trips: {trip_summary}\n"
            f"Pool: {pool_size} pairings | Holdability: {holdability_pct:.0f}%\n"
        )
        narrative += health_line

    # ── Layer 7 ──────────────────────────────────────────────────────
    elif layer_num == 7:
        narrative = (
            f"**Layer 7: {strategy_name}**\n\n"
            f"This is your insurance policy. If PBS can't build a legal "
            f"schedule from Layers 1-6, Layer 7 catches you.\n\n"
            f"Without Layer 7, you'd fall to 'Layer None' -- company-assigned "
            f"random flying with no input. That's what we're preventing.\n\n"
            f"This layer is deliberately broad: {pool_size} pairings in the "
            f"pool. It accepts {trip_summary}.\n"
            f"Credit: {credit_hours}h | Days off: {days_off} | "
            f"Holdability: {holdability_pct:.0f}%\n"
        )
        narrative += health_line

    # ── Generic (themed mode) ────────────────────────────────────────
    else:
        narrative = (
            f"**Layer {layer_num}: {strategy_name}**\n\n"
            f"Working days {first_day}-{last_day} (span: {span_days} days), "
            f"{days_off} days off. Credit: {credit_hours}h.\n"
            f"Trips: {trip_summary}\n"
            f"Pool: {pool_size} pairings | Holdability: {holdability_pct:.0f}%\n"
        )
        narrative += health_line

    return narrative


def _summarize_trips(seqs: list[dict]) -> str:
    """Summarize trip composition (e.g., '3x3-day, 1x4-day')."""
    from collections import Counter
    lengths = Counter()
    for s in seqs:
        dd = s.get("totals", {}).get("duty_days", 1) or 1
        lengths[dd] += 1
    parts = [f"{count}x{dd}-day" for dd, count in sorted(lengths.items())]
    return ", ".join(parts) if parts else "none"


# ── PBS Property Translation ────────────────────────────────────────────


def translate_to_pbs_properties(
    layer_num: int,
    selected_sequences: list[dict],
    pool_size: int,
) -> str:
    """Reverse-engineer PBS properties from optimizer selections.

    Tells the FA what to enter at fapbs.aa.com for this layer.
    """
    if not selected_sequences:
        return f"Layer {layer_num}: No sequences selected -- check constraints.\n"

    # Infer pairing tab properties
    trip_lengths = sorted(set(
        s.get("totals", {}).get("duty_days", 1) or 1 for s in selected_sequences
    ))
    layover_cities = sorted(set(
        c for s in selected_sequences for c in s.get("layover_cities", [])
    ))
    report_times = [
        _hhmm(s.get("duty_periods", [{}])[0].get("report_base", "12:00"))
        for s in selected_sequences if s.get("duty_periods")
    ]
    release_times = [
        _hhmm(s.get("duty_periods", [{}])[-1].get("release_base", "18:00"))
        for s in selected_sequences if s.get("duty_periods")
    ]
    has_ipd = any(s.get("is_ipd") for s in selected_sequences)

    # Credit range
    credits = [s.get("totals", {}).get("tpay_minutes", 0) for s in selected_sequences]
    total_credit = sum(credits)
    credit_hours = round(total_credit / 60, 1)

    lines = [f"**What to enter at fapbs.aa.com for Layer {layer_num}:**\n"]

    # Pairing Tab
    lines.append("Pairing Tab:")
    lines.append(f"  Trip Length: {', '.join(f'{d}-day' for d in trip_lengths)}")
    if len(layover_cities) <= 8 and layover_cities:
        lines.append(f"  Layover City: {', '.join(layover_cities)}")
    elif layover_cities:
        lines.append(f"  Layover City: (no filter -- {len(layover_cities)} cities, too many to list)")
    if report_times:
        min_rpt = min(report_times)
        if min_rpt >= 420:  # 07:00
            lines.append(f"  Report Time: after {min_rpt // 60:02d}:{min_rpt % 60:02d}")
    if has_ipd:
        lines.append("  Pairing Type: IPD")

    # Line Tab
    lines.append("\nLine Tab:")
    if trip_lengths:
        lines.append(f"  Work Block Size: Min {min(trip_lengths)}, Max {max(trip_lengths) + 2}")
    lines.append(f"  Target Credit Range: ~{credit_hours}h")

    # Pool warning
    lines.append(f"\nThis layer's pool has {pool_size} pairings.")
    if pool_size > 20:
        lines.append("That's plenty -- PBS has lots of options to build your line.")
    elif pool_size > 8:
        lines.append("That's moderate -- consider widening filters if PBS can't build a line.")
    else:
        lines.append(
            "That's dangerously low -- PBS may not be able to build a legal line. "
            "Widen your filters!"
        )

    lines.append(
        "\nRemember: All pairings in this layer are equally desirable to PBS. "
        "If you want PBS to prefer specific trips, put them in a higher-priority layer."
    )

    return "\n".join(lines)


# ── "Why Not" Explainer ─────────────────────────────────────────────────


def explain_exclusion(
    seq: dict,
    layer_result: dict,
    pool_sequences: list[dict],
) -> str:
    """Explain why a specific sequence was NOT selected in a layer."""
    seq_id = seq.get("_id", "")
    seq_num = seq.get("seq_number", "?")
    totals = seq.get("totals", {})
    duty_days = totals.get("duty_days", 1)
    credit = round(totals.get("tpay_minutes", 0) / 60, 1)
    cities = ", ".join(seq.get("layover_cities", [])) or "turn"

    pool_ids = {s.get("_id") for s in pool_sequences}
    selected_seqs = layer_result.get("selected", [])
    selected_ids = {s.get("_id") for s in selected_seqs}

    header = f"SEQ-{seq_num} ({duty_days}d, {credit}h, {cities})"

    # Not in pool
    if seq_id not in pool_ids:
        return (
            f"{header}: Not in this layer's pool -- "
            "doesn't match the filter criteria for this layer."
        )

    # Date conflict
    seq_spans = seq.get("_all_spans", [])
    for selected in selected_seqs:
        sel_span = set(selected.get("_chosen_span", set()))
        for span in seq_spans:
            overlap = span & sel_span
            if overlap:
                sel_num = selected.get("seq_number", "?")
                sel_quality = selected.get("_trip_quality", 0)
                seq_quality = seq.get("_trip_quality", 0)
                return (
                    f"{header}: Conflicts with SEQ-{sel_num} "
                    f"(overlap on day {min(overlap)}). "
                    f"The optimizer chose SEQ-{sel_num} because it scores higher "
                    f"({round(sel_quality, 2)} vs {round(seq_quality, 2)} quality)."
                )

    # Credit bust
    total_credit_min = sum(s.get("totals", {}).get("tpay_minutes", 0) for s in selected_seqs)
    projected = total_credit_min + totals.get("tpay_minutes", 0)
    max_credit = layer_result.get("max_credit_minutes", 5400)
    if projected > max_credit:
        return (
            f"{header}: Would push total credit to {round(projected / 60, 1)}h, "
            f"exceeding the {round(max_credit / 60, 1)}h ceiling."
        )

    # Days off bust
    total_work_days = sum(s.get("totals", {}).get("duty_days", 1) for s in selected_seqs)
    total_dates = layer_result.get("total_dates", 30)
    min_days_off = layer_result.get("min_days_off", 11)
    if total_work_days + duty_days > total_dates - min_days_off:
        projected_off = total_dates - total_work_days - duty_days
        return (
            f"{header}: Would leave only {projected_off} days off, "
            f"below the {min_days_off}-day minimum."
        )

    # Low attainability (for non-dream layers)
    att = seq.get("_holdability", 0.5)
    layer_num = layer_result.get("layer_num", 1)
    if att < 0.3 and layer_num >= 4:
        return (
            f"{header}: Great trip but LONG SHOT at your seniority. "
            f"The optimizer deprioritized it in Layer {layer_num} to focus on "
            f"trips you can actually hold. Check if it's in Layer 1-2."
        )

    # Block limit bust
    return (
        f"{header}: Available in pool but the optimizer found a better combination "
        f"of trips overall. The excluded trip would have reduced the total schedule score."
    )


# ── Post-Award Comparison ──────────────────────────────────────────────


def generate_post_award_analysis(
    predicted_layers: list[dict],
    actual_award: dict,
) -> str:
    """Compare predicted holdability to actual PBS award results."""
    month = actual_award.get("month", "unknown")
    actual_line = actual_award.get("line_label", "?")
    pairings = actual_award.get("pairings", [])

    # Find predicted typical layer
    predicted_typical = "?"
    if predicted_layers:
        # Use the layer with highest holdability as predicted
        best = max(predicted_layers, key=lambda l: l.get("holdability_pct", 0))
        predicted_typical = best.get("layer_num", "?")

    lines = [
        f"HOW DID WE DO? -- {month}",
        "",
        "Predicted vs Actual:",
        f"  We predicted your line would come from: Layer {predicted_typical}",
        f"  Your line actually came from: Layer {actual_line}",
    ]

    if str(predicted_typical) == str(actual_line):
        lines.append("  Prediction: Correct!")
    else:
        lines.append("  Adjusting model for next month.")

    # Credit comparison
    actual_credit = actual_award.get("total_credit_minutes", 0)
    lines.append(f"\n  Actual credit: {round(actual_credit / 60, 1)}h")

    lines.append("\nModel updated. Next month's predictions will be more accurate.")

    return "\n".join(lines)


# ── Monthly Data Entry Prompt ───────────────────────────────────────────


def monthly_entry_prompt() -> str:
    """Generate the monthly award recording prompt."""
    return """
RECORD THIS MONTH'S AWARD
(Takes ~5 minutes after awards post)

1. Open your PBS award in Crew Portal
2. For each pairing, note the award code (P1-P7, PN, or CN)
3. Enter the data:

  Month: _________ (e.g., 2026-05)
  Total credit awarded: _______ hours
  Line label: _______ (L1-L7 or LN)

  Pairings:
    SEQ _______ -> awarded from layer: P__
    SEQ _______ -> awarded from layer: P__
    (add more as needed)

  Any pairings you wanted but didn't get?
    SEQ _______ (went to someone more senior)

  Notes: _________________________________

After entering, the model will:
  - Update your holdability predictions
  - Show how this month compared to predictions
  - Refine next month's recommendations
""".strip()


# ── Full Output Generator ──────────────────────────────────────────────


def generate_full_explanation(
    layers_data: list[dict],
    seniority_number: int,
    total_fas: int,
    seniority_percentage: float | None = None,
    year: int = 2026,
    month: int = 4,
    total_dates: int = 30,
    has_calibration: bool = False,
    calibration_data: dict | None = None,
) -> dict:
    """Generate the complete explanation output for all layers.

    Returns dict with:
      - holdability_report: overall seniority assessment
      - layers: list of per-layer explanation dicts
      - cross_layer_summary: diversity/credit/strategy matrix
      - recommendation: personalized advice
      - monthly_prompt: data entry reminder
    """
    from app.services.holdability import generate_holdability_report

    # Generate holdability report
    holdability_report = generate_holdability_report(
        layers_data,
        seniority_number,
        total_fas,
        seniority_percentage=seniority_percentage,
    )

    # Per-layer explanations
    seen_tips: set[str] = set()
    layer_explanations = []

    for ldata in layers_data:
        layer_num = ldata.get("layer_num", 0)
        strategy_name = ldata.get("strategy_name", "")
        selected = ldata.get("sequences", [])
        pool_size = ldata.get("pool_size", 0)
        pool_seqs = ldata.get("pool_sequences", [])

        # Narrative
        narrative = generate_layer_narrative(
            layer_num, strategy_name, ldata,
            seniority_number=seniority_number,
            total_fas=total_fas,
            has_calibration=has_calibration,
        )

        # Calendar grid
        working_dates = set()
        for s in selected:
            working_dates |= set(s.get("_chosen_span", set()))
        grid = format_calendar_grid(year, month, working_dates, total_dates=total_dates)

        # Per-pairing rationales
        rationales = []
        for s in selected:
            rat = generate_pairing_rationale(
                s, layer_num, ldata, pool_seqs,
                seniority_number=seniority_number,
                total_fas=total_fas,
            )
            rationales.append(rat)

        # PBS property translation
        pbs_translation = translate_to_pbs_properties(layer_num, selected, pool_size)

        # Tips
        has_du = ldata.get("has_double_up", False)
        has_waiver = ldata.get("has_waiver", False)
        tips = select_tips(layer_num, pool_size, has_du, has_waiver, seen_tips)
        seen_tips.update(t[:30] for t in tips)  # track seen by prefix

        layer_explanations.append({
            "layer_num": layer_num,
            "narrative": narrative,
            "calendar_grid": grid,
            "rationales": [vars(r) for r in rationales],
            "pbs_translation": pbs_translation,
            "holdability_pct": ldata.get("avg_holdability", 50),
            "tips": tips,
            "pool_size": pool_size,
            "pool_health": ldata.get("pool_health", {}),
            "pool_notes": ldata.get("pool_notes", []),
            "derived_properties": ldata.get("derived_properties"),
            "relaxed_properties": ldata.get("relaxed_properties"),
        })

    # Cross-layer summary
    cross_layer = _build_cross_layer_summary(layers_data)

    # Pool size health table (progressive mode)
    pool_health_table = []
    for ldata in layers_data:
        ph = ldata.get("pool_health", {})
        pool_health_table.append({
            "layer": ldata.get("layer_num", 0),
            "pool_size": ldata.get("pool_size", 0),
            "status": ph.get("status", "ok"),
            "note": ph.get("note", ""),
        })

    strategy_mode = (
        layers_data[0].get("strategy_mode", "themed") if layers_data else "themed"
    )

    return {
        "holdability_report": holdability_report,
        "layers": layer_explanations,
        "cross_layer_summary": cross_layer,
        "pool_health_table": pool_health_table,
        "strategy_mode": strategy_mode,
        "recommendation": holdability_report.get("recommendation", ""),
        "monthly_prompt": monthly_entry_prompt(),
    }


def _build_cross_layer_summary(layers_data: list[dict]) -> dict:
    """Build cross-layer comparison: diversity, credit spread, strategy."""
    if not layers_data:
        return {}

    # Credit spread
    credits = []
    for ld in layers_data:
        c = ld.get("total_credit_minutes", 0) / 60
        credits.append({"layer": ld.get("layer_num", 0), "credit_hours": round(c, 1)})

    # Diversity matrix: how many unique sequences per layer vs shared
    all_ids_per_layer: list[set[str]] = []
    for ld in layers_data:
        ids = set(s.get("_id", "") for s in ld.get("sequences", []))
        all_ids_per_layer.append(ids)

    diversity = []
    for i in range(len(all_ids_per_layer)):
        for j in range(i + 1, len(all_ids_per_layer)):
            shared = len(all_ids_per_layer[i] & all_ids_per_layer[j])
            total = len(all_ids_per_layer[i] | all_ids_per_layer[j])
            overlap_pct = round(shared / total * 100, 0) if total > 0 else 0
            diversity.append({
                "layer_a": i + 1,
                "layer_b": j + 1,
                "shared_sequences": shared,
                "overlap_pct": overlap_pct,
            })

    # Strategy fulfillment
    strategies = []
    for ld in layers_data:
        strategies.append({
            "layer": ld.get("layer_num", 0),
            "strategy": ld.get("strategy_name", ""),
            "sequences": len(ld.get("sequences", [])),
            "credit_hours": round(ld.get("total_credit_minutes", 0) / 60, 1),
            "holdability": round(ld.get("avg_holdability", 50), 0),
        })

    # Pool size progression (progressive mode)
    pool_progression = []
    for ld in layers_data:
        ph = ld.get("pool_health", {})
        pool_progression.append({
            "layer": ld.get("layer_num", 0),
            "pool_size": ld.get("pool_size", 0),
            "pool_status": ph.get("status", "ok"),
            "pool_note": ph.get("note", ""),
        })

    return {
        "credit_spread": credits,
        "diversity_matrix": diversity,
        "strategy_fulfillment": strategies,
        "pool_progression": pool_progression,
    }
