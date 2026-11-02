import csv
import io

import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_liveness_does_not_depend_on_database() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_demo_sample_is_available_without_database() -> None:
    response = client.get("/api/v1/demo/uci-online-retail-sample.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "uci_online_retail_sample.csv" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "occurred_at",
        "account_name",
        "amount",
        "currency",
        "direction",
        "description",
        "category",
        "external_ref",
        "invoice_id",
        "product_code",
        "quantity",
        "unit_price",
        "country",
        "line_total",
        "is_return",
        "invoice_month",
        "invoice_weekday",
        "invoice_hour",
    ]
    assert len(rows) == 8_001


def test_readiness_fails_when_database_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_database() -> None:
        raise RuntimeError("DATABASE_URL is not configured")

    monkeypatch.setattr("app.main.get_engine", missing_database)
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
