import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_CHUNK_CHARS = 1_200
DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "data" / "rag_sources.json"
DEFAULT_OUTPUT = Path("/data/rag_corpus.json")
SKIP_TAGS = {"nav", "footer", "script", "style", "svg", "form", "iframe"}
BLOCK_TAGS = {"p", "li", "td", "th", "blockquote", "dd", "dt"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class MainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.main_depth = 0
        self.skip_stack: list[str] = []
        self.current_block: list[str] | None = None
        self.current_section = ""
        self.heading_block: list[str] | None = None
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "main":
            self.main_depth += 1
            return
        if self.main_depth == 0:
            return
        if tag in SKIP_TAGS:
            self.skip_stack.append(tag)
            return
        if self.skip_stack:
            return
        if tag in HEADING_TAGS:
            self._flush_block()
            self.heading_block = []
        elif tag in BLOCK_TAGS:
            self._flush_block()
            self.current_block = []

    def handle_endtag(self, tag: str) -> None:
        if self.skip_stack:
            if tag == self.skip_stack[-1]:
                self.skip_stack.pop()
            return
        if self.main_depth == 0:
            return
        if tag in HEADING_TAGS and self.heading_block is not None:
            heading = _normalize(" ".join(self.heading_block))
            if heading:
                self.current_section = heading[:250]
                self.blocks.append((self.current_section, heading))
            self.heading_block = None
        elif tag in BLOCK_TAGS:
            self._flush_block()
        elif tag == "main":
            self._flush_block()
            self.main_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.main_depth == 0 or self.skip_stack:
            return
        if self.heading_block is not None:
            self.heading_block.append(data)
        else:
            if self.current_block is None:
                self.current_block = []
            self.current_block.append(data)

    def _flush_block(self) -> None:
        if self.current_block is None:
            return
        text = _normalize(" ".join(self.current_block))
        if text:
            self.blocks.append((self.current_section, text))
        self.current_block = None


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _download(url: str) -> bytes:
    request = Request(
        url,
        headers={"User-Agent": "FinSightAI public-source indexer/0.1 (local development)"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            content = response.read(MAX_SOURCE_BYTES + 1)
    except URLError as error:
        raise RuntimeError(f"Unable to fetch public source {url}: {error}") from error
    if len(content) > MAX_SOURCE_BYTES:
        raise RuntimeError(f"Public source exceeds the {MAX_SOURCE_BYTES} byte ingestion limit: {url}")
    return content


def _chunks(source_id: str, blocks: list[tuple[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for section, text in blocks:
        words = text.split()
        current: list[str] = []
        current_length = 0
        for word in words:
            word_length = len(word) + (1 if current else 0)
            if current and current_length + word_length > MAX_CHUNK_CHARS:
                result.append(
                    {
                        "id": f"{source_id}:{len(result) + 1:04d}",
                        "section": section,
                        "text": " ".join(current),
                    }
                )
                current = []
                current_length = 0
                word_length = len(word)
            current.append(word)
            current_length += word_length
        if current:
            result.append(
                {
                    "id": f"{source_id}:{len(result) + 1:04d}",
                    "section": section,
                    "text": " ".join(current),
                }
            )
    return result


def ingest(manifest_path: Path, output_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("The public source manifest must contain at least one source")

    retrieved_at = datetime.now(UTC).isoformat()
    sources: list[dict[str, object]] = []
    chunks: list[dict[str, str]] = []
    for source in manifest:
        if not isinstance(source, dict) or not all(
            isinstance(source.get(key), str)
            for key in ("source_id", "title", "publisher", "url", "edition", "rights_basis")
        ):
            raise ValueError("Every source needs an id, title, publisher, URL, edition, and rights basis")
        content = _download(source["url"])
        parser = MainTextParser()
        parser.feed(content.decode("utf-8", errors="replace"))
        if not parser.blocks:
            raise RuntimeError(f"No main-page text was extracted from {source['url']}")

        source_chunks = _chunks(source["source_id"], parser.blocks)
        if not source_chunks:
            raise RuntimeError(f"No searchable text was extracted from {source['url']}")
        sources.append(
            {
                **source,
                "retrieved_at": retrieved_at,
                "content_sha256": hashlib.sha256(content).hexdigest(),
                "chunk_count": len(source_chunks),
            }
        )
        chunks.extend(source_chunks)

    corpus = {
        "version": 1,
        "retrieved_at": retrieved_at,
        "sources": sources,
        "chunks": chunks,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    temporary_path.replace(output_path)
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a local, cited text index from selected U.S. federal sources"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        count = ingest(args.manifest, args.output)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"RAG source ingestion failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Indexed {count} source chunks from {args.manifest} into {args.output}")


if __name__ == "__main__":
    main()
