\
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def find_output_root(path: Path) -> Path:
    # supports _ci_out or _soak_out
    if (path / "overview.json").exists():
        return path
    for name in ["_ci_out", "_soak_out"]:
        if (path / name / "overview.json").exists():
            return path / name
    raise FileNotFoundError("No overview.json found at path or common subdirs.")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", help="Path to _soak_out or parent directory")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    root = find_output_root(Path(args.out_dir))
    runs = sorted([p for p in root.glob("run_*") if p.is_dir()])
    rows: List[Tuple[int, float, float]] = []

    for run_dir in runs:
        run_id = int(run_dir.name.split("_")[1])
        stats_p = run_dir / "delta_stats" / "stats.json"
        if not stats_p.exists():
            continue
        stats = load_json(stats_p)
        abs_p50 = float(stats.get("abs_p50", 0.0))
        abs_max = float(stats.get("abs_max", 0.0))
        rows.append((run_id, abs_p50, abs_max))

    rows.sort(key=lambda x: x[2], reverse=True)
    print(f"Scanned {len(rows)} runs in {root}")
    print("Worst runs by abs_max:")
    for run_id, p50, mx in rows[: args.top]:
        print(f"run {run_id:04d} abs_p50={p50:.6g} abs_max={mx:.6g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
