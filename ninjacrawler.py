from playwright.sync_api import sync_playwright
import time
import os
import re

BASE_URL = "https://developer.ninjatrader.com"
START_URL = f"{BASE_URL}/docs/desktop"

OUTPUT_DIR = "ninjatrader_docs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def safe_filename(url_path: str) -> str:
    """Convert URL path into a safe filename."""
    name = url_path.strip("/").replace("/", "_")
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return name or "index"

def expand_all_sections(page):
    """Click all expand/toggle buttons repeatedly."""
    for _ in range(10):
        buttons = page.query_selector_all("button")
        clicked = False
        for b in buttons:
            try:
                aria = b.get_attribute("aria-label")
                if aria and ("expand" in aria.lower() or "toggle" in aria.lower()):
                    b.click()
                    clicked = True
                    time.sleep(0.1)
            except:
                pass
        if not clicked:
            break

def scroll_full_page(page):
    """Scroll down to trigger lazy loading."""
    for _ in range(40):
        page.mouse.wheel(0, 2000)
        time.sleep(0.15)

def extract_links_from_sidebar(page):
    """Extract all documentation links from the left navigation."""
    links = page.query_selector_all("nav a[href]")
    urls = set()

    for link in links:
        href = link.get_attribute("href")
        if href and href.startswith("/docs/desktop"):
            urls.add(BASE_URL + href)

    return sorted(urls)

def scrape_page(page, url):
    """Load a single documentation page and extract text."""
    print(f"Scraping: {url}")
    page.goto(url, wait_until="networkidle")

    # Expand sections and scroll
    expand_all_sections(page)
    scroll_full_page(page)

    # Extract text
    text = page.inner_text("body")

    # Save to file
    filename = safe_filename(url.replace(BASE_URL, "")) + ".txt"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\n\n")
        f.write(text)

    print(f"Saved: {filepath}")

def crawl_all_docs():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Loading main docs page...")
        page.goto(START_URL, wait_until="networkidle")

        # Wait for sidebar
        page.wait_for_selector("nav", timeout=15000)

        print("Expanding sidebar...")
        expand_all_sections(page)

        print("Collecting links...")
        urls = extract_links_from_sidebar(page)
        print(f"Found {len(urls)} documentation pages.")

        # Scrape each page
        for url in urls:
            scrape_page(page, url)

        browser.close()
        print("Done crawling all documentation.")

if __name__ == "__main__":
    crawl_all_docs()
