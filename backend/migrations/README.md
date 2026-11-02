# Database Migrations

Migrations are managed with Alembic and use `DATABASE_URL` from the application settings.

```powershell
alembic upgrade head
alembic revision --autogenerate -m "describe schema change"
```

Review generated migrations before applying them. Back up production data and use a controlled release process for upgrades. Downgrades are not assumed safe for customer data.
