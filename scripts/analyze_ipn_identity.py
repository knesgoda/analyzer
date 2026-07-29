#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

archive_path = Path(".work/ipn/IPN_GB_2024.zip")
with zipfile.ZipFile(archive_path) as archive:
    text = archive.read("IPN_GB_2024.csv").decode("cp1252")
reader = csv.DictReader(io.StringIO(text))
by_placeid = defaultdict(list)
for row in reader:
    if (row.get("ctry23nm") or "").strip().casefold() != "england":
        continue
    by_placeid[(row.get("placeid") or "").strip()].append(row)

size_counts = Counter()
desc_unique = Counter()
cross_descriptor = []
zero_coordinate_groups = Counter()
for placeid, rows in by_placeid.items():
    size_counts[len(rows)] += 1
    descs = sorted({(row.get("descnm") or "").strip() for row in rows})
    for desc in descs:
        desc_unique[desc] += 1
    if len(descs) > 1:
        cross_descriptor.append({
            "placeid": placeid,
            "descs": descs,
            "names": sorted({(row.get("place23nm") or "").strip() for row in rows}),
            "row_count": len(rows),
        })
    nonzero = [
        row for row in rows
        if float((row.get("lat") or "0") or 0) != 0.0
        or float((row.get("long") or "0") or 0) != 0.0
    ]
    if not nonzero:
        for desc in descs:
            zero_coordinate_groups[desc] += 1

largest = sorted(
    (
        {
            "placeid": placeid,
            "row_count": len(rows),
            "descs": sorted({(row.get("descnm") or "").strip() for row in rows}),
            "names": sorted({(row.get("place23nm") or "").strip() for row in rows}),
        }
        for placeid, rows in by_placeid.items()
    ),
    key=lambda item: (-item["row_count"], item["placeid"]),
)[:20]

summary = {
    "unique_placeid": len(by_placeid),
    "group_size_counts": dict(sorted(size_counts.items())),
    "unique_placeids_by_descriptor": dict(sorted(desc_unique.items())),
    "cross_descriptor_placeid_count": len(cross_descriptor),
    "cross_descriptor_samples": cross_descriptor[:20],
    "zero_coordinate_groups_by_descriptor": dict(sorted(zero_coordinate_groups.items())),
    "largest_groups": largest,
}
print("IPN_IDENTITY_ANALYSIS=" + json.dumps(summary, ensure_ascii=False))
