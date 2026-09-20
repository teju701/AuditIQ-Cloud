from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine.metric_resolver import LockedMetricResolution
from app.engine.query_orchestrator import run_query


class QueryEnginePlannerFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.df = pd.DataFrame(
            [
                {
                    "transaction_id": "TXN001",
                    "vendor_name": "Vendor A",
                    "amount": 1000.0,
                    "invoice_date": "2024-01-10",
                    "status": "Paid",
                },
                {
                    "transaction_id": "TXN002",
                    "vendor_name": "Vendor B",
                    "amount": 2500.0,
                    "invoice_date": "2024-01-11",
                    "status": "Paid",
                },
            ]
        )

    def test_primary_planner_failure_returns_no_result_rows(self) -> None:
        planner_failure_payload = {
            "narrative": "I could not generate a reliable structured plan for this question.",
            "logic_explanation": "Plan generation failed.",
            "used_locked_metric": False,
            "metric_used": None,
            "confidence": "low",
            "confidence_reason": "LLM response could not be parsed into structured JSON.",
            "plan_generation_status": "failed",
            "plan": {"intent": "filter", "filters": [], "group_by": [], "aggregations": [], "sort": [], "limit": 50},
        }

        with patch(
            "app.engine.query_orchestrator.resolve_locked_metric",
            return_value=LockedMetricResolution(status="none", metric=None, candidates=[], reason="No deterministic locked metric pattern matched."),
        ), patch("app.engine.query_orchestrator.generate_plan", return_value=planner_failure_payload):
            result = run_query("show top vendors by spend", self.df)

        self.assertEqual(result.get("execution_mode"), "planner_unavailable")
        self.assertIsNone(result.get("result_df"))
        self.assertEqual(result.get("row_count"), 0)
        self.assertFalse(result.get("plan_validated"))
        self.assertEqual(result.get("consensus", {}).get("status"), "low")
        self.assertIsNone(result.get("pandas_code"))

    def test_secondary_planner_failure_marks_consensus_low(self) -> None:
        primary_plan_payload = {
            "narrative": "Filtered records with positive amount.",
            "logic_explanation": "Applied a simple filter on amount.",
            "used_locked_metric": False,
            "metric_used": None,
            "confidence": "medium",
            "confidence_reason": "Generated from structured plan.",
            "plan_generation_status": "success",
            "plan": {
                "intent": "filter",
                "filters": [{"column": "amount", "operator": "gt", "value": 0}],
                "group_by": [],
                "aggregations": [],
                "sort": [],
                "limit": 50,
            },
        }

        secondary_failure_payload = {
            "narrative": "I could not generate a reliable structured plan for this question.",
            "logic_explanation": "Plan generation failed.",
            "used_locked_metric": False,
            "metric_used": None,
            "confidence": "low",
            "confidence_reason": "LLM response could not be parsed into structured JSON.",
            "plan_generation_status": "failed",
            "plan": {"intent": "filter", "filters": [], "group_by": [], "aggregations": [], "sort": [], "limit": 50},
        }

        with patch(
            "app.engine.query_orchestrator.resolve_locked_metric",
            return_value=LockedMetricResolution(status="none", metric=None, candidates=[], reason="No deterministic locked metric pattern matched."),
        ), patch("app.engine.query_orchestrator.generate_plan", side_effect=[primary_plan_payload, secondary_failure_payload]), patch(
            "app.engine.query_orchestrator.ENABLE_DUAL_RUN_CONSENSUS", True
        ):
            result = run_query("show paid transactions", self.df)

        self.assertEqual(result.get("execution_mode"), "safe_plan")
        self.assertEqual(result.get("row_count"), 2)
        self.assertEqual(result.get("consensus", {}).get("status"), "low")
        self.assertTrue(result.get("consensus", {}).get("enabled"))


if __name__ == "__main__":
    unittest.main()
