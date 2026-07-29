# England BelongWhere Layer 1 QA

Generated: 2026-07-29T23:05:00Z
Contract: belongwhere-full-package v1.2.0

## Scope decision

This is not a curated destination list. It includes every current OS Open Names record classified as a populated place in England, with no population cutoff, no relocation-market filter, and no hand-selected exclusion. The six observed settlement classes are retained through BelongWhere place types. The package also includes the unique region, county or unitary, and district or borough context names referenced by those England settlement records, plus one England country record.

OS Open Names also contains roads, postcodes, named buildings, hydrography, landforms, and other named features. Those are not populated places and are intentionally outside the BelongWhere place universe for this wave. This is a semantic scope boundary, not curation.

## Counts

- Source rows scanned: 3,025,714
- OS England populated places: 33,387
- Referenced administrative context places: 327
- England country record: 1
- Total Layer 1 places: 33,715
- Alternate NAME2 values preserved in local_name: 26
- Duplicate source rows skipped by deterministic identity: 0
- Same-name and same-type groups retained because distinct places may share names: 1,958

### BelongWhere place types

| Place type | Count |
|---|---:|
| city | 56 |
| country | 1 |
| county | 85 |
| district | 233 |
| hamlet | 9,884 |
| locality | 1,568 |
| neighborhood | 8,579 |
| region | 9 |
| town | 1,001 |
| village | 12,299 |

### Source settlement local types

| OS local type | Count |
|---|---:|
| City | 56 |
| Hamlet | 9,884 |
| Other Settlement | 1,568 |
| Suburban Area | 8,579 |
| Town | 1,001 |
| Village | 12,299 |

### Skipped England populated-place rows

| Reason | Count |
|---|---:|
| None | 0 |

## Layer parity lock

Waves 2, 3, and 4 must each cover the same 33,715 place_ids. No later wave may reduce this to a curated list. A count change requires a replacement Layer 1 package, a place-id migration record, and explicit QA documentation.

## Validation results

- PASS: Top-level key order matches the template
- PASS: Manifest identity matches BelongWhere v1.2.0
- PASS: Every manifest count equals its array length
- PASS: Every place_id is a unique valid UUID
- PASS: Every place matches the exact template shape and coordinate rules
- PASS: Later-wave arrays are empty by design
- PASS: Non-curated source count plausibility threshold passed
- PASS: JSON round-trip parse passed and contains no em dash

## Source

- Publisher: Ordnance Survey
- Dataset: OS Open Names
- Release: 2026-07
- Dataset page: https://www.data.gov.uk/dataset/1c58a0c6-43e2-4e36-9b17-239f0aebf4e5/os-open-names
- Stable download endpoint used by the build: https://api.os.uk/downloads/v1/products/OpenNames/downloads?area=GB&format=CSV&redirect
- Coordinate conversion: EPSG:27700 British National Grid to EPSG:4326 WGS84 using pyproj

## Known limitations

- This is a Layer 1-only wave. destinations, Layer 2, Layer 3, Layer 4, and cost-of-living arrays are intentionally empty.
- The exhaustive named-place scope is the complete July 2026 OS Open Names England populated-place universe plus the administrative context names referenced by those rows. Roads, postcodes, named buildings, landforms, and other non-settlement features are excluded because they are not populated places.
- Administrative coordinates are locally computed mean centroids of the official settlement points that reference each region, county or unitary, and district or borough. They are not boundary centroids.
- The current v1.2.0 template does not define row shapes for aliases, hierarchy, external identifiers, or geometry. Those sections remain empty to avoid adding unsupported fields. NAME2 is preserved in places.local_name when present, and the stable OS source identity is used to derive each deterministic place_id.
- Later waves must preserve this exact place_id set and total count. No later layer may curate, drop, merge, or silently add places without first issuing a replacement Layer 1 package and a documented migration.

## Later-layer status

- destinations: 0, intentionally deferred
- Layer 2: 0, intentionally deferred
- Layer 3: 0, intentionally deferred
- Layer 4: 0, intentionally deferred
- cost of living: 0, intentionally deferred
- published destinations: 0

The package is valid as a Layer 1-only upload under the v1.2.0 contract. It is not a fully live four-layer country package yet.
