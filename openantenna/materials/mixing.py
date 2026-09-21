"""Two-phase composite mixing rules (pure functions, stdlib only).

All functions take a *matrix* (host) permittivity, a *filler* (inclusion)
permittivity and a filler **volume fraction** ``vf`` in ``[0, 1]``, and return
a scalar effective relative permittivity.  Real inputs give ``float`` results;
complex inputs (i.e. lossy constituents) give ``complex`` results.

Model summary
-------------
==============  ==========================================================
Wiener upper    ``eps_eff = vf*eps_f + (1-vf)*eps_m`` (parallel layering)
Wiener lower    ``eps_eff = 1 / (vf/eps_f + (1-vf)/eps_m)`` (series layering)
Lichtenecker    ``eps_eff = eps_m**(1-vf) * eps_f**vf`` (logarithmic rule)
Maxwell-Garnett ``eps_m * (eps_f + 2eps_m + 2vf(eps_f-eps_m)) /
                 (eps_f + 2eps_m - vf(eps_f-eps_m))``  (spherical inclusions,
                 dilute-filler, asymmetric in the two phases)
Bruggeman       symmetric effective-medium result, see :func:`bruggeman`
==============  ==========================================================

VALIDITY LIMITS - READ BEFORE USING ANY NUMBER FROM THIS MODULE
---------------------------------------------------------------
The mixture formulas above are **quasi-static, homogenised, effective-medium**
results.  They are only defensible when *all* of the following hold:

1. **Scale separation**: every inclusion is much smaller than the wavelength in
   the surrounding medium (``d << lambda``) *and* much smaller than the sample
   thickness.  Once ``d`` approaches a fraction of a wavelength the composite
   scatters coherently, the effective permittivity becomes frequency-dependent
   and (for periodic fillers) direction-dependent - none of that is modelled
   here.
2. **Statistically homogeneous, isotropic, disordered** filler distribution
   with no preferred orientation, no clustering and no alignment.
3. **No percolation**: no connected filler network bridging the sample.
   Near and above the percolation threshold the effective permittivity rises
   steeply with ``vf`` and the formulas (especially Maxwell-Garnett) undershoot
   badly.  See :func:`percolation_warning`.
4. **No interfacial (Maxwell-Wagner) polarisation**: this is a *static* mixing
   description.  At low frequencies, space charge accumulating at conducting
   or high-permittivity interfaces adds a strong relaxational contribution.
   See :func:`maxwell_wagner_warning`.
5. **No chemical interaction, no interphase/sizing layers, no voids or
   porosity**, and no dependence on the host/inclusion contrast ratio beyond
   the idealised spherical geometry.
6. **Only two phases.**  Air voids in a real laminate are a third phase; either
   model them explicitly as an extra step or use a porous-media model.
7. **Bruggeman and the Wiener bounds are symmetric** in the two phases and
   therefore say nothing about which phase is the host; Maxwell-Garnett is
   asymmetric and *must* be given the true matrix phase.  Mixing these up is
   one of the most common (and silent) errors in composites work.

For high-contrast systems (e.g. ``eps_filler ~ 80`` in ``eps_matrix ~ 2.1``)
the different rules disagree by a factor of ~2-3.  Treat any single rule as a
**bracketing estimate**, not as a measurement: report the spread of the models
(see :func:`compare_models`) rather than one number.
"""

from __future__ import annotations

import cmath
import math
from typing import Any, Iterable

#: Below this frequency (Hz) interfacial Maxwell-Wagner polarisation is assumed
#: to be relevant for ordinary composites.
MAXWELL_WAGNER_FREQ_HZ = 1.0e6

#: Below this frequency the warning is upgraded to "strongly affected".
MAXWELL_WAGNER_STRONG_FREQ_HZ = 1.0e4

#: Assumed percolation threshold for a random dispersion of ~spherical fillers.
#: Literature values for spheres sit around 0.16-0.35 depending on packing and
#: polydispersity; 0.30 is used here as a conservative single number.
DEFAULT_PERCOLATION_THRESHOLD = 0.30

