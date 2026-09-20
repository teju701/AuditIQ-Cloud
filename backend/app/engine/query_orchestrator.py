from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any

import pandas as pd

from app.agents.audit_agent import audit_investigation_agent
from app.agents.schemas import AgentTraceEvent
from app.core.settings import ENABLE_DUAL_RUN_CONSENSUS
from app.engine.consensus import build_consensus_report, single_path_consensus
from app.engine.executor import PlanExecutionError, execute_locked_metric, execute_plan
from app.engine.intent_router import classify_intent
from app.engine.metric_resolver import resolve_locked_metric
from app.engine.narrative_grounding import verify_narrative_against_result
from app.engine.validator import PlanValidationError, normalize_plan, validate_and_sanitize_plan
from app.services.provenance_service import build_provenance

BASE_DIR = os.path.dirname(__file__)
METRIC_FILE = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "metric_dictionary.json"))
with open(METRIC_FILE, "r", encoding="utf-8") as f:
    METRIC_DICT = json.load(f)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _failure_response(message: str, reason: str) -> dict[str, Any]:
    return {
        "narrative": message,
        "pandas_code": None,
        "logic_explanation": "",
        "used_locked_metric": False,
        "metric_used": None,
        "confidence": "low",
        "confidence_reason": reason,
        "result_df": None,
        "row_count": 0,
        "plan_intent": "filter",
        "plan_validated": False,
        "execution_mode": "failed",
        "provenance": {},
        "narrative_grounding": {"status": "fail", "issues": [reason], "verified_claims": []},
        "metric_resolution": {
            "status": "none",
            "metric": None,
            "candidates": [],
            "reason": reason,
        },
        "consensus": single_path_consensus("failed", "Query failed before consensus could run."),
        "agent_trace": [
            AgentTraceEvent(
                step="Execution Failure",
                description=f"Query terminated: {message}",
                status="failed",
                details={"reason": reason},
                timestamp=_now_iso(),
            ).model_dump()
        ],
    }


def generate_plan(
    user_query: str,
    df: pd.DataFrame,
    metric_dict: dict[str, Any],
    routed_intent: str,
    planning_mode: str = "primary",
) -> dict[str, Any]:
    return audit_investigation_agent.investigate(
        user_query=user_query,
        df=df,
        metric_dict=metric_dict,
        routed_intent=routed_intent,
        planning_mode=planning_mode,
    )


def _append_reason(base_reason: str, extra_reason: str) -> str:
    if not extra_reason:
        return base_reason
    if not base_reason:
        return extra_reason
    if extra_reason in base_reason:
        return base_reason
    return f"{base_reason}; {extra_reason}"


