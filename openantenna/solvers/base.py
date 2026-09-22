"""Solver adapter interface (stdlib only).

Contract for every adapter:

* :meth:`SolverAdapter.available` reports honestly whether the external solver
  can actually be executed in this environment.
* :meth:`SolverAdapter.prepare` writes the input deck into a *run directory* and
  returns that directory.  It never executes anything.
* :meth:`SolverAdapter.run` executes the external program as a subprocess.  If
  the solver is not available it must raise :class:`SolverUnavailableError`
  rather than silently returning fake results.
* :meth:`SolverAdapter.parse_results` reads the raw output files and returns a
  plain, JSON-serialisable dict.  Parsing is allowed to fail loudly if the
  solver did not produce the expected files.

Fabricating results is never acceptable: a run that did not happen must be
reported as ``status="not_run"``.
"""

from __future__ import annotations

import abc
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from ..model.project import Project
from .progress import ProgressPrinter, SolverProgress


class SolverUnavailableError(RuntimeError):
    """Raised when a solver cannot be executed in this environment."""


@dataclass
class SolverStatus:
    """Result of probing a solver."""

    name: str
    available: bool
    detail: str
    binary_path: Optional[str] = None

    def __bool__(self) -> bool:
        return self.available


@dataclass
class SolverRun:
    """Outcome of one solver invocation."""

    rundir: Path
    status: str  # "not_run" | "ok" | "failed"
    returncode: Optional[int] = None
    log: str = ""
    outputs: Dict[str, str] = field(default_factory=dict)
    duration_s: Optional[float] = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rundir": str(self.rundir),
            "status": self.status,
            "returncode": self.returncode,
            "log_tail": self.log[-4000:],
            "outputs": dict(self.outputs),
            "duration_s": self.duration_s,
        }


class SolverAdapter(abc.ABC):
    """Base class for all solver adapters."""

    name: str = "abstract"

    @abc.abstractmethod
    def available(self) -> SolverStatus:
        """Probe the environment; never raises for a missing solver."""

    @abc.abstractmethod
    def prepare(self, project: Project, rundir: str | Path) -> Path:
        """Write the solver input deck into ``rundir`` and return it."""

    @abc.abstractmethod
    def run(self, rundir: str | Path, timeout_s: Optional[float] = None) -> SolverRun:
        """Execute the solver (subprocess).  Raises if it is unavailable."""

    @abc.abstractmethod
    def parse_results(self, rundir: str | Path) -> Dict[str, Any]:
        """Parse solver output files into a JSON-serialisable dict."""

    # ------------------------------------------------------------------ util
    @staticmethod
    def _execute(
        argv: list[str],
        rundir: Path,
        timeout_s: Optional[float],
        env: Optional[Mapping[str, str]] = None,
        progress_path: Optional[Path] = None,
        total_steps: Optional[int] = None,
        echo_progress: bool = False,
        on_progress: Optional[Callable[[SolverProgress], None]] = None,
    ) -> SolverRun:
        """Run a solver command, streaming its output instead of capturing it.

        A run can last hours, and the generated scripts print progress (timestep, speed,
        energy).  Capturing the output means the log only appears at the end, so a slow
        run and a hung run look identical from outside -- which is exactly what happened
        to two PTFE runs that sat for 90 minutes with a 0-byte console log.  Passing
        ``progress_path`` also persists ``progress.json`` after every update, so any
        external tool (or the GUI) can watch the run without parsing stdout.
        """
        run_env = dict(os.environ) if env is None else dict(env)
        printer = (
            ProgressPrinter(progress_path, total_steps, echo=echo_progress)
            if (progress_path is not None or echo_progress or on_progress is not None)
            else None
        )

        started = time.monotonic()
        timed_out = False

        try:
            process = subprocess.Popen(
                argv,
                cwd=str(rundir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=run_env,
            )
        except OSError as exc:
            return SolverRun(
                rundir=rundir,
                status="failed",
                returncode=None,
                log=f"could not launch {argv[0]}: {exc}",
            )

        def _kill() -> None:
            nonlocal timed_out
            timed_out = True
            process.kill()

        timer = threading.Timer(timeout_s, _kill) if timeout_s else None
        if timer is not None:
            timer.start()

        chunks: list[str] = []
        try:
            if process.stdout is not None:
                for line in process.stdout:
                    chunks.append(line)
                    if printer is not None:
                        snapshot = printer.feed(line)
                        if snapshot is not None and on_progress is not None:
                            on_progress(snapshot)
        finally:
            if timer is not None:
                timer.cancel()
            if process.stdout is not None:
                process.stdout.close()
            returncode = process.wait()

        duration = time.monotonic() - started
        if printer is not None:
            printer.finish()
        log = "".join(chunks)

        if timed_out:
            return SolverRun(
                rundir=rundir,
                status="failed",
                returncode=None,
                log=f"timeout after {timeout_s} s\n{log}",
                duration_s=duration,
            )
        return SolverRun(
            rundir=rundir,
            status="ok" if returncode == 0 else "failed",
            returncode=returncode,
            log=log,
            duration_s=duration,
        )
