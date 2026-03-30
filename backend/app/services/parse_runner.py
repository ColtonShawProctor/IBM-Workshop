"""Background task runner for PDF parsing."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.db import get_collection
from app.services.pdf_parser import parse_bid_sheet

logger = logging.getLogger(__name__)

BATCH_SIZE = 20


def run_parse(bid_period_id: str, user_id: str, file_path: str, airline_code: str | None = None) -> None:
    """Parse a bid sheet PDF and store sequences in the database.

    This function is designed to be run as a FastAPI BackgroundTask.

    Args:
        bid_period_id: The ID of the bid period to associate sequences with.
        user_id: The ID of the user who uploaded the file.
        file_path: Path to the uploaded PDF file.
    """
    bid_periods = get_collection("bid_periods")
    sequences_coll = get_collection("sequences")
    now = datetime.now(timezone.utc).isoformat()

    try:
        result = parse_bid_sheet(file_path, airline_code=airline_code)

        # Batch-insert sequences
        seq_docs = []
        for seq_data in result["sequences"]:
            doc = {
                "_id": str(uuid.uuid4()),
                "bid_period_id": bid_period_id,
                "user_id": user_id,
                "seq_number": seq_data["seq_number"],
                "category": seq_data.get("category"),
                "ops_count": seq_data.get("ops_count", 1),
                "position_min": seq_data.get("position_min", 1),
                "position_max": seq_data.get("position_max", 9),
                "language": seq_data.get("language"),
                "language_count": seq_data.get("language_count"),
                "operating_dates": seq_data.get("operating_dates", []),
                "is_turn": seq_data.get("is_turn", False),
                "has_deadhead": seq_data.get("has_deadhead", False),
                "is_redeye": seq_data.get("is_redeye", False),
                "totals": seq_data.get("totals", {}),
                "layover_cities": seq_data.get("layover_cities", []),
                "duty_periods": seq_data.get("duty_periods", []),
                "source": "parsed",
                "created_at": now,
                "updated_at": now,
            }
            seq_docs.append(doc)

            if len(seq_docs) >= BATCH_SIZE:
                sequences_coll.insert_many(seq_docs)
                seq_docs = []

        # Insert remaining
        if seq_docs:
            sequences_coll.insert_many(seq_docs)

        # Update bid period with results
        bid_periods.update_one(
            {"_id": bid_period_id},
            {
                "$set": {
                    "parse_status": "completed",
                    "total_sequences": result["total_sequences"],
                    "categories": result["categories"],
                    "base_city": result["base_city"],
                    "issued_date": result["issued_date"],
                    "total_dates": result.get("total_dates", 0),
                    "updated_at": now,
                }
            },
        )

        logger.info(
            "Parsed %d sequences for bid_period %s",
            result["total_sequences"],
            bid_period_id,
        )

    except Exception as exc:
        logger.exception("Failed to parse bid sheet for bid_period %s", bid_period_id)
        bid_periods.update_one(
            {"_id": bid_period_id},
            {
                "$set": {
                    "parse_status": "failed",
                    "parse_error": str(exc),
                    "updated_at": now,
                }
            },
        )
