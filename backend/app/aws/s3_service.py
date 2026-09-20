from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError
import pandas as pd

from app.core.settings import AWS_REGION, S3_BUCKET

logger = logging.getLogger("auditiq.aws.s3")


class S3Service:
    def __init__(self, bucket_name: str | None = None, region_name: str | None = None) -> None:
        self.bucket = (bucket_name or S3_BUCKET or "").strip()
        self.region = region_name or AWS_REGION or "us-east-1"
        self._client = None
        self._local_storage_dir = Path(__file__).resolve().parents[3] / ".s3_local"
        self._is_live = bool(self.bucket)

        if self._is_live:
            try:
                self._client = boto3.client("s3", region_name=self.region)
            except Exception as e:
                logger.warning(f"Could not initialize live S3 client: {e}. Using local storage fallback.")
                self._is_live = False

    def _get_local_path(self, s3_key: str) -> Path:
        clean_key = s3_key.replace("/", os.sep)
        path = self._local_storage_dir / clean_key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def upload_raw_file(self, user_id: str, dataset_id: str, filename: str, content: bytes) -> str:
        s3_key = f"audit-data/datasets/{user_id}/{dataset_id}/raw/{filename}"
        if self._is_live and self._client:
            try:
                self._client.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=content,
                    ServerSideEncryption="AES256",
                )
                return s3_key
            except Exception as e:
                logger.error(f"S3 upload_raw_file failed: {e}. Falling back to local storage.")

        local_path = self._get_local_path(s3_key)
        local_path.write_bytes(content)
        return s3_key

    def save_normalized_csv(self, user_id: str, dataset_id: str, df: pd.DataFrame) -> str:
        s3_key = f"audit-data/datasets/{user_id}/{dataset_id}/processed/normalized.csv"
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        content = csv_buffer.getvalue().encode("utf-8")

        if self._is_live and self._client:
            try:
                self._client.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=content,
                    ContentType="text/csv",
                    ServerSideEncryption="AES256",
                )
                return s3_key
            except Exception as e:
                logger.error(f"S3 save_normalized_csv failed: {e}. Falling back to local storage.")

        local_path = self._get_local_path(s3_key)
        local_path.write_bytes(content)
        return s3_key

    def get_normalized_dataframe(self, s3_key: str) -> pd.DataFrame:
        if self._is_live and self._client:
            try:
                response = self._client.get_object(Bucket=self.bucket, Key=s3_key)
                content = response["Body"].read()
                return pd.read_csv(io.BytesIO(content))
            except Exception as e:
                logger.error(f"S3 get_normalized_dataframe failed for key {s3_key}: {e}. Checking local.")

        local_path = self._get_local_path(s3_key)
        if local_path.exists():
            return pd.read_csv(local_path)
        raise FileNotFoundError(f"Normalized dataset not found in S3 or local storage: {s3_key}")

    def save_manifest(self, user_id: str, dataset_id: str, manifest: dict[str, Any]) -> str:
        s3_key = f"audit-data/datasets/{user_id}/{dataset_id}/manifest.json"
        content = json.dumps(manifest, indent=2).encode("utf-8")

        if self._is_live and self._client:
            try:
                self._client.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=content,
                    ContentType="application/json",
                    ServerSideEncryption="AES256",
                )
                return s3_key
            except Exception as e:
                logger.error(f"S3 save_manifest failed: {e}. Falling back to local.")

        local_path = self._get_local_path(s3_key)
        local_path.write_bytes(content)
        return s3_key

    def save_anomalies(self, user_id: str, dataset_id: str, anomalies: list[dict[str, Any]]) -> str:
        s3_key = f"audit-data/datasets/{user_id}/{dataset_id}/anomalies.json"
        content = json.dumps(anomalies, indent=2).encode("utf-8")

        if self._is_live and self._client:
            try:
                self._client.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=content,
                    ContentType="application/json",
                    ServerSideEncryption="AES256",
                )
                return s3_key
            except Exception as e:
                logger.error(f"S3 save_anomalies failed: {e}. Falling back to local.")

        local_path = self._get_local_path(s3_key)
        local_path.write_bytes(content)
        return s3_key

    def save_audit_result(self, user_id: str, dataset_id: str, run_id: str, result: dict[str, Any]) -> str:
        s3_key = f"audit-data/datasets/{user_id}/{dataset_id}/audit-results/{run_id}.json"
        serializable = {}
        for k, v in result.items():
            if isinstance(v, pd.DataFrame):
                serializable[k] = v.fillna("").to_dict("records")
            else:
                try:
                    json.dumps(v)
                    serializable[k] = v
                except (TypeError, OverflowError):
                    serializable[k] = str(v)

        content = json.dumps(serializable, indent=2).encode("utf-8")

        if self._is_live and self._client:
            try:
                self._client.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=content,
                    ContentType="application/json",
                    ServerSideEncryption="AES256",
                )
                return s3_key
            except Exception as e:
                logger.error(f"S3 save_audit_result failed: {e}. Falling back to local.")

        local_path = self._get_local_path(s3_key)
        local_path.write_bytes(content)
        return s3_key

    def get_audit_result(self, s3_key: str) -> dict[str, Any]:
        if self._is_live and self._client:
            try:
                response = self._client.get_object(Bucket=self.bucket, Key=s3_key)
                return json.loads(response["Body"].read().decode("utf-8"))
            except Exception as e:
                logger.error(f"S3 get_audit_result failed for key {s3_key}: {e}. Checking local.")

        local_path = self._get_local_path(s3_key)
        if local_path.exists():
            return json.loads(local_path.read_text(encoding="utf-8"))
        return {}

    def save_pdf_report(self, user_id: str, dataset_id: str, run_id: str, pdf_bytes: bytes) -> str:
        s3_key = f"audit-data/datasets/{user_id}/{dataset_id}/reports/{run_id}.pdf"
        if self._is_live and self._client:
            try:
                self._client.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=pdf_bytes,
                    ContentType="application/pdf",
                    ServerSideEncryption="AES256",
                )
                return s3_key
            except Exception as e:
                logger.error(f"S3 save_pdf_report failed: {e}. Falling back to local.")

        local_path = self._get_local_path(s3_key)
        local_path.write_bytes(pdf_bytes)
        return s3_key

    def generate_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        if self._is_live and self._client:
            try:
                return self._client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": s3_key},
                    ExpiresIn=expires_in,
                )
            except Exception as e:
                logger.error(f"Failed to generate presigned URL: {e}")

        # In local development mode, return a download URL through our API
        return f"/export-pdf/download?key={s3_key}"

    def is_healthy(self) -> bool:
        if not self._is_live or not self._client:
            return True  # Local storage fallback is functional
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False


s3_service = S3Service()
