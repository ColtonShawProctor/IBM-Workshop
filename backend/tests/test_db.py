from __future__ import annotations

from app.db import COLLECTION_NAMES


def test_all_seven_collections_defined():
    assert len(COLLECTION_NAMES) == 7
    expected = {"users", "bid_periods", "sequences", "bids", "bookmarks", "filter_presets", "awarded_schedules"}
    assert set(COLLECTION_NAMES) == expected
