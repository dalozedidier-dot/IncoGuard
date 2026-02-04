#!/usr/bin/env python3
"""
Normalize FluxGuard artifact summaries for auditability.

- Fix generated_at_utc when it is the Unix epoch default.
- Add SHA256 for local files that are referenced in summaries, when present.
- For VoidMark summaries, copy runs/noise/seed from the referenced mark file into the summary.
- For "all" (full chain) summary, copy runs/noise/seed from the full step2 voidmark mark file (when present).

This script is intentionally conservative: it only enriches summaries and does not mutate
the underlying reports besides fixing the timestamp field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


EPOCH_ISO = "1970-01-01T00:00:00Z"
NORMALIZED_BY = "fluxguard_normalize_outputs.py v1"


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def safe_relpath(path: str) -> str:
    # Many summaries reference "_ci_out/..." which is an external root.
    # For artifact bundles, the same file is usually present relative to the bundle root.
    # We try a best effort rewrite by stripping a leading "_ci_out/".
    if path.startswith("_ci_out/"):
        return path[len("_ci_out/"):]
    return path


def ensure_audit_block(summary: Dict[str, Any]) -> Dict[str, Any]:
    audit = summary.get("audit")
    if not isinstance(audit, dict):
        audit = {}
        summary["audit"] = audit
    audit.setdefault("normalized_by", NORMALIZED_BY)
    audit.setdefault("normalized_at_utc", utc_now_iso())
    audit.setdefault("files_sha256", {})
    return audit


def add_file_sha(audit: Dict[str, Any], root: Path, key: str, ref_path: str) -> None:
    files_sha = audit.get("files_sha256")
    if not isinstance(files_sha, dict):
        files_sha = {}
        audit["files_sha256"] = files_sha

    rel = safe_relpath(ref_path)
    p = root / rel
    if p.is_file():
        files_sha[key] = sha256_file(p)


def enrich_voidmark(summary: Dict[str, Any], root: Path, ref_path: str, where: str) -> None:
    rel = safe_relpath(ref_path)
    p = root / rel
    if not p.is_file():
        return
    mark = load_json(p)
    # Copy essential fields into a dedicated audit section to avoid breaking consumers.
    audit = ensure_audit_block(summary)
    vm = audit.setdefault("voidmark", {})
    if isinstance(vm, dict):
        for k in ("runs", "noise", "seed", "base_sha256", "target"):
            if k in mark:
                vm[f"{where}.{k}"] = mark[k]


def normalize_summary_file(path: Path, root: Path) -> bool:
    summary = load_json(path)

    changed = False

    # Fix timestamp default.
    if summary.get("generated_at_utc") == EPOCH_ISO:
        summary["generated_at_utc"] = utc_now_iso()
        changed = True

    audit = ensure_audit_block(summary)

    # Add sha256 for known referenced files.
    cmd = summary.get("command", "")

    if cmd == "all":
        full_chain = summary.get("full_chain")
        if isinstance(full_chain, dict):
            inputs = full_chain.get("inputs")
            if isinstance(inputs, str):
                add_file_sha(audit, root, "full_chain.inputs", inputs)
            rift = full_chain.get("riftlens")
            if isinstance(rift, dict):
                for rep in rift.get("reports", []) if isinstance(rift.get("reports"), list) else []:
                    if isinstance(rep, dict) and isinstance(rep.get("report"), str):
                        add_file_sha(audit, root, f"full_chain.riftlens.{rep.get('threshold')}", rep["report"])
            vm = full_chain.get("voidmark")
            if isinstance(vm, dict) and isinstance(vm.get("mark"), str):
                add_file_sha(audit, root, "full_chain.voidmark.mark", vm["mark"])
                enrich_voidmark(summary, root, vm["mark"], where="full")
    elif cmd == "riftlens":
        rift = summary.get("riftlens")
        if isinstance(rift, dict):
            for rep in rift.get("reports", []) if isinstance(rift.get("reports"), list) else []:
                if isinstance(rep, dict) and isinstance(rep.get("report"), str):
                    add_file_sha(audit, root, f"riftlens.{rep.get('threshold')}", rep["report"])
    elif cmd == "voidmark":
        vm = summary.get("voidmark")
        if isinstance(vm, dict) and isinstance(vm.get("mark"), str):
            add_file_sha(audit, root, "voidmark.mark", vm["mark"])
            enrich_voidmark(summary, root, vm["mark"], where="voidmark")
    elif cmd == "nulltrace":
        # nulltrace already carries seed; nothing to add besides timestamp and general audit block.
        pass

    if changed:
        dump_json(path, summary)

    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Root directory containing extracted FluxGuard artifacts")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Root not found: {root}")

    summary_files = list(root.rglob("fluxguard_summary.json"))
    if not summary_files:
        raise SystemExit("No fluxguard_summary.json files found under root.")

    changed_any = False
    for s in summary_files:
        if normalize_summary_file(s, root):
            changed_any = True

    print(f"Summaries found: {len(summary_files)}")
    print(f"Summaries changed: {'yes' if changed_any else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
