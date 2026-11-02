import io
import json

import pytest
from app.api.routes import recommendations as recommendations_routes
from app.financial_data import grounded_answers
from app.financial_data.recommendations import generate_ollama_recommendations
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

DATASET = {
    "source_kind": "local",
    "source_name": "transactions.csv",
    "transaction_count": 4,
    "undated_count": 0,
    "currencies": [
        {"currency": "USD", "inflow": 250, "outflow": 100, "transactions": 4}
    ],
    "monthly": [
        {"month": "2026-01", "currency": "USD", "inflow": 150, "outflow": 30},
        {"month": "2026-02", "currency": "USD", "inflow": 100, "outflow": 70},
    ],
    "categories": [
        {"category": "Supplies", "currency": "USD", "inflow": 0, "outflow": 100, "transactions": 2}
    ],
}


def test_generate_recommendations_uses_only_aggregate_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data)
        content = json.dumps(
            {
                "recommendations": [
                    {
                        "evidence_id": "item:USD:1",
                        "priority": "medium",
                    }
                ],
                "abstained": False,
            }
        )
        return FakeResponse(json.dumps({"message": {"content": content}}).encode("utf-8"))

    monkeypatch.setattr(grounded_answers, "urlopen", fake_urlopen)

    recommendations, abstained, used_fallback = generate_ollama_recommendations(
        DATASET,
        items=[{
            "item": "Tea",
            "currency": "USD",
            "transactions": 2,
            "inflow": 120,
            "outflow": 0,
            "quantity": 5,
        }],
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
    )

    assert recommendations[0]["title"] == "Check Tea records"
    assert recommendations[0]["observation"] == (
        "Item label 'Tea' in USD: 2 transactions, inflows 120.00 USD, "
        "outflows 0.00 USD, recorded quantity 5.00."
    )
    assert recommendations[0]["item"] == "Tea"
    assert used_fallback is False
    assert recommendations[0]["why_it_matters"] == (
        "Checking Tea against its source documents can help catch missing or mistyped entries "
        "before you rely on these figures."
    )
    assert "Compare the recorded quantity and totals for Tea" in recommendations[0]["action"]
    assert abstained is False
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["timeout"] == 60
    request_body = captured["body"]
    assert isinstance(request_body, dict)
    prompt = json.loads(request_body["messages"][1]["content"])
    assert "transaction_analysis" not in prompt
    assert "source_name" not in json.dumps(prompt)
    assert any(item["evidence_id"] == "item:USD:1" for item in prompt["aggregate_evidence"])
    assert "Tea" in json.dumps(prompt)
    assert "application writes the explanations" in request_body["messages"][0]["content"]
    format_schema = request_body["format"]
    assert isinstance(format_schema, dict)
    evidence_id_schema = format_schema["properties"]["recommendations"]["items"]["properties"]["evidence_id"]
    assert evidence_id_schema["enum"] == ["currency:USD", "category:USD:1", "month:USD:2026-01", "month:USD:2026-02", "item:USD:1"]


def test_generate_recommendations_falls_back_on_invalid_model_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(_request, timeout):
        content = json.dumps(
            {
                "recommendations": [
                    {
                        "evidence_id": "unknown:USD",
                        "priority": "urgent",
                    }
                ],
                "abstained": False,
            }
        )
        return FakeResponse(json.dumps({"message": {"content": content}}).encode("utf-8"))

    monkeypatch.setattr(grounded_answers, "urlopen", fake_urlopen)

    recommendations, abstained, used_fallback = generate_ollama_recommendations(
        DATASET,
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
    )

    assert recommendations
    assert recommendations[0]["observation"]
    assert abstained is False
    assert used_fallback is True


def test_generate_recommendations_adds_item_check_when_model_omits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(_request, timeout):
        content = json.dumps(
            {
                "recommendations": [
                    {
                        "evidence_id": "category:USD:1",
                        "priority": "medium",
                    }
                ],
                "abstained": False,
            }
        )
        return FakeResponse(json.dumps({"message": {"content": content}}).encode("utf-8"))

    monkeypatch.setattr(grounded_answers, "urlopen", fake_urlopen)

    recommendations, abstained, used_fallback = generate_ollama_recommendations(
        DATASET,
        items=[{
            "item": "Tea",
            "currency": "USD",
            "transactions": 2,
            "inflow": 120,
            "outflow": 0,
            "quantity": 5,
        }],
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
    )

    assert len(recommendations) == 2
    assert recommendations[0]["title"] == "Review Supplies spending"
    assert recommendations[1]["title"] == "Check Tea records"
    assert recommendations[1]["item"] == "Tea"
    assert abstained is False
    assert used_fallback is False


