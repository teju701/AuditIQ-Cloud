from __future__ import annotations

import re
from typing import Any

import pandas as pd


ROW_COUNT_CLAIM_PATTERN = re.compile(
    r"\b([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\s+(rows?|records?|transactions?|invoices?|payments?)\b",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(
    r"(?:₹\s*)?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)"
)


def _to_float(token: str) -> float | None:
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def _build_supported_numbers(result_df: pd.DataFrame | None, row_count: int) -> list[float]:
    supported: list[float] = [float(row_count)]

    if result_df is None or result_df.empty:
        return supported

    numeric_df = result_df.select_dtypes(include="number")
    if numeric_df.empty:
        return supported

    for col in numeric_df.columns:
        series = numeric_df[col].dropna()
        if series.empty:
            continue
        supported.append(float(series.sum()))
        supported.append(float(series.min()))
        supported.append(float(series.max()))
        supported.extend(float(v) for v in series.head(20).tolist())

    return supported


def _number_supported(value: float, supported: list[float]) -> bool:
    for evidence in supported:
        if abs(value - evidence) <= 0.01:
            return True
        if abs(evidence) > 0 and abs((value - evidence) / evidence) <= 0.005:
            return True
    return False


def verify_narrative_against_result(
    narrative: str,
    result_df: pd.DataFrame | None,
    row_count: int,
) -> dict[str, Any]:
    text = (narrative or "").strip()
    lowered = text.lower()

    issues: list[str] = []
    verified_claims: list[str] = []

    row_claims = []
    for match in ROW_COUNT_CLAIM_PATTERN.finditer(text):
        raw_number = match.group(1)
        parsed = _to_float(raw_number)
        if parsed is None:
            continue
        row_claims.append(int(parsed))
        if int(parsed) == int(row_count):
            verified_claims.append(f"Row-count claim matches result: {int(parsed)}")
        else:
            issues.append(f"Row-count claim mismatch: narrative says {int(parsed)} but result has {int(row_count)}")

    no_rows_phrase = any(
        phrase in lowered
        for phrase in ["no rows", "no records", "no matching", "did not find any"]
    )
    if no_rows_phrase and row_count > 0:
        issues.append("Narrative says no matches, but result contains rows.")

    supported_numbers = _build_supported_numbers(result_df, row_count)
    unsupported_numbers: list[float] = []
    for match in NUMBER_PATTERN.finditer(text):
        parsed = _to_float(match.group(1))
        if parsed is None:
            continue
        if not _number_supported(parsed, supported_numbers):
            unsupported_numbers.append(parsed)

    if unsupported_numbers and len(unsupported_numbers) >= 2:
        issues.append(
            "Some numeric narrative claims are not directly grounded in computed evidence: "
            + ", ".join(str(v) for v in unsupported_numbers[:5])
        )

    if any("mismatch" in issue.lower() for issue in issues):
        status = "fail"
    elif issues:
        status = "warning"
    else:
        status = "pass"

    return {
        "status": status,
        "issues": issues,
        "verified_claims": verified_claims,
        "row_count_claims": row_claims,
        "unsupported_numbers": unsupported_numbers[:10],
    }
