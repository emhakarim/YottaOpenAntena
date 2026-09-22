"""Phase-2 #7: convergence must travel with the number.

A run that hit the timestep cap cannot support a resonance claim, so the flag has
to reach the sweep summary, the printed table and the CSV — not stop at
``parse_results``.  These tests use a stub adapter, so no solver is needed.
"""

from __future__ import annotations

import csv
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
from openantenna.solvers.base import SolverAdapter, SolverRun, SolverStatus
from openantenna.sweep.engine import SweepAxis
from openantenna.sweep.runner import run_sweep


class ConvergenceStub(SolverAdapter):
    """Stub that alternates converged / not-converged results between jobs."""

    name = "stub"

    def __init__(self) -> None:
        self.calls = 0

    def available(self) -> SolverStatus:
        return SolverStatus(name=self.name, available=True, detail="stub")

    def prepare(self, project: Project, rundir) -> Path:
        path = Path(rundir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def run(self, rundir, timeout_s=None) -> SolverRun:
        return SolverRun(rundir=Path(rundir), status="ok", returncode=0, log="stub")

    def parse_results(self, rundir):
        self.calls += 1
        converged = self.calls % 2 == 1  # first job converged, second one not
        return {
            "resonance_hz": 2.4e9,
            "worst_match_db": -12.0,
            "vswr_at_resonance": 1.5,
            "fractional_bandwidth": 0.01,
            "converged": converged,
            "convergence_note": "stub: end criteria reached" if converged else "stub: timestep cap hit",
        }


def _project() -> Project:
    return Project(
        name="convergence-probe",
        substrate=SubstrateStackup.single("PTFE", 1.6e-3),
        patch=PatchGeometry(width_m=0.049, length_m=0.041, feed_mode="inset"),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.083e9, stop_hz=2.817e9, points=101),
    )


class TestConvergenceReporting(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / "sweep"
        self.stub = ConvergenceStub()
        self.summary = run_sweep(
            _project(),
            [SweepAxis("substrate.layers.0.thickness_m", (0.0008, 0.0016))],
            self.out,
            solver_factory=lambda **_: self.stub,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_flag_reaches_every_job_entry(self):
        flags = [entry.get("converged") for entry in self.summary.results]
        self.assertEqual(flags, [True, False])
        self.assertIn("timestep cap", self.summary.results[1]["convergence_note"])

    def test_the_summary_counts_unconverged_jobs(self):
        self.assertEqual(self.summary.unconverged, 1)
        self.assertEqual(self.summary.to_dict()["unconverged"], 1)

    def test_the_printed_table_warns(self):
        table = self.summary.table()
        self.assertIn("conv", table)
        self.assertIn("WARNING", table)
        self.assertIn("must NOT be quoted", table)

    def test_the_csv_carries_the_flag(self):
        with (self.out / "sweep_results.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertIn("converged", rows[0])
        self.assertEqual(rows[0]["converged"], "True")
        self.assertEqual(rows[1]["converged"], "False")

    def test_the_json_summary_records_it(self):
        payload = json.loads((self.out / "sweep_results.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["unconverged"], 1)
        self.assertIs(payload["results"][1]["converged"], False)


if __name__ == "__main__":
    unittest.main()
