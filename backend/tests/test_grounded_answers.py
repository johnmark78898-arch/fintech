import io
import json

from app.financial_data import grounded_answers


def test_generate_ollama_answer_uses_retrieved_passages_and_parses_citations(
    monkeypatch,
) -> None:
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
        return FakeResponse(
            json.dumps(
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "answer": "Track cash inflows and outflows.",
                                "citation_ids": ["sba:0001"],
                                "abstained": False,
                            }
                        )
                    }
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr(grounded_answers, "urlopen", fake_urlopen)
    passages = [
        {
            "chunk_id": "sba:0001",
            "title": "Manage your finances",
            "section": "Cash flow",
            "excerpt": "Bookkeeping helps a business understand cash flow.",
        }
    ]

    result = grounded_answers.generate_ollama_answer(
        "How do I track cash flow?",
        passages,
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
    )

    assert result == ("Track cash inflows and outflows.", ["sba:0001"], False)
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["timeout"] == 60
    request_body = captured["body"]
    assert isinstance(request_body, dict)
    prompt = json.loads(request_body["messages"][1]["content"])
    assert prompt["question"] == "How do I track cash flow?"
    assert prompt["evidence"][0]["citation_id"] == "sba:0001"
    assert prompt["transaction_summary"] is None


def test_generate_ollama_answer_includes_aggregate_dataset_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        return FakeResponse(
            json.dumps(
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "answer": "Outflows exceeded inflows.",
                                "citation_ids": [],
                                "abstained": False,
                            }
                        )
                    }
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr(grounded_answers, "urlopen", fake_urlopen)
    context = {"transaction_count": 4, "currencies": [{"currency": "GBP"}]}

    result = grounded_answers.generate_ollama_answer(
        "How did this dataset perform?",
        [],
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
        dataset_context=context,
    )

    assert result == ("Outflows exceeded inflows.", [], False)
    request_body = captured["body"]
    assert isinstance(request_body, dict)
    prompt = json.loads(request_body["messages"][1]["content"])
    assert prompt["transaction_summary"] == context


def test_generate_ollama_answer_rejects_remote_endpoints() -> None:
    try:
        grounded_answers.generate_ollama_answer(
            "Question?",
            [],
            base_url="https://example.com",
            model="llama3.2",
        )
    except ValueError as error:
        assert str(error) == "Ollama must be configured with a local HTTP endpoint"
    else:
        raise AssertionError("Remote model URLs must be rejected")
