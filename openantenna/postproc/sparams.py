"""S-parameter handling for a single reflection port (stdlib only).

Only what Phase 1 needs: store a frequency trace of S11, compute the usual
matching metrics (return loss, VSWR, -10 dB bandwidth), and read/write
Touchstone ``.s1p`` files so that simulated results can be compared against
VNA measurements with the same tooling.

Sign convention: S11 is stored as a Python complex number with the usual
``exp(+j*omega*t)``-free engineering convention of Touchstone (RI pairs).
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


def vswr_from_gamma(gamma: float) -> float:
    """VSWR from the magnitude of a reflection coefficient.

    The magnitude is taken internally, so any sign of the input is accepted.
    ``|gamma| >= 1`` (active or unphysical) returns ``inf``.
    """
    gamma = abs(float(gamma))
    if gamma >= 1.0:
        return float("inf")
    return (1.0 + gamma) / (1.0 - gamma)


def return_loss_db(gamma: float) -> float:
    """Return loss in dB (positive number means 'good match')."""
    gamma = abs(float(gamma))
    if gamma == 0.0:
        return float("inf")
    return -20.0 * math.log10(gamma)


def _interp(x0: float, y0: float, x1: float, y1: float, target: float) -> float:
    if y1 == y0:
        return x0
    return x0 + (target - y0) * (x1 - x0) / (y1 - y0)


@dataclass
class S11Trace:
    """A frequency trace of S11 (complex reflection coefficient).

    ``has_phase`` records whether the samples really carry phase.  Data built
    from magnitudes alone (:meth:`from_magnitude_db`) has no phase, and every
    phase-dependent quantity - only the input impedance here - is therefore
    meaningless; :meth:`impedance_ohm` refuses to answer in that case (review
    item Y-05).  ``reference_impedance_ohm`` carries the reference impedance
    from a Touchstone option line when one was read (review item Y-15).
    """

    frequencies_hz: List[float]
    s11: List[complex]
    has_phase: bool = True
    reference_impedance_ohm: float = 50.0

    def __post_init__(self) -> None:
        if len(self.frequencies_hz) != len(self.s11):
            raise ValueError("frequencies_hz and s11 must have the same length")
        if len(self.frequencies_hz) < 2:
            raise ValueError("a trace needs at least two frequency points")
        pairs = sorted(zip(self.frequencies_hz, self.s11), key=lambda item: item[0])
        self.frequencies_hz = [f for f, _ in pairs]
        self.s11 = [s for _, s in pairs]
        for f in self.frequencies_hz:
            if f <= 0:
                raise ValueError("frequencies must be > 0")

    # ------------------------------------------------------------ factories
    @classmethod
    def from_magnitude_db(
        cls, frequencies_hz: Sequence[float], magnitude_db: Sequence[float]
    ) -> "S11Trace":
        """Build a phase-less trace from magnitudes (see :meth:`has_phase`)."""
        mags = [10.0 ** (db / 20.0) for db in magnitude_db]
        return cls(list(frequencies_hz), [complex(m, 0.0) for m in mags], has_phase=False)

    @classmethod
    def from_magnitude_phase_db(
        cls,
        frequencies_hz: Sequence[float],
        magnitude_db: Sequence[float],
        phase_deg: Sequence[float],
        reference_impedance_ohm: float = 50.0,
    ) -> "S11Trace":
        """Build a full trace from magnitude (dB) and phase (degrees) pairs."""
        if not (len(frequencies_hz) == len(magnitude_db) == len(phase_deg)):
            raise ValueError("frequencies, magnitudes and phases must have equal length")
        values = [
            cmath.rect(10.0 ** (db / 20.0), math.radians(phase))
            for db, phase in zip(magnitude_db, phase_deg)
        ]
        return cls(
            list(frequencies_hz),
            values,
            has_phase=True,
            reference_impedance_ohm=reference_impedance_ohm,
        )

    @classmethod
    def from_db_frequency_grid(
        cls, start_hz: float, stop_hz: float, magnitude_db: Sequence[float]
    ) -> "S11Trace":
        points = len(magnitude_db)
        if points < 2:
            raise ValueError("need at least two magnitude samples")
        step = (stop_hz - start_hz) / (points - 1)
        freqs = [start_hz + i * step for i in range(points)]
        return cls.from_magnitude_db(freqs, magnitude_db)

    # -------------------------------------------------------------- metrics
    def magnitude(self) -> List[float]:
        return [abs(s) for s in self.s11]

    def db(self) -> List[float]:
        return [20.0 * math.log10(max(abs(s), 1e-12)) for s in self.s11]

    def vswr(self) -> List[float]:
        return [vswr_from_gamma(abs(s)) for s in self.s11]

    def return_loss_db(self) -> List[float]:
        return [return_loss_db(abs(s)) for s in self.s11]

    def worst_match_index(self) -> int:
        """Index of the resonance (minimum |S11|, i.e. best match)."""
        return min(range(len(self.s11)), key=lambda i: abs(self.s11[i]))

    def resonance_hz(self) -> float:
        return self.frequencies_hz[self.worst_match_index()]

    def worst_match_db(self) -> float:
        return self.db()[self.worst_match_index()]

    def impedance_ohm(self, z0_ohm: Optional[float] = None) -> List[complex]:
        """Input impedance from S11, referred to the trace's reference impedance.

        Raises when the trace has no phase information: with a forced-zero phase
        the reactance would be silently wrong (review item Y-05).  Use
        :meth:`from_magnitude_phase_db` for data that carries phase.
        """
        if not self.has_phase:
            raise ValueError(
                "this S11Trace has no phase information (built from magnitudes only), "
                "so the input impedance is undefined; use from_magnitude_phase_db() or "
                "read a Touchstone file with RI/MA/DB data"
            )
        z0 = self.reference_impedance_ohm if z0_ohm is None else z0_ohm
        out: List[complex] = []
        for s in self.s11:
            if abs(s - 1.0) < 1e-15:
                out.append(complex(float("inf"), 0.0))
            else:
                out.append(z0 * (1.0 + s) / (1.0 - s))
        return out

    # ----------------------------------------------------------- bandwidth
    def refine_resonance(self) -> tuple[float, float, float]:
        """Sub-grid resonance estimate by parabolic interpolation of |S11| (dB).

        The raw minimum of |S11| can only be located to one sweep step (0.4 % at
        the default 101-point sweep), which is far too coarse to target 0.1 %.
        Fitting a parabola through the minimum and its two neighbours locates the
        vertex far below the grid step.

        Returns ``(refined_hz, grid_step_hz, curvature_db_per_hz2)``.  The curvature is
        the second derivative of the dB curve at the dip: it says how sharp the dip is
        and therefore how far the vertex can move for a given uncertainty in |S11|.
        (A parabola through three points has no residual, so no residual is reported.)
        NOTE: this is a *grid* refinement, not a physical uncertainty.
        """
        index = self.worst_match_index()
        frequencies = self.frequencies_hz
        if index == 0 or index == len(frequencies) - 1:
            return frequencies[index], self._grid_step_hz(), float("nan")

        f1, f2, f3 = frequencies[index - 1], frequencies[index], frequencies[index + 1]
        db = self.db()
        y1, y2, y3 = db[index - 1], db[index], db[index + 1]

        curvature = y1 - 2.0 * y2 + y3
        if curvature == 0.0:
            return f2, self._grid_step_hz(), float("nan")
        # vertex offset in units of the half-step, for equally spaced points
        delta = 0.5 * (y1 - y3) / curvature
        half_step = 0.5 * (f3 - f1)
        refined = f2 + delta * half_step
        curvature_db_per_hz2 = curvature / (half_step * half_step) if half_step else float("nan")
        return refined, self._grid_step_hz(), curvature_db_per_hz2

    def _grid_step_hz(self) -> float:
        if len(self.frequencies_hz) < 2:
            return 0.0
        return self.frequencies_hz[1] - self.frequencies_hz[0]

    def resonance_refined_hz(self) -> float:
        """Convenience wrapper returning only the refined frequency."""
        return self.refine_resonance()[0]

    def bandwidth_below(
        self, threshold_db: float = -10.0
    ) -> List[Tuple[float, float, float]]:
        """Contiguous bands where ``|S11|`` is below ``threshold_db``.

        Returns a list of ``(f_start, f_stop, bandwidth_hz)`` with edges linearly
        interpolated between samples.  Each entry is therefore approximate at the
        sweep resolution -- refine the sweep around the band edges before
        quoting a bandwidth number.
        """
        db = self.db()
        bands: List[Tuple[float, float, float]] = []
        start: Optional[float] = None

        for i in range(len(db)):
            below = db[i] <= threshold_db
            if below and start is None:
                if i == 0:
                    start = self.frequencies_hz[0]
                else:
                    start = _interp(
                        self.frequencies_hz[i - 1], db[i - 1],
                        self.frequencies_hz[i], db[i], threshold_db,
                    )
            elif not below and start is not None:
                edge = _interp(
                    self.frequencies_hz[i - 1], db[i - 1],
                    self.frequencies_hz[i], db[i], threshold_db,
                )
                bands.append((start, edge, edge - start))
                start = None

        if start is not None:
            end = self.frequencies_hz[-1]
            bands.append((start, end, end - start))
        return bands

    def fractional_bandwidth(self, threshold_db: float = -10.0) -> Optional[float]:
        """Fractional bandwidth of the band containing the resonance, if any."""
        bands = self.bandwidth_below(threshold_db)
        if not bands:
            return None
        resonance = self.resonance_hz()
        containing = [b for b in bands if b[0] <= resonance <= b[1]]
        band = containing[0] if containing else max(bands, key=lambda b: b[2])
        return band[2] / resonance

    # ------------------------------------------------------------------ IO
    def to_csv(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = ["freq_hz,s11_re,s11_im,s11_db"]
        for f, s, db in zip(self.frequencies_hz, self.s11, self.db()):
            lines.append(f"{f:.6e},{s.real:.9e},{s.imag:.9e},{db:.6f}")
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target.resolve()

    @classmethod
    def from_csv(cls, path: str | Path) -> "S11Trace":
        text = Path(path).read_text(encoding="utf-8")
        freqs: List[float] = []
        values: List[complex] = []
        for index, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            if index == 0 and line.lower().startswith("freq"):
                continue
            parts = [p for p in line.replace(";", ",").split(",") if p.strip()]
            if len(parts) < 3:
                raise ValueError(f"unexpected CSV row: {line!r}")
            freqs.append(float(parts[0]))
            values.append(complex(float(parts[1]), float(parts[2])))
        return cls(freqs, values)

    def write_touchstone(self, path: str | Path, z0_ohm: float = 50.0) -> Path:
        """Write a Touchstone v1 ``.s1p`` file with RI data in Hz."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "! Generated by OpenAntenna Studio (Phase 1)",
            "! Data are SIMULATED/model data, not a standards-compliant calibration.",
            f"# Hz S RI R {z0_ohm:g}",
        ]
        for f, s in zip(self.frequencies_hz, self.s11):
            lines.append(f"{f:.10g} {s.real:+.9e} {s.imag:+.9e}")
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target.resolve()


