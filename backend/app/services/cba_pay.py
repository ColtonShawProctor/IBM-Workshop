"""CBA §3 — Compensation calculations for American Airlines / APFA 2024 CBA."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

# ── CBA §3.A Pay Scale ───────────────────────────────────────────────────────
# Rows: years of service (1–13). Columns: effective dates.
# Rates in dollars per credited hour.

EFFECTIVE_DATES: List[date] = [
    date(2024, 10, 1),
    date(2025, 10, 1),
    date(2026, 10, 1),
    date(2027, 10, 1),
    date(2028, 10, 1),
]

# PAY_TABLE[years_of_service] = [rate_2024, rate_2025, rate_2026, rate_2027, rate_2028]
PAY_TABLE: Dict[int, List[float]] = {
    1:  [35.82, 36.81, 37.91, 39.05, 40.42],
    2:  [37.97, 39.01, 40.18, 41.39, 42.84],
    3:  [40.40, 41.51, 42.76, 44.04, 45.58],
    4:  [43.03, 44.21, 45.54, 46.91, 48.55],
    5:  [47.39, 48.69, 50.15, 51.65, 53.46],
    6:  [53.67, 55.15, 56.80, 58.50, 60.55],
    7:  [59.21, 60.84, 62.67, 64.55, 66.81],
    8:  [61.11, 62.79, 64.67, 66.61, 68.94],
    9:  [62.80, 64.53, 66.47, 68.46, 70.86],
    10: [65.15, 66.94, 68.95, 71.02, 73.51],
    11: [66.94, 68.78, 70.84, 72.97, 75.52],
    12: [70.12, 72.05, 74.21, 76.44, 79.12],
    13: [82.24, 84.50, 87.04, 89.65, 92.79],
}


def get_hourly_rate(years_of_service: int, effective_date: date) -> float:
    """Return the hourly rate in dollars for the given years and date.

    CBA §3.A — selects the rate for the most recent effective date <= given date.
    Years capped at range 1–13 (years >13 use 13th year rate).
    """
    yos = max(1, min(years_of_service, 13))
    rates = PAY_TABLE[yos]

    # Find the most recent effective date <= given date
    idx = 0
    for i, ed in enumerate(EFFECTIVE_DATES):
        if ed <= effective_date:
            idx = i
        else:
            break

    return rates[idx]


# ── CBA §2.P, §2.AAA, §11.D — Rig Calculations ─────────────────────────────


def calc_duty_rig(on_duty_minutes: int) -> int:
    """CBA §2.P — 1 hour per 2 hours on-duty, prorated minute-by-minute."""
    return on_duty_minutes // 2


def calc_trip_rig(tafb_minutes: int) -> int:
    """CBA §2.AAA — 1 hour per 3 hours 30 minutes TAFB, prorated."""
    return int(tafb_minutes / 3.5)


def calc_sit_rig(sit_minutes: int) -> int:
    """CBA §11.D.5 — For sit times >2:30, 1 min pay per 2 min excess of 2:30.

    Does NOT apply to ODANs. Returns 0 if sit_minutes <= 150.
    """
    if sit_minutes <= 150:
        return 0
    excess = sit_minutes - 150
    return excess // 2


def calc_sequence_guarantee(
    block_minutes: int,
    duty_rig_minutes: int,
    trip_rig_minutes: int,
    duty_period_count: int,
) -> int:
    """CBA §11.D — Return credited minutes as the greatest of:

    1. Actual block time
    2. Duty Rig
    3. Trip Rig
    4. 5 hours × duty periods (but multi-DP sequences get min 3h per DP)
    """
    if duty_period_count > 1:
        dp_guarantee = max(5 * 60 * duty_period_count, 3 * 60 * duty_period_count)
    else:
        dp_guarantee = 5 * 60  # single DP = 5 hours

    return max(block_minutes, duty_rig_minutes, trip_rig_minutes, dp_guarantee)


# ── CBA §3.C — Position Premiums ─────────────────────────────────────────────

# POSITION_PREMIUMS[(position, aircraft, is_ipd)] = hourly premium in dollars
# Simplified from CBA §3.C table. Key: (position, aircraft_family)
# aircraft_family derived from equipment code.

_DOMESTIC_PREMIUMS: Dict[Tuple[str, str], float] = {
    ("lead", "B737"):   3.25,
    ("lead", "A319"):   3.25,
    ("lead", "A320"):   3.25,
    ("lead", "A321"):   3.25,
    ("lead", "A321T"):  4.75,
    ("lead", "A321XLR"):3.25,
    ("lead", "B777"):   3.25,
    ("lead", "B787"):   3.25,
    ("purser", "A321T"):5.75,
    ("purser", "B777"): 5.75,
    ("galley", "A321T"):1.00,
    ("galley", "A321XLR"):1.00,
    ("galley", "B777"): 1.00,
    ("galley", "B787"): 1.00,
}

_INTL_NIPD_PREMIUMS: Dict[Tuple[str, str], float] = {
    ("lead", "B737"):   3.25,
    ("lead", "A319"):   3.25,
    ("lead", "A321"):   3.25,
    ("lead", "A321XLR"):3.75,
    ("lead", "B777"):   6.50,
    ("lead", "B787"):   6.50,
}

_INTL_IPD_PREMIUMS: Dict[Tuple[str, str], float] = {
    ("purser", "B777"): 7.50,
    ("purser", "B787"): 7.50,
    ("galley", "A321XLR"):2.00,
    ("galley", "B777"): 2.00,
    ("galley", "B787"): 2.00,
}


def get_position_premium(
    position: str,
    aircraft_type: str,
    is_international: bool,
    is_ipd: bool,
) -> float:
    """CBA §3.C — Return hourly premium in dollars for a position.

    position: "lead", "purser", or "galley"
    aircraft_type: e.g. "B777", "B787", "A321T"
    Returns 0.0 for non-premium positions or unmatched combos.
    """
    key = (position.lower(), aircraft_type)
    if is_ipd:
        return _INTL_IPD_PREMIUMS.get(key, _INTL_NIPD_PREMIUMS.get(key, _DOMESTIC_PREMIUMS.get(key, 0.0)))
    elif is_international:
        return _INTL_NIPD_PREMIUMS.get(key, _DOMESTIC_PREMIUMS.get(key, 0.0))
    else:
        return _DOMESTIC_PREMIUMS.get(key, 0.0)


# ── CBA §3.G — International Premium ─────────────────────────────────────────


def get_international_premium(is_ipd: bool, is_nipd: bool) -> float:
    """CBA §3.G — Return hourly international premium in dollars."""
    if is_ipd:
        return 3.75
    elif is_nipd:
        return 3.00
    return 0.0


# ── CBA §3.J — Foreign Language Speaker Premium ──────────────────────────────


def get_speaker_premium(is_international: bool, is_ipd: bool) -> float:
    """CBA §3.J — Return hourly speaker premium in dollars.

    $2.00/hr domestic, $5.00/hr NIPD international, $5.75/hr IPD.
    """
    if is_ipd:
        return 5.75
    elif is_international:
        return 5.00
    return 2.00


# ── CBA §3.K — Holiday Detection ─────────────────────────────────────────────


def _thanksgiving_date(year: int) -> int:
    """Return the day-of-month of Thanksgiving (4th Thursday of November)."""
    # Nov 1 weekday: 0=Mon .. 6=Sun
    nov1_weekday = date(year, 11, 1).weekday()
    # Thursday = 3
    first_thursday = 1 + (3 - nov1_weekday) % 7
    fourth_thursday = first_thursday + 21
    return fourth_thursday


def get_holiday_dates(year: int, month: int) -> List[int]:
    """CBA §3.K — Return day-of-month integers that are holidays in the given month.

    Holidays:
    - Wed before Thanksgiving, Thanksgiving Day, Sun after, Mon after
    - Dec 24, 25, 26, 31
    - Jan 1
    """
    holidays: List[int] = []

    if month == 11:
        thx = _thanksgiving_date(year)
        holidays.append(thx - 1)  # Wed before
        holidays.append(thx)      # Thanksgiving Day (Thu)
        sun_after = thx + 3       # Sun after
        if sun_after <= 30:
            holidays.append(sun_after)
        mon_after = thx + 4       # Mon after
        if mon_after <= 30:
            holidays.append(mon_after)
    elif month == 12:
        # Mon after Thanksgiving may fall in December
        thx = _thanksgiving_date(year)
        mon_after = thx + 4
        if mon_after > 30:  # Falls in December
            holidays.append(mon_after - 30)
        holidays.extend([24, 25, 26, 31])
    elif month == 1:
        holidays.append(1)

    return sorted(holidays)


def is_holiday(year: int, month: int, day: int) -> bool:
    """CBA §3.K — Check if a specific date is a CBA holiday."""
    return day in get_holiday_dates(year, month)


# ── Task 63: Full Sequence Pay Estimator ─────────────────────────────────────


def estimate_sequence_pay(
    sequence: dict,
    years_of_service: int,
    effective_date: date,
    position: Optional[str] = None,
    is_speaker: bool = False,
) -> Dict[str, int]:
    """Estimate total compensation for a sequence in cents.

    Args:
        sequence: dict with keys matching Sequence model (totals, is_ipd, is_nipd, etc.)
        years_of_service: FA's years for pay rate lookup
        effective_date: date for pay rate lookup
        position: "lead", "purser", "galley", or None
        is_speaker: whether the FA is a language speaker on this sequence

    Returns dict with all pay components and total, in cents.
    """
    hourly_rate = get_hourly_rate(years_of_service, effective_date)
    totals = sequence.get("totals", {})
    block = totals.get("block_minutes", 0)
    tafb = totals.get("tafb_minutes", 0)
    duty_days = totals.get("duty_days", 0) or 1

    # Compute on-duty minutes from duty periods if available
    on_duty = 0
    dps = sequence.get("duty_periods", [])
    for dp in dps:
        dm = dp.get("duty_minutes")
        if dm:
            on_duty += dm

    # Rig calculations
    duty_rig = calc_duty_rig(on_duty) if on_duty else 0
    trip_rig = calc_trip_rig(tafb)
    guarantee = calc_sequence_guarantee(block, duty_rig, trip_rig, max(duty_days, len(dps) or 1))

    # Base pay in cents
    base_pay_cents = int(round(guarantee / 60.0 * hourly_rate * 100))
    duty_rig_cents = int(round(duty_rig / 60.0 * hourly_rate * 100))
    trip_rig_cents = int(round(trip_rig / 60.0 * hourly_rate * 100))
    guarantee_cents = base_pay_cents

    # International premium
    is_ipd = sequence.get("is_ipd", False)
    is_nipd = sequence.get("is_nipd", False)
    intl_rate = get_international_premium(is_ipd, is_nipd)
    intl_premium_cents = int(round(guarantee / 60.0 * intl_rate * 100))

    # Speaker premium
    speaker_premium_cents = 0
    if is_speaker and sequence.get("is_speaker_sequence", False):
        sp_rate = get_speaker_premium(is_ipd or is_nipd, is_ipd)
        speaker_premium_cents = int(round(guarantee / 60.0 * sp_rate * 100))

    # Position premium
    position_premium_cents = 0
    if position:
        # Use first leg's equipment to determine aircraft type
        aircraft = "B777"  # default
        if dps:
            legs = dps[0].get("legs", [])
            if legs:
                aircraft = legs[0].get("equipment", "B777")
        pos_rate = get_position_premium(position, aircraft, is_ipd or is_nipd, is_ipd)
        position_premium_cents = int(round(guarantee / 60.0 * pos_rate * 100))

    # Holiday premium (100% of base rate for holiday hours — simplified as full sequence)
    holiday_premium_cents = 0
    if sequence.get("has_holiday", False):
        holiday_premium_cents = base_pay_cents  # 100% premium

    total_cents = (
        guarantee_cents
        + intl_premium_cents
        + speaker_premium_cents
        + position_premium_cents
        + holiday_premium_cents
    )

    return {
        "base_pay_cents": base_pay_cents,
        "duty_rig_cents": duty_rig_cents,
        "trip_rig_cents": trip_rig_cents,
        "guarantee_cents": guarantee_cents,
        "international_premium_cents": intl_premium_cents,
        "speaker_premium_cents": speaker_premium_cents,
        "position_premium_cents": position_premium_cents,
        "holiday_premium_cents": holiday_premium_cents,
        "total_cents": total_cents,
    }
