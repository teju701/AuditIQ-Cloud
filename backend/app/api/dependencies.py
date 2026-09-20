from __future__ import annotations

from typing import Any

import pandas as pd

from app.aws.auth_service import AuthenticatedUser, get_current_user, verify_dataset_ownership
from app.core.settings import (
    CACHE_ENABLED,
    CACHE_MAX_SIZE,
    CACHE_TTL_SECONDS,
    CACHEABLE_EXECUTION_MODES,
)
from app.engine.query_orchestrator import run_query
from app.services.reproducibility_service import normalize_query
from app.storage.audit_run_store import audit_run_repository
from app.storage.dataset_store import DatasetStore
from app.storage.query_cache import QueryResultCache

dataset_store = DatasetStore()
query_result_cache = QueryResultCache(ttl_seconds=CACHE_TTL_SECONDS, max_size=CACHE_MAX_SIZE)


def cache_meta_disabled(user_query: str, execution_mode: str) -> dict[str, Any]:
    return {
        "hit": False,
        "execution_mode": execution_mode,
        "normalized_query": normalize_query(user_query),
        "cache_key": None,
        "enabled": False,
        "skipped": True,
        "reason": "cache_disabled_by_config",
    }


def cache_meta_skipped(user_query: str, execution_mode: str, reason: str) -> dict[str, Any]:
    return {
        "hit": False,
        "execution_mode": execution_mode,
        "normalized_query": normalize_query(user_query),
        "cache_key": None,
        "enabled": True,
        "skipped": True,
        "reason": reason,
    }


def run_query_with_cache(dataset_hash: str, user_query: str, dataframe: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    if not CACHE_ENABLED:
        fresh_result = run_query(user_query, dataframe)
        execution_mode = str(fresh_result.get("execution_mode", "failed"))
        return fresh_result, cache_meta_disabled(user_query, execution_mode)

    cached_result, cache_meta = query_result_cache.get(dataset_hash, user_query)
    if cached_result is not None:
        cache_meta["enabled"] = True
        cache_meta["skipped"] = False
        return cached_result, cache_meta

    fresh_result = run_query(user_query, dataframe)
    execution_mode = str(fresh_result.get("execution_mode", "failed"))

    if execution_mode not in CACHEABLE_EXECUTION_MODES:
        return fresh_result, cache_meta_skipped(user_query, execution_mode, "execution_mode_not_cacheable")

    cache_meta = query_result_cache.set(dataset_hash, user_query, execution_mode, fresh_result)
    cache_meta["enabled"] = True
    cache_meta["skipped"] = False
    return fresh_result, cache_meta


def parse_positive_int(value: object, default: int) -> int:
    if value is None:
        return default

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if parsed < 1:
        return default

    return parsed
