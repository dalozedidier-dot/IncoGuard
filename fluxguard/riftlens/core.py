from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False


def read_numeric_csv(path: Path) -> Dict[str, List[float]]:
    """
    Lit un CSV avec header.
    Conserve uniquement les colonnes numériques.
    Ignore les cellules non numériques.
    """
    cols: Dict[str, List[float]] = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV sans header")
        for name in reader.fieldnames:
            cols[name] = []

        for row in reader:
            for k, v in row.items():
                if v is None:
                    continue
                v = v.strip()
                if _is_float(v):
                    cols[k].append(float(v))

    numeric = {k: v for k, v in cols.items() if len(v) > 1}
    if not numeric:
        raise ValueError("Aucune colonne numérique exploitable")
    return numeric


def pearson_corr(x: List[float], y: List[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    x = x[:n]
    y = y[:n]
    mx = sum(x) / n
    my = sum(y) / n
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 0.0 or vy <= 0.0:
        return 0.0
    cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    return cov / math.sqrt(vx * vy)


def build_coherence_graph(data: Dict[str, List[float]], threshold: float) -> dict:
    keys = sorted(data.keys())
    edges: List[dict] = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            raw = pearson_corr(data[a], data[b])
            if abs(raw) >= threshold:
                edges.append({"a": a, "b": b, "corr": round(raw, 12)})
    return {"nodes": keys, "edges": edges, "threshold": float(threshold)}


def windowed_corr_edges(
    data: Dict[str, List[float]],
    threshold: float,
    window: int,
    step: int,
) -> List[dict]:
    keys = sorted(data.keys())
    length = min(len(v) for v in data.values())
    out: List[dict] = []
    if length < 2:
        return out

    if window < 2:
        window = min(50, length)
    if step < 1:
        step = window

    for start in range(0, max(1, length - window + 1), step):
        end = start + window
        edges: List[dict] = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                x = data[a][start:end]
                y = data[b][start:end]
                raw = pearson_corr(x, y)
                if abs(raw) >= threshold:
                    edges.append({"a": a, "b": b, "corr": round(raw, 12)})
        out.append(
            {
                "start": int(start),
                "end": int(min(end, length)),
                "edges_count": int(len(edges)),
                "edges": edges,
                "threshold": float(threshold),
            }
        )
    return out


def detect_local_ruptures(
    per_window: List[dict],
    delta_edges_threshold: int = 1,
) -> List[int]:
    rpts: List[int] = []
    if not per_window:
        return rpts
    prev = per_window[0]["edges_count"]
    for w in per_window[1:]:
        cur = w["edges_count"]
        if abs(int(cur) - int(prev)) >= int(delta_edges_threshold):
            rpts.append(int(w["start"]))
        prev = cur
    return sorted(set(rpts))


def lagged_directed_edges(
    data: Dict[str, List[float]],
    threshold: float,
    max_lag: int,
) -> List[dict]:
    keys = sorted(data.keys())
    length = min(len(v) for v in data.values())
    edges: List[dict] = []
    if length < 3:
        return edges

    max_lag = max(1, int(max_lag))

    for src in keys:
        for dst in keys:
            if src == dst:
                continue
            best = 0.0
            best_lag = 1
            for lag in range(1, max_lag + 1):
                x = data[src][0 : length - lag]
                y = data[dst][lag:length]
                r = pearson_corr(x, y)
                if abs(r) > abs(best):
                    best = r
                    best_lag = lag
            if abs(best) >= threshold:
                edges.append(
                    {
                        "from": src,
                        "to": dst,
                        "lag": int(best_lag),
                        "corr": round(best, 12),
                    }
                )
    return edges


def write_report(report: dict, outpath: Path) -> None:
    outpath.parent.mkdir(parents=True, exist_ok=True)
    import json

    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, sort_keys=True)


def riftlens_run_csv(
    input_csv: Path,
    thresholds: List[float],
    output_dir: Path,
    local_ruptures: bool = False,
    window: int = 100,
    step: int = 100,
    delta_edges_threshold: int = 1,
    mode: str = "corr",
    max_lag: int = 3,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = read_numeric_csv(input_csv)
    reports = []

    mode = str(mode).strip().lower()

    for thr in thresholds:
        graph = build_coherence_graph(data, threshold=float(thr))

        extra: dict = {}
        if local_ruptures:
            per_window = windowed_corr_edges(data, threshold=float(thr), window=int(window), step=int(step))
            rpts = detect_local_ruptures(per_window, delta_edges_threshold=int(delta_edges_threshold))
            extra["local_ruptures"] = {
                "window": int(window),
                "step": int(step),
                "delta_edges_threshold": int(delta_edges_threshold),
                "rupture_points": rpts,
                "per_window_edges": [
                    {"start": w["start"], "end": w["end"], "edges_count": w["edges_count"]}
                    for w in per_window
                ],
            }

        if mode == "causal":
            extra["causal_edges"] = lagged_directed_edges(data, threshold=float(thr), max_lag=int(max_lag))
            extra["causal_mode"] = {"type": "lagged_corr_lite", "max_lag": int(max_lag)}

        if extra:
            graph.update(extra)

        out = output_dir / f"riftlens_report_thr_{float(thr):.2f}.json"
        write_report(graph, out)
        reports.append({"threshold": float(thr), "report": str(out)})

    return {"input": str(input_csv), "reports": reports}
