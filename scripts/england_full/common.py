from __future__ import annotations

import math
import re
import unicodedata
import urllib.request
import uuid
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Any

CONTRACT_ID = "belongwhere-full-package"
CONTRACT_VERSION = "1.2.0"
GENERATED_AT = "2026-07-29T23:55:00Z"
OUT_DIR = Path("generated/england-layer1")
WORK_DIR = Path(".work/england-layer1-full")
IPN_ZIP = WORK_DIR / "IPN_GB_2024.zip"
OS_ZIP = WORK_DIR / "opname_csv_gb.zip"
IPN_URL = "https://www.arcgis.com/sharing/rest/content/items/208d9884575647c29f0dd5a1184e711a/data"
IPN_META_URL = "https://www.arcgis.com/sharing/rest/content/items/208d9884575647c29f0dd5a1184e711a/info/metadata/metadata.xml?format=default&output=html"
OS_URL = "https://api.os.uk/downloads/v1/products/OpenNames/downloads?area=GB&format=CSV&redirect"
OS_PAGE_URL = "https://osdatahub.os.uk/downloads/open/OpenNames"
NAMESPACE = uuid.UUID("e741e672-509f-5e18-a552-150adccdd73d")
DASH = "\N{EM DASH}"

TOP_LEVEL_KEYS = [
    "manifest", "sources", "places", "place_aliases", "place_hierarchy",
    "place_boundaries", "external_identifiers", "facts", "fact_sources",
    "fact_reviews", "fact_conflicts", "fact_refresh_jobs", "qa_summary",
    "destinations", "layer2", "layer3", "layer4", "cost_of_living",
]

IPN_TYPE_MAP = {
    "LOC": "locality",
    "BUA": "built_up_area",
    "CED": "electoral_division",
    "CTY": "county",
    "CTYHIST": "historic_county",
    "CTYLT": "lieutenancy_area",
    "LONB": "london_borough",
    "MD": "metropolitan_district",
    "NMD": "non_metropolitan_district",
    "NPARK": "national_park",
    "PAR": "civil_parish",
    "RGN": "region",
    "UA": "unitary_authority",
    "WD": "ward",
}

OS_TYPE_MAP = {
    "city": "city",
    "town": "town",
    "village": "village",
    "hamlet": "hamlet",
    "suburban area": "neighborhood",
    "other settlement": "locality",
}

OS_FIELDS = [
    "ID", "NAMES_URI", "NAME1", "NAME1_LANG", "NAME2", "NAME2_LANG",
    "TYPE", "LOCAL_TYPE", "GEOMETRY_X", "GEOMETRY_Y",
    "MOST_DETAIL_VIEW_RES", "LEAST_DETAIL_VIEW_RES", "MBR_XMIN", "MBR_YMIN",
    "MBR_XMAX", "MBR_YMAX", "POSTCODE_DISTRICT", "POSTCODE_DISTRICT_URI",
    "POPULATED_PLACE", "POPULATED_PLACE_URI", "POPULATED_PLACE_TYPE",
    "DISTRICT_BOROUGH", "DISTRICT_BOROUGH_URI", "DISTRICT_BOROUGH_TYPE",
    "COUNTY_UNITARY", "COUNTY_UNITARY_URI", "COUNTY_UNITARY_TYPE",
    "REGION", "REGION_URI", "COUNTRY", "COUNTRY_URI",
    "RELATED_SPATIAL_OBJECT", "SAME_AS_DBPEDIA", "SAME_AS_GEONAMES",
]


def safe_text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text.replace(DASH, "-")


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", safe_text(value).casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def stable_uuid(source: str, key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"england|{source}|{key}"))


def valid_coord(lat: float, lon: float) -> bool:
    return math.isfinite(lat) and math.isfinite(lon) and 49.5 <= lat <= 56.5 and -6.5 <= lon <= 2.5


def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


class Acc:
    __slots__ = ("lat", "lon", "count")

    def __init__(self) -> None:
        self.lat = 0.0
        self.lon = 0.0
        self.count = 0

    def add(self, lat: float, lon: float) -> None:
        self.lat += lat
        self.lon += lon
        self.count += 1

    def value(self) -> tuple[float, float]:
        if not self.count:
            raise ValueError("empty accumulator")
        return self.lat / self.count, self.lon / self.count


def download(url: str, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 1_000_000 and zipfile.is_zipfile(path):
        return "cached"
    request = urllib.request.Request(url, headers={"User-Agent": "BelongWhere-England-Layer1/1.2.0"})
    with urllib.request.urlopen(request, timeout=240) as response, path.open("wb") as target:
        final_url = response.geturl()
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            target.write(block)
    if not zipfile.is_zipfile(path):
        raise RuntimeError(f"Not a ZIP archive: {path}")
    return final_url


def first_nonblank(rows: list[dict[str, str]], key: str) -> str:
    for row in rows:
        value = safe_text(row.get(key))
        if value:
            return value
    return ""


def place_json(place_id: str, place_type: str, name: str, local_name: str,
               lat: float, lon: float, confidence: str) -> OrderedDict[str, Any]:
    return OrderedDict([
        ("place_id", place_id),
        ("place_type", safe_text(place_type)),
        ("canonical_name", safe_text(name)),
        ("local_name", safe_text(local_name) or safe_text(name)),
        ("country_code_alpha2", "GB"),
        ("country_code_alpha3", "GBR"),
        ("subdivision_code", "GB-ENG"),
        ("latitude", round(lat, 7)),
        ("longitude", round(lon, 7)),
        ("record_status", "active"),
        ("confidence", confidence),
    ])
