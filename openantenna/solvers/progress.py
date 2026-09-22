"""Read the solver's own progress output and render a progress bar.

openEMS prints a line roughly every thousand steps::

    [@     2m28s] Timestep:        18655 || Speed:   39.8 MC/s (7.388e-03 s/TS) || Energy: ~1.07e-18 (-31.89dB)

and a final ``Speed: 37.18 MCells/s`` line when it finishes.

Two things make this worth parsing rather than guessing:

* ``Timestep`` against the cap says how far the run is from the *step limit*.
* ``Energy`` in dB says how far it is from *stopping on its own*: ``end_criteria=1e-4``
  is -40 dB, and the tutorial run above stopped at 24180 steps (-40.99 dB) — long before
  its 400000-step cap.  A bar driven by steps alone therefore reads low for the whole
  run, which is why the energy is shown next to it.

Everything here is stdlib-only and side-effect free apart from
:class:`ProgressPrinter`, which writes ``progress.json`` and prints a line or an
in-place bar.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

_TIMESTEP = re.compile(r"Timestep:\s*(\d+)")
_SPEED = re.compile(r"Speed:\s*([0-9.]+)\s*M(?:C|Cells)/s")
_ENERGY_DB = re.compile(r"\((-?[0-9.]+)\s*dB\)")
_ELAPSED = re.compile(r"\[@\s*(?:(\d+)m)?([0-9.]+)\s*s\]")


@dataclass
class SolverProgress:
    """One progress update from the solver log."""

    elapsed_s: Optional[float] = None
    timestep: Optional[int] = None
    speed_mcells_s: Optional[float] = None
    energy_db: Optional[float] = None

    def is_empty(self) -> bool:
        return (
            self.elapsed_s is None
            and self.timestep is None
            and self.speed_mcells_s is None
            and self.energy_db is None
        )


def parse_line(line: str) -> SolverProgress:
    """Parse one solver output line into a :class:`SolverProgress` (never raises)."""
    progress = SolverProgress()

    match = _TIMESTEP.search(line)
    if match:
        progress.timestep = int(match.group(1))

    match = _SPEED.search(line)
    if match:
        progress.speed_mcells_s = float(match.group(1))

    match = _ENERGY_DB.search(line)
    if match:
        progress.energy_db = float(match.group(1))

    match = _ELAPSED.search(line)
    if match:
        minutes = int(match.group(1) or 0)
        progress.elapsed_s = minutes * 60.0 + float(match.group(2))

    return progress


def has_progress(line: str) -> bool:
    """True when the line carries at least one progress field."""
    return not parse_line(line).is_empty()


def eta_to_cap(p: SolverProgress, cap_steps: Optional[int]) -> Optional[float]:
    """Seconds remaining if the run continues to the step cap (observed rate only).

    This is deliberately *not* an estimate of the finish time: a run normally stops
    earlier, when the energy criterion is met.  It is the honest upper bound.
    """
    if not cap_steps or p.timestep in (None, 0) or p.elapsed_s in (None, 0):
        return None
    remaining = cap_steps - int(p.timestep)
    if remaining <= 0:
        return 0.0
    seconds_per_step = p.elapsed_s / float(p.timestep)
    return remaining * seconds_per_step


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "?"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def format_bar(
    p: SolverProgress,
    cap_steps: Optional[int],
    width: int = 28,
    db_target: Optional[float] = -40.0,
) -> str:
    """A one-line progress bar; percentages are relative to the step cap.

    The percentage is **of the step cap**, not of the work: a run normally stops on the
    energy criterion long before the cap (the tutorial run finished at 6.0 % of its cap,
    24 180 of 400 000 steps, and that was the *end* of it).  Reading the percentage as
    "how much is left to do" would therefore be wrong, so the label says so explicitly.
    """
    if cap_steps and p.timestep is not None and cap_steps > 0:
        fraction = min(1.0, max(0.0, p.timestep / float(cap_steps)))
    else:
        fraction = 0.0
    filled = int(round(fraction * width))
    bar = "#" * filled + "-" * (width - filled)

    parts = [f"[{bar}] {fraction * 100:5.1f}% of the {cap_steps:,}-step cap" if cap_steps
             else f"[{bar}] {fraction * 100:5.1f}%"]
    if p.timestep is not None and cap_steps:
        parts.append(f"step {p.timestep:,}/{cap_steps:,}")
    if p.energy_db is not None and db_target is not None:
        parts.append(f"energy {p.energy_db:.1f} dB (run stops at {db_target:.0f} dB)")
    if p.speed_mcells_s:
        parts.append(f"{p.speed_mcells_s:.1f} MCells/s")
    if p.elapsed_s is not None:
        parts.append(f"elapsed {format_duration(p.elapsed_s)}")
    eta = eta_to_cap(p, cap_steps)
    if eta is not None and eta > 0:
        parts.append(f"worst case {format_duration(eta)} more")
    parts.append("cap is an upper bound, not the finish line")
    return "  ".join(parts)


class ProgressPrinter:
    """Streams solver progress to a JSON file and to the console.

    ``progress.json`` is written atomically after every update, so an external tool can
    watch a run without parsing stdout.  On a terminal the console gets an in-place bar;
    when stdout is a pipe (a redirected log) it gets a complete line per update, flushed,
    because an unflushed bar in a file is useless.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        cap_steps: Optional[int] = None,
        db_target: Optional[float] = -40.0,
        stream=None,
        echo: bool = True,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.cap_steps = cap_steps
        self.db_target = db_target
        self.stream = stream if stream is not None else sys.stdout
        self.echo = echo
        self.latest = SolverProgress()
        self.updates = 0
        self._tty = bool(getattr(self.stream, "isatty", lambda: False)())

    def feed(self, line: str) -> Optional[SolverProgress]:
        """Consume one log line; returns the parsed update when it carried progress."""
        parsed = parse_line(line)
        if parsed.is_empty():
            return None

        # Keep the best-known value for each field: the final "Speed:" line has no
        # timestep, and a mid-run line may omit the energy.
        for field in ("elapsed_s", "timestep", "speed_mcells_s", "energy_db"):
            value = getattr(parsed, field)
            if value is not None:
                setattr(self.latest, field, value)

        self.updates += 1
        self._write_json()
        if self.echo:
            self._print_line()
        return self.latest

    def _print_line(self) -> None:
        text = format_bar(self.latest, self.cap_steps, db_target=self.db_target)
        try:
            if self._tty:
                self.stream.write("\r" + text)
            else:
                self.stream.write("[progress] " + text + "\n")
            self.stream.flush()
        except (ValueError, OSError):  # pragma: no cover - closed stream
            self.echo = False

    def _write_json(self) -> None:
        if self.path is None:
            return
        payload = asdict(self.latest)
        payload["updates"] = self.updates
        payload["percent_of_cap"] = (
            round(100.0 * self.latest.timestep / self.cap_steps, 3)
            if self.cap_steps and self.latest.timestep
            else None
        )
        payload["eta_to_cap_s"] = eta_to_cap(self.latest, self.cap_steps)
        payload["bar"] = format_bar(self.latest, self.cap_steps, db_target=self.db_target)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(
                dir=str(self.path.parent), prefix=self.path.name, suffix=".tmp"
            )
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
                fh.write("\n")
            os.replace(temp_name, self.path)
        except OSError:  # pragma: no cover - read-only run directory
            pass

    def finish(self) -> None:
        """End the in-place bar so later output starts on a fresh line."""
        if self._tty and self.echo:
            try:
                self.stream.write("\n")
                self.stream.flush()
            except (ValueError, OSError):  # pragma: no cover
                pass
