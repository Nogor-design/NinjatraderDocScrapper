import argparse
import sqlite3
from pathlib import Path

import requests

from ollama_rag import (
    DEFAULT_OLLAMA_URL,
    ensure_schema,
    index_has_chunk,
    insert_chunk,
    load_chunks,
    normalize,
    ollama_embed,
    update_metadata,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local SQLite embedding index from NinjaTrader docs chunks.jsonl using Ollama."
    )
    parser.add_argument("--chunks", default="ninjatrader_docs\\chunks.jsonl", help="Input chunks JSONL.")
    parser.add_argument("--db", default="ninjatrader_docs\\rag_index.sqlite", help="Output SQLite index.")
    parser.add_argument("--embed-model", default="nomic-embed-text", help="Ollama embedding model.")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for test runs.")
    parser.add_argument("--reset", action="store_true", help="Delete and rebuild the SQLite index first.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks_path = Path(args.chunks)
    if not chunks_path.exists():
        raise SystemExit(f"Chunks file not found: {chunks_path}")

    db_path = Path(args.db)
    if args.reset and db_path.exists():
        db_path.unlink()

    ensure_schema(args.db)

    processed = 0
    inserted = 0
    with sqlite3.connect(args.db) as connection:
        for record in load_chunks(str(chunks_path)):
            processed += 1
            if args.limit and processed > args.limit:
                break

            if index_has_chunk(connection, record["id"]):
                if processed % 100 == 0:
                    print(f"Checked {processed} chunks, index already contains {record['id']}")
                continue

            try:
                vector = normalize(ollama_embed(args.ollama_url, args.embed_model, record["text"]))
            except requests.HTTPError as exc:
                message = (
                    f"Embedding failed for chunk {record['id']} with {len(record['text'])} chars "
                    f"using model {args.embed_model}: {exc}"
                )
                raise SystemExit(message) from exc
            insert_chunk(connection, record, vector)
            inserted += 1

            if inserted % 10 == 0:
                connection.commit()
                print(f"Indexed {inserted} new chunks ({processed} processed)")

        update_metadata(connection, "embed_model", args.embed_model)
        update_metadata(connection, "chunks_path", str(chunks_path))
        connection.commit()

    print(f"Done. Processed {processed} chunks and inserted {inserted} new rows into {args.db}")


if __name__ == "__main__":
    main()
