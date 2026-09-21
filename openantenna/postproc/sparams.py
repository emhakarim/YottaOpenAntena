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
    """VSWR from the magnitude of a reflection coefficient (0 <= |gamma| < 1)."""
    gamma = abs(float(gamma))
    if gamma >= 1.0:
        return float("inf")
    if gamma < 0:
        raise ValueError("gamma must be a magnitude >= 0")
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
    """A frequency trace of S11 (complex reflection coefficient)."""

    frequencies_hz: List[float]
    s11: List[complex]

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
        mags = [10.0 ** (db / 20.0) for db in magnitude_db]
        return cls(list(frequencies_hz), [complex(m, 0.0) for m in mags])

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

    def impedance_ohm(self, z0_ohm: float = 50.0) -> List[complex]:
        """Input impedance from S11 (ignores any transmission-line reference plane)."""
        out: List[complex] = []
        for s in self.s11:
            if abs(s - 1.0) < 1e-15:
                out.append(complex(float("inf"), 0.0))
            else:
                out.append(z0_ohm * (1.0 + s) / (1.0 - s))
        return out

    # ----------------------------------------------------------- bandwidth
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
    freqs: List[float] = []
    values: List[complex] = []
    seen_option = False

    for raw in text.splitlines():
        line = raw.split("!", 1)[0].strip()
        if not line:
            continue
        if line.startswith("#"):
            tokens = line[1:].upper().split()
            for token in tokens:
                if token.lower() in _FREQ_UNITS:
                    freq_scale = _FREQ_UNITS[token.lower()]
                elif token in ("RI", "MA", "DB"):
                    fmt = token.lower()
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
    return S11Trace(freqs, values)
