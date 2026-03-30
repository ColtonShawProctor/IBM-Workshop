"""CBA scheduling rules — duty time, rest, block limits, days off.

American Airlines / APFA 2024 Collective Bargaining Agreement.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.models.schemas import CBAViolation


# ── Task 64: CBA §11.E — Domestic Duty Time Chart ───────────────────────────
# Key: (report_time_range_start_minutes, report_time_range_end_minutes)
# Value: list of max duty minutes indexed by segment count (idx 0=1seg ... idx 6=7+seg)

_DOMESTIC_CHART: List[Tuple[int, int, List[int]]] = [
    # (start_min, end_min, [1seg, 2seg, 3seg, 4seg, 5seg, 6seg, 7+seg])
    (0,    239,  [555, 555, 555, 555, 555, 555, 555]),    # 0000-0359
    (240,  299,  [615, 615, 615, 615, 555, 555, 555]),    # 0400-0459
    (300,  359,  [735, 735, 735, 735, 705, 675, 645]),    # 0500-0559
    (360,  419,  [795, 795, 735, 735, 735, 705, 645]),    # 0600-0659
    (420,  779,  [795, 795, 795, 795, 795, 765, 705]),    # 0700-1259
    (780,  1019, [735, 735, 735, 735, 705, 675, 645]),    # 1300-1659
    (1020, 1319, [735, 735, 675, 675, 615, 555, 555]),    # 1700-2159
    (1320, 1379, [675, 675, 615, 615, 555, 555, 555]),    # 2200-2259
    (1380, 1439, [615, 615, 615, 555, 555, 555, 555]),    # 2300-2359
]


def get_max_domestic_duty(report_hbt_minutes: int, segment_count: int) -> int:
    """CBA §11.E — Max scheduled domestic duty in minutes.

    Args:
        report_hbt_minutes: report time in minutes from midnight (HBT)
        segment_count: number of flight segments in the duty period
    """
    seg_idx = min(segment_count - 1, 6) if segment_count >= 1 else 0
    for start, end, limits in _DOMESTIC_CHART:
        if start <= report_hbt_minutes <= end:
            return limits[seg_idx]
    # Fallback to most restrictive
    return 555


# CBA §11.F — Actual operations limits by report time
_DOMESTIC_ACTUAL_CHART: List[Tuple[int, int, int, int]] = [
    # (start_min, end_min, rescheduled_max_min, operational_max_min)
    (300,  1019, 795, 900),   # 0500-1659
    (1020, 1379, 735, 780),   # 1700-2259
    (1380, 299,  675, 720),   # 2300-0459 (wraps midnight)
]


def get_max_domestic_actual_duty(report_hbt_minutes: int) -> Tuple[int, int]:
    """CBA §11.F — (rescheduled_max_minutes, operational_max_minutes)."""
    for start, end, resch, ops in _DOMESTIC_ACTUAL_CHART:
        if start <= end:
            if start <= report_hbt_minutes <= end:
                return (resch, ops)
        else:
            # Wraps midnight
            if report_hbt_minutes >= start or report_hbt_minutes <= end:
                return (resch, ops)
    return (675, 720)


# ── Task 65: CBA §14.B/D — International Duty Type ──────────────────────────


def classify_international_duty(
    max_block_minutes: int, scheduled_duty_minutes: int
) -> Optional[str]:
    """CBA §14.B — Classify international duty period by range type.

    Returns one of: non_long_range, mid_range, long_range, extended_long_range, or None.
    """
    if max_block_minutes <= 0:
        return None

    if max_block_minutes > 855:  # >14:15
        return "extended_long_range"
    elif max_block_minutes > 720:  # >12:00 and <=14:15
        return "long_range"
    elif scheduled_duty_minutes > 840:  # >14:00 duty, <=12:00 block
        return "mid_range"
    else:
        return "non_long_range"


_INTL_DUTY_LIMITS: Dict[str, Dict[str, int]] = {
    "non_long_range": {
        "max_scheduled_minutes": 840,
        "max_actual_minutes": 960,
        "max_block_minutes": 720,
    },
    "mid_range": {
        "max_scheduled_minutes": 900,
        "max_actual_minutes": 1020,
        "max_block_minutes": 720,
    },
    "long_range": {
        "max_scheduled_minutes": 960,
        "max_actual_minutes": 1080,
        "max_block_minutes": 855,
    },
    "extended_long_range": {
        "max_scheduled_minutes": 1200,
        "max_actual_minutes": 1380,  # scheduled + 3h
        "max_block_minutes": 9999,   # no explicit block cap
    },
}


def get_intl_duty_limits(duty_type: str) -> Dict[str, int]:
    """CBA §14.D — Return duty limits for an international duty type."""
    return _INTL_DUTY_LIMITS.get(duty_type, _INTL_DUTY_LIMITS["non_long_range"])


# ── Task 66: CBA §11.I/J, §14.H/I — Rest Requirements ──────────────────────


def get_home_base_rest(
    is_ipd: bool, is_international: bool, max_block_minutes: int = 0
) -> int:
    """Return minimum home base rest in minutes.

    CBA §11.I (domestic), §14.H (international).
    """
    if not is_international:
        return 660  # 11h domestic

    if max_block_minutes > 855:  # Extended long-range
        return 2880  # 48h
    elif max_block_minutes > 720:  # Long-range
        return 2160  # 36h
    elif is_ipd:
        return 870  # 14:30
    else:
        return 720  # 12h non-IPD international


def get_layover_rest(is_ipd: bool, is_international: bool) -> int:
    """Return minimum layover rest in minutes.

    CBA §11.J (domestic), §14.I (international).
    """
    if is_ipd:
        return 840  # 14h
    return 600  # 10h for both domestic and non-IPD international


# ── Task 67: CBA §11.B — 7-Day Block Hour Limits ────────────────────────────


def check_seven_day_block_limits(
    sequences: List[dict], is_reserve: bool, bid_period_days: int = 31
) -> List[CBAViolation]:
    """CBA §11.B — Check rolling 7-day block hour windows.

    Each sequence dict must have 'operating_dates' and 'totals.block_minutes'.
    Deadhead block is excluded (per CBA, deadhead doesn't count toward 7-day limit).
    """
    max_block = 35 * 60 if is_reserve else 30 * 60  # 2100 or 1800 minutes
    label = "35h (Reserve)" if is_reserve else "30h (Lineholder)"
    violations: List[CBAViolation] = []

    # Build a day→block_minutes map
    day_block: Dict[int, int] = {}
    for seq in sequences:
        block = seq.get("totals", {}).get("block_minutes", 0)
        dh_count = seq.get("totals", {}).get("deadhead_count", 0)
        # Approximate: exclude deadhead by reducing proportionally
        leg_count = seq.get("totals", {}).get("leg_count", 1) or 1
        if dh_count and leg_count:
            working_ratio = max(0, (leg_count - dh_count)) / leg_count
            block = int(block * working_ratio)
        dates = seq.get("operating_dates", [])
        if dates:
            per_day = block // len(dates)
            for d in dates:
                day_block[d] = day_block.get(d, 0) + per_day

    # Check every 7-day window
    for start_day in range(1, bid_period_days - 5):
        window_days = list(range(start_day, start_day + 7))
        total = sum(day_block.get(d, 0) for d in window_days)
        if total > max_block:
            violations.append(CBAViolation(
                rule="CBA §11.B",
                severity="error",
                message=f"7-day block limit exceeded: {total // 60}h {total % 60}m in days {window_days[0]}-{window_days[-1]} (max {label})",
                affected_dates=window_days,
                affected_sequences=[],
            ))
            break  # Report first violation only to avoid noise

    return violations


# ── Task 68: CBA §11.C, §11.H — Consecutive Days & Min Days Off ─────────────


def check_six_day_limit(
    sequences: List[dict], bid_period_days: int = 31
) -> List[CBAViolation]:
    """CBA §11.C — No more than 6 consecutive duty days without 24h off."""
    violations: List[CBAViolation] = []
    duty_days = set()
    for seq in sequences:
        for d in seq.get("operating_dates", []):
            duty_days.add(d)

    consecutive = 0
    start_of_run = 1
    for day in range(1, bid_period_days + 1):
        if day in duty_days:
            if consecutive == 0:
                start_of_run = day
            consecutive += 1
            if consecutive > 6:
                affected = list(range(start_of_run, day + 1))
                violations.append(CBAViolation(
                    rule="CBA §11.C",
                    severity="error",
                    message=f"More than 6 consecutive duty days without 24h off: days {start_of_run}-{day}",
                    affected_dates=affected,
                    affected_sequences=[],
                ))
                break
        else:
            consecutive = 0

    return violations


def check_minimum_days_off(
    sequences: List[dict],
    bid_period_days: int = 30,
    vacation_days: int = 0,
) -> List[CBAViolation]:
    """CBA §11.H — Lineholders: minimum 11 calendar days off per month."""
    violations: List[CBAViolation] = []
    duty_days = set()
    for seq in sequences:
        for d in seq.get("operating_dates", []):
            duty_days.add(d)

    total_days_off = bid_period_days - len(duty_days)

    # Prorate if vacation >= 7 days
    min_required = 11
    if vacation_days >= 7:
        # Simplified proration: reduce requirement by 1 per 7 vacation days
        min_required = max(8, 11 - (vacation_days // 7))

    if total_days_off < min_required:
        violations.append(CBAViolation(
            rule="CBA §11.H",
            severity="warning",
            message=f"Only {total_days_off} days off, minimum required is {min_required}",
            affected_dates=[],
            affected_sequences=[],
        ))

    return violations


# ── Task 69: CBA §2.EE — Credit Hour Range ──────────────────────────────────

_LINE_BOUNDS = {
    "standard": (4200, 5400),   # 70-90h in minutes
    "high":     (4200, 6600),   # 70-110h
    "low":      (2400, 5400),   # 40-90h
}


def check_credit_hour_range(
    total_credit_minutes: int, line_option: str = "standard"
) -> List[CBAViolation]:
    """CBA §2.EE — Check credit hours against Line of Time bounds."""
    violations: List[CBAViolation] = []
    lo, hi = _LINE_BOUNDS.get(line_option, (4200, 5400))

    if total_credit_minutes < lo:
        hours = total_credit_minutes / 60
        min_h = lo / 60
        violations.append(CBAViolation(
            rule="CBA §2.EE",
            severity="warning",
            message=f"Credit hours {hours:.1f}h below line minimum {min_h:.0f}h ({line_option} option)",
            affected_dates=[],
            affected_sequences=[],
        ))
    elif total_credit_minutes > hi:
        hours = total_credit_minutes / 60
        max_h = hi / 60
        violations.append(CBAViolation(
            rule="CBA §2.EE",
            severity="warning",
            message=f"Credit hours {hours:.1f}h above line maximum {max_h:.0f}h ({line_option} option)",
            affected_dates=[],
            affected_sequences=[],
        ))

    return violations


# ── Task 70: Rest Between Sequences ──────────────────────────────────────────


def _time_str_to_minutes(t: str) -> int:
    """Convert 'HH:MM' to minutes from midnight."""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def check_rest_between_sequences(
    seq_a: dict, seq_b: dict
) -> Optional[CBAViolation]:
    """Check that adequate rest exists between two consecutive sequences.

    seq_a finishes first, seq_b starts next. Both are dicts with duty_periods.
    """
    dps_a = seq_a.get("duty_periods", [])
    dps_b = seq_b.get("duty_periods", [])
    if not dps_a or not dps_b:
        return None

    last_dp_a = dps_a[-1]
    first_dp_b = dps_b[0]

    release_str = last_dp_a.get("release_base", "00:00")
    report_str = first_dp_b.get("report_base", "00:00")

    release_min = _time_str_to_minutes(release_str)
    report_min = _time_str_to_minutes(report_str)

    # Assume seq_b is on the next day if report < release
    if report_min <= release_min:
        rest = (1440 - release_min) + report_min
    else:
        rest = report_min - release_min

    # Determine required rest based on seq_a type
    is_ipd = seq_a.get("is_ipd", False)
    is_intl = is_ipd or seq_a.get("is_nipd", False)
    max_block = 0
    for dp in dps_a:
        for leg in dp.get("legs", []):
            max_block = max(max_block, leg.get("block_minutes", 0))

    required = get_home_base_rest(is_ipd, is_intl, max_block)

    if rest < required:
        seq_a_num = seq_a.get("seq_number", 0)
        seq_b_num = seq_b.get("seq_number", 0)
        return CBAViolation(
            rule="CBA §11.I" if not is_intl else "CBA §14.H",
            severity="error",
            message=(
                f"Insufficient rest between SEQ {seq_a_num} and SEQ {seq_b_num}: "
                f"{rest // 60}h {rest % 60}m available, {required // 60}h {required % 60}m required"
            ),
            affected_dates=[],
            affected_sequences=[seq_a_num, seq_b_num],
        )

    return None
