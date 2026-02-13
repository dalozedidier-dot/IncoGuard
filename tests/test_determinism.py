import unittest
from pathlib import Path
import shutil
import tempfile
import os
import subprocess
import sys
import hashlib


ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "fluxguard"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class TestDeterminism(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="incoguard_det_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_voidmark_mark_is_stable(self) -> None:
        out1 = self.tmp / "_ci_out1" / "full"
        out2 = self.tmp / "_ci_out2" / "full"

        env = dict(os.environ)
        env["PYTHONHASHSEED"] = "0"
        env["SOURCE_DATE_EPOCH"] = "0"

        def run(out: Path) -> None:
            cmd = [
                sys.executable,
                str(PKG / "incoguard.py"),
                "all",
                "--shadow-prev",
                str(PKG / "datasets" / "example.csv"),
                "--shadow-curr",
                str(PKG / "datasets" / "example_drift.csv"),
                "--output-dir",
                str(out),
            ]
            subprocess.check_call(cmd, cwd=str(PKG), env=env)

        run(out1)
        run(out2)

        m1 = out1 / "step2_voidmark" / "vault" / "voidmark_mark.json"
        m2 = out2 / "step2_voidmark" / "vault" / "voidmark_mark.json"
        self.assertTrue(m1.exists() and m2.exists())
        self.assertEqual(sha256_file(m1), sha256_file(m2))


if __name__ == "__main__":
    unittest.main()
