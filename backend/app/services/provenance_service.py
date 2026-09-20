from __future__ import annotations

import json
from typing import Any

import pandas as pd


def _parse_plan_payload(plan_payload: Any) -> dict[str, Any]:
    if isinstance(plan_payload, dict):
        return plan_payload

    if isinstance(plan_payload, str):
        if plan_payload.startswith("locked_metric::"):
            return {"locked_metric": plan_payload.split("::", 1)[1]}
        try:
            parsed = json.loads(plan_payload)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}

    return {}


def build_provenance(
    input_df: pd.DataFrame,
    result_df: pd.DataFrame | None,
    execution_mode: str,
    plan_intent: str,
    plan_payload: Any,
    used_locked_metric: bool,
    metric_used: str | None,
) -> dict[str, Any]:
    input_rows = int(len(input_df))
    output_rows = int(len(result_df)) if isinstance(result_df, pd.DataFrame) else 0

    coverage_pct = 0.0
    if input_rows > 0:
        coverage_pct = round((output_rows / input_rows) * 100.0, 2)

    parsed_plan = _parse_plan_payload(plan_payload)

    lineage: dict[str, Any]
    if execution_mode == "locked_metric":
        lineage = {
            "locked_metric": metric_used or parsed_plan.get("locked_metric"),
            "filters": [],
            "group_by": [],
            "aggregations": [],
            "sort": [],
            "limit": None,
        }
    else:
        lineage = {
            "filters": parsed_plan.get("filters", []),
            "group_by": parsed_plan.get("group_by", []),
            "aggregations": parsed_plan.get("aggregations", []),
            "sort": parsed_plan.get("sort", []),
            "limit": parsed_plan.get("limit"),
        }

    sample_columns = list(result_df.columns) if isinstance(result_df, pd.DataFrame) else []
    sample_rows = (
        result_df.head(3).fillna("").to_dict("records")
        if isinstance(result_df, pd.DataFrame)
        else []
    )

    return {
        "execution_mode": execution_mode,
        "intent": plan_intent,
        "used_locked_metric": used_locked_metric,
        "metric_used": metric_used,
        "input_rows": input_rows,
        "output_rows": output_rows,
        "evidence_coverage_pct": coverage_pct,
        "lineage": lineage,
        "result_columns": sample_columns,
        "sample_rows": sample_rows,
    }
