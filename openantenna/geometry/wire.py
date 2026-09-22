"""Neutral wire-antenna geometry — the second family of structures (Phase 2).

Deliberately parametric, and honest about what is *not* modelled:

* ``length_factor`` is an **input**, not a physics claim.  A real wire dipole
  resonates a few percent short of ``0.5 lambda`` because of the end effect and the
  conductor radius; that shortening is not computed here.  Callers who want it pass
  a smaller factor and say why.
* The thin-wire assumption (``radius << length``) is enforced, because every
  closed-form and NEC-style result breaks down for thick wires.
* Nothing here predicts impedance or gain: those come from a solver (the NEC2
  adapter) or from measurement.

Analytic references used by the tests come from elsewhere in the package (a
half-wave dipole's directivity of 1.6409, already a golden value in
``tests/test_patterns.py``) — not from memory.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List

C0 = 299792458.0

#: a wire is treated as "thin" only up to this radius/length ratio
MAX_RADIUS_RATIO = 0.05


def wavelength0(frequency_hz: float) -> float:
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be > 0")
    return C0 / frequency_hz


@dataclass
class WireDesign:
    """One straight wire radiator (dipole, or monopole above a ground plane)."""

    frequency_hz: float
    length_m: float
    radius_m: float
    feed_gap_m: float
    ground_plane: bool = False
    segments: int = 31
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.frequency_hz <= 0:
            raise ValueError("frequency_hz must be > 0")
        if self.length_m <= 0:
            raise ValueError("length_m must be > 0")
        if self.radius_m <= 0:
            raise ValueError("radius_m must be > 0")
        if self.radius_m / self.length_m > MAX_RADIUS_RATIO:
            raise ValueError(
                f"radius/length = {self.radius_m / self.length_m:.4f} exceeds the thin-wire "
                f"assumption ({MAX_RADIUS_RATIO}); thin-wire results do not apply"
            )
        if self.feed_gap_m <= 0 or self.feed_gap_m >= self.length_m:
            raise ValueError("feed_gap_m must be > 0 and smaller than length_m")
        if self.segments < 5:
            raise ValueError("segments must be >= 5 to resolve the current distribution")
        if not self.ground_plane and self.segments % 2 == 0:
            raise ValueError(
                "a centre-fed dipole needs an ODD number of segments so that a segment "
                "centre lands on the feed point (NEC convention)"
            )

    @property
    def wavelength_m(self) -> float:
        return wavelength0(self.frequency_hz)

    @property
    def length_lambda(self) -> float:
        return self.length_m / self.wavelength_m

    @property
    def radius_lambda(self) -> float:
        return self.radius_m / self.wavelength_m

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frequency_hz": self.frequency_hz,
            "length_m": self.length_m,
            "radius_m": self.radius_m,
            "feed_gap_m": self.feed_gap_m,
            "ground_plane": self.ground_plane,
            "segments": self.segments,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WireDesign":
        design = cls(
            frequency_hz=float(data["frequency_hz"]),
            length_m=float(data["length_m"]),
            radius_m=float(data["radius_m"]),
            feed_gap_m=float(data["feed_gap_m"]),
            ground_plane=bool(data.get("ground_plane", False)),
            segments=int(data.get("segments", 31)),
        )
        # keep any warnings that travelled with the document, so a round-trip is lossless
        design.warnings = [str(w) for w in data.get("warnings", [])]
        return design

    def summary(self) -> str:
        kind = "monopole over ground plane" if self.ground_plane else "centre-fed dipole"
        lines = [
            f"wire             : {kind}",
            f"frequency        : {self.frequency_hz / 1e9:.4f} GHz (lambda0 = {self.wavelength_m * 1e3:.3f} mm)",
            f"length           : {self.length_m * 1e3:.3f} mm ({self.length_lambda:.4f} lambda0)",
            f"radius           : {self.radius_m * 1e3:.3f} mm ({self.radius_lambda:.6f} lambda0)",
            f"feed gap         : {self.feed_gap_m * 1e3:.3f} mm",
            f"segments         : {self.segments}",
            "note             : impedance and gain must come from a solver (NEC2) or a "
            "measurement; this geometry module predicts neither.",
        ]
        for warning in self.warnings:
            lines.append(f"WARNING          : {warning}")
        return "\n".join(lines)


def synthesize_dipole(
    frequency_hz: float,
    radius_m: float = 1.0e-3,
    length_factor: float = 0.5,
    segments: int = 31,
) -> WireDesign:
    """Half-wave-style centre-fed dipole.

    ``length = length_factor * lambda0`` with ``length_factor = 0.5`` by default.
    The end-effect shortening is **not** applied — pass a smaller factor if your
    design uses one, and record the reason.
    """
    if not 0.2 <= length_factor <= 0.6:
        raise ValueError("length_factor outside the dipole range 0.2 .. 0.6")
    lam = wavelength0(frequency_hz)
    length = length_factor * lam
    if segments % 2 == 0:
        segments += 1  # a centre-fed dipole needs a segment centre at the feed
    design = WireDesign(
        frequency_hz=frequency_hz,
        length_m=length,
        radius_m=radius_m,
        feed_gap_m=length / segments,
        segments=segments,
    )
    if length_factor != 0.5:
        design.warnings.append(
            f"length_factor = {length_factor:g} deviates from 0.5 lambda; make sure this is "
            "the end-effect shortening you intend, not an accident"
        )
    return design


def synthesize_monopole(
    frequency_hz: float,
    radius_m: float = 1.0e-3,
    length_factor: float = 0.25,
    segments: int = 21,
) -> WireDesign:
    """Quarter-wave monopole above an ideal ground plane (image theory)."""
    if not 0.1 <= length_factor <= 0.3:
        raise ValueError("length_factor outside the monopole range 0.1 .. 0.3")
    lam = wavelength0(frequency_hz)
    length = length_factor * lam
    return WireDesign(
        frequency_hz=frequency_hz,
        length_m=length,
        radius_m=radius_m,
        feed_gap_m=min(length / segments, 1.0e-3),
        ground_plane=True,
        segments=segments,
    )
