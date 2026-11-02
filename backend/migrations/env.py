from alembic import context
from app.core.config import get_settings
from app.database.base import Base
from app.models import entities  # noqa: F401
from sqlalchemy import create_engine, pool

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    database_url = get_settings().database_url
    if database_url is None:
        raise RuntimeError("DATABASE_URL is not configured")
    return database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)
    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