def run_query(user_query: str, df: pd.DataFrame) -> dict[str, Any]:
    if df is None or len(df.columns) == 0:
        return _failure_response(
            "Dataset has no usable columns.",
            "Structured plan execution requires a valid dataset schema.",
        )

    trace: list[dict[str, Any]] = []

    # Step 1: Intent Classification
    routed_intent = classify_intent(user_query)
    trace.append(
        AgentTraceEvent(
            step="Intent Classification",
            description=f"Parsed user question; classified intent as '{routed_intent}'.",
            status="completed",
            details={"routed_intent": routed_intent},
            timestamp=_now_iso(),
        ).model_dump()
    )

    # Step 2: Deterministic Locked Metric Resolution
    metric_resolution = resolve_locked_metric(user_query, list(METRIC_DICT.get("metrics", {}).keys()))

    narrative = "Here are the requested audit insights."
    logic_explanation = "Applied structured query plan."
    confidence = "medium"
    confidence_reason = "Generated from structured plan."
    used_locked_metric = False
    metric_used: str | None = None

    normalized_plan = {"intent": routed_intent, "filters": [], "group_by": [], "aggregations": [], "sort": [], "limit": 50}

    result_df: pd.DataFrame | None = None
    execution_mode = "safe_plan"
    plan_validated = False
    consensus = single_path_consensus("failed", "Consensus not executed.")

    if metric_resolution.status == "ambiguous":
        options = ", ".join(metric_resolution.candidates)
        narrative = (
            f"Your query maps to multiple locked metrics ({options}). "
            "Please clarify which one to run."
        )
        logic_explanation = "Execution stopped because deterministic metric resolution was ambiguous."
        confidence = "low"
        confidence_reason = metric_resolution.reason
        execution_mode = "clarification_required"
        plan_validated = False
        consensus = single_path_consensus(execution_mode, "Execution stopped for clarification.")
        trace.append(
            AgentTraceEvent(
                step="Metric Resolution",
                description=f"Ambiguous query matched multiple rules: {options}.",
                status="warning",
                details={"candidates": metric_resolution.candidates},
                timestamp=_now_iso(),
            ).model_dump()
        )
    elif metric_resolution.status == "matched" and metric_resolution.metric:
        metric_used = metric_resolution.metric
        metric_meta = METRIC_DICT.get("metrics", {}).get(metric_used, {})
        narrative = (
            f"Applied locked metric '{metric_used}'. "
            f"{metric_meta.get('description', '')}"
        ).strip()
        confidence = "high"
        confidence_reason = "Metric resolved deterministically before AI planning."

        trace.append(
            AgentTraceEvent(
                step="Deterministic Tool Routing",
                description=f"Matched locked audit rule '{metric_used}': {metric_meta.get('description', '')}",
                status="completed",
                details={"metric": metric_used},
                timestamp=_now_iso(),
            ).model_dump()
        )

        try:
            result_df, locked_logic = execute_locked_metric(df, metric_used)
            logic_explanation = locked_logic or "Executed locked metric definition."
            used_locked_metric = True
            execution_mode = "locked_metric"
            plan_validated = True
            narrative = f"{narrative} Found {len(result_df)} matching records."
            consensus = single_path_consensus(execution_mode, "Locked metric path is deterministic.")

            trace.append(
                AgentTraceEvent(
                    step="Deterministic Execution",
                    description=f"Executed allow-listed rule in Pandas. Computed {len(result_df)} matching records.",
                    status="completed",
                    details={"matched_count": len(result_df)},
                    timestamp=_now_iso(),
                ).model_dump()
            )
        except (PlanValidationError, PlanExecutionError) as exc:
            execution_mode = "failed"
            confidence = "low"
            confidence_reason = str(exc)
            narrative = f"{narrative} (Execution note: {str(exc)})"
            result_df = None
            consensus = single_path_consensus(execution_mode, "Locked metric execution failed.")
        except Exception as exc:
            execution_mode = "failed"
            confidence = "low"
            confidence_reason = "Unexpected locked metric execution error"
            narrative = f"{narrative} (Execution note: {str(exc)})"
            result_df = None
            consensus = single_path_consensus(execution_mode, "Locked metric execution failed unexpectedly.")
    else:
        # Flexible AI-assisted investigation via Strands Bedrock Agent
        trace.append(
            AgentTraceEvent(
                step="AI Agent Investigation",
                description="Query requires exploratory analysis; invoking Strands Audit Agent with Amazon Bedrock.",
                status="started",
                details={"intent": routed_intent},
                timestamp=_now_iso(),
            ).model_dump()
        )

        plan_result = generate_plan(
            user_query,
            df,
            METRIC_DICT,
            routed_intent,
            planning_mode="primary",
        )
        # Merge agent internal trace
        trace.extend(plan_result.get("agent_trace", []))

        plan_generation_status = str(plan_result.get("plan_generation_status", "success")).strip().lower()
        narrative = str(plan_result.get("narrative", narrative))
        logic_explanation = str(plan_result.get("logic_explanation", logic_explanation))
        confidence = str(plan_result.get("confidence", confidence)).lower()
        confidence_reason = str(plan_result.get("confidence_reason", confidence_reason))
        used_locked_metric = bool(plan_result.get("used_locked_metric", False))
        metric_used = plan_result.get("metric_used")

        if plan_generation_status != "success":
            used_locked_metric = False
            metric_used = None
            execution_mode = "planner_unavailable"
            plan_validated = False
            result_df = None
            consensus = single_path_consensus(
                execution_mode,
                "Amazon Bedrock planner could not produce a parseable structured plan.",
            )
        else:
            normalized_plan = normalize_plan(plan_result.get("plan"), routed_intent)

            try:
                if used_locked_metric and isinstance(metric_used, str) and metric_used in METRIC_DICT.get("metrics", {}):
                    result_df, locked_logic = execute_locked_metric(df, metric_used)
                    logic_explanation = locked_logic or logic_explanation
                    execution_mode = "locked_metric"
                    plan_validated = True
                    consensus = single_path_consensus(execution_mode, "Locked metric path executed from planner output.")
                else:
                    used_locked_metric = False
                    metric_used = None
                    validated_plan = validate_and_sanitize_plan(normalized_plan, list(df.columns))
                    result_df = execute_plan(df, validated_plan)
                    normalized_plan = validated_plan
                    execution_mode = "safe_plan"
                    plan_validated = True

                    trace.append(
                        AgentTraceEvent(
                            step="Safe Sandbox Execution",
                            description=f"Executed sanitized plan ({validated_plan.get('intent')}) in Pandas. Retrieved {len(result_df)} records.",
                            status="completed",
                            details={"row_count": len(result_df)},
                            timestamp=_now_iso(),
                        ).model_dump()
                    )

                    if ENABLE_DUAL_RUN_CONSENSUS:
                        secondary_plan: dict | None = None
                        secondary_df: pd.DataFrame | None = None
                        secondary_error: str | None = None

                        try:
                            secondary_plan_result = generate_plan(
                                user_query,
                                df,
                                METRIC_DICT,
                                routed_intent,
                                planning_mode="secondary",
                            )
                            secondary_status = str(
                                secondary_plan_result.get("plan_generation_status", "success")
                            ).strip().lower()
                            if secondary_status != "success":
                                secondary_error = str(
                                    secondary_plan_result.get(
                                        "confidence_reason",
                                        "Secondary planner could not produce a parseable structured plan.",
                                    )
                                )
                            else:
                                secondary_plan = normalize_plan(secondary_plan_result.get("plan"), routed_intent)
                                secondary_validated = validate_and_sanitize_plan(secondary_plan, list(df.columns))
                                secondary_df = execute_plan(df, secondary_validated)
                                secondary_plan = secondary_validated
                        except (PlanValidationError, PlanExecutionError) as secondary_exc:
                            secondary_error = str(secondary_exc)
                        except Exception as secondary_exc:
                            secondary_error = f"Unexpected secondary run error: {str(secondary_exc)}"

                        consensus = build_consensus_report(
                            primary_plan=normalized_plan,
                            secondary_plan=secondary_plan,
                            primary_result_df=result_df,
                            secondary_result_df=secondary_df,
                            secondary_error=secondary_error,
                        )
                    else:
                        consensus = single_path_consensus(execution_mode, "Dual-run consensus disabled by configuration.")
            except (PlanValidationError, PlanExecutionError) as exc:
                execution_mode = "failed"
                confidence = "low"
                confidence_reason = str(exc)
                narrative = f"{narrative} (Execution note: {str(exc)})"
                result_df = None
                consensus = single_path_consensus(execution_mode, "Primary safe plan execution failed.")
            except Exception as exc:
                execution_mode = "failed"
                confidence = "low"
                confidence_reason = "Unexpected plan execution error"
                narrative = f"{narrative} (Execution note: {str(exc)})"
                result_df = None
                consensus = single_path_consensus(execution_mode, "Primary safe plan execution failed unexpectedly.")

    if isinstance(result_df, pd.Series):
        result_df = result_df.reset_index()
    if result_df is not None and not isinstance(result_df, pd.DataFrame):
        result_df = None

    row_count = len(result_df) if result_df is not None else 0

    if execution_mode == "locked_metric":
        pandas_code = f"locked_metric::{metric_used}"
    elif execution_mode == "safe_plan":
        pandas_code = json.dumps(normalized_plan)
    else:
        pandas_code = None

    provenance = build_provenance(
        input_df=df,
        result_df=result_df,
        execution_mode=execution_mode,
        plan_intent=routed_intent,
        plan_payload=pandas_code,
        used_locked_metric=used_locked_metric,
        metric_used=metric_used,
    )

    narrative_grounding = verify_narrative_against_result(
        narrative=narrative,
        result_df=result_df,
        row_count=row_count,
    )

    if narrative_grounding.get("status") == "fail":
        confidence = "low"
        confidence_reason = _append_reason(
            confidence_reason,
            "Narrative grounding failed against computed evidence.",
        )
    elif narrative_grounding.get("status") == "warning":
        if confidence == "high":
            confidence = "medium"
        confidence_reason = _append_reason(
            confidence_reason,
            "Narrative includes partially grounded numeric claims.",
        )

    consensus_status = str(consensus.get("status", "low"))
    if consensus_status == "low":
        confidence = "low"
        confidence_reason = _append_reason(
            confidence_reason,
            "Dual-run consensus is low.",
        )
    elif consensus_status == "medium" and confidence == "high":
        confidence = "medium"
        confidence_reason = _append_reason(
            confidence_reason,
            "Dual-run consensus is medium.",
        )

    trace.append(
        AgentTraceEvent(
            step="Verification & Grounding",
            description=f"Verified narrative claims against computed evidence ({narrative_grounding.get('status', 'pass').upper()}).",
            status="completed" if narrative_grounding.get("status") != "fail" else "failed",
            details={"grounding_status": narrative_grounding.get("status")},
            timestamp=_now_iso(),
        ).model_dump()
    )

    return {
        "narrative": narrative,
        "pandas_code": pandas_code,
        "logic_explanation": logic_explanation,
        "used_locked_metric": used_locked_metric,
        "metric_used": metric_used,
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "result_df": result_df,
        "row_count": row_count,
        "plan_intent": routed_intent,
        "plan_validated": plan_validated,
        "execution_mode": execution_mode,
        "provenance": provenance,
        "narrative_grounding": narrative_grounding,
        "metric_resolution": {
            "status": metric_resolution.status,
            "metric": metric_resolution.metric,
            "candidates": metric_resolution.candidates,
            "reason": metric_resolution.reason,
        },
        "consensus": consensus,
        "agent_trace": trace,
    }