def test_slow_selling_item_gets_cautious_discount_test(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        content = json.dumps({
            "recommendations": [
                {"evidence_id": "item:USD:1", "priority": "medium"},
                {"evidence_id": "slow_seller:USD:1", "priority": "high"},
                {"evidence_id": "currency:USD", "priority": "medium"},
            ],
            "abstained": False,
        })
        return FakeResponse(json.dumps({"message": {"content": content}}).encode("utf-8"))

    monkeypatch.setattr(grounded_answers, "urlopen", fake_urlopen)
    recommendations, abstained, used_fallback = generate_ollama_recommendations(
        DATASET,
        items=[{
            "item": "Tea",
            "currency": "USD",
            "transactions": 2,
            "inflow": 30,
            "outflow": 0,
            "quantity": 2,
            "sales_count": 1,
            "units_sold": 2,
            "return_count": 0,
            "peer_product_count": 5,
            "peer_median_units_sold": 4,
        }],
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
    )

    promotion = next(item for item in recommendations if item["item"] == "Tea")
    assert len([item for item in recommendations if item["item"] == "Tea"]) == 1
    assert promotion["title"] == "Consider a small promotion for Tea"
    assert "1 recorded sale entries" in promotion["observation"]
    assert "median across 5 products is 4.00 units sold" in promotion["observation"]
    assert "discounts may reduce your margin" in promotion["why_it_matters"]
    assert "small time-limited discount or bundle" in promotion["action"]
    assert "margin" in promotion["action"]
    request_body = captured["body"]
    assert isinstance(request_body, dict)
    prompt = json.loads(request_body["messages"][1]["content"])
    assert any(evidence["evidence_id"] == "slow_seller:USD:1" for evidence in prompt["aggregate_evidence"])
    assert abstained is False
    assert used_fallback is False


def test_item_without_sales_comparison_does_not_get_discount_suggestion() -> None:
    from app.financial_data.recommendations import _recommendation_evidence

    evidence = _recommendation_evidence(
        DATASET,
        [{
            "item": "Tea",
            "currency": "USD",
            "transactions": 2,
            "inflow": 30,
            "outflow": 0,
            "quantity": 2,
            "sales_count": 1,
            "units_sold": 2,
            "return_count": 0,
            "peer_product_count": 4,
            "peer_median_units_sold": 4,
        }],
    )

    assert not any(item["kind"] == "slow_seller" for item in evidence)


def test_slow_seller_requires_complete_quantity_and_five_peer_products() -> None:
    from app.financial_data.recommendations import _recommendation_evidence

    evidence = _recommendation_evidence(
        DATASET,
        [{
            "item": "Tea",
            "currency": "USD",
            "transactions": 2,
            "inflow": 30,
            "outflow": 0,
            "quantity": 2,
            "sales_count": 1,
            "units_sold": 2,
            "return_count": 0,
            "peer_product_count": 4,
            "peer_median_units_sold": 4,
        }],
    )

    assert not any(item["kind"] == "slow_seller" for item in evidence)

    incomplete_quantity = _recommendation_evidence(
        DATASET,
        [{
            "item": "Tea",
            "currency": "USD",
            "transactions": 2,
            "inflow": 30,
            "outflow": 0,
            "quantity": None,
            "sales_count": 1,
            "units_sold": 2,
            "return_count": 0,
            "peer_product_count": 5,
            "peer_median_units_sold": 4,
        }],
    )

    assert not any(item["kind"] == "slow_seller" for item in incomplete_quantity)


def test_recommendations_endpoint_returns_local_model_suggestions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def generate(dataset_context, **kwargs):
        captured["dataset"] = dataset_context
        captured["items"] = kwargs["items"]
        captured["model"] = kwargs["model"]
        return (
            [
                {
                    "title": "Review supplies outflows",
                    "observation": "Category label 'Supplies' has 100.00 USD outflows across 2 transactions.",
                    "why_it_matters": "Checking these entries against receipts may help confirm the purchases were recorded as expected.",
                    "action": "Check the receipts and confirm these outflows are recorded in the right category.",
                    "priority": "medium",
                    "item": None,
                }
            ],
            False,
            True,
        )

    monkeypatch.setattr(recommendations_routes, "generate_ollama_recommendations", generate)

    item_summary = {
        "item": "Tea",
        "currency": "USD",
        "transactions": 2,
        "inflow": 120,
        "outflow": 0,
        "quantity": 5,
    }
    response = client.post("/api/v1/recommendations", json={"dataset": DATASET, "items": [item_summary]})

    assert response.status_code == 200
    assert response.json()["recommendations"][0]["priority"] == "medium"
    assert response.json()["notice"]
    assert response.json()["model"] == captured["model"]
    assert captured["dataset"]["transaction_count"] == 4
    assert captured["items"] == [item_summary]


def test_recommendations_endpoint_rejects_invalid_dataset_context() -> None:
    response = client.post("/api/v1/recommendations", json={"dataset": {"transaction_count": -1}})

    assert response.status_code == 422
