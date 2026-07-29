from __future__ import annotations

import hashlib
import json
import zipfile
from collections import OrderedDict
from typing import Any

from common import OUT_DIR
from qa import qa_markdown
from validate import validate


def write_outputs(
    package: OrderedDict[str, Any],
    stats: dict[str, Any],
    checks: list[str],
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = "England_BelongWhere_Layer1_Package_v1.2.0"
    json_path = OUT_DIR / f"{base}.json"
    qa_path = OUT_DIR / f"{base}_QA.md"
    checksum_path = OUT_DIR / f"{base}_SHA256.txt"
    zip_path = OUT_DIR / f"{base}.zip"
    summary_path = OUT_DIR / "England_BelongWhere_Layer1_Summary.json"

    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(package, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    qa_path.write_text(
        qa_markdown(stats, checks, package),
        encoding="utf-8",
        newline="\n",
    )

    digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
    checksum_path.write_text(
        f"{digest}  {json_path.name}\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.write(json_path, json_path.name)
        archive.write(qa_path, qa_path.name)
        archive.write(checksum_path, checksum_path.name)

    summary = {
        **stats,
        "validation_checks": checks,
        "json_sha256": digest,
        "files": {
            "json": json_path.name,
            "qa": qa_path.name,
            "checksum": checksum_path.name,
            "zip": zip_path.name,
        },
        "file_sizes": {
            path.name: path.stat().st_size
            for path in (json_path, qa_path, checksum_path, zip_path)
        },
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    reparsed = json.loads(
        json_path.read_text(encoding="utf-8"),
        object_pairs_hook=OrderedDict,
    )
    validate(reparsed, stats)
    if hashlib.sha256(json_path.read_bytes()).hexdigest() != digest:
        raise AssertionError("Checksum self-check failed")
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise AssertionError("ZIP integrity failure")
        expected = sorted([json_path.name, qa_path.name, checksum_path.name])
        if sorted(archive.namelist()) != expected:
            raise AssertionError("ZIP content mismatch")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
