from __future__ import annotations

import json
import uuid
from collections import OrderedDict
from typing import Any

from common import (
    CONTRACT_ID,
    CONTRACT_VERSION,
    DASH,
    TOP_LEVEL_KEYS,
    valid_coord,
)


def validate(package: OrderedDict[str, Any], stats: dict[str, Any]) -> list[str]:
    checks: list[str] = []
    if list(package.keys()) != TOP_LEVEL_KEYS:
        raise AssertionError("Top-level contract order mismatch")
    checks.append("Top-level key order matches the v1.2.0 template")

    manifest = package["manifest"]
    expected = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "canonical_layer3_dimension_count": 58,
        "required_layer3_score_count": 46,
        "layer3_score_scale": "0-10",
        "layer3_score_step": 0.5,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise AssertionError(f"Manifest mismatch: {key}")
    checks.append("Manifest contract identity and Layer 3 metadata are exact")

    for section, count in manifest["counts"].items():
        if len(package[section]) != count:
            raise AssertionError(f"Count mismatch for {section}")
    checks.append("Every manifest count equals its array length")

    ids = [row["place_id"] for row in package["places"]]
    if len(ids) != len(set(ids)):
        raise AssertionError("Duplicate place_id")
    for value in ids:
        uuid.UUID(value)
    checks.append("Every place_id is a unique valid UUID")

    required_keys = [
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
    for row in package["places"]:
        if list(row.keys()) != required_keys:
            raise AssertionError(f"Place row shape mismatch: {row.get('place_id')}")
        if not row["canonical_name"]:
            raise AssertionError("Blank canonical name")
        if not valid_coord(float(row["latitude"]), float(row["longitude"])):
            raise AssertionError(f"Invalid coordinate: {row['place_id']}")
        if row["country_code_alpha2"] != "GB" or row["subdivision_code"] != "GB-ENG":
            raise AssertionError("Country code mismatch")
    checks.append("Every place matches the exact template shape and England coordinate bounds")

    if stats["ons_ipn"]["unique_places"] < 70_000:
        raise AssertionError("ONS source completeness plausibility failure")
    if stats["os_open_names"]["populated_places"] < 30_000:
        raise AssertionError("OS source completeness plausibility failure")
    checks.append("Both official source-universe plausibility thresholds passed")

    for section in ("destinations", "layer2", "layer3", "layer4", "cost_of_living"):
        if package[section]:
            raise AssertionError(f"{section} must be empty in Wave 1")
    checks.append("All later-wave arrays are empty by design")

    compact = json.dumps(package, ensure_ascii=False, separators=(",", ":"))
    if DASH in compact:
        raise AssertionError("Em dash found")
    json.loads(compact, object_pairs_hook=OrderedDict)
    checks.append("JSON round-trip parse passed and contains no em dash")
    return checks
