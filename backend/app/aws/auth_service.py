from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
import requests

from app.core.settings import (
    COGNITO_APP_CLIENT_ID,
    COGNITO_ISSUER,
    COGNITO_REGION,
    COGNITO_USER_POOL_ID,
    DEV_MODE,
)

logger = logging.getLogger("auditiq.aws.auth")

bearer_scheme = HTTPBearer(auto_error=False)

# In-memory JWKS cache
_JWKS_CACHE: dict[str, Any] = {}
_JWKS_EXPIRY: float = 0


def _get_cognito_jwks() -> dict[str, Any]:
    global _JWKS_CACHE, _JWKS_EXPIRY
    now = time.time()
    if _JWKS_CACHE and now < _JWKS_EXPIRY:
        return _JWKS_CACHE

    if not COGNITO_USER_POOL_ID or not COGNITO_REGION:
        return {}

    jwks_url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    try:
        resp = requests.get(jwks_url, timeout=5)
        if resp.status_code == 200:
            _JWKS_CACHE = resp.json()
            _JWKS_EXPIRY = now + 86400  # Cache for 24 hours
            return _JWKS_CACHE
    except Exception as e:
        logger.warning(f"Failed to fetch Cognito JWKS: {e}")

    return {}


def _decode_cognito_token(token: str) -> dict[str, Any]:
    jwks = _get_cognito_jwks()
    if not jwks:
        # Fallback decode without key check in development if keys not accessible
        if DEV_MODE:
            return jwt.decode(token, options={"verify_signature": False})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cognito JWKS key set unavailable.",
        )

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token key ID (kid).",
            )

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        payload = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=COGNITO_APP_CLIENT_ID if COGNITO_APP_CLIENT_ID else None,
            issuer=COGNITO_ISSUER if COGNITO_ISSUER else None,
            options={"verify_aud": bool(COGNITO_APP_CLIENT_ID)},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication token has expired.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid authentication token: {str(e)}")


class AuthenticatedUser:
    def __init__(self, user_id: str, username: str, role: str = "AUDITOR", email: str = "") -> None:
        self.user_id = user_id
        self.username = username
        self.role = role.upper()
        self.email = email

    @property
    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "email": self.email,
        }


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> AuthenticatedUser:
    # 1. Custom mock user header in test/dev environments
    mock_user_id = request.headers.get("X-User-Id")
    if mock_user_id and DEV_MODE:
        role = request.headers.get("X-User-Role", "AUDITOR")
        return AuthenticatedUser(
            user_id=mock_user_id,
            username=f"Mock-{mock_user_id}",
            role=role,
            email=f"{mock_user_id}@auditiq.cloud",
        )

    # 2. Token provided in Authorization header
    if credentials and credentials.credentials:
        token = credentials.credentials.strip()
        payload = _decode_cognito_token(token)
        user_id = payload.get("sub") or payload.get("username") or payload.get("cognito:username")
        username = payload.get("cognito:username") or payload.get("username") or user_id
        groups = payload.get("cognito:groups", [])
        role = "ADMIN" if "ADMIN" in [g.upper() for g in groups] else "AUDITOR"
        email = payload.get("email", "")
        return AuthenticatedUser(user_id=user_id, username=username, role=role, email=email)

    # 3. Development fallback if unauthenticated
    if DEV_MODE:
        return AuthenticatedUser(
            user_id="auditor_local_01",
            username="Local Auditor",
            role="AUDITOR",
            email="auditor@auditiq.cloud",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please log in through Amazon Cognito.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_dataset_ownership(dataset_meta: dict[str, Any] | None, user: AuthenticatedUser) -> None:
    if not dataset_meta:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    owner_id = dataset_meta.get("user_id")
    if owner_id and owner_id != user.user_id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this dataset.",
        )
