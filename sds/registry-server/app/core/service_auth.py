"""Service-token auth dependencies for internal Registry APIs."""

from secrets import compare_digest
from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.config import settings


def build_bearer_auth_header(token: str) -> dict[str, str]:
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def _require_token(expected_token: str, token_name: str, authorization: Optional[str]) -> None:
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{token_name} is not configured",
        )

    provided_token = _extract_bearer_token(authorization)
    if not compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token"
        )


def require_registry_service_token(
    authorization: Optional[str] = Header(None),
) -> None:
    _require_token(settings.REGISTRY_SERVICE_TOKEN, "REGISTRY_SERVICE_TOKEN", authorization)


def require_dsp_service_token(authorization: Optional[str] = Header(None)) -> None:
    _require_token(settings.DSP_SERVICE_TOKEN, "DSP_SERVICE_TOKEN", authorization)
