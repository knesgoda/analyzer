# England BelongWhere Layer 1 QA

Generated: 2026-07-29T23:55:00Z
Contract: belongwhere-full-package v1.2.0

## Scope

This is an exhaustive named-place and administrative-geography package, not a curated relocation list. It includes every canonical England place identity in the official ONS Index of Place Names across all 14 descriptors, then uses the current July 2026 OS Open Names populated-place universe to refine locality types and add settlements that cannot be safely matched to the ONS snapshot. There is no population threshold and no hand-selected exclusion inside the declared place scope.

Roads, road junctions, postcodes, buildings, rivers, landforms, and unnamed output areas are not locations in this package scope. Their exclusion is semantic, not curation.

## Final parity lock

Layer 1 total: 78,978
Waves 2, 3, and 4 must each contain the same 78,978 place_ids.

## Source reconciliation

- ONS England source rows: 86,267
- ONS canonical place identities: 74,570
- ONS multi-row identities aggregated: 9,662
- OS England populated places: 33,387
- OS records safely matched to ONS: 28,980
- Unmatched OS settlements added: 4,407
- Ambiguous same-name matches retained as distinct: 54
- England country record: 1

## ONS canonical descriptors

| Descriptor | Canonical places |
|---|---:|
| BUA | 8,477 |
| CED | 1,475 |
| CTY | 27 |
| CTYHIST | 39 |
| CTYLT | 48 |
| LOC | 45,543 |
| LONB | 33 |
| MD | 36 |
| NMD | 164 |
| NPARK | 10 |
| PAR | 11,586 |
| RGN | 9 |
| UA | 64 |
| WD | 7,059 |

## Final BelongWhere place types

| Type | Count |
|---|---:|
| built_up_area | 8,477 |
| city | 45 |
| civil_parish | 11,586 |
| country | 1 |
| county | 27 |
| electoral_division | 1,475 |
| hamlet | 9,859 |
| historic_county | 39 |
| lieutenancy_area | 48 |
| locality | 19,060 |
| london_borough | 33 |
| metropolitan_district | 36 |
| national_park | 10 |
| neighborhood | 8,566 |
| non_metropolitan_district | 164 |
| region | 9 |
| town | 885 |
| unitary_authority | 64 |
| village | 11,535 |
| ward | 7,059 |

## Validation

- PASS: Top-level key order matches the v1.2.0 template
- PASS: Manifest contract identity and Layer 3 metadata are exact
- PASS: Every manifest count equals its array length
- PASS: Every place_id is a unique valid UUID
- PASS: Every place matches the exact template shape and England coordinate bounds
- PASS: Both official source-universe plausibility thresholds passed
- PASS: All later-wave arrays are empty by design
- PASS: JSON round-trip parse passed and contains no em dash

## Known limitations

- This is a Layer 1-only wave. destinations, Layer 2, Layer 3, Layer 4, and cost-of-living arrays are intentionally empty.
- The ONS Index of Place Names is the broad official identity spine and reflects geography as at December 2023, published July 2024. The July 2026 OS Open Names release supplements it with current populated places and more specific settlement types.
- All 14 England ONS IPN descriptors are included. Roads, road junctions, postcodes, named buildings, hydrography, landforms, and unnamed statistical output areas are excluded because they are not named populated or administrative places in this package scope.
- ONS split component rows are aggregated by canonical placeid. Components are not counted as separate locations. Distinct same-name places and distinct geography types are retained.
- The current v1.2.0 template does not define row shapes for aliases, hierarchy, external identifiers, or boundaries. Those sections remain empty to avoid unsupported fields. Deterministic place_ids are derived from official ONS placeid or OS Names URI identities.
- Later waves must preserve this exact 78,978-place place_id set. No later layer may curate, drop, merge, or silently add places without a replacement Layer 1 package and documented migration.

## Later-wave status

- destinations: 0
- Layer 2: 0
- Layer 3: 0
- Layer 4: 0
- cost of living: 0
- published destinations: 0

The package is valid as a Layer 1-only upload. It is not a fully live four-layer country package yet.
