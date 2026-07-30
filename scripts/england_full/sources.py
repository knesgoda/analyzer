from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from pyproj import Transformer

from common import (
    Acc,
    IPN_TYPE_MAP,
    IPN_ZIP,
    OS_FIELDS,
    OS_TYPE_MAP,
    OS_ZIP,
    first_nonblank,
    norm,
    safe_text,
    stable_uuid,
    valid_coord,
)


def choose_canonical_name(rows: list[dict[str, str]]) -> tuple[str, int]:
    all_names = [safe_text(row.get("place23nm")) for row in rows]
    all_names = [name for name in all_names if name]
    if not all_names:
        raise RuntimeError("ONS IPN identity has no place name")
    unique_names = set(all_names)
    primary_names = [
        safe_text(row.get("place23nm"))
        for row in rows
        if safe_text(row.get("splitind")) == "0" and safe_text(row.get("place23nm"))
    ]
    candidates = primary_names or all_names
    counts = Counter(candidates)
    highest = max(counts.values())
    name = sorted((item for item, count in counts.items() if count == highest), key=norm)[0]
    return name, max(0, len(unique_names) - 1)


def read_ipn() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with zipfile.ZipFile(IPN_ZIP) as archive:
        raw = archive.read("IPN_GB_2024.csv")
    reader = csv.DictReader(io.StringIO(raw.decode("cp1252")))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    contexts: dict[tuple[str, str], Acc] = defaultdict(Acc)
    row_count = 0
    descriptor_rows = Counter()

    for row in reader:
        if norm(row.get("ctry23nm")) != "england":
            continue
        row_count += 1
        placeid = safe_text(row.get("placeid"))
        if not placeid:
            raise RuntimeError("ONS IPN England row missing placeid")
        groups[placeid].append(row)
        descriptor_rows[safe_text(row.get("descnm"))] += 1
        try:
            lat = float(safe_text(row.get("lat")) or "0")
            lon = float(safe_text(row.get("long")) or "0")
        except ValueError:
            continue
        if not valid_coord(lat, lon):
            continue
        for field in ("cty23cd", "cty23nm", "ctyhistnm", "ctyltnm", "rgn23cd", "rgn23nm"):
            value = norm(row.get(field))
            if value:
                contexts[(field, value)].add(lat, lon)

    places: list[dict[str, Any]] = []
    descriptor_places = Counter()
    split_groups = 0
    multi_name_groups = 0
    alternate_name_values = 0
    derived_coordinates = Counter()
    unresolved: list[dict[str, str]] = []

    for placeid, rows in groups.items():
        descs = {safe_text(row.get("descnm")) for row in rows}
        if len(descs) != 1:
            raise RuntimeError(f"ONS placeid {placeid} spans multiple descriptors: {sorted(descs)}")
        desc = next(iter(descs))
        name, alternate_count = choose_canonical_name(rows)
        if alternate_count:
            multi_name_groups += 1
            alternate_name_values += alternate_count
        if desc not in IPN_TYPE_MAP:
            raise RuntimeError(f"Unknown ONS descriptor {desc}")
        descriptor_places[desc] += 1
        if len(rows) > 1:
            split_groups += 1

        direct = Acc()
        for row in rows:
            try:
                lat = float(safe_text(row.get("lat")) or "0")
                lon = float(safe_text(row.get("long")) or "0")
            except ValueError:
                continue
            if valid_coord(lat, lon):
                direct.add(lat, lon)

        coordinate_basis = "direct"
        if direct.count:
            lat, lon = direct.value()
        else:
            keys: list[tuple[str, str]] = []
            if desc == "CTY":
                keys.extend([
                    ("cty23cd", norm(first_nonblank(rows, "cty23cd"))),
                    ("cty23nm", norm(name)),
                ])
            elif desc == "RGN":
                keys.extend([
                    ("rgn23nm", norm(name)),
                    ("rgn23cd", norm(first_nonblank(rows, "rgn23cd"))),
                ])
            elif desc == "CTYHIST":
                keys.append(("ctyhistnm", norm(name)))
            elif desc == "CTYLT":
                keys.append(("ctyltnm", norm(name)))
            found = None
            for key in keys:
                if key[1] and key in contexts and contexts[key].count:
                    found = contexts[key].value()
                    break
            if found is None:
                unresolved.append({"placeid": placeid, "descriptor": desc, "name": name})
                continue
            lat, lon = found
            coordinate_basis = "derived_context_centroid"
            derived_coordinates[desc] += 1

        places.append({
            "id": stable_uuid("ons-ipn", placeid),
            "source_key": placeid,
            "descriptor": desc,
            "type": IPN_TYPE_MAP[desc],
            "name": name,
            "local_name": name,
            "lat": lat,
            "lon": lon,
            "confidence": "high" if direct.count == 1 else "medium",
            "coordinate_basis": coordinate_basis,
            "lad": first_nonblank(rows, "lad23nm"),
            "county": first_nonblank(rows, "cty23nm"),
            "region": first_nonblank(rows, "rgn23nm"),
        })

    if unresolved:
        raise RuntimeError("Unresolved ONS coordinates: " + json.dumps(unresolved[:20], ensure_ascii=False))
    if len(places) < 70_000:
        raise RuntimeError(f"ONS canonical place count implausibly small: {len(places)}")

    return places, {
        "rows": row_count,
        "unique_places": len(places),
        "descriptor_row_counts": dict(sorted(descriptor_rows.items())),
        "descriptor_place_counts": dict(sorted(descriptor_places.items())),
        "split_identity_groups": split_groups,
        "multiple_name_identity_groups": multi_name_groups,
        "alternate_name_values": alternate_name_values,
        "derived_coordinate_counts": dict(sorted(derived_coordinates.items())),
    }


