from __future__ import annotations

import json
from typing import Any
import pandas as pd

from strands import tool

from app.engine.executor import execute_locked_metric, execute_plan
from app.engine.validator import validate_and_sanitize_plan


class AuditToolContext:
    """Holds active dataframe and tracking for tool executions during an audit investigation."""
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df
        self.invoked_tools: list[str] = []
        self.last_result_df: pd.DataFrame | None = None
        self.last_explanation: str = ""

    def record_run(self, tool_name: str, result_df: pd.DataFrame, explanation: str) -> dict[str, Any]:
        self.invoked_tools.append(tool_name)
        self.last_result_df = result_df
        self.last_explanation = explanation
        return {
            "tool": tool_name,
            "status": "success",
            "matched_records": len(result_df),
            "explanation": explanation,
            "sample_columns": list(result_df.columns)[:8],
            "sample": result_df.head(3).fillna("").to_dict("records"),
        }


# Active thread/request context pointer
_current_context: AuditToolContext | None = None


def set_tool_context(df: pd.DataFrame) -> AuditToolContext:
    global _current_context
    _current_context = AuditToolContext(df)
    return _current_context


def get_tool_context() -> AuditToolContext:
    global _current_context
    if _current_context is None:
        _current_context = AuditToolContext(pd.DataFrame())
    return _current_context


# Deterministic Audit Tools registered with Strands @tool
@tool
def find_duplicate_vendors() -> str:
    """Detects vendor entities sharing the same GSTIN identification number across multiple vendor names."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "duplicate_vendor")
    return json.dumps(ctx.record_run("find_duplicate_vendors", res_df, expl))


@tool
def find_round_number_invoices() -> str:
    """Detects round-number invoice amounts divisible exactly by 1,000 without fractional paise."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "round_number_invoice")
    return json.dumps(ctx.record_run("find_round_number_invoices", res_df, expl))


@tool
def find_late_payments() -> str:
    """Detects invoices where payment date occurred more than 30 days after the agreed contractual due date."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "late_payment")
    return json.dumps(ctx.record_run("find_late_payments", res_df, expl))


@tool
def find_missing_purchase_orders() -> str:
    """Detects unapproved invoices above Rs 10,000 processed without an authorized purchase order."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "no_purchase_order")
    return json.dumps(ctx.record_run("find_missing_purchase_orders", res_df, expl))


@tool
def find_high_value_transactions() -> str:
    """Detects high-value transaction amounts exceeding Rs 2,00,000 requiring senior management approval."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "high_value_transaction")
    return json.dumps(ctx.record_run("find_high_value_transactions", res_df, expl))


@tool
def find_disputed_invoices() -> str:
    """Retrieves all invoice transactions currently flagged with Disputed resolution status."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "disputed_invoice")
    return json.dumps(ctx.record_run("find_disputed_invoices", res_df, expl))


@tool
def find_duplicate_invoice_numbers() -> str:
    """Detects identical invoice numbers billed across multiple transactions."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "duplicate_invoice")
    return json.dumps(ctx.record_run("find_duplicate_invoice_numbers", res_df, expl))


@tool
def detect_spending_spike() -> str:
    """Detects anomalous transaction amounts exceeding 2 standard deviations above the dataset average."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "spending_spike")
    return json.dumps(ctx.record_run("detect_spending_spike", res_df, expl))


@tool
def detect_vendor_concentration() -> str:
    """Detects vendors accounting for more than 12% of total cumulative organization expenditure."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "vendor_concentration")
    return json.dumps(ctx.record_run("detect_vendor_concentration", res_df, expl))


@tool
def detect_split_payments() -> str:
    """Detects potential invoice splitting structured just below financial policy thresholds."""
    ctx = get_tool_context()
    res_df, expl = execute_locked_metric(ctx.df, "split_payment")
    return json.dumps(ctx.record_run("detect_split_payments", res_df, expl))


@tool
def breakdown_by_dimension(dimension: str, metric_column: str = "amount", aggregation: str = "sum") -> str:
    """Computes spend or transaction breakdown grouped by a specific dimension like department or category."""
    ctx = get_tool_context()
    columns = list(ctx.df.columns)
    plan = {
        "intent": "breakdown",
        "group_by": [dimension],
        "aggregations": [{"column": metric_column, "op": aggregation, "as": f"{aggregation}_{metric_column}"}],
        "sort": [{"column": f"{aggregation}_{metric_column}", "direction": "desc"}],
        "limit": 25,
    }
    validated = validate_and_sanitize_plan(plan, columns)
    res_df = execute_plan(ctx.df, validated)
    return json.dumps(ctx.record_run(f"breakdown_by_{dimension}", res_df, f"Grouped by {dimension}"))


@tool
def calculate_trend(date_column: str = "invoice_date", grain: str = "month", metric_column: str = "amount") -> str:
    """Calculates chronological trend of spend over time (day, week, month, quarter, year)."""
    ctx = get_tool_context()
    columns = list(ctx.df.columns)
    plan = {
        "intent": "trend",
        "trend": {
            "date_column": date_column,
            "grain": grain,
            "metric": {"column": metric_column, "op": "sum"},
        },
        "sort": [{"column": "period", "direction": "asc"}],
        "limit": 50,
    }
    validated = validate_and_sanitize_plan(plan, columns)
    res_df = execute_plan(ctx.df, validated)
    return json.dumps(ctx.record_run("calculate_trend", res_df, f"Calculated {grain} trend on {date_column}"))


ALL_AUDIT_TOOLS = [
    find_duplicate_vendors,
    find_round_number_invoices,
    find_late_payments,
    find_missing_purchase_orders,
    find_high_value_transactions,
    find_disputed_invoices,
    find_duplicate_invoice_numbers,
    detect_spending_spike,
    detect_vendor_concentration,
    detect_split_payments,
    breakdown_by_dimension,
    calculate_trend,
]
