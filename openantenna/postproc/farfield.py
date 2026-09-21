"""Far-field results from the solver: reader and independent cross-checks.

When the near-to-far-field box is enabled, the generated model writes:

    nf2ff_summary.csv   freq_hz, directivity_lin, directivity_dbi, prad_w, p_acc_w, eta_rad
    nf2ff_pattern.csv   theta_deg, phi_deg, e_norm

Why this module exists: without far-field data the toolkit could not observe
efficiency, so every gain/efficiency number was analytic-only and unvalidated
(review item A-2, from the third-party suggestions).  With these files the solver's
directivity and radiation efficiency become directly comparable with the analytic
helpers in :mod:`openantenna.postproc.patterns`.

The integration here is deliberately independent of the solver's own integration:
if the two disagree, one of them is wrong, which is exactly what we want to know.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

SUMMARY_NAME = "nf2ff_summary.csv"
PATTERN_NAME = "nf2ff_pattern.csv"


@dataclass
class FarFieldPoint:
    """One frequency row of the far-field summary."""

    frequency_hz: float
    directivity_linear: float
    directivity_dbi: float
    radiated_power_w: float
    accepted_power_w: float
    radiation_efficiency: float

    def to_dict(self) -> dict:
        return {
            "frequency_hz": self.frequency_hz,
            "directivity_linear": self.directivity_linear,
            "directivity_dbi": self.directivity_dbi,
            "radiated_power_w": self.radiated_power_w,
            "accepted_power_w": self.accepted_power_w,
            "radiation_efficiency": self.radiation_efficiency,
        }


def read_summary(path: str | Path) -> List[FarFieldPoint]:
    """Read ``nf2ff_summary.csv`` into a list of :class:`FarFieldPoint`."""
    target = Path(path)
    if target.is_dir():
        target = target / SUMMARY_NAME
    if not target.exists():
        raise FileNotFoundError(f"{target} not found (far-field data missing)")
    points: List[FarFieldPoint] = []
    with target.open("r", encoding="utf-8") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            try:
                points.append(
                    FarFieldPoint(
                        frequency_hz=float(row["freq_hz"]),
                        directivity_linear=float(row["directivity_lin"]),
                        directivity_dbi=float(row["directivity_dbi"]),
                        radiated_power_w=float(row["prad_w"]),
                        accepted_power_w=float(row["p_accepted_w"] if "p_accepted_w" in row else row["p_acc_w"]),
                        radiation_efficiency=float(row["eta_rad"]),
                    )
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(f"bad row {index + 1} in {target.name}: {exc}") from exc
    if not points:
        raise ValueError(f"no data rows in {target}")
    return points


def read_pattern(
    path: str | Path,
) -> Tuple[List[float], List[float], List[List[float]], List[float]]:
    """Read ``nf2ff_pattern.csv``.

    Returns ``(thetas_deg, phis_deg, e_norm[theta][phi], frequencies_hz)`` where
    ``frequencies_hz`` is a single-element list with the pattern frequency (the
    generated file stores one frequency; kept as a list for future extension).
    """
    target = Path(path)
    if target.is_dir():
        target = target / PATTERN_NAME
    if not target.exists():
        raise FileNotFoundError(f"{target} not found (far-field pattern missing)")

    thetas: List[float] = []
    phis: List[float] = []
    rows: List[Tuple[float, float, float]] = []
    with target.open("r", encoding="utf-8") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            try:
                theta = float(row["theta_deg"])
                phi = float(row["phi_deg"])
                value = float(row["e_norm"])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"bad row {index + 1} in {target.name}: {exc}") from exc
            if theta not in thetas:
                thetas.append(theta)
            if phi not in phis:
                phis.append(phi)
            rows.append((theta, phi, value))
    if not rows:
        raise ValueError(f"no data rows in {target}")

    theta_index = {value: i for i, value in enumerate(thetas)}
    phi_index = {value: i for i, value in enumerate(phis)}
    grid = [[0.0] * len(phis) for _ in thetas]
    for theta, phi, value in rows:
        grid[theta_index[theta]][phi_index[phi]] = value
    return thetas, phis, grid, [0.0]


def directivity_from_pattern_grid(
    thetas_deg: List[float],
    phis_deg: List[float],
    e_norm: List[List[float]],
) -> float:
    """Linear directivity by trapezoidal integration over the far-field grid.

    Independent of the solver's own integration: the same grid, a plain
    ``4*pi*|E|max^2 / integral(|E|^2 sin(theta) dtheta dphi)``.  The phi grid is
    treated as periodic (its endpoint is duplicated in the file, which is what the
    trapezoidal rule wants for a closed interval).
    """
    if len(thetas_deg) < 2 or len(phis_deg) < 2:
        raise ValueError("need at least a 2 x 2 grid")
    d_theta = math.radians(thetas_deg[1] - thetas_deg[0])
    d_phi = math.radians(phis_deg[1] - phis_deg[0])
    if d_theta <= 0 or d_phi <= 0:
        raise ValueError("grids must be strictly increasing")

    def weight(index: int, count: int) -> float:
        if count == 2:
            return 1.0
        return 0.5 if index in (0, count - 1) else 1.0

    total = 0.0
    peak = 0.0
    for i, theta_deg in enumerate(thetas_deg):
        sin_theta = math.sin(math.radians(theta_deg))
        w_theta = weight(i, len(thetas_deg))
        for j in range(len(phis_deg)):
            value = abs(e_norm[i][j])
            peak = max(peak, value)
            total += w_theta * weight(j, len(phis_deg)) * value * value * sin_theta * d_theta * d_phi
    if total <= 0.0:
        raise ValueError("pattern integrates to zero")
    return 4.0 * math.pi * peak * peak / total


def summary_text(points: List[FarFieldPoint], reference_hz: Optional[float] = None) -> str:
    """Human-readable table, optionally flagging the row nearest ``reference_hz``."""
    lines = [
        f"{'freq [GHz]':>11}{'D [dBi]':>10}{'Prad [W]':>12}{'Pacc [W]':>12}{'eta_rad':>10}"
    ]
    lines.append("-" * 55)
    index = 0
    if reference_hz:
        index = min(
            range(len(points)), key=lambda i: abs(points[i].frequency_hz - reference_hz)
        )
    for i, point in enumerate(points):
        marker = " <-" if i == index and reference_hz else ""
        lines.append(
            f"{point.frequency_hz / 1e9:>11.4f}{point.directivity_dbi:>10.2f}"
            f"{point.radiated_power_w:>12.3e}{point.accepted_power_w:>12.3e}"
            f"{point.radiation_efficiency:>10.4f}{marker}"
        )
    lines.append("")
    lines.append(
        "Radiation efficiency = Prad/Pacc from the solver's own far field. This is the "
        "first efficiency number the toolkit can observe rather than assume."
    )
    return "\n".join(lines)
