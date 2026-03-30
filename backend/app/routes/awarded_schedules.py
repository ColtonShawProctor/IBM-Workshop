from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.db import get_collection
from app.models.schemas import (
    AwardAnalysis,
    AwardedSchedule,
    AwardedSequenceEntry,
    AttainabilityAccuracy,
    MatchedEntry,
)
from app.services.auth import get_current_user_id

router = APIRouter(
    prefix="/bid-periods/{bid_period_id}",
    tags=["Awarded Schedule"],
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _verify_bid_period(bid_period_id: str, user_id: str) -> dict:
    bp_coll = get_collection("bid_periods")
    doc = bp_coll.find_one({"_id": bid_period_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid period not found")
    return doc


def _doc_to_awarded_schedule(doc: dict) -> AwardedSchedule:
    entries = [
        AwardedSequenceEntry(**e) for e in doc.get("awarded_sequences", [])
    ]
    return AwardedSchedule(
        id=doc["_id"],
        bid_period_id=doc["bid_period_id"],
        bid_id=doc.get("bid_id"),
        source_filename=doc.get("source_filename"),
        imported_at=doc.get("imported_at"),
        awarded_sequences=entries,
    )


def _parse_awarded_file(content: str) -> list[dict]:
    """Parse awarded schedule from a CSV or plain-text file.

    Supported formats:
    1. CSV with headers: seq_number, operating_dates, tpay_minutes, block_minutes, tafb_minutes
    2. Simple text: one sequence number per line (minimal data)
    """
    lines = content.strip().splitlines()
    if not lines:
        return []

    # Try CSV parsing first
    try:
        reader = csv.DictReader(io.StringIO(content))
        fields = reader.fieldnames or []
        if "seq_number" in fields:
            entries = []
            for row in reader:
                dates_raw = row.get("operating_dates", "")
                if dates_raw:
                    operating_dates = [int(d.strip()) for d in dates_raw.split(";") if d.strip()]
                else:
                    operating_dates = []
                entries.append({
                    "seq_number": int(row["seq_number"]),
                    "sequence_id": row.get("sequence_id") or None,
                    "operating_dates": operating_dates,
                    "tpay_minutes": int(row.get("tpay_minutes", 0) or 0),
                    "block_minutes": int(row.get("block_minutes", 0) or 0),
                    "tafb_minutes": int(row.get("tafb_minutes", 0) or 0),
                })
            return entries
    except (KeyError, ValueError):
        pass

    # Fallback: one seq_number per line
    entries = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"(\d+)", line)
        if match:
            entries.append({
                "seq_number": int(match.group(1)),
                "sequence_id": None,
                "operating_dates": [],
                "tpay_minutes": 0,
                "block_minutes": 0,
                "tafb_minutes": 0,
            })
    return entries


def _enrich_awarded_entries(
    entries: list[dict], bid_period_id: str, user_id: str
) -> list[dict]:
    """Match awarded seq_numbers to sequences in the bid period and fill in missing data."""
    if not entries:
        return entries

    seq_coll = get_collection("sequences")
    seq_numbers = [e["seq_number"] for e in entries]

    # Fetch all matching sequences in one query
    seq_docs = list(seq_coll.find({
        "bid_period_id": bid_period_id,
        "user_id": user_id,
        "seq_number": {"$in": seq_numbers},
    }))
    seq_by_number: dict[int, dict] = {}
    for s in seq_docs:
        seq_by_number[s["seq_number"]] = s

    for entry in entries:
        matched_seq = seq_by_number.get(entry["seq_number"])
        if matched_seq:
            entry["sequence_id"] = matched_seq["_id"]
            # Fill in missing data from the parsed sequence
            if not entry["operating_dates"]:
                entry["operating_dates"] = matched_seq.get("operating_dates", [])
            totals = matched_seq.get("totals", {})
            if entry["tpay_minutes"] == 0:
                entry["tpay_minutes"] = totals.get("tpay_minutes", 0)
            if entry["block_minutes"] == 0:
                entry["block_minutes"] = totals.get("block_minutes", 0)
            if entry["tafb_minutes"] == 0:
                entry["tafb_minutes"] = totals.get("tafb_minutes", 0)

    return entries


# ── Task 21: Awarded Schedule Import + GET ──────────────────────────────────


@router.post("/awarded-schedule", status_code=201, response_model=AwardedSchedule)
async def import_awarded_schedule(
    bid_period_id: str,
    file: UploadFile = File(...),
    bid_id: Optional[str] = Form(default=None),
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    # Validate bid_id if provided
    if bid_id:
        bid_coll = get_collection("bids")
        bid_doc = bid_coll.find_one({"_id": bid_id, "bid_period_id": bid_period_id, "user_id": user_id})
        if not bid_doc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bid not found in this period")

    # Read and parse the uploaded file
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must be UTF-8 text (CSV or plain text)",
        )

    entries = _parse_awarded_file(content)
    if not entries:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No awarded sequences found in file",
        )

    # Enrich with sequence data from bid period
    entries = _enrich_awarded_entries(entries, bid_period_id, user_id)

    now = datetime.now(timezone.utc).isoformat()
    doc_id = str(uuid.uuid4())
    doc = {
        "_id": doc_id,
        "bid_period_id": bid_period_id,
        "user_id": user_id,
        "bid_id": bid_id,
        "source_filename": file.filename,
        "imported_at": now,
        "awarded_sequences": entries,
    }

    as_coll = get_collection("awarded_schedules")
    as_coll.insert_one(doc)

    return _doc_to_awarded_schedule(doc)


@router.get("/awarded-schedule", response_model=AwardedSchedule)
async def get_awarded_schedule(
    bid_period_id: str,
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    as_coll = get_collection("awarded_schedules")
    # Return the most recent awarded schedule for this bid period
    docs = list(as_coll.find({"bid_period_id": bid_period_id, "user_id": user_id}))
    if not docs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No awarded schedule found")

    docs.sort(key=lambda d: d.get("imported_at", ""), reverse=True)
    return _doc_to_awarded_schedule(docs[0])


# ── Task 22: Award Analysis Endpoint ───────────────────────────────────────


def _compute_analysis(
    awarded_doc: dict, bid_doc: dict
) -> AwardAnalysis:
    """Compare awarded sequences against a bid to produce analysis."""
    awarded_seqs = awarded_doc.get("awarded_sequences", [])
    bid_entries = bid_doc.get("entries", [])

    awarded_seq_numbers = {e["seq_number"] for e in awarded_seqs}

    # Build lookup from bid entries: seq_number → entry
    bid_by_seq = {}
    for entry in bid_entries:
        if not entry.get("is_excluded", False):
            bid_by_seq[entry.get("seq_number", 0)] = entry

    # Matched entries: all bid entries with was_awarded flag
    matched_entries: list[MatchedEntry] = []
    match_count = 0
    top_10_match_count = 0

    for entry in bid_entries:
        if entry.get("is_excluded", False):
            continue
        sn = entry.get("seq_number", 0)
        was_awarded = sn in awarded_seq_numbers
        if was_awarded:
            match_count += 1
            if entry.get("rank", 999) <= 10:
                top_10_match_count += 1
        matched_entries.append(MatchedEntry(
            seq_number=sn,
            bid_rank=entry.get("rank", 0),
            was_awarded=was_awarded,
            attainability=entry.get("attainability", "unknown"),
        ))

    # Unmatched awards: sequences awarded but not in the bid
    unmatched_awards = sorted(
        sn for sn in awarded_seq_numbers if sn not in bid_by_seq
    )

    # Attainability accuracy
    high_awarded = 0
    high_total = 0
    low_awarded = 0
    low_total = 0
    for entry in matched_entries:
        if entry.attainability == "high":
            high_total += 1
            if entry.was_awarded:
                high_awarded += 1
        elif entry.attainability == "low":
            low_total += 1
            if entry.was_awarded:
                low_awarded += 1

    total_non_excluded = len([e for e in bid_entries if not e.get("is_excluded", False)])
    top_10_total = min(10, total_non_excluded)

    match_rate = match_count / total_non_excluded if total_non_excluded else 0.0
    top_10_match_rate = top_10_match_count / top_10_total if top_10_total else 0.0

    # Generate insights
    insights = _generate_insights(
        match_count=match_count,
        match_rate=match_rate,
        top_10_match_count=top_10_match_count,
        top_10_match_rate=top_10_match_rate,
        high_awarded=high_awarded,
        high_total=high_total,
        low_awarded=low_awarded,
        low_total=low_total,
        unmatched_awards=unmatched_awards,
        awarded_seqs=awarded_seqs,
        matched_entries=matched_entries,
    )

    return AwardAnalysis(
        bid_id=bid_doc["_id"],
        awarded_schedule_id=awarded_doc["_id"],
        match_count=match_count,
        match_rate=round(match_rate, 4),
        top_10_match_count=top_10_match_count,
        top_10_match_rate=round(top_10_match_rate, 4),
        matched_entries=matched_entries,
        unmatched_awards=unmatched_awards,
        attainability_accuracy=AttainabilityAccuracy(
            high_awarded=high_awarded,
            high_total=high_total,
            low_awarded=low_awarded,
            low_total=low_total,
        ),
        insights=insights,
    )


def _generate_insights(
    *,
    match_count: int,
    match_rate: float,
    top_10_match_count: int,
    top_10_match_rate: float,
    high_awarded: int,
    high_total: int,
    low_awarded: int,
    low_total: int,
    unmatched_awards: list[int],
    awarded_seqs: list[dict],
    matched_entries: list[MatchedEntry],
) -> list[str]:
    """Generate human-readable insights about bid-vs-award performance."""
    insights: list[str] = []

    # Top-level match rate
    total_awarded = len(awarded_seqs)
    if total_awarded:
        insights.append(
            f"{match_count} of your {total_awarded} awarded sequence(s) were in your bid."
        )

    if top_10_match_count:
        insights.append(
            f"{top_10_match_count} of your top 10 picks were awarded "
            f"({top_10_match_rate:.0%} hit rate)."
        )

    # Attainability model accuracy
    if high_total:
        high_rate = high_awarded / high_total
        insights.append(
            f"{high_awarded} of {high_total} sequences marked 'high' attainability "
            f"were awarded ({high_rate:.0%} accuracy)."
        )

    if low_awarded > 0:
        insights.append(
            f"Surprise: {low_awarded} sequence(s) marked 'low' attainability were "
            f"actually awarded — your seniority may be more competitive than estimated."
        )
    elif low_total > 0:
        insights.append(
            "No 'low' attainability sequences were awarded, confirming "
            "the seniority model was accurate for contested sequences."
        )

    # Unmatched awards
    if unmatched_awards:
        nums = ", ".join(str(n) for n in unmatched_awards[:5])
        suffix = f" and {len(unmatched_awards) - 5} more" if len(unmatched_awards) > 5 else ""
        insights.append(
            f"Sequence(s) {nums}{suffix} were awarded but not in your bid. "
            "Consider including similar sequences next month."
        )

    # Awards from bottom half of bid
    if matched_entries:
        total = len(matched_entries)
        bottom_half_awards = sum(
            1 for e in matched_entries
            if e.was_awarded and e.bid_rank > total // 2
        )
        if bottom_half_awards > 0:
            insights.append(
                f"{bottom_half_awards} award(s) came from the bottom half of your bid. "
                "This suggests good depth of coverage in your ranking strategy."
            )

    return insights


@router.get("/award-analysis", response_model=AwardAnalysis)
async def get_award_analysis(
    bid_period_id: str,
    bid_id: Optional[str] = Query(default=None),
    user_id: str = Depends(get_current_user_id),
):
    _verify_bid_period(bid_period_id, user_id)

    # Get the awarded schedule
    as_coll = get_collection("awarded_schedules")
    awarded_docs = list(as_coll.find({"bid_period_id": bid_period_id, "user_id": user_id}))
    if not awarded_docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No awarded schedule found for this bid period",
        )
    awarded_docs.sort(key=lambda d: d.get("imported_at", ""), reverse=True)
    awarded_doc = awarded_docs[0]

    # Get the bid to compare against
    bid_coll = get_collection("bids")
    if bid_id:
        bid_doc = bid_coll.find_one({"_id": bid_id, "bid_period_id": bid_period_id, "user_id": user_id})
        if not bid_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")
    else:
        # Default to the bid linked in the awarded schedule, or the most recent finalized bid
        if awarded_doc.get("bid_id"):
            bid_doc = bid_coll.find_one({
                "_id": awarded_doc["bid_id"],
                "bid_period_id": bid_period_id,
                "user_id": user_id,
            })
        else:
            bid_doc = None

        if not bid_doc:
            # Fall back to the most recent finalized or exported bid
            bid_docs = list(bid_coll.find({
                "bid_period_id": bid_period_id,
                "user_id": user_id,
                "status": {"$in": ["finalized", "exported"]},
            }))
            if not bid_docs:
                # Fall back to any bid
                bid_docs = list(bid_coll.find({
                    "bid_period_id": bid_period_id,
                    "user_id": user_id,
                }))
            if not bid_docs:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No bid found to compare against",
                )
            bid_docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
            bid_doc = bid_docs[0]

    return _compute_analysis(awarded_doc, bid_doc)
