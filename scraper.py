import os
import time
import re
import urllib.parse
import urllib.robotparser
from collections import deque

import requests
from bs4 import BeautifulSoup

# -----------------------------
# CONFIG
# -----------------------------
# ROOT_URL = "https://ninjatrader.com/support/helpGuides/nt8/"  # adjust if needed
ROOT_URL = "https://developer.ninjatrader.com/docs/"  # adjust if needed

OUTPUT_DIR = "ninjatrader_docs"
USER_AGENT = "NinjaTraderDocsScraper/1.0 (for personal RAG use)"
REQUEST_DELAY_SECONDS = 1.0  # be polite

MAX_PAGES = 2000  # safety cap

# Optional: restrict to URLs containing these substrings
ALLOWED_PATH_KEYWORDS = [
    "/nt8/",
    # add more if you want to narrow scope
]

# -----------------------------
# UTILITIES
# -----------------------------

def is_allowed_by_robots(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
    except Exception:
        # If robots.txt can't be read, default to disallowing nothing
        return True

    return rp.can_fetch(USER_AGENT, url)


def normalize_url(base_url: str, link: str) -> str | None:
    if not link:
        return None
    link = link.strip()
    if link.startswith("#") or link.startswith("mailto:") or link.startswith("javascript:"):
        return None
    return urllib.parse.urljoin(base_url, link)


def same_domain(url: str, root: str) -> bool:
    return urllib.parse.urlparse(url).netloc == urllib.parse.urlparse(root).netloc


def allowed_path(url: str) -> bool:
    if not ALLOWED_PATH_KEYWORDS:
        return True
    path = urllib.parse.urlparse(url).path
    return any(k in path for k in ALLOWED_PATH_KEYWORDS)


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "page"


def extract_clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove nav, footer, scripts, styles, etc.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Optional: remove specific layout elements if you know their classes/ids
    # for nav in soup.select("nav, header, footer, .menu, .navbar"):
    #     nav.decompose()

    text = soup.get_text(separator="\n")
    # Clean up blank lines
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def save_page_text(url: str, text: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or "index"
    slug = slugify(path)
    filename = os.path.join(OUTPUT_DIR, f"{slug}.txt")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\n\n")
        f.write(text)


# -----------------------------
# MAIN CRAWLER
# -----------------------------

def crawl_docs(root_url: str):
    if not is_allowed_by_robots(root_url):
        raise RuntimeError(f"robots.txt does not allow scraping {root_url} for this user agent.")

    visited = set()
    queue = deque([root_url])
    pages_crawled = 0

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    while queue and pages_crawled < MAX_PAGES:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if not same_domain(url, root_url) or not allowed_path(url):
            continue

        print(f"[{pages_crawled+1}] Fetching: {url}")
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"  ! Error fetching {url}: {e}")
            continue

        text = extract_clean_text(resp.text)
        save_page_text(url, text)
        pages_crawled += 1

        # Parse links for further crawling
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            next_url = normalize_url(url, a["href"])
            if not next_url:
                continue
            if next_url not in visited and same_domain(next_url, root_url) and allowed_path(next_url):
                queue.append(next_url)

        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"Done. Crawled {pages_crawled} pages. Output in: {OUTPUT_DIR}")


if __name__ == "__main__":
    crawl_docs(ROOT_URL)
