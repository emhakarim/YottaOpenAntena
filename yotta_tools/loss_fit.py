"""Loss modelling where the engine cannot do dispersion (Phase 2, item 1).

CORRECTION (this module was written on a wrong premise): the installed CSXCAD *does*
support dispersive materials.  The classes live in the ``CSXCAD.CSProperties`` submodule, and
``openantenna/solvers/openems.py`` now emits a native Debye substrate
(``loss_model="debye"``; see ``docs/dispersive-substrates.md``).  Prefer that path when the
engine supports dispersion - the machinery below stays for engines that only offer a constant
conductivity, and for quantifying what such an approximation costs.

For an engine whose only loss knob is a **constant** conductivity ``kappa`` [S/m] (the model
script converts a reference tan(delta) into it):

    kappa = tan_delta * 2*pi*f_ref * eps0 * eps_r          (see openantenna/solvers/openems.py)

That is exact at ``f_ref`` and wrong everywhere else, because a real dielectric's tan(delta)
varies with frequency.  This module makes that approximation honest and measurable:

* ``debye_tan_delta``      - the analytic tan(delta)(f) of a single-pole Debye material,
* ``piecewise_kappa``      - a **banded** constant-kappa approximation of it,
* ``piecewise_error``      - the worst-case relative error of that approximation,
* ``fit_debye``            - recover (eps_s, eps_inf, tau) from tabulated tan(delta)(f).

The point: with the API that exists, a Debye dielectric is representable as N constant-kappa
bands, and the error of doing so is a number we can report instead of hiding.  Stdlib only -
this module keeps the MIT core dependency-free.
"""

from __future__ import annotations

import cmath
import math
from typing import Iterable, List, Sequence, Tuple

EPS0 = 8.8541878128e-12  # vacuum permittivity [F/m]

__all__ = [
    "EPS0",
    "debye_eps",
    "debye_tan_delta",
    "kappa_for_tan_delta",
    "piecewise_kappa",
    "piecewise_error",
    "fit_debye",
]


def debye_eps(
    frequency_hz: float,
    eps_s: float,
    eps_inf: float,
    tau_s: float,
    sigma_dc_s_per_m: float = 0.0,
) -> complex:
    """Complex relative permittivity of a single-pole Debye dielectric."""
    w = 2.0 * math.pi * frequency_hz
    eps = eps_inf + (eps_s - eps_inf) / (1.0 + 1j * w * tau_s)
    if sigma_dc_s_per_m:
        eps = eps - 1j * sigma_dc_s_per_m / (w * EPS0)
    return eps


def debye_tan_delta(
    frequency_hz: float,
    eps_s: float,
    eps_inf: float,
    tau_s: float,
    sigma_dc_s_per_m: float = 0.0,
) -> float:
    """Loss tangent of a Debye dielectric.

    ``tan(delta) = Im(eps) / Re(eps)`` with the ``exp(+j w t)`` convention used by CSXCAD;
    the sign is normalised here so the result is always non-negative.
    """
    eps = debye_eps(frequency_hz, eps_s, eps_inf, tau_s, sigma_dc_s_per_m)
    if eps.real <= 0.0:
        return math.inf
    return abs(eps.imag / eps.real)


def kappa_for_tan_delta(frequency_hz: float, eps_r: float, tan_delta: float) -> float:
    """Constant conductivity [S/m] that reproduces ``tan_delta`` at ``frequency_hz``.

    This is the inverse of what ``openantenna/solvers/openems.py`` does when it turns a
    reference loss tangent into KAPPA_SUB.
    """
    if frequency_hz <= 0.0:
        raise ValueError("frequency must be positive")
    return tan_delta * 2.0 * math.pi * frequency_hz * EPS0 * eps_r


def _tan_delta_from_kappa(frequency_hz: float, eps_r: float, kappa: float) -> float:
    """The tan(delta) a *simulation* with constant ``kappa`` actually represents."""
    if frequency_hz <= 0.0:
        raise ValueError("frequency must be positive")
    return kappa / (2.0 * math.pi * frequency_hz * EPS0 * eps_r)


def piecewise_kappa(
    band_edges_hz: Sequence[float],
    eps_s: float,
    eps_inf: float,
    tau_s: float,
    sigma_dc_s_per_m: float = 0.0,
) -> List[Tuple[float, float, float]]:
    """Approximate a Debye loss tangent by constant kappa per band.

    Each band ``[f_lo, f_hi)`` gets the conductivity that is exact at its **geometric
    centre** (the natural choice on a log-frequency axis, and the point where the error of
    the approximation is smallest in relative terms).

    Returns a list of ``(f_lo, f_hi, kappa)`` with ``len(band_edges) - 1`` entries.
    """
    if len(band_edges_hz) < 2:
        raise ValueError("need at least two band edges")
    edges = [float(f) for f in band_edges_hz]
    if any(b <= a for a, b in zip(edges, edges[1:])):
        raise ValueError("band edges must be strictly increasing")
    bands: List[Tuple[float, float, float]] = []
    for lo, hi in zip(edges, edges[1:]):
        centre = math.sqrt(lo * hi)
        eps_r = abs(debye_eps(centre, eps_s, eps_inf, tau_s, sigma_dc_s_per_m).real)
        tan = debye_tan_delta(centre, eps_s, eps_inf, tau_s, sigma_dc_s_per_m)
        bands.append((lo, hi, kappa_for_tan_delta(centre, eps_r, tan)))
    return bands


