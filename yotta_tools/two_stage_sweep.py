"""Plan the second (fine) sweep from a coarse one — and refuse edge minima (Yotta, A6).

Two problems this solves, both seen in this project:

1. **Cost.**  A 201-point sweep over 700 MHz spends most of its points far from the
   resonance.  Locate the minimum coarsely, then sweep finely only where it is.
2. **A silent trap.**  A minimum sitting on the first or last sample is not a resonance:
   it is the sweep edge (a run whose S11 keeps falling past the band looks "resonant" at
   f_max).  One of my own batch runs read 2.817 GHz = f_max exactly like that.  This tool
   marks such a result **invalid** instead of planning a fine sweep around it.

Usage::

    python yotta_tools/two_stage_sweep.py runs/coarse/s11.csv
    python yotta_tools/two_stage_sweep.py --run-dir runs/coarse --span-fraction 0.10
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

EDGE_TOLERANCE_FRACTION = 0.01  # a minimum closer than 1 % of the span to an edge is suspicious
#: a minimum within this many coarse samples of an edge is treated as a boundary artifact:
#: the fine sweep would have no room around it, so the resonance is probably outside the band
EDGE_STEPS = 2


def load_s11(path: Path) -> list[tuple[float, float]]:
    """Read (frequency, |S11| in dB) from a run's s11.csv."""
    rows: list[tuple[float, float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            freq = float(row["freq_hz"])
            re = float(row.get("s11_re", 0.0) or 0.0)
            im = float(row.get("s11_im", 0.0) or 0.0)
            magnitude = (re * re + im * im) ** 0.5
            import math

            rows.append((freq, 20.0 * math.log10(max(magnitude, 1e-12))))
    rows.sort()
    return rows


def plan(samples: list[tuple[float, float]], span_fraction: float = 0.10) -> dict:
    """Return the fine-sweep plan, or a refusal when the coarse data cannot support one."""
    if len(samples) < 5:
        return {"status": "insufficient-data", "reason": f"only {len(samples)} samples"}

    freqs = [f for f, _ in samples]
    dbs = [d for _, d in samples]
    index = min(range(len(dbs)), key=lambda i: dbs[i])
    span = freqs[-1] - freqs[0]
    step = span / (len(freqs) - 1)
    edge_zone = EDGE_TOLERANCE_FRACTION * span

    at_edge = (
        index in (0, len(dbs) - 1)
        or index <= EDGE_STEPS - 1
        or index >= len(dbs) - EDGE_STEPS
        or (freqs[index] - freqs[0] < edge_zone)
        or (freqs[-1] - freqs[index] < edge_zone)
    )
    result = {
        "samples": len(samples),
        "coarse_span_hz": span,
        "coarse_step_hz": step,
        "minimum_hz": freqs[index],
        "minimum_db": dbs[index],
        "minimum_at_edge": at_edge,
    }
    if at_edge:
        result["status"] = "invalid-edge-minimum"
        result["reason"] = (
            "the minimum sits at (or within %d samples of) the sweep edge - that is a boundary "
            "artifact, not a resonance. Widen the band and re-run the coarse sweep; do not "
            "quote this frequency as a resonance." % EDGE_STEPS
        )
        return result

    half = span_fraction * span
    start = max(freqs[0], freqs[index] - half)
    stop = min(freqs[-1], freqs[index] + half)
    points = max(11, int(round((stop - start) / step)) + 1)
    result.update(
        {
            "status": "ok",
            "recommended": {
                "start_hz": start,
                "stop_hz": stop,
                "points": points,
                "step_hz": (stop - start) / (points - 1),
                "note": "same step as the coarse sweep, window centred on the minimum",
            },
            "cost_ratio_vs_full": round((stop - start) / span, 4),
        }
    )
    return result


def run_dir_to_csv(run_dir: Path) -> Path:
    csv_path = run_dir / "s11.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"{csv_path} not found")
    return csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan a fine sweep from a coarse one.")
    parser.add_argument("csv", nargs="?", help="path to a coarse s11.csv")
    parser.add_argument("--run-dir", help="run directory containing s11.csv")
    parser.add_argument("--span-fraction", type=float, default=0.10,
                        help="half-width of the fine window as a fraction of the coarse span")
    parser.add_argument("--out", default="yotta_tools/two_stage_sweep.json")
    args = parser.parse_args(argv)

    if args.csv:
        csv_path = Path(args.csv)
    elif args.run_dir:
        csv_path = run_dir_to_csv(Path(args.run_dir))
    else:
        parser.error("give a csv path or --run-dir")
        return 2

    samples = load_s11(csv_path)
    result = plan(samples, args.span_fraction)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"coarse: {result['samples']} samples over {result['coarse_span_hz']/1e9:.3f} GHz")
    print(f"minimum: {result.get('minimum_hz', float('nan'))/1e9:.4f} GHz at {result.get('minimum_db', float('nan')):.2f} dB")
    if result["status"] == "ok":
        rec = result["recommended"]
        print(f"fine sweep: {rec['start_hz']/1e9:.4f} .. {rec['stop_hz']/1e9:.4f} GHz, {rec['points']} points "
              f"(step {rec['step_hz']/1e6:.1f} MHz)")
        print(f"cost vs the full band: {result['cost_ratio_vs_full']*100:.1f} %")
    else:
        print(f"REFUSED ({result['status']}): {result['reason']}")
    print(f"written: {args.out}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
