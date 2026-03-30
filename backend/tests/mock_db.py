"""In-memory mock for Astra DB collections used in tests."""
from __future__ import annotations

import copy
from typing import Any, Optional
from unittest.mock import MagicMock


class MockCollection:
    """Minimal in-memory document store that mirrors the Astra Collection API."""

    def __init__(self, name: str):
        self.name = name
        self._docs: dict[str, dict] = {}

    def insert_one(self, doc: dict) -> MagicMock:
        key = doc.get("_id", str(len(self._docs)))
        self._docs[key] = copy.deepcopy(doc)
        result = MagicMock()
        result.inserted_id = key
        return result

    def insert_many(self, docs: list[dict]) -> MagicMock:
        ids = []
        for d in docs:
            r = self.insert_one(d)
            ids.append(r.inserted_id)
        result = MagicMock()
        result.inserted_ids = ids
        return result

    def find_one(self, filter_dict: Optional[dict] = None, **kwargs) -> Optional[dict]:
        for doc in self._docs.values():
            if self._matches(doc, filter_dict or {}):
                return copy.deepcopy(doc)
        return None

    def find(self, filter_dict: Optional[dict] = None, *, sort: Optional[dict] = None, limit: Optional[int] = None, **kwargs):
        results = []
        for doc in self._docs.values():
            if self._matches(doc, filter_dict or {}):
                results.append(copy.deepcopy(doc))
        if limit:
            results = results[:limit]
        return results

    def update_one(self, filter_dict: dict, update: dict) -> MagicMock:
        for key, doc in self._docs.items():
            if self._matches(doc, filter_dict):
                if "$set" in update:
                    for k, v in update["$set"].items():
                        self._set_nested(doc, k, v)
                result = MagicMock()
                result.matched_count = 1
                result.modified_count = 1
                return result
        result = MagicMock()
        result.matched_count = 0
        result.modified_count = 0
        return result

    def delete_one(self, filter_dict: dict) -> MagicMock:
        for key, doc in list(self._docs.items()):
            if self._matches(doc, filter_dict):
                del self._docs[key]
                result = MagicMock()
                result.deleted_count = 1
                return result
        result = MagicMock()
        result.deleted_count = 0
        return result

    def delete_many(self, filter_dict: dict) -> MagicMock:
        to_del = [k for k, d in self._docs.items() if self._matches(d, filter_dict)]
        for k in to_del:
            del self._docs[k]
        result = MagicMock()
        result.deleted_count = len(to_del)
        return result

    def count_documents(self, filter_dict: Optional[dict] = None, **kwargs) -> int:
        return sum(1 for d in self._docs.values() if self._matches(d, filter_dict or {}))

    def _matches(self, doc: dict, filt: dict) -> bool:
        for k, v in filt.items():
            if k.startswith("$"):
                continue
            val = self._get_nested(doc, k)
            if isinstance(v, dict):
                for op, operand in v.items():
                    if op == "$gte" and not (val is not None and val >= operand):
                        return False
                    if op == "$lte" and not (val is not None and val <= operand):
                        return False
                    if op == "$in" and val not in operand:
                        return False
            else:
                if val != v:
                    return False
        return True

    def _get_nested(self, doc: dict, key: str) -> Any:
        parts = key.split(".")
        cur = doc
        for p in parts:
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                return None
        return cur

    def _set_nested(self, doc: dict, key: str, value: Any):
        parts = key.split(".")
        cur = doc
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value


_collections: dict[str, MockCollection] = {}


def get_mock_collection(name: str) -> MockCollection:
    if name not in _collections:
        _collections[name] = MockCollection(name)
    return _collections[name]


def reset_mock_db():
    _collections.clear()
