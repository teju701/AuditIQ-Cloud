from __future__ import annotations

from pydantic import BaseModel


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_rows: int
    total_pages: int
    has_prev: bool
    has_next: bool
