"""Monthly award recording routes for holdability calibration.

Endpoints:
  POST   /awards                      — Record a monthly PBS award
  GET    /awards                      — List recorded awards
  GET    /awards/{id}                 — Get a single award record
  DELETE /awards/{id}                 — Delete an award record
  GET    /awards/calibration          — Get calibration results
  GET    /awards/prompt               — Get monthly data entry prompt
  POST   /awards/upload-base-award    — Upload a base-wide award PDF
  GET    /awards/survival-curves      — Get computed survival curves
  GET    /awards/accuracy-check       — Compare predictions vs actual awards
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.db import get_collection
from app.models.schemas import (
    MonthlyAwardInput,
    MonthlyAwardRecord,
    AwardedPairingRecord,
)
from app.services.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/awards", tags=["Awards"])


@router.post("", status_code=201, response_model=MonthlyAwardRecord)
async def record_monthly_award(
    body: MonthlyAwardInput,
    user_id: str = Depends(get_current_user_id),
):
    """Record one month's PBS award results for holdability calibration."""
    users_coll = get_collection("users")
    user_doc = users_coll.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    profile = user_doc.get("profile", {})
    seniority = profile.get("seniority_number")
    total_fas = profile.get("total_base_fas")

    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "_id": record_id,
        "user_id": user_id,
        "month": body.month,
        "seniority_number": seniority,
        "total_base_fas": total_fas,
        "total_credit_minutes": body.total_credit_minutes,
        "line_label": body.line_label,
        "pairings": [p.model_dump() for p in body.pairings],
        "lost_seq_numbers": body.lost_seq_numbers,
        "notes": body.notes,
        "created_at": now,
    }

    awards_coll = get_collection("awards")
    awards_coll.insert_one(doc)

    return MonthlyAwardRecord(id=record_id, **{k: v for k, v in doc.items() if k != "_id"})


@router.get("", response_model=list[MonthlyAwardRecord])
async def list_awards(
    user_id: str = Depends(get_current_user_id),
):
    """List all recorded monthly awards for the current user."""
    awards_coll = get_collection("awards")
    docs = list(awards_coll.find({"user_id": user_id}).sort("month", -1).limit(24))

    records = []
    for doc in docs:
        pairings = [AwardedPairingRecord(**p) for p in doc.get("pairings", [])]
        records.append(MonthlyAwardRecord(
            id=doc["_id"],
            user_id=doc["user_id"],
            month=doc.get("month", ""),
            seniority_number=doc.get("seniority_number"),
            total_base_fas=doc.get("total_base_fas"),
            total_credit_minutes=doc.get("total_credit_minutes", 0),
            line_label=doc.get("line_label", ""),
            pairings=pairings,
            lost_seq_numbers=doc.get("lost_seq_numbers", []),
            notes=doc.get("notes"),
            created_at=doc.get("created_at"),
        ))
    return records


@router.get("/prompt")
async def get_monthly_prompt():
    """Get the monthly data entry prompt text."""
    from app.services.explainer import monthly_entry_prompt
    return {"prompt": monthly_entry_prompt()}


@router.get("/calibration")
async def get_calibration(
    user_id: str = Depends(get_current_user_id),
):
    """Get holdability calibration results from historical award data."""
    from app.services.holdability import (
        MonthlyRecord,
        AwardedPairing,
        calibrate,
    )

    awards_coll = get_collection("awards")
    docs = list(awards_coll.find({"user_id": user_id}).sort("month", 1))

    if not docs:
        return {
            "months_of_data": 0,
            "message": "No award data recorded yet. Use POST /awards to record your monthly PBS awards.",
        }

    # Convert to calibration records
    records = []
    for doc in docs:
        pairings = []
        for p in doc.get("pairings", []):
            pairings.append(AwardedPairing(
                seq_id=str(p.get("seq_number", "")),
                award_code=p.get("award_code", "PN"),
                credit_minutes=p.get("credit_minutes", 0),
                layover_cities=p.get("layover_cities", []),
                duty_days=p.get("duty_days", 0),
            ))
        records.append(MonthlyRecord(
            month=doc.get("month", ""),
            seniority=doc.get("seniority_number", 0) or 0,
            total_base=doc.get("total_base_fas", 0) or 0,
            pairings=pairings,
            total_credit_minutes=doc.get("total_credit_minutes", 0),
            line_label=doc.get("line_label", ""),
            lost_pairings=[str(s) for s in doc.get("lost_seq_numbers", [])],
        ))

    result = calibrate(records)

    return {
        "months_of_data": result.months_of_data,
        "layer_distribution": result.layer_distribution,
        "typical_layer": result.typical_layer,
        "survival_by_trait": result.survival_by_trait,
        "improving": result.improving,
        "stable": result.stable,
    }


