"""Turn two completed runs into a verdict, by the rules, without a human eyeballing it.

`docs/convergence-policy.md` says a result is accepted only when it is **stable between two
settings** (``|delta f| / f <= 0.2 %``), and rejected when the shift is larger, when there is no
minimum inside the band, or when the minimum sits on a band edge. Those rules were being applied
by hand, in prose - which is exactly the kind of step that quietly changes meaning between two
reports. This tool applies them mechanically and prints *why*.

Inputs are two run directories produced by the harness (``parallel_batch.py`` or a single run):

    runs/batch_e2b_prab_on/     s11.csv              freq_hz,s11_re,s11_im
                                run_summary.json     f_min_hz, f_max_hz, n_freq
                                run.stdout.log       the engine's own convergence statement

Usage:
    python -m yotta_tools.two_setting_verdict --a runs/run_e3 --b runs/run_e4
    python -m yotta_tools.two_setting_verdict --a A --b B --json verdict.json --edge-steps 2

Convergence is read from the engine log, never guessed:

* "End criteria reached after N iterations"  -> converged (N timesteps)
* "Max. number of timesteps was reached"     -> NOT converged (hit the cap)
* neither line found                        -> unverifiable, which is not the same as converged

Exit status is 0 even when the verdict is a rejection: a rejected experiment is a valid outcome,
and a tool that fails on it would tempt callers to ignore its output.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

DEFAULT_TOLERANCE = 0.002  # 0.2 %, docs/convergence-policy.md
DEFAULT_EDGE_STEPS = 2     # matches yotta_tools/two_stage_sweep.py EDGE_STEPS
BANDS = ((0.002, "di bawah ambang terima (<0,2 %)"),
         (0.01, "bergeser (0,2-1 %)"),
         (math.inf, "bergeser besar (>=1 %)"))

CONVERGED_RE = re.compile(r"End criteria reached after\s+([\d,]+)")
CAP_HIT_RE = re.compile(r"Max\. number of timesteps was reached")
TIMESTEP_RE = re.compile(r"Timestep:\s*([\d,]+)")


class RunData:
    """One run directory, reduced to what a verdict needs."""

    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)
        if not self.dir.is_dir():
            raise FileNotFoundError(f"run directory not found: {self.dir}")
        self.freq_hz, self.s11_db, self.vswr = _read_s11(self.dir / "s11.csv")
        summary = _read_json(self.dir / "run_summary.json")
        self.f_min_hz = summary.get("f_min_hz", self.freq_hz[0])
        self.f_max_hz = summary.get("f_max_hz", self.freq_hz[-1])
        self.converged, self.timesteps, self.convergence_note = _read_convergence(self.dir / "run.stdout.log")
        self.min_index = min(range(len(self.s11_db)), key=self.s11_db.__getitem__)
        self.resonance_hz = self.freq_hz[self.min_index]

    @property
    def edge_limit(self) -> int:
        return len(self.freq_hz) - 1

    def at_edge(self, edge_steps: int) -> bool:
        """True when the minimum sits within ``edge_steps`` of either end of the sweep."""
        return self.min_index < edge_steps or self.min_index > self.edge_limit - edge_steps

    def row(self) -> dict[str, object]:
        return {
            "run": self.dir.name,
            "resonance_hz": self.resonance_hz,
            "resonance_ghz": round(self.resonance_hz / 1e9, 4),
            "s11_db": round(self.s11_db[self.min_index], 2),
            "vswr": round(self.vswr[self.min_index], 3),
            "samples": len(self.freq_hz),
            "index": self.min_index,
            "converged": self.converged,
            "timesteps": self.timesteps,
            "convergence_note": self.convergence_note,
        }


def _read_s11(path: Path) -> tuple[list[float], list[float], list[float]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found; the solver never wrote it - a missing file is an error, not a zero"
        )
    freq: list[float] = []
    s11_db: list[float] = []
    vswr: list[float] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = {"freq_hz", "s11_re", "s11_im"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing column(s) {sorted(missing)}")
        for row in reader:
            try:
                f = float(row["freq_hz"])
                re_part = float(row["s11_re"])
                im_part = float(row["s11_im"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}: unreadable row {row!r}") from exc
            magnitude = math.hypot(re_part, im_part)
            freq.append(f)
            s11_db.append(20.0 * math.log10(magnitude) if magnitude > 0 else -300.0)
            vswr.append((1.0 + magnitude) / (1.0 - magnitude) if magnitude < 1.0 else math.inf)
    if len(freq) < 3:
        raise ValueError(f"{path}: only {len(freq)} sample(s); a resonance needs a sweep")
    if any(b <= a for a, b in zip(freq, freq[1:])):
        raise ValueError(f"{path}: frequency column is not increasing")
    return freq, s11_db, vswr


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_convergence(path: Path) -> tuple[bool | None, int | None, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, None, "no engine log found"
    if match := CAP_HIT_RE.search(text):
        last = None
        for step_match in TIMESTEP_RE.finditer(text):
            last = int(step_match.group(1).replace(",", ""))
        return False, last, "hit the timestep cap before the end criteria (not converged)"
    if match := CONVERGED_RE.search(text):
        return True, int(match.group(1).replace(",", "")), "end criteria reached"
    return None, None, "engine log has no convergence statement; treat as unverified"


def band_label(relative_shift: float) -> str:
    for limit, label in BANDS:
        if relative_shift < limit:
            return label
    return BANDS[-1][1]


def verdict(a: RunData, b: RunData, tolerance: float = DEFAULT_TOLERANCE,
            edge_steps: int = DEFAULT_EDGE_STEPS) -> dict[str, object]:
    """Apply docs/convergence-policy.md to two runs and explain the outcome."""
    reasons: list[str] = []
    relative = abs(a.resonance_hz - b.resonance_hz) / ((a.resonance_hz + b.resonance_hz) / 2.0)

    for run in (a, b):
        if run.at_edge(edge_steps):
            reasons.append(
                f"{run.dir.name}: minimum at sample {run.min_index} of {run.edge_limit} "
                f"({run.resonance_hz / 1e9:.4f} GHz) is within {edge_steps} steps of a sweep edge - "
                "an artefact the two-stage sweep exists to avoid"
            )
    for run in (a, b):
        if run.converged is False:
            reasons.append(f"{run.dir.name}: not converged ({run.convergence_note})")
        elif run.converged is None:
            reasons.append(f"{run.dir.name}: convergence unverifiable ({run.convergence_note})")

    accepted = not reasons and relative <= tolerance
    if accepted:
        reasons.append(
            f"shift {100 * relative:.3f} % <= {100 * tolerance:.2f} % between two settings, "
            "and both runs converged"
        )
    elif not reasons:
        reasons.append(
            f"shift {100 * relative:.3f} % > {100 * tolerance:.2f} % between the two settings"
        )

    return {
        "verdict": "accepted" if accepted else "rejected",
        "relative_shift": relative,
        "relative_shift_pct": round(100 * relative, 4),
        "band": band_label(relative),
        "tolerance_pct": 100 * tolerance,
        "edge_steps": edge_steps,
        "reasons": reasons,
        "runs": [a.row(), b.row()],
        "quotable": bool(accepted),
        "rules": "docs/convergence-policy.md (stability between two settings, no edge minimum)",
    }


def render(result: dict[str, object]) -> str:
    runs = result["runs"]
    lines = [
        f"verdict: {result['verdict'].upper()}  "
        f"(shift {result['relative_shift_pct']:.3f} %, {result['band']})",
        "",
        "| run | resonance [GHz] | |S11| [dB] | VSWR | samples | converged | timesteps |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        lines.append(
            f"| {run['run']} | {run['resonance_ghz']:.4f} | {run['s11_db']:.2f} | "
            f"{run['vswr']:.3f} | {run['samples']} | {run['converged']} | {run['timesteps']} |"
        )
    lines.append("")
    lines.append("reasons:")
    lines.extend(f"  - {reason}" for reason in result["reasons"])
    if not result["quotable"]:
        lines.append("")
        lines.append("NOT QUOTABLE: do not cite these numbers as a result (docs/convergence-policy.md).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--a", required=True, help="first run directory (e.g. the 1e-3 setting)")
    parser.add_argument("--b", required=True, help="second run directory (e.g. the 1e-4 setting)")
    parser.add_argument("--tol", type=float, default=DEFAULT_TOLERANCE,
                        help="relative frequency tolerance (default 0.002 = 0.2 %%)")
    parser.add_argument("--edge-steps", type=int, default=DEFAULT_EDGE_STEPS,
                        help="samples from each sweep edge that count as an edge artefact")
    parser.add_argument("--json", help="also write the verdict as JSON to this path")
    args = parser.parse_args(argv)

    try:
        a = RunData(Path(args.a))
        b = RunData(Path(args.b))
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = verdict(a, b, tolerance=args.tol, edge_steps=args.edge_steps)
    print(render(result))
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwritten: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
