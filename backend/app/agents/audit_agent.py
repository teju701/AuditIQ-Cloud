from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
from typing import Any
import pandas as pd

from strands import Agent
from strands.models import BedrockModel

from app.agents.prompts import (
    SYSTEM_AUDIT_PROMPT,
    build_compact_schema_profile,
    build_investigation_prompt,
)
from app.agents.schemas import AgentTraceEvent
from app.agents.tools import ALL_AUDIT_TOOLS, set_tool_context
from app.aws.bedrock_service import bedrock_service
from app.core.settings import AWS_REGION, BEDROCK_MODEL_ID

logger = logging.getLogger("auditiq.agents.audit_agent")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None


class AuditInvestigationAgent:
    def __init__(self) -> None:
        self._model = None
        self._agent = None
        self._init_agent()

    def _init_agent(self) -> None:
        try:
            if bedrock_service.is_available():
                self._model = BedrockModel(
                    model_id=BEDROCK_MODEL_ID,
                    region_name=AWS_REGION,
                )
                self._agent = Agent(
                    model=self._model,
                    system_prompt=SYSTEM_AUDIT_PROMPT,
                    tools=ALL_AUDIT_TOOLS,
                )
        except Exception as e:
            logger.info(f"Strands Bedrock agent could not be pre-initialized ({e}). Will check on query.")
            self._agent = None

    def investigate(
        self,
        user_query: str,
        df: pd.DataFrame,
        metric_dict: dict[str, Any],
        routed_intent: str,
        planning_mode: str = "primary",
    ) -> dict[str, Any]:
        trace: list[dict[str, Any]] = []

        # 1. Intent Recognition milestone
        trace.append(
            AgentTraceEvent(
                step="Intent Classification",
                description=f"Classified audit query intent as '{routed_intent}'.",
                status="completed",
                details={"intent": routed_intent},
                timestamp=_now_iso(),
            ).model_dump()
        )

        # 2. Context & Tool Setup
        ctx = set_tool_context(df)
        schema_summary = build_compact_schema_profile(df)
        trace.append(
            AgentTraceEvent(
                step="Schema Profiling",
                description=f"Compiled compact schema profile for {len(df.columns)} columns across {len(df):,} transactions.",
                status="completed",
                details={"total_rows": len(df), "columns": list(df.columns)},
                timestamp=_now_iso(),
            ).model_dump()
        )

        # 3. Check Bedrock availability
        if not bedrock_service.is_available():
            trace.append(
                AgentTraceEvent(
                    step="Bedrock Investigation",
                    description="Amazon Bedrock runtime unavailable in current environment; falling back to deterministic metric evaluation.",
                    status="warning",
                    details={"provider": "amazon-bedrock", "status": "unavailable"},
                    timestamp=_now_iso(),
                ).model_dump()
            )
            return {
                "narrative": "Amazon Bedrock AI investigation planner is currently unavailable or AWS credentials are not configured.",
                "logic_explanation": "Investigation paused due to planner unavailability.",
                "used_locked_metric": False,
                "metric_used": None,
                "confidence": "low",
                "confidence_reason": "Amazon Bedrock planner unavailable.",
                "plan_generation_status": "failed",
                "planning_mode": planning_mode,
                "agent_trace": trace,
                "plan": {"intent": routed_intent, "filters": [], "group_by": [], "aggregations": [], "sort": [], "limit": 50},
            }

        prompt = build_investigation_prompt(user_query, schema_summary, metric_dict, routed_intent)

        trace.append(
            AgentTraceEvent(
                step="Agent Tool Selection",
                description=f"Invoking Bedrock model '{BEDROCK_MODEL_ID}' with safe audit tools.",
                status="completed",
                details={"model_id": BEDROCK_MODEL_ID, "tools_count": len(ALL_AUDIT_TOOLS)},
                timestamp=_now_iso(),
            ).model_dump()
        )

        try:
            # First attempt: direct invocation through Bedrock service to get structured plan
            raw_response = bedrock_service.invoke_model(
                prompt=prompt,
                system_prompt=SYSTEM_AUDIT_PROMPT,
                max_tokens=2048,
                temperature=0.0,
            )
            parsed = _extract_json_payload(raw_response)
        except Exception as e:
            logger.warning(f"Bedrock invocation exception: {e}")
            parsed = None

        if not parsed:
            trace.append(
                AgentTraceEvent(
                    step="Plan Validation",
                    description="Could not parse a structured plan from the AI response.",
                    status="failed",
                    details={"error": "unparseable_output"},
                    timestamp=_now_iso(),
                ).model_dump()
            )
            return {
                "narrative": "I could not generate a reliable structured plan for this question.",
                "logic_explanation": "Plan generation failed.",
                "used_locked_metric": False,
                "metric_used": None,
                "confidence": "low",
                "confidence_reason": "Bedrock response could not be parsed into structured JSON.",
                "plan_generation_status": "failed",
                "planning_mode": planning_mode,
                "agent_trace": trace,
                "plan": {"intent": routed_intent, "filters": [], "group_by": [], "aggregations": [], "sort": [], "limit": 50},
            }

        # Successful planning
        trace.append(
            AgentTraceEvent(
                step="Plan Verification",
                description=f"Successfully generated evidence plan with intent '{parsed.get('plan', {}).get('intent', routed_intent)}'.",
                status="completed",
                details={
                    "confidence": parsed.get("confidence", "medium"),
                    "used_locked_metric": parsed.get("used_locked_metric", False),
                },
                timestamp=_now_iso(),
            ).model_dump()
        )

        parsed.setdefault("narrative", "Here is the requested audit insight.")
        parsed.setdefault("logic_explanation", "Applied structured query plan.")
        parsed.setdefault("used_locked_metric", False)
        parsed.setdefault("metric_used", None)
        parsed.setdefault("confidence", "medium")
        parsed.setdefault("confidence_reason", "Generated from structured plan.")
        parsed.setdefault("plan_generation_status", "success")
        parsed.setdefault("planning_mode", planning_mode)
        parsed.setdefault("agent_trace", trace)
        parsed.setdefault("plan", {"intent": routed_intent, "filters": [], "group_by": [], "aggregations": [], "sort": [], "limit": 50})

        return parsed


audit_investigation_agent = AuditInvestigationAgent()
