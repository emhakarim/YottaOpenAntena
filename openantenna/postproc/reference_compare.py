"""Compare our model against an external reference (e.g. CST Studio) on identical terms.

The point of this module is that **both sides are reduced with the same metric**: the minimum of
|S11| plus the sub-grid parabolic refinement that :class:`~openantenna.postproc.sparams.S11Trace`
already uses for our own runs.  Comparing "their reported resonance" against "our refined one"
would mix two definitions and manufacture bias out of bookkeeping.

Layout for a design folder::

    runs/cst_reference/<design>/
        cst_s11.s1p      or  cst_s11.csv     <- the external reference
        run/                                 <- our model on the SAME geometry
            s11.csv
            run_summary.json                 <- supplies the converged flag

``.s1p`` is read with :func:`~openantenna.postproc.sparams.read_touchstone`; a CSV must have
``freq_hz, s11_re, s11_im`` like our own writer.

Stdlib only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .calibration import RunSample
from .sparams import S11Trace, read_touchstone

__all__ = ["load_reference", "resonance_of", "compare_traces", "compare_design", "compare_folder"]

REFERENCE_NAMES = ("cst_s11.s1p", "cst_s11.csv")


def load_reference(path: str | Path) -> S11Trace:
    """Read an external S11 file: Touchstone ``.s1p`` or our own CSV schema."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path}: reference file not found")
    if path.suffix.lower() in (".s1p", ".s2p", ".s3p"):
        return read_touchstone(path)
    return S11Trace.from_csv(path)


def resonance_of(trace: S11Trace) -> Tuple[float, float]:
    """Refined resonance and the |S11| there, in the project's metric for both sides."""
    frequency = trace.resonance_refined_hz()
    index = trace.worst_match_index()
    return float(frequency), float(trace.db()[index])


def compare_traces(
    reference: S11Trace,
    ours: S11Trace,
    topology: str,
    converged: Optional[bool] = True,
    source: str = "",
) -> RunSample:
    """A :class:`RunSample` with the *reference* resonance as reference and ours as measured."""
    reference_hz, reference_db = resonance_of(reference)
    our_hz, our_db = resonance_of(ours)
    sample = RunSample(
        topology=topology,
        source=source,
        reference_hz=reference_hz,
        measured_hz=our_hz,
        converged=bool(converged),
        notes=(
            f"reference |S11| {reference_db:.2f} dB; ours {our_db:.2f} dB; "
            "both reduced by the same metric (minimum + parabolic refinement)"
        ),
    )
    return sample


def _converged(run_dir: Path) -> Optional[bool]:
    import json

    summary = run_dir / "run_summary.json"
    if not summary.exists():
        return None
    try:
        value = json.loads(summary.read_text(encoding="utf-8")).get("converged")
    except (OSError, ValueError):
        return None
    return bool(value) if value is not None else None


def compare_design(design_dir: str | Path) -> RunSample:
    """Compare one design folder against our run in its ``run/`` subdirectory."""
    design_dir = Path(design_dir)
    reference_path = next(
        (design_dir / name for name in REFERENCE_NAMES if (design_dir / name).exists()), None
    )
    if reference_path is None:
        raise FileNotFoundError(
            f"{design_dir}: expected one of {REFERENCE_NAMES} (the external reference)"
        )
    run_dir = design_dir / "run"
    our_csv = run_dir / "s11.csv"
    if not our_csv.exists():
        raise FileNotFoundError(
            f"{run_dir}: our model's s11.csv is missing. A comparison needs both sides; "
            "without it there is nothing to compare against."
        )
    return compare_traces(
        load_reference(reference_path),
        S11Trace.from_csv(our_csv),
        topology=design_dir.name,
        converged=_converged(run_dir),
        source=str(reference_path),
    )


def compare_folder(root: str | Path) -> List[RunSample]:
    """Compare every design folder under ``root`` (sorted, so reports are reproducible)."""
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"{root}: no such folder")
    designs = sorted(path for path in root.iterdir() if path.is_dir())
    if not designs:
        raise ValueError(f"{root}: no design folders found")
    samples: List[RunSample] = []
    for design in designs:
        try:
            samples.append(compare_design(design))
        except FileNotFoundError as exc:
            samples.append(
                RunSample(
                    topology=design.name,
                    source=str(design),
                    reference_hz=float("nan"),
                    measured_hz=float("nan"),
                    converged=False,
                    notes=f"incomplete: {exc}",
                )
            )
    return samples
