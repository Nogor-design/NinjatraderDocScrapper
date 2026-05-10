from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class RetrievalDocument:
    """A local context document available to the Strategy Factory."""

    id: str
    kind: str
    path: str
    title: str
    text: str
    tags: tuple[str, ...] = ()
    score: float = 0.0


def build_spec_query(spec: dict) -> str:
    """Flatten a canonical strategy spec into retrieval-friendly search text."""
    parts: list[str] = []
    strategy = spec.get("strategy") or {}
    parts.extend(str(strategy.get(key, "")) for key in ("id", "name", "hypothesis", "source_prompt"))
    parts.append(str(spec.get("direction", "")))

    for entry in spec.get("entries") or []:
        parts.append(str(entry.get("id", "")))
        parts.append(str(entry.get("type", "")))
        parts.extend(str(value) for value in (entry.get("params") or {}).values())

    for item in spec.get("filters") or []:
        parts.append(str(item.get("type", "")))
        parts.extend(str(value) for value in (item.get("params") or {}).values())

    exits = spec.get("exits") or {}
    for key in ("stop", "target", "partial", "runner"):
        value = exits.get(key) or {}
        if isinstance(value, dict):
            parts.append(str(value.get("type", key)))
            parts.extend(str(item) for item in value.values())

    risk = spec.get("risk") or {}
    parts.extend(key for key, value in risk.items() if value)
    execution = spec.get("execution") or {}
    parts.append(json.dumps(execution, sort_keys=True))
    return " ".join(part for part in parts if part).strip()


def discover_local_documents(root: str | Path = REPO_ROOT, *, include_docs_pages: bool = False) -> list[RetrievalDocument]:
    """Discover skeletons, module cards, examples, and labeled artifacts in priority order."""
    base = Path(root)
    documents: list[RetrievalDocument] = []
    documents.extend(_read_glob(base, "strategy_factory/modules/**/*.md", "module_card"))
    documents.extend(_read_glob(base, "strategy_factory/skeletons/*", "skeleton"))
    documents.extend(_read_glob(base, "strategy_factory/specs/examples/*.json", "spec_example"))
    documents.extend(_read_glob(base, "iteration_artifacts/good/**/code.cs", "known_good_code"))
    documents.extend(_read_glob(base, "iteration_artifacts/good/**/metadata.json", "known_good_metadata"))
    documents.extend(_read_glob(base, "iteration_artifacts/bad/**/code.cs", "known_bad_code"))
    documents.extend(_read_glob(base, "iteration_artifacts/bad/**/compiler_errors.txt", "known_bad_error"))
    if include_docs_pages:
        documents.extend(_read_glob(base, "ninjatrader_docs/pages/*.md", "docs_page"))
    return documents


def retrieve_local_context(
    query: str,
    *,
    root: str | Path = REPO_ROOT,
    top_k: int = 8,
    include_docs_pages: bool = False,
) -> list[RetrievalDocument]:
    """Rank local Strategy Factory context without needing an embedding server."""
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    documents = discover_local_documents(root, include_docs_pages=include_docs_pages)
    if not documents:
        return []

    doc_tokens = [_tokens(" ".join((doc.title, " ".join(doc.tags), doc.text))) for doc in documents]
    document_frequency: Counter[str] = Counter()
    for tokens in doc_tokens:
        document_frequency.update(set(tokens))

    ranked: list[RetrievalDocument] = []
    for doc, tokens in zip(documents, doc_tokens):
        score = _bm25_like_score(query_tokens, tokens, document_frequency, len(documents))
        if score <= 0:
            continue
        ranked.append(replace(doc, score=score + _kind_boost(doc.kind)))

    ranked.sort(key=lambda item: (item.score, -_kind_rank(item.kind), item.title), reverse=True)
    return ranked[:top_k]


def retrieve_context_for_spec(
    spec: dict,
    *,
    root: str | Path = REPO_ROOT,
    top_k: int = 8,
    include_docs_pages: bool = False,
) -> list[RetrievalDocument]:
    return retrieve_local_context(
        build_spec_query(spec),
        root=root,
        top_k=top_k,
        include_docs_pages=include_docs_pages,
    )


def format_retrieval_context(documents: Iterable[RetrievalDocument]) -> str:
    parts: list[str] = []
    for index, doc in enumerate(documents, start=1):
        parts.append(
            "\n".join(
                [
                    f"[Local {index}] {doc.title}",
                    f"kind: {doc.kind}",
                    f"path: {doc.path}",
                    f"score: {doc.score:.4f}",
                    doc.text.strip(),
                ]
            )
        )
    return "\n\n".join(parts)


def _read_glob(root: Path, pattern: str, kind: str) -> list[RetrievalDocument]:
    documents: list[RetrievalDocument] = []
    for path in sorted(root.glob(pattern)):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel_path = path.relative_to(root).as_posix()
        documents.append(
            RetrievalDocument(
                id=rel_path,
                kind=kind,
                path=str(path),
                title=_title_from_path(path, text),
                text=text,
                tags=_tags_from_path(path, kind),
            )
        )
    return documents


def _title_from_path(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return path.stem


def _tags_from_path(path: Path, kind: str) -> tuple[str, ...]:
    parts = [kind, path.stem]
    parts.extend(parent.name for parent in path.parents[:3])
    return tuple(_tokens(" ".join(parts)))


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def _bm25_like_score(
    query_tokens: list[str],
    document_tokens: list[str],
    document_frequency: Counter[str],
    document_count: int,
) -> float:
    counts = Counter(document_tokens)
    length_norm = max(1.0, math.sqrt(len(document_tokens) / 250.0))
    score = 0.0
    for token in query_tokens:
        frequency = counts[token]
        if frequency == 0:
            continue
        idf = math.log(1 + (document_count + 1) / (document_frequency[token] + 1))
        score += (1 + math.log(frequency)) * idf / length_norm
    return score


def _kind_boost(kind: str) -> float:
    return {
        "module_card": 2.0,
        "skeleton": 1.5,
        "spec_example": 1.0,
        "known_good_code": 0.8,
        "known_good_metadata": 0.6,
        "known_bad_error": 0.5,
        "known_bad_code": 0.3,
        "docs_page": 0.0,
    }.get(kind, 0.0)


def _kind_rank(kind: str) -> int:
    order = {
        "module_card": 0,
        "skeleton": 1,
        "spec_example": 2,
        "known_good_code": 3,
        "known_good_metadata": 4,
        "known_bad_error": 5,
        "known_bad_code": 6,
        "docs_page": 7,
    }
    return order.get(kind, 99)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve local Strategy Factory context.")
    parser.add_argument("--query", default="", help="Search text.")
    parser.add_argument("--spec", default="", help="Optional canonical strategy spec JSON to search from.")
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of documents to return.")
    parser.add_argument("--include-docs-pages", action="store_true", help="Also search scraped NinjaTrader docs pages.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        results = retrieve_context_for_spec(
            spec,
            root=args.root,
            top_k=args.top_k,
            include_docs_pages=args.include_docs_pages,
        )
    else:
        results = retrieve_local_context(
            args.query,
            root=args.root,
            top_k=args.top_k,
            include_docs_pages=args.include_docs_pages,
        )
    print(format_retrieval_context(results))


if __name__ == "__main__":
    main()
