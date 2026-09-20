import re
from typing import Literal

QueryIntent = Literal["why_change", "comparison", "breakdown", "trend", "filter"]


WHY_CHANGE_PATTERNS = [
    r"\bwhy\b.*\b(change|changed|increase|decrease|drop|spike|rise|fell|fall)\b",
    r"\b(reason|cause|driver|drivers)\b",
    r"\bwhat caused\b",
]

COMPARISON_PATTERNS = [
    r"\bcompare\b",
    r"\bversus\b",
    r"\bvs\b",
    r"\bdifference between\b",
]

BREAKDOWN_PATTERNS = [
    r"\bbreakdown\b",
    r"\bcomposition\b",
    r"\bsplit by\b",
    r"\bcontribution\b",
]

TREND_PATTERNS = [
    r"\btrend\b",
    r"\bover time\b",
    r"\bmonth(?:ly)?\b",
    r"\bquarter(?:ly)?\b",
    r"\byear(?:ly)?\b",
]


def _matches_any(query: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, query) is not None for pattern in patterns)


def classify_intent(user_query: str) -> QueryIntent:
    query = (user_query or "").strip().lower()
    if not query:
        return "filter"

    if _matches_any(query, WHY_CHANGE_PATTERNS):
        return "why_change"
    if _matches_any(query, COMPARISON_PATTERNS):
        return "comparison"
    if _matches_any(query, BREAKDOWN_PATTERNS):
        return "breakdown"
    if _matches_any(query, TREND_PATTERNS):
        return "trend"

    return "filter"
