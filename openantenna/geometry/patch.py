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
    """Effective permittivity ``ereff`` of the microstrip-like patch line."""
    if height_m <= 0 or width_m <= 0 or epsilon_r <= 0:
        raise ValueError("epsilon_r, height_m and width_m must all be > 0")
    ratio = height_m / width_m
    return 0.5 * (epsilon_r + 1.0) + 0.5 * (epsilon_r - 1.0) * (1.0 + 12.0 * ratio) ** -0.5


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
    ereff = effective_permittivity(epsilon_r, height_m, width_m)
    dl = delta_length(height_m, ereff, width_m)
    return C0 / (2.0 * (length_m + 2.0 * dl) * math.sqrt(ereff))


def estimate_fractional_bandwidth(
    epsilon_r: float, height_m: float, width_m: float, length_m: float, frequency_hz: float
) -> float:
    """Very rough VSWR <= 2 bandwidth estimate (fraction of f0).

    Uses the widely quoted empirical relation
    ``B ~ 3.77 * (er-1)/er^2 * (h/lambda0) * (W/L)``.  It is an order-of-magnitude
    aid for a *matched* patch; it is not a substitute for a swept simulation.
    """
    if epsilon_r <= 1.0:
        return float("nan")
    lam0 = wavelength0(frequency_hz)
    return (
        3.77
        * (epsilon_r - 1.0)
        / (epsilon_r ** 2)
        * (height_m / lam0)
        * (width_m / length_m)
    )


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
    warnings: List[str] = field(default_factory=list)

    @property
    def frequency_error_hz(self) -> float:
        return self.achieved_frequency_hz - self.target_frequency_hz

    def to_dict(self) -> dict:
        return {
            "width_m": self.width_m,
            "length_m": self.length_m,
            "epsilon_eff": self.epsilon_eff,
            "delta_l_m": self.delta_l_m,
            "target_frequency_hz": self.target_frequency_hz,
            "achieved_frequency_hz": self.achieved_frequency_hz,
            "fractional_bandwidth_est": self.fractional_bandwidth_est,
            "epsilon_r": self.epsilon_r,
            "height_m": self.height_m,
            "feed_mode": self.feed_mode,
            "inset_depth_m": self.inset_depth_m,
            "warnings": list(self.warnings),
        }

    def summary(self) -> str:
        lines = [
            f"target f0        : {self.target_frequency_hz / 1e9:.4f} GHz",
            f"substrate        : eps_r={self.epsilon_r:g}, h={self.height_m * 1e3:.3f} mm",
            f"patch W x L      : {self.width_m * 1e3:.3f} x {self.length_m * 1e3:.3f} mm",
            f"eps_eff          : {self.epsilon_eff:.4f}",
            f"fringing dL      : {self.delta_l_m * 1e3:.4f} mm (per side)",
            f"resonance check  : {self.achieved_frequency_hz / 1e9:.4f} GHz "
            f"(delta {self.frequency_error_hz / 1e6:+.3f} MHz)",
            f"BW estimate      : ~{self.fractional_bandwidth_est * 100.0:.2f} % (VSWR<=2, crude)",
        ]
        if self.feed_mode == "inset":
            lines.append(f"inset depth      : {self.inset_depth_m * 1e3:.3f} mm (approx., verify)")
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
    if height_m / wavelength0(frequency_hz) > 0.01:
        warnings.append(
            "Substrate is electrically thick (h/lambda0 > 0.01): the transmission-line "
            "model is no longer reliable, expect a resonance shift and surface waves."
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

    return PatchDesign(
        width_m=width,
        length_m=length,
        epsilon_eff=ereff,
        delta_l_m=dl,
        target_frequency_hz=frequency_hz,
        achieved_frequency_hz=resonant_frequency(epsilon_r, height_m, width, length),
        fractional_bandwidth_est=estimate_fractional_bandwidth(
            epsilon_r, height_m, width, length, frequency_hz
        ),
        epsilon_r=epsilon_r,
        height_m=height_m,
        feed_mode=feed_mode,
        inset_depth_m=inset,
        warnings=warnings,
    )
