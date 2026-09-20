from __future__ import annotations

from typing import Any


class PlanValidationError(ValueError):
    pass


ALLOWED_INTENTS = {"why_change", "comparison", "breakdown", "trend", "filter"}
ALLOWED_FILTER_OPERATORS = {
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "in",
    "not_in",
    "between",
    "is_null",
    "not_null",
    "is_true",
    "is_false",
}
ALLOWED_AGGREGATIONS = {"sum", "avg", "min", "max", "count", "count_distinct"}
ALLOWED_SORT_DIRECTIONS = {"asc", "desc"}
MAX_LIMIT = 200
DEFAULT_LIMIT = 50

OPERATOR_ALIASES = {
    "=": "eq",
    "==": "eq",
    "!=": "ne",
    ">": "gt",
    ">=": "gte",
    "<": "lt",
    "<=": "lte",
}

AGGREGATION_ALIASES = {
    "mean": "avg",
    "average": "avg",
    "nunique": "count_distinct",
    "distinct_count": "count_distinct",
    "distinct": "count_distinct",
}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _normalize_filter(raw: dict[str, Any]) -> dict[str, Any] | None:
    column = raw.get("column")
    if not isinstance(column, str) or not column.strip():
        return None

    raw_op = str(raw.get("operator", "eq")).strip().lower()
    operator = OPERATOR_ALIASES.get(raw_op, raw_op)
    if operator not in ALLOWED_FILTER_OPERATORS:
        return None

    normalized: dict[str, Any] = {"column": column, "operator": operator}
    if operator == "between":
        normalized["value"] = raw.get("value")
        normalized["value_to"] = raw.get("value_to")
    elif operator not in {"is_null", "not_null", "is_true", "is_false"}:
        normalized["value"] = raw.get("value")

    return normalized


def _normalize_aggregation(raw: dict[str, Any]) -> dict[str, Any] | None:
    raw_op = str(raw.get("op", "count")).strip().lower()
    op = AGGREGATION_ALIASES.get(raw_op, raw_op)
    if op not in ALLOWED_AGGREGATIONS:
        return None

    column = raw.get("column")
    if column is not None and not isinstance(column, str):
        return None

    alias = raw.get("as")
    if not isinstance(alias, str) or not alias.strip():
        base = f"{op}_{column}" if column else op
        alias = base

    return {"column": column, "op": op, "as": alias}


def _normalize_sort(raw: dict[str, Any]) -> dict[str, Any] | None:
    column = raw.get("column") or raw.get("by")
    if not isinstance(column, str) or not column.strip():
        return None

    direction = str(raw.get("direction", raw.get("order", "desc"))).strip().lower()
    if direction not in ALLOWED_SORT_DIRECTIONS:
        direction = "desc"

    return {"column": column, "direction": direction}