def iter_os_rows() -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(OS_ZIP) as archive:
        members = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
            and not name.endswith("/")
            and "header" not in Path(name).name.casefold()
        ]
        for member in sorted(members):
            with archive.open(member) as raw:
                reader = csv.reader(
                    io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
                )
                for values in reader:
                    if not values or safe_text(values[0]).upper() == "ID":
                        continue
                    if len(values) < len(OS_FIELDS):
                        values.extend([""] * (len(OS_FIELDS) - len(values)))
                    elif len(values) > len(OS_FIELDS):
                        values = values[:len(OS_FIELDS)]
                    yield {field: safe_text(value) for field, value in zip(OS_FIELDS, values)}


def read_os() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    records: list[dict[str, Any]] = []
    rows_scanned = 0
    skipped = Counter()
    local_types = Counter()
    seen_keys: set[str] = set()

    for row in iter_os_rows():
        rows_scanned += 1
        if norm(row.get("TYPE")) != "populatedplace" or norm(row.get("COUNTRY")) != "england":
            continue
        name = safe_text(row.get("NAME1"))
        if not name:
            skipped["missing_name"] += 1
            continue
        try:
            x = float(row["GEOMETRY_X"])
            y = float(row["GEOMETRY_Y"])
            lon, lat = transformer.transform(x, y)
        except Exception:
            skipped["invalid_coordinates"] += 1
            continue
        if not valid_coord(lat, lon):
            skipped["outside_england_bounds"] += 1
            continue
        source_key = safe_text(row.get("NAMES_URI")) or safe_text(row.get("ID"))
        if not source_key:
            skipped["missing_source_identity"] += 1
            continue
        if source_key in seen_keys:
            skipped["duplicate_source_identity"] += 1
            continue
        seen_keys.add(source_key)
        local_raw = safe_text(row.get("LOCAL_TYPE")) or "Other Settlement"
        local_types[local_raw] += 1
        mapped = OS_TYPE_MAP.get(norm(local_raw), "locality")
        alt = safe_text(row.get("NAME2"))
        records.append({
            "id": stable_uuid("os-open-names", source_key),
            "source_key": source_key,
            "type": mapped,
            "name": name,
            "local_name": alt if alt and norm(alt) != norm(name) else name,
            "lat": lat,
            "lon": lon,
            "district": safe_text(row.get("DISTRICT_BOROUGH")),
            "county": safe_text(row.get("COUNTY_UNITARY")),
            "region": safe_text(row.get("REGION")),
            "local_type": local_raw,
        })

    if skipped:
        raise RuntimeError("OS England populated-place rows skipped: " + json.dumps(dict(skipped)))
    if len(records) < 30_000:
        raise RuntimeError(f"OS England populated-place count implausibly small: {len(records)}")

    return records, {
        "rows_scanned": rows_scanned,
        "populated_places": len(records),
        "local_type_counts": dict(sorted(local_types.items())),
        "skipped": dict(skipped),
    }
