"""Security dependencies for challenge write endpoints."""

from secrets import compare_digest
from typing import Optional

from fastapi import Header, HTTPException, status

from acps_ca_challenge.config import settings


def require_challenge_write_token(
    authorization: Optional[str] = Header(None),
) -> None:
    if not settings.CHALLENGE_WRITE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CHALLENGE_WRITE_TOKEN is not configured",
        )

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

    if not compare_digest(token.strip(), settings.CHALLENGE_WRITE_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token"
        )
