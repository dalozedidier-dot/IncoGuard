from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from riftlens.core import riftlens_run_csv
from voidmark.vault import voidmark_run_stress_test

def relpath(p: Path, base: Path) -> str:
    try:
        return p.relative_to(base).as_posix()
    except Exception:
        return p.as_posix()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)


def run_full_chain(
    shadow_prev: Path,
    shadow_curr: Path,
    output_dir: Path,
    rift_thresholds: List[float],
    rift_local_ruptures: bool,
    rift_window: int,
    rift_step: int,
    rift_delta_edges: int,
    rift_mode: str,
    rift_max_lag: int,
    void_runs: int,
    void_noise: float,
    void_seed: int = 0,
    void_baseline_mark: Optional[Path] = None,
    version_db: Optional[Path] = None,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    step0 = output_dir / "step0_inputs"
    step0.mkdir(parents=True, exist_ok=True)
    inputs_report = {
        "shadow_prev": str(shadow_prev),
        "shadow_curr": str(shadow_curr),
        "shadow_prev_sha256": sha256_file(shadow_prev) if shadow_prev.is_file() else None,
        "shadow_curr_sha256": sha256_file(shadow_curr) if shadow_curr.is_file() else None,
    }
    write_json(step0 / "inputs_report.json", inputs_report)

    step1 = output_dir / "step1_riftlens"
    rift = riftlens_run_csv(
        input_csv=shadow_curr,
        thresholds=[float(x) for x in rift_thresholds],
        output_dir=step1,
        local_ruptures=bool(rift_local_ruptures),
        window=int(rift_window),
        step=int(rift_step),
        delta_edges_threshold=int(rift_delta_edges),
        mode=str(rift_mode),
        max_lag=int(rift_max_lag),
    )

    step2 = output_dir / "step2_voidmark"
    void = voidmark_run_stress_test(
        target=output_dir,
        runs=int(void_runs),
        noise=float(void_noise),
        output_dir=step2,
        seed=int(void_seed),
        fingerprint_csv_path=shadow_curr,
        baseline_mark=void_baseline_mark,
        ks_alpha=0.05,
        version_db=version_db,
    )

    chain = {
        "inputs": relpath(step0 / "inputs_report.json", output_dir),
        "riftlens": rift,
        "voidmark": void,
        "params": {
            "rift_thresholds": [float(x) for x in rift_thresholds],
            "rift_local_ruptures": bool(rift_local_ruptures),
            "rift_window": int(rift_window),
            "rift_step": int(rift_step),
            "rift_delta_edges": int(rift_delta_edges),
            "rift_mode": str(rift_mode),
            "rift_max_lag": int(rift_max_lag),
            "void_runs": int(void_runs),
            "void_noise": float(void_noise),
            "void_seed": int(void_seed),
        },
    }
    write_json(output_dir / "full_chain_report.json", chain)
    return chain
