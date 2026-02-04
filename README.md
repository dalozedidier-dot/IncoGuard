EchoNull determinism and stability update bundle v1

Goal
Stabilize outputs across runs by controlling randomness, limiting parallelism, and making JSON serialization stable.

What this bundle contains
1) common/determinism.py
Seed utilities for random and numpy with a single seed effective model, plus UTC timestamp helper.

2) common/jsonio.py
Stable JSON writer with optional float quantization for cross Python determinism.

3) scripts/patch_orchestrator_determinism.py
Best effort patcher that tries to inject deterministic seeding and CLI flags into the orchestrator runner.
It creates .bak backups for modified files.

4) scripts/inspect_soak_outliers.py
Tool to scan an output directory and print the worst runs based on delta_stats and graph metrics.

5) scripts/check_output_hashes.py
Tool to compare two output directories and report exact file hash differences.

How to apply
1) Unzip at repo root
2) Run:
   python scripts/patch_orchestrator_determinism.py

3) Review changes:
   git diff

4) Run a deterministic soak locally:
   python -m orchestrator.run --runs 50 --out _soak_out --workers 1 --seed-base 1000 --seed-mode per-run --deterministic --zip

Notes
- If your orchestrator CLI does not match the patcher patterns, the patcher will not modify code. In that case, apply the changes manually using the added helper modules.
- For strict determinism across Python versions, set JSON quantization digits to 12 in common/jsonio.py.
