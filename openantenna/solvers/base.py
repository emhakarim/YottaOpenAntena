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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ..model.project import Project


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
    ) -> SolverRun:
        run_env = dict(os.environ) if env is None else dict(env)
        try:
            completed = subprocess.run(
                argv,
                cwd=str(rundir),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
                env=run_env,
            )
        except subprocess.TimeoutExpired as exc:
            return SolverRun(
                rundir=rundir,
                status="failed",
                returncode=None,
                log=f"timeout after {timeout_s} s: {exc}",
            )
        log = (completed.stdout or "") + (completed.stderr or "")
        return SolverRun(
            rundir=rundir,
            status="ok" if completed.returncode == 0 else "failed",
            returncode=completed.returncode,
            log=log,
        )
