#!/usr/bin/env python3
"""OS Open Names headerless-tile adapter for the England Layer 1 builder."""
from __future__ import annotations

import csv
import io
import sys
import zipfile
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_england_layer1 as builder

FIELDS = [
    "ID",
    "NAMES_URI",
    "NAME1",
    "NAME1_LANG",
    "NAME2",
    "NAME2_LANG",
    "TYPE",
    "LOCAL_TYPE",
    "GEOMETRY_X",
    "GEOMETRY_Y",
    "MOST_DETAIL_VIEW_RES",
    "LEAST_DETAIL_VIEW_RES",
    "MBR_XMIN",
    "MBR_YMIN",
    "MBR_XMAX",
    "MBR_YMAX",
    "POSTCODE_DISTRICT",
    "POSTCODE_DISTRICT_URI",
    "POPULATED_PLACE",
    "POPULATED_PLACE_URI",
    "POPULATED_PLACE_TYPE",
    "DISTRICT_BOROUGH",
    "DISTRICT_BOROUGH_URI",
    "DISTRICT_BOROUGH_TYPE",
    "COUNTY_UNITARY",
    "COUNTY_UNITARY_URI",
    "COUNTY_UNITARY_TYPE",
    "REGION",
    "REGION_URI",
    "COUNTRY",
    "COUNTRY_URI",
    "RELATED_SPATIAL_OBJECT",
    "SAME_AS_DBPEDIA",
    "SAME_AS_GEONAMES",
]


def iter_headerless_rows() -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(builder.ZIP_PATH) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv")
            and not name.endswith("/")
            and "header" not in Path(name).name.casefold()
        ]
        if not members:
            raise RuntimeError("No OS Open Names data CSV members found")
        for member in sorted(members):
            with archive.open(member) as raw:
                text = io.TextIOWrapper(
                    raw,
                    encoding="utf-8-sig",
                    errors="replace",
                    newline="",
                )
                reader = csv.reader(text)
                for values in reader:
                    if not values:
                        continue
                    if values[0].strip().upper() == "ID":
                        continue
                    if len(values) < len(FIELDS):
                        values.extend([""] * (len(FIELDS) - len(values)))
                    elif len(values) > len(FIELDS):
                        values = values[: len(FIELDS)]
                    yield {
                        field: builder.clean(value)
                        for field, value in zip(FIELDS, values)
                    }


builder.iter_csv_rows = iter_headerless_rows
raise SystemExit(builder.main())
