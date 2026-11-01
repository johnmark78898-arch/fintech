from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from app.core.auth import get_current_user
from app.core.config import Settings
from app.database.base import Base
from app.models.entities import User
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class FakeJwksClient:
    def __init__(self, public_key: Any) -> None:
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        return SimpleNamespace(key=self.public_key)


@pytest.fixture
def auth_context(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[Session, Settings, Any], None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    user = User(
        email="provisioned@example.test",
        display_name="Provisioned User",
        auth_subject="issuer|user-123",
    )
    session.add(user)
    session.commit()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        "app.core.auth._get_jwks_client",
        lambda _url: FakeJwksClient(private_key.public_key()),
    )
    settings = Settings(
        auth_issuer="https://issuer.example.test/",
        auth_audience="finsight-api",
        auth_jwks_url="https://issuer.example.test/.well-known/jwks.json",
    )
    try:
        yield session, settings, private_key
    finally:
        session.close()
        engine.dispose()


def _token(private_key: Any, *, audience: str = "finsight-api") -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "https://issuer.example.test/",
        "aud": audience,
        "sub": "issuer|user-123",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def test_verifies_oidc_token_and_maps_provisioned_subject(auth_context) -> None:
    session, settings, private_key = auth_context

    user = get_current_user(_token(private_key), session, settings)

    assert user.auth_subject == "issuer|user-123"


def test_rejects_token_with_wrong_audience(auth_context) -> None:
    session, settings, private_key = auth_context

    with pytest.raises(HTTPException) as error:
        get_current_user(_token(private_key, audience="another-api"), session, settings)

    assert error.value.status_code == 401
