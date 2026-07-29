#!/usr/bin/env python3
import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

ITEM_ID = "208d9884575647c29f0dd5a1184e711a"
URL = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}/data"
TARGET = Path(".work/ipn/IPN_GB_2024.zip")
TARGET.parent.mkdir(parents=True, exist_ok=True)
request = urllib.request.Request(URL, headers={"User-Agent": "BelongWhere-IPN-Inspector/1.0"})
with urllib.request.urlopen(request, timeout=120) as response, TARGET.open("wb") as out:
    while True:
        block = response.read(1024 * 1024)
        if not block:
            break
        out.write(block)
print(f"IPN_ARCHIVE_SIZE={TARGET.stat().st_size}")
with zipfile.ZipFile(TARGET) as archive:
    print("IPN_MEMBERS=" + json.dumps(archive.namelist(), ensure_ascii=False))
    for member in archive.namelist():
        if not member.casefold().endswith((".csv", ".txt")):
            continue
        raw = archive.read(member)
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            continue
        reader = csv.reader(io.StringIO(text))
        print(f"IPN_SAMPLE_MEMBER={member}")
        for index, row in enumerate(reader):
            print("IPN_ROW=" + json.dumps(row, ensure_ascii=False))
            if index >= 3:
                break
