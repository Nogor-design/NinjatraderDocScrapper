import requests
import json

url = "https://developer.ninjatrader.com/_next/data/latest/docs/desktop.json"
resp = requests.get(url)
data = resp.json()

# Extract text fields
def extract_text(obj):
    if isinstance(obj, dict):
        return " ".join(extract_text(v) for v in obj.values())
    elif isinstance(obj, list):
        return " ".join(extract_text(v) for v in obj)
    elif isinstance(obj, str):
        return obj
    return ""

text = extract_text(data)
with open("ninjatrader_docs/desktop_docs.txt", "w", encoding="utf-8") as f:
    f.write(text)
