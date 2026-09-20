from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app


DATA_PATH = REPO_DIR / "data" / "transactions.csv"


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def setUp(self) -> None:
        # Keep tests deterministic by resetting cache state between test cases.
        self.client.post("/cache/invalidate", json={})

    def _upload_dataset(self) -> dict:
        with open(DATA_PATH, "rb") as f:
            response = self.client.post(
                "/upload",
                files={"file": ("transactions.csv", f, "text/csv")},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("dataset_id", payload)
        return payload

    def test_upload_response_contract(self) -> None:
        payload = self._upload_dataset()

        self.assertIn("dataset_hash", payload)
        self.assertIn("semantic_mapping", payload)
        self.assertIn("schema_profile", payload)
        self.assertIn("anomalies", payload)
        self.assertEqual(payload["rows"], 500)

    def test_query_requires_dataset_id(self) -> None:
        response = self.client.post("/query", json={"query": "show duplicate gstin"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("dataset_id is required", response.json().get("detail", ""))

    def test_query_invalid_dataset_id(self) -> None:
        response = self.client.post("/query", json={"dataset_id": "invalid", "query": "show duplicate gstin"})

        self.assertEqual(response.status_code, 404)
        self.assertIn("Dataset session not found", response.json().get("detail", ""))

    def test_locked_metric_query_cache_roundtrip(self) -> None:
        uploaded = self._upload_dataset()
        dataset_id = uploaded["dataset_id"]
        query = "Show vendors who share the same GSTIN"

        first = self.client.post("/query", json={"dataset_id": dataset_id, "query": query})
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()

        self.assertEqual(first_payload.get("execution_mode"), "locked_metric")
        self.assertTrue(first_payload.get("used_locked_metric"))
        self.assertEqual(first_payload.get("metric_used"), "duplicate_vendor")
        self.assertEqual(first_payload.get("metric_resolution", {}).get("status"), "matched")
        self.assertIn("consensus", first_payload)
        self.assertEqual(first_payload.get("consensus", {}).get("status"), "high")
        self.assertFalse(first_payload.get("cache", {}).get("hit"))

        second = self.client.post("/query", json={"dataset_id": dataset_id, "query": query})
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()

        self.assertTrue(second_payload.get("cache", {}).get("hit"))
        self.assertEqual(first_payload.get("replay_id"), second_payload.get("replay_id"))

    def test_cache_invalidate_dataset_scope(self) -> None:
        uploaded = self._upload_dataset()
        dataset_id = uploaded["dataset_id"]
        query = "Show vendors who share the same GSTIN"

        _ = self.client.post("/query", json={"dataset_id": dataset_id, "query": query})

        invalidate = self.client.post("/cache/invalidate", json={"dataset_id": dataset_id})
        self.assertEqual(invalidate.status_code, 200)
        invalidate_payload = invalidate.json()

        self.assertEqual(invalidate_payload.get("scope"), "dataset")
        self.assertGreaterEqual(int(invalidate_payload.get("removed_entries", 0)), 1)

        after = self.client.post("/query", json={"dataset_id": dataset_id, "query": query})
        self.assertEqual(after.status_code, 200)
        self.assertFalse(after.json().get("cache", {}).get("hit"))

    def test_export_pdf_response_headers(self) -> None:
        uploaded = self._upload_dataset()
        dataset_id = uploaded["dataset_id"]

        response = self.client.post(
            "/export-pdf",
            json={"dataset_id": dataset_id, "query": "Show vendors who share the same GSTIN"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response.headers.get("content-type", ""))
        self.assertTrue(response.headers.get("X-Replay-Id"))
        self.assertIn(response.headers.get("X-Cache-Hit", ""), {"true", "false"})
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_query_pagination_next_page(self) -> None:
        uploaded = self._upload_dataset()
        dataset_id = uploaded["dataset_id"]
        query = "Show vendors who share the same GSTIN"

        first = self.client.post(
            "/query",
            json={"dataset_id": dataset_id, "query": query, "page": 1, "page_size": 25},
        )
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()

        second = self.client.post(
            "/query",
            json={"dataset_id": dataset_id, "query": query, "page": 2, "page_size": 25},
        )
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()

        first_pagination = first_payload.get("pagination", {})
        second_pagination = second_payload.get("pagination", {})

        self.assertEqual(first_pagination.get("page"), 1)
        self.assertEqual(first_pagination.get("page_size"), 25)
        self.assertEqual(first_pagination.get("total_rows"), 103)
        self.assertEqual(first_pagination.get("total_pages"), 5)
        self.assertFalse(first_pagination.get("has_prev"))
        self.assertTrue(first_pagination.get("has_next"))

        self.assertEqual(second_pagination.get("page"), 2)
        self.assertEqual(second_pagination.get("page_size"), 25)
        self.assertEqual(second_pagination.get("total_rows"), 103)
        self.assertTrue(second_pagination.get("has_prev"))
        self.assertTrue(second_pagination.get("has_next"))

        self.assertEqual(len(first_payload.get("result_records", [])), 25)
        self.assertEqual(len(second_payload.get("result_records", [])), 25)

        first_records = first_payload.get("result_records", [])
        second_records = second_payload.get("result_records", [])
        self.assertNotEqual(first_records[0].get("transaction_id"), second_records[0].get("transaction_id"))


if __name__ == "__main__":
    unittest.main()
