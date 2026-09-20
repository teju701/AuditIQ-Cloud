from __future__ import annotations

from typing import Any

import pandas as pd


class PlanExecutionError(RuntimeError):
    pass


def execute_locked_metric(df: pd.DataFrame, metric_name: str) -> tuple[pd.DataFrame, str]:
    metric = (metric_name or "").strip()

    if metric == "duplicate_vendor":
        required = {"gstin", "vendor_name"}
        _ensure_required_columns(df, required, metric)
        dup_gstin = df.groupby("gstin")["vendor_name"].nunique()
        matched = dup_gstin[dup_gstin > 1].index
        result = df[df["gstin"].isin(matched)].copy()
        return result, "Filtered to GSTIN values mapped to multiple vendor names."

    if metric == "round_number_invoice":
        required = {"amount"}
        _ensure_required_columns(df, required, metric)
        amount = pd.to_numeric(df["amount"], errors="coerce")
        result = df[(amount % 1000 == 0)].copy()
        return result, "Filtered to invoice amounts exactly divisible by 1,000."

    if metric == "late_payment":
        required = {"payment_date", "due_date"}
        _ensure_required_columns(df, required, metric)
        working = df.copy()
        working["payment_date"] = pd.to_datetime(working["payment_date"], errors="coerce")
        working["due_date"] = pd.to_datetime(working["due_date"], errors="coerce")
        working["days_late"] = (working["payment_date"] - working["due_date"]).dt.days
        result = working[working["days_late"] > 30].copy()
        return result, "Filtered to records where payment_date is more than 30 days after due_date."

    if metric == "no_purchase_order":
        required = {"amount", "has_purchase_order"}
        _ensure_required_columns(df, required, metric)
        amount = pd.to_numeric(df["amount"], errors="coerce")
        has_po = _series_to_bool(df["has_purchase_order"])
        result = df[(amount > 10000) & (~has_po)].copy()
        return result, "Filtered to transactions above 10,000 without a purchase order."

    if metric == "high_value_transaction":
        required = {"amount"}
        _ensure_required_columns(df, required, metric)
        amount = pd.to_numeric(df["amount"], errors="coerce")
        result = df[amount > 200000].copy()
        return result, "Filtered to transactions above 200,000."

    if metric == "disputed_invoice":
        required = {"status"}
        _ensure_required_columns(df, required, metric)
        result = df[df["status"].astype(str).str.lower() == "disputed"].copy()
        return result, "Filtered to rows where status equals Disputed."

    if metric == "duplicate_invoice":
        required = {"invoice_number"}
        _ensure_required_columns(df, required, metric)
        inv_counts = df["invoice_number"].value_counts()
        duplicate_invoices = inv_counts[inv_counts > 1].index
        result = df[df["invoice_number"].isin(duplicate_invoices)].copy()
        return result, "Filtered to duplicate invoice numbers appearing more than once."

    if metric == "spending_spike":
        required = {"amount"}
        _ensure_required_columns(df, required, metric)
        amounts = pd.to_numeric(df["amount"], errors="coerce").dropna()
        mean_val = amounts.mean()
        std_val = amounts.std()
        threshold = mean_val + (2.0 * std_val) if std_val > 0 else mean_val
        result = df[pd.to_numeric(df["amount"], errors="coerce") > threshold].copy()
        return result, f"Filtered to statistical spending spikes exceeding 2 standard deviations above mean ({round(threshold, 2):,})."

    if metric == "vendor_concentration":
        required = {"vendor_name", "amount"}
        _ensure_required_columns(df, required, metric)
        total_spend = pd.to_numeric(df["amount"], errors="coerce").sum()
        if total_spend > 0:
            vendor_totals = df.groupby("vendor_name")["amount"].sum()
            top_vendors = vendor_totals[vendor_totals / total_spend > 0.12].index
            result = df[df["vendor_name"].isin(top_vendors)].copy()
            return result, "Filtered to transactions from concentrated vendors representing >12% of total spend."
        return df.head(0).copy(), "No transactions with positive amount."

    if metric == "split_payment":
        required = {"vendor_name", "amount"}
        _ensure_required_columns(df, required, metric)
        amounts = pd.to_numeric(df["amount"], errors="coerce")
        # Split transactions: multiple transactions to the same vendor clustered just below round threshold (e.g. 40,000-50,000 or 90,000-100,000)
        near_threshold = df[((amounts >= 45000) & (amounts < 50000)) | ((amounts >= 90000) & (amounts < 100000))].copy()
        vendor_counts = near_threshold["vendor_name"].value_counts()
        split_vendors = vendor_counts[vendor_counts > 1].index
        result = near_threshold[near_threshold["vendor_name"].isin(split_vendors)].copy()
        return result, "Filtered to potential split payments just below approval thresholds from recurring vendors."

    raise PlanExecutionError(f"Locked metric '{metric_name}' is not supported by executor.")


