\
from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


def utc_now_iso() -> str:
    """UTC ISO8601 timestamp with Z suffix, seconds precision."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def seed_effective(seed_base: int, run_id: int, salt: int = 0) -> int:
    """
    Stable 32-bit seed derivation.
    Uses a golden ratio constant to decorrelate sequential run ids.
    """
    return (seed_base ^ (run_id * 0x9E3779B1) ^ salt) & 0xFFFFFFFF


def seed_everything(seed: int) -> None:
    """
    Seed python random and numpy if available.
    Also sets an env var for downstream code that reads it.
    """
    os.environ["ECHONULL_SEED_EFFECTIVE"] = str(int(seed))
    random.seed(int(seed))
    try:
        import numpy as np  # type: ignore

        np.random.seed(int(seed))
    except Exception:
        # numpy not installed or other issues
        pass


def set_pythonhashseed(seed: int) -> None:
    """
    Sets PYTHONHASHSEED for reproducible hashing.
    Note: this only affects new interpreter processes.
    """
    os.environ["PYTHONHASHSEED"] = str(int(seed))


@dataclass(frozen=True)
class DeterminismConfig:
    seed_base: int = 1000
    seed_mode: str = "per-run"  # "fixed" or "per-run"
    salt: int = 0

    def seed_for_run(self, run_id: int) -> int:
        if self.seed_mode == "fixed":
            return int(self.seed_base) & 0xFFFFFFFF
        if self.seed_mode == "per-run":
            return seed_effective(int(self.seed_base), int(run_id), int(self.salt))
        raise ValueError(f"Unsupported seed_mode: {self.seed_mode!r}")
