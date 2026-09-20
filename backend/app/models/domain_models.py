from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QueryContext:
    dataset_id: str
    dataset_hash: str
    user_query: str