def execute_plan(df: pd.DataFrame, plan: dict[str, Any]) -> pd.DataFrame:
    filtered = _apply_filters(df.copy(), plan.get("filters", []))
    intent = plan.get("intent", "filter")

    if intent == "comparison":
        result = _execute_comparison(filtered, plan)
    elif intent == "trend":
        result = _execute_trend(filtered, plan)
    elif intent == "why_change":
        result = _execute_why_change(filtered, plan)
    else:
        result = _execute_generic(filtered, plan)
        if intent == "breakdown" and not result.empty:
            numeric_cols = [c for c in result.columns if pd.api.types.is_numeric_dtype(result[c])]
            if numeric_cols:
                base_col = numeric_cols[-1]
                total = result[base_col].sum()
                if total != 0:
                    result["share_pct"] = (result[base_col] / total * 100).round(2)

    return _apply_sort_and_limit(result, plan)


def _ensure_required_columns(df: pd.DataFrame, required: set[str], metric_name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise PlanExecutionError(
            f"Locked metric '{metric_name}' requires missing column(s): {', '.join(sorted(missing))}."
        )


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        val = value.strip().lower()
        if val in {"true", "1", "yes", "y"}:
            return True
        if val in {"false", "0", "no", "n"}:
            return False
    return None


def _series_to_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)

    parsed = series.map(_parse_bool)
    if parsed.notna().any():
        return parsed.fillna(False).astype(bool)

    return series.fillna(False).astype(bool)


def _coerce_value_for_series(series: pd.Series, value: Any) -> Any:
    parsed_bool = _parse_bool(value)
    if parsed_bool is not None:
        return parsed_bool
    if pd.api.types.is_bool_dtype(series):
        return value

    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        return numeric

    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(value, errors="coerce")

    return value


def _build_mask(df: pd.DataFrame, column: str, operator: str, value: Any = None, value_to: Any = None) -> pd.Series:
    series = df[column]

    if operator == "is_null":
        return series.isna()
    if operator == "not_null":
        return series.notna()
    if operator == "is_true":
        return _series_to_bool(series)
    if operator == "is_false":
        return ~_series_to_bool(series)

    if operator == "contains":
        return series.astype(str).str.contains(str(value), case=False, na=False)

    if operator in {"in", "not_in"}:
        values = value if isinstance(value, list) else [value]
        mask = series.isin(values)
        return ~mask if operator == "not_in" else mask

    if operator == "between":
        low = _coerce_value_for_series(series, value)
        high = _coerce_value_for_series(series, value_to)
        return series.between(low, high, inclusive="both")

    bool_value = _parse_bool(value)
    if bool_value is not None and operator in {"eq", "ne"}:
        bool_series = _series_to_bool(series)
        if operator == "eq":
            return bool_series == bool_value
        return bool_series != bool_value

    coerced = _coerce_value_for_series(series, value)

    if operator == "eq":
        return series == coerced
    if operator == "ne":
        return series != coerced
    if operator == "gt":
        return series > coerced
    if operator == "gte":
        return series >= coerced
    if operator == "lt":
        return series < coerced
    if operator == "lte":
        return series <= coerced

    raise PlanExecutionError(f"Unsupported filter operator '{operator}'.")


