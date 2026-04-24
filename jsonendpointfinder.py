import requests
from bs4 import BeautifulSoup
import json
import os

ROOT = "https://developer.ninjatrader.com/docs/desktop"
OUT = "ninjatrader_docs"
os.makedirs(OUT, exist_ok=True)

html = requests.get(ROOT).text
soup = BeautifulSoup(html, "html.parser")

# Extract the Next.js data blob
next_data_script = soup.find("script", id="__NEXT_DATA__")
next_data = json.loads(next_data_script.string)

# This contains the buildId and page structure
build_id = next_data["buildId"]
page_path = next_data["page"]  # e.g. "/docs/desktop"

json_url = f"https://developer.ninjatrader.com/_next/data/{build_id}{page_path}.json"

print("Discovered JSON URL:", json_url)