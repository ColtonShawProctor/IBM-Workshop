"""Unified CBA validator — combines all CBA rule checks into a single result.

American Airlines / APFA 2024 Collective Bargaining Agreement.
"""

from __future__ import annotations

from typing import List

from app.models.schemas import (
    CBAValidationResult,
    CBAViolation,
    CreditHourSummary,
    DaysOffSummary,
)
from app.services.cba_rules import (
    check_seven_day_block_limits,
    check_six_day_limit,
    check_minimum_days_off,
    check_credit_hour_range,
    check_rest_between_sequences,
)


_LINE_BOUNDS = {
    "standard": (70, 90),
    "high":     (70, 110),
    "low":      (40, 90),
}


def validate_bid(
    sequences: List[dict],
    line_option: str = "standard",
    is_reserve: bool = False,
    bid_period_days: int = 30,
    vacation_days: int = 0,
) -> CBAValidationResult:
    """Run all CBA checks and return a unified validation result.

    Args:
        sequences: list of sequence dicts (with operating_dates, totals, duty_periods, etc.)
        line_option: "standard", "high", or "low"
        is_reserve: True for Reserve, False for Lineholder
        bid_period_days: total days in the bid period
        vacation_days: vacation days (for proration of days-off minimum)

    Returns:
        CBAValidationResult with all violations aggregated.
    """
    all_violations: List[CBAViolation] = []

    # 1. 7-day block hour limits (CBA §11.B)
    all_violations.extend(
        check_seven_day_block_limits(sequences, is_reserve, bid_period_days)
    )

    # 2. 6-consecutive-day limit (CBA §11.C)
    all_violations.extend(
        check_six_day_limit(sequences, bid_period_days)
    )

    # 3. Minimum days off (CBA §11.H) — Lineholders only
    if not is_reserve:
        all_violations.extend(
            check_minimum_days_off(sequences, bid_period_days, vacation_days)
        )

    # 4. Credit hour range (CBA §2.EE)
    total_credit_minutes = sum(
        s.get("totals", {}).get("tpay_minutes", 0) for s in sequences
    )
    all_violations.extend(
        check_credit_hour_range(total_credit_minutes, line_option)
    )

    # 5. Rest between consecutive sequences (CBA §11.I/J, §14.H/I)
    # Sort sequences by first operating date
    sorted_seqs = sorted(sequences, key=lambda s: min(s.get("operating_dates", [999])))
    for i in range(len(sorted_seqs) - 1):
        violation = check_rest_between_sequences(sorted_seqs[i], sorted_seqs[i + 1])
        if violation:
            all_violations.append(violation)

    # Compute summaries
    lo_h, hi_h = _LINE_BOUNDS.get(line_option, (70, 90))
    credit_hours = total_credit_minutes / 60.0

    credit_summary = CreditHourSummary(
        estimated_credit_hours=round(credit_hours, 1),
        line_min=lo_h,
        line_max=hi_h,
        within_range=(lo_h <= credit_hours <= hi_h),
    )

    duty_days_set = set()
    for s in sequences:
        for d in s.get("operating_dates", []):
            duty_days_set.add(d)
    total_days_off = bid_period_days - len(duty_days_set)
    min_required = 11 if not is_reserve else 0

    days_off_summary = DaysOffSummary(
        total_days_off=total_days_off,
        minimum_required=min_required,
        meets_requirement=(total_days_off >= min_required),
    )

    return CBAValidationResult(
        is_valid=(len(all_violations) == 0),
        violations=all_violations,
        credit_hour_summary=credit_summary,
        days_off_summary=days_off_summary,
    )
