from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.reproducibility_service import normalize_query


@dataclass
class LockedMetricResolution:
    status: str
    metric: str | None
    candidates: list[str]
    reason: str


METRIC_PATTERNS: dict[str, list[str]] = {
    "duplicate_vendor": [
        r"\bduplicate\s+gstin\b",
        r"\bsame\s+gstin\b",
        r"\bshared\s+gstin\b",
        r"\bmultiple\s+vendor\b.*\bgstin\b",
        r"\bduplicate\s+vendor\b",
    ],
    "round_number_invoice": [
        r"\bround\s+number\b",
        r"\bdivisible\s+by\s+1[,]?000\b",
        r"\bamount\s+exactly\s+divisible\b",
    ],
    "late_payment": [
        r"\blate\s+payments?\b",
        r"\boverdue\b",
        r"\bpast\s+due\b",
        r"\bpayment\s+delay\b",
        r"\bpaid\s+late\b",
    ],
    "no_purchase_order": [
        r"\bno\s+purchase\s+order\b",
        r"\bwithout\s+purchase\s+order\b",
        r"\bno\s+po\b",
        r"\bwithout\s+po\b",
    ],
    "high_value_transaction": [
        r"\bhigh\s+value\b",
        r"\babove\s+2[,]?00[,]?000\b",
        r"\bover\s+2[,]?00[,]?000\b",
        r"\bgreater\s+than\s+2[,]?00[,]?000\b",
        r"\babove\s+200000\b",
        r"\bover\s+200000\b",
    ],
    "disputed_invoice": [
        r"\bdisputed\s+invoices?\b",
        r"\bstatus\s+disputed\b",
        r"\bdisputed\b",
    ],
    "duplicate_invoice": [
        r"\bduplicate\s+invoice\s+numbers?\b",
        r"\bduplicate\s+invoices?\b",
        r"\bsame\s+invoice\s+number\b",
        r"\brepeated\s+invoice\b",
    ],
    "spending_spike": [
        r"\bspending\s+spikes?\b",
        r"\bunusual\s+spike\b",
        r"\bexpense\s+spikes?\b",
        r"\bamount\s+spikes?\b",
        r"\boutlier\s+spending\b",
    ],
    "vendor_concentration": [
        r"\bvendor\s+concentration\b",
        r"\bconcentrated\s+vendors?\b",
        r"\bmajor\s+vendor\s+share\b",
        r"\bvendor\s+dependency\b",
    ],
    "split_payment": [
        r"\bsplit\s+payments?\b",
        r"\bthreshold\s+splitting\b",
        r"\bpotential\s+split\b",
        r"\bsplit\s+transactions?\b",
    ],
}


def _score_metric(query: str, metric_key: str) -> int:
    patterns = METRIC_PATTERNS.get(metric_key, [])
    return sum(1 for pattern in patterns if re.search(pattern, query, flags=re.IGNORECASE))


def _fallback_metrics_from_query_text(query: str, metric_keys: list[str]) -> list[str]:
    if "metric" in query and "locked" in query:
        return metric_keys
    return []


def resolve_locked_metric(user_query: str, metric_keys: list[str]) -> LockedMetricResolution:
    query = normalize_query(user_query)

    scored: list[tuple[str, int]] = []
    for metric_key in metric_keys:
        score = _score_metric(query, metric_key)
        if score > 0:
            scored.append((metric_key, score))

    if not scored:
        fallback = _fallback_metrics_from_query_text(query, metric_keys)
        if len(fallback) == 1:
            return LockedMetricResolution(
                status="matched",
                metric=fallback[0],
                candidates=fallback,
                reason="Matched a single locked metric fallback pattern.",
            )
        if len(fallback) > 1:
            return LockedMetricResolution(
                status="ambiguous",
                metric=None,
                candidates=sorted(fallback),
                reason="Query references locked metrics but does not specify one uniquely.",
            )
        return LockedMetricResolution(
            status="none",
            metric=None,
            candidates=[],
            reason="No deterministic locked metric pattern matched.",
        )

    scored.sort(key=lambda item: item[1], reverse=True)
    top_score = scored[0][1]
    top_candidates = sorted([metric for metric, score in scored if score == top_score])

    if len(top_candidates) == 1:
        return LockedMetricResolution(
            status="matched",
            metric=top_candidates[0],
            candidates=top_candidates,
            reason="Deterministic metric pattern matched with highest score.",
        )

    return LockedMetricResolution(
        status="ambiguous",
        metric=None,
        candidates=top_candidates,
        reason="Multiple locked metrics matched with equal confidence.",
    )
