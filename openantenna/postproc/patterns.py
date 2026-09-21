"""Far-field post-processing helpers (stdlib only).

These are deliberately simple, transparent quantities: an ideal-dipole element
pattern, pattern multiplication with the array factor, trapezoidal directivity
integration and an explicit efficiency budget.  Nothing here is a full-wave
result; it is the cheap sanity layer that sits between a solver run and a
report.
"""

from __future__ import annotations

import cmath
import math
from typing import Callable, Iterable, List, Sequence, Tuple

from ..geometry.array import array_factor


def dipole_element_pattern(theta_rad: float, length_lambda: float = 0.5) -> float:
    """Normalised amplitude pattern of an ideal thin dipole [V/m, unitless].

    ``F(theta) = [cos(kL/2 cos t) - cos(kL/2)] / sin(t)``, with
    ``kL/2 = pi * length_lambda``.  ``length_lambda=0.5`` gives the familiar
    half-wave dipole.  Undefined (0) exactly on the axis.
    """
    if length_lambda <= 0:
        raise ValueError("length_lambda must be > 0")
    sin_theta = math.sin(theta_rad)
    if abs(sin_theta) < 1e-12:
        return 0.0
    half = math.pi * length_lambda
    return abs((math.cos(half * math.cos(theta_rad)) - math.cos(half)) / sin_theta)


def array_pattern_product(
    positions_m: Sequence[Tuple[float, float]],
    frequency_hz: float,
    theta_rad: float,
    phi_rad: float,
    element_pattern: Callable[[float, float], float] | None = None,
    weights: Sequence[complex] | None = None,
    scan_theta_rad: float = 0.0,
    scan_phi_rad: float = 0.0,
) -> float:
    """Pattern multiplication: ``|AF| * |element pattern|``.

    This is the standard approximation for an array of identical elements whose
    mutual coupling is neglected.  It is invalid near scan blindness and for
    strongly coupled (small-spacing, high-eps_r) arrays -- which is exactly the
    regime that needs a full-wave check.
    """
    af = abs(
        array_factor(
            positions_m,
            frequency_hz,
            theta_rad,
            phi_rad,
            weights=weights,
            scan_theta_rad=scan_theta_rad,
            scan_phi_rad=scan_phi_rad,
        )
    )
    if element_pattern is None:
        return af
    return af * element_pattern(theta_rad, phi_rad)


def directivity_from_pattern(
    theta_rad_values: Sequence[float],
    phi_rad_values: Sequence[float],
    pattern: Callable[[float, float], float],
) -> float:
    """Numerical directivity (linear) from a far-field *amplitude* function.

    Uses the standard ``D = 4*pi*|F|max^2 / integral(|F|^2 sin(theta) dtheta dphi)``
    with a simple midpoint/trapezoidal rule.  The grid must be a regular
    rectangular ``theta`` x ``phi`` grid.
    """
    thetas = list(theta_rad_values)
    phis = list(phi_rad_values)
    if len(thetas) < 2 or len(phis) < 2:
        raise ValueError("need at least 2 x 2 grid points")

    d_theta = thetas[1] - thetas[0]
    d_phi = phis[1] - phis[0]
    if d_theta <= 0 or d_phi <= 0:
        raise ValueError("grids must be strictly increasing")

    total = 0.0
    peak = 0.0
    for theta in thetas:
        sin_theta = math.sin(theta)
        for phi in phis:
            value = abs(pattern(theta, phi))
            peak = max(peak, value)
            total += value * value * sin_theta * d_theta * d_phi
    if total <= 0.0:
        raise ValueError("pattern integrates to zero")
    return 4.0 * math.pi * peak * peak / total


def efficiency_budget(
    radiated_power_w: float,
    accepted_power_w: float,
    s11: complex = 0j,
) -> dict:
    """Explicit loss/efficiency budget for one port.

    ``accepted_power_w`` is the power delivered into the antenna terminals
    (i.e. after reflection).  ``s11`` is used only for the impedance-mismatch
    factor ``1-|S11|^2``, so a caller that already removed the reflected power
    should pass ``s11=0``.  All returned values are linear ratios unless the key
    ends in ``_db``.
    """
    if accepted_power_w <= 0:
        raise ValueError("accepted_power_w must be > 0")
    if radiated_power_w < 0:
        raise ValueError("radiated_power_w must be >= 0")
    if radiated_power_w > accepted_power_w * (1.0 + 1e-9):
        raise ValueError(
            "radiated_power_w cannot exceed accepted_power_w; check which reference "
            "plane each number was measured at"
        )

    radiation_efficiency = radiated_power_w / accepted_power_w
    mismatch_factor = 1.0 - abs(s11) ** 2
    total_efficiency = radiation_efficiency * mismatch_factor
    return {
        "radiation_efficiency": radiation_efficiency,
        "radiation_efficiency_db": 10.0 * math.log10(max(radiation_efficiency, 1e-12)),
        "mismatch_factor": mismatch_factor,
        "mismatch_loss_db": -10.0 * math.log10(max(mismatch_factor, 1e-12)),
        "total_efficiency": total_efficiency,
        "total_efficiency_db": 10.0 * math.log10(max(total_efficiency, 1e-12)),
        "dissipated_power_w": accepted_power_w - radiated_power_w,
    }


def gain_dbi(directivity_linear: float, efficiency_linear: float) -> float:
    """Gain in dBi from linear directivity and linear efficiency."""
    if directivity_linear <= 0:
        raise ValueError("directivity_linear must be > 0")
    if efficiency_linear <= 0:
        raise ValueError("efficiency_linear must be > 0")
    return 10.0 * math.log10(directivity_linear * efficiency_linear)


def aperture_directivity(
    size_x_m: float, size_y_m: float, frequency_hz: float, aperture_efficiency: float = 1.0
) -> float:
    """Upper-bound directivity of a uniform rectangular aperture (linear)."""
    if size_x_m <= 0 or size_y_m <= 0:
        raise ValueError("aperture dimensions must be > 0")
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be > 0")
    if not 0.0 < aperture_efficiency <= 1.0:
        raise ValueError("aperture_efficiency must be in (0, 1]")
    lam0 = 299792458.0 / frequency_hz
    return aperture_efficiency * 4.0 * math.pi * size_x_m * size_y_m / (lam0 * lam0)
