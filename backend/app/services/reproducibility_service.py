from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


def normalize_query(query: str) -> str:
    text = (query or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def hash_query(query: str) -> str:
    normalized = normalize_query(query)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def hash_plan(plan_payload: Any) -> str:
    if isinstance(plan_payload, str):
        try:
            parsed = json.loads(plan_payload)
            serialized = json.dumps(parsed, sort_keys=True, separators=(",", ":"), default=str)
        except json.JSONDecodeError:
            serialized = plan_payload
    else:
        serialized = json.dumps(plan_payload, sort_keys=True, separators=(",", ":"), default=str)

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_reproducibility_manifest(
    dataset_id: str,
    dataset_hash: str,
    user_query: str,
    plan_payload: Any,
    execution_mode: str,
    row_count: int,
) -> tuple[dict[str, Any], str]:
    normalized_query = normalize_query(user_query)
    query_hash = hash_query(user_query)
    plan_hash = hash_plan(plan_payload)
    generated_at = datetime.now(timezone.utc).isoformat()

    manifest: dict[str, Any] = {
        "dataset_id": dataset_id,
        "dataset_hash": dataset_hash,
        "normalized_query": normalized_query,
        "query_hash": query_hash,
        "plan_hash": plan_hash,
        "execution_mode": execution_mode,
        "row_count": row_count,
        "generated_at": generated_at,
    }

    replay_seed = json.dumps(
        {
            "dataset_id": dataset_id,
            "dataset_hash": dataset_hash,
            "query_hash": query_hash,
            "plan_hash": plan_hash,
            "execution_mode": execution_mode,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    replay_id = hashlib.sha256(replay_seed.encode("utf-8")).hexdigest()[:16]

    return manifest, replay_id
