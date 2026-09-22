"""Tests for the openEMS adapter: script generation, honest availability, parsing.

The generated script is inspected statically and parsed; it is NOT executed by
this test suite.  Executing it requires an openEMS/CSXCAD installation, and the
tests must stay meaningful on a machine without one.
"""

from __future__ import annotations

import ast
import json
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

    def test_ground_margin_is_rendered_and_sweepable(self):
        """N-01: the ground-plane margin must be a knob, not a hidden constant."""
        self.assertIn("GROUND_MARGIN_LAMBDA", self.script)
        self.assertIn("GROUND:", self.script)
        from openantenna.solvers.openems import OpenEMSSolver

        wider = OpenEMSSolver(ground_margin_lambda=0.75)
        rendered = wider.render_script(make_project())
        self.assertIn("GROUND_MARGIN_LAMBDA = 0.75", rendered)

    def test_construction_settings_are_configurable(self):
        """Phase-1 completion: boundary, PML cells, smoothing and convergence are knobs."""
        solver = OpenEMSSolver(
            boundary="MUR",
            pml_cells=6,
            mesh_smoothing_ratio=1.2,
            max_timesteps=50000,
            end_criteria=1e-5,
        )
        script = solver.render_script(make_project())
        self.assertIn('FDTD.SetBoundaryCond(["MUR"] * 6)', script)
        self.assertIn('BOUNDARY_MODE = "MUR"', script)
        self.assertIn("MESH_SMOOTHING = 1.2", script)
        self.assertIn("MAX_TS = 50000", script)
        self.assertIn("END_CRITERIA = 1e-05", script)

        pml = OpenEMSSolver(boundary="PML", pml_cells=6).render_script(make_project())
        self.assertIn("PML_CELLS = 6", pml)
        self.assertIn('% PML_CELLS] * 6)', pml)
        self.assertIn('BOUNDARY_MODE = "PML"', pml)

    def test_settings_are_recorded_in_the_manifest(self):
        solver = OpenEMSSolver(boundary="MUR", pml_cells=6, max_timesteps=12345)
        with tempfile.TemporaryDirectory() as tmp:
            rundir = solver.prepare(make_project(), tmp)
            manifest = json.loads((rundir / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["boundary"], "MUR")
        self.assertEqual(manifest["pml_cells"], 6)
        self.assertEqual(manifest["max_timesteps"], 12345)
        self.assertEqual(manifest["mesh"]["pml_cells"], 6)
        self.assertIn("ground_margin_lambda", manifest)

    def test_adapter_defaults_are_part_of_the_contract(self):
        """Mutation guard M13 (Yotta round 6): the defaults are a documented
        contract - changing them silently would change every generated model."""
        solver = OpenEMSSolver()
        self.assertEqual(solver.end_criteria, 1e-4)
        self.assertEqual(solver.pml_cells, 8)
        self.assertEqual(solver.boundary, "PML")
        self.assertEqual(solver.mesh_cells_per_wavelength, 15)
        self.assertEqual(solver.substrate_cells, 8)
        self.assertEqual(solver.ground_margin_lambda, 0.25)
        self.assertEqual(solver.mesh_smoothing_ratio, 1.4)
        self.assertTrue(solver.metal_edge_snapping)
        self.assertEqual(solver.loss_model, "kappa")

    def test_invalid_settings_are_rejected(self):
        with self.assertRaises(ValueError):
            OpenEMSSolver(boundary="ABC")
        with self.assertRaises(ValueError):
            OpenEMSSolver(pml_cells=1)
        with self.assertRaises(ValueError):
            OpenEMSSolver(mesh_smoothing_ratio=1.0)
        with self.assertRaises(ValueError):
            OpenEMSSolver(max_timesteps=10)
        with self.assertRaises(ValueError):
            OpenEMSSolver(end_criteria=0.0)
        with self.assertRaises(ValueError):
            OpenEMSSolver(ground_margin_lambda=0.0)

    def test_construction_knobs_are_reachable_without_editing_source(self):
        """A-7: the A/B knobs (port refinement, edge snapping, NF2FF) and the
        far-field recorder must be controllable from outside the package."""
        off = OpenEMSSolver(port_refine=False, metal_edge_snapping=False, nf2ff=False)
        script = off.render_script(make_project())
        self.assertIn("PORT_REFINE = False", script)
        self.assertIn("METAL_EDGE_SNAPPING = False", script)
        self.assertIn("NF2FF_ENABLED = False", script)
        self.assertIn("NF2FF_FREQS = ", script)

        on = OpenEMSSolver(nf2ff=True, nf2ff_frequencies=7)
        manifest_script = on.render_script(make_project())
        self.assertIn("NF2FF_ENABLED = True", manifest_script)
        self.assertIn("NF2FF_FREQS = 7", manifest_script)
        # the far-field block writes a summary and a pattern for our own reader
        self.assertIn("nf2ff_summary.csv", manifest_script)
        self.assertIn("nf2ff_pattern.csv", manifest_script)
        self.assertIn("eta_rad", manifest_script)

    def test_nf2ff_frequency_count_is_validated(self):
        with self.assertRaises(ValueError):
            OpenEMSSolver(nf2ff_frequencies=0)

    def test_nf2ff_setting_is_recorded_in_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = OpenEMSSolver(nf2ff=False).prepare(make_project(), tmp)
            manifest = json.loads((rundir / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["nf2ff"])
        self.assertIn("nf2ff_frequencies", manifest)

    def test_rendered_script_is_valid_python(self):
        """A generated model must at least compile.

        This guard exists because a template bug (a literal newline inside a string)
        produced 'SyntaxError: unterminated string literal' in a generated script, and
        nothing noticed until a solver run was attempted minutes later.  Compiling the
        rendered text is instant and catches that whole class of defect.
        """
        variants = [
            {},
            {"nf2ff": False},
            {"nf2ff": True, "nf2ff_frequencies": 3},
            {"port_refine": False},
            {"metal_edge_snapping": False},
            {"boundary": "MUR"},
            {"ground_margin_lambda": 0.8},
            {"loss_model": "none"},
        ]
        for kwargs in variants:
            script = OpenEMSSolver(**kwargs).render_script(make_project())
            compile(script, "sim.py", "exec")

    def test_nf2ff_box_is_created_after_the_mesh(self):
        """A static ordering check for a runtime-only failure.

        openEMS raises "Error::CreateNF2FFBox: Grid is invalid" when the box is
        created before the mesh has lines.  That only shows up at run time, so the
        order is asserted here instead of waiting for a solver to tell us.
        """
        script = OpenEMSSolver(nf2ff=True).render_script(make_project())
        self.assertLess(
            script.index("SmoothMeshLines"),
            script.index("CreateNF2FFBox"),
            "the NF2FF box must be created after SmoothMeshLines",
        )
        self.assertLess(script.index("DOMAIN:"), script.index("CreateNF2FFBox"))
        # and the domain must leave the absorbing boundary enough room: openEMS
        # needs pml_cells of clearance, otherwise CreateNF2FFBox fails at run time
        solver = OpenEMSSolver()
        self.assertGreaterEqual(
            solver.mesh_cells_per_wavelength * solver.air_margin_lambda, solver.pml_cells
        )

    def test_unit_cell_uses_symmetry_walls_and_the_element_pitch(self):
        """Phase 2: an infinite-array unit cell at broadside.

        openEMS's Python API has no periodic boundary, so this is built from PEC/PMC
        symmetry walls - which is exact at broadside and must be labelled as such.
        """
        script = OpenEMSSolver(unit_cell=True).render_script(make_project(nx=4, ny=4))
        self.assertIn('["PEC", "PEC", "PMC", "PMC"', script)
        self.assertIn("broadside only", script)
        self.assertIn("UNIT_CELL = True", script)
        line = next(row for row in script.splitlines() if row.startswith("ELEMENTS = "))
        elements = ast.literal_eval(line.split("=", 1)[1].strip())
        self.assertEqual(len(elements), 1, "a unit cell contains exactly one element")
        # the lateral domain must be one element pitch, not ground + margin
        self.assertIn("DOM_X = GROUND_X / 2.0", script)

    def test_unit_cell_is_recorded_in_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = OpenEMSSolver(unit_cell=True).prepare(make_project(nx=2, ny=2), tmp)
            manifest = json.loads((rundir / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["unit_cell"])
        self.assertEqual(manifest["boundary"], "PML")  # the knob, not the rendered walls

    def test_finite_array_keeps_the_pml_boundary(self):
        script = OpenEMSSolver().render_script(make_project(nx=4, ny=4))
        self.assertIn("UNIT_CELL = False", script)
        self.assertNotIn('["PEC", "PEC", "PMC", "PMC"', script)

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
        # no solver log in this fixture -> convergence must be reported as unknown,
        # never silently assumed (review item N-02)
        self.assertFalse(result["converged"])
        self.assertIn("log not found", result["convergence_note"])

    def test_parse_results_reports_convergence_state(self):
        """N-02: a run that hit the timestep cap must not look converged."""
        rows = ["freq_hz,s11_re,s11_im"]
        for i in range(11):
            rows.append(f"{2.0e9 + i * 50e6:.6e},0.5,0.0")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s11.csv"
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            (Path(tmp) / "run.stdout.log").write_text(
                "Time for 400000 iterations with 20000.00 cells : 500.00 sec\n"
                "RunFDTD: Warning: Max. number of timesteps was reached before the "
                "end-criteria of -50dB was reached...\n",
                encoding="utf-8",
            )
            capped = OpenEMSSolver().parse_results(tmp)

        self.assertFalse(capped["converged"])
        self.assertIn("NOT converged", capped["convergence_note"])
        self.assertEqual(capped["timesteps"], 400000)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s11.csv"
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            (Path(tmp) / "run.stdout.log").write_text(
                "Time for 120000 iterations with 20000.00 cells : 200.00 sec\n",
                encoding="utf-8",
            )
            settled = OpenEMSSolver().parse_results(tmp)

        self.assertTrue(settled["converged"])
        self.assertEqual(settled["timesteps"], 120000)

    def test_missing_csv_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                OpenEMSSolver().parse_results(tmp)


if __name__ == "__main__":
    unittest.main()
