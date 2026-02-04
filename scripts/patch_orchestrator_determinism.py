\
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional, Tuple

ROOT = Path(".").resolve()


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _write(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


def _backup(p: Path) -> None:
    bak = p.with_suffix(p.suffix + ".bak")
    if not bak.exists():
        bak.write_bytes(p.read_bytes())


def find_orchestrator_entrypoints() -> list[Path]:
    candidates: list[Path] = []
    # common typical locations
    direct = [
        ROOT / "orchestrator" / "run.py",
        ROOT / "orchestrator" / "__main__.py",
        ROOT / "orchestrator" / "cli.py",
        ROOT / "orchestrator" / "runner.py",
        ROOT / "orchestrator" / "run" / "__init__.py",
    ]
    for p in direct:
        if p.exists():
            candidates.append(p)

    # heuristic search for argparse flags
    for p in (ROOT / "orchestrator").rglob("*.py") if (ROOT / "orchestrator").exists() else []:
        try:
            txt = _read(p)
        except Exception:
            continue
        if "argparse" in txt and "--runs" in txt:
            if p not in candidates:
                candidates.append(p)

    return candidates


def ensure_helpers_present() -> None:
    common_dir = ROOT / "common"
    common_dir.mkdir(parents=True, exist_ok=True)
    init_py = common_dir / "__init__.py"
    if not init_py.exists():
        init_py.write_text("", encoding="utf-8")


def inject_imports(txt: str) -> Tuple[str, bool]:
    changed = False
    if "from common.determinism import" not in txt:
        # insert after stdlib imports block if possible
        m = re.search(r"(?m)^(import .+\n(?:import .+\n|from .+ import .+\n)*)\n", txt)
        ins = "from common.determinism import DeterminismConfig, seed_everything, utc_now_iso\n"
        if m:
            start = m.end(1)
            txt = txt[:start] + ins + txt[start:]
        else:
            txt = ins + txt
        changed = True

    if "from common.jsonio import" not in txt:
        m = re.search(r"(?m)^from common\.determinism import .*?\n", txt)
        ins = "from common.jsonio import dump_json\n"
        if m:
            txt = txt[:m.end()] + ins + txt[m.end():]
        else:
            txt = ins + txt
        changed = True

    return txt, changed


def inject_cli_args(txt: str) -> Tuple[str, bool]:
    """
    Adds argparse flags:
    --seed-base int
    --seed-mode fixed|per-run
    --deterministic
    and ensures default workers=1 if a workers arg exists.
    """
    changed = False

    # add seed args after --runs if found
    runs_pat = re.compile(r"(?m)^(?P<indent>\s*)parser\.add_argument\(\s*['\"]--runs['\"].*\)\s*$")
    m = runs_pat.search(txt)
    if m and "--seed-base" not in txt:
        indent = m.group("indent")
        block = (
            f"{indent}parser.add_argument('--seed-base', type=int, default=1000)\n"
            f"{indent}parser.add_argument('--seed-mode', choices=['fixed', 'per-run'], default='per-run')\n"
            f"{indent}parser.add_argument('--deterministic', action='store_true')\n"
        )
        insert_at = m.end()
        txt = txt[:insert_at] + "\n" + block + txt[insert_at:]
        changed = True

    # set default workers=1 if present and not already 1
    # This is intentionally conservative: it only edits if default is explicit and different.
    workers_pat = re.compile(r"(?m)^(?P<indent>\s*)parser\.add_argument\(\s*['\"]--workers['\"].*default\s*=\s*(?P<def>\d+).*?\)\s*$")
    m2 = workers_pat.search(txt)
    if m2:
        d = int(m2.group("def"))
        if d != 1:
            line = m2.group(0)
            newline = re.sub(r"default\s*=\s*\d+", "default=1", line)
            txt = txt.replace(line, newline)
            changed = True

    return txt, changed


def inject_seeding_in_loop(txt: str) -> Tuple[str, bool]:
    """
    Tries to find a run loop and inject seeding per iteration.
    Looks for 'for ... in range(' patterns that reference args.runs or runs.
    """
    changed = False

    if "seed_everything(" in txt and "DeterminismConfig" in txt:
        return txt, False

    # ensure a config exists near main
    if "det_cfg = DeterminismConfig" not in txt:
        # crude insertion near args parsing
        m = re.search(r"(?m)^\s*args\s*=\s*parser\.parse_args\(\)\s*$", txt)
        if m:
            indent = re.match(r"(?m)^(\s*)", m.group(0)).group(1)
            ins = (
                f"{indent}det_cfg = DeterminismConfig(seed_base=int(args.seed_base), seed_mode=str(args.seed_mode))\n"
                f"{indent}if getattr(args, 'deterministic', False):\n"
                f"{indent}    # force single worker for determinism\n"
                f"{indent}    if hasattr(args, 'workers'):\n"
                f"{indent}        args.workers = 1\n"
            )
            txt = txt[:m.end()] + "\n" + ins + txt[m.end():]
            changed = True

    # inject into loop
    loop_pat = re.compile(r"(?m)^(?P<indent>\s*)for\s+(?P<var>\w+)\s+in\s+range\(\s*(?P<rng>[^)]+)\)\s*:\s*$")
    for m in loop_pat.finditer(txt):
        rng = m.group("rng")
        if "runs" not in rng:
            continue
        indent = m.group("indent") + "    "
        var = m.group("var")
        inject = (
            f"{indent}seed = det_cfg.seed_for_run(int({var}) + 1)\n"
            f"{indent}seed_everything(seed)\n"
            f"{indent}# optional: persist per run metadata\n"
            f"{indent}try:\n"
            f"{indent}    run_meta = {{'run_id': int({var}) + 1, 'seed_base': int(det_cfg.seed_base), 'seed_mode': str(det_cfg.seed_mode), 'seed_effective': int(seed), 'generated_at_utc': utc_now_iso()}}\n"
            f"{indent}except Exception:\n"
            f"{indent}    run_meta = None\n"
        )
        # do not double inject
        if "seed = det_cfg.seed_for_run" in txt[m.end():m.end()+400]:
            continue
        txt = txt[:m.end()] + "\n" + inject + txt[m.end():]
        changed = True
        break

    return txt, changed


def patch_json_writes(txt: str) -> Tuple[str, bool]:
    """
    Replace json.dump calls that write dicts to a file handle with dump_json(path, data).
    This cannot catch all patterns, so it is conservative.
    """
    changed = False

    # If dump_json already used, skip
    if "dump_json(" in txt:
        return txt, False

    # naive detection of patterns: with open(path, 'w') as f: json.dump(obj, f, ...)
    pat = re.compile(
        r"with\s+open\(\s*(?P<path>[^,]+)\s*,\s*['\"]w['\"].*?\)\s+as\s+(?P<fh>\w+)\s*:\s*\n(?P<indent>\s*)json\.dump\(\s*(?P<obj>[^,]+)\s*,\s*(?P=fh)\s*(?P<rest>,[^\n]+)?\)\s*",
        re.MULTILINE,
    )
    m = pat.search(txt)
    if m:
        path_expr = m.group("path").strip()
        obj_expr = m.group("obj").strip()
        indent = m.group("indent")
        replacement = f"dump_json({path_expr}, {obj_expr})"
        block = f"with open({path_expr}, 'w', encoding='utf-8') as _:\n{indent}{replacement}\n"
        txt = txt[:m.start()] + block + txt[m.end():]
        changed = True

    return txt, changed


def apply_patch(p: Path) -> bool:
    original = _read(p)
    txt = original
    any_change = False

    txt, ch = inject_imports(txt); any_change |= ch
    txt, ch = inject_cli_args(txt); any_change |= ch
    txt, ch = inject_seeding_in_loop(txt); any_change |= ch
    txt, ch = patch_json_writes(txt); any_change |= ch

    if any_change and txt != original:
        _backup(p)
        _write(p, txt)
    return any_change


def main() -> int:
    ensure_helpers_present()
    candidates = find_orchestrator_entrypoints()
    if not candidates:
        print("No orchestrator entrypoint candidates found. Nothing patched.")
        return 2

    patched_any = False
    for p in candidates:
        try:
            changed = apply_patch(p)
        except Exception as e:
            print(f"Failed to patch {p}: {e}")
            continue
        if changed:
            patched_any = True
            print(f"Patched: {p}")

    if not patched_any:
        print("Found candidates but no patterns matched. Apply changes manually.")
        return 1

    print("Patch complete. Review with: git diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
