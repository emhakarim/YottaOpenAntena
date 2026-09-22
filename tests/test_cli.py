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


class TestNf2ffDefault(unittest.TestCase):
    """A2 / R-7: the near-to-far-field box is opt-in through the real CLI too.

    It costs every run (a far-field pass, and 12 near-field HDF5 files before the
    DFT-only recording change) for data that S11 work never reads.
    """

    def test_gen_openems_leaves_nf2ff_off_unless_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_cli(
                "gen-openems",
                "--freq", "2.45e9", "--material", "PTFE", "--h", "0.0016",
                "--start", "2.0e9", "--stop", "3.0e9", "--points", "21",
                "--out", tmp,
            )
            script = (Path(tmp) / "sim.py").read_text(encoding="utf-8")
            self.assertIn("NF2FF_ENABLED = False", script)

    def test_gen_openems_enables_nf2ff_when_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_cli(
                "gen-openems",
                "--freq", "2.45e9", "--material", "PTFE", "--h", "0.0016",
                "--start", "2.0e9", "--stop", "3.0e9", "--points", "21",
                "--nf2ff",
                "--out", tmp,
            )
            script = (Path(tmp) / "sim.py").read_text(encoding="utf-8")
            self.assertIn("NF2FF_ENABLED = True", script)


class TestCouplingCli(unittest.TestCase):
    """The toolkit must be able to report coupling, not only the verification tool."""

    def _runs(self, root: Path) -> list[str]:
        from test_port_matrix_reader import make_run

        return [f"{p}={make_run(root, p, 3)}" for p in (1, 2, 3)]

    def test_coupling_reports_the_worst_pair(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            args = self._runs(Path(tmp))
            result = run_cli(
                "coupling",
                "--ports", "3",
                "--frequency", "2.45e9",
                *[part for spec in args for part in ("--run", spec)],
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("worst coupling", result.stdout)
        self.assertIn("0.05", result.stdout)

    def test_coupling_refuses_to_quote_an_unconverged_run(self):
        import tempfile
        from pathlib import Path as _Path

        from test_port_matrix_reader import make_run

        with tempfile.TemporaryDirectory() as tmp:
            root = _Path(tmp)
            specs = [f"1={make_run(root, 1, 2)}", f"2={make_run(root, 2, 2, converged=False)}"]
            result = run_cli(
                "coupling",
                "--ports",
                "2",
                "--frequency",
                "2.45e9",
                *[part for spec in specs for part in ("--run", spec)],
                expect_ok=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("convergence-policy", result.stderr)

    def test_a_bad_run_spec_is_rejected_with_a_clear_message(self):
        result = run_cli(
            "coupling", "--ports", "2", "--frequency", "2.45e9", "--run", "nonsense",
            expect_ok=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("PORT=DIR", result.stderr)


if __name__ == "__main__":
    unittest.main()
