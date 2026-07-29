from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from common import haversine_km, norm


def context_score(os_place: dict[str, Any], ipn_place: dict[str, Any]) -> int:
    score = 0
    pairs = [
        (os_place.get("district"), ipn_place.get("lad")),
        (os_place.get("county"), ipn_place.get("county")),
        (os_place.get("region"), ipn_place.get("region")),
    ]
    for left, right in pairs:
        a, b = norm(left), norm(right)
        if a and b and (a == b or a in b or b in a):
            score += 1
    return score


def merge_places(
    ipn_places: list[dict[str, Any]],
    os_places: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    index: dict[str, list[int]] = defaultdict(list)
    for idx, place in enumerate(ipn_places):
        if place["descriptor"] in {"LOC", "BUA"}:
            index[norm(place["name"])].append(idx)

    matched = 0
    matched_loc = 0
    matched_bua = 0
    ambiguous = 0
    unmatched: list[dict[str, Any]] = []
    match_distances: list[float] = []
    refined_types = Counter()

    for os_place in os_places:
        candidates = []
        for idx in index.get(norm(os_place["name"]), []):
            candidate = ipn_places[idx]
            distance = haversine_km(
                os_place["lat"], os_place["lon"], candidate["lat"], candidate["lon"]
            )
            ctx = context_score(os_place, candidate)
            if distance <= 1.5 or (ctx >= 1 and distance <= 5.0):
                priority = 0 if candidate["descriptor"] == "LOC" else 1
                candidates.append((priority, -ctx, distance, idx, ctx))

        if not candidates:
            unmatched.append(os_place)
            continue

        candidates.sort()
        top = candidates[0]
        accept = len(candidates) == 1
        if not accept:
            second = candidates[1]
            if top[0] < second[0] and top[2] <= 1.5:
                accept = True
            elif top[0] == second[0] and (
                top[4] > second[4]
                or top[2] <= 0.25
                or top[2] + 0.75 < second[2]
            ):
                accept = True

        if not accept:
            ambiguous += 1
            unmatched.append(os_place)
            continue

        _, _, distance, idx, _ = top
        target = ipn_places[idx]
        matched += 1
        match_distances.append(distance)

        if target["descriptor"] == "LOC":
            matched_loc += 1
            old_type = target["type"]
            target["type"] = os_place["type"]
            target["lat"] = os_place["lat"]
            target["lon"] = os_place["lon"]
            target["confidence"] = "high"
            target["coordinate_basis"] = "os_current_match"
            if os_place["local_name"]:
                target["local_name"] = os_place["local_name"]
            if target["type"] != old_type:
                refined_types[target["type"]] += 1
        else:
            matched_bua += 1

    merged = [*ipn_places]
    for place in unmatched:
        merged.append({
            "id": place["id"],
            "source_key": place["source_key"],
            "descriptor": "OS_POPULATED_PLACE",
            "type": place["type"],
            "name": place["name"],
            "local_name": place["local_name"],
            "lat": place["lat"],
            "lon": place["lon"],
            "confidence": "high",
            "coordinate_basis": "os_direct",
            "lad": place["district"],
            "county": place["county"],
            "region": place["region"],
        })

    return merged, {
        "matched_to_ons": matched,
        "matched_to_ons_localities": matched_loc,
        "matched_to_ons_built_up_areas": matched_bua,
        "ambiguous_same_name_matches_retained_as_distinct": ambiguous,
        "unmatched_os_additions": len(unmatched),
        "refined_ons_locality_types": dict(sorted(refined_types.items())),
        "match_distance_km_max": round(max(match_distances), 4) if match_distances else 0,
        "match_distance_km_mean": (
            round(sum(match_distances) / len(match_distances), 4)
            if match_distances else 0
        ),
    }
