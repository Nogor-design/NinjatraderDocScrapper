import argparse
import csv
import difflib
import json
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import requests

from generate_ninjascript import SYSTEM_PROMPT, build_user_prompt, extract_code_block, retrieve
from ollama_rag import DEFAULT_OLLAMA_URL, ollama_chat


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "webgui"
DB_PATH = ROOT / "ninjatrader_gui.sqlite"
ARTIFACTS_DIR = ROOT / "iteration_artifacts"
TRAINING_EXPORTS_DIR = ROOT / "training_exports"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def resolve_user_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


def ensure_schema() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS iterations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                user_task TEXT NOT NULL,
                existing_code TEXT NOT NULL,
                compiler_errors TEXT NOT NULL,
                answer TEXT NOT NULL,
                code TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT 'unreviewed',
                label_notes TEXT NOT NULL DEFAULT '',
                output_path TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL,
                embed_model TEXT NOT NULL,
                top_k INTEGER NOT NULL,
                temperature REAL NOT NULL,
                sources_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                artifact_path TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
            """
        )
        connection.commit()


def db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def list_sessions() -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   COUNT(i.id) AS iteration_count,
                   SUM(CASE WHEN i.label = 'good' THEN 1 ELSE 0 END) AS good_count,
                   SUM(CASE WHEN i.label = 'bad' THEN 1 ELSE 0 END) AS bad_count
            FROM sessions s
            LEFT JOIN iterations i ON i.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC, s.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def create_session(title: str) -> dict:
    created_at = now_iso()
    title = title.strip() or f"Session {created_at}"
    with db_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO sessions (title, created_at, updated_at) VALUES (?, ?, ?)",
            (title, created_at, created_at),
        )
        session_id = cursor.lastrowid
        connection.commit()
    return get_session(session_id)


def update_session_timestamp(connection: sqlite3.Connection, session_id: int) -> None:
    connection.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now_iso(), session_id),
    )


def get_session(session_id: int) -> dict:
    with db_connection() as connection:
        session = connection.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if session is None:
            raise KeyError(f"Session {session_id} not found")

        iterations = connection.execute(
            """
            SELECT id, session_id, user_task, existing_code, compiler_errors, answer, code,
                   label, label_notes, output_path, model, embed_model, top_k, temperature,
                   sources_json, created_at, artifact_path
            FROM iterations
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()

    data = dict(session)
    data["iterations"] = []
    for row in iterations:
        item = dict(row)
        item["sources"] = json.loads(item.pop("sources_json"))
        data["iterations"].append(item)
    return data


def get_iteration(iteration_id: int) -> dict:
    with db_connection() as connection:
        row = connection.execute(
            """
            SELECT id, session_id, user_task, existing_code, compiler_errors, answer, code,
                   label, label_notes, output_path, model, embed_model, top_k, temperature,
                   sources_json, created_at, artifact_path
            FROM iterations
            WHERE id = ?
            """,
            (iteration_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"Iteration {iteration_id} not found")
    item = dict(row)
    item["sources"] = json.loads(item.pop("sources_json"))
    return item


def session_history_messages(session_id: int, limit_pairs: int = 4) -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT user_task, compiler_errors, answer
            FROM iterations
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit_pairs),
        ).fetchall()

    messages: list[dict] = []
    for row in reversed(rows):
        user_content = f"Task:\n{row['user_task']}"
        if row["compiler_errors"]:
            user_content += f"\n\nCompiler errors:\n{row['compiler_errors']}"
        messages.append({"role": "user", "content": user_content})
        messages.append({"role": "assistant", "content": row["answer"]})
    return messages


def current_models(ollama_url: str) -> list[str]:
    response = requests.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=15)
    response.raise_for_status()
    return [item["name"] for item in response.json().get("models", [])]


def load_compiler_errors_csv(csv_path_text: str) -> dict:
    csv_path = resolve_user_path(csv_path_text)
    if not csv_path.exists():
        raise FileNotFoundError(f"Compiler CSV not found: {csv_path}")

    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not any((value or "").strip() for value in row.values()):
                continue
            file_name = (row.get("NinjaScript File") or row.get("File") or "").strip()
            error = (row.get("Error") or "").strip()
            code = (row.get("Code") or "").strip()
            line = (row.get("Line") or "").strip()
            column = (row.get("Column") or "").strip()
            formatted = f"{file_name}({line},{column}) {code}: {error}".strip()
            rows.append(
                {
                    "file": file_name,
                    "error": error,
                    "code": code,
                    "line": line,
                    "column": column,
                    "formatted": formatted,
                }
            )

    text = "\n".join(item["formatted"] for item in rows)
    return {"path": str(csv_path), "count": len(rows), "rows": rows, "text": text}


