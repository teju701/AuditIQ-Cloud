def compute_trust_score(query_result: dict) -> dict:
    score = 100
    reasons = []

    if not query_result.get("used_locked_metric"):
        score -= 20
        reasons.append("Query used inferred logic rather than a locked metric definition.")

    row_count = query_result.get("row_count", 0)
    if row_count == 0:
        score -= 30
        reasons.append("No rows matched — query may be too specific or use incorrect field values.")
    elif row_count > 400:
        score -= 15
        reasons.append("Very high row count — query may be too broad.")

    if query_result.get("confidence") == "low":
        score -= 25
        reasons.append(query_result.get("confidence_reason", "AI reported low confidence."))
    elif query_result.get("confidence") == "medium":
        score -= 10

    grounding = query_result.get("narrative_grounding") or {}
    grounding_status = grounding.get("status")
    if grounding_status == "fail":
        score -= 15
        reasons.append("Narrative claims are not fully grounded in computed evidence.")
    elif grounding_status == "warning":
        score -= 8
        reasons.append("Narrative includes partially grounded numeric claims.")

    provenance = query_result.get("provenance") or {}
    coverage = provenance.get("evidence_coverage_pct")
    if isinstance(coverage, (int, float)):
        if query_result.get("row_count", 0) > 0 and coverage < 0.05:
            score -= 6
            reasons.append("Very narrow evidence slice was returned; verify representativeness.")
        elif coverage > 90:
            score -= 8
            reasons.append("Very broad evidence slice was returned; answer may be overly general.")

    consensus = query_result.get("consensus") or {}
    if consensus.get("enabled"):
        status = consensus.get("status")
        if status == "low":
            score -= 20
            reasons.append("Dual-run consensus is low — independent reasoning paths diverged.")
        elif status == "medium":
            score -= 8
            reasons.append("Dual-run consensus is medium — validate before finalizing conclusions.")
    elif consensus.get("reason"):
        reasons.append(consensus.get("reason"))

    executed_safely = (
        query_result.get("execution_mode") in {"safe_plan", "locked_metric"}
        and query_result.get("plan_validated") is True
    )

    if not executed_safely and query_result.get("pandas_code") is None:
        score -= 40
        reasons.append("Structured query plan could not be executed safely.")

    score = max(0, score)

    if score >= 75:
        level = "High"
        color = "green"
    elif score >= 45:
        level = "Medium"
        color = "amber"
    else:
        level = "Low"
        color = "red"

    return {
        "score": score,
        "level": level,
        "color": color,
        "reasons": reasons if reasons else ["Answer is based on a locked metric definition with clean execution."]
    }