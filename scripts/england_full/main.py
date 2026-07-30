#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifacts import write_outputs
from package_builder import build_package
from validate import validate


def main() -> int:
    package, stats = build_package()
    checks = validate(package, stats)
    write_outputs(package, stats, checks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
