import argparse
import json
import re
import time
from pathlib import Path
from typing import Iterable

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


BASE_URL = "https://developer.ninjatrader.com"
DESKTOP_DOCS_URL = f"{BASE_URL}/docs/desktop"
USER_AGENT = "NinjaTraderDocsRAG/1.0"

DOC_ENTRY_RE = re.compile(
    r'\{\\"order\\":\d+,\\"parent\\":(?:null|\\"[^\\"]*\\"),'
    r'\\"pathName\\":\\"[^\\"]+\\",\\"section\\":\\"[^\\"]+\\",'
    r'\\"title\\":\\"(?:[^\\"]|\\\\.)*\\"\}'
)


def safe_name(value: str) -> str:
    value = value.strip().strip("/")
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)
    return value or "index"


def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    lines = [line.rstrip() for line in text.splitlines()]

    cleaned: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        cleaned.append(line)
        previous_blank = blank

    return "\n".join(cleaned).strip()


def discover_docs() -> list[dict]:
    response = requests.get(
        DESKTOP_DOCS_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    docs: dict[str, dict] = {
        "index": {
            "order": 0,
            "parent": None,
            "pathName": "index",
            "section": "guides",
            "title": "Introduction",
        }
    }

    for raw in DOC_ENTRY_RE.findall(response.text):
        decoded = raw.replace('\\"', '"')
        doc = json.loads(decoded)
        docs[doc["pathName"]] = doc

    return sorted(
        docs.values(),
        key=lambda item: (
            item.get("section") or "",
            item.get("parent") or "",
            item.get("order", 0),
            item.get("title") or "",
        ),
    )


def doc_url(path_name: str) -> str:
    if path_name == "index":
        return DESKTOP_DOCS_URL
    return f"{DESKTOP_DOCS_URL}/{path_name}"


def extract_article(page, url: str) -> tuple[str, str]:
    page.goto(url, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(750)

    try:
        page.locator("main").first.wait_for(timeout=15_000)
    except PlaywrightTimeoutError:
        pass

    title = ""
    for selector in ("main h1", "h1"):
        locator = page.locator(selector).first
        try:
            if locator.count():
                title = clean_text(locator.inner_text(timeout=2_000))
                if title:
                    break
        except PlaywrightTimeoutError:
            continue

    text = ""
    for selector in ("main article", "article", "main section.py-4"):
        locator = page.locator(selector).first
        try:
            if locator.count():
                text = clean_text(locator.inner_text(timeout=5_000))
                if text:
                    break
        except PlaywrightTimeoutError:
            continue

    if not text:
        text = clean_text(page.locator("body").inner_text(timeout=10_000))

    return title, text


def chunk_text(text: str, *, max_chars: int = 2400, overlap_chars: int = 250) -> Iterable[str]:
    paragraphs = re.split(r"\n{2,}", text)
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        next_text = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(next_text) <= max_chars:
            current = next_text
            continue

        if current:
            yield current.strip()
            current = current[-overlap_chars:].strip()

        if len(paragraph) > max_chars:
            start = 0
            while start < len(paragraph):
                end = start + max_chars
                yield paragraph[start:end].strip()
                start = max(0, end - overlap_chars)
                if start >= len(paragraph):
                    break
            current = ""
        else:
            current = paragraph

    if current:
        yield current.strip()


def write_outputs(out_dir: Path, docs: list[dict], pages: list[dict]) -> None:
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / "manifest.jsonl"
    chunks_path = out_dir / "chunks.jsonl"

    with manifest_path.open("w", encoding="utf-8") as manifest_file, chunks_path.open(
        "w", encoding="utf-8"
    ) as chunks_file:
        for page in pages:
            path_name = page["pathName"]
            markdown_path = pages_dir / f"{safe_name(path_name)}.md"

            header = [
                "---",
                f'title: "{page["title"].replace(chr(34), chr(39))}"',
                f"url: {page['url']}",
                f"section: {page.get('section') or ''}",
                f"parent: {page.get('parent') or ''}",
                f"pathName: {path_name}",
                "---",
                "",
                f"# {page['title']}",
                "",
            ]
            markdown_path.write_text("\n".join(header) + page["text"] + "\n", encoding="utf-8")

            manifest_record = {
                key: page[key]
                for key in ("title", "url", "section", "parent", "pathName", "text_chars")
            }
            manifest_record["markdown_path"] = str(markdown_path)
            manifest_file.write(json.dumps(manifest_record, ensure_ascii=False) + "\n")

            for index, chunk in enumerate(chunk_text(page["text"])):
                chunk_record = {
                    "id": f"{path_name}:{index}",
                    "title": page["title"],
                    "url": page["url"],
                    "section": page.get("section"),
                    "parent": page.get("parent"),
                    "pathName": path_name,
                    "chunk_index": index,
                    "text": chunk,
                }
                chunks_file.write(json.dumps(chunk_record, ensure_ascii=False) + "\n")

    index_path = out_dir / "docs_index.json"
    index_path.write_text(json.dumps(docs, indent=2, ensure_ascii=False), encoding="utf-8")


def scrape(args: argparse.Namespace) -> None:
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = discover_docs()
    if args.include:
        include_pattern = re.compile(args.include, re.IGNORECASE)
        docs = [
            doc
            for doc in docs
            if include_pattern.search(doc["pathName"])
            or include_pattern.search(doc["title"])
            or include_pattern.search(doc.get("parent") or "")
        ]
    if args.limit:
        docs = docs[: args.limit]

    print(f"Discovered {len(docs)} desktop documentation pages to scrape.")

    pages: list[dict] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.show_browser)
        page = browser.new_page(user_agent=USER_AGENT)

        for number, doc in enumerate(docs, start=1):
            url = doc_url(doc["pathName"])
            print(f"[{number}/{len(docs)}] {doc['title']} - {url}")
            try:
                title, text = extract_article(page, url)
            except Exception as exc:
                print(f"  ! skipped: {exc}")
                continue

            title = title or doc["title"]
            text = clean_text(text)
            if len(text) < args.min_chars:
                print(f"  ! skipped: extracted only {len(text)} chars")
                continue

            pages.append(
                {
                    **doc,
                    "title": title,
                    "url": url,
                    "text": text,
                    "text_chars": len(text),
                }
            )
            time.sleep(args.delay)

        browser.close()

    write_outputs(out_dir, docs, pages)
    print(f"Saved {len(pages)} pages to {out_dir}")
    print(f"RAG chunks: {out_dir / 'chunks.jsonl'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape hydrated NinjaTrader Desktop SDK docs into Markdown and JSONL chunks."
    )
    parser.add_argument("--output", default="ninjatrader_docs", help="Output directory.")
    parser.add_argument("--limit", type=int, default=0, help="Limit pages for test runs.")
    parser.add_argument(
        "--include",
        default="",
        help="Optional regex matched against title, pathName, or parent.",
    )
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between pages.")
    parser.add_argument(
        "--min-chars",
        type=int,
        default=80,
        help="Skip pages with less extracted text than this.",
    )
    parser.add_argument("--show-browser", action="store_true", help="Run browser visibly.")
    return parser.parse_args()


if __name__ == "__main__":
    scrape(parse_args())
