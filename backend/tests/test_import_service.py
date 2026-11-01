from collections.abc import Generator
from uuid import UUID

import pytest
from app.database.base import Base
from app.financial_data.import_service import import_transactions_csv
from app.models.entities import (
    FinancialTransaction,
    ImportBatch,
    Organization,
    OrganizationMembership,
    User,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session


@pytest.fixture
def authorized_session() -> Generator[tuple[Session, UUID, UUID], None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)

    organization = Organization(name="Demo organization")
    user = User(email="analyst@example.test", display_name="Analyst")
    session.add_all([organization, user])
    session.flush()
    session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role_key="analyst",
            status="active",
        )
    )
    organization_id = organization.id
    user_id = user.id
    session.commit()

    yield session, organization_id, user_id

    session.close()
    engine.dispose()


def test_import_persists_tenant_scoped_transactions(
    authorized_session: tuple[Session, UUID, UUID],
) -> None:
    session, organization_id, user_id = authorized_session
    content = (
        b"occurred_at,account_name,amount,currency,direction,description\n"
        b"2026-10-31T12:30:00Z,Operating,125.50,USD,inflow,Customer receipt\n"
    )

    with session.begin():
        summary = import_transactions_csv(
            session,
            organization_id=organization_id,
            user_id=user_id,
            filename=r"C:\uploads\transactions.csv",
            content=content,
        )

    transaction = session.scalar(select(FinancialTransaction))
    batch = session.scalar(select(ImportBatch))
    assert summary.status == "completed"
    assert summary.inserted_rows == 1
    assert summary.rejected_rows == 0
    assert transaction is not None
    assert transaction.organization_id == organization_id
    assert transaction.account_id is not None
    assert batch is not None and batch.filename == "transactions.csv"


def test_repeat_import_is_idempotent_for_transaction_rows(
    authorized_session: tuple[Session, UUID, UUID],
) -> None:
    session, organization_id, user_id = authorized_session
    content = (
        b"occurred_at,account_name,amount,currency,direction\n"
        b"2026-10-31T12:30:00Z,Operating,125.50,USD,inflow\n"
    )

    with session.begin():
        first = import_transactions_csv(
            session,
            organization_id=organization_id,
            user_id=user_id,
            filename="transactions.csv",
            content=content,
        )
    with session.begin():
        second = import_transactions_csv(
            session,
            organization_id=organization_id,
            user_id=user_id,
            filename="transactions.csv",
            content=content,
        )

    transaction_count = session.scalar(
        select(func.count()).select_from(FinancialTransaction)
    )
    assert first.inserted_rows == 1
    assert second.inserted_rows == 0
    assert second.duplicate_rows == 1
    assert transaction_count == 1


def test_viewer_cannot_import_financial_data(
    authorized_session: tuple[Session, UUID, UUID],
) -> None:
    session, organization_id, user_id = authorized_session
    membership = session.scalar(select(OrganizationMembership))
    assert membership is not None
    membership.role_key = "viewer"
    session.commit()

    with pytest.raises(PermissionError), session.begin():
        import_transactions_csv(
            session,
            organization_id=organization_id,
            user_id=user_id,
            filename="transactions.csv",
            content=b"not parsed because role is read-only",
        )

    assert session.scalar(select(func.count()).select_from(ImportBatch)) == 0