#: Relative permittivity of vacuum (for the free-space wavelength in warnings).
C0 = 299792458.0


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _validate_vf(volume_fraction: float) -> float:
    vf = float(volume_fraction)
    if not math.isfinite(vf):
        raise ValueError(f"volume_fraction must be finite, got {volume_fraction!r}")
    if vf < 0.0 or vf > 1.0:
        raise ValueError(
            f"volume_fraction must lie in [0, 1], got {volume_fraction!r}"
        )
    return vf


def _real_positive(*values: float) -> bool:
    for v in values:
        try:
            if isinstance(v, complex):
                return False
            if float(v) <= 0.0:
                return False
        except (TypeError, ValueError):
            return False
    return True


def _as_complex(value: Any) -> complex:
    return complex(value)


# --------------------------------------------------------------------------
# Wiener bounds
# --------------------------------------------------------------------------
def wiener_upper(eps_matrix: float, eps_filler: float, volume_fraction: float) -> float | complex:
    """Wiener *upper* bound (parallel layering): ``vf*eps_f + (1-vf)*eps_m``.

    This is the arithmetic (volume-weighted) average: the electric field is
    assumed parallel to the layers, i.e. the "best case" for the filler.
    """
    vf = _validate_vf(volume_fraction)
    if _real_positive(eps_matrix, eps_filler):
        return vf * float(eps_filler) + (1.0 - vf) * float(eps_matrix)
    return vf * _as_complex(eps_filler) + (1.0 - vf) * _as_complex(eps_matrix)


def wiener_lower(eps_matrix: float, eps_filler: float, volume_fraction: float) -> float | complex:
    """Wiener *lower* bound (series layering): ``1 / (vf/eps_f + (1-vf)/eps_m)``.

    This is the harmonic average: the electric field is assumed perpendicular
    to the layers, i.e. the "worst case" for the filler.
    """
    vf = _validate_vf(volume_fraction)
    if _real_positive(eps_matrix, eps_filler):
        return 1.0 / (vf / float(eps_filler) + (1.0 - vf) / float(eps_matrix))
    return 1.0 / (vf / _as_complex(eps_filler) + (1.0 - vf) / _as_complex(eps_matrix))


def wiener_bounds(
    eps_matrix: float, eps_filler: float, volume_fraction: float
) -> tuple[float | complex, float | complex]:
    """Return ``(lower, upper)`` Wiener bounds for the composite."""
    return (
        wiener_lower(eps_matrix, eps_filler, volume_fraction),
        wiener_upper(eps_matrix, eps_filler, volume_fraction),
    )


# --------------------------------------------------------------------------
# Lichtenecker
# --------------------------------------------------------------------------
def lichtenecker(eps_matrix: float, eps_filler: float, volume_fraction: float) -> float | complex:
    """Lichtenecker logarithmic mixing rule: ``eps_m**(1-vf) * eps_f**vf``.

    Equivalently ``log(eps_eff) = (1-vf)*log(eps_m) + vf*log(eps_f)``.  It lies
    inside the Wiener bounds (as a weighted geometric mean) and is widely used
    for laminates and powders, but it has no rigorous derivation - it is an
    interpolation rule.  Requires positive (or complex) permittivities;
    permittivities that cross zero (e.g. Drude metals below the plasma
    frequency) must not be fed into it.
    """
    vf = _validate_vf(volume_fraction)
    if _real_positive(eps_matrix, eps_filler):
        return math.exp(
            (1.0 - vf) * math.log(float(eps_matrix)) + vf * math.log(float(eps_filler))
        )
    return cmath.exp(
        (1.0 - vf) * cmath.log(_as_complex(eps_matrix))
        + vf * cmath.log(_as_complex(eps_filler))
    )


