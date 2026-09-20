from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class AgentTraceEvent(BaseModel):
    step: str
    description: str
    status: Literal["started", "completed", "warning", "failed"] = "completed"
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None


class ToolExecutionResult(BaseModel):
    tool_name: str
    logic_explanation: str
    row_count: int
    summary_metric: dict[str, Any] = Field(default_factory=dict)
    sample_records: list[dict[str, Any]] = Field(default_factory=list)
    success: bool = True
    error: str | None = None


class AuditFinding(BaseModel):
    narrative: str
    finding: str
    logic_explanation: str
    intent: str = "filter"
    tools_used: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    confidence_reason: str = "Computed from deterministic tool evidence."
    plan: dict[str, Any] = Field(default_factory=dict)
    agent_trace: list[AgentTraceEvent] = Field(default_factory=list)
