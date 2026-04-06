"""Parser for APFA PBS base-wide award PDFs.

These are award files showing every FA's awarded schedule at a base,
including sequence numbers, priority layers, positions, and block times.

Format per FA block (between dashed separator lines):
  LINE <N> PAY <HH:MM>  <calendar header>
  <emp_id> TAFB <HH:MM> <day-of-week row>
  <layer> CR. <HH:MM>   <sequence numbers on calendar>
  OFF <N>  DH <HH:MM>   <cities/activity row>
  PRIORITY               P1 P2 ... (one per pairing)
  POSITION               01 02 ... (one per pairing)
  DTY <HH:MM> BLK <HH:MM> <seq=/rpt/rls/blk, ...>

Blocks with "NO PAIRINGS AWARDED" have no PRIORITY/POSITION/DTY rows.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Dashed separator pattern (at least 20 dashes)
_SEP_RE = re.compile(r"^-{20,}$")

# LINE row: "LINE 123 PAY 78:17 ..."
_LINE_RE = re.compile(r"LINE\s+(\d+)\s+PAY\s+(\d+[:.]\d+)")

# Employee / TAFB row: "061765 TAFB 122:03 ..."
_EMP_RE = re.compile(r"^(\d{6})\s+TAFB\s+(\d+[:.]\d+)")

# Layer / credit row: "LN CR. 78:17 ..." or "L1 CR. 78:17 ..."
_LAYER_RE = re.compile(r"^(LN|L[1-7])\s+CR\.\s+(\d+[:.]\d+)")

# OFF / DH row: "OFF 21 DH 0:00 ..."
_OFF_RE = re.compile(r"^OFF\s+(\d+)\s+DH\s+(\d+[:.]\d+)")

# PRIORITY row
_PRIORITY_RE = re.compile(r"^PRIORITY\s+(.+)")

# POSITION row
_POSITION_RE = re.compile(r"^POSITION\s+(.+)")

# DTY/BLK row: "DTY 078:17 BLK 78:17 05338=/0713/1945/1022, ..."
_DTY_RE = re.compile(r"^DTY\s+(\d+[:.]\d+)\s+BLK\s+(\d+[:.]\d+)\s+(.*)")

# Individual pairing in DTY row: "05338=/0713/1945/1022"
# The DTY row uses 5-digit seq numbers — the first digit is a prefix (trip type
# indicator: 0=intl/multi-day, 2=domestic turns, etc.). The actual 4-digit sequence
# number matching bid pool data is the last 4 characters.
_PAIRING_RE = re.compile(r"(\d{5})=/(\d{4})/(\d{4})/(\d{3,5})")

# NO PAIRINGS line
_NO_PAIR_RE = re.compile(r"NO PAIRINGS AWARDED", re.IGNORECASE)

# Stats page markers
_STATS_RE = re.compile(r"^(LINE STATISTICS|Number of open|Total number of|Total P\d|Total PN|Average|Open)")


@dataclass
class AwardedPairing:
    """One pairing from an FA's awarded schedule."""
    seq_number: int
    priority: str = ""          # "P1" through "P7", "PN", "CN"
    position: str = ""          # "01"-"09", "PUR"
    report_time: str = ""       # "0713" (HHMM)
    release_time: str = ""      # "1945" (HHMM)
    block_minutes: int = 0


@dataclass
class AwardedLine:
    """One FA's complete award for the month."""
    line_number: int
    employee_id: str
    layer_label: str            # "LN", "L1", ..., "L7"
    pay_minutes: int = 0
    tafb_minutes: int = 0
    days_off: int = 0
    deadhead_minutes: int = 0
    pairings: list[AwardedPairing] = field(default_factory=list)
    no_pairings: bool = False


@dataclass
class MonthAward:
    """Parsed result from one base-wide award PDF."""
    month: str                  # "2026-01"
    base: str                   # "ORD"
    total_lines: int = 0
    lines: list[AwardedLine] = field(default_factory=list)


def _hhmm_to_minutes(t: str) -> int:
    """Convert 'HH:MM' or 'HH.MM' or 'HHMM' to total minutes."""
    t = t.replace(".", ":")
    if ":" in t:
        parts = t.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    if len(t) == 4 and t.isdigit():
        return int(t[:2]) * 60 + int(t[2:])
    return 0


def _parse_block_minutes(raw: str) -> int:
    """Parse block time from DTY row — could be HH:MM or HHMM."""
    raw = raw.strip()
    if ":" in raw:
        parts = raw.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    if raw.isdigit():
        if len(raw) <= 3:
            # Probably just minutes
            return int(raw)
        # HHMM
        return int(raw[:-2]) * 60 + int(raw[-2:])
    return 0


