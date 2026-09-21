"""Array layout generation and array-factor post-processing (stdlib only).

Two different jobs live here and they must not be confused:

* :func:`build_array_layout` produces *geometry* (element positions and overall
  size).  It is used to generate a finite-array model.
* :func:`array_factor` / :func:`array_factor_plane` implement the textbook
  **array factor** (pattern multiplication).  That is a far-field approximation
  for identical, uncoupled, isotropic-in-pattern elements.  It is the standard
  way to predict the pattern of a large array without a full-wave model, but it
  cannot predict mutual coupling, scan blindness or element pattern distortion.
  Those need a full-wave unit-cell or finite-array run.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

from ..model.project import ArrayConfig
from .patch import PatchDesign, wavelength0

C0 = 299792458.0


def element_positions(
    nx: int, ny: int, dx_m: float, dy_m: float, centered: bool = True
) -> List[Tuple[float, float]]:
    """Positions ``(x, y)`` of an ``nx`` x ``ny`` grid of elements.

    Elements are laid out along x and y; with ``centered=True`` the array is
    centred on the origin.
    """
    if nx < 1 or ny < 1:
        raise ValueError("nx and ny must be >= 1")
    if dx_m <= 0 or dy_m <= 0:
        raise ValueError("dx_m and dy_m must be > 0")
    x_offset = (nx - 1) * dx_m / 2.0 if centered else 0.0
    y_offset = (ny - 1) * dy_m / 2.0 if centered else 0.0
    return [
        (ix * dx_m - x_offset, iy * dy_m - y_offset)
        for iy in range(ny)
        for ix in range(nx)
    ]


@dataclass
class ArrayLayout:
    """Geometry of a finite array of identical rectangular patches."""

    nx: int
    ny: int
    dx_m: float
    dy_m: float
    frequency_hz: float
    positions_m: List[Tuple[float, float]] = field(default_factory=list)
    element_width_m: float | None = None
    element_length_m: float | None = None
    warnings: List[str] = field(default_factory=list)

    @property
    def element_count(self) -> int:
        return self.nx * self.ny

    @property
    def grid_size_x_m(self) -> float:
        return (self.nx - 1) * self.dx_m

    @property
    def grid_size_y_m(self) -> float:
        return (self.ny - 1) * self.dy_m

    @property
    def size_x_m(self) -> float:
        """Total extent including the element footprint."""
        width = self.element_width_m or 0.0
        return self.grid_size_x_m + width

    @property
    def size_y_m(self) -> float:
        length = self.element_length_m or 0.0
        return self.grid_size_y_m + length

    @property
    def size_x_lambda0(self) -> float:
        return self.size_x_m / wavelength0(self.frequency_hz)

    @property
    def size_y_lambda0(self) -> float:
        return self.size_y_m / wavelength0(self.frequency_hz)

    @property
    def aperture_area_m2(self) -> float:
        return self.size_x_m * self.size_y_m

    def to_dict(self) -> dict:
        return {
            "nx": self.nx,
            "ny": self.ny,
            "dx_m": self.dx_m,
            "dy_m": self.dy_m,
            "frequency_hz": self.frequency_hz,
            "element_count": self.element_count,
            "positions_m": [list(p) for p in self.positions_m],
            "element_width_m": self.element_width_m,
            "element_length_m": self.element_length_m,
            "size_x_m": self.size_x_m,
            "size_y_m": self.size_y_m,
            "size_x_lambda0": self.size_x_lambda0,
            "size_y_lambda0": self.size_y_lambda0,
            "warnings": list(self.warnings),
        }

    def summary(self) -> str:
        lines = [
            f"array            : {self.nx} x {self.ny} = {self.element_count} elements",
            f"element spacing  : {self.dx_m * 1e3:.3f} x {self.dy_m * 1e3:.3f} mm",
            (
                f"aperture         : {self.size_x_m * 1e3:.3f} x {self.size_y_m * 1e3:.3f} mm"
                f" ({self.size_x_lambda0:.3f} x {self.size_y_lambda0:.3f} lambda0)"
            ),
            f"first element at : ({self.positions_m[0][0] * 1e3:.3f}, "
            f"{self.positions_m[0][1] * 1e3:.3f}) mm",
        ]
        for warning in self.warnings:
            lines.append(f"WARNING          : {warning}")
        return "\n".join(lines)


def build_array_layout(
    array: ArrayConfig, frequency_hz: float, element: PatchDesign | None = None
) -> ArrayLayout:
    """Build the layout of a finite array from the neutral model."""
    dx, dy = array.spacing_m(frequency_hz)
    layout = ArrayLayout(
        nx=array.nx,
        ny=array.ny,
        dx_m=dx,
        dy_m=dy,
        frequency_hz=frequency_hz,
        positions_m=element_positions(array.nx, array.ny, dx, dy),
        element_width_m=element.width_m if element else None,
        element_length_m=element.length_m if element else None,
    )

    warnings = layout.warnings
    lam0 = wavelength0(frequency_hz)
    if max(array.spacing_x_lambda0, array.spacing_y_lambda0) > 0.5:
        warnings.append(
            "Spacing > 0.5 lambda0: grating lobes (and, for a finite array, high "
            "sidelobes) are expected for wide scan angles."
        )
    if min(array.spacing_x_lambda0, array.spacing_y_lambda0) < 0.5 and element is not None:
        if element.width_m > min(dx, dy):
            warnings.append(
                f"Element width {element.width_m * 1e3:.3f} mm exceeds the element pitch "
                f"{min(dx, dy) * 1e3:.3f} mm: the patches physically overlap."
            )
    if layout.element_count >= 16:
        warnings.append(
            f"{layout.element_count} elements: prefer a unit-cell (periodic boundary) "
            "study for the periodic behaviour plus an array-factor calculation, and use "
            "a full-wave finite model only for coupling spot-checks."
        )
    if layout.size_x_m > 10.0 * lam0 or layout.size_y_m > 10.0 * lam0:
        warnings.append(
            "The array is electrically large; a full-wave FDTD model of the whole "
            "structure will be memory- and time-expensive."
        )
    return layout


# ---------------------------------------------------------------------------
# Array factor (pattern multiplication)
# ---------------------------------------------------------------------------
def array_factor(
    positions_m: Sequence[Tuple[float, float]],
    frequency_hz: float,
    theta_rad: float,
    phi_rad: float,
    weights: Sequence[complex] | None = None,
    scan_theta_rad: float = 0.0,
    scan_phi_rad: float = 0.0,
) -> complex:
    """Complex array factor for the direction ``(theta, phi)``.

    ``theta`` is measured from the +z axis, ``phi`` in the xy plane.  Element
    positions are assumed to lie in the xy plane.  A uniform progressive phase
    shift steers the beam to ``(scan_theta, scan_phi)`` when ``weights`` is not
    given (or when ``weights`` is a uniform-amplitude sequence).
    """
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be > 0")
    k = 2.0 * math.pi / wavelength0(frequency_hz)
    u = math.sin(theta_rad) * math.cos(phi_rad)
    v = math.sin(theta_rad) * math.sin(phi_rad)
    u0 = math.sin(scan_theta_rad) * math.cos(scan_phi_rad)
    v0 = math.sin(scan_theta_rad) * math.sin(scan_phi_rad)

    if weights is None:
        weights = [1.0 + 0.0j] * len(positions_m)
    if len(weights) != len(positions_m):
        raise ValueError("weights and positions must have the same length")

    total = 0.0 + 0.0j
    for (x, y), weight in zip(positions_m, weights):
        phase = k * ((x * u + y * v) - (x * u0 + y * v0))
        total += weight * cmath.exp(1j * phase)
    return total


def array_factor_plane(
    positions_m: Sequence[Tuple[float, float]],
    frequency_hz: float,
    n_points: int = 361,
    plane: str = "e",
    scan_theta_rad: float = 0.0,
    scan_phi_rad: float = 0.0,
) -> List[Tuple[float, float]]:
    """Array factor magnitude in dB over one principal plane.

    ``plane="e"`` sweeps theta with phi = 0 (x-z plane), ``plane="h"`` sweeps
    theta with phi = 90 deg (y-z plane).  Returns ``[(angle_deg, af_db), ...]``
    normalised so that the maximum is 0 dB.
    """
    if plane not in ("e", "h"):
        raise ValueError("plane must be 'e' or 'h'")
    if n_points < 3:
        raise ValueError("n_points must be >= 3")

    phi = 0.0 if plane == "e" else math.pi / 2.0
    samples: List[Tuple[float, float]] = []
    for i in range(n_points):
        theta = math.pi * i / (n_points - 1)
        value = abs(
            array_factor(
                positions_m,
                frequency_hz,
                theta,
                phi,
                scan_theta_rad=scan_theta_rad,
                scan_phi_rad=scan_phi_rad,
            )
        )
        samples.append((math.degrees(theta), value))

    peak = max(value for _, value in samples) or 1.0
    return [
        (angle, 20.0 * math.log10(max(value / peak, 1e-12))) for angle, value in samples
    ]
