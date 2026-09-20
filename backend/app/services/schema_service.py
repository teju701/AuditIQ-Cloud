from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

import pandas as pd


@dataclass
class SchemaMappingResult:
    dataframe: pd.DataFrame
    semantic_mapping: dict[str, str]
    unmapped_columns: list[str]
    schema_profile: dict[str, dict[str, Any]]
    missing_core_fields: list[str]


CANONICAL_ALIASES: dict[str, list[str]] = {
    "transaction_id": ["transaction id", "txn id", "tx id", "id"],
    "vendor_id": ["vendor id", "supplier id"],
    "vendor_name": ["vendor", "vendor name", "supplier", "supplier name"],
    "gstin": ["gst", "gstin", "tax id", "tax identifier"],
    "department": ["dept", "department", "cost center"],
    "category": ["expense category", "category", "spend category"],
    "invoice_date": ["invoice date", "bill date", "txn date", "transaction date"],
    "due_date": ["due date", "payment due date"],
    "payment_date": ["paid date", "payment date", "settlement date"],
    "amount": ["invoice amount", "amount", "total amount", "transaction amount", "value"],
    "has_purchase_order": ["purchase order", "has purchase order", "has po", "po", "po available"],
    "invoice_number": ["invoice number", "bill number"],
    "approved_by": ["approver", "approved by"],
    "status": ["invoice status", "payment status", "status"],
}

CORE_FIELDS = [
    "amount",
    "gstin",
    "vendor_name",
    "has_purchase_order",
    "payment_date",
    "due_date",
    "status",
]


def _normalize_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1", "yes", "y"}:
            return True
        if token in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    return None


def _infer_mapping(columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used_columns: set[str] = set()

    normalized_columns = {col: _normalize_name(col) for col in columns}

    for canonical, aliases in CANONICAL_ALIASES.items():
        candidate_tokens = {_normalize_name(canonical), *(_normalize_name(a) for a in aliases)}

        exact_match = next(
            (
                col
                for col, normalized in normalized_columns.items()
                if normalized in candidate_tokens and col not in used_columns
            ),
            None,
        )
        if exact_match is not None:
            mapping[canonical] = exact_match
            used_columns.add(exact_match)
            continue

        fuzzy_match = next(
            (
                col
                for col, normalized in normalized_columns.items()
                if col not in used_columns
                and any(token and (token in normalized or normalized in token) for token in candidate_tokens)
            ),
            None,
        )
        if fuzzy_match is not None:
            mapping[canonical] = fuzzy_match
            used_columns.add(fuzzy_match)

    return mapping


def _coerce_canonical_types(dataframe: pd.DataFrame) -> pd.DataFrame:
    df = dataframe.copy()

    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    if "has_purchase_order" in df.columns:
        parsed = df["has_purchase_order"].map(_parse_bool)
        if parsed.notna().any():
            df["has_purchase_order"] = parsed.fillna(False)

    return df


def _build_schema_profile(dataframe: pd.DataFrame) -> dict[str, dict[str, Any]]:
    profile: dict[str, dict[str, Any]] = {}
    for col in dataframe.columns:
        series = dataframe[col]
        profile[col] = {
            "dtype": str(series.dtype),
            "null_pct": round(float(series.isna().mean() * 100), 2),
            "sample_values": [str(v) for v in series.dropna().head(3).tolist()],
        }
    return profile


def map_and_profile_dataframe(dataframe: pd.DataFrame) -> SchemaMappingResult:
    original_columns = [str(col) for col in dataframe.columns]
    renamed_input = dataframe.copy()
    renamed_input.columns = original_columns

    semantic_mapping = _infer_mapping(original_columns)

    rename_map = {
        source_col: canonical_name
        for canonical_name, source_col in semantic_mapping.items()
        if source_col != canonical_name and source_col in renamed_input.columns
    }

    mapped_df = renamed_input.rename(columns=rename_map)
    mapped_df = _coerce_canonical_types(mapped_df)

    mapped_sources = set(semantic_mapping.values())
    unmapped_columns = [col for col in original_columns if col not in mapped_sources]

    missing_core_fields = [field for field in CORE_FIELDS if field not in mapped_df.columns]

    schema_profile = _build_schema_profile(mapped_df)

    return SchemaMappingResult(
        dataframe=mapped_df,
        semantic_mapping=semantic_mapping,
        unmapped_columns=unmapped_columns,
        schema_profile=schema_profile,
        missing_core_fields=missing_core_fields,
    )
