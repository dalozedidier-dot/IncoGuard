#!/usr/bin/env python3
"""
Quantize floats in JSON files under a directory.

This helps neutralize micro float differences across Python versions / platforms
when JSON outputs are hashed or compared.

Default: 12 decimals.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def quantize(obj: Any, ndigits: int) -> Any:
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: quantize(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [quantize(v, ndigits) for v in obj]
    return obj


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Root directory containing JSON files")
    ap.add_argument("--ndigits", type=int, default=12)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Root not found: {root}")

    json_files = [p for p in root.rglob("*.json") if p.is_file()]
    changed = 0

    for p in json_files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        new = quantize(data, args.ndigits)
        if new != data:
            p.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            changed += 1

    print(f"JSON files scanned: {len(json_files)}")
    print(f"JSON files changed: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