# --------------------------------------------------------------------------
# Maxwell-Garnett
# --------------------------------------------------------------------------
def maxwell_garnett(
    eps_matrix: float, eps_filler: float, volume_fraction: float
) -> float | complex:
    """Maxwell-Garnett rule for **spherical** inclusions in a host matrix.

    ``eps_eff = eps_m * (eps_f + 2eps_m + 2vf(eps_f - eps_m))
                     / (eps_f + 2eps_m - vf(eps_f - eps_m))``

    Asymmetric: ``eps_matrix`` is the continuous host, ``eps_filler`` the
    dispersed inclusion.  Derived for dilute, non-interacting spheres; for
    ``vf`` beyond roughly 0.2-0.3 the neglect of inclusion-inclusion
    interaction (and, worse, of percolation) dominates the error.
    """
    vf = _validate_vf(volume_fraction)
    if _real_positive(eps_matrix, eps_filler):
        em = float(eps_matrix)
        ef = float(eps_filler)
        num = ef + 2.0 * em + 2.0 * vf * (ef - em)
        den = ef + 2.0 * em - vf * (ef - em)
        if den == 0.0:
            raise ZeroDivisionError(
                "Maxwell-Garnett denominator vanished (resonant inclusion contrast)"
            )
        return em * num / den
    em = _as_complex(eps_matrix)
    ef = _as_complex(eps_filler)
    num = ef + 2.0 * em + 2.0 * vf * (ef - em)
    den = ef + 2.0 * em - vf * (ef - em)
    if den == 0:
        raise ZeroDivisionError(
            "Maxwell-Garnett denominator vanished (resonant inclusion contrast)"
        )
    return em * num / den


# --------------------------------------------------------------------------
# Bruggeman (symmetric effective medium)
# --------------------------------------------------------------------------
def bruggeman(
    eps_matrix: float, eps_filler: float, volume_fraction: float
) -> float | complex:
    """Symmetric Bruggeman effective-medium approximation for spheres.

    Solves ``vf*(eps_f-e)/(eps_f+2e) + (1-vf)*(eps_m-e)/(eps_m+2e) = 0``, which
    for two phases reduces to the quadratic

    ``2e**2 - (3*vf*(eps_f-eps_m) + 2*eps_m - eps_f) * e - eps_f*eps_m = 0``

    and hence to the closed form used here, with
    ``B = 3*vf*(eps_f-eps_m) + 2*eps_m - eps_f`` and
    ``e = (B + sqrt(B**2 + 8*eps_f*eps_m)) / 4``.

    The ``+`` root is the physically relevant branch for positive constituents
    (it reduces to ``eps_m`` at ``vf=0`` and to ``eps_f`` at ``vf=1``).  Unlike
    Maxwell-Garnett the two phases enter symmetrically: no host/inclusion
    distinction is made, which is what makes it usable up to ``vf ~ 0.5``.
    Percolation is still *not* described - the symmetric rule simply
    interpolates through the mixture.
    """
    vf = _validate_vf(volume_fraction)
    use_real = _real_positive(eps_matrix, eps_filler)
    if use_real:
        em: Any = float(eps_matrix)
        ef: Any = float(eps_filler)
    else:
        em = _as_complex(eps_matrix)
        ef = _as_complex(eps_filler)
    b = 3.0 * vf * (ef - em) + 2.0 * em - ef
    disc = b * b + 8.0 * ef * em
    if use_real:
        if disc < 0.0:
            root = cmath.sqrt(disc)
            return (b + root) / 4.0
        return (b + math.sqrt(disc)) / 4.0
    return (b + cmath.sqrt(disc)) / 4.0


