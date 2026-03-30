from __future__ import annotations

from functools import lru_cache
from typing import Optional

from astrapy import DataAPIClient, Database, Collection

from app.config import settings

COLLECTION_NAMES = [
    "users",
    "bid_periods",
    "sequences",
    "bids",
    "bookmarks",
    "filter_presets",
    "awarded_schedules",
]


@lru_cache(maxsize=1)
def get_database() -> Database:
    client = DataAPIClient(settings.astra_db_token)
    return client.get_database_by_api_endpoint(
        settings.astra_db_api_endpoint,
        keyspace=settings.astra_db_keyspace,
    )


def get_collection(name: str) -> Collection:
    assert name in COLLECTION_NAMES, f"Unknown collection: {name}"
    db = get_database()
    return db.get_collection(name)


def init_collections() -> list[str]:
    """Create all collections if they don't already exist. Returns names created."""
    db = get_database()
    existing = {c.name for c in db.list_collections()}
    created: list[str] = []
    for name in COLLECTION_NAMES:
        if name not in existing:
            db.create_collection(name)
            created.append(name)
    return created
