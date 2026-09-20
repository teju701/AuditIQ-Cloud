from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    audit_run_repository,
    dataset_store,
    get_current_user,
    parse_positive_int,
    run_query_with_cache,
)
from app.aws.auth_service import AuthenticatedUser
from app.core.settings import DEFAULT_QUERY_PAGE_SIZE, MAX_QUERY_PAGE_SIZE
from app.services.reproducibility_service import build_reproducibility_manifest
from app.services.trust_service import compute_trust_score

router = APIRouter(tags=["query"])


@router.post("/query")
async def query_data(
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
):
    dataset_id = str(body.get("dataset_id", "")).strip()
    if not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id is required. Upload a dataset first.")

    session = dataset_store.get_dataset(dataset_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Dataset session not found. Please upload again.")

    # Prevent IDOR access
    if session.user_id and session.user_id != user.user_id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have access to this dataset.",
        )

    user_query = str(body.get("query", "")).strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    requested_page = parse_positive_int(body.get("page"), 1)
    requested_page_size = parse_positive_int(body.get("page_size"), DEFAULT_QUERY_PAGE_SIZE)
    page_size = min(requested_page_size, MAX_QUERY_PAGE_SIZE)

    result, cache_meta = run_query_with_cache(session.dataset_hash, user_query, session.dataframe)
    trust = compute_trust_score(result)

    manifest, replay_id = build_reproducibility_manifest(
        dataset_id=session.dataset_id,
        dataset_hash=session.dataset_hash,
        user_query=user_query,
        plan_payload=result.get("pandas_code"),
        execution_mode=result.get("execution_mode", "failed"),
        row_count=result.get("row_count", 0),
    )

    total_rows = int(result.get("row_count", 0))
    total_pages = max(1, math.ceil(total_rows / page_size)) if total_rows > 0 else 1
    page = min(requested_page, total_pages)

    result_records = []
    if result.get("result_df") is not None:
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        result_records = result["result_df"].iloc[start_index:end_index].fillna("").to_dict("records")

    agent_trace = result.get("agent_trace", [])

    # Persistent Audit Run Record in DynamoDB and S3
    persisted_run = audit_run_repository.save_audit_run(
        user_id=user.user_id,
        dataset_id=session.dataset_id,
        user_query=user_query,
        normalized_query=manifest.get("normalized_query", user_query),
        intent=result.get("plan_intent", "filter"),
        execution_mode=result.get("execution_mode", "failed"),
        matched_metric=result.get("metric_used"),
        finding=result.get("narrative", ""),
        confidence=result.get("confidence", "medium"),
        confidence_reason=result.get("confidence_reason", ""),
        trust_score=trust.get("score", 0),
        trust_level=trust.get("level", "LOW"),
        grounding_status=result.get("narrative_grounding", {}).get("status", "unknown"),
        consensus_status=result.get("consensus", {}).get("status", "unknown"),
        replay_id=replay_id,
        query_hash=manifest.get("query_hash", ""),
        plan_hash=manifest.get("plan_hash", ""),
        dataset_hash=session.dataset_hash,
        evidence_count=total_rows,
        result_payload={
            "narrative": result.get("narrative"),
            "logic_explanation": result.get("logic_explanation"),
            "evidence_sample": result_records[:20],
            "total_rows": total_rows,
            "columns": list(result["result_df"].columns) if result.get("result_df") is not None else [],
        },
        agent_trace=agent_trace,
    )

    return {
        "run_id": persisted_run.get("run_id"),
        "dataset_id": session.dataset_id,
        "dataset_hash": session.dataset_hash,
        "replay_id": replay_id,
        "reproducibility": manifest,
        "cache": cache_meta,
        "provenance": result.get("provenance", {}),
        "narrative_grounding": result.get("narrative_grounding", {}),
        "metric_resolution": result.get("metric_resolution", {}),
        "consensus": result.get("consensus", {}),
        "narrative": result["narrative"],
        "logic_explanation": result["logic_explanation"],
        "used_locked_metric": result["used_locked_metric"],
        "metric_used": result.get("metric_used"),
        "confidence": result["confidence"],
        "plan_intent": result.get("plan_intent"),
        "execution_mode": result.get("execution_mode"),
        "row_count": result["row_count"],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
        "trust": trust,
        "result_records": result_records,
        "columns": list(result["result_df"].columns) if result.get("result_df") is not None else [],
        "agent_trace": agent_trace,
    }