def normalize_plan(raw_plan: dict[str, Any] | None, routed_intent: str) -> dict[str, Any]:
    plan = raw_plan if isinstance(raw_plan, dict) else {}

    raw_intent = str(plan.get("intent", routed_intent)).strip().lower()
    intent = raw_intent if raw_intent in ALLOWED_INTENTS else routed_intent

    filters = []
    for candidate in _as_list(plan.get("filters")):
        if isinstance(candidate, dict):
            normalized = _normalize_filter(candidate)
            if normalized is not None:
                filters.append(normalized)

    group_by = [col for col in _as_list(plan.get("group_by")) if isinstance(col, str) and col.strip()]

    aggregations = []
    for candidate in _as_list(plan.get("aggregations")):
        if isinstance(candidate, dict):
            normalized = _normalize_aggregation(candidate)
            if normalized is not None:
                aggregations.append(normalized)

    sort_list = []
    raw_sort = plan.get("sort")
    if isinstance(raw_sort, dict):
        raw_sort = [raw_sort]
    for candidate in _as_list(raw_sort):
        if isinstance(candidate, dict):
            normalized = _normalize_sort(candidate)
            if normalized is not None:
                sort_list.append(normalized)

    try:
        limit = int(plan.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    limit = max(1, min(limit, MAX_LIMIT))

    comparison = plan.get("comparison") if isinstance(plan.get("comparison"), dict) else {}
    trend = plan.get("trend") if isinstance(plan.get("trend"), dict) else {}
    why_change = plan.get("why_change") if isinstance(plan.get("why_change"), dict) else {}

    return {
        "intent": intent,
        "filters": filters,
        "group_by": group_by,
        "aggregations": aggregations,
        "sort": sort_list,
        "limit": limit,
        "comparison": comparison,
        "trend": trend,
        "why_change": why_change,
    }


def _ensure_column_exists(column: str | None, column_set: set[str], error_label: str) -> None:
    if not column:
        raise PlanValidationError(f"Missing required column for {error_label}.")
    if column not in column_set:
        raise PlanValidationError(f"Column '{column}' is not present in dataset for {error_label}.")


def validate_and_sanitize_plan(plan: dict[str, Any], df_columns: list[str]) -> dict[str, Any]:
    column_set = set(df_columns)

    validated = normalize_plan(plan, plan.get("intent", "filter"))

    validated["filters"] = [f for f in validated["filters"] if f["column"] in column_set]
    validated["group_by"] = [col for col in validated["group_by"] if col in column_set]

    cleaned_aggs = []
    for agg in validated["aggregations"]:
        column = agg.get("column")
        if column is not None and column not in column_set:
            continue
        cleaned_aggs.append(agg)
    validated["aggregations"] = cleaned_aggs

    intent = validated["intent"]

    if intent == "comparison":
        comparison = validated["comparison"]
        column = comparison.get("column") or (validated["group_by"][0] if validated["group_by"] else None)
        _ensure_column_exists(column, column_set, "comparison")
        comparison["column"] = column

        metric = comparison.get("metric") if isinstance(comparison.get("metric"), dict) else {}
        metric_column = metric.get("column")
        if metric_column is not None and metric_column not in column_set:
            metric_column = None
        metric_op = AGGREGATION_ALIASES.get(str(metric.get("op", "count")).lower(), str(metric.get("op", "count")).lower())
        if metric_op not in ALLOWED_AGGREGATIONS:
            metric_op = "count"
        comparison["metric"] = {"column": metric_column, "op": metric_op}

    if intent == "trend":
        trend = validated["trend"]
        date_column = trend.get("date_column")
        if not isinstance(date_column, str) or date_column not in column_set:
            inferred = next((c for c in df_columns if "date" in c.lower()), None)
            if inferred is None:
                raise PlanValidationError("Trend intent requires a date column, but none was found.")
            trend["date_column"] = inferred

        grain = str(trend.get("grain", "month")).lower()
        if grain not in {"day", "week", "month", "quarter", "year"}:
            grain = "month"
        trend["grain"] = grain

        metric = trend.get("metric") if isinstance(trend.get("metric"), dict) else {}
        metric_column = metric.get("column")
        if metric_column is not None and metric_column not in column_set:
            metric_column = None
        metric_op = AGGREGATION_ALIASES.get(str(metric.get("op", "count")).lower(), str(metric.get("op", "count")).lower())
        if metric_op not in ALLOWED_AGGREGATIONS:
            metric_op = "count"
        trend["metric"] = {"column": metric_column, "op": metric_op}

    if intent == "why_change":
        why_change = validated["why_change"]

        date_column = why_change.get("date_column")
        if not isinstance(date_column, str) or date_column not in column_set:
            inferred_date = next((c for c in df_columns if "date" in c.lower()), None)
            if inferred_date is None:
                raise PlanValidationError("Why-change intent requires a date column.")
            why_change["date_column"] = inferred_date

        dimension = why_change.get("dimension")
        if not isinstance(dimension, str) or dimension not in column_set:
            inferred_dimension = next(
                (
                    c
                    for c in df_columns
                    if c != why_change["date_column"] and "id" not in c.lower() and "date" not in c.lower()
                ),
                None,
            )
            if inferred_dimension is None:
                raise PlanValidationError("Why-change intent requires a dimension column.")
            why_change["dimension"] = inferred_dimension

        grain = str(why_change.get("grain", "month")).lower()
        if grain not in {"day", "week", "month", "quarter", "year"}:
            grain = "month"
        why_change["grain"] = grain

        metric = why_change.get("metric") if isinstance(why_change.get("metric"), dict) else {}
        metric_column = metric.get("column")
        if metric_column is not None and metric_column not in column_set:
            metric_column = None
        metric_op = AGGREGATION_ALIASES.get(str(metric.get("op", "sum")).lower(), str(metric.get("op", "sum")).lower())
        if metric_op not in ALLOWED_AGGREGATIONS:
            metric_op = "sum"
        why_change["metric"] = {"column": metric_column, "op": metric_op}

    return validated