def diff_iterations(left_iteration_id: int, right_iteration_id: int) -> dict:
    left = get_iteration(left_iteration_id)
    right = get_iteration(right_iteration_id)
    diff_lines = list(
        difflib.unified_diff(
            left["code"].splitlines(),
            right["code"].splitlines(),
            fromfile=f"iteration_{left_iteration_id}",
            tofile=f"iteration_{right_iteration_id}",
            lineterm="",
        )
    )
    return {
        "left_iteration_id": left_iteration_id,
        "right_iteration_id": right_iteration_id,
        "left_label": left["label"],
        "right_label": right["label"],
        "diff": "\n".join(diff_lines),
    }


def labeled_iterations() -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT i.id, i.session_id, i.user_task, i.existing_code, i.compiler_errors, i.answer, i.code,
                   i.label, i.label_notes, i.output_path, i.model, i.embed_model, i.top_k, i.temperature,
                   i.sources_json, i.created_at, i.artifact_path, s.title AS session_title
            FROM iterations i
            JOIN sessions s ON s.id = i.session_id
            WHERE i.label IN ('good', 'bad')
            ORDER BY i.id ASC
            """
        ).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item["sources"] = json.loads(item.pop("sources_json"))
        items.append(item)
    return items


def training_user_content(iteration: dict) -> str:
    parts = [f"Task:\n{iteration['user_task']}"]
    if iteration["existing_code"].strip():
        parts.append(f"Existing code:\n```csharp\n{iteration['existing_code'].strip()}\n```")
    if iteration["compiler_errors"].strip():
        parts.append(f"Compiler errors:\n```text\n{iteration['compiler_errors'].strip()}\n```")
    return "\n\n".join(parts)


def export_training_bundle() -> dict:
    TRAINING_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = TRAINING_EXPORTS_DIR / f"export_{stamp}"
    export_dir.mkdir(parents=True, exist_ok=True)

    labeled = labeled_iterations()
    good = [item for item in labeled if item["label"] == "good"]
    bad = [item for item in labeled if item["label"] == "bad"]

    good_sft_path = export_dir / "good_sft.jsonl"
    review_corpus_path = export_dir / "review_corpus.jsonl"
    summary_path = export_dir / "summary.json"

    with good_sft_path.open("w", encoding="utf-8") as handle:
        for item in good:
            record = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": training_user_content(item)},
                    {"role": "assistant", "content": item["answer"]},
                ],
                "metadata": {
                    "iteration_id": item["id"],
                    "session_id": item["session_id"],
                    "session_title": item["session_title"],
                    "label_notes": item["label_notes"],
                    "output_path": item["output_path"],
                    "artifact_path": item["artifact_path"],
                    "sources": item["sources"],
                },
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    with review_corpus_path.open("w", encoding="utf-8") as handle:
        for item in labeled:
            record = {
                "iteration_id": item["id"],
                "session_id": item["session_id"],
                "session_title": item["session_title"],
                "label": item["label"],
                "label_notes": item["label_notes"],
                "task": item["user_task"],
                "existing_code": item["existing_code"],
                "compiler_errors": item["compiler_errors"],
                "answer": item["answer"],
                "code": item["code"],
                "model": item["model"],
                "embed_model": item["embed_model"],
                "created_at": item["created_at"],
                "output_path": item["output_path"],
                "artifact_path": item["artifact_path"],
                "sources": item["sources"],
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {
        "exported_at": now_iso(),
        "export_dir": str(export_dir),
        "good_examples": len(good),
        "bad_examples": len(bad),
        "total_labeled": len(labeled),
        "files": {
            "good_sft": str(good_sft_path),
            "review_corpus": str(review_corpus_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def save_iteration_artifact(iteration_id: int, label: str, notes: str, compiler_errors: str) -> str:
    iteration = get_iteration(iteration_id)
    folder = ARTIFACTS_DIR / label / f"iteration_{iteration_id}"
    folder.mkdir(parents=True, exist_ok=True)

    metadata = {
        "id": iteration["id"],
        "session_id": iteration["session_id"],
        "label": label,
        "label_notes": notes,
        "model": iteration["model"],
        "embed_model": iteration["embed_model"],
        "created_at": iteration["created_at"],
        "task": iteration["user_task"],
        "output_path": iteration["output_path"],
        "sources": iteration["sources"],
    }
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (folder / "response.md").write_text(iteration["answer"], encoding="utf-8")
    (folder / "code.cs").write_text(iteration["code"], encoding="utf-8")
    if compiler_errors.strip():
        (folder / "compiler_errors.txt").write_text(compiler_errors, encoding="utf-8")
    if notes.strip():
        (folder / "notes.txt").write_text(notes, encoding="utf-8")
    return str(folder)


def mark_iteration(iteration_id: int, label: str, notes: str, compiler_errors: str) -> dict:
    artifact_path = ""
    if label in {"good", "bad"}:
        artifact_path = save_iteration_artifact(iteration_id, label, notes, compiler_errors)

    with db_connection() as connection:
        connection.execute(
            """
            UPDATE iterations
            SET label = ?, label_notes = ?, compiler_errors = ?, artifact_path = ?
            WHERE id = ?
            """,
            (label, notes, compiler_errors, artifact_path, iteration_id),
        )
        session_id = connection.execute(
            "SELECT session_id FROM iterations WHERE id = ?",
            (iteration_id,),
        ).fetchone()[0]
        update_session_timestamp(connection, session_id)
        connection.commit()
    return get_iteration(iteration_id)


def save_code_file(iteration_id: int, output_path: str, code_override: str = "") -> dict:
    iteration = get_iteration(iteration_id)
    code = code_override or iteration["code"]
    target = resolve_user_path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code, encoding="utf-8")

    with db_connection() as connection:
        connection.execute(
            "UPDATE iterations SET output_path = ? WHERE id = ?",
            (str(target), iteration_id),
        )
        session_id = connection.execute(
            "SELECT session_id FROM iterations WHERE id = ?",
            (iteration_id,),
        ).fetchone()[0]
        update_session_timestamp(connection, session_id)
        connection.commit()
    return get_iteration(iteration_id)


def run_generation(payload: dict) -> dict:
    session_id = int(payload["session_id"])
    task = payload.get("task", "").strip()
    if not task:
        raise ValueError("Task is required")

    existing_code = payload.get("existing_code", "")
    compiler_errors = payload.get("compiler_errors", "")
    compiler_errors_csv_path = payload.get("compiler_errors_csv_path", "").strip()
    model = payload.get("model", "qwen3-coder:30b")
    embed_model = payload.get("embed_model", "nomic-embed-text")
    top_k = int(payload.get("top_k", 8))
    temperature = float(payload.get("temperature", 0.1))
    output_path = payload.get("output_path", "").strip()
    ollama_url = payload.get("ollama_url", DEFAULT_OLLAMA_URL)
    db_path = payload.get("db", str(ROOT / "ninjatrader_docs" / "rag_index.sqlite"))

    if compiler_errors_csv_path:
        compiler_errors = load_compiler_errors_csv(compiler_errors_csv_path)["text"]

    retrieve_args = SimpleNamespace(
        db=db_path,
        ollama_url=ollama_url,
        embed_model=embed_model,
        top_k=top_k,
    )
    query_text = "\n\n".join(
        part for part in [task, existing_code[:3000], compiler_errors[:3000]] if part.strip()
    )
    results = retrieve(retrieve_args, query_text)
    rag_message = build_user_prompt(task, results, existing_code, compiler_errors)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(session_history_messages(session_id))
    messages.append({"role": "user", "content": rag_message})

    answer = ollama_chat(
        ollama_url,
        model,
        messages,
        temperature=temperature,
    )
    code = extract_code_block(answer)

    saved_output_path = ""
    if output_path:
        target = resolve_user_path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code if target.suffix.lower() == ".cs" else answer, encoding="utf-8")
        saved_output_path = str(target)

    created_at = now_iso()
    with db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO iterations (
                session_id, user_task, existing_code, compiler_errors, answer, code,
                label, label_notes, output_path, model, embed_model, top_k, temperature,
                sources_json, created_at, artifact_path
            ) VALUES (?, ?, ?, ?, ?, ?, 'unreviewed', '', ?, ?, ?, ?, ?, ?, ?, '')
            """,
            (
                session_id,
                task,
                existing_code,
                compiler_errors,
                answer,
                code,
                saved_output_path,
                model,
                embed_model,
                top_k,
                temperature,
                json.dumps(
                    [
                        {
                            "title": item["title"],
                            "url": item["url"],
                            "score": item["score"],
                            "chunk_index": item["chunk_index"],
                        }
                        for item in results
                    ]
                ),
                created_at,
            ),
        )
        iteration_id = cursor.lastrowid
        session_title = connection.execute(
            "SELECT title FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()[0]
        if session_title.startswith("Session ") and task:
            new_title = task[:80]
            connection.execute("UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id))
        update_session_timestamp(connection, session_id)
        connection.commit()
    return get_iteration(iteration_id)


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "NinjaTraderGUI/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self.serve_static("index.html", "text/html; charset=utf-8")
        if parsed.path.startswith("/static/"):
            relative = parsed.path.removeprefix("/static/")
            return self.serve_static(relative, self.content_type(relative))
        if parsed.path == "/api/sessions":
            return self.write_json({"sessions": list_sessions()})
        if parsed.path.startswith("/api/sessions/"):
            try:
                session_id = int(parsed.path.split("/")[-1])
                return self.write_json(get_session(session_id))
            except Exception as exc:
                return self.write_error_json(exc)
        if parsed.path == "/api/models":
            query = parse_qs(parsed.query)
            ollama_url = query.get("ollama_url", [DEFAULT_OLLAMA_URL])[0]
            try:
                return self.write_json({"models": current_models(ollama_url)})
            except Exception as exc:
                return self.write_error_json(exc)
        if parsed.path == "/api/compiler-errors/load":
            query = parse_qs(parsed.query)
            csv_path = query.get("path", [""])[0]
            try:
                return self.write_json(load_compiler_errors_csv(csv_path))
            except Exception as exc:
                return self.write_error_json(exc)
        if parsed.path.startswith("/api/iterations/") and parsed.path.endswith("/diff"):
            try:
                iteration_id = int(parsed.path.split("/")[-2])
                query = parse_qs(parsed.query)
                other_id = int(query.get("other_id", ["0"])[0])
                return self.write_json(diff_iterations(iteration_id, other_id))
            except Exception as exc:
                return self.write_error_json(exc)
        return self.write_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self.read_json_body()
            if parsed.path == "/api/sessions":
                title = payload.get("title", "")
                return self.write_json(create_session(title), status=HTTPStatus.CREATED)
            if parsed.path == "/api/export":
                return self.write_json(export_training_bundle(), status=HTTPStatus.CREATED)
            if parsed.path.endswith("/generate") and parsed.path.startswith("/api/sessions/"):
                session_id = int(parsed.path.split("/")[-2])
                payload["session_id"] = session_id
                return self.write_json(run_generation(payload), status=HTTPStatus.CREATED)
            if parsed.path.endswith("/label") and parsed.path.startswith("/api/iterations/"):
                iteration_id = int(parsed.path.split("/")[-2])
                label = payload.get("label", "unreviewed")
                notes = payload.get("notes", "")
                compiler_errors = payload.get("compiler_errors", "")
                return self.write_json(
                    mark_iteration(iteration_id, label, notes, compiler_errors),
                    status=HTTPStatus.OK,
                )
            if parsed.path.endswith("/save") and parsed.path.startswith("/api/iterations/"):
                iteration_id = int(parsed.path.split("/")[-2])
                output_path = payload.get("output_path", "").strip()
                if not output_path:
                    raise ValueError("output_path is required")
                code = payload.get("code", "")
                return self.write_json(save_code_file(iteration_id, output_path, code), status=HTTPStatus.OK)
        except Exception as exc:
            return self.write_error_json(exc)

        return self.write_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def serve_static(self, relative_path: str, content_type: str) -> None:
        path = (STATIC_DIR / relative_path).resolve()
        if (
            not path.exists()
            or not path.is_file()
            or (STATIC_DIR not in path.parents and path != STATIC_DIR / "index.html")
        ):
            return self.write_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def content_type(self, relative_path: str) -> str:
        suffix = Path(relative_path).suffix.lower()
        return {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(suffix, "text/plain; charset=utf-8")

    def write_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def write_error_json(self, exc: Exception) -> None:
        status = HTTPStatus.BAD_REQUEST
        if isinstance(exc, KeyError):
            status = HTTPStatus.NOT_FOUND
        self.write_json({"error": str(exc)}, status=status)

    def log_message(self, format: str, *args) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local NinjaTrader iteration web GUI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    ensure_schema()
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), RequestHandler)
    print(f"NinjaTrader GUI running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
