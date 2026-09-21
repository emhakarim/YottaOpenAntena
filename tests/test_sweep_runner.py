"""Tests for real sweep execution, using a stub solver adapter.

The stub produces a **synthetic** S11 curve so that the orchestration can be
tested without openEMS: job enumeration, per-job prepare/run/parse, store
records, the summary and the CSV.  The stub is a test double and never part of the
production path - a production run that did not happen is never recorded as a
result.
"""

from __future__ import annotations

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
from openantenna.solvers.base import SolverAdapter, SolverRun, SolverStatus, SolverUnavailableError
from openantenna.solvers.openems import OpenEMSSolver
from openantenna.store.results import ResultsStore
from openantenna.sweep.engine import SweepAxis
from openantenna.sweep.runner import run_sweep


class StubSolver(SolverAdapter):
    """A solver double: writes a synthetic S11 dip and reuses the real parser."""

    name = "stub"

    def __init__(
        self,
        resonance_hz: float = 2.40e9,
        available: bool = True,
        fail_when=None,
        **kwargs,
    ) -> None:
        self.resonance_hz = resonance_hz
        self._available = available
        self.fail_when = fail_when or (lambda project: False)
        self.prepared: list[Path] = []
        self.extra = kwargs

    def available(self) -> SolverStatus:
        return SolverStatus(
            name=self.name,
            available=self._available,
            detail="stub adapter" if self._available else "stub reports unavailable",
        )

    def prepare(self, project: Project, rundir) -> Path:
        path = Path(rundir)
        path.mkdir(parents=True, exist_ok=True)
        (path / "project.json").write_text(project.to_json(), encoding="utf-8")
        self.prepared.append(path)
        return path.resolve()

    def run(self, rundir, timeout_s=None) -> SolverRun:
        path = Path(rundir)
        if self.fail_when(json.loads((path / "project.json").read_text(encoding="utf-8"))):
            return SolverRun(path, status="failed", returncode=1, log="stub failure")
        rows = ["freq_hz,s11_re,s11_im"]
        for i in range(21):
            frequency = 2.0e9 + i * 50e6
            magnitude = 0.05 if abs(frequency - self.resonance_hz) < 1e7 else 0.9
            rows.append(f"{frequency:.6e},{magnitude:.6e},0.0")
        (path / "s11.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
        return SolverRun(path, status="ok", returncode=0, log="stub run")

    def parse_results(self, rundir):
        # Reuse the production parser on the stub's synthetic CSV.
        return OpenEMSSolver().parse_results(rundir)


def make_project() -> Project:
    return Project(
        name="sweep-unit",
        substrate=SubstrateStackup.single("PTFE", 1.6e-3),
        patch=PatchGeometry(width_m=0.037, length_m=0.037, feed_mode="inset", feed_inset_m=0.01),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.0e9, stop_hz=3.0e9, points=21),
    )


class TestRunSweep(unittest.TestCase):
    def test_every_job_runs_and_is_recorded(self):
        axes = [SweepAxis.parse("substrate.layers.0.thickness_m=0.0016,0.0032")]
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "runs.sqlite"
            summary = run_sweep(
                make_project(),
                axes,
                Path(tmp) / "out",
                solver_factory=StubSolver,
                store_path=store_path,
            )
            self.assertEqual(summary.job_count, 2)
            self.assertEqual(summary.completed, 2)
            self.assertEqual(summary.failed, 0)
            self.assertTrue((Path(tmp) / "out" / "sweep_results.json").exists())
            self.assertTrue((Path(tmp) / "out" / "sweep_results.csv").exists())
            for entry in summary.results:
                self.assertIn("resonance_hz", entry)
                self.assertIn("worst_match_db", entry)
            with ResultsStore(store_path) as store:
                self.assertEqual(store.count(), 2)
                statuses = {row["status"] for row in store.list_runs()}
            self.assertEqual(statuses, {"ok"})

    def test_failure_is_recorded_and_does_not_stop_the_sweep(self):
        def fail_second(project_doc: dict) -> bool:
            return project_doc["substrate"]["layers"][0]["thickness_m"] > 0.002

        axes = [SweepAxis.parse("substrate.layers.0.thickness_m=0.0016,0.0032")]
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "runs.sqlite"
            summary = run_sweep(
                make_project(),
                axes,
                Path(tmp) / "out",
                solver_factory=lambda **kw: StubSolver(fail_when=fail_second, **kw),
                store_path=store_path,
            )
            self.assertEqual(summary.completed, 1)
            self.assertEqual(summary.failed, 1)
            failed = [e for e in summary.results if "error" in e]
            self.assertEqual(len(failed), 1)
            with ResultsStore(store_path) as store:
                statuses = sorted(row["status"] for row in store.list_runs())
            self.assertEqual(statuses, ["failed", "ok"])

    def test_unavailable_solver_refuses_before_doing_work(self):
        axes = [SweepAxis.parse("substrate.layers.0.thickness_m=0.0016,0.0032")]
        with tempfile.TemporaryDirectory() as tmp:
            stub = StubSolver(available=False)
            with self.assertRaises(SolverUnavailableError):
                run_sweep(
                    make_project(),
                    axes,
                    Path(tmp) / "out",
                    solver_factory=lambda **kw: stub,
                )
            self.assertEqual(stub.prepared, [])

    def test_csv_contains_one_row_per_job(self):
        axes = [SweepAxis.parse("patch.length_m=0.036,0.038")]
        with tempfile.TemporaryDirectory() as tmp:
            run_sweep(
                make_project(),
                axes,
                Path(tmp) / "out",
                solver_factory=StubSolver,
            )
            rows = (Path(tmp) / "out" / "sweep_results.csv").read_text(
                encoding="utf-8"
            ).strip().splitlines()
        self.assertEqual(len(rows), 3)  # header + 2 jobs


class TestMaterialAxis(unittest.TestCase):
    def test_empty_axis_values_are_rejected(self):
        """Mutation guard M11 (Yotta round 6): an empty value tuple must never
        produce a job list that silently does nothing."""
        with self.assertRaises(ValueError):
            SweepAxis("substrate.layers.0.thickness_m", ())

    def test_string_values_are_accepted_for_a_material_sweep(self):
        axis = SweepAxis.parse("substrate.layers.0.material=PTFE,RO4003C,FR-4")
        self.assertEqual(axis.values, ("PTFE", "RO4003C", "FR-4"))

    def test_numeric_values_still_parse_as_numbers(self):
        axis = SweepAxis.parse("sweep.points=51,101")
        self.assertEqual(axis.values, (51, 101))
        self.assertIsInstance(axis.values[0], int)

    def test_mixed_numeric_scale_is_float(self):
        axis = SweepAxis.parse("substrate.layers.0.thickness_m=0.0008,0.0016")
        self.assertEqual(axis.values, (0.0008, 0.0016))

    def test_material_sweep_runs_through_the_runner(self):
        axes = [SweepAxis.parse("substrate.layers.0.material=PTFE,FR-4")]
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_sweep(
                make_project(),
                axes,
                Path(tmp) / "out",
                solver_factory=StubSolver,
            )
        self.assertEqual(summary.completed, 2)
        self.assertTrue(
            any(e["overrides"]["substrate.layers.0.material"] == "FR-4" for e in summary.results)
        )


if __name__ == "__main__":
    unittest.main()
