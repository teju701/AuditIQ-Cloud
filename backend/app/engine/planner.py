from __future__ import annotations

import json
import os
import re
from typing import Any

import google.generativeai as genai
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = genai.GenerativeModel("gemini-2.5-flash")


def _read_int_env(name: str, default: int, min_value: int, max_value: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        value = int(raw)
    except ValueError:
        return default

    return max(min_value, min(value, max_value))


PROMPT_MAX_COLUMNS = _read_int_env("AUDITIQ_PROMPT_MAX_COLUMNS", 24, 5, 100)
PROMPT_MAX_SAMPLE_VALUES = _read_int_env("AUDITIQ_PROMPT_MAX_SAMPLE_VALUES", 3, 1, 10)
PROMPT_MAX_TOP_VALUES = _read_int_env("AUDITIQ_PROMPT_MAX_TOP_VALUES", 5, 2, 20)


def _build_schema_profile(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    profile: dict[str, dict[str, Any]] = {}
    columns = list(df.columns)

    # Prioritize canonical audit fields and then include remaining columns up to configured cap.
    preferred = [
        "transaction_id",
        "vendor_id",
        "vendor_name",
        "gstin",
        "department",
        "category",
        "invoice_date",
        "due_date",
        "payment_date",
        "amount",
        "has_purchase_order",
        "status",
    ]
    ordered = [c for c in preferred if c in columns] + [c for c in columns if c not in preferred]
    selected_columns = ordered[:PROMPT_MAX_COLUMNS]

    for column in selected_columns:
        series = df[column]

        non_null = int(series.notna().sum())
        distinct = int(series.nunique(dropna=True))
        sample_values = [str(v) for v in series.dropna().head(PROMPT_MAX_SAMPLE_VALUES).tolist()]

        top_values: list[str] = []
        if distinct > 0 and distinct <= 50:
            top_values = [
                f"{str(idx)} ({int(cnt)})"
                for idx, cnt in series.astype(str).value_counts(dropna=True).head(PROMPT_MAX_TOP_VALUES).items()
            ]

        profile[column] = {
            "dtype": str(series.dtype),
            "non_null": non_null,
            "distinct": distinct,
            "null_pct": round(float(series.isna().mean() * 100), 2),
            "sample_values": sample_values,
            "top_values": top_values,
        }

    profile["__dataset_summary__"] = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "profiled_columns": int(len(selected_columns)),
        "unprofiled_columns": int(max(0, len(df.columns) - len(selected_columns))),
    }

    return profile


def _build_prompt(
    user_query: str,
    routed_intent: str,
    schema_profile: dict[str, dict[str, Any]],
    metric_dict: dict[str, Any],
    planning_mode: str,
) -> str:
    metrics_str = json.dumps(metric_dict.get("metrics", {}), indent=2)
    field_defs = json.dumps(metric_dict.get("field_definitions", {}), indent=2)

    mode_instruction = (
        "Produce your best deterministic plan."
        if planning_mode == "primary"
        else "Produce an independent second-opinion plan; do not copy any previous plan."
    )

    return f"""You are an internal audit AI assistant that must produce a STRICT STRUCTURED execution plan.
PLANNING MODE: {planning_mode}
MODE INSTRUCTION: {mode_instruction}

ROUTED INTENT (deterministic): {routed_intent}

DATASET PROFILE:
{json.dumps(schema_profile, indent=2)}

LOCKED METRIC DEFINITIONS (use exact definitions only):
{metrics_str}

FIELD DEFINITIONS:
{field_defs}

USER QUERY:
{user_query}

Return ONLY valid JSON with this shape:
{{
  "narrative": "2-3 sentence plain-English answer.",
  "logic_explanation": "One sentence describing the plan.",
  "used_locked_metric": true or false,
  "metric_used": "metric key or null",
  "confidence": "high|medium|low",
  "confidence_reason": "One sentence reason",
  "plan": {{
    "intent": "{routed_intent}",
    "filters": [{{"column": "", "operator": "eq|ne|gt|gte|lt|lte|contains|in|not_in|between|is_null|not_null|is_true|is_false", "value": "", "value_to": ""}}],
    "group_by": [""],
    "aggregations": [{{"column": "", "op": "sum|avg|min|max|count|count_distinct", "as": ""}}],
    "sort": [{{"column": "", "direction": "asc|desc"}}],
    "limit": 50,
    "comparison": {{"column": "", "left_value": "", "right_value": "", "metric": {{"column": "", "op": "sum|avg|min|max|count|count_distinct"}}}},
    "trend": {{"date_column": "", "grain": "day|week|month|quarter|year", "metric": {{"column": "", "op": "sum|avg|min|max|count|count_distinct"}}}},
    "why_change": {{"date_column": "", "grain": "day|week|month|quarter|year", "dimension": "", "metric": {{"column": "", "op": "sum|avg|min|max|count|count_distinct"}}, "base_period": "", "compare_period": ""}}
  }}
}}

Rules:
- Use only columns that appear in DATASET PROFILE.
- If you use a locked metric, set used_locked_metric=true and metric_used to exact key.
- For why-change/comparison/trend intents, fill only relevant sub-object and leave others empty.
- Do not output markdown.
"""


def _extract_json(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group())
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def generate_plan(
    user_query: str,
    df: pd.DataFrame,
    metric_dict: dict[str, Any],
    routed_intent: str,
    planning_mode: str = "primary",
) -> dict[str, Any]:
    schema_profile = _build_schema_profile(df)
    prompt = _build_prompt(user_query, routed_intent, schema_profile, metric_dict, planning_mode)

    try:
        response = MODEL.generate_content(prompt)
        raw = (response.text or "").strip()
    except Exception:
        raw = ""

    parsed = _extract_json(raw) if raw else None
    if parsed is None:
        return {
            "narrative": "I could not generate a reliable structured plan for this question.",
            "logic_explanation": "Plan generation failed.",
            "used_locked_metric": False,
            "metric_used": None,
            "confidence": "low",
            "confidence_reason": "LLM response could not be parsed into structured JSON.",
            "plan_generation_status": "failed",
            "planning_mode": planning_mode,
            "plan": {"intent": routed_intent, "filters": [], "group_by": [], "aggregations": [], "sort": [], "limit": 50},
        }

    parsed.setdefault("narrative", "Here is the requested audit insight.")
    parsed.setdefault("logic_explanation", "Applied structured query plan.")
    parsed.setdefault("used_locked_metric", False)
    parsed.setdefault("metric_used", None)
    parsed.setdefault("confidence", "medium")
    parsed.setdefault("confidence_reason", "Generated from structured plan.")
    parsed.setdefault("plan_generation_status", "success")
    parsed.setdefault("planning_mode", planning_mode)
    parsed.setdefault("plan", {"intent": routed_intent, "filters": [], "group_by": [], "aggregations": [], "sort": [], "limit": 50})

    return parsed
