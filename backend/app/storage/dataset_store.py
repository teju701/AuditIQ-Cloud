from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any
from uuid import uuid4

import pandas as pd

from app.aws.dynamodb_service import dynamodb_service
from app.aws.s3_service import s3_service

logger = logging.getLogger("auditiq.storage.dataset")


@dataclass
class DatasetSession:
    dataset_id: str
    dataframe: pd.DataFrame
    dataset_hash: str
    created_at: str
    metadata: dict[str, Any]
    user_id: str = "auditor_local_01"
    file_name: str = "transactions.csv"
    s3_raw_key: str = ""
    s3_normalized_key: str = ""


class DatasetRepository:
    def __init__(self) -> None:
        self._cache: dict[str, DatasetSession] = {}

    def add_dataset(
        self,
        dataframe: pd.DataFrame,
        metadata: dict[str, Any] | None = None,
        user_id: str = "auditor_local_01",
        file_name: str = "transactions.csv",
        raw_content: bytes | None = None,
    ) -> DatasetSession:
        dataset_id = uuid4().hex
        dataset_hash = self._compute_dataset_hash(dataframe)
        created_at = datetime.now(timezone.utc).isoformat()
        meta = metadata or {}

        # 1. S3 Persistence: Raw file (if provided) & Processed normalized CSV
        s3_raw_key = ""
        if raw_content:
            s3_raw_key = s3_service.upload_raw_file(user_id, dataset_id, file_name, raw_content)

        s3_norm_key = s3_service.save_normalized_csv(user_id, dataset_id, dataframe)

        # 2. S3 Manifest & Anomalies
        manifest = {
            "dataset_id": dataset_id,
            "user_id": user_id,
            "file_name": file_name,
            "dataset_hash": dataset_hash,
            "row_count": len(dataframe),
            "columns": list(dataframe.columns),
            "semantic_mapping": meta.get("semantic_mapping", {}),
            "created_at": created_at,
        }
        s3_service.save_manifest(user_id, dataset_id, manifest)

        anomalies = meta.get("anomalies", [])
        if anomalies:
            s3_service.save_anomalies(user_id, dataset_id, anomalies)

        # 3. DynamoDB Metadata Persistence
        dynamo_record = {
            "dataset_id": dataset_id,
            "user_id": user_id,
            "file_name": file_name,
            "s3_raw_key": s3_raw_key,
            "s3_normalized_key": s3_norm_key,
            "dataset_hash": dataset_hash,
            "row_count": len(dataframe),
            "columns": list(dataframe.columns),
            "schema_profile": meta.get("schema_profile", {}),
            "anomaly_summary": meta.get("anomaly_summary", {}),
            "created_at": created_at,
            "processing_status": "ready",
        }
        dynamodb_service.put_dataset_metadata(dynamo_record)

        session = DatasetSession(
            dataset_id=dataset_id,
            dataframe=dataframe,
            dataset_hash=dataset_hash,
            created_at=created_at,
            metadata=meta,
            user_id=user_id,
            file_name=file_name,
            s3_raw_key=s3_raw_key,
            s3_normalized_key=s3_norm_key,
        )

        self._cache[dataset_id] = session
        return session

    def get_dataset(self, dataset_id: str) -> DatasetSession | None:
        # Check in-memory cache first for fast execution
        if dataset_id in self._cache:
            return self._cache[dataset_id]

        # SURVIVE RESTART: Reload from DynamoDB + S3
        metadata_item = dynamodb_service.get_dataset_metadata(dataset_id)
        if not metadata_item:
            return None

        s3_norm_key = metadata_item.get("s3_normalized_key")
        if not s3_norm_key:
            return None

        try:
            df = s3_service.get_normalized_dataframe(s3_norm_key)
            session = DatasetSession(
                dataset_id=dataset_id,
                dataframe=df,
                dataset_hash=metadata_item.get("dataset_hash", ""),
                created_at=metadata_item.get("created_at", ""),
                metadata={
                    "schema_profile": metadata_item.get("schema_profile", {}),
                    "anomaly_summary": metadata_item.get("anomaly_summary", {}),
                },
                user_id=metadata_item.get("user_id", "auditor_local_01"),
                file_name=metadata_item.get("file_name", ""),
                s3_raw_key=metadata_item.get("s3_raw_key", ""),
                s3_normalized_key=s3_norm_key,
            )
            # Rehydrate in-memory cache
            self._cache[dataset_id] = session
            return session
        except Exception as e:
            logger.error(f"Failed to reload dataset {dataset_id} from S3 key {s3_norm_key}: {e}")
            return None

    def list_user_datasets(self, user_id: str) -> list[dict[str, Any]]:
        return dynamodb_service.list_user_datasets(user_id)

    def count(self) -> int:
        return len(self._cache)

    @staticmethod
    def _compute_dataset_hash(dataframe: pd.DataFrame) -> str:
        payload = {
            "columns": list(dataframe.columns),
            "shape": list(dataframe.shape),
            "data": dataframe.astype(str).fillna("<NA>").to_dict(orient="records"),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# Keep DatasetStore name for compatibility with existing imports
DatasetStore = DatasetRepository
