from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.dependencies import dataset_store, query_result_cache
from app.core.settings import CACHE_ENABLED, CACHE_MAX_SIZE, CACHE_TTL_SECONDS


router = APIRouter(tags=["cache"])


@router.post("/cache/invalidate")
async def invalidate_cache(body: dict | None = None):
    payload = body or {}

    if not CACHE_ENABLED:
        return {
            "scope": "disabled",
            "removed_entries": 0,
            "cache": {
                "enabled": False,
                "ttl_seconds": CACHE_TTL_SECONDS,
                "max_size": CACHE_MAX_SIZE,
            },
        }

    dataset_id = str(payload.get("dataset_id", "")).strip()
    dataset_hash = str(payload.get("dataset_hash", "")).strip()

    if dataset_id:
        session = dataset_store.get_dataset(dataset_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Dataset session not found. Please upload again.")
        dataset_hash = session.dataset_hash

    if dataset_hash:
        removed = query_result_cache.invalidate_dataset(dataset_hash)
        return {
            "scope": "dataset",
            "dataset_hash": dataset_hash,
            "removed_entries": removed,
            "cache": query_result_cache.dump_stats(),
        }

    removed = query_result_cache.clear()
    return {
        "scope": "all",
        "removed_entries": removed,
        "cache": query_result_cache.dump_stats(),
    }
