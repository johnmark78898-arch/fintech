import json
import math
import os
import re
from pathlib import Path
from typing import Any

RAG_CORPUS_PATH = Path(os.environ.get("RAG_CORPUS_PATH", "/data/rag_corpus.json"))
_SEARCH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "can", "do", "for", "from",
    "how", "i", "in", "is", "it", "my", "of", "on", "or", "that", "the",
    "this", "to", "was", "what", "when", "where", "which", "who", "why",
    "with", "you", "your",
}


class PublicLibraryNotReady(RuntimeError):
    pass


class PublicLibraryCorrupt(RuntimeError):
    pass


def _load_corpus() -> dict[str, Any]:
    try:
        raw = RAG_CORPUS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PublicLibraryNotReady("The public source library has not been indexed") from error
    try:
        corpus = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PublicLibraryCorrupt("The public source library index is invalid") from error
    if (
        not isinstance(corpus, dict)
        or not isinstance(corpus.get("sources"), list)
        or not isinstance(corpus.get("chunks"), list)
    ):
        raise PublicLibraryCorrupt("The public source library index is invalid")
    required_source_fields = {
        "source_id",
        "title",
        "publisher",
        "url",
        "edition",
        "retrieved_at",
        "chunk_count",
        "rights_basis",
    }
    if any(
        not isinstance(source, dict)
        or not required_source_fields.issubset(source)
        or any(
            not isinstance(source.get(field), str)
            for field in ("source_id", "title", "publisher", "url", "edition", "retrieved_at")
        )
        or not isinstance(source.get("chunk_count"), int)
        for source in corpus["sources"]
    ):
        raise PublicLibraryCorrupt("The public source library contains invalid source metadata")
    if any(
        not isinstance(chunk, dict)
        or not isinstance(chunk.get("id"), str)
        or not isinstance(chunk.get("text"), str)
        for chunk in corpus["chunks"]
    ):
        raise PublicLibraryCorrupt("The public source library contains an invalid chunk")
    return corpus


def get_public_library_status() -> dict[str, object]:
    corpus = _load_corpus()
    return {
        "status": "ready",
        "source_count": len(corpus["sources"]),
        "chunk_count": len(corpus["chunks"]),
        "retrieved_at": corpus.get("retrieved_at"),
        "sources": [
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "publisher": source["publisher"],
                "url": source["url"],
                "edition": source["edition"],
                "retrieved_at": source["retrieved_at"],
                "chunk_count": source["chunk_count"],
                "rights_basis": source["rights_basis"],
            }
            for source in corpus["sources"]
        ],
    }


def search_public_library(query: str, *, limit: int = 8) -> list[dict[str, object]]:
    terms = [
        term
        for term in dict.fromkeys(re.findall(r"[\w'-]{2,}", query.casefold()))
        if term not in _SEARCH_STOPWORDS
    ]
    if not terms:
        raise ValueError("Enter at least one search term")
    phrases = [f"{left} {right}" for left, right in zip(terms, terms[1:])]

    corpus = _load_corpus()
    sources = {
        source["source_id"]: source
        for source in corpus["sources"]
        if isinstance(source, dict) and isinstance(source.get("source_id"), str)
    }
    chunks = corpus["chunks"]
    tokenized_chunks: list[tuple[dict[str, Any], str, dict[str, int]]] = []
    document_frequencies = dict.fromkeys(terms, 0)
    phrase_frequencies = dict.fromkeys(phrases, 0)
    for chunk in chunks:
        if not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str):
            raise PublicLibraryCorrupt("The public source library contains an invalid chunk")
        section = chunk.get("section", "")
        if chunk["text"].strip().casefold() == str(section).strip().casefold():
            continue
        searchable = f"{chunk.get('section', '')} {chunk['text']}".casefold()
        counts: dict[str, int] = {}
        for token in re.findall(r"[\w'-]{2,}", searchable):
            if token in document_frequencies:
                counts[token] = counts.get(token, 0) + 1
        for term in counts:
            document_frequencies[term] += 1
        for phrase in phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", searchable):
                phrase_frequencies[phrase] += 1
        tokenized_chunks.append((chunk, searchable, counts))

    matches: list[tuple[float, dict[str, object]]] = []
    for chunk, searchable, counts in tokenized_chunks:
        matched_terms = len(counts)
        minimum_matches = 1 if len(terms) == 1 else 2
        if matched_terms < minimum_matches:
            continue
        source = sources.get(str(chunk.get("id", "")).split(":", maxsplit=1)[0])
        if source is None:
            raise PublicLibraryCorrupt("The public source library contains an invalid source reference")
        text = chunk["text"]
        score = 0.0
        for term, frequency in counts.items():
            document_frequency = document_frequencies[term]
            inverse_frequency = math.log(
                1 + (len(chunks) - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            score += inverse_frequency * (frequency * 2.2) / (frequency + 1.2)
        score *= matched_terms / len(terms)
        for phrase in phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", searchable):
                phrase_frequency = phrase_frequencies[phrase]
                score += 2.5 * math.log(
                    1 + (len(chunks) - phrase_frequency + 0.5) / (phrase_frequency + 0.5)
                )
        first_match = min(
            (position for term in terms if (position := text.casefold().find(term)) >= 0),
            default=0,
        )
        start = max(0, first_match - 100)
        end = min(len(text), start + 360)
        excerpt = text[start:end]
        if start:
            excerpt = f"…{excerpt}"
        if end < len(text):
            excerpt = f"{excerpt}…"
        matches.append(
            (
                score,
                {
                    "chunk_id": chunk.get("id"),
                    "title": source["title"],
                    "publisher": source["publisher"],
                    "url": source["url"],
                    "edition": source["edition"],
                    "retrieved_at": source["retrieved_at"],
                    "section": chunk.get("section", ""),
                    "excerpt": excerpt,
                },
            )
        )
    matches.sort(key=lambda result: result[0], reverse=True)
    return [result for _, result in matches[:limit]]
