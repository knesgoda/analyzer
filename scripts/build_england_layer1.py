#!/usr/bin/env python3
"""Build the complete England Layer 1 BelongWhere package from OS Open Names.

Scope is source-driven, not curated:
- every OS Open Names record whose TYPE is populatedPlace and COUNTRY is England
- unique England region, county or unitary, and district or borough context records
  referenced by those populated places

The output preserves the BelongWhere v1.2.0 top-level contract and leaves later
layers empty for subsequent waves.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import urllib.request
import uuid
import zipfile
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, Iterable

from pyproj import Transformer

CONTRACT_ID = "belongwhere-full-package"
CONTRACT_VERSION = "1.2.0"
GENERATED_AT = "2026-07-29T23:05:00Z"
SOURCE_VINTAGE = "2026-07"
SOURCE_DOWNLOAD_URL = (
    "https://api.os.uk/downloads/v1/products/OpenNames/downloads"
    "?area=GB&format=CSV&redirect"
)
SOURCE_PAGE_URL = "https://www.data.gov.uk/dataset/1c58a0c6-43e2-4e36-9b17-239f0aebf4e5/os-open-names"
OUT_DIR = Path(os.environ.get("OUT_DIR", "generated/england-layer1"))
WORK_DIR = Path(os.environ.get("WORK_DIR", ".work/england-layer1"))
ZIP_PATH = WORK_DIR / "opname_csv_gb.zip"
NAMESPACE = uuid.UUID("e741e672-509f-5e18-a552-150adccdd73d")

TOP_LEVEL_KEYS = [
    "manifest",
    "sources",
    "places",
    "place_aliases",
    "place_hierarchy",
    "place_boundaries",
    "external_identifiers",
    "facts",
    "fact_sources",
    "fact_reviews",
    "fact_conflicts",
    "fact_refresh_jobs",
    "qa_summary",
    "destinations",
    "layer2",
    "layer3",
    "layer4",
    "cost_of_living",
]

LOCAL_TYPE_MAP = {
    "city": "city",
    "town": "town",
    "village": "village",
    "hamlet": "hamlet",
    "suburban area": "neighborhood",
    "other settlement": "locality",
}

DASH = "\N{EM DASH}"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", clean(value)).casefold()


def stable_uuid(kind: str, source_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"england|{kind}|{source_key}"))


def float_or_none(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def download_source() -> str:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists() and ZIP_PATH.stat().st_size > 1_000_000:
        return "cached"
    request = urllib.request.Request(
        SOURCE_DOWNLOAD_URL,
        headers={"User-Agent": "BelongWhere-England-Layer1/1.2.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response, ZIP_PATH.open("wb") as target:
        final_url = response.geturl()
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)
    if not zipfile.is_zipfile(ZIP_PATH):
        raise RuntimeError(f"Downloaded source is not a ZIP archive: {ZIP_PATH}")
    return final_url


def iter_csv_rows() -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(ZIP_PATH) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv") and not name.endswith("/")
        ]
        if not members:
            raise RuntimeError("No CSV members found in OS Open Names archive")
        for member in sorted(members):
            with archive.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
                reader = csv.DictReader(text)
                if not reader.fieldnames:
                    continue
                for original in reader:
                    yield {clean(k).upper(): clean(v) for k, v in original.items() if k is not None}


class CentroidAccumulator:
    def __init__(self) -> None:
        self.sum_lat = 0.0
        self.sum_lon = 0.0
        self.count = 0

    def add(self, lat: float, lon: float) -> None:
        self.sum_lat += lat
        self.sum_lon += lon
        self.count += 1

    def value(self) -> tuple[float, float]:
        if self.count == 0:
            raise ValueError("Cannot compute centroid without points")
        return self.sum_lat / self.count, self.sum_lon / self.count


def admin_key(level: str, uri: str, name: str, parents: tuple[str, ...]) -> str:
    if uri:
        return f"uri:{uri}"
    return "name:" + "|".join([level, *parents, name]).casefold()


def place_record(
    *,
    place_id: str,
    place_type: str,
    canonical_name: str,
    local_name: str,
    latitude: float,
    longitude: float,
    confidence: str,
) -> OrderedDict[str, Any]:
    return OrderedDict(
        [
            ("place_id", place_id),
            ("place_type", place_type),
            ("canonical_name", canonical_name),
            ("local_name", local_name),
            ("country_code_alpha2", "GB"),
            ("country_code_alpha3", "GBR"),
            ("subdivision_code", "GB-ENG"),
            ("latitude", round(latitude, 7)),
            ("longitude", round(longitude, 7)),
            ("record_status", "active"),
            ("confidence", confidence),
        ]
    )


def build() -> tuple[OrderedDict[str, Any], dict[str, Any]]:
    transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    settlements: dict[str, OrderedDict[str, Any]] = {}
    local_type_counts: Counter[str] = Counter()
    skipped = Counter()
    duplicate_source_rows = 0
    alternate_name_count = 0
    rows_scanned = 0
    admins: dict[str, dict[str, Any]] = {}

    for row in iter_csv_rows():
        rows_scanned += 1
        if normalized(row.get("TYPE")) != "populatedplace":
            continue
        if normalized(row.get("COUNTRY")) != "england":
            continue

        name = clean(row.get("NAME1"))
        if not name:
            skipped["missing_name"] += 1
            continue

        x = float_or_none(row.get("GEOMETRY_X"))
        y = float_or_none(row.get("GEOMETRY_Y"))
        if x is None or y is None:
            skipped["missing_coordinates"] += 1
            continue
        try:
            lon, lat = transformer.transform(x, y)
        except Exception:
            skipped["coordinate_transform_error"] += 1
            continue
        if not (-6.5 <= lon <= 2.5 and 49.5 <= lat <= 56.5):
            skipped["outside_england_sanity_bounds"] += 1
            continue

        local_type_raw = clean(row.get("LOCAL_TYPE")) or "Other Settlement"
        local_type = normalized(local_type_raw)
        mapped_type = LOCAL_TYPE_MAP.get(local_type)
        if mapped_type is None:
            mapped_type = re.sub(r"[^a-z0-9]+", "_", local_type).strip("_") or "locality"
        local_type_counts[local_type_raw] += 1

        names_uri = clean(row.get("NAMES_URI"))
        source_id = clean(row.get("ID"))
        source_key = names_uri or source_id
        if not source_key:
            source_key = "fallback:" + "|".join(
                [name, local_type_raw, f"{x:.3f}", f"{y:.3f}"]
            )
        pid = stable_uuid("os-open-names", source_key)
        if pid in settlements:
            duplicate_source_rows += 1
            continue

        alt_name = clean(row.get("NAME2"))
        if alt_name and normalized(alt_name) != normalized(name):
            alternate_name_count += 1
        local_name = alt_name or name
        settlements[pid] = place_record(
            place_id=pid,
            place_type=mapped_type,
            canonical_name=name,
            local_name=local_name,
            latitude=lat,
            longitude=lon,
            confidence="high",
        )

        region = clean(row.get("REGION"))
        region_uri = clean(row.get("REGION_URI"))
        county = clean(row.get("COUNTY_UNITARY"))
        county_uri = clean(row.get("COUNTY_UNITARY_URI"))
        county_type = clean(row.get("COUNTY_UNITARY_TYPE")) or "county_or_unitary"
        district = clean(row.get("DISTRICT_BOROUGH"))
        district_uri = clean(row.get("DISTRICT_BOROUGH_URI"))
        district_type = clean(row.get("DISTRICT_BOROUGH_TYPE")) or "district_or_borough"

        context_specs = []
        if region:
            context_specs.append(("region", region, region_uri, tuple()))
        if county:
            context_specs.append(("county_or_unitary", county, county_uri, (region,)))
        if district:
            context_specs.append(("district_or_borough", district, district_uri, (region, county)))

        for level, admin_name, admin_uri, parents in context_specs:
            key = admin_key(level, admin_uri, admin_name, parents)
            if key not in admins:
                if level == "region":
                    place_type = "region"
                    source_type = "Region"
                elif level == "county_or_unitary":
                    place_type = "county"
                    source_type = county_type
                else:
                    place_type = "district"
                    source_type = district_type
                admins[key] = {
                    "level": level,
                    "name": admin_name,
                    "uri": admin_uri,
                    "parents": parents,
                    "place_type": place_type,
                    "source_type": source_type,
                    "centroid": CentroidAccumulator(),
                }
            admins[key]["centroid"].add(lat, lon)

    if not settlements:
        raise RuntimeError("No England populated-place records were extracted")

    country_centroid = CentroidAccumulator()
    for place in settlements.values():
        country_centroid.add(place["latitude"], place["longitude"])
    england_lat, england_lon = country_centroid.value()
    country_place = place_record(
        place_id=stable_uuid("country", "England|GB-ENG"),
        place_type="country",
        canonical_name="England",
        local_name="England",
        latitude=england_lat,
        longitude=england_lon,
        confidence="medium",
    )

    admin_places: list[OrderedDict[str, Any]] = []
    admin_type_counts: Counter[str] = Counter()
    for key, data in sorted(
        admins.items(),
        key=lambda item: (item[1]["level"], item[1]["name"].casefold(), item[0]),
    ):
        lat, lon = data["centroid"].value()
        source_key = data["uri"] or key
        admin_places.append(
            place_record(
                place_id=stable_uuid(data["level"], source_key),
                place_type=data["place_type"],
                canonical_name=data["name"],
                local_name=data["name"],
                latitude=lat,
                longitude=lon,
                confidence="medium",
            )
        )
        admin_type_counts[data["place_type"]] += 1

    settlement_places = sorted(
        settlements.values(),
        key=lambda p: (p["place_type"], p["canonical_name"].casefold(), p["place_id"]),
    )
    places = [country_place, *admin_places, *settlement_places]

    place_type_counts = Counter(p["place_type"] for p in places)
    name_type_counts = Counter(
        (normalized(p["canonical_name"]), p["place_type"]) for p in places
    )
    duplicate_name_type_groups = sum(1 for count in name_type_counts.values() if count > 1)

    source = OrderedDict(
        [
            ("source_id", "src_os_open_names_2026_07"),
            ("title", "OS Open Names July 2026"),
            ("publisher", "Ordnance Survey"),
            ("source_type", "government"),
            ("source_tier", "primary"),
            ("vintage_or_date", "2026-07-01"),
            ("url", SOURCE_PAGE_URL),
            ("use_status", "approved"),
        ]
    )

    count_template = OrderedDict(
        [
            ("places", len(places)),
            ("place_aliases", 0),
            ("place_hierarchy", 0),
            ("place_boundaries", 0),
            ("external_identifiers", 0),
            ("facts", 0),
            ("fact_sources", 0),
            ("fact_reviews", 0),
            ("fact_conflicts", 0),
            ("fact_refresh_jobs", 0),
            ("sources", 1),
            ("qa_summary", 1),
            ("destinations", 0),
            ("layer2", 0),
            ("layer3", 0),
            ("layer4", 0),
            ("cost_of_living", 0),
        ]
    )

    limitations = [
        "This is a Layer 1-only wave. destinations, Layer 2, Layer 3, Layer 4, and cost-of-living arrays are intentionally empty.",
        "The exhaustive named-place scope is the complete July 2026 OS Open Names England populated-place universe plus the administrative context names referenced by those rows. Roads, postcodes, named buildings, landforms, and other non-settlement features are excluded because they are not populated places.",
        "Administrative coordinates are locally computed mean centroids of the official settlement points that reference each region, county or unitary, and district or borough. They are not boundary centroids.",
        "The current v1.2.0 template does not define row shapes for aliases, hierarchy, external identifiers, or geometry. Those sections remain empty to avoid adding unsupported fields. NAME2 is preserved in places.local_name when present, and the stable OS source identity is used to derive each deterministic place_id.",
        "Later waves must preserve this exact place_id set and total count. No later layer may curate, drop, merge, or silently add places without first issuing a replacement Layer 1 package and a documented migration.",
    ]

    quality_gates = [
        {"gate": "source_scope", "status": "passed", "details": "All OS Open Names England populated-place rows were evaluated without a population threshold."},
        {"gate": "json_parse", "status": "passed", "details": "The completed package was parsed after serialization."},
        {"gate": "top_level_contract", "status": "passed", "details": "Top-level sections and order match BelongWhere v1.2.0."},
        {"gate": "place_id_uniqueness", "status": "passed", "details": "Every place_id is a unique deterministic UUID."},
        {"gate": "coordinate_validity", "status": "passed", "details": "All emitted coordinates are finite WGS84 values within England sanity bounds."},
        {"gate": "wave_parity_lock", "status": "passed", "details": f"Future Waves 2, 3, and 4 are required to preserve all {len(places):,} Layer 1 place_ids."},
    ]

    manifest = OrderedDict(
        [
            ("contract_id", CONTRACT_ID),
            ("contract_version", CONTRACT_VERSION),
            ("canonical_layer3_dimension_count", 58),
            ("required_layer3_score_count", 46),
            ("layer3_score_scale", "0-10"),
            ("layer3_score_step", 0.5),
            ("package", "BelongWhere England Full Package"),
            ("version", CONTRACT_VERSION),
            ("generated_at", GENERATED_AT),
            ("counts", count_template),
            ("quality_gates", quality_gates),
            ("known_limitations", limitations),
        ]
    )

    qa_note = (
        f"England Layer 1 complete source-universe extraction. "
        f"Emitted {len(places):,} places: {len(settlement_places):,} OS populated places, "
        f"{len(admin_places):,} referenced administrative contexts, and 1 England country record. "
        f"Later layer arrays are intentionally empty in this wave."
    )

    package: OrderedDict[str, Any] = OrderedDict(
        [
            ("manifest", manifest),
            ("sources", [source]),
            ("places", places),
            ("place_aliases", []),
            ("place_hierarchy", []),
            ("place_boundaries", []),
            ("external_identifiers", []),
            ("facts", []),
            ("fact_sources", []),
            ("fact_reviews", []),
            ("fact_conflicts", []),
            ("fact_refresh_jobs", []),
            ("qa_summary", [{"generated_at": GENERATED_AT, "notes": qa_note}]),
            ("destinations", []),
            ("layer2", []),
            ("layer3", []),
            ("layer4", []),
            ("cost_of_living", []),
        ]
    )

    stats = {
        "rows_scanned": rows_scanned,
        "source_populated_places": len(settlement_places),
        "administrative_context_places": len(admin_places),
        "country_records": 1,
        "total_places": len(places),
        "place_type_counts": dict(sorted(place_type_counts.items())),
        "source_local_type_counts": dict(sorted(local_type_counts.items())),
        "admin_type_counts": dict(sorted(admin_type_counts.items())),
        "alternate_name_count": alternate_name_count,
        "duplicate_source_rows_skipped": duplicate_source_rows,
        "skipped": dict(sorted(skipped.items())),
        "duplicate_name_type_groups_retained": duplicate_name_type_groups,
        "source_download_url": SOURCE_DOWNLOAD_URL,
        "source_page_url": SOURCE_PAGE_URL,
        "source_vintage": SOURCE_VINTAGE,
    }
    return package, stats


def validate(package: OrderedDict[str, Any], stats: dict[str, Any]) -> list[str]:
    checks: list[str] = []
    if list(package.keys()) != TOP_LEVEL_KEYS:
        raise AssertionError("Top-level keys or order do not match the contract")
    checks.append("Top-level key order matches the template")

    manifest = package["manifest"]
    required_manifest = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "canonical_layer3_dimension_count": 58,
        "required_layer3_score_count": 46,
        "layer3_score_scale": "0-10",
        "layer3_score_step": 0.5,
    }
    for key, expected in required_manifest.items():
        if manifest.get(key) != expected:
            raise AssertionError(f"Manifest {key} mismatch")
    checks.append("Manifest identity matches BelongWhere v1.2.0")

    for section, expected in manifest["counts"].items():
        if len(package[section]) != expected:
            raise AssertionError(
                f"Manifest count mismatch for {section}: {expected} vs {len(package[section])}"
            )
    checks.append("Every manifest count equals its array length")

    places = package["places"]
    ids = [p["place_id"] for p in places]
    if len(ids) != len(set(ids)):
        raise AssertionError("Duplicate place_id detected")
    for pid in ids:
        uuid.UUID(pid)
    checks.append("Every place_id is a unique valid UUID")

    required_place_keys = [
        "place_id",
        "place_type",
        "canonical_name",
        "local_name",
        "country_code_alpha2",
        "country_code_alpha3",
        "subdivision_code",
        "latitude",
        "longitude",
        "record_status",
        "confidence",
    ]
    for place in places:
        if list(place.keys()) != required_place_keys:
            raise AssertionError(f"Place shape mismatch for {place.get('place_id')}")
        if not place["canonical_name"].strip():
            raise AssertionError("Blank canonical name")
        lat = place["latitude"]
        lon = place["longitude"]
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise AssertionError("Non-numeric coordinate")
        if not (49.5 <= lat <= 56.5 and -6.5 <= lon <= 2.5):
            raise AssertionError(f"Coordinate outside England bounds: {lat}, {lon}")
        if place["country_code_alpha2"] != "GB" or place["subdivision_code"] != "GB-ENG":
            raise AssertionError("Incorrect country or subdivision code")
    checks.append("Every place matches the exact template shape and coordinate rules")

    for section in ["destinations", "layer2", "layer3", "layer4", "cost_of_living"]:
        if package[section]:
            raise AssertionError(f"{section} must be empty in Layer 1-only output")
    checks.append("Later-wave arrays are empty by design")

    if stats["source_populated_places"] <= 20_000:
        raise AssertionError("Extracted populated-place count is implausibly small")
    checks.append("Non-curated source count plausibility threshold passed")

    serialized = json.dumps(package, ensure_ascii=False, separators=(",", ":"))
    if DASH in serialized:
        raise AssertionError("Em dash found in JSON")
    json.loads(serialized, object_pairs_hook=OrderedDict)
    checks.append("JSON round-trip parse passed and contains no em dash")
    return checks


def render_qa(stats: dict[str, Any], checks: list[str], package: OrderedDict[str, Any]) -> str:
    def table_rows(mapping: dict[str, Any]) -> str:
        return "\n".join(f"| {key} | {value:,} |" for key, value in mapping.items())

    manifest = package["manifest"]
    lines = [
        "# England BelongWhere Layer 1 QA",
        "",
        f"Generated: {GENERATED_AT}",
        f"Contract: {CONTRACT_ID} v{CONTRACT_VERSION}",
        "",
        "## Scope decision",
        "",
        "This is not a curated destination list. It includes every current OS Open Names record classified as a populated place in England, with no population cutoff, no relocation-market filter, and no hand-selected exclusion. The six observed settlement classes are retained through BelongWhere place types. The package also includes the unique region, county or unitary, and district or borough context names referenced by those England settlement records, plus one England country record.",
        "",
        "OS Open Names also contains roads, postcodes, named buildings, hydrography, landforms, and other named features. Those are not populated places and are intentionally outside the BelongWhere place universe for this wave. This is a semantic scope boundary, not curation.",
        "",
        "## Counts",
        "",
        f"- Source rows scanned: {stats['rows_scanned']:,}",
        f"- OS England populated places: {stats['source_populated_places']:,}",
        f"- Referenced administrative context places: {stats['administrative_context_places']:,}",
        f"- England country record: {stats['country_records']:,}",
        f"- Total Layer 1 places: {stats['total_places']:,}",
        f"- Alternate NAME2 values preserved in local_name: {stats['alternate_name_count']:,}",
        f"- Duplicate source rows skipped by deterministic identity: {stats['duplicate_source_rows_skipped']:,}",
        f"- Same-name and same-type groups retained because distinct places may share names: {stats['duplicate_name_type_groups_retained']:,}",
        "",
        "### BelongWhere place types",
        "",
        "| Place type | Count |",
        "|---|---:|",
        table_rows(stats["place_type_counts"]),
        "",
        "### Source settlement local types",
        "",
        "| OS local type | Count |",
        "|---|---:|",
        table_rows(stats["source_local_type_counts"]),
        "",
        "### Skipped England populated-place rows",
        "",
        "| Reason | Count |",
        "|---|---:|",
        table_rows(stats["skipped"]) if stats["skipped"] else "| None | 0 |",
        "",
        "## Layer parity lock",
        "",
        f"Waves 2, 3, and 4 must each cover the same {stats['total_places']:,} place_ids. No later wave may reduce this to a curated list. A count change requires a replacement Layer 1 package, a place-id migration record, and explicit QA documentation.",
        "",
        "## Validation results",
        "",
    ]
    lines.extend(f"- PASS: {check}" for check in checks)
    lines.extend(
        [
            "",
            "## Source",
            "",
            "- Publisher: Ordnance Survey",
            "- Dataset: OS Open Names",
            f"- Release: {SOURCE_VINTAGE}",
            f"- Dataset page: {SOURCE_PAGE_URL}",
            f"- Stable download endpoint used by the build: {SOURCE_DOWNLOAD_URL}",
            "- Coordinate conversion: EPSG:27700 British National Grid to EPSG:4326 WGS84 using pyproj",
            "",
            "## Known limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in manifest["known_limitations"])
    lines.extend(
        [
            "",
            "## Later-layer status",
            "",
            "- destinations: 0, intentionally deferred",
            "- Layer 2: 0, intentionally deferred",
            "- Layer 3: 0, intentionally deferred",
            "- Layer 4: 0, intentionally deferred",
            "- cost of living: 0, intentionally deferred",
            "- published destinations: 0",
            "",
            "The package is valid as a Layer 1-only upload under the v1.2.0 contract. It is not a fully live four-layer country package yet.",
            "",
        ]
    )
    qa = "\n".join(lines)
    if DASH in qa:
        raise AssertionError("Em dash found in QA report")
    return qa


def write_outputs(package: OrderedDict[str, Any], stats: dict[str, Any], checks: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_name = "England_BelongWhere_Layer1_Package_v1.2.0.json"
    qa_name = "England_BelongWhere_Layer1_Package_v1.2.0_QA.md"
    checksum_name = "England_BelongWhere_Layer1_Package_v1.2.0_SHA256.txt"
    zip_name = "England_BelongWhere_Layer1_Package_v1.2.0.zip"

    json_path = OUT_DIR / json_name
    qa_path = OUT_DIR / qa_name
    checksum_path = OUT_DIR / checksum_name
    zip_path = OUT_DIR / zip_name
    summary_path = OUT_DIR / "England_BelongWhere_Layer1_Summary.json"

    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(package, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    qa_path.write_text(render_qa(stats, checks, package), encoding="utf-8", newline="\n")

    digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
    checksum_path.write_text(f"{digest}  {json_name}\n", encoding="utf-8")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(json_path, arcname=json_name)
        archive.write(qa_path, arcname=qa_name)
        archive.write(checksum_path, arcname=checksum_name)

    summary = {
        **stats,
        "validation_checks": checks,
        "json_sha256": digest,
        "files": {
            "json": json_name,
            "qa": qa_name,
            "checksum": checksum_name,
            "zip": zip_name,
        },
        "file_sizes": {
            json_name: json_path.stat().st_size,
            qa_name: qa_path.stat().st_size,
            checksum_name: checksum_path.stat().st_size,
            zip_name: zip_path.stat().st_size,
        },
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    reparsed = json.loads(json_path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    validate(reparsed, stats)
    expected = checksum_path.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(json_path.read_bytes()).hexdigest()
    if expected != actual:
        raise AssertionError("Checksum self-check failed")
    with zipfile.ZipFile(zip_path) as archive:
        if sorted(archive.namelist()) != sorted([json_name, qa_name, checksum_name]):
            raise AssertionError("ZIP contents mismatch")
        if archive.testzip() is not None:
            raise AssertionError("ZIP integrity check failed")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    final_url = download_source()
    print(f"Source ready: {final_url}", file=sys.stderr)
    package, stats = build()
    checks = validate(package, stats)
    write_outputs(package, stats, checks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
