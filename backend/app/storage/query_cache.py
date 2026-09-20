from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import time
from typing import Any

from app.services.reproducibility_service import normalize_query


@dataclass
class _CacheEntry:
    dataset_hash: str
    query_key: str
    execution_mode: str
    created_at_epoch: float
    result: dict[str, Any]


class QueryResultCache:
    def __init__(self, ttl_seconds: int = 900, max_size: int = 500) -> None:
        self.ttl_seconds = max(0, int(ttl_seconds))
        self.max_size = max(1, int(max_size))

        self._cache: dict[str, _CacheEntry] = {}
        self._query_index: dict[str, str] = {}

        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._expiration_count = 0
        self._invalidation_count = 0

    def _query_key(self, dataset_hash: str, user_query: str) -> str:
        normalized = normalize_query(user_query)
        payload = f"{dataset_hash}|{normalized}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _full_key(self, dataset_hash: str, user_query: str, execution_mode: str) -> str:
        query_key = self._query_key(dataset_hash, user_query)
        payload = f"{query_key}|{execution_mode}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _entry_is_expired(self, created_at_epoch: float, now_epoch: float) -> bool:
        if self.ttl_seconds == 0:
            return True
        return (now_epoch - created_at_epoch) > self.ttl_seconds

    def _remove_cache_entry(self, full_key: str) -> bool:
        entry = self._cache.pop(full_key, None)
        if entry is None:
            return False

        indexed_full_key = self._query_index.get(entry.query_key)
        if indexed_full_key == full_key:
            self._query_index.pop(entry.query_key, None)
        return True

    def _evict_expired_entries(self) -> int:
        now_epoch = time.time()
        to_remove: list[str] = []
        for full_key, entry in self._cache.items():
            if self._entry_is_expired(entry.created_at_epoch, now_epoch):
                to_remove.append(full_key)

        removed = 0
        for full_key in to_remove:
            if self._remove_cache_entry(full_key):
                removed += 1

        if removed:
            self._expiration_count += removed

        return removed

    def _evict_if_oversized(self) -> int:
        if len(self._cache) <= self.max_size:
            return 0

        # Evict oldest entries first until size is within limit.
        ordered = sorted(self._cache.items(), key=lambda item: item[1].created_at_epoch)
        to_evict = len(self._cache) - self.max_size
        removed = 0
        for full_key, _ in ordered[:to_evict]:
            if self._remove_cache_entry(full_key):
                removed += 1

        if removed:
            self._eviction_count += removed

        return removed

    def _cache_miss_meta(self, dataset_hash: str, user_query: str) -> dict[str, Any]:
        query_key = self._query_key(dataset_hash, user_query)
        return {
            "hit": False,
            "execution_mode": None,
            "normalized_query": normalize_query(user_query),
            "cache_key": query_key,
        }

    def get(self, dataset_hash: str, user_query: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        self._evict_expired_entries()

        query_key = self._query_key(dataset_hash, user_query)
        full_key = self._query_index.get(query_key)
        if not full_key:
            self._miss_count += 1
            return None, self._cache_miss_meta(dataset_hash, user_query)

        entry = self._cache.get(full_key)
        if entry is None:
            self._query_index.pop(query_key, None)
            self._miss_count += 1
            return None, self._cache_miss_meta(dataset_hash, user_query)

        if self._entry_is_expired(entry.created_at_epoch, time.time()):
            self._remove_cache_entry(full_key)
            self._expiration_count += 1
            self._miss_count += 1
            return None, self._cache_miss_meta(dataset_hash, user_query)

        self._hit_count += 1
        return copy.deepcopy(entry.result), {
            "hit": True,
            "execution_mode": entry.execution_mode,
            "normalized_query": normalize_query(user_query),
            "cache_key": query_key,
        }

    def set(self, dataset_hash: str, user_query: str, execution_mode: str, result: dict[str, Any]) -> dict[str, Any]:
        self._evict_expired_entries()

        query_key = self._query_key(dataset_hash, user_query)
        full_key = self._full_key(dataset_hash, user_query, execution_mode)

        # Remove stale entry for the same normalized query key if execution mode changed.
        existing_full_key = self._query_index.get(query_key)
        if existing_full_key and existing_full_key != full_key:
            self._remove_cache_entry(existing_full_key)

        self._cache[full_key] = _CacheEntry(
            dataset_hash=dataset_hash,
            query_key=query_key,
            execution_mode=execution_mode,
            created_at_epoch=time.time(),
            result=copy.deepcopy(result),
        )
        self._query_index[query_key] = full_key

        self._evict_if_oversized()

        return {
            "hit": False,
            "execution_mode": execution_mode,
            "normalized_query": normalize_query(user_query),
            "cache_key": query_key,
        }

    def invalidate_dataset(self, dataset_hash: str) -> int:
        target = str(dataset_hash).strip()
        if not target:
            return 0

        to_remove = [
            full_key
            for full_key, entry in self._cache.items()
            if entry.dataset_hash == target
        ]

        removed = 0
        for full_key in to_remove:
            if self._remove_cache_entry(full_key):
                removed += 1

        if removed:
            self._invalidation_count += removed

        return removed

    def clear(self) -> int:
        removed = len(self._cache)
        self._cache.clear()
        self._query_index.clear()
        if removed:
            self._invalidation_count += removed
        return removed

    def count(self) -> int:
        self._evict_expired_entries()
        return len(self._cache)

    def dump_stats(self) -> dict[str, Any]:
        self._evict_expired_entries()
        return {
            "ttl_seconds": self.ttl_seconds,
            "max_size": self.max_size,
            "cached_results": len(self._cache),
            "query_index_entries": len(self._query_index),
            "hits": self._hit_count,
            "misses": self._miss_count,
            "evictions": self._eviction_count,
            "expirations": self._expiration_count,
            "invalidations": self._invalidation_count,
        }
