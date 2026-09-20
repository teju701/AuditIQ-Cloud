from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    dataset_id: str | None = None
    query: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1)


class ExportPdfRequest(BaseModel):
    dataset_id: str | None = None
    query: str | None = None


class CacheInvalidateRequest(BaseModel):
    dataset_id: str | None = None
    dataset_hash: str | None = None
