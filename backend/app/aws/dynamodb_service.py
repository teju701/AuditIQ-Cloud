from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.settings import AWS_REGION, DYNAMODB_AUDIT_RUNS_TABLE, DYNAMODB_DATASETS_TABLE

logger = logging.getLogger("auditiq.aws.dynamodb")


def _sanitize_for_dynamodb(obj: Any) -> Any:
    """Recursively convert float to str or decimal if needed, and None to empty str/omit."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_dynamodb(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_sanitize_for_dynamodb(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 4)
    return obj


class DynamoDBService:
    def __init__(
        self,
        datasets_table: str | None = None,
        audit_runs_table: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self.datasets_table_name = datasets_table or DYNAMODB_DATASETS_TABLE or "AuditIQDatasets"
        self.audit_runs_table_name = audit_runs_table or DYNAMODB_AUDIT_RUNS_TABLE or "AuditIQAuditRuns"
        self.region = region_name or AWS_REGION or "us-east-1"

        self._resource = None
        self._datasets_table = None
        self._audit_runs_table = None
        self._is_live = False

        # In-memory local fallback store
        self._local_datasets: dict[str, dict[str, Any]] = {}
        self._local_audit_runs: dict[str, dict[str, Any]] = {}
        self._local_dir = Path(__file__).resolve().parents[3] / ".dynamodb_local"
        self._load_local_state()

        try:
            self._resource = boto3.resource("dynamodb", region_name=self.region)
            self._datasets_table = self._resource.Table(self.datasets_table_name)
            self._audit_runs_table = self._resource.Table(self.audit_runs_table_name)
            # Ping table to check existence
            self._datasets_table.load()
            self._audit_runs_table.load()
            self._is_live = True
        except Exception as e:
            logger.info(f"DynamoDB live tables not active or accessible ({e}). Using local persistent state.")
            self._is_live = False

    def _load_local_state(self) -> None:
        try:
            self._local_dir.mkdir(parents=True, exist_ok=True)
            ds_file = self._local_dir / "datasets.json"
            if ds_file.exists():
                self._local_datasets = json.loads(ds_file.read_text(encoding="utf-8"))
            ar_file = self._local_dir / "audit_runs.json"
            if ar_file.exists():
                self._local_audit_runs = json.loads(ar_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not load local DynamoDB state: {e}")

    def _save_local_state(self) -> None:
        try:
            self._local_dir.mkdir(parents=True, exist_ok=True)
            (self._local_dir / "datasets.json").write_text(json.dumps(self._local_datasets, indent=2), encoding="utf-8")
            (self._local_dir / "audit_runs.json").write_text(json.dumps(self._local_audit_runs, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not save local DynamoDB state: {e}")

    # Dataset Metadata Operations
    def put_dataset_metadata(self, item: dict[str, Any]) -> None:
        sanitized = _sanitize_for_dynamodb(item)
        if self._is_live and self._datasets_table:
            try:
                self._datasets_table.put_item(Item=sanitized)
                return
            except Exception as e:
                logger.error(f"DynamoDB put_dataset_metadata failed: {e}. Falling back to local.")

        dataset_id = str(sanitized.get("dataset_id"))
        self._local_datasets[dataset_id] = sanitized
        self._save_local_state()

    def get_dataset_metadata(self, dataset_id: str) -> dict[str, Any] | None:
        if self._is_live and self._datasets_table:
            try:
                response = self._datasets_table.get_item(Key={"dataset_id": dataset_id})
                return response.get("Item")
            except Exception as e:
                logger.error(f"DynamoDB get_dataset_metadata failed: {e}. Falling back to local.")

        return self._local_datasets.get(dataset_id)

    def list_user_datasets(self, user_id: str) -> list[dict[str, Any]]:
        if self._is_live and self._datasets_table:
            try:
                from boto3.dynamodb.conditions import Attr
                response = self._datasets_table.scan(
                    FilterExpression=Attr("user_id").eq(user_id)
                )
                items = response.get("Items", [])
                items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                return items
            except Exception as e:
                logger.error(f"DynamoDB list_user_datasets failed: {e}. Falling back to local.")

        user_items = [v for v in self._local_datasets.values() if v.get("user_id") == user_id]
        user_items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return user_items

    # Audit Run Operations
    def put_audit_run(self, item: dict[str, Any]) -> None:
        sanitized = _sanitize_for_dynamodb(item)
        if self._is_live and self._audit_runs_table:
            try:
                self._audit_runs_table.put_item(Item=sanitized)
                return
            except Exception as e:
                logger.error(f"DynamoDB put_audit_run failed: {e}. Falling back to local.")

        run_id = str(sanitized.get("run_id"))
        self._local_audit_runs[run_id] = sanitized
        self._save_local_state()

    def get_audit_run(self, run_id: str) -> dict[str, Any] | None:
        if self._is_live and self._audit_runs_table:
            try:
                response = self._audit_runs_table.get_item(Key={"run_id": run_id})
                return response.get("Item")
            except Exception as e:
                logger.error(f"DynamoDB get_audit_run failed: {e}. Falling back to local.")

        return self._local_audit_runs.get(run_id)

    def list_user_audit_runs(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if self._is_live and self._audit_runs_table:
            try:
                from boto3.dynamodb.conditions import Attr
                response = self._audit_runs_table.scan(
                    FilterExpression=Attr("user_id").eq(user_id),
                    Limit=limit,
                )
                items = response.get("Items", [])
                items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                return items[:limit]
            except Exception as e:
                logger.error(f"DynamoDB list_user_audit_runs failed: {e}. Falling back to local.")

        user_items = [v for v in self._local_audit_runs.values() if v.get("user_id") == user_id]
        user_items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return user_items[:limit]

    def is_healthy(self) -> bool:
        if not self._is_live or not self._datasets_table:
            return True  # Local fallback is healthy
        try:
            return self._datasets_table.table_status in ("ACTIVE", "UPDATING")
        except Exception:
            return False


dynamodb_service = DynamoDBService()
