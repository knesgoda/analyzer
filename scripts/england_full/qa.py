from __future__ import annotations

from collections import OrderedDict
from typing import Any

from common import CONTRACT_ID, CONTRACT_VERSION, DASH, GENERATED_AT


def qa_markdown(
    stats: dict[str, Any],
    checks: list[str],
    package: OrderedDict[str, Any],
) -> str:
    ipn = stats["ons_ipn"]
    os_stats = stats["os_open_names"]
    merge_stats = stats["cross_source_merge"]
    lines = [
        "# England BelongWhere Layer 1 QA",
        "",
        f"Generated: {GENERATED_AT}",
        f"Contract: {CONTRACT_ID} v{CONTRACT_VERSION}",
        "",
        "## Scope",
        "",
        "This is an exhaustive named-place and administrative-geography package, not a curated relocation list. It includes every canonical England place identity in the official ONS Index of Place Names across all 14 descriptors, then uses the current July 2026 OS Open Names populated-place universe to refine locality types and add settlements that cannot be safely matched to the ONS snapshot. There is no population threshold and no hand-selected exclusion inside the declared place scope.",
        "",
        "Roads, road junctions, postcodes, buildings, rivers, landforms, and unnamed output areas are not locations in this package scope. Their exclusion is semantic, not curation.",
        "",
        "## Final parity lock",
        "",
        f"Layer 1 total: {stats['total_places']:,}",
        f"Waves 2, 3, and 4 must each contain the same {stats['total_places']:,} place_ids.",
        "",
        "## Source reconciliation",
        "",
        f"- ONS England source rows: {ipn['rows']:,}",
        f"- ONS canonical place identities: {ipn['unique_places']:,}",
        f"- ONS multi-row identities aggregated: {ipn['split_identity_groups']:,}",
        f"- OS England populated places: {os_stats['populated_places']:,}",
        f"- OS records safely matched to ONS: {merge_stats['matched_to_ons']:,}",
        f"- Unmatched OS settlements added: {merge_stats['unmatched_os_additions']:,}",
        f"- Ambiguous same-name matches retained as distinct: {merge_stats['ambiguous_same_name_matches_retained_as_distinct']:,}",
        "- England country record: 1",
        "",
        "## ONS canonical descriptors",
        "",
        "| Descriptor | Canonical places |",
        "|---|---:|",
    ]
    for key, value in ipn["descriptor_place_counts"].items():
        lines.append(f"| {key} | {value:,} |")

    lines += [
        "",
        "## Final BelongWhere place types",
        "",
        "| Type | Count |",
        "|---|---:|",
    ]
    for key, value in stats["place_type_counts"].items():
        lines.append(f"| {key} | {value:,} |")

    lines += ["", "## Validation", ""]
    lines.extend(f"- PASS: {check}" for check in checks)
    lines += ["", "## Known limitations", ""]
    lines.extend(f"- {item}" for item in package["manifest"]["known_limitations"])
    lines += [
        "",
        "## Later-wave status",
        "",
        "- destinations: 0",
        "- Layer 2: 0",
        "- Layer 3: 0",
        "- Layer 4: 0",
        "- cost of living: 0",
        "- published destinations: 0",
        "",
        "The package is valid as a Layer 1-only upload. It is not a fully live four-layer country package yet.",
        "",
    ]
    text = "\n".join(lines)
    if DASH in text:
        raise AssertionError("Em dash found in QA")
    return text
