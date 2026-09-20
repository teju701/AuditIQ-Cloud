from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd


def _safe_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _plan_signature(plan_payload: dict[str, Any] | None) -> str:
    return hashlib.sha256(_safe_json(plan_payload or {}).encode("utf-8")).hexdigest()


def _row_hashes(df: pd.DataFrame | None, max_rows: int = 500) -> set[str]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return set()

    working = df.copy()
    working = working.head(max_rows)
    working = working.reindex(sorted(working.columns), axis=1)

    hashes: set[str] = set()
    for record in working.fillna("").astype(str).to_dict(orient="records"):
        row_payload = _safe_json(record)
        hashes.add(hashlib.sha256(row_payload.encode("utf-8")).hexdigest())
    return hashes


def _jaccard_similarity_pct(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 100.0
    union = left | right
    if not union:
        return 100.0
    intersection = left & right
    return round((len(intersection) / len(union)) * 100.0, 2)


def _row_count_similarity_pct(left_count: int, right_count: int) -> float:
    top = max(left_count, right_count)
    if top == 0:
        return 100.0
    gap = abs(left_count - right_count)
    return round((1 - (gap / top)) * 100.0, 2)


def _status_from_score(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def build_consensus_report(
    primary_plan: dict[str, Any] | None,
    secondary_plan: dict[str, Any] | None,
    primary_result_df: pd.DataFrame | None,
    secondary_result_df: pd.DataFrame | None,
    secondary_error: str | None = None,
) -> dict[str, Any]:
    if secondary_error:
        return {
            "enabled": True,
            "status": "low",
            "score": 25.0,
            "reason": f"Secondary consensus run failed: {secondary_error}",
            "plan_match": False,
            "plan_similarity_pct": 0.0,
            "row_overlap_pct": 0.0,
            "row_count_similarity_pct": 0.0,
            "primary_row_count": int(len(primary_result_df)) if isinstance(primary_result_df, pd.DataFrame) else 0,
            "secondary_row_count": int(len(secondary_result_df)) if isinstance(secondary_result_df, pd.DataFrame) else 0,
            "primary_plan_hash": _plan_signature(primary_plan),
            "secondary_plan_hash": _plan_signature(secondary_plan),
        }

    primary_signature = _plan_signature(primary_plan)
    secondary_signature = _plan_signature(secondary_plan)

    plan_match = primary_signature == secondary_signature
    plan_similarity_pct = 100.0 if plan_match else 40.0

    primary_hashes = _row_hashes(primary_result_df)
    secondary_hashes = _row_hashes(secondary_result_df)

    row_overlap_pct = _jaccard_similarity_pct(primary_hashes, secondary_hashes)
    primary_count = int(len(primary_result_df)) if isinstance(primary_result_df, pd.DataFrame) else 0
    secondary_count = int(len(secondary_result_df)) if isinstance(secondary_result_df, pd.DataFrame) else 0
    row_count_similarity_pct = _row_count_similarity_pct(primary_count, secondary_count)

    # Weighted blend prioritizes evidence agreement.
    score = round(
        (0.25 * plan_similarity_pct) +
        (0.50 * row_overlap_pct) +
        (0.25 * row_count_similarity_pct),
        2,
    )
    status = _status_from_score(score)

    if status == "high":
        reason = "Primary and secondary runs strongly agree on evidence and counts."
    elif status == "medium":
        reason = "Primary and secondary runs partially agree; review before relying on fine-grained claims."
    else:
        reason = "Primary and secondary runs diverge significantly; analyst review is recommended."

    return {
        "enabled": True,
        "status": status,
        "score": score,
        "reason": reason,
        "plan_match": plan_match,
        "plan_similarity_pct": plan_similarity_pct,
        "row_overlap_pct": row_overlap_pct,
        "row_count_similarity_pct": row_count_similarity_pct,
        "primary_row_count": primary_count,
        "secondary_row_count": secondary_count,
        "primary_plan_hash": primary_signature,
        "secondary_plan_hash": secondary_signature,
    }


def single_path_consensus(execution_mode: str, reason: str) -> dict[str, Any]:
    score = 100.0 if execution_mode in {"locked_metric", "safe_plan"} else 0.0
    status = "high" if score >= 80 else "low"
    return {
        "enabled": False,
        "status": status,
        "score": score,
        "reason": reason,
        "plan_match": True,
        "plan_similarity_pct": 100.0 if score > 0 else 0.0,
        "row_overlap_pct": 100.0 if score > 0 else 0.0,
        "row_count_similarity_pct": 100.0 if score > 0 else 0.0,
        "primary_row_count": None,
        "secondary_row_count": None,
        "primary_plan_hash": None,
        "secondary_plan_hash": None,
    }
