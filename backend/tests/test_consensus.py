from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine.consensus import build_consensus_report, single_path_consensus


class ConsensusTests(unittest.TestCase):
    def test_high_consensus_for_matching_plan_and_rows(self) -> None:
        plan = {
            "intent": "breakdown",
            "filters": [],
            "group_by": ["department"],
            "aggregations": [{"column": "amount", "op": "sum", "as": "total_amount"}],
            "sort": [{"column": "total_amount", "direction": "desc"}],
            "limit": 50,
        }

        df = pd.DataFrame(
            [
                {"department": "IT", "total_amount": 100.0},
                {"department": "Finance", "total_amount": 80.0},
            ]
        )

        report = build_consensus_report(plan, plan.copy(), df, df.copy())

        self.assertEqual(report["status"], "high")
        self.assertGreaterEqual(report["score"], 90.0)
        self.assertTrue(report["plan_match"])

    def test_low_consensus_when_secondary_fails(self) -> None:
        primary_plan = {"intent": "trend"}
        primary_df = pd.DataFrame([{"period": "2024-01", "value": 10.0}])

        report = build_consensus_report(
            primary_plan=primary_plan,
            secondary_plan=None,
            primary_result_df=primary_df,
            secondary_result_df=None,
            secondary_error="secondary plan failed",
        )

        self.assertEqual(report["status"], "low")
        self.assertLessEqual(report["score"], 30.0)
        self.assertIn("failed", report["reason"])

    def test_single_path_consensus(self) -> None:
        report = single_path_consensus("locked_metric", "deterministic path")
        self.assertFalse(report["enabled"])
        self.assertEqual(report["status"], "high")
        self.assertEqual(report["score"], 100.0)


if __name__ == "__main__":
    unittest.main()
