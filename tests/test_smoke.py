import unittest
from pathlib import Path
import shutil
import tempfile
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "fluxguard"


class TestSmoke(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="fluxguard_test_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_chain_runs_and_outputs_exist(self) -> None:
        out = self.tmp / "_ci_out" / "full"
        cmd = [
            sys.executable,
            str(PKG / "fluxguard.py"),
            "all",
            "--shadow-prev",
            str(PKG / "datasets" / "example.csv"),
            "--shadow-curr",
            str(PKG / "datasets" / "example_drift.csv"),
            "--rift-local-ruptures",
            "--rift-window",
            "2",
            "--rift-step",
            "1",
            "--output-dir",
            str(out),
        ]
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = "0"
        env["SOURCE_DATE_EPOCH"] = "0"
        subprocess.check_call(cmd, cwd=str(PKG), env=env)

        self.assertTrue((out / "full_chain_report.json").exists())
        self.assertTrue((out / "step2_voidmark" / "vault" / "voidmark_mark.json").exists())
        self.assertTrue((out / "step1_riftlens").exists())


if __name__ == "__main__":
    unittest.main()
