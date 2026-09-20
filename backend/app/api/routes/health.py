from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import dataset_store, query_result_cache
from app.aws.bedrock_service import bedrock_service
from app.aws.dynamodb_service import dynamodb_service
from app.aws.s3_service import s3_service
from app.core.settings import (
    APP_SUBTITLE,
    APP_TITLE,
    APP_VERSION,
    AWS_REGION,
    BEDROCK_MODEL_ID,
    CACHEABLE_EXECUTION_MODES,
    CACHE_ENABLED,
    DEV_MODE,
)

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    loaded = dataset_store.count()
    cache_stats = query_result_cache.dump_stats()
    cache_stats.update({
        "enabled": CACHE_ENABLED,
        "cacheable_execution_modes": sorted(CACHEABLE_EXECUTION_MODES),
    })

    s3_ok = s3_service.is_healthy()
    dynamo_ok = dynamodb_service.is_healthy()
    bedrock_ok = bedrock_service.is_available()

    return {
        "status": "ok",
        "service": APP_TITLE,
        "subtitle": APP_SUBTITLE,
        "version": APP_VERSION,
        "environment": "development" if DEV_MODE else "production",
        "aws_region": AWS_REGION,
        "dataset_storage": "s3" if s3_ok else "s3_local_fallback",
        "metadata_storage": "dynamodb" if dynamo_ok else "dynamodb_local_fallback",
        "ai_provider": "amazon-bedrock" if bedrock_ok else "amazon-bedrock-offline",
        "bedrock_model": BEDROCK_MODEL_ID,
        "agent_framework": "strands",
        "dataset_loaded": loaded > 0,
        "datasets_loaded": loaded,
        "cache": cache_stats,
    }


@router.get("/test")
def root():
    return {
        "message": "AuditIQ Cloud API is running 🚀",
        "service": APP_TITLE,
        "version": APP_VERSION,
    }
