"""Airline-specific parser configurations.

Each configuration defines the regex patterns and parsing rules for a specific
airline's bid sheet format.  The default configuration matches the ORD-based
format used during initial development.

To add a new airline, create a new AirlineConfig instance and register it in
AIRLINE_CONFIGS.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class AirlineConfig:
    """Configuration for parsing a specific airline's bid sheet format."""

    airline_code: str
    description: str

    # ── Regex patterns ──────────────────────────────────────────────────
    # Each pattern must define the same named/positional groups as the
    # default config so the parser state machine can extract fields.

    footer_re: re.Pattern[str]
    seq_re: re.Pattern[str]
    rpt_re: re.Pattern[str]
    rls_re: re.Pattern[str]
    ttl_re: re.Pattern[str]
    leg_prefix_re: re.Pattern[str]
    layover_hotel_re: re.Pattern[str]
    layover_transport_re: re.Pattern[str]
    category_line_re: re.Pattern[str]
    dash_re: re.Pattern[str]

    # ── Time format ─────────────────────────────────────────────────────
    time_format: str = "HHMM"        # "HHMM" or "HH:MM"
    duration_format: str = "H.MM"    # "H.MM" or "HH:MM"

    # ── Category patterns for the footer ────────────────────────────────
    base_city_pattern: re.Pattern[str] = field(
        default_factory=lambda: re.compile(r"([A-Z]{3})")
    )

    # ── Scheduling rules ────────────────────────────────────────────────
    redeye_depart_after: int = 21     # hour (24h) — depart after this = red-eye candidate
    redeye_arrive_before: int = 6     # hour (24h) — arrive before this = red-eye

    # ── Deadhead suffix ─────────────────────────────────────────────────
    deadhead_suffix: str = "D"        # suffix on flight number indicating deadhead

    # ── Date format in footer ───────────────────────────────────────────
    date_format: str = "%d%b%Y"       # e.g. "08DEC2025"


# ── Default configuration (United/ORD-style) ────────────────────────────

DEFAULT_CONFIG = AirlineConfig(
    airline_code="default",
    description="Default bid sheet format (United ORD-style)",
    footer_re=re.compile(
        r"F/A\s+ISSUED\s+(\d{2}[A-Z]{3}\d{4})\s+"
        r"EFF\s+(\d{2}[A-Z]{3}\d{4})\s+"
        r"(.+?)\s+PAGE\s+\d+",
    ),
    seq_re=re.compile(
        r"^SEQ\s+(\d+)\s+(\d+)\s+OPS\s+POSN\s+(\d+)\s+THRU\s+(\d+)"
        r"(?:\s+LANG\s+([A-Z]{2})\s+(\d+))?"
    ),
    rpt_re=re.compile(r"^RPT\s+(\d{4})/(\d{4})"),
    rls_re=re.compile(r"^RLS\s+(\d{4})/(\d{4})\s+(.*)"),
    ttl_re=re.compile(r"^TTL\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)"),
    leg_prefix_re=re.compile(
        r"^(\d+)\s+(\d+)/(\d+)\s+(\d+)\s+"
        r"(\d+[A-Z]?)\s+"
        r"([A-Z]{3})\s+"
        r"(\d{4})/(\d{4})"
    ),
    layover_hotel_re=re.compile(
        r"^([A-Z]{3})\s+(.+?)\s+([\d][\d\-\u2013\u2212]+[\d])\s+(\d+\.\d+)$"
    ),
    layover_transport_re=re.compile(
        r"^([A-Z][A-Za-z &]+?)\s+([\d][\d\-\u2013\u2212]+[\d])$"
    ),
    category_line_re=re.compile(
        r"^(ORD\s+(?:777|787|NBI|NBD|MSP\s+NBD|MSP\s+NBI))\s*$"
    ),
    dash_re=re.compile(r"^[\-\u2212\u2013]{5,}"),
)


# ── Registry ────────────────────────────────────────────────────────────

AIRLINE_CONFIGS: dict[str, AirlineConfig] = {
    "default": DEFAULT_CONFIG,
}


def get_airline_config(airline_code: Optional[str] = None) -> AirlineConfig:
    """Return the parser configuration for the given airline.

    Falls back to the default config if airline_code is None or not found.
    """
    if airline_code and airline_code in AIRLINE_CONFIGS:
        return AIRLINE_CONFIGS[airline_code]
    return DEFAULT_CONFIG


def register_airline_config(config: AirlineConfig) -> None:
    """Register a new airline configuration."""
    AIRLINE_CONFIGS[config.airline_code] = config


def list_airline_configs() -> list[dict[str, str]]:
    """Return a list of available airline configurations."""
    return [
        {"code": c.airline_code, "description": c.description}
        for c in AIRLINE_CONFIGS.values()
    ]
