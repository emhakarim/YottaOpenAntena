"""Distinguish the patch resonance from the |S11| minimum.

Review item N-04 warned that the minimum of |S11| is not necessarily the natural
resonance of the patch: the feed and its reactance contribute.  This script reads
S11 traces that already exist and reports, per run:

* the frequency of minimum |S11| (what the tuning loop chased),
* the frequency of maximum Re(Zin) (the classic series-resonance indicator),
* the frequency where Im(Zin) crosses zero from inductive to capacitive,
* the analytic predictions (transmission-line and cavity models) for reference.

No simulation is required - it works on stored s11.csv files.

Usage:
    python scripts/analyze_resonance.py [run_dir ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repository root (portable, no absolute paths)
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import resonant_frequency, resonant_frequency_cavity
from openantenna.postproc.sparams import S11Trace

DEFAULT_RUNS = ["patch_ptfe_v4", "gp_0p25", "gp_0p50", "gp_1p00", "tune_it3"]
ER = 2.1
H = 1.6e-3
WIDTH = 0.049142
SYNTH_LENGTH = 0.041378916081297096


def crossing_zero(freqs, values) -> float | None:
    """First frequency where a sampled sequence crosses zero (linear interp)."""
    for i in range(1, len(values)):
        a, b = values[i - 1], values[i]
        if a == 0.0:
            return freqs[i - 1]
        if (a < 0 < b) or (a > 0 > b):
            span = b - a
            if span == 0:
                return freqs[i]
            return freqs[i - 1] + (0.0 - a) * (freqs[i] - freqs[i - 1]) / span
    return None


def analyse(run_dir: Path) -> None:
    csv_path = run_dir / "s11.csv"
    if not csv_path.exists():
        print(f"{run_dir.name:<14} no s11.csv")
        return
    trace = S11Trace.from_csv(csv_path)
    freqs = trace.frequencies_hz
    zin = trace.impedance_ohm()

    min_index = trace.worst_match_index()
    f_min = freqs[min_index]
    f_max_r = freqs[max(range(len(zin)), key=lambda i: zin[i].real)]
    f_x_zero = crossing_zero(freqs, [z.imag for z in zin])

    tl = resonant_frequency(ER, H, WIDTH, SYNTH_LENGTH)
    cavity = resonant_frequency_cavity(ER, H, WIDTH, SYNTH_LENGTH)

    print(f"{run_dir.name:<14} |S11|min {f_min/1e9:.4f} GHz | maxReZ {f_max_r/1e9:.4f} GHz "
          f"| ImZ=0 {('%.4f GHz' % (f_x_zero/1e9)) if f_x_zero else 'none'}")
    print(
        f"{'':<14} peak Re(Z) = {max(z.real for z in zin):.1f} ohm "
        f"| R at |S11|min = {zin[min_index].real:.1f} ohm "
        f"| X at |S11|min = {zin[min_index].imag:+.1f} ohm"
    )
    print(
        f"{'':<14} analytic: TL {tl/1e9:.4f} GHz, cavity {cavity/1e9:.4f} GHz "
        f"(lower bound for any valid eps_eff)"
    )


def main() -> int:
    names = sys.argv[1:] or DEFAULT_RUNS
    print("models for the synthesis geometry (W = 49.143 mm, L = 41.379 mm, PTFE 1.6 mm):")
    analyse_dir = ROOT / "runs"
    for name in names:
        analyse(analyse_dir / name)
        print()
    print(
        "Reading: if max Re(Z) sits well above the |S11| minimum, the minimum is a\n"
        "feed/matching artefact and the tuning loop chased the wrong feature."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
