import json
import os

CACHE_FILE = "releases.json"


def load_from_releases_json():
    if not os.path.exists(CACHE_FILE) or os.path.getsize(CACHE_FILE) == 0:
        return None
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_to_releases_json(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