# --------------------------------------------------------------------------
# Convenience: all models at once
# --------------------------------------------------------------------------
def compare_models(
    eps_matrix: float,
    eps_filler: float,
    volume_fraction: float,
    frequency_hz: float | None = None,
) -> dict[str, Any]:
    """Evaluate every rule plus the Wiener bounds in one call.

    Returns a plain dict (JSON-serializable when the inputs are real):

    ``matrix``, ``filler``, ``volume_fraction``, ``wiener_lower``,
    ``wiener_upper``, ``lichtenecker``, ``maxwell_garnett``, ``bruggeman``,
    ``spread`` (max-min over the four rules), ``outside_wiener_bounds`` (bool),
    ``warnings`` (list of str), ``validity_note``.
    """
    vf = _validate_vf(volume_fraction)
    lo, hi = wiener_bounds(eps_matrix, eps_filler, vf)
    models = {
        "lichtenecker": lichtenecker(eps_matrix, eps_filler, vf),
        "maxwell_garnett": maxwell_garnett(eps_matrix, eps_filler, vf),
        "bruggeman": bruggeman(eps_matrix, eps_filler, vf),
    }
    values = [float(v.real) if isinstance(v, complex) else float(v) for v in models.values()]
    lo_r = float(lo.real) if isinstance(lo, complex) else float(lo)
    hi_r = float(hi.real) if isinstance(hi, complex) else float(hi)
    outside = [name for name, val in zip(models, values) if val < lo_r - 1e-9 or val > hi_r + 1e-9]

    warnings: list[str] = []
    for fn in (percolation_warning,):
        msg = fn(vf)
        if msg:
            warnings.append(msg)
    if frequency_hz is not None:
        msg = maxwell_wagner_warning(frequency_hz)
        if msg:
            warnings.append(msg)
    if outside:
        warnings.append(
            "Model(s) outside the Wiener bounds ({}). This usually signals a "
            "lossy/complex or resonant contrast; the bounds themselves assume "
            "real, non-resonant phases.".format(", ".join(outside))
        )
    if vf > 0.5:
        warnings.append(
            "Filler volume fraction > 0.5: 'filler in matrix' language is "
            "probably wrong. Re-check which phase is continuous, or switch to "
            "the symmetric Bruggeman rule."
        )
    if eps_filler > 5.0 * max(eps_matrix, 1e-30):
        warnings.append(
            "High permittivity contrast (filler/matrix > 5): the rules disagree "
            "strongly and the field concentrates inside the filler, so filler "
            "losses tend to dominate the composite loss. Use the model spread "
            "as an uncertainty band, not one rule."
        )

    return {
        "matrix": eps_matrix,
        "filler": eps_filler,
        "volume_fraction": vf,
        "wiener_lower": lo,
        "wiener_upper": hi,
        "lichtenecker": models["lichtenecker"],
        "maxwell_garnett": models["maxwell_garnett"],
        "bruggeman": models["bruggeman"],
        "spread": max(values) - min(values) if values else 0.0,
        "inside_wiener_bounds": not outside,
        "outside_wiener_bounds": outside,
        "warnings": warnings,
        "validity_note": (
            "Quasi-static homogenisation: valid only for inclusions much "
            "smaller than the wavelength, a homogeneous/disordered filler "
            "distribution, no percolation and no interfacial polarisation. "
            "These are bracketing estimates, not measurements."
        ),
    }