_FREQ_UNITS = {
    "hz": 1.0, "khz": 1.0e3, "mhz": 1.0e6, "ghz": 1.0e9,
}


def read_touchstone(path: str | Path) -> S11Trace:
    """Read a one-port Touchstone file (RI, MA or DB; Hz/kHz/MHz/GHz).

    A pragmatic parser for comparison work, not a full implementation of every
    corner of the Touchstone specification (no multi-port, no interleaving of
    multiple line lengths beyond the standard 4 numbers per line).
    """
    text = Path(path).read_text(encoding="utf-8")
    freq_scale = 1.0
    fmt = "ri"
    reference_impedance_ohm = 50.0
    freqs: List[float] = []
    values: List[complex] = []
    seen_option = False

    for raw in text.splitlines():
        line = raw.split("!", 1)[0].strip()
        if not line:
            continue
        if line.startswith("#"):
            tokens = line[1:].upper().split()
            for index, token in enumerate(tokens):
                if token.lower() in _FREQ_UNITS:
                    freq_scale = _FREQ_UNITS[token.lower()]
                elif token in ("RI", "MA", "DB"):
                    fmt = token.lower()
                elif token == "R" and index + 1 < len(tokens):
                    # Touchstone option line: "... R <value>"; keep it so that
                    # impedance_ohm() uses the right reference (review item Y-15).
                    try:
                        reference_impedance_ohm = float(tokens[index + 1])
                    except ValueError:
                        reference_impedance_ohm = 50.0
            seen_option = True
            continue
        if not seen_option:
            # tolerant fallback: assume Hz / RI
            seen_option = True
        parts = line.replace(",", " ").split()
        if len(parts) < 3:
            continue
        freq = float(parts[0]) * freq_scale
        a = float(parts[1])
        b = float(parts[2])
        if fmt == "ri":
            value = complex(a, b)
        elif fmt == "ma":
            value = cmath.rect(a, math.radians(b))
        else:  # db
            value = cmath.rect(10.0 ** (a / 20.0), math.radians(b))
        freqs.append(freq)
        values.append(value)

    if not freqs:
        raise ValueError(f"no data rows found in {path}")
    return S11Trace(
        freqs, values, has_phase=True, reference_impedance_ohm=reference_impedance_ohm
    )