def _apply_filters(df: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    if not filters:
        return df

    mask = pd.Series([True] * len(df), index=df.index)
    for condition in filters:
        column = condition.get("column")
        if column not in df.columns:
            continue

        operator = condition.get("operator", "eq")
        value = condition.get("value")
        value_to = condition.get("value_to")
        mask &= _build_mask(df, column, operator, value, value_to)

    return df[mask].copy()


def _compute_metric(data: pd.DataFrame, column: str | None, op: str) -> float:
    if op == "count":
        if column and column in data.columns:
            return float(data[column].count())
        return float(len(data))

    if column is None or column not in data.columns:
        return 0.0

    series = data[column]

    if op == "count_distinct":
        return float(series.nunique(dropna=True))

    numeric = pd.to_numeric(series, errors="coerce")
    if op == "sum":
        return float(numeric.sum())
    if op == "avg":
        return float(numeric.mean()) if len(numeric.dropna()) else 0.0
    if op == "min":
        return float(numeric.min()) if len(numeric.dropna()) else 0.0
    if op == "max":
        return float(numeric.max()) if len(numeric.dropna()) else 0.0

    raise PlanExecutionError(f"Unsupported aggregation op '{op}'.")


def _execute_generic(df: pd.DataFrame, plan: dict[str, Any]) -> pd.DataFrame:
    group_by = plan.get("group_by", [])
    aggregations = plan.get("aggregations", [])

    if not group_by and not aggregations:
        return df

    if group_by:
        grouped = df.groupby(group_by, dropna=False)
        rows = []
        for key, chunk in grouped:
            row: dict[str, Any] = {}
            if isinstance(key, tuple):
                for idx, col in enumerate(group_by):
                    row[col] = key[idx]
            else:
                row[group_by[0]] = key

            if aggregations:
                for agg in aggregations:
                    row[agg["as"]] = _compute_metric(chunk, agg.get("column"), agg["op"])
            else:
                row["count"] = float(len(chunk))

            rows.append(row)

        return pd.DataFrame(rows)

    aggregate_row = {}
    for agg in aggregations:
        aggregate_row[agg["as"]] = _compute_metric(df, agg.get("column"), agg["op"])
    return pd.DataFrame([aggregate_row])


def _metric_from_spec(spec: dict[str, Any], default_op: str = "count") -> tuple[str | None, str]:
    metric = spec.get("metric") if isinstance(spec.get("metric"), dict) else {}
    column = metric.get("column") if isinstance(metric.get("column"), str) else None
    op = str(metric.get("op", default_op)).strip().lower()
    return column, op


def _aggregate_metric_by_dimension(
    data: pd.DataFrame,
    dimension: str,
    metric_column: str | None,
    metric_op: str,
    output_name: str,
) -> pd.Series:
    if data.empty:
        return pd.Series(dtype="float64", name=output_name)

    values: dict[Any, float] = {}
    grouped = data.groupby(dimension, dropna=False)
    for key, chunk in grouped:
        values[key] = _compute_metric(chunk, metric_column, metric_op)

    result = pd.Series(values, dtype="float64")
    result.name = output_name
    return result


def _execute_comparison(df: pd.DataFrame, plan: dict[str, Any]) -> pd.DataFrame:
    comparison = plan.get("comparison", {})
    column = comparison.get("column") or (plan.get("group_by") or [None])[0]
    if column is None or column not in df.columns:
        raise PlanExecutionError("Comparison intent requires a valid comparison column.")

    left = comparison.get("left_value") or comparison.get("left")
    right = comparison.get("right_value") or comparison.get("right")

    if left is None or right is None:
        top_values = df[column].dropna().astype(str).value_counts().head(2).index.tolist()
        if len(top_values) < 2:
            raise PlanExecutionError("Comparison requires at least two distinct values.")
        left, right = top_values[0], top_values[1]

    metric_column, metric_op = _metric_from_spec(comparison)

    left_df = df[df[column].astype(str) == str(left)]
    right_df = df[df[column].astype(str) == str(right)]

    left_value = _compute_metric(left_df, metric_column, metric_op)
    right_value = _compute_metric(right_df, metric_column, metric_op)

    delta_abs = right_value - left_value
    delta_pct = (delta_abs / left_value * 100.0) if left_value != 0 else None

    return pd.DataFrame(
        [
            {
                "comparison_column": column,
                "left_group": left,
                "left_value": left_value,
                "right_group": right,
                "right_value": right_value,
                "delta_abs": delta_abs,
                "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
            }
        ]
    )


def _bucket_period(series: pd.Series, grain: str) -> pd.Series:
    if grain == "day":
        return series.dt.to_period("D").astype(str)
    if grain == "week":
        return series.dt.to_period("W").astype(str)
    if grain == "quarter":
        return series.dt.to_period("Q").astype(str)
    if grain == "year":
        return series.dt.to_period("Y").astype(str)
    return series.dt.to_period("M").astype(str)


def _execute_trend(df: pd.DataFrame, plan: dict[str, Any]) -> pd.DataFrame:
    trend = plan.get("trend", {})
    date_column = trend.get("date_column")
    if date_column is None or date_column not in df.columns:
        raise PlanExecutionError("Trend intent requires a valid date column.")

    grain = trend.get("grain", "month")
    metric_column, metric_op = _metric_from_spec(trend)

    working = df.copy()
    working[date_column] = pd.to_datetime(working[date_column], errors="coerce")
    working = working[working[date_column].notna()].copy()
    if working.empty:
        return pd.DataFrame(columns=["period", "value", "change_abs", "change_pct"])

    working["period"] = _bucket_period(working[date_column], grain)

    grouped = working.groupby("period", dropna=False)
    rows = []
    for period, chunk in grouped:
        rows.append({"period": period, "value": _compute_metric(chunk, metric_column, metric_op)})

    result = pd.DataFrame(rows).sort_values("period").reset_index(drop=True)
    result["change_abs"] = result["value"].diff().fillna(0.0)
    result["change_pct"] = (result["value"].pct_change() * 100).fillna(0.0).round(2)
    return result


def _execute_why_change(df: pd.DataFrame, plan: dict[str, Any]) -> pd.DataFrame:
    spec = plan.get("why_change", {})
    date_column = spec.get("date_column")
    dimension = spec.get("dimension")

    if date_column is None or date_column not in df.columns:
        raise PlanExecutionError("Why-change intent requires a valid date column.")
    if dimension is None or dimension not in df.columns:
        raise PlanExecutionError("Why-change intent requires a valid dimension column.")

    grain = spec.get("grain", "month")
    metric_column, metric_op = _metric_from_spec(spec, default_op="sum")

    working = df.copy()
    working[date_column] = pd.to_datetime(working[date_column], errors="coerce")
    working = working[working[date_column].notna()].copy()
    if working.empty:
        return pd.DataFrame(columns=[dimension, "base_value", "compare_value", "delta", "contribution_pct"])

    working["period"] = _bucket_period(working[date_column], grain)
    periods = sorted(working["period"].dropna().unique().tolist())
    if len(periods) < 2:
        raise PlanExecutionError("Why-change analysis requires at least two time periods.")

    requested_base = str(spec.get("base_period")) if spec.get("base_period") else None
    requested_compare = str(spec.get("compare_period")) if spec.get("compare_period") else None

    base_period = requested_base if requested_base in periods else periods[-2]
    compare_period = requested_compare if requested_compare in periods else periods[-1]

    if base_period == compare_period:
        base_period = periods[-2]
        compare_period = periods[-1]

    base_df = working[working["period"] == base_period]
    compare_df = working[working["period"] == compare_period]

    base_group = _aggregate_metric_by_dimension(base_df, dimension, metric_column, metric_op, "base_value")
    compare_group = _aggregate_metric_by_dimension(compare_df, dimension, metric_column, metric_op, "compare_value")

    result = pd.concat([base_group, compare_group], axis=1).fillna(0.0).reset_index()
    result = result.rename(columns={"index": dimension})
    result["delta"] = result["compare_value"] - result["base_value"]

    total_delta = result["delta"].sum()
    if total_delta == 0:
        result["contribution_pct"] = 0.0
    else:
        result["contribution_pct"] = (result["delta"] / total_delta * 100).round(2)

    result["base_period"] = base_period
    result["compare_period"] = compare_period

    return result.sort_values("delta", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


def _apply_sort_and_limit(df: pd.DataFrame, plan: dict[str, Any]) -> pd.DataFrame:
    result = df.copy()

    for sort_spec in plan.get("sort", []):
        sort_col = sort_spec.get("column")
        direction = sort_spec.get("direction", "desc")
        if sort_col in result.columns:
            result = result.sort_values(sort_col, ascending=(direction == "asc"))

    limit = int(plan.get("limit", 50))
    return result.head(limit).reset_index(drop=True)
