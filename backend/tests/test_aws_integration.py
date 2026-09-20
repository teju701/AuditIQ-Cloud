from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.tools import (
    detect_spending_spike,
    detect_split_payments,
    detect_vendor_concentration,
    find_duplicate_invoice_numbers,
    find_duplicate_vendors,
    set_tool_context,
)
from app.aws.dynamodb_service import dynamodb_service
from app.aws.s3_service import s3_service
from app.main import app
from app.storage.dataset_store import DatasetStore


class AwsIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.test_df = pd.DataFrame([
            {
                "transaction_id": "TXN_001",
                "vendor_id": "V001",
                "vendor_name": "Acme Corp",
                "gstin": "27AABCU9603R1ZM",
                "department": "Engineering",
                "category": "Software",
                "invoice_date": "2024-03-01",
                "due_date": "2024-03-31",
                "payment_date": "2024-03-15",
                "amount": 250000.0,
                "has_purchase_order": True,
                "invoice_number": "INV-1001",
                "status": "Paid",
            },
            {
                "transaction_id": "TXN_002",
                "vendor_id": "V002",
                "vendor_name": "Beta Services",
                "gstin": "27AABCU9603R1ZM",  # Duplicate GSTIN
                "department": "Finance",
                "category": "Consulting",
                "invoice_date": "2024-03-02",
                "due_date": "2024-04-01",
                "payment_date": "2024-05-15",  # Late payment (>30 days late)
                "amount": 48000.0,
                "has_purchase_order": False,
                "invoice_number": "INV-1002",
                "status": "Disputed",
            },
            {
                "transaction_id": "TXN_003",
                "vendor_id": "V002",
                "vendor_name": "Beta Services",
                "gstin": "27AABCU9603R1ZM",
                "department": "Finance",
                "category": "Consulting",
                "invoice_date": "2024-03-03",
                "due_date": "2024-04-02",
                "payment_date": "2024-04-02",
                "amount": 49000.0,  # Clustered with TXN_002 for potential split payment
                "has_purchase_order": True,
                "invoice_number": "INV-1001",  # Duplicate invoice number
                "status": "Paid",
            },
        ])

    def test_health_endpoint_reports_aws_components(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("aws_region", data)
        self.assertIn("dataset_storage", data)
        self.assertIn("metadata_storage", data)
        self.assertIn("ai_provider", data)
        self.assertEqual(data["agent_framework"], "strands")

    def test_s3_storage_and_presigned_url(self) -> None:
        key = s3_service.upload_raw_file("user_test", "ds_test", "test.csv", b"a,b\n1,2")
        self.assertTrue(key.startswith("audit-data/datasets/user_test/ds_test/raw/"))
        url = s3_service.generate_presigned_url(key)
        self.assertTrue(len(url) > 0)

    def test_dynamodb_metadata_roundtrip(self) -> None:
        item = {
            "dataset_id": "ds_test_dyn",
            "user_id": "user_dyn_01",
            "file_name": "dyn.csv",
            "row_count": 10,
        }
        dynamodb_service.put_dataset_metadata(item)
        fetched = dynamodb_service.get_dataset_metadata("ds_test_dyn")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.get("file_name"), "dyn.csv")

    def test_dataset_survives_backend_restart(self) -> None:
        store = DatasetStore()
        session = store.add_dataset(self.test_df, user_id="restart_user", file_name="restart.csv")
        dataset_id = session.dataset_id

        # Simulate backend process restart by clearing in-memory cache
        store._cache.clear()
        self.assertEqual(len(store._cache), 0)

        # Reloading dataset after restart from persistent storage
        reloaded = store.get_dataset(dataset_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(len(reloaded.dataframe), 3)
        self.assertEqual(reloaded.user_id, "restart_user")

    def test_strands_audit_tools(self) -> None:
        set_tool_context(self.test_df)

        # Duplicate vendors check
        dup_v_res = find_duplicate_vendors()
        self.assertIn("find_duplicate_vendors", dup_v_res)
        self.assertIn("matched_records", dup_v_res)

        # Duplicate invoice numbers check
        dup_inv_res = find_duplicate_invoice_numbers()
        self.assertIn("find_duplicate_invoice_numbers", dup_inv_res)

        # Spending spike check
        spike_res = detect_spending_spike()
        self.assertIn("detect_spending_spike", spike_res)

        # Split payment check
        split_res = detect_split_payments()
        self.assertIn("detect_split_payments", split_res)

    def test_user_ownership_and_audit_history_flow(self) -> None:
        csv_bytes = io.BytesIO()
        self.test_df.to_csv(csv_bytes, index=False)
        csv_bytes.seek(0)

        # Upload as User A
        upload_resp = self.client.post(
            "/upload",
            files={"file": ("transactions.csv", csv_bytes, "text/csv")},
            headers={"X-User-Id": "user_alpha"},
        )
        self.assertEqual(upload_resp.status_code, 200)
        dataset_id = upload_resp.json()["dataset_id"]

        # Query as User A
        query_resp = self.client.post(
            "/query",
            json={"dataset_id": dataset_id, "query": "Show disputed invoices"},
            headers={"X-User-Id": "user_alpha"},
        )
        self.assertEqual(query_resp.status_code, 200)
        query_data = query_resp.json()
        self.assertIn("run_id", query_data)
        self.assertIn("agent_trace", query_data)
        self.assertTrue(len(query_data["agent_trace"]) > 0)

        run_id = query_data["run_id"]

        # User A can view audit run
        run_resp = self.client.get(f"/audit-runs/{run_id}", headers={"X-User-Id": "user_alpha"})
        self.assertEqual(run_resp.status_code, 200)
        self.assertEqual(run_resp.json()["run_id"], run_id)

        # User B cannot access User A's dataset (IDOR prevention)
        forbidden_resp = self.client.post(
            "/query",
            json={"dataset_id": dataset_id, "query": "Show disputed invoices"},
            headers={"X-User-Id": "user_beta"},
        )
        self.assertEqual(forbidden_resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
