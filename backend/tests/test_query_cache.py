from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.storage.query_cache import QueryResultCache


class QueryCacheLifecycleTests(unittest.TestCase):
    def test_cache_hit_roundtrip(self) -> None:
        cache = QueryResultCache(ttl_seconds=120, max_size=10)
        payload = {"row_count": 10, "execution_mode": "locked_metric"}

        cache.set("hash-a", "show duplicate gstin", "locked_metric", payload)
        cached, meta = cache.get("hash-a", "show duplicate gstin")

        self.assertIsNotNone(cached)
        self.assertTrue(meta["hit"])
        self.assertEqual(cached["row_count"], 10)

    def test_ttl_expiration(self) -> None:
        cache = QueryResultCache(ttl_seconds=0, max_size=10)
        cache.set("hash-a", "show duplicate gstin", "locked_metric", {"row_count": 10})

        cached, meta = cache.get("hash-a", "show duplicate gstin")

        self.assertIsNone(cached)
        self.assertFalse(meta["hit"])

    def test_max_size_eviction(self) -> None:
        cache = QueryResultCache(ttl_seconds=120, max_size=2)
        cache.set("hash-a", "query one", "safe_plan", {"id": 1})
        cache.set("hash-a", "query two", "safe_plan", {"id": 2})
        cache.set("hash-a", "query three", "safe_plan", {"id": 3})

        first, _ = cache.get("hash-a", "query one")
        second, _ = cache.get("hash-a", "query two")
        third, third_meta = cache.get("hash-a", "query three")

        self.assertIsNone(first)
        self.assertIsNotNone(second)
        self.assertIsNotNone(third)
        self.assertTrue(third_meta["hit"])
        self.assertEqual(cache.count(), 2)

    def test_dataset_invalidation(self) -> None:
        cache = QueryResultCache(ttl_seconds=120, max_size=10)
        cache.set("hash-a", "query one", "safe_plan", {"id": 1})
        cache.set("hash-b", "query one", "safe_plan", {"id": 2})

        removed = cache.invalidate_dataset("hash-a")
        first, _ = cache.get("hash-a", "query one")
        second, second_meta = cache.get("hash-b", "query one")

        self.assertEqual(removed, 1)
        self.assertIsNone(first)
        self.assertIsNotNone(second)
        self.assertTrue(second_meta["hit"])


if __name__ == "__main__":
    unittest.main()
