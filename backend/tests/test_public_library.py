import json

import pytest
from app.api.routes import public_library as public_library_routes
from app.financial_data import public_library
from app.financial_data.grounded_answers import OllamaUnavailable
from app.main import app
from fastapi.testclient import TestClient
from scripts.ingest_public_rag import MainTextParser, _chunks

client = TestClient(app)


def _write_test_corpus(path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "retrieved_at": "2026-11-01T00:00:00+00:00",
                "sources": [
                    {
                        "source_id": "sba",
                        "title": "Manage your finances",
                        "publisher": "U.S. Small Business Administration",
                        "url": "https://www.sba.gov/counseling/manage-your-business/",
                        "edition": "current",
                        "rights_basis": "Qualifying federal text",
                        "retrieved_at": "2026-11-01T00:00:00+00:00",
                        "chunk_count": 1,
                    }
                ],
                "chunks": [
                    {
                        "id": "sba:0001",
                        "section": "Cash flow",
                        "text": "Bookkeeping helps a business understand cash flow and manage finances.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_public_library_reports_not_ready_when_index_is_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(public_library, "RAG_CORPUS_PATH", tmp_path / "missing.json")

    response = client.get("/api/v1/public-library/status")

    assert response.status_code == 503
    assert response.json() == {"detail": "The public source library has not been indexed"}


def test_public_library_search_returns_source_citations(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = tmp_path / "corpus.json"
    _write_test_corpus(corpus_path)
    monkeypatch.setattr(public_library, "RAG_CORPUS_PATH", corpus_path)

    response = client.get("/api/v1/public-library/search", params={"query": "cash flow"})

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["title"] == "Manage your finances"
    assert result["section"] == "Cash flow"
    assert result["url"].startswith("https://www.sba.gov/")
    assert "cash flow" in result["excerpt"].lower()


def test_public_library_ranks_topical_terms_above_generic_matches(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = tmp_path / "corpus.json"
    _write_test_corpus(corpus_path)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus["chunks"] = [
        {
            "id": "sba:0001",
            "section": "Business management",
            "text": "Small business owners manage a small business by planning operations.",
        },
        {
            "id": "sba:0002",
            "section": "Cash flow",
            "text": "Cash flow planning helps a business understand incoming and outgoing funds.",
        },
    ]
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    monkeypatch.setattr(public_library, "RAG_CORPUS_PATH", corpus_path)

    results = public_library.search_public_library("How can a small business manage cash flow?")

    assert results[0]["chunk_id"] == "sba:0002"


def test_public_library_omits_heading_only_chunks(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = tmp_path / "corpus.json"
    _write_test_corpus(corpus_path)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus["chunks"].append(
        {
            "id": "sba:0002",
            "section": "Manage your business",
            "text": "Manage your business",
        }
    )
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    monkeypatch.setattr(public_library, "RAG_CORPUS_PATH", corpus_path)

    results = public_library.search_public_library("manage business cash flow")

    assert all(result["chunk_id"] != "sba:0002" for result in results)


def test_public_library_rejects_empty_search_terms(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = tmp_path / "corpus.json"
    _write_test_corpus(corpus_path)
    monkeypatch.setattr(public_library, "RAG_CORPUS_PATH", corpus_path)

    response = client.get("/api/v1/public-library/search", params={"query": "!!!"})

    assert response.status_code == 422
    assert response.json() == {"detail": "Enter at least one search term"}


def test_public_answer_cites_only_retrieved_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    retrieval_limits = []
    passage = {
        "chunk_id": "sba:0001",
        "title": "Manage your finances",
        "publisher": "U.S. Small Business Administration",
        "url": "https://www.sba.gov/counseling/manage-your-business/",
        "edition": "current",
        "retrieved_at": "2026-11-01T00:00:00+00:00",
        "section": "Cash flow",
        "excerpt": "Bookkeeping helps a business understand cash flow.",
    }
    def retrieve(_query, **kwargs):
        retrieval_limits.append(kwargs["limit"])
        return [passage]

    monkeypatch.setattr(public_library_routes, "search_public_library", retrieve)
    monkeypatch.setattr(
        public_library_routes,
        "generate_ollama_answer",
        lambda *_args, **_kwargs: ("Track business cash flow with bookkeeping.", ["sba:0001"], False),
    )

    response = client.post(
        "/api/v1/public-library/answer",
        json={"question": "How can a business track cash flow?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Track business cash flow with bookkeeping."
    assert response.json()["citations"] == [passage]
    assert response.json()["abstained"] is False
    assert retrieval_limits == [2]


def test_public_answer_abstains_when_retrieval_finds_no_passages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(public_library_routes, "search_public_library", lambda _query, **_kwargs: [])
    monkeypatch.setattr(
        public_library_routes,
        "generate_ollama_answer",
        lambda *_args, **_kwargs: pytest.fail("Ollama should not be called without evidence"),
    )

    response = client.post(
        "/api/v1/public-library/answer",
        json={"question": "What is my private account balance?"},
    )

    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["citations"] == []


def test_public_answer_uses_aggregate_dataset_when_no_public_passages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        public_library_routes,
        "search_public_library",
        lambda *_args, **_kwargs: pytest.fail("Dataset analysis must not retrieve public passages"),
    )

    def generate(_question, passages, **kwargs):
        captured["passages"] = passages
        captured["dataset"] = kwargs["dataset_context"]
        return "Outflows exceeded inflows in the selected period.", ["hallucinated:0001"], False

    monkeypatch.setattr(public_library_routes, "generate_ollama_answer", generate)
    dataset = {
        "source_kind": "local",
        "source_name": "transactions.csv",
        "transaction_count": 4,
        "undated_count": 0,
        "currencies": [
            {"currency": "GBP", "inflow": 500, "outflow": 700, "transactions": 4}
        ],
        "monthly": [],
        "categories": [],
    }

    response = client.post(
        "/api/v1/public-library/answer",
        json={"question": "Did outflows exceed inflows?", "dataset": dataset},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Outflows exceeded inflows in the selected period."
    assert response.json()["data_based"] is True
    assert response.json()["abstained"] is False
    assert response.json()["citations"] == []
    assert captured["passages"] == []
    assert captured["dataset"]["source_name"] == "transactions.csv"


def test_public_answer_rejects_model_citations_outside_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        public_library_routes,
        "search_public_library",
        lambda _query, **_kwargs: [{"chunk_id": "sba:0001"}],
    )
    monkeypatch.setattr(
        public_library_routes,
        "generate_ollama_answer",
        lambda *_args, **_kwargs: ("Unsupported claim.", ["irs:9999"], False),
    )

    response = client.post(
        "/api/v1/public-library/answer",
        json={"question": "What does this guidance say?"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "The local model returned an invalid citation. Try again."}


def test_public_answer_reports_when_local_ollama_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        public_library_routes,
        "search_public_library",
        lambda _query, **_kwargs: [{"chunk_id": "sba:0001"}],
    )
    monkeypatch.setattr(
        public_library_routes,
        "generate_ollama_answer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OllamaUnavailable("offline")),
    )

    response = client.post(
        "/api/v1/public-library/answer",
        json={"question": "What does this guidance say?"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Local Ollama is unavailable. Start Ollama and install the configured model."
    }


def test_source_parser_keeps_main_text_and_omits_navigation_and_links() -> None:
    parser = MainTextParser()
    parser.feed(
        "<nav>Navigation</nav><main><h1>Business finances</h1>"
        "<p>Bookkeeping supports cash flow. <a href='https://third-party.example'>"
        "Related guidance</a></p></main>"
    )

    chunks = _chunks("sba", parser.blocks)
    extracted = " ".join(chunk["text"] for chunk in chunks)

    assert "Business finances" in extracted
    assert "cash flow" in extracted
    assert "Related guidance" in extracted
    assert "Navigation" not in extracted
