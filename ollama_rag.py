import json
import math
import sqlite3
from pathlib import Path
from typing import Iterable

import requests


DEFAULT_OLLAMA_URL = "http://localhost:11434"


def ollama_embed(ollama_url: str, model: str, text: str) -> list[float]:
    response = requests.post(
        f"{ollama_url.rstrip('/')}/api/embed",
        json={"model": model, "input": text},
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    embeddings = data.get("embeddings")
    if embeddings and isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
        return embeddings[0]

    embedding = data.get("embedding")
    if embedding:
        return embedding

    raise RuntimeError(f"Unexpected Ollama embed response: {data}")


def ollama_chat(
    ollama_url: str,
    model: str,
    messages: list[dict],
    *,
    temperature: float = 0.1,
) -> str:
    response = requests.post(
        f"{ollama_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def normalize(vector: Iterable[float]) -> list[float]:
    values = [float(item) for item in vector]
    magnitude = math.sqrt(sum(item * item for item in values))
    if magnitude == 0:
        return values
    return [item / magnitude for item in values]


def dot(left: Iterable[float], right: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def ensure_schema(db_path: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                section TEXT,
                parent TEXT,
                path_name TEXT,
                chunk_index INTEGER,
                text TEXT NOT NULL,
                vector_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.commit()


def index_has_chunk(connection: sqlite3.Connection, chunk_id: str) -> bool:
    row = connection.execute("SELECT 1 FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
    return row is not None


def insert_chunk(connection: sqlite3.Connection, record: dict, vector: list[float]) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO chunks (
            id, title, url, section, parent, path_name, chunk_index, text, vector_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["id"],
            record["title"],
            record["url"],
            record.get("section"),
            record.get("parent"),
            record.get("pathName"),
            record.get("chunk_index"),
            record["text"],
            json.dumps(vector),
        ),
    )


def load_chunks(chunks_path: str) -> Iterable[dict]:
    with Path(chunks_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def update_metadata(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        (key, value),
    )


def load_all_index_rows(db_path: str) -> list[dict]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, title, url, section, parent, path_name, chunk_index, text, vector_json
            FROM chunks
            """
        ).fetchall()

    items = []
    for row in rows:
        items.append(
            {
                "id": row[0],
                "title": row[1],
                "url": row[2],
                "section": row[3],
                "parent": row[4],
                "pathName": row[5],
                "chunk_index": row[6],
                "text": row[7],
                "vector": json.loads(row[8]),
            }
        )
    return items


def format_source_list(results: list[dict]) -> str:
    lines = []
    for item in results:
        lines.append(
            f"- {item['title']} | {item['url']} | score={item['score']:.4f} | chunk={item['chunk_index']}"
        )
    return "\n".join(lines)

