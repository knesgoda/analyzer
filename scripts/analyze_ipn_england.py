#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ARCHIVE = Path(".work/ipn/IPN_GB_2024.zip")
MEMBER = "IPN_GB_2024.csv"

with zipfile.ZipFile(ARCHIVE) as archive:
    raw = archive.read(MEMBER)
text = raw.decode("cp1252")
reader = csv.DictReader(io.StringIO(text))
counts = Counter()
split_counts = Counter()
samples = defaultdict(list)
place_codes = Counter()
rows = 0
blank_country = 0
for row in reader:
    country = (row.get("ctry23nm") or "").strip()
    if not country:
        blank_country += 1
    if country.casefold() != "england":
        continue
    rows += 1
    desc = (row.get("descnm") or "").strip() or "BLANK"
    counts[desc] += 1
    split_counts[(row.get("splitind") or "").strip()] += 1
    code = (row.get("place23cd") or "").strip()
    if code:
        place_codes[code] += 1
    if len(samples[desc]) < 4:
        samples[desc].append({
            key: (row.get(key) or "").strip()
            for key in [
                "tempcode",
                "placeid",
                "place23cd",
                "place23nm",
                "splitind",
                "descnm",
                "ctry23nm",
                "cty23cd",
                "cty23nm",
                "lad23cd",
                "lad23nm",
                "lad23desc",
                "wd23cd",
                "par23cd",
                "rgn23cd",
                "rgn23nm",
                "bua22cd",
                "lat",
                "long",
            ]
        })

summary = {
    "england_rows": rows,
    "unique_place23cd": len(place_codes),
    "duplicate_place23cd_groups": sum(1 for value in place_codes.values() if value > 1),
    "blank_country_rows_all_gb": blank_country,
    "descriptor_counts": dict(sorted(counts.items())),
    "split_indicator_counts": dict(sorted(split_counts.items())),
    "samples": {key: value for key, value in sorted(samples.items())},
}
print("IPN_ENGLAND_ANALYSIS=" + json.dumps(summary, ensure_ascii=False))
