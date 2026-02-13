#!/usr/bin/env python3
"""
Compatibility wrapper.

The project has been renamed from FluxGuard to IncoGuard.
This tool keeps the old behavior while providing the new entrypoint name.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    target = Path(__file__).with_name("fluxguard_validate_refs.py")
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
