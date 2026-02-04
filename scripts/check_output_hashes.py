\
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Tuple


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_files(root: Path) -> Dict[str, str]:
    files: Dict[str, str] = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(root))
            files[rel] = sha256_file(p)
    return files


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("a", help="First output dir (_ci_out or _soak_out)")
    ap.add_argument("b", help="Second output dir (_ci_out or _soak_out)")
    args = ap.parse_args()

    ra = Path(args.a)
    rb = Path(args.b)
    fa = list_files(ra)
    fb = list_files(rb)

    all_keys = sorted(set(fa) | set(fb))
    only_a = [k for k in all_keys if k not in fb]
    only_b = [k for k in all_keys if k not in fa]
    diff = [k for k in all_keys if k in fa and k in fb and fa[k] != fb[k]]

    print(f"Files A: {len(fa)}")
    print(f"Files B: {len(fb)}")
    print(f"Only in A: {len(only_a)}")
    print(f"Only in B: {len(only_b)}")
    print(f"Different: {len(diff)}")

    if diff:
        print("First 50 diffs:")
        for k in diff[:50]:
            print(f"{k}  {fa[k][:12]}  {fb[k][:12]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
