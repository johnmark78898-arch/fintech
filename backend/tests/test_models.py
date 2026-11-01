from app.database.base import Base
from app.models import entities  # noqa: F401
from sqlalchemy import create_engine, inspect


def test_financial_schema_creates_with_tenant_scoped_account_foreign_key() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {"organizations", "financial_accounts", "transactions"}.issubset(tables)

    transaction_foreign_keys = inspector.get_foreign_keys("transactions")
    assert any(
        foreign_key["constrained_columns"] == ["organization_id", "account_id"]
        and foreign_key["referred_table"] == "financial_accounts"
        and foreign_key["referred_columns"] == ["organization_id", "id"]
        for foreign_key in transaction_foreign_keys
    )
