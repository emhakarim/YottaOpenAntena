"""Real sweep execution: enumerate jobs, run them, record the results.

``sweep/engine.py`` only *enumerates* jobs.  This module executes them: for each
job it prepares a model, runs the solver through an adapter, parses the result,
records it in the sqlite store and finally writes a summary plus a CSV.

The adapter factory is injectable so the whole orchestration can be tested with a
stub adapter, without openEMS.  The stub lives in the test file and is never part
of the production path: a run that did not happen is never recorded as a result.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from ..model.project import Project
from ..solvers.base import SolverAdapter, SolverUnavailableError
from ..solvers.openems import OpenEMSSolver
from ..store.results import ResultsStore
from .engine import ParameterSweep, SweepAxis


@dataclass
class SweepRunSummary:
    """Outcome of one sweep execution."""

    out_dir: Path
    job_count: int
    completed: int
    failed: int
    results: List[Dict[str, Any]] = field(default_factory=list)
    store_path: Optional[str] = None
    #: jobs whose solver output says the timestep cap was reached (or has no log)
    unconverged: int = 0

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.completed == self.job_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "out_dir": str(self.out_dir),
            "job_count": self.job_count,
            "completed": self.completed,
            "failed": self.failed,
            "unconverged": self.unconverged,
            "store_path": self.store_path,
            "results": self.results,
        }

    def table(self) -> str:
        lines = [
            f"{'job':<40}{'resonance [GHz]':>16}{'|S11| [dB]':>12}{'VSWR':>8}{'conv':>7}"
        ]
        lines.append("-" * 80)
        for entry in self.results:
            resonance = entry.get("resonance_hz")
            match = entry.get("worst_match_db")
            vswr = entry.get("vswr")
            lines.append(
                f"{entry['job_id'][:39]:<40}"
                f"{(resonance / 1e9 if resonance else float('nan')):>16.4f}"
                f"{(match if match is not None else float('nan')):>12.2f}"
                f"{(vswr if vswr is not None else float('nan')):>8.3f}"
                f"{(str(entry.get('converged')) if entry.get('converged') is not None else '?'):>7}"
            )
        lines.append("-" * 80)
        lines.append(f"completed {self.completed}/{self.job_count}, failed {self.failed}")
        if self.unconverged:
            lines.append(
                f"WARNING: {self.unconverged} job(s) did NOT converge (timestep cap reached or "
                "no solver log): their resonance values must NOT be quoted as results."
            )
        return "\n".join(lines)


def run_sweep(
    project: Project,
    axes: Sequence[SweepAxis],
    out_dir: str | Path,
    solver_factory: Callable[..., SolverAdapter] = OpenEMSSolver,
    solver_kwargs: Optional[Dict[str, Any]] = None,
    store_path: Optional[str | Path] = None,
    stop_on_error: bool = False,
) -> SweepRunSummary:
    """Execute every job of a parameter sweep and record the results.

    Raises :class:`SolverUnavailableError` before doing any work when the solver
    cannot run, so a sweep never silently produces an empty result set.
    """
    solver_kwargs = dict(solver_kwargs or {})
    sweep = ParameterSweep(project, axes)
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)

    solver = solver_factory(**solver_kwargs)
    status = solver.available()
    if not status.available:
        raise SolverUnavailableError(
            f"cannot run a sweep: {status.detail}. Model generation and "
            "sweep enumeration still work without a solver."
        )

    store: Optional[ResultsStore] = ResultsStore(store_path) if store_path else None
    summary = SweepRunSummary(
        out_dir=root,
        job_count=sweep.job_count,
        completed=0,
        failed=0,
        store_path=str(store_path) if store_path else None,
    )

    try:
        for job in sweep.jobs():
            job_dir = root / job.job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            entry: Dict[str, Any] = {"job_id": job.job_id, "overrides": job.overrides}
            try:
                job_project = sweep.project_for(job)
                solver.prepare(job_project, job_dir)
                run = solver.run(job_dir)
                entry["solver_status"] = run.status
                entry["returncode"] = run.returncode
                if run.status != "ok":
                    raise RuntimeError(f"solver returned {run.status} ({run.returncode})")
                parsed = solver.parse_results(job_dir)
                entry.update(
                    {
                        "resonance_hz": parsed.get("resonance_hz"),
                        "worst_match_db": parsed.get("worst_match_db"),
                        "vswr": parsed.get("vswr_at_resonance"),
                        "fractional_bandwidth": parsed.get("fractional_bandwidth"),
                        # Convergence travels with the number: a run that hit the
                        # timestep cap cannot support a resonance claim
                        # (Phase 2 convergence reporting; review item N-02).
                        "converged": parsed.get("converged"),
                        "convergence_note": parsed.get("convergence_note"),
                    }
                )
                if parsed.get("converged") is False:
                    summary.unconverged += 1
                summary.completed += 1
                if store is not None:
                    store.save_run(
                        job.job_id,
                        job_project.to_dict(),
                        status="ok",
                        results=parsed,
                        note=f"sweep of {len(axes)} axis/axes",
                    )
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
                summary.failed += 1
                if store is not None:
                    store.save_run(
                        job.job_id,
                        project.to_dict(),
                        status="failed",
                        note=entry["error"],
                    )
                if stop_on_error:
                    summary.results.append(entry)
                    raise
            summary.results.append(entry)
    finally:
        if store is not None:
            store.close()

    (root / "sweep_results.json").write_text(
        json.dumps(summary.to_dict(), indent=2, default=str) + "\n", encoding="utf-8"
    )
    with (root / "sweep_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["job_id", "overrides", "resonance_hz", "worst_match_db", "vswr", "converged", "error"]
        )
        for entry in summary.results:
            writer.writerow(
                [
                    entry["job_id"],
                    json.dumps(entry["overrides"], default=str),
                    entry.get("resonance_hz", ""),
                    entry.get("worst_match_db", ""),
                    entry.get("vswr", ""),
                    entry.get("converged", ""),
                    entry.get("error", ""),
                ]
            )
    return summary
