from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import urlparse

import jwt
from app.core.config import Settings, get_settings
from app.database.session import get_session
from app.models.entities import User
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError
from sqlalchemy import select
from sqlalchemy.orm import Session

bearer_scheme = HTTPBearer(auto_error=False)


def require_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@lru_cache(maxsize=4)
def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, timeout=5, cache_jwk_set=True)


def get_current_user(
    token: Annotated[str, Depends(require_bearer_token)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if not settings.auth_issuer or not settings.auth_audience or not settings.auth_jwks_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider is not configured",
        )

    jwks_url = urlparse(settings.auth_jwks_url)
    if jwks_url.scheme != "https" and jwks_url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider configuration is invalid",
        )

    try:
        signing_key = _get_jwks_client(settings.auth_jwks_url).get_signing_key_from_jwt(token)
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth_audience,
            issuer=settings.auth_issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except PyJWKClientConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider is unavailable",
        ) from None
    except (InvalidTokenError, PyJWKClientError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = session.scalar(
        select(User).where(User.auth_subject == subject, User.status == "active")
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not provisioned",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
