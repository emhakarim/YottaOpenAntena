"""Solver worker thread for the GUI.

Running a simulation takes minutes, so it must never block the Qt event loop.
The worker owns one ``OpenEMSSolver`` invocation end to end: prepare, run, parse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import QThread, Signal

from ..model.project import Project
from ..solvers.progress import SolverProgress, format_bar
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


class QueueWorker(QThread):
    """Run several prepared designs one after another, reporting per case.

    Sequential on purpose: the solver itself is already multithreaded, so two concurrent
    FDTD runs on this laptop fight over the same cores and memory bandwidth (measured:
    each got ~5 of 16 threads and the pair took longer than either alone).  A batch is
    about throughput of *results*, not of CPU.
    """

    case_started = Signal(int, str)
    progress = Signal(str)
    progress_value = Signal(int)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, cases: list, base_rundir: Path, **solver_kwargs: Any) -> None:
        super().__init__()
        self.cases = list(cases)
        self.base_rundir = Path(base_rundir)
        self.solver_kwargs = solver_kwargs
        self._cap_steps: int | None = None
        self._updates = 0

    def _on_progress(self, snapshot: SolverProgress) -> None:
        self._updates += 1
        cap = self._cap_steps
        if cap and snapshot.timestep:
            self.progress_value.emit(min(100, int(round(100.0 * snapshot.timestep / cap))))
        if self._updates % 10 == 1:
            self.progress.emit(format_bar(snapshot, cap))

    def run(self) -> None:  # noqa: D102 - Qt entry point
        results: list[dict] = []
        try:
            solver = OpenEMSSolver(**self.solver_kwargs)
            self._cap_steps = getattr(solver, "max_timesteps", None)
            status = solver.available()
            if not status.available:
                raise SolverUnavailableError(status.detail)
            for index, (label, project) in enumerate(self.cases):
                self.case_started.emit(index, label)
                rundir = self.base_rundir / _case_dirname(index, label)
                prepared = solver.prepare(project, rundir)
                self.progress.emit(f"[{index + 1}/{len(self.cases)}] {label}: {prepared}")
                run = solver.run(prepared, on_progress=self._on_progress)
                if run.status != "ok":
                    raise RuntimeError(
                        f"case '{label}' failed (code {run.returncode}); log tail:\n"
                        f"{run.log[-1500:]}"
                    )
                parsed = solver.parse_results(prepared)
                results.append({"label": label, "rundir": str(prepared), "results": parsed})
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(results)


def _case_dirname(index: int, label: str) -> str:
    """A filesystem-safe, order-preserving directory name for one queued case."""
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in label).strip("_")
    return f"case{index + 1:02d}_{safe or 'case'}"


class SimulateWorker(QThread):
    """Prepare, run and parse one simulation."""

    progress = Signal(str)
    progress_value = Signal(int)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, project: Project, rundir: Path, **solver_kwargs: Any) -> None:
        super().__init__()
        self.project = project
        self.rundir = Path(rundir)
        self.solver_kwargs = solver_kwargs
        self._cap_steps: int | None = None
        self._updates = 0

    def _on_progress(self, snapshot: SolverProgress) -> None:
        """Feed the solver's own progress to the bar, and occasionally to the log.

        Runs from the worker thread; the signals are delivered to the GUI thread, so
        touching widgets from here would be wrong.
        """
        self._updates += 1
        cap = self._cap_steps
        if cap and snapshot.timestep:
            self.progress_value.emit(min(100, int(round(100.0 * snapshot.timestep / cap))))
        if self._updates % 10 == 1:
            self.progress.emit(format_bar(snapshot, cap))

    def run(self) -> None:  # noqa: D102 - Qt entry point
        try:
            solver = OpenEMSSolver(**self.solver_kwargs)
            self._cap_steps = getattr(solver, "max_timesteps", None)
            status = solver.available()
            self.progress.emit(f"solver availability: {status.available} - {status.detail}")
            if not status.available:
                raise SolverUnavailableError(status.detail)

            self.progress.emit("generating the model ...")
            prepared = solver.prepare(self.project, self.rundir)
            self.progress.emit(f"model written to {prepared}")

            self.progress.emit("running the solver (this takes minutes; the window stays responsive) ...")
            run = solver.run(prepared, on_progress=self._on_progress)
            self.progress.emit(f"solver exited with status {run.status} (code {run.returncode})")
            if run.status != "ok":
                raise RuntimeError(f"solver run failed; log tail:\n{run.log[-2000:]}")

            self.progress.emit("parsing results ...")
            parsed = solver.parse_results(prepared)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit({"rundir": str(self.rundir), "results": parsed})
