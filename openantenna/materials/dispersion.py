"""Frequency-dispersion models for dielectric and metallic materials.

Pure standard library (``math`` / ``cmath`` only) - no numpy, no scipy.

Models
------
Debye (single relaxation pole)::

    eps'(w)  = eps_inf + (eps_s - eps_inf) / (1 + (w*tau)**2)
    eps''(w) = (eps_s - eps_inf) * w*tau / (1 + (w*tau)**2)

    eps(w)   = eps_inf + (eps_s - eps_inf) / (1 + j*w*tau) - j*sigma_dc/(w*eps0)

Lorentz (damped resonant oscillator)::

    eps(w)   = eps_inf + (eps_s - eps_inf) * w0**2 / (w0**2 - w**2 + j*gamma*w)

Drude (free-electron / metal, no restoring force)::

    eps(w)   = eps_inf - wp**2 / (w**2 + j*gamma*w)

Conventions
-----------
* ``w = 2*pi*f``, SI units (Hz, seconds, S/m).
* Time convention ``exp(+j*w*t)``; lossy material terms are of the form
  ``-j*eps''`` so that ``eps'' > 0`` means loss.
* Frequencies must be strictly positive; ``f = 0`` raises ``ValueError``
  (Debye-with-sigma and Drude are singular at DC and are handled by the
  caller, not silently by these functions).
* The anisotropy of real laminates (e.g. woven-glass FR-4) is **not**
  modelled - these are scalar (isotropic) models.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

#: Vacuum permittivity [F/m].
EPS0 = 8.8541878128e-12

#: Vacuum permeability [H/m] (unused here, kept for reference by callers).
MU0 = 1.25663706212e-6

#: Speed of light in vacuum [m/s].
C0 = 299792458.0


def _check_freq(frequency_hz: float) -> float:
    try:
        f = float(frequency_hz)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"frequency must be a number, got {frequency_hz!r}") from exc
    if not math.isfinite(f):
        raise ValueError(f"frequency must be finite, got {frequency_hz!r}")
    if f <= 0.0:
        raise ValueError(
            f"frequency must be > 0 Hz (got {frequency_hz!r}); DC is singular for "
            "Debye-with-sigma and Drude models"
        )
    return f


def _check_tau(tau_s: float) -> float:
    tau = float(tau_s)
    if not math.isfinite(tau) or tau <= 0.0:
        raise ValueError(f"relaxation time tau must be > 0 s, got {tau_s!r}")
    return tau


# --------------------------------------------------------------------------
# Forward models (pure functions: one frequency -> one complex permittivity)
# --------------------------------------------------------------------------
def debye_eps(
    frequency_hz: float,
    eps_inf: float,
    delta_eps: float,
    tau_s: float,
    sigma_dc_s_per_m: float = 0.0,
) -> complex:
    """Single-pole Debye permittivity at ``frequency_hz``.

    ``delta_eps = eps_s - eps_inf`` is the relaxation strength
    (``delta_eps > 0`` for a normal polar dielectric).  ``sigma_dc`` adds a
    free-charge (ohmic) loss term ``-j*sigma/(w*eps0)``.
    """
    f = _check_freq(frequency_hz)
    tau = _check_tau(tau_s)
    w = 2.0 * math.pi * f
    eps = complex(eps_inf) + complex(delta_eps) / complex(1.0, w * tau)
    if sigma_dc_s_per_m:
        eps -= complex(0.0, float(sigma_dc_s_per_m) / (w * EPS0))
    return eps


def lorentz_eps(
    frequency_hz: float,
    eps_inf: float,
    delta_eps: float,
    resonance_hz: float,
    gamma_hz: float,
) -> complex:
    """Damped-oscillator (Lorentz) permittivity at ``frequency_hz``.

    ``resonance_hz`` is the transverse resonance ``f0 = w0/(2*pi)`` and
    ``gamma_hz`` the damping width ``gamma/(2*pi)``.  ``delta_eps`` is the
    oscillator strength (difference between the static and high-frequency
    limits of the resonance term, i.e. ``eps(0) - eps_inf`` for gamma > 0).
    """
    f = _check_freq(frequency_hz)
    f0 = _check_freq(resonance_hz)
    if gamma_hz < 0:
        raise ValueError(f"gamma_hz must be >= 0, got {gamma_hz!r}")
    w = 2.0 * math.pi * f
    w0 = 2.0 * math.pi * f0
    g = 2.0 * math.pi * float(gamma_hz)
    denom = complex(w0 * w0 - w * w, g * w)
    return complex(eps_inf) + complex(delta_eps) * w0 * w0 / denom


def drude_eps(
    frequency_hz: float,
    eps_inf: float,
    plasma_freq_hz: float,
    gamma_hz: float = 0.0,
) -> complex:
    """Drude (free-electron) permittivity at ``frequency_hz``.

    ``plasma_freq_hz`` is ``wp/(2*pi)`` and ``gamma_hz`` the collision
    frequency ``gamma/(2*pi)``.  Use for metals (copper: wp/(2*pi) ~ 1.9e15 Hz,
    gamma/(2*pi) ~ 4.5e12 Hz for the simple Drude picture).
    """
    f = _check_freq(frequency_hz)
    fp = _check_freq(plasma_freq_hz)
    if gamma_hz < 0:
        raise ValueError(f"gamma_hz must be >= 0, got {gamma_hz!r}")
    w = 2.0 * math.pi * f
    wp = 2.0 * math.pi * fp
    g = 2.0 * math.pi * float(gamma_hz)
    return complex(eps_inf) - complex(wp * wp) / complex(w * w, g * w)


def apparent_tan_delta(eps: complex) -> float:
    """Loss tangent ``-Im(eps)/Re(eps)`` of a complex relative permittivity.

    Returns ``0.0`` when the real part is zero (no well-defined ratio).
    """
    e = complex(eps)
    if e.real == 0.0:
        return 0.0
    return -e.imag / e.real


def loss_tangent(eps: complex) -> float:
    """Alias of :func:`apparent_tan_delta` (kept for readability in callers)."""
    return apparent_tan_delta(eps)


# --------------------------------------------------------------------------
# Frequency-response containers
# --------------------------------------------------------------------------
@dataclass
class DebyeParams:
    """Parameters of a single-pole Debye model (JSON-serializable)."""

    eps_inf: float
    delta_eps: float
    tau_s: float
    sigma_dc_s_per_m: float = 0.0

    @property
    def eps_s(self) -> float:
        """Static (low-frequency) permittivity ``eps_inf + delta_eps``."""
        return self.eps_inf + self.delta_eps

    @property
    def is_physical(self) -> bool:
        """True when the parameters are in the physically meaningful range."""
        return self.eps_inf > 0.0 and self.delta_eps > 0.0 and self.tau_s > 0.0

    def evaluate(self, frequency_hz: float) -> complex:
        return debye_eps(
            frequency_hz,
            self.eps_inf,
            self.delta_eps,
            self.tau_s,
            self.sigma_dc_s_per_m,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "debye",
            "poles": 1,
            "eps_inf": self.eps_inf,
            "delta_eps": self.delta_eps,
            "eps_s": self.eps_s,
            "tau_s": self.tau_s,
            "sigma_dc_s_per_m": self.sigma_dc_s_per_m,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DebyeParams":
        return cls(
            eps_inf=float(data["eps_inf"]),
            delta_eps=float(data["delta_eps"]),
            tau_s=float(data["tau_s"]),
            sigma_dc_s_per_m=float(data.get("sigma_dc_s_per_m", 0.0)),
        )


@dataclass
class FitResult:
    """Result of a 1-pole Debye grid-search fit against sampled data."""

    params: DebyeParams
    rmse_eps_real: float
    rmse_eps_imag: float
    rmse_total: float
    n_points: int
    freqs_hz: list[float] = field(default_factory=list)
    residuals_real: list[float] = field(default_factory=list)
    residuals_imag: list[float] = field(default_factory=list)
    method: str = "grid-search + 2-parameter linear least squares"
    notes: list[str] = field(default_factory=list)

    @property
    def is_physical(self) -> bool:
        return self.params.is_physical

    def to_dict(self) -> dict[str, Any]:
        return {
            "params": self.params.to_dict(),
            "rmse_eps_real": self.rmse_eps_real,
            "rmse_eps_imag": self.rmse_eps_imag,
            "rmse_total": self.rmse_total,
            "n_points": self.n_points,
            "method": self.method,
            "is_physical": self.is_physical,
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------
# Fitting (no scipy: closed-form linear step inside a grid search over tau)
# --------------------------------------------------------------------------
def _lsq_for_tau(
    freqs: Sequence[float],
    eps_real: Sequence[float],
    eps_imag: Sequence[float],
    tau: float,
) -> tuple[float, float, float] | None:
    """Best ``(eps_inf, delta_eps, rmse)`` for a fixed ``tau``.

    For fixed ``tau`` the Debye model is *linear* in ``(eps_inf, delta_eps)``::

        x_i = 1/(1 + (w_i*tau)**2)      y_i = (w_i*tau)/(1 + (w_i*tau)**2)
        eps'_i  = eps_inf + delta_eps*x_i
        eps''_i = delta_eps*y_i

    so ordinary least squares reduces to a 2x2 normal-equation system that is
    solved in closed form here.  Only ``tau`` needs a search.
    """
    n = len(freqs)
    if n == 0:
        return None
    xs = [0.0] * n
    ys = [0.0] * n
    for i, f in enumerate(freqs):
        wt = 2.0 * math.pi * f * tau
        d = 1.0 + wt * wt
        xs[i] = 1.0 / d
        ys[i] = wt / d
    sum_x = sum(xs)
    ser_x = sum(xs[i] * eps_real[i] for i in range(n))
    sey_y = sum(eps_imag[i] * ys[i] for i in range(n))
    sxx = sum(x * x for x in xs)
    syy = sum(y * y for y in ys)
    ser = sum(eps_real)
    denom = sxx + syy - sum_x * sum_x / n
    if abs(denom) < 1e-30:
        return None
    delta = (ser_x + sey_y - ser * sum_x / n) / denom
    eps_inf = (ser - delta * sum_x) / n
    # residual
    sse_r = 0.0
    sse_i = 0.0
    for i in range(n):
        model_r = eps_inf + delta * xs[i]
        model_i = delta * ys[i]
        sse_r += (eps_real[i] - model_r) ** 2
        sse_i += (eps_imag[i] - model_i) ** 2
    rmse = math.sqrt((sse_r + sse_i) / (2.0 * n))
    return eps_inf, delta, rmse


def fit_debye_1pole(
    freqs_hz: Sequence[float],
    eps_real: Sequence[float],
    eps_imag: Sequence[float],
    tau_bounds_s: tuple[float, float] | None = None,
    n_tau: int = 240,
    refine_rounds: int = 4,
) -> FitResult:
    """Fit a single-pole Debye model to ``(f, eps', eps'')`` samples.

    Strategy (deliberately scipy-free):

    1. log-spaced grid search over ``tau``; for every candidate ``tau`` the
       optimal ``(eps_inf, delta_eps)`` is obtained in closed form (see
       :func:`_lsq_for_tau`);
    2. a few rounds of golden-section refinement inside the bracket around the
       best grid point.

    ``tau_bounds_s`` defaults to ``[1e-3/(2*pi*f_max), 1e3/(2*pi*f_min)]``,
    which brackets the relaxation times that a measurement window can resolve.

    This is a heuristic fit.  It does **not** report confidence intervals and
    makes no claim of statistical optimality beyond the least-squares
    objective on the sampled points.
    """
    n = len(freqs_hz)
    if n < 3:
        raise ValueError("need at least 3 data points to fit a 1-pole Debye model")
    if len(eps_real) != n or len(eps_imag) != n:
        raise ValueError("freqs_hz, eps_real and eps_imag must have the same length")
    freqs = [_check_freq(f) for f in freqs_hz]
    er = [float(v) for v in eps_real]
    ei = [float(v) for v in eps_imag]

    if tau_bounds_s is None:
        lo = 1e-3 / (2.0 * math.pi * max(freqs))
        hi = 1e3 / (2.0 * math.pi * min(freqs))
    else:
        lo, hi = float(tau_bounds_s[0]), float(tau_bounds_s[1])
    if not (lo > 0.0 and hi > lo):
        raise ValueError(f"invalid tau bounds: {lo!r} .. {hi!r}")

    def objective(tau: float) -> tuple[float, float, float] | None:
        return _lsq_for_tau(freqs, er, ei, tau)

    # --- stage 1: log-spaced grid -----------------------------------------
    log_lo, log_hi = math.log10(lo), math.log10(hi)
    best_tau = None
    best: tuple[float, float, float] | None = None
    step = (log_hi - log_lo) / (n_tau - 1) if n_tau > 1 else 0.0
    for i in range(n_tau):
        tau = 10.0 ** (log_lo + i * step)
        cand = objective(tau)
        if cand is None:
            continue
        if best is None or cand[2] < best[2]:
            best, best_tau = cand, tau
    if best is None or best_tau is None:
        raise ValueError("Debye fit failed: no usable tau candidate")

    # --- stage 2: golden-section refinement -------------------------------
    a = best_tau / (10.0 ** max(step * 2.0, 1e-6))
    b = best_tau * (10.0 ** max(step * 2.0, 1e-6))
    a = max(a, lo * 1e-3)
    b = min(b, hi * 1e3)
    inv_phi = (math.sqrt(5.0) - 1.0) / 2.0
    c = b - inv_phi * (b - a)
    d = a + inv_phi * (b - a)
    fc, fd = objective(c), objective(d)
    for _ in range(max(0, refine_rounds) + 24):
        if b - a < 1e-14 * max(b, 1e-30):
            break
        if fc is None or (fd is not None and fd[2] < fc[2]):
            a, c, fc = c, d, fd
            d = a + inv_phi * (b - a)
            fd = objective(d)
        else:
            b, d, fd = d, c, fc
            c = b - inv_phi * (b - a)
            fc = objective(c)
    for cand_tau, cand in ((c, fc), (d, fd), (best_tau, best)):
        if cand is not None and cand[2] < best[2]:
            best, best_tau = cand, cand_tau

    eps_inf, delta, _ = best
    params = DebyeParams(eps_inf=eps_inf, delta_eps=delta, tau_s=best_tau)

    residuals_real: list[float] = []
    residuals_imag: list[float] = []
    sse_r = 0.0
    sse_i = 0.0
    for f, r, im in zip(freqs, er, ei):
        model = params.evaluate(f)
        # Convention fix: callers supply eps'' as a POSITIVE loss term (that is
        # what _lsq_for_tau fits and what apparent_tan_delta reports), while
        # debye_eps() returns the negative imaginary part.  Comparing the two
        # directly inflated every imaginary residual by about 2*eps'', which
        # left the fitted parameters correct but the reported rmse meaningless.
        model_eps_imag = -model.imag
        dr = r - model.real
        di = im - model_eps_imag
        residuals_real.append(dr)
        residuals_imag.append(di)
        sse_r += dr * dr
        sse_i += di * di

    notes: list[str] = []
    if not params.is_physical:
        notes.append(
            "Fitted parameters are outside the physically normal range "
            "(eps_inf > 0, delta_eps > 0, tau > 0). Treat the fit as a "
            "numerical curve fit only, not as a physical relaxation process."
        )
    notes.append("Fit is unweighted; measurement uncertainty is not propagated.")
    if n < 8:
        notes.append(f"Only {n} data points: the fit is weakly constrained.")

    return FitResult(
        params=params,
        rmse_eps_real=math.sqrt(sse_r / n),
        rmse_eps_imag=math.sqrt(sse_i / n),
        rmse_total=math.sqrt((sse_r + sse_i) / (2.0 * n)),
        n_points=n,
        freqs_hz=list(freqs),
        residuals_real=residuals_real,
        residuals_imag=residuals_imag,
        notes=notes,
    )


def fit_debye_from_complex(
    freqs_hz: Sequence[float],
    eps_samples: Iterable[complex],
    **kwargs: Any,
) -> FitResult:
    """Convenience wrapper around :func:`fit_debye_1pole` for complex samples."""
    samples = [complex(e) for e in eps_samples]
    return fit_debye_1pole(
        freqs_hz,
        [e.real for e in samples],
        # Sign convention: debye_eps() returns a NEGATIVE imaginary part, while
        # fit_debye_1pole() expects eps'' as a POSITIVE loss term (see
        # _lsq_for_tau and apparent_tan_delta).  Forwarding e.imag unchanged
        # inverted the sign and produced non-physical fits -- review item Y-01.
        [-e.imag for e in samples],
        **kwargs,
    )
