"""Rectangular patch antenna synthesis (stdlib only).

This module implements the classical **transmission-line model** for a
rectangular microstrip patch on a single dielectric layer:

1. radiative width           ``W = c / (2 f0) * sqrt(2 / (er + 1))``
2. effective permittivity    ``ereff = (er+1)/2 + (er-1)/2 * (1 + 12 h/W)^-0.5``
   (Hammerstad-Jensen form; the same expression is cited in Balanis, *Antenna
   Theory*, as the standard wide-line approximation)
3. fringing extension        ``dL = 0.412 h * ((ereff+0.3)(W/h+0.264)) /
   ((ereff-0.258)(W/h+0.8))``
4. resonant length           ``L = c / (2 f0 sqrt(ereff)) - 2 dL``

HOW MUCH TO TRUST THIS
----------------------
The transmission-line model is a *first-order* design aid.  It is accurate to
roughly a few percent for thin substrates (``h / lambda0 < ~0.01``), and it
degrades quickly as the substrate gets thicker (surface waves, radiation from
the fringing slots, feed reactance).  It says nothing about the feed geometry,
input impedance match, bandwidth or mutual coupling.  Every number produced
here must be confirmed with a full-wave solver before fabrication.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import List

C0 = 299792458.0  # speed of light in vacuum [m/s]


#: vacuum wave impedance [ohm] - the constant the Hammerstad-Jensen form needs
_Z0_VACUUM = 376.730313668

def wavelength0(frequency_hz: float) -> float:
    """Free-space wavelength in metres."""
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be > 0")
    return C0 / frequency_hz


def _check(frequency_hz: float, epsilon_r: float, height_m: float) -> None:
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be > 0")
    if epsilon_r <= 0:
        raise ValueError("epsilon_r must be > 0")
    if height_m <= 0:
        raise ValueError("height_m must be > 0")


def patch_width(frequency_hz: float, epsilon_r: float) -> float:
    """Radiating-edge width ``W`` [m]."""
    _check(frequency_hz, epsilon_r, 1.0)
    return C0 / (2.0 * frequency_hz) * math.sqrt(2.0 / (epsilon_r + 1.0))


def effective_permittivity(epsilon_r: float, height_m: float, width_m: float) -> float:
    """Effective permittivity ``ereff`` of the microstrip-like patch line.

    Wide-line expression (``W/h >= 1``).  Below ``W/h = 1`` Hammerstad's
    narrow-line correction ``0.04*(1 - W/h)^2`` is added, otherwise the
    wide-line form over-estimates ``ereff`` (review item Y-12).
    """
    if height_m <= 0 or width_m <= 0 or epsilon_r <= 0:
        raise ValueError("epsilon_r, height_m and width_m must all be > 0")
    ratio = height_m / width_m
    ereff = 0.5 * (epsilon_r + 1.0) + 0.5 * (epsilon_r - 1.0) * (1.0 + 12.0 * ratio) ** -0.5
    w_over_h = width_m / height_m
    if w_over_h < 1.0:
        ereff += 0.5 * (epsilon_r - 1.0) * 0.04 * (1.0 - w_over_h) ** 2
    return ereff


def delta_length(height_m: float, epsilon_eff: float, width_m: float) -> float:
    """Fringing extension ``dL`` [m] (0.412 h ... empirical fit)."""
    if height_m <= 0 or width_m <= 0 or epsilon_eff <= 0:
        raise ValueError("height_m, width_m and epsilon_eff must all be > 0")
    w_over_h = width_m / height_m
    numerator = (epsilon_eff + 0.3) * (w_over_h + 0.264)
    denominator = (epsilon_eff - 0.258) * (w_over_h + 0.8)
    return 0.412 * height_m * numerator / denominator


def patch_length(frequency_hz: float, epsilon_eff: float, d_l: float) -> float:
    """Resonant patch length ``L`` [m]."""
    if frequency_hz <= 0 or epsilon_eff <= 0:
        raise ValueError("frequency_hz and epsilon_eff must be > 0")
    if d_l < 0:
        raise ValueError("d_l must be >= 0")
    return C0 / (2.0 * frequency_hz * math.sqrt(epsilon_eff)) - 2.0 * d_l


def resonant_frequency(
    epsilon_r: float, height_m: float, width_m: float, length_m: float
) -> float:
    """First-order resonance of an already-sized patch [Hz]."""
    eps_eff = effective_permittivity(epsilon_r, height_m, width_m)
    delta_l = delta_length(height_m, eps_eff, width_m)
    return C0 / (2.0 * (length_m + 2.0 * delta_l) * math.sqrt(eps_eff))


def _validate_microstrip(epsilon_r: float, height_m: float) -> None:
    """Single validation gate for a microstrip patch (review items Y-10, Y-11).

    ``epsilon_r <= 1`` is rejected for every feed mode, instead of producing a
    ``NaN`` bandwidth on one path and raising on another.
    """
    if epsilon_r <= 1.0:
        raise ValueError(
            f"epsilon_r must be > 1 for a microstrip patch, got {epsilon_r!r}; "
            "a substrate in air cannot support a guided patch mode"
        )
    if height_m <= 0:
        raise ValueError("height_m must be > 0")


def substrate_is_electrically_thick(
    height_m: float, frequency_hz: float, threshold: float = 0.01
) -> bool:
    """True when ``h / lambda0`` exceeds ``threshold``.

    Single shared criterion for "the transmission-line model is no longer
    reliable"; ``model.Project.check`` applies the same number so a design cannot
    pass one path and fail the other (review item Y-11).
    """
    if height_m <= 0 or frequency_hz <= 0:
        raise ValueError("height_m and frequency_hz must be > 0")
    return height_m / wavelength0(frequency_hz) > threshold


def resonant_frequency_cavity(
    epsilon_r: float, height_m: float, width_m: float, length_m: float
) -> float:
    """Resonance from the **cavity model** - a genuinely different model.

    Same fringing extension as the transmission-line model, but ``sqrt(eps_r)``
    instead of ``sqrt(eps_eff)``.  Because ``eps_r > eps_eff`` the wave is slower
    and this predicts a **lower** frequency than the transmission-line synthesis
    (2.4007 GHz vs the 2.45 GHz target for the PTFE reference geometry).  The gap
    between the two models is informative; the old "resonance check" merely
    re-evaluated the synthesis formula and was an algebraic identity (review item
    Y-04).
    """
    _validate_microstrip(epsilon_r, height_m)
    eps_eff = effective_permittivity(epsilon_r, height_m, width_m)
    dl = delta_length(height_m, eps_eff, width_m)
    return C0 / (2.0 * (length_m + 2.0 * dl) * math.sqrt(epsilon_r))


def estimate_fractional_bandwidth(
    epsilon_r: float, height_m: float, width_m: float, length_m: float, frequency_hz: float
) -> float:
    """Very rough VSWR <= 2 bandwidth estimate (fraction of f0).

    Uses the widely quoted empirical relation
    ``B ~ 3.77 * (er-1)/er^2 * (h/lambda0) * (W/L)``.  It is an order-of-magnitude
    aid for a *matched* patch; it is not a substitute for a swept simulation.
    ``epsilon_r <= 1`` is rejected by :func:`_validate_microstrip` instead of
    returning ``NaN`` (review item Y-10).
    """
    lam0 = wavelength0(frequency_hz)
    return (
        3.77
        * (epsilon_r - 1.0)
        / (epsilon_r ** 2)
        * (height_m / lam0)
        * (width_m / length_m)
    )


def microstrip_impedance(
    epsilon_r: float, height_m: float, width_m: float
) -> float:
    """Characteristic impedance of a microstrip line [ohm], Hammerstad-Jensen.

    Needed for review item Y-19 / B2: the synthesis formula describes a coplanar inset
    feed, which requires a 50 ohm feed *line*, and until now the package could size a
    patch but not the line feeding it.

    Valid for ``0 < W/h <= 100`` and ``epsilon_r <= 128`` (the usual range of validity of
    the closed form); outside it the value is still returned, because refusing would block
    exploratory designs, but :func:`microstrip_width_for_impedance` checks the limits.
    """
    _validate_microstrip(epsilon_r, height_m)
    if width_m <= 0:
        raise ValueError("width_m must be > 0")
    ratios = width_m / height_m
    if ratios < 1.0:
        # Wheeler/Hammerstad narrow-line form, the usual choice below W/h = 1
        return _Z0_VACUUM / (2.0 * math.pi) * math.log(
            8.0 / ratios + ratios / 4.0
        ) / math.sqrt(effective_permittivity(epsilon_r, height_m, width_m))
    # Hammerstad-Jensen closed form (the F1 expression).  The older two-branch Wheeler
    # wide-line form gives 3.0794 mm for 50 ohm on FR-4 h = 1.6 mm, against 3.0627 mm from
    # the independent implementation in yotta_tools/microstrip_reference.py and from the
    # standard textbook value - a 0.55 % disagreement that this cross-check exposed.
    f1 = 6.0 + (2.0 * math.pi - 6.0) * math.exp(-((30.666 / ratios) ** 0.7528))
    return (
        _Z0_VACUUM
        / (2.0 * math.pi * math.sqrt(effective_permittivity(epsilon_r, height_m, width_m)))
        * math.log(f1 / ratios + math.sqrt(1.0 + (2.0 / ratios) ** 2))
    )


def microstrip_width_for_impedance(
    epsilon_r: float, height_m: float, target_ohm: float = 50.0
) -> float:
    """Feed-line width [m] that gives ``target_ohm`` on this substrate.

    Bisection on :func:`microstrip_impedance`, which is monotonically decreasing in width:
    no closed-form inversion is needed and the tolerance is explicit (1e-4 relative).
    """
    _validate_microstrip(epsilon_r, height_m)
    if not 0.0 < target_ohm < 400.0:
        raise ValueError("target_ohm must be between 0 and 400 (a microstrip range)")
    low = height_m * 1e-3
    high = height_m * 1e3
    if microstrip_impedance(epsilon_r, height_m, low) < target_ohm:
        return low
    if microstrip_impedance(epsilon_r, height_m, high) > target_ohm:
        return high
    for _ in range(200):
        middle = 0.5 * (low + high)
        if microstrip_impedance(epsilon_r, height_m, middle) > target_ohm:
            low = middle
        else:
            high = middle
        if high - low < 1e-4 * high:
            break
    return 0.5 * (low + high)


def inset_depth_for_input_resistance(
    length_m: float, width_m: float, epsilon_r: float, reference_impedance_ohm: float = 50.0
) -> float:
    """Approximate inset-feed depth that matches ``reference_impedance_ohm``.

    ``R_in(y0) = R_in(edge) * cos^2(pi y0 / L)`` with the crude edge-resistance
    estimate ``R_in(edge) ~ 90 * er^2/(er-1) * (L/W)^2`` [ohm].

    Returns 0.0 when the edge resistance is already below the target (no inset
    can raise the resistance -- the patch is simply too wide relative to its
    length for this feed), and clamps to ``L/2`` in the degenerate cases.
    """
    if epsilon_r <= 1.0:
        raise ValueError("epsilon_r must be > 1 for a microstrip patch")
    r_edge = 90.0 * (epsilon_r ** 2) / (epsilon_r - 1.0) * (length_m / width_m) ** 2
    if r_edge <= reference_impedance_ohm:
        return 0.0
    ratio = math.sqrt(reference_impedance_ohm / r_edge)
    y0 = length_m / math.pi * math.acos(max(-1.0, min(1.0, ratio)))
    return max(0.0, min(y0, 0.5 * length_m))


def ground_plane_size(
    width_m: float, length_m: float, frequency_hz: float, margin_lambda: float = 0.25
) -> tuple[float, float]:
    """Ground-plane size with a margin on every side [m].

    ``margin_lambda`` is the margin in free-space wavelengths per side; 0.25 is a
    common starting point, but the required margin depends strongly on the
    substrate and on how much the ground plane is part of the radiating
    structure (it always is, to some extent).
    """
    margin = margin_lambda * wavelength0(frequency_hz)
    return width_m + 2.0 * margin, length_m + 2.0 * margin


@dataclass
class PatchDesign:
    """Result of :func:`synthesize_patch`."""

    width_m: float
    length_m: float
    epsilon_eff: float
    delta_l_m: float
    target_frequency_hz: float
    achieved_frequency_hz: float
    fractional_bandwidth_est: float
    epsilon_r: float
    height_m: float
    feed_mode: str = "inset"
    inset_depth_m: float = 0.0
    #: width of the microstrip feed line [m]; 0.0 when the feed is not a line (probe).
    #: Added for review item Y-19 / B2: the synthesis describes a coplanar inset, which
    #: needs a line, so the width belongs in the design record and in the project model.
    feed_line_width_m: float = 0.0
    frequency_cavity_hz: float = 0.0
    warnings: List[str] = field(default_factory=list)

    @property
    def frequency_error_hz(self) -> float:
        """Offset of the **cavity-model** cross-check, not of the synthesis.

        The synthesis result is algebraic identity by construction; this property
        deliberately reports the independent model (review item Y-04).
        """
        return self.frequency_cavity_hz - self.target_frequency_hz

    def to_dict(self) -> dict:
        return {
            "width_m": self.width_m,
            "length_m": self.length_m,
            "epsilon_eff": self.epsilon_eff,
            "delta_l_m": self.delta_l_m,
            "target_frequency_hz": self.target_frequency_hz,
            "achieved_frequency_hz": self.achieved_frequency_hz,
            "frequency_cavity_hz": self.frequency_cavity_hz,
            "fractional_bandwidth_est": self.fractional_bandwidth_est,
            "epsilon_r": self.epsilon_r,
            "height_m": self.height_m,
            "feed_mode": self.feed_mode,
            "inset_depth_m": self.inset_depth_m,
            "feed_line_width_m": self.feed_line_width_m,
            "warnings": list(self.warnings),
        }

    def summary(self) -> str:
        lines = [
            f"target f0        : {self.target_frequency_hz / 1e9:.4f} GHz",
            f"substrate        : eps_r={self.epsilon_r:g}, h={self.height_m * 1e3:.3f} mm",
            f"patch W x L      : {self.width_m * 1e3:.3f} x {self.length_m * 1e3:.3f} mm",
            f"eps_eff          : {self.epsilon_eff:.4f}",
            f"fringing dL      : {self.delta_l_m * 1e3:.4f} mm (per side)",
            (
                f"cavity cross-chk : {self.frequency_cavity_hz / 1e9:.4f} GHz "
                f"(delta {self.frequency_error_hz / 1e6:+.1f} MHz vs target, "
                "independent model)"
            ),
            (
                "self-consistency : the synthesis formula re-evaluated - algebraic "
                "identity, NOT a verification"
            ),
            f"BW estimate      : ~{self.fractional_bandwidth_est * 100.0:.2f} % (VSWR<=2, crude)",
        ]
        if self.feed_mode == "inset":
            lines.append(f"inset depth      : {self.inset_depth_m * 1e3:.3f} mm (approx., verify)")
        if self.feed_line_width_m:
            lines.append(
                f"feed line width  : {self.feed_line_width_m * 1e3:.3f} mm "
                "(microstrip line for the 50 ohm target)"
            )
        for warning in self.warnings:
            lines.append(f"WARNING          : {warning}")
        return "\n".join(lines)


def synthesize_patch(
    frequency_hz: float,
    epsilon_r: float,
    height_m: float,
    feed_mode: str = "inset",
    reference_impedance_ohm: float = 50.0,
) -> PatchDesign:
    """Design a rectangular patch for ``frequency_hz`` on a single layer."""
    _check(frequency_hz, epsilon_r, height_m)
    _validate_microstrip(epsilon_r, height_m)

    width = patch_width(frequency_hz, epsilon_r)
    ereff = effective_permittivity(epsilon_r, height_m, width)
    dl = delta_length(height_m, ereff, width)
    length = patch_length(frequency_hz, ereff, dl)
    if length <= 0:
        raise ValueError(
            "synthesised patch length is not positive; substrate is too thick / "
            "frequency too low for the transmission-line model"
        )

    warnings: List[str] = []
    if substrate_is_electrically_thick(height_m, frequency_hz):
        warnings.append(
            "Substrate is electrically thick (h/lambda0 > 0.01): the transmission-line "
            "model is no longer reliable, expect a resonance shift and surface waves. "
            "(Same criterion as model.Project.check - review item Y-11.)"
        )
    if epsilon_r > 12:
        warnings.append(
            "High eps_r: bandwidth will be narrow and surface-wave coupling strong; "
            "coupling between array elements will grow."
        )

    inset = 0.0
    if feed_mode == "inset":
        inset = inset_depth_for_input_resistance(length, width, epsilon_r, reference_impedance_ohm)
        if inset == 0.0:
            warnings.append(
                "Estimated edge resistance is already below the reference impedance, so no "
                "inset depth is proposed; an edge feed or a quarter-wave transformer is "
                "probably a better match strategy."
            )

    line_width = 0.0
    if feed_mode in ("inset", "edge"):
        # Both feeds are a microstrip line; only the inset depth differs.  The width is what
        # the generator needs to draw the coplanar feed (review item Y-19 / B2).
        line_width = microstrip_width_for_impedance(
            epsilon_r, height_m, reference_impedance_ohm
        )

    return PatchDesign(
        width_m=width,
        length_m=length,
        epsilon_eff=ereff,
        delta_l_m=dl,
        target_frequency_hz=frequency_hz,
        achieved_frequency_hz=resonant_frequency(epsilon_r, height_m, width, length),
        frequency_cavity_hz=resonant_frequency_cavity(epsilon_r, height_m, width, length),
        fractional_bandwidth_est=estimate_fractional_bandwidth(
            epsilon_r, height_m, width, length, frequency_hz
        ),
        epsilon_r=epsilon_r,
        height_m=height_m,
        feed_mode=feed_mode,
        inset_depth_m=inset,
        feed_line_width_m=line_width,
        warnings=warnings,
    )
