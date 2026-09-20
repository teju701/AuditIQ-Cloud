from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
from uuid import uuid4

from app.aws.dynamodb_service import dynamodb_service
from app.aws.s3_service import s3_service

logger = logging.getLogger("auditiq.storage.audit_runs")


class AuditRunRepository:
    def __init__(self) -> None:
        pass

    def save_audit_run(
        self,
        user_id: str,
        dataset_id: str,
        user_query: str,
        normalized_query: str,
        intent: str,
        execution_mode: str,
        matched_metric: str | None,
        finding: str,
        confidence: str,
        confidence_reason: str,
        trust_score: float | int,
        trust_level: str,
        grounding_status: str,
        consensus_status: str,
        replay_id: str,
        query_hash: str,
        plan_hash: str,
        dataset_hash: str,
        evidence_count: int,
        result_payload: dict[str, Any],
        agent_trace: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        run_id = f"run_{uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()

        # 1. Store full result & evidence in S3 to prevent DynamoDB item size overflow
        s3_payload = {
            "run_id": run_id,
            "user_id": user_id,
            "dataset_id": dataset_id,
            "query": user_query,
            "finding": finding,
            "result": result_payload,
            "agent_trace": agent_trace or [],
            "created_at": created_at,
        }
        result_s3_key = s3_service.save_audit_result(user_id, dataset_id, run_id, s3_payload)

        # 2. Store indexed metadata in DynamoDB
        dynamo_item = {
            "run_id": run_id,
            "user_id": user_id,
            "dataset_id": dataset_id,
            "query": user_query,
            "normalized_query": normalized_query,
            "intent": intent,
            "execution_mode": execution_mode,
            "matched_metric": matched_metric or "",
            "finding": finding,
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "trust_score": trust_score,
            "trust_level": trust_level,
            "grounding_status": grounding_status,
            "consensus_status": consensus_status,
            "replay_id": replay_id,
            "query_hash": query_hash,
            "plan_hash": plan_hash,
            "dataset_hash": dataset_hash,
            "evidence_count": evidence_count,
            "created_at": created_at,
            "result_s3_key": result_s3_key,
            "report_s3_key": "",
        }
        dynamodb_service.put_audit_run(dynamo_item)

        return dynamo_item

    def get_audit_run(self, run_id: str) -> dict[str, Any] | None:
        meta = dynamodb_service.get_audit_run(run_id)
        if not meta:
            return None

        # Rehydrate full result from S3 if key present
        s3_key = meta.get("result_s3_key")
        if s3_key:
            full_data = s3_service.get_audit_result(s3_key)
            if full_data:
                meta["details"] = full_data
        return meta

    def list_user_audit_runs(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return dynamodb_service.list_user_audit_runs(user_id, limit=limit)

    def attach_report_key(self, run_id: str, report_s3_key: str) -> None:
        run = dynamodb_service.get_audit_run(run_id)
        if run:
            run["report_s3_key"] = report_s3_key
            dynamodb_service.put_audit_run(run)


audit_run_repository = AuditRunRepository()