@router.delete("/{award_id}", status_code=204)
async def delete_award(
    award_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a monthly award record."""
    awards_coll = get_collection("awards")
    result = awards_coll.delete_one({"_id": award_id, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Award record not found")


# ── Level 3: Base-Wide Award File Endpoints ────────────────────────────────


@router.post("/upload-base-award", status_code=201)
async def upload_base_award(
    file: UploadFile = File(...),
    month: str = Query(..., description="Month in YYYY-MM format"),
    base: str = Query("ORD", description="Base airport code"),
    user_id: str = Depends(get_current_user_id),
):
    """Upload a base-wide APFA PBS award PDF and parse it.

    Parses the award file, stores the parsed data, and triggers
    survival curve rebuild.
    """
    from app.services.award_parser import parse_award_text, extract_pairing_award_map
    from app.services.holdability import build_survival_curves, set_cached_survival_curves

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Read PDF content and extract text
    import pdfplumber
    content = await file.read()
    all_lines: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))

    full_text = "\n".join(all_lines)
    award = parse_award_text(full_text, month=month, base=base)

    if not award.lines:
        raise HTTPException(status_code=422, detail="Could not parse any FA lines from this PDF")

    # Extract pairing map and store
    pmap = extract_pairing_award_map(award)
    all_pairings = []
    for instances in pmap.values():
        all_pairings.extend(instances)

    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "_id": record_id,
        "user_id": user_id,
        "type": "base_award",
        "month": month,
        "base": base,
        "total_lines": award.total_lines,
        "lines_with_pairings": sum(1 for ln in award.lines if not ln.no_pairings),
        "total_pairing_instances": len(all_pairings),
        "unique_sequences": len(pmap),
        "pairing_data": all_pairings,
        "created_at": now,
    }

    base_awards_coll = get_collection("base_awards")
    # Upsert: replace if same month+base already exists
    base_awards_coll.delete_many({"month": month, "base": base, "user_id": user_id})
    base_awards_coll.insert_one(doc)

    # Rebuild survival curves from all stored base awards
    _rebuild_survival_curves(user_id)

    return {
        "id": record_id,
        "month": month,
        "base": base,
        "total_lines": award.total_lines,
        "lines_with_pairings": doc["lines_with_pairings"],
        "total_pairing_instances": len(all_pairings),
        "unique_sequences": len(pmap),
    }


@router.get("/survival-curves")
async def get_survival_curves(
    user_id: str = Depends(get_current_user_id),
):
    """Get the computed empirical survival curves."""
    from app.services.holdability import get_cached_survival_curves

    curves = get_cached_survival_curves()
    if not curves:
        # Try to rebuild from stored data
        curves = _rebuild_survival_curves(user_id)

    if not curves:
        return {
            "status": "no_data",
            "message": "No base-wide award files uploaded yet. Use POST /awards/upload-base-award.",
            "curves": {},
        }

    # Format for API response
    formatted = {}
    for key, curve in curves.items():
        formatted[key] = [{"seniority_pct": p, "survival_rate": s} for p, s in curve]

    return {
        "status": "ok",
        "bucket_count": len(curves),
        "curves": formatted,
    }


@router.get("/accuracy-check")
async def accuracy_check(
    seniority_pct: float = Query(30.0, description="User's seniority percentage (0-100)"),
    user_id: str = Depends(get_current_user_id),
):
    """Compare predicted holdability vs actual award outcomes.

    For each trait bucket, compares the heuristic prediction vs
    empirical survival rate at the user's seniority.
    """
    from app.services.holdability import (
        compute_attainability,
        get_cached_survival_curves,
        lookup_survival,
        holdability_category,
    )

    curves = get_cached_survival_curves()
    if not curves:
        curves = _rebuild_survival_curves(user_id)

    if not curves:
        raise HTTPException(
            status_code=404,
            detail="No survival curve data. Upload base-wide award PDFs first.",
        )

    pct = seniority_pct / 100.0
    seniority_number = int(pct * 2200)  # approximate line number
    total_fas = 2200

    results = []
    for key, curve in sorted(curves.items()):
        # Empirical survival
        empirical = 0.0
        for p, s in curve:
            if abs(p - pct) < 0.03:
                empirical = s
                break

        # Heuristic prediction for this trait bucket
        # Derive approximate desirability from the trait key
        desirability = _estimate_desirability_from_key(key)
        heuristic = compute_attainability(
            seniority_number, total_fas, desirability, 10,
            seniority_percentage=seniority_pct,
        )

        emp_cat = holdability_category(empirical)
        heur_cat = holdability_category(heuristic)

        results.append({
            "trait": key,
            "empirical_survival": round(empirical, 3),
            "heuristic_prediction": round(heuristic, 3),
            "empirical_category": emp_cat,
            "heuristic_category": heur_cat,
            "category_match": emp_cat == heur_cat,
            "error": round(abs(empirical - heuristic), 3),
        })

    # Compute summary metrics
    total = len(results)
    matches = sum(1 for r in results if r["category_match"])
    avg_error = sum(r["error"] for r in results) / total if total else 0

    return {
        "seniority_pct": seniority_pct,
        "total_buckets": total,
        "category_accuracy": round(matches / total, 3) if total else 0,
        "avg_error": round(avg_error, 3),
        "buckets": results,
    }


def _rebuild_survival_curves(user_id: str) -> dict:
    """Rebuild survival curves from stored base award data."""
    from app.services.holdability import build_survival_curves, set_cached_survival_curves

    base_awards_coll = get_collection("base_awards")
    docs = list(base_awards_coll.find({"user_id": user_id}).sort("month", 1))

    if not docs:
        return {}

    award_data = []
    for doc in docs:
        award_data.append({
            "total_lines": doc.get("total_lines", 1),
            "pairings": doc.get("pairing_data", []),
        })

    curves = build_survival_curves(award_data)
    if curves:
        set_cached_survival_curves(curves)
    return curves


def _estimate_desirability_from_key(key: str) -> float:
    """Rough desirability estimate from a trait key for accuracy comparison."""
    d = 0.5
    if "high_credit" in key:
        d += 0.2
    elif "low_credit" in key:
        d -= 0.15
    if "morning" in key:
        d += 0.05
    elif "early" in key:
        d -= 0.1
    elif "afternoon" in key:
        d -= 0.05
    return max(0.0, min(1.0, d))
