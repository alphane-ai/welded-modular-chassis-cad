#!/usr/bin/env python3
"""Read-only integrity check for the single production drawing set."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys


def main():
    repo = Path(__file__).resolve().parent.parent
    manifest = json.loads((repo / "delivery-manifest.json").read_text(encoding="utf-8"))
    production = (repo / manifest["root"]).resolve()
    if not production.is_relative_to(repo) or not production.is_dir():
        print("FAIL: production directory is missing or outside the repository")
        return 1

    errors = []
    expected = {}
    for item in manifest["files"]:
        rel = item["path"]
        target = (production / rel).resolve()
        if not target.is_relative_to(production) or rel in expected:
            errors.append(f"Invalid or duplicate manifest path: {rel}")
            continue
        expected[rel] = item

    actual = {
        p.relative_to(production).as_posix(): p
        for p in production.rglob("*")
        if p.is_file() and not p.name.startswith("~$")
    }
    for rel in sorted(set(expected) - set(actual)):
        errors.append(f"Missing: {rel}")
    for rel in sorted(set(actual) - set(expected)):
        errors.append(f"Unexpected: {rel}")

    hashes = defaultdict(list)
    for rel, path in sorted(actual.items()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[digest].append(rel)
        item = expected.get(rel)
        if item is None:
            continue
        if path.stat().st_size != item["bytes"]:
            errors.append(f"Size changed: {rel}")
        if digest != item["sha256"]:
            errors.append(f"SHA-256 changed: {rel}")

    for names in hashes.values():
        if len(names) > 1:
            errors.append("Duplicate content: " + " / ".join(names))

    if len(expected) != manifest["file_count"]:
        errors.append("Manifest file count does not match its entries")
    if errors:
        for error in errors:
            print("FAIL: " + error)
        return 1

    counts = Counter(path.suffix.lower() for path in actual.values())
    print(f"OK: {len(actual)} delivery files; SHA-256 matches; no duplicate content")
    print(", ".join(f"{ext}: {count}" for ext, count in sorted(counts.items())))
    print("Scope: file integrity only; CAD geometry and manufacturing are not revalidated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
