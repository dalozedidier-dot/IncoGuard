\
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


def quantize_floats(obj: Any, ndigits: int = 12) -> Any:
    """
    Recursively round floats for deterministic JSON output across platforms and Python versions.
    """
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: quantize_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [quantize_floats(v, ndigits) for v in obj]
    return obj


def dump_json(
    path: str | Path,
    data: Any,
    *,
    ndigits: int = 12,
    sort_keys: bool = True,
    indent: int = 2,
) -> str:
    """
    Write stable JSON to disk and return the sha256 of the written bytes.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    stable = quantize_floats(data, ndigits=ndigits)
    raw = json.dumps(stable, sort_keys=sort_keys, indent=indent, ensure_ascii=False).encode("utf-8") + b"\n"
    p.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
