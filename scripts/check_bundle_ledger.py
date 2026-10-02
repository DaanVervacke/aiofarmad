"""Fail when the contract ledger no longer covers the captured app bundle."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "captures" / "farmad_main_2ba421e258d1f7c6.js"
CONTRACT = REPO / "tests" / "fixtures" / "farmad_app_contract.json"

PATH_RE = re.compile(r'this\.baseUrl\+"(/[a-zA-Z0-9/_{}.$-]+)')


def bundle_paths() -> set[str]:
    """Return every api path the bundle's generated clients can build."""
    return set(PATH_RE.findall(BUNDLE.read_text(encoding="utf-8")))


def ledger() -> Any:
    """Return the pinned ledger section of the contract fixture."""
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return data["ledger"]


def main() -> int:
    """Compare the bundle path set against the ledger and report every drift."""
    if not BUNDLE.is_file():
        print("skipped: no captured bundle under captures/")
        return 0
    pinned = ledger()
    rows = pinned["rows"]
    row_paths = {row["path"] for row in rows}
    failures: list[str] = []
    missing = sorted(bundle_paths() - row_paths)
    stale = sorted(row_paths - bundle_paths())
    if missing:
        failures.append(f"{len(missing)} bundle paths missing from the ledger: {missing[:8]}")
    if stale:
        failures.append(f"{len(stale)} ledger paths absent from the bundle: {stale[:8]}")
    if len(rows) != pinned["pathCount"]:
        failures.append(f"pathCount {pinned['pathCount']} does not match {len(rows)} rows")
    if failures:
        for failure in failures:
            print(f"ledger drift: {failure}")
        return 1
    implemented = sum(1 for row in rows if row["status"] == "implemented")
    print(f"no drift: {len(rows)} bundle paths classified, {implemented} implemented")
    return 0


if __name__ == "__main__":
    sys.exit(main())
