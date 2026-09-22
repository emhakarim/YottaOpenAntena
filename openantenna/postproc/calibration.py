"""Calibration of the generated model against independent references (gate condition 2).

The gate does not ask for 0.1 % absolute accuracy - that is unreachable, because the material
permittivity alone is uncertain by about 1 %.  It asks for one of two things:

* ``|df| <= 1 %`` against an independent reference **on at least two topologies**, or
* a correction factor with a **written validity range**.

This module turns measured runs into that record.  It refuses to produce a number from a run
that did not converge, and it refuses to claim a correction factor from a single topology,
because the project already found a bias that *looked* constant per recipe and was not
(spread of 2.7 points across topologies - a claim that had to be withdrawn).

Stdlib only.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

__all__ = ["RunSample", "CalibrationReport", "sample_from_run", "calibrate"]

#: the gate's tolerance: |df|/f must be at or under this on at least two topologies
GATE_TOLERANCE_PERCENT = 1.0


@dataclass
class RunSample:
    """One converged run compared against its independent reference."""

    topology: str
    source: str
    reference_hz: float
    measured_hz: float
    converged: bool = True
    notes: str = ""

    @property
    def bias_percent(self) -> float:
        if self.reference_hz <= 0:
            raise ValueError("reference_hz must be > 0")
        return 100.0 * (self.measured_hz - self.reference_hz) / self.reference_hz


def sample_from_run(
    topology: str, reference_hz: float, run_dir: str | Path, source: str = ""
) -> RunSample:
    """Build a sample from a run directory: resonance from the analysis, convergence from it.

    ``resonance_analysis.json`` is preferred (it carries the sub-grid refinement); otherwise the
    ``s11.csv`` minimum is used and that is stated in the notes.
    """
    run_dir = Path(run_dir)
    summary = run_dir / "run_summary.json"
    converged = None
    if summary.exists():
        try:
            converged = json.loads(summary.read_text(encoding="utf-8")).get("converged")
        except (OSError, ValueError):
            converged = None

    analysis = run_dir / "resonance_analysis.json"
    note = ""
    if analysis.exists():
        payload = json.loads(analysis.read_text(encoding="utf-8"))
        resonance = payload.get("refined_hz") or payload.get("resonance_hz")
        note = "resonance from resonance_analysis.json (sub-grid refinement)"
    else:
        from .sparams import S11Trace

        trace = S11Trace.from_csv(run_dir / "s11.csv")
        index = trace.worst_match_index()
        resonance = float(trace.frequencies_hz[index])
        note = "resonance from the raw S11 minimum; no sub-grid refinement available"
    if resonance is None:
        raise ValueError(f"{run_dir}: no resonance recorded")

    return RunSample(
        topology=topology,
        source=source or str(run_dir),
        reference_hz=float(reference_hz),
        measured_hz=float(resonance),
        converged=bool(converged) if converged is not None else False,
        notes=note,
    )


@dataclass
class CalibrationReport:
    """What can and cannot be claimed from a set of samples."""

    samples: List[RunSample]
    per_topology: Dict[str, Dict[str, float]] = field(default_factory=dict)
    conclusion: str = ""
    correction_factor: Optional[float] = None
    validity: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "samples": [
                {
                    "topology": sample.topology,
                    "source": sample.source,
                    "reference_hz": sample.reference_hz,
                    "measured_hz": sample.measured_hz,
                    "bias_percent": sample.bias_percent,
                    "converged": sample.converged,
                    "notes": sample.notes,
                }
                for sample in self.samples
            ],
            "per_topology": self.per_topology,
            "overall_mean_bias_percent": self.overall_mean_bias,
            "spread_percent": self.spread,
            "topologies": sorted({sample.topology for sample in self.samples}),
            "correction_factor": self.correction_factor,
            "validity": self.validity,
            "conclusion": self.conclusion,
            "gate_tolerance_percent": GATE_TOLERANCE_PERCENT,
        }

    @property
    def overall_mean_bias(self) -> Optional[float]:
        biases = [sample.bias_percent for sample in self.samples if sample.converged]
        return sum(biases) / len(biases) if biases else None

    @property
    def spread(self) -> Optional[float]:
        means = [entry["mean_bias_percent"] for entry in self.per_topology.values()]
        return (max(means) - min(means)) if len(means) > 1 else None

    def summary(self) -> str:
        lines = ["Calibration against independent references", ""]
        if not self.samples:
            return "\n".join(lines + ["  no samples"])
        for topology, entry in sorted(self.per_topology.items()):
            lines.append(
                f"  {topology:22} mean bias {entry['mean_bias_percent']:+.3f} % "
                f"(worst |bias| {entry['worst_abs_bias_percent']:.3f} %, n={int(entry['n'])})"
            )
        lines.append("")
        lines.append(f"  all samples (n={len(self.samples)}): mean bias {self.overall_mean_bias:+.3f} %")
        if self.spread is not None:
            lines.append(f"  spread across topologies: {self.spread:.3f} points")
        lines.append("")
        lines.append("  " + self.conclusion)
        if self.correction_factor is not None:
            lines.append(f"  correction factor: {self.correction_factor:.6f}  ({self.validity})")
        return "\n".join(lines)


def calibrate(samples: Sequence[RunSample]) -> CalibrationReport:
    """Score the samples against the gate, and say honestly what may be claimed.

    Rules enforced here:

    * an unconverged sample is dropped, and the report says how many were dropped;
    * a correction factor requires **at least two topologies** (a single-topology "constant
      bias" is exactly the claim the project had to withdraw once);
    * a tolerance pass requires every kept topology to be inside
      :data:`GATE_TOLERANCE_PERCENT`.
    """
    if not samples:
        raise ValueError("no samples given")
    keep: List[RunSample] = []
    dropped: List[RunSample] = []
    for sample in samples:
        (keep if sample.converged else dropped).append(sample)
    if not keep:
        raise ValueError("every sample is unconverged; there is nothing to calibrate")

    grouped: Dict[str, List[float]] = {}
    for sample in keep:
        grouped.setdefault(sample.topology, []).append(sample.bias_percent)
    per_topology = {
        topology: {
            "mean_bias_percent": sum(biases) / len(biases),
            "worst_abs_bias_percent": max(abs(bias) for bias in biases),
            "n": float(len(biases)),
        }
        for topology, biases in grouped.items()
    }

    report = CalibrationReport(samples=keep, per_topology=per_topology)
    means = [entry["mean_bias_percent"] for entry in per_topology.values()]
    worst = max(entry["worst_abs_bias_percent"] for entry in per_topology.values())

    inside = worst <= GATE_TOLERANCE_PERCENT
    if inside and len(per_topology) >= 2:
        report.conclusion = (
            f"gate condition 2 SATISFIED on {len(per_topology)} topologies: worst |bias| "
            f"{worst:.3f} % <= {GATE_TOLERANCE_PERCENT} %. State the topologies and frequencies; "
            "this does not licence other geometries."
        )
    elif inside:
        report.conclusion = (
            f"only one topology has data ({next(iter(per_topology))}); |bias| {worst:.3f} % is "
            "inside tolerance, but gate condition 2 needs at least two topologies before it counts."
        )
    else:
        spread = (max(means) - min(means)) if len(means) > 1 else None
        report.correction_factor = 1.0 - (sum(means) / len(means)) / 100.0
        report.validity = (
            "applies only to the topologies below, at the frequencies measured; a correction "
            "factor derived from one recipe does not transfer"
        )
        report.conclusion = (
            f"gate condition 2 NOT satisfied: worst |bias| {worst:.3f} % > "
            f"{GATE_TOLERANCE_PERCENT} %"
            + (f", spread across topologies {spread:.3f} points" if spread is not None else "")
            + ". A correction factor is offered with a written validity range instead."
        )
    if dropped:
        report.validity = (
            (report.validity + "; " if report.validity else "")
            + f"{len(dropped)} unconverged sample(s) excluded: {sorted({s.topology for s in dropped})}"
        )
    return report
