#!/usr/bin/env python3
"""
Validate referenced artifacts exist locally and report their sha256.

This does not mutate files. It is a quick audit tool for extracted bundles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_relpath(path: str) -> str:
    return path[len("_ci_out/"):] if path.startswith("_ci_out/") else path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Root directory containing extracted FluxGuard artifacts")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Root not found: {root}")

    summaries = list(root.rglob("fluxguard_summary.json"))
    if not summaries:
        raise SystemExit("No fluxguard_summary.json files found.")

    missing: List[str] = []
    found: Dict[str, str] = {}

    for s in summaries:
        data = json.loads(s.read_text(encoding="utf-8"))
        cmd = data.get("command")
        if cmd == "all":
            full_chain = data.get("full_chain", {})
            if isinstance(full_chain, dict):
                for key in ("inputs",):
                    ref = full_chain.get(key)
                    if isinstance(ref, str):
                        p = root / safe_relpath(ref)
                        if p.is_file():
                            found[f"{s}:{key}"] = sha256_file(p)
                        else:
                            missing.append(f"{s}:{key}:{ref}")
                rift = full_chain.get("riftlens", {})
                if isinstance(rift, dict):
                    for rep in rift.get("reports", []) if isinstance(rift.get("reports"), list) else []:
                        if isinstance(rep, dict) and isinstance(rep.get("report"), str):
                            ref = rep["report"]
                            p = root / safe_relpath(ref)
                            if p.is_file():
                                found[f"{s}:riftlens:{rep.get('threshold')}"] = sha256_file(p)
                            else:
                                missing.append(f"{s}:riftlens:{ref}")
                vm = full_chain.get("voidmark", {})
                if isinstance(vm, dict) and isinstance(vm.get("mark"), str):
                    ref = vm["mark"]
                    p = root / safe_relpath(ref)
                    if p.is_file():
                        found[f"{s}:voidmark:mark"] = sha256_file(p)
                    else:
                        missing.append(f"{s}:voidmark:mark:{ref}")
        elif cmd == "riftlens":
            rift = data.get("riftlens", {})
            if isinstance(rift, dict):
                for rep in rift.get("reports", []) if isinstance(rift.get("reports"), list) else []:
                    if isinstance(rep, dict) and isinstance(rep.get("report"), str):
                        ref = rep["report"]
                        p = root / safe_relpath(ref)
                        if p.is_file():
                            found[f"{s}:riftlens:{rep.get('threshold')}"] = sha256_file(p)
                        else:
                            missing.append(f"{s}:riftlens:{ref}")
        elif cmd == "voidmark":
            vm = data.get("voidmark", {})
            if isinstance(vm, dict) and isinstance(vm.get("mark"), str):
                ref = vm["mark"]
                p = root / safe_relpath(ref)
                if p.is_file():
                    found[f"{s}:voidmark:mark"] = sha256_file(p)
                else:
                    missing.append(f"{s}:voidmark:mark:{ref}")

    print(f"Summaries: {len(summaries)}")
    print(f"Found refs: {len(found)}")
    print(f"Missing refs: {len(missing)}")
    if missing:
        print("Missing examples (first 20):")
        for m in missing[:20]:
            print("  " + m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
