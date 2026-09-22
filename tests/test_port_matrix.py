"""Phase 2 #4: S-matrix assembly, and the regression for the unbounded port object."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openantenna.model.project import ArrayConfig, FrequencySweep, Project, SubstrateStackup
from openantenna.solvers.openems import OpenEMSSolver
from yotta_tools import port_matrix


def _project() -> Project:
    project = Project(
        name="array",
        substrate=SubstrateStackup(layers=[{"material": "PTFE", "thickness_m": 1.6e-3}]),
        sweep=FrequencySweep(start_hz=2.4e9, stop_hz=2.5e9, points=3),
        array=ArrayConfig(nx=2, ny=2, spacing_x_lambda0=0.5, spacing_y_lambda0=0.5),
    )
    # element ports are probe-style for now: the generator refuses to combine them with a
    # printed feed line (per-element lines belong to the corporate feed, Phase 2 #5).
    project.patch.feed_line_width_m = 0.0
    return project


class TestRenderedScript(unittest.TestCase):
    def test_the_driven_port_is_bound_so_main_can_run(self):
        """Regression: the element loop used to discard the port objects -> NameError."""
        script = OpenEMSSolver(element_ports=True).render_script(_project())
        self.assertIn("ELEMENT_PORTS_OBJS = []", script)
        self.assertIn("ELEMENT_PORTS_OBJS.append(", script)
        self.assertIn("port = ELEMENT_PORTS_OBJS[0]", script)
        self.assertIn("port = driven", script)

    def test_every_port_is_dumped(self):
        script = OpenEMSSolver(element_ports=True).render_script(_project())
        self.assertIn('"port_%d.csv" % index', script)
        self.assertIn("uf_inc_re", script)
        self.assertIn("uf_ref_im", script)

    def test_single_port_path_stays_the_default(self):
        # Both branches are always *present* as script text - only the runtime value of
        # ELEMENT_PORTS picks one - so the assertion is about the selection, not the text.
        script = OpenEMSSolver().render_script(_project())
        self.assertIn("ELEMENT_PORTS = False", script)
        self.assertIn("port = FDTD.AddLumpedPort(", script)


def _write_port(path: Path, freqs, inc, ref) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write("freq_hz,uf_inc_re,uf_inc_im,uf_ref_re,uf_ref_im\n")
        for f, i, r in zip(freqs, inc, ref):
            handle.write(f"{f:.6e},{i.real:.9e},{i.imag:.9e},{r.real:.9e},{r.imag:.9e}\n")


class TestAssembly(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.freqs = [2.40e9, 2.45e9, 2.50e9]

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, name: str, driven: int, coupling: complex, match: complex) -> Path:
        run = self.root / name
        run.mkdir(parents=True)
        for i in (1, 2):
            inc = [complex(1.0, 0.0) if i == driven else complex(0.0, 0.0)] * 3
            ref = [match if i == driven else coupling] * 3
            _write_port(run / f"port_{i}.csv", self.freqs, inc, ref)
        (run / "run_summary.json").write_text(
            '{"converged": false, "runtime_s": 12.0}', encoding="utf-8"
        )
        return run

    def test_matrix_is_assembled_from_one_run_per_port(self):
        a = self._run("a", driven=1, coupling=0.05 + 0j, match=0.2 + 0j)
        b = self._run("b", driven=2, coupling=0.05 + 0j, match=0.3 + 0j)
        result = port_matrix.assemble([(a, 1), (b, 2)], n_ports=2)
        self.assertAlmostEqual(abs(result["s"][0][0][0]), 0.2)
        self.assertAlmostEqual(abs(result["s"][1][0][0]), 0.05, msg="S21 from run a")
        self.assertAlmostEqual(abs(result["s"][0][1][0]), 0.05, msg="S12 from run b")
        self.assertAlmostEqual(abs(result["s"][1][1][0]), 0.3)

    def test_missing_port_file_is_an_error_not_a_zero(self):
        run = self._run("a", driven=1, coupling=0.05, match=0.2)
        (run / "port_2.csv").unlink()
        with self.assertRaises(FileNotFoundError):
            port_matrix.assemble([(run, 1)], n_ports=2)

    def test_convergence_state_is_kept_and_reported(self):
        a = self._run("a", driven=1, coupling=0.05, match=0.2)
        b = self._run("b", driven=2, coupling=0.05, match=0.2)
        result = port_matrix.assemble([(a, 1), (b, 2)], n_ports=2)
        self.assertEqual([entry["converged"] for entry in result["runs"]], [False, False])
        summary = port_matrix.coupling_summary(result, index=0)
        self.assertLess(summary["s11_db"], 0.0)
        self.assertLess(summary["worst_coupling_db"], summary["s11_db"])

    def test_bad_driven_port_is_rejected(self):
        run = self._run("a", driven=1, coupling=0.05, match=0.2)
        with self.assertRaises(ValueError):
            port_matrix.assemble([(run, 3)], n_ports=2)


if __name__ == "__main__":
    unittest.main()
