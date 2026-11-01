from collections.abc import Generator
from pathlib import Path
from uuid import UUID

import pytest
from app.core.auth import get_current_user
from app.database.base import Base
from app.database.session import get_session
from app.main import app
from app.models.entities import (
    FinancialTransaction,
    Organization,
    OrganizationMembership,
    User,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def authorized_client() -> Generator[tuple[TestClient, UUID, Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    organization = Organization(name="Retail demo")
    user = User(
        email="owner@example.test",
        display_name="Owner",
        auth_subject="test|owner",
    )
    session.add_all([organization, user])
    session.flush()
    session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role_key="owner",
            status="active",
        )
    )
    organization_id = organization.id
    session.commit()

    def override_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            yield client, organization_id, session
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_csv_upload_imports_bundled_real_data(
    authorized_client: tuple[TestClient, UUID, Session],
) -> None:
    client, organization_id, session = authorized_client
    project_root = Path(__file__).resolve().parents[2]
    sample = (project_root / "data" / "demo" / "uci_online_retail_sample.csv").read_bytes()

    response = client.post(
        f"/api/v1/organizations/{organization_id}/imports/csv",
        files={"file": ("uci_online_retail_sample.csv", sample, "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["inserted_rows"] == 8_000
    assert response.json()["rejected_rows"] == 0
    assert session.scalar(select(func.count()).select_from(FinancialTransaction)) == 8_000


def test_csv_upload_requires_bearer_authentication() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/organizations/00000000-0000-0000-0000-000000000001/imports/csv",
            files={"file": ("transactions.csv", b"not read", "text/csv")},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
