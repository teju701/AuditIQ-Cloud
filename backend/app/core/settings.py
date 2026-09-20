from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load from both backend/.env and root .env if present
_root_env = Path(__file__).resolve().parents[3] / ".env"
_backend_env = Path(__file__).resolve().parents[2] / ".env"
if _backend_env.exists():
    load_dotenv(_backend_env)
if _root_env.exists():
    load_dotenv(_root_env)
load_dotenv()


APP_TITLE = "AuditIQ Cloud API"
APP_SUBTITLE = "Evidence-backed AI financial audit investigation on AWS"
APP_VERSION = "2.0.0"


def read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    token = raw.strip().lower()
    if token in {"1", "true", "yes", "y", "on"}:
        return True
    if token in {"0", "false", "no", "n", "off"}:
        return False
    return default


def read_int_env(name: str, default: int, min_value: int, max_value: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        value = int(raw)
    except ValueError:
        return default

    return max(min_value, min(value, max_value))


def read_csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values if values else default


# AWS Core Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "")
DYNAMODB_DATASETS_TABLE = os.getenv("DYNAMODB_DATASETS_TABLE", "AuditIQDatasets")
DYNAMODB_AUDIT_RUNS_TABLE = os.getenv("DYNAMODB_AUDIT_RUNS_TABLE", "AuditIQAuditRuns")

# Amazon Cognito Configuration
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
COGNITO_APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID", "")
COGNITO_REGION = os.getenv("COGNITO_REGION", AWS_REGION)
COGNITO_ISSUER = os.getenv(
    "COGNITO_ISSUER",
    f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
    if COGNITO_USER_POOL_ID
    else "",
)

# Amazon Bedrock Configuration
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

# Cache & Consensus Configuration
CACHE_ENABLED = read_bool_env("AUDITIQ_CACHE_ENABLED", True)
CACHE_TTL_SECONDS = read_int_env("AUDITIQ_CACHE_TTL_SECONDS", 900, 0, 86400)
CACHE_MAX_SIZE = read_int_env("AUDITIQ_CACHE_MAX_SIZE", 500, 1, 5000)
CACHEABLE_EXECUTION_MODES = {"safe_plan", "locked_metric"}
ENABLE_DUAL_RUN_CONSENSUS = read_bool_env("AUDITIQ_ENABLE_DUAL_RUN_CONSENSUS", False)

# Prompt Budget Controls
PROMPT_MAX_COLUMNS = read_int_env("AUDITIQ_PROMPT_MAX_COLUMNS", 24, 5, 100)
PROMPT_MAX_SAMPLE_VALUES = read_int_env("AUDITIQ_PROMPT_MAX_SAMPLE_VALUES", 3, 1, 10)
PROMPT_MAX_TOP_VALUES = read_int_env("AUDITIQ_PROMPT_MAX_TOP_VALUES", 5, 2, 20)

# Networking & Local Dev
CORS_ORIGINS = read_csv_env("AUDITIQ_CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"])
DEV_MODE = read_bool_env("AUDITIQ_DEV_MODE", True)

DEFAULT_QUERY_PAGE_SIZE = 50
MAX_QUERY_PAGE_SIZE = 200
