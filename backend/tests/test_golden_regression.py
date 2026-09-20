from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine.metric_resolver import resolve_locked_metric
from app.engine.executor import execute_locked_metric, execute_plan
from app.engine.validator import validate_and_sanitize_plan
from app.services.schema_service import map_and_profile_dataframe


DATA_PATH = REPO_DIR / "data" / "transactions.csv"

EXPECTED_LOCKED_COUNTS = {
    "duplicate_vendor": 103,
    "round_number_invoice": 10,
    "late_payment": 7,
    "no_purchase_order": 75,
    "high_value_transaction": 307,
    "disputed_invoice": 107,
}


class GoldenRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw_df = pd.read_csv(DATA_PATH)
        cls.df = map_and_profile_dataframe(raw_df).dataframe
        cls.columns = list(cls.df.columns)

    def test_locked_metric_counts(self) -> None:
        for metric, expected_count in EXPECTED_LOCKED_COUNTS.items():
            with self.subTest(metric=metric):
                result, _ = execute_locked_metric(self.df, metric)
                self.assertEqual(len(result), expected_count)

    def test_locked_metric_resolver_matched(self) -> None:
        res = resolve_locked_metric(
            "Show vendors who share the same GSTIN",
            list(EXPECTED_LOCKED_COUNTS.keys()),
        )
        self.assertEqual(res.status, "matched")
        self.assertEqual(res.metric, "duplicate_vendor")

    def test_locked_metric_resolver_ambiguous(self) -> None:
        res = resolve_locked_metric(
            "Run a locked metric analysis",
            list(EXPECTED_LOCKED_COUNTS.keys()),
        )
        self.assertEqual(res.status, "ambiguous")
        self.assertGreaterEqual(len(res.candidates), 2)

    def test_trend_safe_plan_execution(self) -> None:
        plan = {
            "intent": "trend",
            "filters": [],
            "group_by": [],
            "aggregations": [],
            "sort": [{"column": "period", "direction": "asc"}],
            "limit": 50,
            "comparison": {},
            "trend": {
                "date_column": "invoice_date",
                "grain": "month",
                "metric": {"column": "transaction_id", "op": "count"},
            },
            "why_change": {},
        }

        validated = validate_and_sanitize_plan(plan, self.columns)
        result = execute_plan(self.df, validated)

        self.assertEqual(validated["intent"], "trend")
        self.assertEqual(len(result), 12)
        self.assertListEqual(list(result.columns), ["period", "value", "change_abs", "change_pct"])

    def test_breakdown_safe_plan_execution(self) -> None:
        plan = {
            "intent": "breakdown",
            "filters": [],
            "group_by": ["department"],
            "aggregations": [
                {"column": "transaction_id", "op": "count", "as": "transaction_count"},
                {"column": "amount", "op": "sum", "as": "total_amount"},
            ],
            "sort": [{"column": "total_amount", "direction": "desc"}],
            "limit": 50,
            "comparison": {},
            "trend": {},
            "why_change": {},
        }

        validated = validate_and_sanitize_plan(plan, self.columns)
        result = execute_plan(self.df, validated)

        self.assertEqual(validated["intent"], "breakdown")
        self.assertIn("share_pct", result.columns)
        self.assertAlmostEqual(float(result["share_pct"].sum()), 100.0, delta=0.25)

    def test_why_change_safe_plan_execution(self) -> None:
        plan = {
            "intent": "why_change",
            "filters": [],
            "group_by": [],
            "aggregations": [],
            "sort": [{"column": "delta", "direction": "desc"}],
            "limit": 50,
            "comparison": {},
            "trend": {},
            "why_change": {
                "date_column": "invoice_date",
                "grain": "month",
                "dimension": "department",
                "metric": {"column": "amount", "op": "sum"},
            },
        }

        validated = validate_and_sanitize_plan(plan, self.columns)
        result = execute_plan(self.df, validated)

        self.assertEqual(validated["intent"], "why_change")
        self.assertFalse(result.empty)
        self.assertIn("contribution_pct", result.columns)


if __name__ == "__main__":
    unittest.main()
