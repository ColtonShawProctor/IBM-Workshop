"""Parse airline bid sheet PDFs into structured sequence data."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

import pdfplumber

from app.services.airline_configs import AirlineConfig, get_airline_config, DEFAULT_CONFIG


# ── Regex patterns (kept for backwards compatibility) ─────────────────────

FOOTER_RE = DEFAULT_CONFIG.footer_re
SEQ_RE = DEFAULT_CONFIG.seq_re
RPT_RE = DEFAULT_CONFIG.rpt_re
RLS_RE = DEFAULT_CONFIG.rls_re
TTL_RE = DEFAULT_CONFIG.ttl_re
LEG_PREFIX_RE = DEFAULT_CONFIG.leg_prefix_re
LAYOVER_HOTEL_RE = DEFAULT_CONFIG.layover_hotel_re
LAYOVER_TRANSPORT_RE = DEFAULT_CONFIG.layover_transport_re
CATEGORY_LINE_RE = DEFAULT_CONFIG.category_line_re
DASH_RE = DEFAULT_CONFIG.dash_re

# Calendar dates on the right side of lines
CALENDAR_RE = re.compile(r"((?:\d{1,2}|[-–]{2})\s*)+$")

# IPD destination stations: Europe, Asia, Deep South America (CBA §14.B)
_IPD_DESTINATION_STATIONS = {
    # Europe
    "LHR", "CDG", "FCO", "BCN", "MAD", "AMS", "FRA", "MUC", "ZRH", "DUB",
    "MXP", "LGW", "EDI", "ATH", "PRG", "BUD", "VCE", "LIS",
    # Asia
    "NRT", "HND", "ICN", "PVG", "HKG", "PEK", "BKK", "SIN", "DEL", "BOM",
    "TPE", "MNL", "KIX", "CTS",
    # Deep South America
    "GRU", "EZE", "SCL", "GIG", "LIM", "BOG",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _hmm_to_minutes(hmm: str) -> int:
    """Convert H.MM format (e.g. '21.45') to integer minutes."""
    parts = hmm.split(".")
    hours = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    return hours * 60 + minutes


def _format_time(raw: str) -> str:
    """Convert HHMM string to HH:MM format."""
    return f"{raw[:2]}:{raw[2:]}"


def _parse_date(date_str: str, fmt: str = "%d%b%Y") -> str:
    """Convert '08DEC2025' to '2025-12-08' ISO format."""
    dt = datetime.strptime(date_str, fmt)
    return dt.strftime("%Y-%m-%d")


def _normalize_dashes(s: str) -> str:
    """Replace en-dash (U+2013) and minus sign (U+2212) with hyphen-minus."""
    return s.replace("\u2013", "-").replace("\u2212", "-")


def _extract_calendar_dates(line: str) -> list[int]:
    """Extract operating dates from the right side of a line."""
    tokens = line.split()
    dates: list[int] = []
    i = len(tokens) - 1
    while i >= 0:
        tok_clean = _normalize_dashes(tokens[i])
        if tok_clean == "--" or re.fullmatch(r"\d{1,2}", tok_clean):
            i -= 1
        else:
            break
    calendar_tokens = tokens[i + 1:]
    for tok in calendar_tokens:
        tok_clean = _normalize_dashes(tok)
        if tok_clean != "--" and re.fullmatch(r"\d{1,2}", tok_clean):
            dates.append(int(tok_clean))
    return dates


def _parse_leg_line(line: str, config: AirlineConfig = DEFAULT_CONFIG) -> Optional[dict]:
    """Parse a leg line and return a dict of leg fields, or None."""
    m = config.leg_prefix_re.match(line)
    if not m:
        return None

    dp_num = int(m.group(1))
    day_of_seq = int(m.group(2))
    day_of_seq_total = int(m.group(3))
    equipment = m.group(4)
    flight_raw = m.group(5)
    dep_station = m.group(6)
    dep_local = m.group(7)
    dep_base = m.group(8)

    rest = line[m.end():].split()

    arr_station = None
    arr_local = None
    arr_base = None
    meal_code = None
    pax_svc = None
    block_str = None
    ground_str = None

    i = 0

    if i < len(rest) and re.fullmatch(r"\*?[A-Z]{1,2}", rest[i]) and not re.fullmatch(r"[A-Z]{3}", rest[i]):
        meal_code = rest[i]
        i += 1

    if i < len(rest) and re.fullmatch(r"[A-Z]{3}", rest[i]):
        arr_station = rest[i]
        i += 1
    else:
        return None

    if i < len(rest) and re.fullmatch(r"\d{4}/\d{4}", rest[i]):
        parts = rest[i].split("/")
        arr_local = parts[0]
        arr_base = parts[1]
        i += 1
    else:
        return None

    remaining: list[str] = []
    while i < len(rest):
        tok = _normalize_dashes(rest[i])
        if tok == "--":
            break
        if re.fullmatch(r"\d{1,2}", tok) and int(tok) <= 31:
            break
        remaining.append(rest[i])
        i += 1

    parsed_remaining: list[str] = list(remaining)

    block_idx = None
    for j, tok in enumerate(parsed_remaining):
        if re.fullmatch(r"\d+\.\d+", tok):
            block_idx = j
            break

    if block_idx is None:
        return None

    block_str = parsed_remaining[block_idx]

    if block_idx + 1 < len(parsed_remaining):
        gt = parsed_remaining[block_idx + 1]
        if re.fullmatch(r"\d+\.\d+X?", gt):
            ground_str = gt

    pre_block = parsed_remaining[:block_idx]
    for tok in pre_block:
        if tok.startswith("*") or (re.fullmatch(r"[A-Z]{1,2}", tok) and tok not in ("Q", "QL", "QD", "QB") and not tok.startswith("Q")):
            if tok.startswith("*"):
                meal_code = tok
            elif re.fullmatch(r"Q[A-Z0-9/]{0,3}", tok):
                pax_svc = tok
            elif meal_code is None and pax_svc is not None:
                pass
            elif pax_svc is None and re.fullmatch(r"[A-Z]{2,3}", tok) and tok[0] == "Q":
                pax_svc = tok
            else:
                if meal_code is None:
                    meal_code = tok
        elif re.fullmatch(r"Q[A-Z0-9/]{0,3}", tok):
            pax_svc = tok
        elif re.fullmatch(r"\*?[A-Z]{1,3}", tok):
            if tok.startswith("Q"):
                pax_svc = tok
            elif meal_code is None:
                meal_code = tok
            elif pax_svc is None:
                pax_svc = tok

    dh_suffix = config.deadhead_suffix
    is_deadhead = flight_raw.endswith(dh_suffix)
    flight_number = flight_raw.rstrip(dh_suffix) if is_deadhead else flight_raw

    ground_minutes = None
    is_connection = False
    if ground_str:
        is_connection = ground_str.endswith("X")
        ground_clean = ground_str.rstrip("X")
        ground_minutes = _hmm_to_minutes(ground_clean)

    return {
        "dp_number": dp_num,
        "day_of_seq": day_of_seq,
        "day_of_seq_total": day_of_seq_total,
        "equipment": equipment,
        "flight_number": flight_number,
        "is_deadhead": is_deadhead,
        "departure_station": dep_station,
        "departure_local": _format_time(dep_local),
        "departure_base": _format_time(dep_base),
        "meal_code": meal_code,
        "arrival_station": arr_station,
        "arrival_local": _format_time(arr_local),
        "arrival_base": _format_time(arr_base),
        "pax_service": pax_svc,
        "block_minutes": _hmm_to_minutes(block_str),
        "ground_minutes": ground_minutes,
        "is_connection": is_connection,
    }


# ── Page-level parser ──────────────────────────────────────────────────────

def _parse_page_text(
    text: str,
    config: AirlineConfig = DEFAULT_CONFIG,
) -> tuple[list[dict], Optional[str], Optional[dict]]:
    """Parse a single page of extracted text."""
    lines = text.split("\n")
    sequences: list[dict] = []
    category: Optional[str] = None
    footer_info: Optional[dict] = None

    current_seq: Optional[dict] = None
    current_dp: Optional[dict] = None
    current_legs: list[dict] = []
    duty_periods: list[dict] = []
    all_dates: list[int] = []
    awaiting_transport = False
    last_layover: Optional[dict] = None

    def _finalize_dp():
        nonlocal current_dp, current_legs
        if current_dp and current_legs:
            current_dp["legs"] = current_legs
            duty_periods.append(current_dp)
        current_dp = None
        current_legs = []

    def _finalize_seq():
        nonlocal current_seq, duty_periods, all_dates, last_layover, awaiting_transport
        if current_seq:
            _finalize_dp()
            current_seq["duty_periods"] = duty_periods
            current_seq["operating_dates"] = sorted(set(all_dates))
            sequences.append(current_seq)
        current_seq = None
        duty_periods = []
        all_dates = []
        last_layover = None
        awaiting_transport = False

    for line in lines:
        line = line.rstrip()
        if not line:
            continue

        fm = config.footer_re.search(line)
        if fm:
            issued = _parse_date(fm.group(1), config.date_format)
            effective = _parse_date(fm.group(2), config.date_format)
            cat_raw = fm.group(3).strip()
            footer_info = {
                "issued_date": issued,
                "effective_start": effective,
                "category": cat_raw,
            }
            category = cat_raw
            continue

        cm = config.category_line_re.match(line.strip())
        if cm:
            if not category:
                category = cm.group(1).strip()
            continue

        if config.dash_re.match(line.strip()):
            _finalize_seq()
            continue

        sm = config.seq_re.match(line)
        if sm:
            _finalize_seq()
            current_seq = {
                "seq_number": int(sm.group(1)),
                "ops_count": int(sm.group(2)),
                "position_min": int(sm.group(3)),
                "position_max": int(sm.group(4)),
                "language": sm.group(5),
                "language_count": int(sm.group(6)) if sm.group(6) else None,
            }
            dates = _extract_calendar_dates(line)
            all_dates.extend(dates)
            continue

        if current_seq is None:
            continue

        rm = config.rpt_re.match(line)
        if rm:
            _finalize_dp()
            current_dp = {
                "report_local": _format_time(rm.group(1)),
                "report_base": _format_time(rm.group(2)),
                "release_local": "",
                "release_base": "",
                "dp_number": len(duty_periods) + 1,
                "day_of_seq": None,
                "day_of_seq_total": None,
            }
            dates = _extract_calendar_dates(line)
            all_dates.extend(dates)
            continue

        rlm = config.rls_re.match(line)
        if rlm:
            if current_dp:
                current_dp["release_local"] = _format_time(rlm.group(1))
                current_dp["release_base"] = _format_time(rlm.group(2))
                remainder = rlm.group(3).strip()
                nums = re.findall(r"\d+\.\d+", remainder)
                if len(nums) >= 3:
                    current_dp["synth_minutes"] = _hmm_to_minutes(nums[0])
                    current_dp["tpay_minutes"] = _hmm_to_minutes(nums[1])
                    current_dp["duty_minutes"] = _hmm_to_minutes(nums[2])
                elif len(nums) >= 1:
                    current_dp["duty_minutes"] = _hmm_to_minutes(nums[-1])
            dates = _extract_calendar_dates(line)
            all_dates.extend(dates)
            continue

        tm = config.ttl_re.match(line)
        if tm:
            if current_seq:
                current_seq["totals"] = {
                    "block_minutes": _hmm_to_minutes(tm.group(1)),
                    "synth_minutes": _hmm_to_minutes(tm.group(2)),
                    "tpay_minutes": _hmm_to_minutes(tm.group(3)),
                    "tafb_minutes": _hmm_to_minutes(tm.group(4)),
                }
            continue

        leg = _parse_leg_line(line, config)
        if leg:
            if current_dp:
                if current_dp["day_of_seq"] is None:
                    current_dp["day_of_seq"] = leg["day_of_seq"]
                    current_dp["day_of_seq_total"] = leg["day_of_seq_total"]
                current_dp["dp_number"] = leg["dp_number"]
            leg_dict = {
                "leg_index": len(current_legs) + 1,
                "flight_number": leg["flight_number"],
                "is_deadhead": leg["is_deadhead"],
                "equipment": leg["equipment"],
                "departure_station": leg["departure_station"],
                "departure_local": leg["departure_local"],
                "departure_base": leg["departure_base"],
                "meal_code": leg["meal_code"],
                "arrival_station": leg["arrival_station"],
                "arrival_local": leg["arrival_local"],
                "arrival_base": leg["arrival_base"],
                "pax_service": leg["pax_service"],
                "block_minutes": leg["block_minutes"],
                "ground_minutes": leg["ground_minutes"],
                "is_connection": leg["is_connection"],
            }
            current_legs.append(leg_dict)
            dates = _extract_calendar_dates(line)
            all_dates.extend(dates)
            awaiting_transport = False
            continue

        lm = config.layover_hotel_re.match(line.strip())
        if lm and current_dp:
            last_layover = {
                "city": lm.group(1),
                "hotel_name": lm.group(2).strip(),
                "hotel_phone": lm.group(3).replace("\u2013", "-").replace("\u2212", "-"),
                "transport_company": None,
                "transport_phone": None,
                "rest_minutes": _hmm_to_minutes(lm.group(4)),
            }
            current_dp["layover"] = last_layover
            awaiting_transport = True
            continue

        if awaiting_transport and last_layover:
            ltm = config.layover_transport_re.match(line.strip())
            if ltm:
                last_layover["transport_company"] = ltm.group(1).strip()
                last_layover["transport_phone"] = ltm.group(2).replace("\u2013", "-").replace("\u2212", "-")
                awaiting_transport = False
                continue

    _finalize_seq()

    return sequences, category, footer_info


def _colon_time_to_minutes(t: str) -> int:
    """Convert 'HH:MM' format to minutes since midnight."""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def enrich_sequence_totals(seq: dict) -> None:
    """Compute CBA rig values and ensure TPAY reflects the CBA guarantee.

    Fixes the uniform-TPAY problem: when the PDF's TPAY equals the flat
    5h/duty-day guarantee, we recompute from actual block, duty rig, and
    trip rig so the optimizer can differentiate trips of the same length.

    Safe to call multiple times (idempotent).
    """
    dps = seq.get("duty_periods", [])
    totals = seq.get("totals", {})
    if not totals:
        return

    block = totals.get("block_minutes", 0)
    tafb = totals.get("tafb_minutes", 0)
    duty_days = totals.get("duty_days", len(dps)) or len(dps) or 1

    # ── Compute total on-duty minutes from per-DP data ──
    on_duty_total = 0
    for dp in dps:
        dm = dp.get("duty_minutes", 0)
        if dm:
            on_duty_total += dm
        else:
            # Fallback: compute from report/release times
            rpt_str = dp.get("report_base", "")
            rls_str = dp.get("release_base", "")
            if rpt_str and rls_str and ":" in rpt_str and ":" in rls_str:
                rpt = _colon_time_to_minutes(rpt_str)
                rls = _colon_time_to_minutes(rls_str)
                if rls > rpt:
                    on_duty_total += rls - rpt
                elif rls < rpt:  # crosses midnight
                    on_duty_total += (24 * 60 - rpt) + rls

    # ── CBA rig calculations ──
    # §2.P: duty rig = 1 hour per 2 hours on-duty
    duty_rig = on_duty_total // 2 if on_duty_total else 0
    # §2.AAA: trip rig = 1 hour per 3.5 hours TAFB
    trip_rig = int(tafb / 3.5) if tafb else 0
    # §11.D: minimum guarantee = 5 hours per duty period
    dp_guarantee = 5 * 60 * duty_days

    computed_tpay = max(block, duty_rig, trip_rig, dp_guarantee)

    totals["duty_rig_minutes"] = duty_rig
    totals["trip_rig_minutes"] = trip_rig

    # Only adjust TPAY when it appears to be the flat 5h/day guarantee
    # (or missing entirely).  This targets the uniform-TPAY problem without
    # overriding intentionally varied TPAY values from the bid sheet.
    parsed_tpay = totals.get("tpay_minutes", 0)
    if parsed_tpay == 0 or parsed_tpay == dp_guarantee:
        totals["tpay_minutes"] = max(parsed_tpay, computed_tpay)

    seq["totals"] = totals


def _derive_sequence_fields(seq: dict, config: AirlineConfig = DEFAULT_CONFIG) -> None:
    """Compute derived fields (is_turn, has_deadhead, is_redeye, etc.) in place."""
    dps = seq.get("duty_periods", [])
    has_layover = any(dp.get("layover") for dp in dps)
    seq["is_turn"] = len(dps) == 1 and not has_layover

    seq["has_deadhead"] = any(
        leg.get("is_deadhead", False)
        for dp in dps
        for leg in dp.get("legs", [])
    )

    seq["is_redeye"] = False
    for dp in dps:
        for leg in dp.get("legs", []):
            dep_local = leg.get("departure_local", "")
            arr_local = leg.get("arrival_local", "")
            if dep_local and arr_local:
                dep_hour = int(dep_local[:2])
                arr_hour = int(arr_local[:2])
                if dep_hour >= config.redeye_depart_after and arr_hour < config.redeye_arrive_before:
                    seq["is_redeye"] = True

    layover_cities = []
    for dp in dps:
        lay = dp.get("layover")
        if lay and lay.get("city"):
            if lay["city"] not in layover_cities:
                layover_cities.append(lay["city"])
    seq["layover_cities"] = layover_cities

    totals = seq.get("totals", {})
    leg_count = sum(len(dp.get("legs", [])) for dp in dps)
    deadhead_count = sum(
        1 for dp in dps
        for leg in dp.get("legs", [])
        if leg.get("is_deadhead", False)
    )
    totals["duty_days"] = len(dps)
    totals["leg_count"] = leg_count
    totals["deadhead_count"] = deadhead_count
    seq["totals"] = totals

    # IPD / NIPD classification
    cat = (seq.get("category") or "").upper()
    is_international = "INTL" in cat
    is_widebody_intl = is_international and ("777" in cat or "787" in cat)

    if is_international:
        # Collect all destination stations
        all_stations = set(layover_cities)
        for dp in dps:
            for lg in dp.get("legs", []):
                arr = lg.get("arrival_station", "")
                if arr:
                    all_stations.add(arr)

        has_ipd_dest = bool(all_stations & _IPD_DESTINATION_STATIONS)

        if is_widebody_intl and has_ipd_dest:
            seq["is_ipd"] = True
            seq["is_nipd"] = False
        else:
            seq["is_ipd"] = False
            seq["is_nipd"] = True
    else:
        seq["is_ipd"] = False
        seq["is_nipd"] = False

    # Speaker sequence detection
    seq["is_speaker_sequence"] = seq.get("language") is not None

    # Domestic flag
    seq["is_domestic"] = not is_international

    # Compute rig values and ensure TPAY reflects CBA guarantee
    enrich_sequence_totals(seq)


# ── Main entry point ────────────────────────────────────────────────────────

def parse_bid_sheet(file_path: str, airline_code: Optional[str] = None) -> dict:
    """Parse a bid sheet PDF and return structured data.

    Args:
        file_path: Path to the PDF file.
        airline_code: Optional airline configuration code. Defaults to 'default'.

    Returns:
        Dict with sequences, categories, metadata.
    """
    config = get_airline_config(airline_code)

    all_sequences: list[dict] = []
    categories: set[str] = set()
    issued_date: Optional[str] = None
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    base_city: Optional[str] = None
    current_category: Optional[str] = None

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=5, y_tolerance=5)
            if not text:
                continue

            sequences, page_category, footer_info = _parse_page_text(text, config)

            if page_category:
                current_category = page_category
            if footer_info:
                cat = footer_info["category"]
                categories.add(cat)
                current_category = cat
                if not issued_date:
                    issued_date = footer_info["issued_date"]
                if not effective_start:
                    effective_start = footer_info["effective_start"]
                if not base_city:
                    base_match = config.base_city_pattern.match(cat)
                    if base_match:
                        base_city = base_match.group(1)

            for seq in sequences:
                seq["category"] = current_category
                _derive_sequence_fields(seq, config)

            all_sequences.extend(sequences)

    if effective_start and all_sequences:
        all_op_dates = set()
        for seq in all_sequences:
            all_op_dates.update(seq.get("operating_dates", []))
        if all_op_dates:
            max_date = max(all_op_dates)
            eff_start_dt = datetime.strptime(effective_start, "%Y-%m-%d")
            import calendar
            _, last_day = calendar.monthrange(eff_start_dt.year, eff_start_dt.month)
            effective_end = f"{eff_start_dt.year}-{eff_start_dt.month:02d}-{max_date:02d}"
            total_dates = len(all_op_dates)
        else:
            total_dates = 0
    else:
        total_dates = 0

    return {
        "sequences": all_sequences,
        "categories": sorted(categories),
        "base_city": base_city,
        "issued_date": issued_date,
        "effective_start": effective_start,
        "effective_end": effective_end,
        "total_sequences": len(all_sequences),
        "total_dates": total_dates,
    }


def parse_bid_sheet_text(text: str, airline_code: Optional[str] = None) -> dict:
    """Parse bid sheet from already-extracted text (for testing)."""
    config = get_airline_config(airline_code)
    sequences, category, footer_info = _parse_page_text(text, config)

    categories: set[str] = set()
    issued_date = None
    effective_start = None
    effective_end = None
    base_city = None

    if footer_info:
        cat = footer_info["category"]
        categories.add(cat)
        issued_date = footer_info["issued_date"]
        effective_start = footer_info["effective_start"]
        base_match = config.base_city_pattern.match(cat)
        if base_match:
            base_city = base_match.group(1)

    if category:
        categories.add(category)

    for seq in sequences:
        seq["category"] = category or (footer_info["category"] if footer_info else None)
        _derive_sequence_fields(seq, config)

    if effective_start and sequences:
        all_op_dates = set()
        for seq in sequences:
            all_op_dates.update(seq.get("operating_dates", []))
        if all_op_dates:
            max_date = max(all_op_dates)
            eff_start_dt = datetime.strptime(effective_start, "%Y-%m-%d")
            effective_end = f"{eff_start_dt.year}-{eff_start_dt.month:02d}-{max_date:02d}"
            total_dates = len(all_op_dates)
        else:
            total_dates = 0
    else:
        total_dates = 0

    return {
        "sequences": sequences,
        "categories": sorted(categories),
        "base_city": base_city,
        "issued_date": issued_date,
        "effective_start": effective_start,
        "effective_end": effective_end,
        "total_sequences": len(sequences),
        "total_dates": total_dates,
    }
