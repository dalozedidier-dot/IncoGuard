#!/usr/bin/env python3
"""
DEPRECATED: FluxGuard has been renamed to IncoGuard.

Use:
  python incoguard.py <command> [args...]

This wrapper is kept for backward compatibility and will be removed in a future release.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    sys.stderr.write(
        "DEPRECATED: 'fluxguard.py' has been renamed to 'incoguard.py'. "
        "Please update your scripts and CI.
"
    )
    target = Path(__file__).with_name("incoguard.py")
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