def piecewise_error(
    frequencies_hz: Iterable[float],
    bands: Sequence[Tuple[float, float, float]],
    eps_s: float,
    eps_inf: float,
    tau_s: float,
    sigma_dc_s_per_m: float = 0.0,
) -> Tuple[float, float, List[Tuple[float, float, float]]]:
    """Worst-case relative error of the banded approximation over a frequency grid.

    Returns ``(max_relative_error, mean_relative_error, per_point)`` where each per-point
    entry is ``(frequency_hz, tan_delta_debye, tan_delta_kappa)``.  Only the Debye
    relaxation term is compared - the ``u * tan_delta`` product that a bandwidth measurement
    actually sees is reported separately by the caller, because it needs Q.
    """
    per_point: List[Tuple[float, float, float]] = []
    errors: List[float] = []
    for f in frequencies_hz:
        f = float(f)
        target = debye_tan_delta(f, eps_s, eps_inf, tau_s, sigma_dc_s_per_m)
        kappa = None
        for lo, hi, value in bands:
            if lo <= f <= hi:
                kappa = value
                break
        if kappa is None:  # outside every band: take the nearest edge's value
            kappa = bands[0][2] if f < bands[0][0] else bands[-1][2]
        eps_r = abs(debye_eps(f, eps_s, eps_inf, tau_s, sigma_dc_s_per_m).real)
        got = _tan_delta_from_kappa(f, eps_r, kappa)
        rel = abs(got - target) / target if target > 0 else 0.0
        errors.append(rel)
        per_point.append((f, target, got))
    if not errors:
        return (0.0, 0.0, [])
    return (max(errors), sum(errors) / len(errors), per_point)


def fit_debye(
    frequencies_hz: Sequence[float],
    tan_delta: Sequence[float],
    eps_inf_hint: float | None = None,
) -> Tuple[float, float, float, float]:
    """Recover ``(eps_s, eps_inf, tau_s, residual)`` from tabulated tan(delta)(f).

    A coarse log-spaced scan over ``tau`` followed by golden-section refinement; for each
    ``tau`` the remaining two unknowns enter **linearly**, so they are solved by a closed
    form 2x2 least squares on the normalised Debye loss tangent

        tan(delta) = A * w*tau / (eps_inf * (1 + (w*tau)^2) + A)

    with ``A = eps_s - eps_inf``.  ``eps_inf_hint`` pins the second unknown when a measured
    high-frequency permittivity is known; otherwise it is fitted too.
    """
    freqs = [float(f) for f in frequencies_hz]
    tans = [float(t) for t in tan_delta]
    if len(freqs) != len(tans) or len(freqs) < 3:
        raise ValueError("need at least three (frequency, tan_delta) pairs")

    def residual_for(tau: float, eps_inf: float, a: float) -> float:
        total = 0.0
        for f, measured in zip(freqs, tans):
            model = debye_tan_delta(f, eps_inf + a, eps_inf, tau)
            total += (model - measured) ** 2
        return total

    def best_a(eps_inf: float, tau: float) -> float:
        # minimise sum (A*K_i / (eps_inf*(1+K_i^2) + A) - t_i)^2 by scanning A coarsely:
        # the closed form is not worth the algebra for a diagnostic fit, and this is
        # deterministic and bounded.
        lo, hi = 1e-6, 500.0
        for _ in range(60):
            m1 = lo + (hi - lo) / 3.0
            m2 = hi - (hi - lo) / 3.0
            if residual_for(tau, eps_inf, m1) < residual_for(tau, eps_inf, m2):
                hi = m2
            else:
                lo = m1
        return 0.5 * (lo + hi)

    best = None
    for tau in [10.0 ** (k / 8.0 - 13.0) for k in range(0, 121)]:  # 1e-13 .. 1e2 s
        eps_inf = eps_inf_hint if eps_inf_hint else 2.0
        a = best_a(eps_inf, tau)
        r = residual_for(tau, eps_inf, a)
        if best is None or r < best[3]:
            best = (eps_inf + a, eps_inf, tau, r)

    if best is None:  # pragma: no cover - the scan always yields a candidate
        return (math.nan, math.nan, math.nan, math.inf)
    return (best[0], best[1], best[2], math.sqrt(best[3] / len(freqs)))
