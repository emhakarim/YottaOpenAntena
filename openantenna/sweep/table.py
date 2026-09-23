"""Parameter sweep as a table (Phase 4, CST-style sweeps).

A sweep in CST is a table: parameters on one side, values to try, and a results column you can sort
and plot.  This module is that table without any UI - it enumerates the runs, tracks each one's
status and result, aggregates a summary, and writes CSV so the GUI, the CLI and a report all read
the same object.

Two generation modes, because they answer different questions:

* ``factorial`` - every combination of the given values.  Answers "what happens across the whole
  space", and grows multiplicatively (which is why it is capped).
* ``one_at_a_time`` - vary one parameter, hold the rest at a baseline.  This is the sweep most design
  work actually needs, and it is what makes a resonance-versus-parameter curve.
"""

from __future__ import annotations

import csv
import itertools
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

STATUSES = ("pending", "running", "done", "failed")
MAX_RUNS = 4096


@dataclass
class RunRecord:
    """One row of the sweep table."""

    index: int
    params: Dict[str, float]
    status: str = "pending"
    result: Dict[str, float] = field(default_factory=dict)
    note: str = ""

    def mark(self, status: str, result: Mapping[str, float] | None = None, note: str = "") -> None:
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r}; expected one of {STATUSES}")
        self.status = status
        if result:
            self.result.update({key: float(value) for key, value in result.items()})
        if note:
            self.note = note


class SweepTable:
    """An ordered set of parameter runs plus their outcomes."""

    def __init__(self, records: Sequence[RunRecord], mode: str, parameters: Mapping[str, Sequence[float]]):
        self._records: List[RunRecord] = list(records)
        self.mode = mode
        self.parameters = {name: list(values) for name, values in parameters.items()}

    # ---- construction -------------------------------------------------------------------
    @staticmethod
    def _clean(values: Mapping[str, Sequence[float]]) -> Dict[str, List[float]]:
        if not values:
            raise ValueError("a sweep needs at least one parameter")
        cleaned: Dict[str, List[float]] = {}
        for name, series in values.items():
            series = list(series)
            if not series:
                raise ValueError(f"parameter {name!r} has no values")
            if any(not math.isfinite(float(value)) for value in series):
                raise ValueError(f"parameter {name!r} has a non-finite value")
            cleaned[name] = [float(value) for value in series]
        return cleaned

    @classmethod
    def factorial(cls, values: Mapping[str, Sequence[float]]) -> "SweepTable":
        """Every combination of the given values, in a deterministic order."""
        cleaned = cls._clean(values)
        names = list(cleaned)
        total = 1
        for name in names:
            total *= len(cleaned[name])
        if total > MAX_RUNS:
            raise ValueError(
                f"that sweep would be {total} runs, above the cap of {MAX_RUNS}. Use one_at_a_time "
                "or trim the value lists - a capped table is better than a queue nobody can finish."
            )
        records = []
        for index, combination in enumerate(itertools.product(*(cleaned[name] for name in names))):
            records.append(RunRecord(index=index, params=dict(zip(names, combination))))
        return cls(records, "factorial", cleaned)

    @classmethod
    def one_at_a_time(
        cls, baseline: Mapping[str, float], values: Mapping[str, Sequence[float]]
    ) -> "SweepTable":
        """Vary one parameter at a time, everything else held at ``baseline``."""
        if not baseline:
            raise ValueError("a one-at-a-time sweep needs a baseline")
        cleaned = cls._clean(values)
        for name in cleaned:
            if name not in baseline:
                raise ValueError(f"parameter {name!r} is swept but missing from the baseline")
        records = [RunRecord(index=0, params=dict(baseline), note="baseline")]
        for name, series in cleaned.items():
            for value in series:
                params = dict(baseline)
                params[name] = value
                if params == dict(baseline):
                    continue  # the baseline point is already row 0
                records.append(RunRecord(index=len(records), params=params, note=f"vary {name}"))
        return cls(records, "one_at_a_time", cleaned)

    # ---- access -------------------------------------------------------------------------
    @property
    def records(self) -> Tuple[RunRecord, ...]:
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)

    def status_counts(self) -> Dict[str, int]:
        counts = {status: 0 for status in STATUSES}
        for record in self._records:
            counts[record.status] += 1
        return counts

    def marked(self, status: str) -> Tuple[RunRecord, ...]:
        return tuple(record for record in self._records if record.status == status)

    def summary(self, metric: str) -> Dict[str, list]:
        """Group a numeric result by each swept parameter, skipping unfinished runs.

        Returns ``{parameter: [(value, [metric values])], ...}`` - the shape a
        resonance-versus-parameter curve needs.  A run touches several parameters, so it contributes
        to each of them at its own value.
        """
        grouped: Dict[str, Dict[float, list]] = {name: {} for name in self.parameters}
        for record in self._records:
            if record.status != "done" or metric not in record.result:
                continue
            for name in self.parameters:
                if name in record.params:
                    grouped[name].setdefault(record.params[name], []).append(record.result[metric])
        return {name: sorted(points.items()) for name, points in grouped.items()}

    def to_csv(self, path: str | Path) -> Path:
        """Write the table: parameter columns, then status, note and every result column."""
        target = Path(path)
        parameter_names = list(self.parameters)
        result_names: List[str] = []
        for record in self._records:
            for name in record.result:
                if name not in result_names:
                    result_names.append(name)
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["index", *parameter_names, "status", *result_names, "note"])
            for record in self._records:
                writer.writerow(
                    [
                        record.index,
                        *[record.params.get(name, "") for name in parameter_names],
                        record.status,
                        *[record.result.get(name, "") for name in result_names],
                        record.note,
                    ]
                )
        return target


def run_table(table: SweepTable, runner, *, stop_on_failure: bool = False) -> SweepTable:
    """Drive a table with ``runner(params, record) -> Mapping[str, float]``.

    The runner is whatever produces the numbers - the analytic model today, a solver process later.
    A runner that raises marks the row ``failed`` with the message instead of aborting the sweep, so a
    single bad point cannot destroy a queue that took hours.
    """
    for record in table.records:
        record.mark("running")
        try:
            result = runner(record.params, record)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            record.mark("failed", note=f"{type(exc).__name__}: {exc}")
            if stop_on_failure:
                raise
            continue
        record.mark("done", result=result or {})
    return table
