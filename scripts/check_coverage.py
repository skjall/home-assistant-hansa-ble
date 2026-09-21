#!/usr/bin/env python3
"""Hold each module to the coverage its tier demands.

pytest already fails below 95% overall. This adds the per-module floors that
a single number hides: a config flow at 88% still passes a 95% average, and
the Bronze rule asks for all of it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Rule config-flow-test-coverage: "100% test coverage for the config flow".
FLOORS = {
    "custom_components/hansa_ble/config_flow.py": 100.0,
    "custom_components/hansa_ble/coordinator.py": 95.0,
}
# The wire protocol moved to the hansa_ble_protocol package and is covered by
# that package's own tests, which the CI runs in a job of its own.
OVERALL = 95.0


def main() -> int:
    report = ROOT / ".artefakte" / "coverage.json"
    if not report.exists():
        print("coverage.json is missing - run the tests first.")
        return 1

    data = json.loads(report.read_text(encoding="utf-8"))
    files = data["files"]
    problems: list[str] = []

    for path, floor in FLOORS.items():
        entry = files.get(path)
        if entry is None:
            problems.append(f"{path}: not covered at all - was it renamed?")
            continue
        actual = entry["summary"]["percent_covered"]
        if actual + 1e-9 < floor:
            missing = entry["missing_lines"]
            problems.append(
                f"{path}: {actual:.1f}% < {floor:.0f}% "
                f"(uncovered lines: {', '.join(map(str, missing[:12]))})"
            )

    total = data["totals"]["percent_covered"]
    if total + 1e-9 < OVERALL:
        problems.append(f"overall: {total:.1f}% < {OVERALL:.0f}%")

    if problems:
        print("Coverage is below what the claimed tier requires\n")
        for line in problems:
            print(f"  FAIL  {line}")
        return 1

    print(f"Coverage: {total:.1f}% overall, every module above its floor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
