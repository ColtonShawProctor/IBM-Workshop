"""Commute impact analysis for flight attendants who commute to their base city.

Analyzes whether sequences are feasible for commuters based on first-day report
times, last-day release times, and gaps between consecutive sequences.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Commute windows: (commute_from, base_city) -> timing data.
# first_arrival_minutes: earliest a commuter can arrive at base (minutes from midnight)
# last_departure_minutes: latest flight from base back to commute city
# flight_time_minutes: approximate one-way flight time
COMMUTE_WINDOWS: Dict[tuple, Dict[str, int]] = {
    ("DCA", "ORD"): {"first_arrival_minutes": 510, "last_departure_minutes": 1200, "flight_time_minutes": 120},
    ("DEN", "ORD"): {"first_arrival_minutes": 540, "last_departure_minutes": 1170, "flight_time_minutes": 150},
    ("LAX", "ORD"): {"first_arrival_minutes": 600, "last_departure_minutes": 1140, "flight_time_minutes": 240},
    ("ATL", "ORD"): {"first_arrival_minutes": 510, "last_departure_minutes": 1200, "flight_time_minutes": 120},
    ("SFO", "ORD"): {"first_arrival_minutes": 600, "last_departure_minutes": 1140, "flight_time_minutes": 255},
    ("BOS", "ORD"): {"first_arrival_minutes": 540, "last_departure_minutes": 1200, "flight_time_minutes": 165},
    ("MIA", "ORD"): {"first_arrival_minutes": 540, "last_departure_minutes": 1170, "flight_time_minutes": 195},
    ("DFW", "ORD"): {"first_arrival_minutes": 510, "last_departure_minutes": 1200, "flight_time_minutes": 150},
    ("PHX", "ORD"): {"first_arrival_minutes": 570, "last_departure_minutes": 1170, "flight_time_minutes": 210},
    ("SEA", "ORD"): {"first_arrival_minutes": 630, "last_departure_minutes": 1110, "flight_time_minutes": 270},
    # Reverse pairs for bases other than ORD
    ("ORD", "DCA"): {"first_arrival_minutes": 510, "last_departure_minutes": 1200, "flight_time_minutes": 120},
    ("ORD", "DFW"): {"first_arrival_minutes": 510, "last_departure_minutes": 1200, "flight_time_minutes": 150},
    ("ORD", "MIA"): {"first_arrival_minutes": 540, "last_departure_minutes": 1170, "flight_time_minutes": 195},
}

# Conservative fallback for unknown city pairs
DEFAULT_COMMUTE_WINDOW: Dict[str, int] = {
    "first_arrival_minutes": 600,   # 10:00
    "last_departure_minutes": 1080, # 18:00
    "flight_time_minutes": 180,     # 3 hours
}

REPORT_BUFFER_MINUTES = 60   # Must arrive this many min before report
RELEASE_BUFFER_MINUTES = 90  # Must be released this many min before last flight
YELLOW_MARGIN_MINUTES = 30   # Within this margin of threshold = "yellow"


def _get_commute_window(commute_from: str, base_city: str) -> Dict[str, int]:
    """Look up commute window for a city pair, falling back to defaults."""
    return COMMUTE_WINDOWS.get(
        (commute_from.upper(), base_city.upper()),
        DEFAULT_COMMUTE_WINDOW,
    )


def _parse_hhmm(time_str: str) -> int:
    """Convert 'HH:MM' string to minutes from midnight."""
    parts = time_str.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


def analyze_commute_impact(
    sequence: Any,
    commute_from: str,
    base_city: str,
) -> Dict[str, Any]:
    """Analyze commute feasibility for a single sequence.

    Args:
        sequence: A Sequence model or dict with duty_periods containing
                  report_base / release_base as 'HH:MM' strings.
        commute_from: IATA code of the city the FA commutes from.
        base_city: IATA code of the FA's base city.

    Returns:
        Dict with first_day_feasible, first_day_note, last_day_feasible,
        last_day_note, hotel_nights_needed, impact_level.
    """
    window = _get_commute_window(commute_from, base_city)
    first_arrival = window["first_arrival_minutes"]
    last_departure = window["last_departure_minutes"]

    # Extract first report and last release from duty periods
    duty_periods = _get_duty_periods(sequence)
    if not duty_periods:
        return _empty_impact()

    first_dp = duty_periods[0]
    last_dp = duty_periods[-1]

    first_report = _get_report_base_minutes(first_dp)
    last_release = _get_release_base_minutes(last_dp)

    # First day analysis
    threshold_first = first_arrival + REPORT_BUFFER_MINUTES
    first_day_feasible = first_report >= threshold_first
    first_day_margin = first_report - threshold_first

    arrival_hhmm = f"{first_arrival // 60:02d}:{first_arrival % 60:02d}"
    report_hhmm = f"{first_report // 60:02d}:{first_report % 60:02d}"

    if first_day_feasible:
        first_day_note = (
            f"Report {report_hhmm} — easy commute "
            f"(earliest {commute_from}→{base_city} arrives {arrival_hhmm})"
        )
    else:
        first_day_note = (
            f"Report {report_hhmm} — hotel night needed "
            f"(earliest {commute_from}→{base_city} arrives {arrival_hhmm})"
        )

    # Last day analysis
    threshold_last = last_departure - RELEASE_BUFFER_MINUTES
    last_day_feasible = last_release <= threshold_last
    last_day_margin = threshold_last - last_release

    release_hhmm = f"{last_release // 60:02d}:{last_release % 60:02d}"

    if last_day_feasible:
        last_day_note = f"Release {release_hhmm} — easy commute home"
    else:
        last_day_note = (
            f"Release {release_hhmm} — hotel night needed "
            f"(last {base_city}→{commute_from} departs "
            f"{last_departure // 60:02d}:{last_departure % 60:02d})"
        )

    # Hotel nights
    hotel_nights = 0
    if not first_day_feasible:
        hotel_nights += 1
    if not last_day_feasible:
        hotel_nights += 1

    # Impact level
    if hotel_nights > 0:
        impact_level = "red"
    elif first_day_margin < YELLOW_MARGIN_MINUTES or last_day_margin < YELLOW_MARGIN_MINUTES:
        impact_level = "yellow"
    else:
        impact_level = "green"

    return {
        "first_day_feasible": first_day_feasible,
        "first_day_note": first_day_note,
        "last_day_feasible": last_day_feasible,
        "last_day_note": last_day_note,
        "hotel_nights_needed": hotel_nights,
        "impact_level": impact_level,
    }


def analyze_commute_gap(
    seq_a_release_minutes: int,
    seq_b_report_minutes: int,
    gap_hours: float,
    commute_from: str,
    base_city: str,
) -> Dict[str, Any]:
    """Analyze whether there's time to commute home between two consecutive sequences.

    Minimum viable gap = 2 * flight_time + 2h buffer + 8h sleep.

    Args:
        seq_a_release_minutes: Release time of first sequence (minutes from midnight).
        seq_b_report_minutes: Report time of next sequence (minutes from midnight).
        gap_hours: Hours between the two sequences (may span multiple days).
        commute_from: IATA code of commute city.
        base_city: IATA code of base city.

    Returns:
        Dict with can_go_home, gap_hours, note.
    """
    window = _get_commute_window(commute_from, base_city)
    flight_time = window["flight_time_minutes"]

    # Need: fly home + sleep + fly back
    min_gap_minutes = 2 * flight_time + 120 + 480  # 2 * flight + 2h buffer + 8h sleep

    gap_minutes = gap_hours * 60
    can_go_home = gap_minutes >= min_gap_minutes

    if can_go_home:
        note = (
            f"{gap_hours:.1f}h gap — enough time to commute home to {commute_from} "
            f"and back"
        )
    else:
        min_hours = min_gap_minutes / 60
        note = (
            f"{gap_hours:.1f}h gap — insufficient to commute home to {commute_from} "
            f"(need ~{min_hours:.0f}h for round-trip + rest)"
        )

    return {
        "can_go_home": can_go_home,
        "gap_hours": gap_hours,
        "note": note,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_duty_periods(sequence: Any) -> list:
    """Extract duty_periods from a Sequence model or dict."""
    if hasattr(sequence, "duty_periods"):
        return sequence.duty_periods
    if isinstance(sequence, dict):
        return sequence.get("duty_periods", [])
    return []


def _get_report_base_minutes(dp: Any) -> int:
    """Get report_base as minutes from midnight from a DutyPeriod model or dict."""
    if hasattr(dp, "report_base"):
        return _parse_hhmm(dp.report_base)
    if isinstance(dp, dict):
        return _parse_hhmm(dp.get("report_base", "00:00"))
    return 0


def _get_release_base_minutes(dp: Any) -> int:
    """Get release_base as minutes from midnight from a DutyPeriod model or dict."""
    if hasattr(dp, "release_base"):
        return _parse_hhmm(dp.release_base)
    if isinstance(dp, dict):
        return _parse_hhmm(dp.get("release_base", "00:00"))
    return 0


def _empty_impact() -> Dict[str, Any]:
    """Return a neutral commute impact when no duty periods exist."""
    return {
        "first_day_feasible": True,
        "first_day_note": "No duty periods — commute impact unknown",
        "last_day_feasible": True,
        "last_day_note": "No duty periods — commute impact unknown",
        "hotel_nights_needed": 0,
        "impact_level": "green",
    }
