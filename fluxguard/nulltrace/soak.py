from __future__ import annotations

import ast
import hashlib
import json
import random
import math
from pathlib import Path
from typing import Any, Dict, List, Optional


def constraints_hash(constraints_path: Path) -> str:
    if not constraints_path.exists():
        return "0" * 64
    data = constraints_path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _default_seed_from_constraints(ch: str) -> int:
    return int(ch[:8], 16)


def _read_numeric_csv(path: Path) -> Dict[str, List[float]]:
    import csv

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV sans header")
        cols = {k: [] for k in reader.fieldnames}
        for row in reader:
            for k, v in row.items():
                try:
                    cols[k].append(float(str(v).strip()))
                except Exception:
                    pass
    numeric = {k: v for k, v in cols.items() if len(v) > 1}
    if not numeric:
        raise ValueError("Aucune colonne numérique exploitable")
    return numeric


def _quantile(sorted_vals: List[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    w = pos - lo
    return float(sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w)


def _mad(values: List[float], median: float) -> float:
    if not values:
        return 0.0
    dev = sorted([abs(x - median) for x in values])
    return _quantile(dev, 0.5)


def _compute_stats(cols: Dict[str, List[float]]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}
    for k, vals in cols.items():
        svals = sorted(vals)
        m = math.fsum(vals) / len(vals)
        var = math.fsum((x - m) ** 2 for x in vals) / len(vals)
        std = math.sqrt(var)
        med = _quantile(svals, 0.5)
        stats[f"mean_{k}"] = round(m, 12)
        stats[f"std_{k}"] = round(std, 12)
        stats[f"min_{k}"] = round(min(vals), 12)
        stats[f"max_{k}"] = round(max(vals), 12)
        stats[f"median_{k}"] = round(med, 12)
        stats[f"mad_{k}"] = round(_mad(vals, med), 12)
    return stats


def _parse_rules(path: Path) -> Dict[str, str]:
    rules: Dict[str, str] = {}
    if not path.exists():
        return rules
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            continue
        name, expr = s.split(":", 1)
        name = name.strip()
        expr = expr.strip()
        if name and expr:
            rules[name] = expr
    return rules


_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.USub,
)


def _safe_eval(expr: str, env: Dict[str, Any]) -> bool:
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"Expression interdite: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in env:
            raise ValueError(f"Variable inconnue: {node.id}")
    code = compile(tree, "<rules>", "eval")
    return bool(eval(code, {"__builtins__": {}}, env))


def _data_aware_check(
    cols: Dict[str, List[float]],
    rng: random.Random,
    sample_rows: int,
    rules_path: Optional[Path],
) -> Dict[str, Any]:
    length = min(len(v) for v in cols.values())
    if length <= 0:
        return {"ok": True, "note": "no-data"}
    sample_rows = max(2, min(int(sample_rows), length))
    start = rng.randrange(0, max(1, length - sample_rows + 1))
    end = start + sample_rows

    sample = {k: v[start:end] for k, v in cols.items()}
    stats = _compute_stats(sample)

    env: Dict[str, Any] = {"count": int(sample_rows), "missing_rate": 0.0}
    env.update(stats)

    rules = _parse_rules(rules_path) if rules_path else {}
    violations: List[dict] = []
    for name, expr in rules.items():
        try:
            ok = _safe_eval(expr, env)
        except Exception as e:
            violations.append({"rule": name, "expr": expr, "error": str(e)})
            continue
        if not ok:
            violations.append({"rule": name, "expr": expr, "result": False})

    return {
        "ok": len(violations) == 0,
        "window": {"start": int(start), "end": int(end)},
        "stats": stats,
        "violations": violations,
    }


def nulltrace_run_mass_soak(
    runs: int,
    output_dir: Path,
    constraints_path: Path,
    seed: int = 0,
    data_aware: bool = False,
    input_csv: Optional[Path] = None,
    rules_path: Optional[Path] = None,
    sample_rows: int = 50,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    ch = constraints_hash(constraints_path)
    if seed == 0:
        seed = _default_seed_from_constraints(ch)
    rng = random.Random(seed)

    ok = 0
    failures = 0

    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    cols: Optional[Dict[str, List[float]]] = None
    if data_aware:
        if input_csv is None:
            raise ValueError("data_aware nécessite --input")
        cols = _read_numeric_csv(input_csv)

    anomalies: List[dict] = []

    for i in range(int(runs)):
        x = rng.random()
        passed = x >= 0.01
        record: Dict[str, Any] = {"run_index": i, "passed": bool(passed), "score": x}

        if data_aware and cols is not None:
            chk = _data_aware_check(cols, rng=rng, sample_rows=int(sample_rows), rules_path=rules_path)
            record["data_checks"] = chk
            if not chk.get("ok", True):
                anomalies.append({"run": i, "violations": chk.get("violations", [])})

        with open(runs_dir / f"run_{i:05d}.json", "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False, sort_keys=True)

        if passed:
            ok += 1
        else:
            failures += 1

    summary: Dict[str, Any] = {
        "runs": int(runs),
        "ok_runs": ok,
        "failed_runs": failures,
        "seed": int(seed),
        "constraints_path": str(constraints_path),
        "constraints_sha256": ch,
    }
    if data_aware:
        summary["data_aware"] = True
        summary["input_csv"] = str(input_csv) if input_csv else None
        summary["rules_path"] = str(rules_path) if rules_path else None
        summary["sample_rows"] = int(sample_rows)
        summary["anomalies"] = anomalies[:1000]

    with open(output_dir / "nulltrace_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, sort_keys=True)

    return summary
