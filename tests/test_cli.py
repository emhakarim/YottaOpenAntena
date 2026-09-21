"""End-to-end tests for the command line interface (subprocess, stdlib only)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, expect_ok: bool = True) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        [sys.executable, "-m", "openantenna.cli", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if expect_ok:
        assert completed.returncode == 0, (
            f"CLI exited {completed.returncode}\nstdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


class TestBasicCommands(unittest.TestCase):
    def test_version(self):
        result = run_cli("--version")
        self.assertIn("openantenna", result.stdout.lower())

    def test_material_list_contains_the_built_ins(self):
        result = run_cli("material", "list")
        for name in ("PTFE", "FR-4", "RO4003C", "copper", "air"):
            self.assertIn(name, result.stdout)

    def test_material_show_reports_loss_terms(self):
        result = run_cli("material", "show", "--name", "PTFE", "--freq", "3e9")
        self.assertIn("epsilon_r", result.stdout)
        self.assertIn("effective tan_delta", result.stdout)
        self.assertIn("source", result.stdout)

    def test_material_show_rejects_unknown_names(self):
        result = run_cli("material", "show", "--name", "unobtainium", expect_ok=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("error", result.stderr.lower())

    def test_solver_status_is_honest(self):
        result = run_cli("solver", "status")
        self.assertIn("available", result.stdout)
        self.assertIn("openems", result.stdout.lower())


class TestMixCommand(unittest.TestCase):
    def test_composite_mix_reports_models_and_warnings(self):
        result = run_cli("mix", "--matrix", "2.1", "--filler", "80", "--vf", "0.3")
        self.assertIn("Wiener", result.stdout)
        self.assertIn("Maxwell-Garnett", result.stdout)
        self.assertIn("effective loss tangent", result.stdout)

    def test_percolation_warning_is_printed_for_high_loading(self):
        result = run_cli(
            "mix", "--matrix", "2.1", "--filler", "80", "--vf", "0.6", "--freq", "1e6"
        )
        self.assertIn("warning", result.stdout.lower())

    def test_invalid_volume_fraction_fails_cleanly(self):
        result = run_cli(
            "mix", "--matrix", "2.1", "--filler", "80", "--vf", "1.5", expect_ok=False
        )
        self.assertEqual(result.returncode, 1)


class TestDesignCommands(unittest.TestCase):
    def test_patch_synthesis(self):
        result = run_cli("design", "patch", "--freq", "2.45e9", "--material", "PTFE", "--h", "0.0016")
        self.assertIn("patch W x L", result.stdout)
        self.assertIn("cavity cross-chk", result.stdout)

    def test_patch_writes_a_project_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project.json"
            run_cli(
                "design", "patch",
                "--freq", "2.45e9", "--material", "PTFE", "--h", "0.0016",
                "--project-out", str(target),
            )
            document = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(document["kind"], "openantenna.project")
        self.assertEqual(document["substrate"]["layers"][0]["material"], "PTFE")

    def test_array_layout_warns_for_sixteen_elements(self):
        result = run_cli(
            "design", "array",
            "--nx", "4", "--ny", "4", "--freq", "2.45e9", "--material", "PTFE", "--h", "0.0016",
        )
        self.assertIn("4 x 4", result.stdout)
        self.assertIn("unit-cell", result.stdout)

    def test_array_rejects_impossible_geometry(self):
        result = run_cli(
            "design", "array", "--nx", "0", "--ny", "4", "--freq", "2.45e9", expect_ok=False
        )
        self.assertEqual(result.returncode, 1)


class TestGenOpenEMS(unittest.TestCase):
    def test_generates_a_runnable_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(
                "gen-openems",
                "--freq", "2.45e9", "--material", "PTFE", "--h", "0.0016",
                "--start", "2.0e9", "--stop", "3.0e9", "--points", "21",
                "--out", tmp,
            )
            script = Path(tmp) / "sim.py"
            self.assertTrue(script.exists())
            text = script.read_text(encoding="utf-8")
        self.assertIn("AddLumpedPort", text)
        self.assertIn("NEVER BEEN EXECUTED", text)
        self.assertIn("not been executed", result.stdout)


class TestSweepDryRun(unittest.TestCase):
    def test_manifest_enumerates_jobs_without_running_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_cli(
                "sweep", "dry-run",
                "--freq", "2.45e9", "--material", "PTFE", "--h", "0.0016",
                "--axis", "substrate.layers.0.thickness_m=0.0008,0.0016,0.0032",
                "--axis", "sweep.points=51,101",
                "--out", tmp,
            )
            manifest = json.loads(
                (Path(tmp) / "sweep_manifest.json").read_text(encoding="utf-8")
            )
        self.assertEqual(manifest["job_count"], 6)
        self.assertEqual(len(manifest["jobs"]), 6)
        self.assertFalse(manifest["executed"])

    def test_unknown_axis_path_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(
                "sweep", "dry-run", "--axis", "nope.nothing=1,2", "--out", tmp, expect_ok=False
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("error", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
