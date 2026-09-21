"""Tests for the openEMS adapter: script generation, honest availability, parsing.

The generated script is inspected statically and parsed; it is NOT executed by
this test suite.  Executing it requires an openEMS/CSXCAD installation, and the
tests must stay meaningful on a machine without one.
"""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.base import SolverUnavailableError
from openantenna.solvers.openems import OpenEMSSolver


def make_project(nx: int = 1, ny: int = 1, material: str = "PTFE") -> Project:
    return Project(
        name="unit-test",
        substrate=SubstrateStackup.single(material, 1.6e-3),
        patch=PatchGeometry(feed_mode="inset"),
        array=ArrayConfig(nx=nx, ny=ny, spacing_x_lambda0=0.5, spacing_y_lambda0=0.5),
        sweep=FrequencySweep(start_hz=2.0e9, stop_hz=3.0e9, points=51),
    )


class TestScriptGeneration(unittest.TestCase):
    def setUp(self):
        self.solver = OpenEMSSolver()
        self.script = self.solver.render_script(make_project())

    def test_script_contains_the_core_api_calls(self):
        for token in (
            "from CSXCAD import ContinuousStructure",
            "from openEMS import openEMS",
            "FDTD.SetGaussExcite",
            "FDTD.SetBoundaryCond",
            "AddLumpedPort",
            "SmoothMeshLines",
            "FDTD.Run",
            "CalcPort",
        ):
            self.assertIn(token, self.script, msg=f"missing {token}")

    def test_script_marks_itself_as_unverified(self):
        self.assertIn("NEVER BEEN EXECUTED", self.script)

    def test_port_is_snapped_to_the_grid(self):
        """Regression guard: without edges2grid the port excite box is dropped
        and every S11 value comes back NaN."""
        self.assertIn('edges2grid="xy"', self.script)

    def test_meshing_covers_an_air_region(self):
        """Regression guard: a model without air above the patch loses its
        absorbing boundary (openEMS falls back to PEC) and traps the field."""
        self.assertIn("DOM_Z_TOP", self.script)
        self.assertIn("AIR_TOP_LAMBDA", self.script)

    def test_metal_is_a_thin_sheet(self):
        """Regression guard: a physical 35 um metal thickness collapsed the FDTD
        timestep to 6.5e-14 s."""
        self.assertNotIn("PATCH_THICKNESS", self.script)

    def test_element_positions_are_rendered_for_an_array(self):
        script = self.solver.render_script(make_project(nx=4, ny=4))
        line = next(
            row for row in script.splitlines() if row.startswith("ELEMENTS = ")
        )
        elements = ast.literal_eval(line.split("=", 1)[1].strip())
        self.assertEqual(len(elements), 16)
        self.assertEqual(len(elements[0]), 2)

    def test_unknown_material_is_rejected(self):
        project = make_project(material="unobtainium")
        with self.assertRaises(ValueError):
            self.solver.render_script(project)


class TestPrepare(unittest.TestCase):
    def test_prepare_writes_script_project_and_manifest(self):
        solver = OpenEMSSolver()
        with tempfile.TemporaryDirectory() as tmp:
            rundir = solver.prepare(make_project(), tmp)
            self.assertTrue((rundir / "sim.py").exists())
            self.assertTrue((rundir / "project.json").exists())
            manifest = (rundir / "run_manifest.json").read_text(encoding="utf-8")
            self.assertIn('"verified": false', manifest)

    def test_manifest_reports_the_solver_warnings(self):
        solver = OpenEMSSolver()
        with tempfile.TemporaryDirectory() as tmp:
            rundir = solver.prepare(make_project(nx=4, ny=4), tmp)
            manifest = (rundir / "run_manifest.json").read_text(encoding="utf-8")
            self.assertIn("unit-cell", manifest)


class TestAvailability(unittest.TestCase):
    def test_status_object_is_always_returned(self):
        status = OpenEMSSolver().available()
        self.assertEqual(status.name, "openems")
        self.assertIsInstance(status.available, bool)
        self.assertTrue(status.detail)

    def test_run_refuses_to_fake_results_when_unavailable(self):
        solver = OpenEMSSolver()
        status = solver.available()
        if status.available:
            self.skipTest("openEMS is installed here; the unavailable path cannot be exercised")
        with tempfile.TemporaryDirectory() as tmp:
            rundir = solver.prepare(make_project(), tmp)
            with self.assertRaises(SolverUnavailableError):
                solver.run(rundir)


class TestResultParsing(unittest.TestCase):
    def test_parse_results_reads_a_port_csv(self):
        solver = OpenEMSSolver()
        rows = ["freq_hz,s11_re,s11_im"]
        for i in range(21):
            freq = 2.0e9 + i * 50e6
            magnitude = 0.9 if i not in (10,) else 0.2
            rows.append(f"{freq:.6e},{magnitude:.6e},0.0")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s11.csv"
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            result = solver.parse_results(tmp)
        self.assertEqual(len(result["frequencies_hz"]), 21)
        self.assertAlmostEqual(result["worst_match_db"], 20.0 * -0.69897, delta=0.01)
        self.assertAlmostEqual(result["resonance_hz"], 2.5e9, delta=1.0)
        self.assertFalse(result["verified"])

    def test_missing_csv_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                OpenEMSSolver().parse_results(tmp)


if __name__ == "__main__":
    unittest.main()