def format_comparison_table(result: dict[str, Any]) -> str:
    """Render the output of :func:`compare_models` as a plain-text table."""
    def num(value: Any) -> str:
        if isinstance(value, complex):
            return f"{value.real:.6g}{value.imag:+.6g}j"
        return f"{float(value):.6g}"

    rows = [
        ("Wiener lower bound (series)", result["wiener_lower"]),
        ("Lichtenecker (log rule)", result["lichtenecker"]),
        ("Maxwell-Garnett (spheres)", result["maxwell_garnett"]),
        ("Bruggeman (symmetric EMA)", result["bruggeman"]),
        ("Wiener upper bound (parallel)", result["wiener_upper"]),
    ]
    width = max(len(name) for name, _ in rows)
    lines = [
        "eps_matrix = {}   eps_filler = {}   vf = {:.4g}".format(
            num(result["matrix"]), num(result["filler"]), result["volume_fraction"]
        ),
        "",
    ]
    for name, value in rows:
        lines.append(f"  {name:<{width}} : eps_eff = {num(value)}")
    lines.append("")
    lines.append(f"  model spread (max-min) : {result['spread']:.4g}")
    lines.append(
        "  inside Wiener bounds   : {}".format("yes" if result["inside_wiener_bounds"] else "NO")
    )
    if result["warnings"]:
        lines.append("")
        lines.append("  WARNINGS:")
        for w in result["warnings"]:
            lines.append(f"    - {w}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Loss estimation (order-of-magnitude bracketing only)
# --------------------------------------------------------------------------
def estimate_effective_tan_delta(
    eps_matrix: float,
    eps_filler: float,
    volume_fraction: float,
    tan_delta_matrix: float = 0.0,
    tan_delta_filler: float = 0.0,
) -> dict[str, Any]:
    """Bracket the effective loss tangent of a two-phase composite.

    .. warning::

       THIS IS AN ORDER-OF-MAGNITUDE ESTIMATE, NOT AN ACCURATE MODEL.

    Two simple bounds are produced by pushing the *complex* constituent
    permittivities through the two Wiener layering limits and reading off
    ``tan_delta_eff = -Im(eps_eff)/Re(eps_eff)``:

    * ``series`` (field normal to the layering / series capacitance) -> the
      **lower** bound,
    * ``parallel`` (field along the layering) -> the **upper** bound.

    A plain volume-weighted average of the constituent loss tangents is also
    returned as a reference number (``volume_weighted_reference``); it is a
    common shortcut that appears in the literature but has no rigorous basis
    for a lossy mixture.

    Explicit caveats, because they matter more than the numbers:

    * Real composites are neither series nor parallel; the truth is bracketed
      by these two limits, often with a large gap.
    * With a **high-permittivity filler the electric field concentrates in the
      filler**, so the *filler* loss dominates the composite loss - typically
      pushing the result toward (or even above) the filler's own loss tangent,
      not toward the volume-weighted average. A small volume fraction of a
      lossy high-eps filler can therefore dominate the total loss.
    * Interfacial (Maxwell-Wagner) loss, percolation-driven conduction, void,
      moisture and manufacturing variation are all ignored.
    * If the inputs are supplied as *complex* permittivities, the supplied
      imaginary parts are used as-is and ``tan_delta_*`` arguments are ignored
      (to avoid double counting the loss).
    """
    vf = _validate_vf(volume_fraction)
    tdm = float(tan_delta_matrix)
    tdf = float(tan_delta_filler)

    eps_m_complex = complex(eps_matrix) if isinstance(eps_matrix, complex) else complex(
        float(eps_matrix), -float(eps_matrix) * tdm
    )
    eps_f_complex = complex(eps_filler) if isinstance(eps_filler, complex) else complex(
        float(eps_filler), -float(eps_filler) * tdf
    )

    eps_series = 1.0 / (vf / eps_f_complex + (1.0 - vf) / eps_m_complex)
    eps_parallel = vf * eps_f_complex + (1.0 - vf) * eps_m_complex
    # Reference number only: volume-weighted average of the constituent loss
    # tangents.  (The previous `eps_vol_real` intermediate was unused.)
    tan_vol = (1.0 - vf) * (
        -eps_m_complex.imag / eps_m_complex.real if eps_m_complex.real else 0.0
    ) + vf * (-eps_f_complex.imag / eps_f_complex.real if eps_f_complex.real else 0.0)

    tan_series = _tan_of(eps_series)
    tan_parallel = _tan_of(eps_parallel)
    lo, hi = min(tan_series, tan_parallel), max(tan_series, tan_parallel)

    notes = [
        "ORDER-OF-MAGNITUDE ESTIMATE ONLY. Series/parallel layering bounds do "
        "not describe a real disordered composite; the true loss generally "
        "lies between them, and the gap can be large.",
        "Series (field normal to layering) is reported as the lower bound and "
        "parallel (field along layering) as the upper bound.",
        "With a high-permittivity filler the field concentrates in the filler, "
        "so filler loss tends to dominate and the composite loss can approach "
        "or exceed the filler's own tan delta - the volume-weighted average "
        "underestimates this.",
        "Interfacial (Maxwell-Wagner) loss, DC conduction/percolation, voids "
        "and moisture are not included.",
    ]
    if hi > 0.0 and lo > 0.0 and hi / lo > 5.0:
        notes.append(
            "The two bounds differ by more than 5x; treat the result as a "
            "rough range only."
        )
    if vf > 0.0 and isinstance(eps_filler, (int, float)) and float(eps_filler) > 5.0 * float(
        eps_matrix.real if isinstance(eps_matrix, complex) else eps_matrix
    ):
        notes.append(
            "High permittivity contrast: expect the true loss to sit closer to "
            "the filler-dominated (upper) side."
        )

    return {
        "volume_fraction": vf,
        "eps_matrix_complex": eps_m_complex,
        "eps_filler_complex": eps_f_complex,
        "eps_eff_series": eps_series,
        "eps_eff_parallel": eps_parallel,
        "tan_delta_series": tan_series,
        "tan_delta_parallel": tan_parallel,
        "lower_bound": lo,
        "upper_bound": hi,
        "volume_weighted_reference": tan_vol,
        "tan_delta_matrix": tdm,
        "tan_delta_filler": tdf,
        "notes": notes,
    }


def _tan_of(eps: complex) -> float:
    e = complex(eps)
    if e.real == 0.0:
        return 0.0
    return -e.imag / e.real


# --------------------------------------------------------------------------
# Warnings (advisory text only - these are NOT physics models)
# --------------------------------------------------------------------------
def percolation_warning(
    volume_fraction: float, percolation_threshold: float | None = None
) -> str | None:
    """Advisory text when ``vf`` is near/above an assumed percolation threshold.

    Returns ``None`` when no warning is warranted.  The threshold is a rough,
    packing-dependent number (see :data:`DEFAULT_PERCOLATION_THRESHOLD`); the
    return value is a **warning string, not a model** and no physics is applied
    to the permittivity.
    """
    vf = _validate_vf(volume_fraction)
    thr = (
        DEFAULT_PERCOLATION_THRESHOLD
        if percolation_threshold is None
        else float(percolation_threshold)
    )
    if thr <= 0.0 or thr > 1.0:
        raise ValueError(
            f"percolation_threshold must lie in (0, 1], got {percolation_threshold!r}"
        )
    if vf >= thr:
        return (
            f"vf={vf:.4g} is at or above the assumed percolation threshold "
            f"({thr:.4g}): a connected filler network may exist. Effective-medium "
            "mixing rules are unreliable here (they typically undershoot the "
            "permittivity and badly undershoot the loss); model the composite "
            "as a percolating/conductor-loaded system instead."
        )
    if vf >= 0.9 * thr:
        return (
            f"vf={vf:.4g} is approaching the assumed percolation threshold "
            f"({thr:.4g}). Mixing rules are still usable but uncertainty is "
            "already large."
        )
    return None


def maxwell_wagner_warning(frequency_hz: float) -> str | None:
    """Advisory text when interfacial (Maxwell-Wagner) polarisation matters.

    Interfacial polarisation between phases of different conductivity /
    permittivity produces a strong relaxational loss at low frequencies that
    the quasi-static mixing rules completely ignore.  Returns ``None`` when the
    frequency is high enough that the warning is not warranted.
    """
    f = float(frequency_hz)
    if not math.isfinite(f):
        raise ValueError(f"frequency_hz must be finite, got {frequency_hz!r}")
    if f <= 0.0:
        raise ValueError(f"frequency_hz must be > 0, got {frequency_hz!r}")
    if f < MAXWELL_WAGNER_STRONG_FREQ_HZ:
        return (
            f"f={f:.4g} Hz: strongly below the Maxwell-Wagner regime. Interfacial "
            "polarisation dominates the measured permittivity and loss here; the "
            "quasi-static mixing rules in this module do not apply. Use measured "
            "broadband data (and a multi-pole Debye fit) instead."
        )
    if f < MAXWELL_WAGNER_FREQ_HZ:
        return (
            f"f={f:.4g} Hz: below ~1 MHz. Maxwell-Wagner interfacial polarisation "
            "may add a significant relaxational loss that is NOT included in "
            "these quasi-static mixing rules. Increase in importance as f falls "
            "and as the phase conductivity contrast rises."
        )
    return None


def quasi_static_warning(
    frequency_hz: float, particle_size_m: float, eps_eff: float = 1.0
) -> str | None:
    """Advisory text when the inclusion size is not small vs. the wavelength.

    The quasi-static assumption behind every rule in this module needs
    ``particle_size << lambda_eff``.  This helper flags the case
    ``particle_size > lambda_eff/20`` (a conventional rule of thumb, not a
    sharp transition) and returns ``None`` otherwise.
    """
    f = float(frequency_hz)
    d = float(particle_size_m)
    if f <= 0.0 or not math.isfinite(f):
        raise ValueError(f"frequency_hz must be > 0, got {frequency_hz!r}")
    if d <= 0.0 or not math.isfinite(d):
        raise ValueError(f"particle_size_m must be > 0, got {particle_size_m!r}")
    lam0 = C0 / f
    lam_eff = lam0 / math.sqrt(max(float(eps_eff), 1e-12))
    ratio = d / lam_eff
    if ratio > 1.0 / 20.0:
        return (
            f"inclusion size {d:.4g} m is {ratio:.3g} of the effective wavelength "
            f"({lam_eff:.4g} m) at {f:.4g} Hz: the quasi-static homogenisation "
            "assumption (d << lambda) is violated. Coherent scattering and "
            "frequency dispersion must be modelled explicitly."
        )
    return None
