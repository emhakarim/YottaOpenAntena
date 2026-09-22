"""Tests for the package-side coupling reader (Phase 2 #4, toolkit half).

The runs are synthetic: these tests check the *reading and the honesty rules*, not the solver.
What must hold: the S-matrix is assembled from per-port dumps, a missing port file is an error
rather than a zero, an unconverged run is refused, and the trend groups by element distance.
"""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from openantenna.postproc.port_matrix import (
    PORT_HEADER,
    assemble,
    read_port_csv,
)

FREQS = [2.40e9, 2.45e9, 2.50e9]


def write_port(path: Path, *, incident: complex, reflected: complex) -> None:
    lines = [",".join(PORT_HEADER)]
    for f in FREQS:
        lines.append(
            f"{f:.6e},{incident.real:.6e},{incident.imag:.6e},{reflected.real:.6e},{reflected.imag:.6e}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_run(root: Path, driven: int, n_ports: int, *, converged: bool | None = True) -> Path:
    """A run directory whose port files encode a known, simple matrix.

    Port ``p`` reflects ``r`` when driven, and couples to every other port with ``c``.
    """
    run = root / f"run_p{driven}"
    run.mkdir(parents=True, exist_ok=True)
    for port in range(1, n_ports + 1):
        if port == driven:
            write_port(run / f"port_{port}.csv", incident=1 + 0j, reflected=0.2 + 0.1j)
        else:
            write_port(run / f"port_{port}.csv", incident=1 + 0j, reflected=0.05 + 0j)
    if converged is not None:
        (run / "run_summary.json").write_text(
            json.dumps({"converged": converged, "timesteps": 1000}), encoding="utf-8"
        )
    return run


class TestReading(unittest.TestCase):
    def test_reads_a_well_formed_port_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "port_1.csv"
            write_port(path, incident=1 + 0j, reflected=0.5 + 0j)
            trace = read_port_csv(path)
        self.assertEqual(trace.frequencies_hz, FREQS)
        self.assertEqual(trace.uf_inc, [1 + 0j, 1 + 0j, 1 + 0j])
        self.assertEqual(trace.uf_ref[0], 0.5 + 0j)

    def test_a_wrong_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "port_1.csv"
            path.write_text("freq,garbage\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                read_port_csv(path)
        self.assertIn("unexpected header", str(ctx.exception))


class TestAssembly(unittest.TestCase):
    def test_assembles_the_matrix_from_per_port_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = [(make_run(root, p, 3), p) for p in (1, 2, 3)]
            matrix = assemble(runs, n_ports=3)
        self.assertEqual(matrix.n_ports, 3)
        used, s = matrix.at(2.45e9)
        self.assertAlmostEqual(used, 2.45e9)
        # diagonal: reflection of the driven port
        self.assertAlmostEqual(abs(s[0][0]), abs(0.2 + 0.1j), places=9)
        # off-diagonal: the coupling encoded in the synthetic runs
        self.assertAlmostEqual(abs(s[1][0]), 0.05, places=9)
        self.assertAlmostEqual(abs(s[0][1]), 0.05, places=9)

    def test_a_missing_port_file_is_an_error_not_a_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = make_run(root, 1, 3)
            (run / "port_3.csv").unlink()
            with self.assertRaises(ValueError) as ctx:
                assemble([(run, 1), (make_run(root, 2, 3), 2), (make_run(root, 3, 3), 3)], 3)
        self.assertIn("missing", str(ctx.exception))
        self.assertIn("never a zero", str(ctx.exception))

    def test_a_missing_column_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError) as ctx:
                assemble([(make_run(root, 1, 3), 1)], n_ports=3)
        self.assertIn("no run drove port", str(ctx.exception))

    def test_an_unconverged_run_is_refused_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = [
                (make_run(root, 1, 2), 1),
                (make_run(root, 2, 2, converged=False), 2),
            ]
            with self.assertRaises(ValueError) as ctx:
                assemble(runs, n_ports=2)
            self.assertIn("convergence-policy", str(ctx.exception))
            exploratory = assemble(runs, n_ports=2, require_convergence=False)
        self.assertFalse(exploratory.require_convergence)
        self.assertEqual(exploratory.converged[2], False)

    def test_a_run_that_records_no_convergence_is_also_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = [(make_run(root, p, 2, converged=None), p) for p in (1, 2)]
            with self.assertRaises(ValueError):
                assemble(runs, n_ports=2)

    def test_the_same_port_cannot_be_driven_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = [(make_run(root, 1, 2), 1), (make_run(root, 1, 2), 1)]
            with self.assertRaises(ValueError) as ctx:
                assemble(runs, n_ports=2)
        self.assertIn("twice", str(ctx.exception))


class TestReports(unittest.TestCase):
    def test_coupling_summary_reports_the_worst_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = [(make_run(root, p, 3), p) for p in (1, 2, 3)]
            matrix = assemble(runs, n_ports=3)
        summary = matrix.coupling_summary(2.45e9)
        self.assertAlmostEqual(summary["worst_magnitude"], 0.05, places=9)
        self.assertAlmostEqual(summary["mean_magnitude"], 0.05, places=9)
        self.assertEqual(len(summary["pairs"]), 6)  # 3x3 minus the diagonal
        self.assertIn("only meaningful", summary["note"])

    def test_the_trend_groups_by_element_distance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = [(make_run(root, p, 3), p) for p in (1, 2, 3)]
            matrix = assemble(runs, n_ports=3)
        spacing = 0.5 * 0.1224
        positions = [(0.0, 0.0), (spacing, 0.0), (2 * spacing, 0.0)]
        trend = matrix.coupling_vs_spacing(positions, 2.45e9)
        self.assertEqual(len(trend), 3)
        self.assertAlmostEqual(trend[0]["distance_m"], spacing, places=9)
        self.assertAlmostEqual(trend[-1]["distance_m"], 2 * spacing, places=9)
        self.assertTrue(all(math.isfinite(entry["mutual_db"]) for entry in trend))
        with self.assertRaises(ValueError):
            matrix.coupling_vs_spacing(positions[:2], 2.45e9)


if __name__ == "__main__":
    unittest.main()
