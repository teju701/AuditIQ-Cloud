from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.audit_runs import router as audit_runs_router
from app.api.routes.cache import router as cache_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.export import router as export_router
from app.api.routes.health import router as health_router
from app.api.routes.query import router as query_router
from app.api.routes.upload import router as upload_router
from app.core.settings import APP_SUBTITLE, APP_TITLE, APP_VERSION, CORS_ORIGINS, DEV_MODE

# Configure CloudWatch-friendly structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("auditiq.server")

app = FastAPI(
    title=APP_TITLE,
    description=APP_SUBTITLE,
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"^https?://.*" if DEV_MODE else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cloudwatch_observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or f"req_{uuid4().hex[:8]}"
    start_time = time.time()

    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)

    response.headers["X-Request-Id"] = request_id

    # CloudWatch structured log line (never logs sensitive payload or credentials)
    logger.info(
        f"request_id={request_id} method={request.method} path={request.url.path} "
        f"status={response.status_code} duration_ms={duration_ms}"
    )
    return response


app.include_router(cache_router)
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(export_router)
app.include_router(datasets_router)
app.include_router(audit_runs_router)
app.include_router(health_router)
