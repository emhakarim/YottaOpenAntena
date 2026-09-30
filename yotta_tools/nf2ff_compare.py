"""NF2FF pattern cross-check helper (Yotta item R-5).

Reads a run directory produced by the generator with ``nf2ff=True``
(``nf2ff_pattern.csv`` + ``nf2ff_summary.csv``) and independently recomputes the
directivity from the exported pattern using
``openantenna.postproc.patterns.directivity_from_pattern`` - the cross-check
that ties the solver far field to the analytic helper library.

Usage::

    python yotta_tools/nf2ff_compare.py runs/batch_k2c_loss_ptfe [runs/...]
    python yotta_tools/nf2ff_compare.py --json out.json runs/...

Findings and the first executed comparison: ``docs/nf2ff-comparison.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from openantenna.postproc import patterns  # noqa: E402


def load_pattern(run_dir: Path):
    """Return ({(theta_deg, phi_deg): amplitude}, sorted thetas, sorted phis)."""
    rows = list(csv.reader((run_dir / "nf2ff_pattern.csv").read_text(encoding="utf-8").splitlines()))
    if not rows or rows[0][:1] != ["theta_deg"]:
        raise ValueError(f"{run_dir}: unexpected nf2ff_pattern.csv header")
    data = {}
    for theta, phi, amplitude in rows[1:]:
        data[(float(theta), float(phi))] = float(amplitude)
    thetas = sorted({key[0] for key in data})
    phis = sorted({key[1] for key in data})
    if len(thetas) < 2 or len(phis) < 2:
        raise ValueError(f"{run_dir}: pattern grid too small")
    return data, thetas, phis


def load_summary(run_dir: Path):
    path = run_dir / "nf2ff_summary.csv"
    if not path.is_file():
        return []
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    return [
        {
            "freq_hz": float(r[0]),
            "directivity_lin": float(r[1]),
            "directivity_dbi": float(r[2]),
            "eta_rad": r[5],
        }
        for r in rows[1:]
    ]


def half_angle_deg(data, thetas, cut_phi, peak_t, threshold=1 / math.sqrt(2)):
    """First theta >= peak where the cut drops below -3 dB, linearly interpolated."""
    vals = [(t, data[(t, cut_phi)]) for t in thetas]
    peak_v = max(v for _, v in vals)
    prev_t = prev_v = None
    for t, v in vals:
        if t < peak_t:
            continue
        if v / peak_v < threshold and prev_v is not None:
            span = v - prev_v
            if span != 0:
                frac = (threshold * peak_v - prev_v) / span
                return prev_t + frac * (t - prev_t)
            return float(t)
        prev_t, prev_v = t, v
    return None


def analyse(run_dir: Path) -> dict:
    data, thetas, phis = load_pattern(run_dir)
    (t_peak, p_peak), e_peak = max(data.items(), key=lambda kv: kv[1])

    def pattern_fn(theta_rad, phi_rad):
        key = (round(math.degrees(theta_rad), 3), round(math.degrees(phi_rad), 3))
        return data.get(key, 0.0)

    d_re = patterns.directivity_from_pattern(
        [math.radians(t) for t in thetas],
        [math.radians(p) for p in phis],
        pattern_fn,
    )
    cuts = {}
    for cut_phi in (0.0, 90.0):
        if any(abs(p - cut_phi) < 1e-9 for p in phis):
            cuts[f"phi_{cut_phi:g}"] = {
                "half_angle_deg": half_angle_deg(data, thetas, cut_phi, t_peak)
            }
    return {
        "run": run_dir.name,
        "grid": [len(thetas), len(phis)],
        "peak": {"theta_deg": t_peak, "phi_deg": p_peak, "e": e_peak},
        "directivity_recomputed_lin": d_re,
        "directivity_recomputed_dbi": 10 * math.log10(d_re),
        "cuts": cuts,
        "summary": load_summary(run_dir),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="NF2FF pattern vs patterns.py cross-check.")
    parser.add_argument("run_dirs", nargs="+", help="run directories containing nf2ff_pattern.csv")
    parser.add_argument("--json", help="write the results as JSON to this path")
    args = parser.parse_args(argv)

    results = []
    for text in args.run_dirs:
        run = Path(text)
        if not (run / "nf2ff_pattern.csv").is_file():
            print(f"skip (no nf2ff_pattern.csv): {run}")
            continue
        record = analyse(run)
        results.append(record)
        print(f"== {record['run']} ==")
        print(
            "  peak theta=%g phi=%g"
            % (record["peak"]["theta_deg"], record["peak"]["phi_deg"])
        )
        print(
            "  directivity recomputed: %.4f lin (%.3f dBi)"
            % (record["directivity_recomputed_lin"], record["directivity_recomputed_dbi"])
        )
        for name, cut in record["cuts"].items():
            if cut["half_angle_deg"] is not None:
                print(f"  cut {name}: -3 dB half-angle ~{cut['half_angle_deg']:.1f} deg")
        for row in record["summary"]:
            print(
                "  summary %.4e Hz -> D=%.3f lin (%.2f dBi), eta_rad=%s"
                % (row["freq_hz"], row["directivity_lin"], row["directivity_dbi"], row["eta_rad"])
            )
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print("wrote", args.json)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
