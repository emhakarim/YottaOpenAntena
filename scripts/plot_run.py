"""Plot a run directory: S11 and (when present) the far-field pattern.

Convenience for humans; the toolkit's own code paths never need an image.  matplotlib
is imported lazily so the core stays dependency-free, and the Agg backend is forced so
this also works on a headless machine.

Usage:
    python scripts/plot_run.py runs/<run-dir> [output.png]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openantenna.postproc.farfield import PATTERN_NAME, SUMMARY_NAME, read_pattern, read_summary
from openantenna.postproc.sparams import S11Trace


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: plot_run.py <run-dir> [output.png]", file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[1])
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else run_dir / "plot.png"

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - depends on the environment
        print(f"matplotlib is required for plotting: {exc}", file=sys.stderr)
        return 1

    s11_path = run_dir / "s11.csv"
    if not s11_path.exists():
        print(f"no s11.csv in {run_dir}", file=sys.stderr)
        return 1
    trace = S11Trace.from_csv(s11_path)

    has_pattern = (run_dir / PATTERN_NAME).exists()
    has_summary = (run_dir / SUMMARY_NAME).exists()
    columns = 2 if has_pattern else 1
    figure, axes = plt.subplots(1, columns, figsize=(6 * columns, 4), tight_layout=True)
    if columns == 1:
        axes = [axes]

    axis = axes[0]
    axis.plot([f / 1e9 for f in trace.frequencies_hz], trace.db())
    axis.axhline(-10.0, linestyle="--", linewidth=0.8)
    index = trace.worst_match_index()
    axis.plot(
        [trace.frequencies_hz[index] / 1e9],
        [trace.db()[index]],
        marker="o",
        markersize=4,
    )
    axis.set_xlabel("frequency [GHz]")
    axis.set_ylabel("|S11| [dB]")
    axis.set_title(
        f"{run_dir.name}\nresonance {trace.frequencies_hz[index] / 1e9:.4f} GHz, "
        f"VSWR {trace.vswr()[index]:.3f}"
    )
    axis.grid(True)

    if has_pattern:
        thetas, phis, grid, _ = read_pattern(run_dir / PATTERN_NAME)
        phi_index = min(range(len(phis)), key=lambda j: abs(phis[j] - 0.0))
        values = [grid[i][phi_index] for i in range(len(thetas))]
        peak = max(values) or 1.0
        axis = axes[1]
        axis.plot(thetas, [20.0 * __import__("math").log10(max(v / peak, 1e-12)) for v in values])
        axis.set_xlabel("theta [deg]")
        axis.set_ylabel("normalised [dB]")
        axis.set_ylim(-40, 2)
        title = "E-plane cut (phi = 0)"
        if has_summary:
            points = read_summary(run_dir / SUMMARY_NAME)
            nearest = min(points, key=lambda p: abs(p.frequency_hz - trace.resonance_hz()))
            title += f"\nD = {nearest.directivity_dbi:.2f} dBi, eta_rad = {nearest.radiation_efficiency:.3f}"
        axis.set_title(title)
        axis.grid(True)

    figure.savefig(out_path, dpi=120)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
