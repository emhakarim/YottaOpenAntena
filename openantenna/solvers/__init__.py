"""Solver adapters.

An adapter turns the neutral model into the input deck of one external solver,
runs it as a *separate process*, and parses its output.  See
``docs/licensing.md`` for why the process boundary matters.
"""

from __future__ import annotations

from .base import SolverAdapter, SolverRun, SolverStatus, SolverUnavailableError
from .openems import OpenEMSSolver

__all__ = [
    "SolverAdapter",
    "SolverRun",
    "SolverStatus",
    "SolverUnavailableError",
    "OpenEMSSolver",
]
