"""Array coupling from per-port openEMS runs (Phase 2 #4, toolkit side).

One run per driven port: every run dumps ``port_<n>.csv`` for *all* element ports, and the
driven port is chosen at run time with ``OPENANTENNA_EXCITE_PORT``.  One run therefore gives one
column of the scattering matrix, ``S_ij = uf_ref(i) / uf_inc(j)``, and N runs give the whole
matrix - with the deck unchanged between runs, which is what makes the columns comparable.

This is the package-side counterpart of the verification tool in
``yotta_tools/port_matrix.py``; the two are deliberately separate implementations, the same way
``yotta_tools/microstrip_reference.py`` cross-checks the microstrip synthesis in
:mod:`openantenna.geometry.patch`.

Two rules are enforced rather than documented:

* a **missing** ``port_<n>.csv`` is an error - a zero would fake perfect isolation;
* a run that did not **converge** is refused, because ``docs/convergence-policy.md`` forbids
  quoting a number from such a run.  ``require_convergence=False`` exists for exploration and
  says so in the returned summary.

Stdlib only.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "PORT_HEADER",
    "PortTrace",
    "CouplingMatrix",
    "read_port_csv",
    "assemble",
]

PORT_HEADER = ["freq_hz", "uf_inc_re", "uf_inc_im", "uf_ref_re", "uf_ref_im"]


@dataclass
class PortTrace:
    """Time-domain-to-frequency dump of one port: incident and reflected wave spectra."""

    frequencies_hz: List[float]
    uf_inc: List[complex]
    uf_ref: List[complex]

    def __len__(self) -> int:
        return len(self.frequencies_hz)


def read_port_csv(path: str | Path) -> PortTrace:
    """Read ``port_<n>.csv``; a wrong header or an empty file is an error, not a zero."""
    path = Path(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:  # pragma: no cover - empty file
            raise ValueError(f"{path}: empty file") from exc
        if [column.strip() for column in header] != PORT_HEADER:
            raise ValueError(
                f"{path}: unexpected header {header}, expected {PORT_HEADER}"
            )
        frequencies: List[float] = []
        inc: List[complex] = []
        ref: List[complex] = []
        for line_number, row in enumerate(reader, start=2):
            if not row:
                continue
            try:
                values = [float(value) for value in row]
            except ValueError as exc:
                raise ValueError(f"{path}: line {line_number} is not numeric: {row}") from exc
            if len(values) != 5:
                raise ValueError(f"{path}: line {line_number} has {len(values)} columns")
            frequencies.append(values[0])
            inc.append(complex(values[1], values[2]))
            ref.append(complex(values[3], values[4]))
    if not frequencies:
        raise ValueError(f"{path}: no data rows")
    return PortTrace(frequencies_hz=frequencies, uf_inc=inc, uf_ref=ref)


@dataclass
class CouplingMatrix:
    """S-matrix assembled from one run per driven port.

    ``s[i][j][k]`` is S between port ``i+1`` and driven port ``j+1`` at ``frequencies_hz[k]``.
    """

    frequencies_hz: List[float]
    s: List[List[List[complex]]]
    driven_ports: List[int]
    n_ports: int
    converged: Dict[int, Optional[bool]]
    require_convergence: bool

    def at(self, frequency_hz: float) -> Tuple[float, List[List[complex]]]:
        """The matrix at the **nearest sampled** frequency, with the frequency actually used.

        No interpolation: the number returned is one the solver computed, and the caller can see
        which sample it is.
        """
        if not self.frequencies_hz:
            raise ValueError("the matrix carries no frequencies")
        index = min(
            range(len(self.frequencies_hz)),
            key=lambda k: abs(self.frequencies_hz[k] - frequency_hz),
        )
        return self.frequencies_hz[index], [[row[index] for row in column] for column in self.s]

    def coupling_summary(self, frequency_hz: float) -> Dict[str, object]:
        """Worst and mean coupling between *different* ports, plus the per-pair list."""
        used_hz, matrix = self.at(frequency_hz)
        pairs: List[Dict[str, object]] = []
        for i in range(self.n_ports):
            for j in range(self.n_ports):
                if i == j:
                    continue
                pairs.append(
                    {
                        "from_port": j + 1,
                        "to_port": i + 1,
                        "magnitude": abs(matrix[i][j]),
                        "db": 20.0 * math.log10(max(abs(matrix[i][j]), 1e-12)),
                    }
                )
        magnitudes = [float(pair["magnitude"]) for pair in pairs]
        return {
            "frequency_hz": used_hz,
            "requested_frequency_hz": frequency_hz,
            "pairs": pairs,
            "worst_magnitude": max(magnitudes) if magnitudes else 0.0,
            "worst_db": 20.0 * math.log10(max(max(magnitudes), 1e-12)) if magnitudes else -240.0,
            "mean_magnitude": (sum(magnitudes) / len(magnitudes)) if magnitudes else 0.0,
            "converged": self.converged,
            "require_convergence": self.require_convergence,
            "note": (
                "A coupling number is only meaningful for runs that differ in one variable, and "
                "only from runs that converged."
            ),
        }

    def coupling_vs_spacing(
        self,
        positions_m: Sequence[Tuple[float, float]],
        frequency_hz: float,
    ) -> List[Dict[str, object]]:
        """Off-diagonal coupling grouped by element distance: the trend, not the full matrix."""
        used_hz, matrix = self.at(frequency_hz)
        if len(positions_m) != self.n_ports:
            raise ValueError(
                f"{len(positions_m)} positions for {self.n_ports} ports: they must match"
            )
        grouped: List[Dict[str, object]] = []
        for i in range(self.n_ports):
            for j in range(i + 1, self.n_ports):
                dx = positions_m[i][0] - positions_m[j][0]
                dy = positions_m[i][1] - positions_m[j][1]
                distance = math.hypot(dx, dy)
                mutual = max(abs(matrix[i][j]), abs(matrix[j][i]))
                grouped.append(
                    {
                        "ports": (i + 1, j + 1),
                        "distance_m": distance,
                        "mutual_magnitude": mutual,
                        "mutual_db": 20.0 * math.log10(max(mutual, 1e-12)),
                    }
                )
        grouped.sort(key=lambda entry: entry["distance_m"])
        return grouped


def _converged(run_dir: Path) -> Optional[bool]:
    """Read the run's own convergence verdict, or None when it did not record one."""
    summary = run_dir / "run_summary.json"
    if not summary.exists():
        return None
    try:
        payload = json.loads(summary.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = payload.get("converged")
    return bool(value) if value is not None else None


def assemble(
    runs: Iterable[Tuple[str | Path, int]],
    n_ports: int,
    require_convergence: bool = True,
) -> CouplingMatrix:
    """Assemble the coupling matrix from ``(run_dir, driven_port)`` pairs.

    ``n_ports`` must be given explicitly: inferring it from "the ports we happen to have files
    for" is exactly how a missing column turns into a silent zero.
    """
    runs = [(Path(directory), int(driven)) for directory, driven in runs]
    if not runs:
        raise ValueError("no runs given")
    if n_ports < 2:
        raise ValueError("a coupling matrix needs at least two ports")

    frequencies: Optional[List[float]] = None
    columns: Dict[int, List[List[complex]]] = {}
    converged: Dict[int, Optional[bool]] = {}
    for run_dir, driven in runs:
        if not 1 <= driven <= n_ports:
            raise ValueError(f"driven port {driven} is outside 1..{n_ports}")
        if driven in columns:
            raise ValueError(f"port {driven} was driven twice; each column needs one run")
        traces: List[PortTrace] = []
        for port in range(1, n_ports + 1):
            path = run_dir / f"port_{port}.csv"
            if not path.exists():
                raise ValueError(
                    f"{run_dir}: port_{port}.csv is missing. A missing port file is an error, "
                    "never a zero - a zero would fake perfect isolation."
                )
            traces.append(read_port_csv(path))
        if frequencies is None:
            frequencies = list(traces[0].frequencies_hz)
        elif traces[0].frequencies_hz != frequencies:
            raise ValueError(f"{run_dir}: frequency grid differs from the other runs")
        column = [
            [
                traces[port].uf_ref[k] / traces[driven - 1].uf_inc[k]
                if traces[driven - 1].uf_inc[k] != 0
                else complex("nan")
                for k in range(len(frequencies))
            ]
            for port in range(n_ports)
        ]
        columns[driven] = column
        converged[driven] = _converged(run_dir)

    missing = [port for port in range(1, n_ports + 1) if port not in columns]
    if missing:
        raise ValueError(
            f"no run drove port(s) {missing}; the matrix would have empty columns"
        )
    if require_convergence:
        unconverged = sorted(
            port for port, state in converged.items() if state is not True
        )
        if unconverged:
            raise ValueError(
                f"run(s) for port(s) {unconverged} did not converge (or did not record it): "
                "docs/convergence-policy.md forbids quoting numbers from them. "
                "Pass require_convergence=False for an exploratory look."
            )

    matrix = [
        [columns[j][i] for j in range(1, n_ports + 1)] for i in range(n_ports)
    ]
    return CouplingMatrix(
        frequencies_hz=list(frequencies or []),
        s=matrix,
        driven_ports=sorted(columns),
        n_ports=n_ports,
        converged=converged,
        require_convergence=require_convergence,
    )
