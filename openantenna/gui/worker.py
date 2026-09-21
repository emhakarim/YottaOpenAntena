"""Solver worker thread for the GUI.

Running a simulation takes minutes, so it must never block the Qt event loop.
The worker owns one ``OpenEMSSolver`` invocation end to end: prepare, run, parse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import QThread, Signal

from ..model.project import Project
from ..solvers.base import SolverUnavailableError
from ..solvers.openems import OpenEMSSolver


class GenerateWorker(QThread):
    """Write the solver input deck for a project (fast, no solver needed)."""

    done = Signal(str)
    failed = Signal(str)

    def __init__(self, project: Project, rundir: Path, **solver_kwargs: Any) -> None:
        super().__init__()
        self.project = project
        self.rundir = Path(rundir)
        self.solver_kwargs = solver_kwargs

    def run(self) -> None:  # noqa: D102 - Qt entry point
        try:
            solver = OpenEMSSolver(**self.solver_kwargs)
            prepared = solver.prepare(self.project, self.rundir)
        except Exception as exc:  # surfaced to the user, never swallowed
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(str(prepared))


class SimulateWorker(QThread):
    """Prepare, run and parse one simulation."""

    progress = Signal(str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        project: Project,
        rundir: Path,
        timeout_s: float | None = 3600.0,
        **solver_kwargs: Any,
    ) -> None:
        super().__init__()
        self.project = project
        self.rundir = Path(rundir)
        # A hung external solver must not block the worker for ever: the thread
        # cannot be cancelled, so the run itself carries a timeout (review G-3).
        self.timeout_s = timeout_s
        self.solver_kwargs = solver_kwargs

    def run(self) -> None:  # noqa: D102 - Qt entry point
        try:
            solver = OpenEMSSolver(**self.solver_kwargs)
            status = solver.available()
            self.progress.emit(f"solver availability: {status.available} - {status.detail}")
            if not status.available:
                raise SolverUnavailableError(status.detail)

            self.progress.emit("generating the model ...")
            prepared = solver.prepare(self.project, self.rundir)
            self.progress.emit(f"model written to {prepared}")

            self.progress.emit("running the solver (this takes minutes; the window stays responsive) ...")
            run = solver.run(prepared, timeout_s=self.timeout_s)
            self.progress.emit(f"solver exited with status {run.status} (code {run.returncode})")
            if run.status != "ok":
                raise RuntimeError(f"solver run failed; log tail:\n{run.log[-2000:]}")

            self.progress.emit("parsing results ...")
            parsed = solver.parse_results(prepared)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit({"rundir": str(self.rundir), "results": parsed})
