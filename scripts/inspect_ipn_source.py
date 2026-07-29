#!/usr/bin/env python3
import json
import urllib.request

ITEM_ID = "208d9884575647c29f0dd5a1184e711a"
BASE = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}"


def get_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "BelongWhere-IPN-Inspector/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


item = get_json(BASE + "?f=json")
print("ITEM_META")
for key in ["id", "title", "type", "typeKeywords", "url", "name", "size", "access", "owner", "modified"]:
    print(f"{key}={json.dumps(item.get(key), ensure_ascii=False)}")

try:
    data = get_json(BASE + "/data?f=json")
    print("ITEM_DATA_KEYS=" + json.dumps(sorted(data.keys())))
    print("ITEM_DATA=" + json.dumps(data, ensure_ascii=False)[:10000])
except Exception as exc:
    print(f"ITEM_DATA_ERROR={type(exc).__name__}:{exc}")
