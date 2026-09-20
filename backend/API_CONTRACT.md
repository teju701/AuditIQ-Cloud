# AuditIQ Backend API Contract

Base URL: `http://localhost:8000`

## 1. Health

Endpoint: `GET /health`

Purpose:
- Check service health.
- Check dataset session state.
- Check cache stats and config.

Success response (`200`):
```json
{
  "status": "ok",
  "dataset_loaded": true,
  "datasets_loaded": 1,
  "cache": {
    "enabled": true,
    "cacheable_execution_modes": ["locked_metric", "safe_plan"],
    "ttl_seconds": 900,
    "max_size": 500,
    "cached_results": 3,
    "query_index_entries": 3,
    "hits": 2,
    "misses": 1,
    "evictions": 0,
    "expirations": 0,
    "invalidations": 0
  }
}
```

## 2. Upload Dataset

Endpoint: `POST /upload`

Request:
- Multipart form-data
- Field name: `file`
- Supported file extensions: `.csv`, `.xlsx`, `.xls`

Example:
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@../data/transactions.csv"
```

Success response (`200`) fields:
- `dataset_id`: unique session id used by all later calls.
- `dataset_hash`: deterministic dataset fingerprint.
- `rows`, `columns`
- `semantic_mapping`, `unmapped_columns`, `missing_core_fields`, `schema_profile`
- `anomalies`
- `preview`

Error responses:
- `400`: unsupported file type.

## 3. Query

Endpoint: `POST /query`

Request JSON:
```json
{
  "dataset_id": "<required>",
  "query": "Show vendors who share the same GSTIN",
  "page": 1,
  "page_size": 50
}
```

Pagination request notes:
- `page` is optional and defaults to `1`.
- `page_size` is optional and defaults to `50` (max `200`).

Success response (`200`) fields:
- Core answer:
  - `narrative`, `logic_explanation`
  - `execution_mode` (`locked_metric`, `safe_plan`, `clarification_required`, `planner_unavailable`, `failed`)
  - `plan_intent` (`filter`, `comparison`, `trend`, `breakdown`, `why_change`)
  - `row_count`, `columns`, `result_records`
  - `pagination` (`page`, `page_size`, `total_rows`, `total_pages`, `has_prev`, `has_next`)
- Trust and explainability:
  - `trust`
  - `provenance`
  - `narrative_grounding`
  - `metric_resolution`
  - `consensus`
- Reproducibility:
  - `replay_id`
  - `reproducibility`
- Cache metadata:
  - `cache` (`hit`, `enabled`, `skipped`, `reason`, `cache_key`, `normalized_query`)

Error responses:
- `400`: missing `dataset_id` or empty query.
- `404`: unknown dataset session.

## 4. Export PDF

Endpoint: `POST /export-pdf`

Request JSON:
```json
{
  "dataset_id": "<required>",
  "query": "Show vendors who share the same GSTIN"
}
```

Success response:
- Status: `200`
- Body: PDF bytes (`application/pdf`)
- Headers:
  - `X-Replay-Id`
  - `X-Cache-Hit`
  - `Content-Disposition`

PDF sections include:
- Trust score
- Query and narrative
- Filter logic
- Reproducibility
- Evidence provenance
- Narrative grounding
- Evidence table

Error responses:
- `400`: missing `dataset_id` or empty query.
- `404`: unknown dataset session.

## 5. Cache Invalidation

Endpoint: `POST /cache/invalidate`

Request modes:
1. Clear entire cache:
```json
{}
```
2. Invalidate by dataset session:
```json
{
  "dataset_id": "<dataset_id>"
}
```
3. Invalidate by dataset hash:
```json
{
  "dataset_hash": "<dataset_hash>"
}
```

Success response (`200`) includes:
- `scope` (`all`, `dataset`, `disabled`)
- `removed_entries`
- `cache` stats snapshot

## 6. Test Endpoint

Endpoint: `GET /test`

Response (`200`):
```json
{"message": "Auditiq backend is running"}
```

## Environment Variables

Supported backend cache settings:
- `AUDITIQ_CACHE_ENABLED` (`true`/`false`, default `true`)
- `AUDITIQ_CACHE_TTL_SECONDS` (default `900`, clamped `0..86400`)
- `AUDITIQ_CACHE_MAX_SIZE` (default `500`, clamped `1..5000`)

Supported backend consensus/settings:
- `AUDITIQ_ENABLE_DUAL_RUN_CONSENSUS` (`true`/`false`, default `true`)
- `AUDITIQ_PROMPT_MAX_COLUMNS` (default `24`, compacts schema profile in planner prompt)
- `AUDITIQ_PROMPT_MAX_SAMPLE_VALUES` (default `3`)
- `AUDITIQ_PROMPT_MAX_TOP_VALUES` (default `5`)

## Smoke Test Sequence

1. `GET /health`
2. `POST /upload`
3. `POST /query` with same query twice and verify `cache.hit` becomes `true` on second run.
4. `POST /cache/invalidate` for dataset id and re-run query, verify `cache.hit` returns `false`.
5. `POST /export-pdf` and verify `X-Replay-Id` and `X-Cache-Hit` headers.