def _extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF, joining pages."""
    import pdfplumber
    all_lines: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))
    return "\n".join(all_lines)


def parse_award_text(text: str, month: str = "", base: str = "ORD") -> MonthAward:
    """Parse the full text of an award PDF into structured data.

    Args:
        text: Full text extracted from the award PDF.
        month: Month string like "2026-01".
        base: Base airport code.

    Returns:
        MonthAward with all parsed FA lines.
    """
    raw_lines = text.split("\n")

    # Split into blocks between dashed separators.
    # A block is the set of lines between two consecutive separator lines.
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if _SEP_RE.match(stripped):
            if current_block:
                blocks.append(current_block)
                current_block = []
        elif _STATS_RE.match(stripped):
            # Skip stats/summary lines at end
            continue
        else:
            current_block.append(stripped)

    # Don't lose the last block
    if current_block:
        blocks.append(current_block)

    # Parse each block into an AwardedLine
    parsed_lines: list[AwardedLine] = []
    for block in blocks:
        line_obj = _parse_fa_block(block)
        if line_obj is not None:
            parsed_lines.append(line_obj)

    # Detect total_lines from the data
    total = len(parsed_lines)

    award = MonthAward(
        month=month,
        base=base,
        total_lines=total,
        lines=parsed_lines,
    )

    logger.info(
        "Parsed %s %s award: %d lines, %d with pairings",
        base, month, total,
        sum(1 for ln in parsed_lines if not ln.no_pairings),
    )
    return award


def _parse_fa_block(block_lines: list[str]) -> AwardedLine | None:
    """Parse one FA's block of lines into an AwardedLine."""
    if not block_lines:
        return None

    line_number = 0
    employee_id = ""
    layer_label = ""
    pay_minutes = 0
    tafb_minutes = 0
    days_off = 0
    dh_minutes = 0
    no_pairings = False
    priorities: list[str] = []
    positions: list[str] = []
    raw_dty = ""

    for i, raw in enumerate(block_lines):
        # LINE row
        m = _LINE_RE.search(raw)
        if m:
            line_number = int(m.group(1))
            pay_minutes = _hhmm_to_minutes(m.group(2))
            continue

        # Employee / TAFB
        m = _EMP_RE.match(raw)
        if m:
            employee_id = m.group(1)
            tafb_minutes = _hhmm_to_minutes(m.group(2))
            continue

        # Layer / credit
        m = _LAYER_RE.match(raw)
        if m:
            layer_label = m.group(1)
            continue

        # OFF / DH
        m = _OFF_RE.match(raw)
        if m:
            days_off = int(m.group(1))
            dh_minutes = _hhmm_to_minutes(m.group(2))
            continue

        # NO PAIRINGS
        if _NO_PAIR_RE.search(raw):
            no_pairings = True
            continue

        # PRIORITY
        m = _PRIORITY_RE.match(raw)
        if m:
            priorities = m.group(1).split()
            continue

        # POSITION
        m = _POSITION_RE.match(raw)
        if m:
            positions = m.group(1).split()
            continue

        # DTY/BLK row (may span multiple lines in the block)
        m = _DTY_RE.match(raw)
        if m:
            raw_dty = m.group(3)
            # Check if subsequent lines are continuation of DTY (no known prefix)
            for j in range(i + 1, len(block_lines)):
                cont = block_lines[j]
                if (_LINE_RE.search(cont) or _EMP_RE.match(cont) or
                        _LAYER_RE.match(cont) or _OFF_RE.match(cont) or
                        _PRIORITY_RE.match(cont) or _POSITION_RE.match(cont) or
                        _DTY_RE.match(cont) or _NO_PAIR_RE.search(cont) or
                        _SEP_RE.match(cont)):
                    break
                # Continuation line — append
                raw_dty += " " + cont
            continue

    if line_number == 0:
        return None

    # Parse pairings from DTY row
    pairings: list[AwardedPairing] = []
    if raw_dty:
        for pm in _PAIRING_RE.finditer(raw_dty):
            raw_seq = pm.group(1)
            # Strip leading prefix digit — actual 4-digit seq is last 4 chars
            seq_num = int(raw_seq[-4:])
            rpt = pm.group(2)
            rls = pm.group(3)
            blk_raw = pm.group(4)
            blk = _parse_block_minutes(blk_raw)
            pairings.append(AwardedPairing(
                seq_number=seq_num,
                report_time=rpt,
                release_time=rls,
                block_minutes=blk,
            ))

    # Assign priorities and positions to pairings (same order)
    for idx, p in enumerate(pairings):
        if idx < len(priorities):
            p.priority = priorities[idx]
        if idx < len(positions):
            p.position = positions[idx]

    return AwardedLine(
        line_number=line_number,
        employee_id=employee_id,
        layer_label=layer_label,
        pay_minutes=pay_minutes,
        tafb_minutes=tafb_minutes,
        days_off=days_off,
        deadhead_minutes=dh_minutes,
        pairings=pairings,
        no_pairings=no_pairings,
    )


def parse_award_pdf(pdf_path: str, month: str = "", base: str = "ORD") -> MonthAward:
    """Parse a base-wide award PDF file.

    Args:
        pdf_path: Path to the PDF file.
        month: Month string like "2026-01".
        base: Base airport code.

    Returns:
        MonthAward with all parsed FA lines.
    """
    text = _extract_text_from_pdf(pdf_path)
    return parse_award_text(text, month=month, base=base)


def extract_pairing_award_map(award: MonthAward) -> dict[int, list[dict]]:
    """Build a map: seq_number → list of award instances.

    Each instance records which line (seniority) was awarded that seq,
    with priority, position, and block time. Multiple FAs can be awarded
    the same sequence number (different operating dates).

    Returns:
        {seq_number: [{line_number, priority, position, block_minutes, ...}]}
    """
    result: dict[int, list[dict]] = {}
    for fa in award.lines:
        if fa.no_pairings:
            continue
        for p in fa.pairings:
            entry = {
                "line_number": fa.line_number,
                "seniority_pct": fa.line_number / award.total_lines if award.total_lines else 0,
                "priority": p.priority,
                "position": p.position,
                "report_time": p.report_time,
                "release_time": p.release_time,
                "block_minutes": p.block_minutes,
                "layer_label": fa.layer_label,
            }
            result.setdefault(p.seq_number, []).append(entry)
    return result
