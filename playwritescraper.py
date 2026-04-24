from playwright.sync_api import sync_playwright
import time
import os

OUTPUT_DIR = "ninjatrader_docs"
URL = "https://developer.ninjatrader.com/docs/desktop"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def scrape_docs():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")

        # Expand all collapsible sections
        buttons = page.query_selector_all("button")
        for b in buttons:
            try:
                b.click()
                time.sleep(0.1)
            except:
                pass

        # Scroll to bottom to load lazy content
        for _ in range(20):
            page.mouse.wheel(0, 2000)
            time.sleep(0.2)

        text = page.inner_text("body")

        with open(os.path.join(OUTPUT_DIR, "desktop_docs.txt"), "w", encoding="utf-8") as f:
            f.write(text)

        browser.close()

if __name__ == "__main__":
    scrape_docs()
