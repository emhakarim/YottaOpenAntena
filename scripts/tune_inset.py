"""Inset (feed) tuning at the length-converged geometry.

Why a second loop: ``auto_tune.py`` fixes the *resonance* by correcting the patch
length, but the *match* is a separate question.  The analytic inset formula
describes a coplanar inset line, while the model actually drives a vertical lumped
port (a probe) - review item Y-19 - so the match has to be tuned empirically as
well.

This script holds the converged length from ``runs/auto_tune_summary.json`` and
sweeps the inset ratio around the analytic value, reporting |S11| and VSWR at the
resonance for each point.  The result is a matched reference design that the
material and loss sweeps can build on.

Usage:
    python scripts/tune_inset.py [length_mm] [ratio,ratio,...]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repository root (portable, no absolute paths)
sys.path.insert(0, str(ROOT))

from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

F_TARGET = 2.45e9
ER = 2.1
H = 1.6e-3
WIDTH_M = 0.049142  # patch width from the synthesis (unchanged: width sets Q/BW)


def converged_length_m() -> float:
    """Read the tuned length from the auto-tune summary if it exists."""
    summary = ROOT / "runs" / "auto_tune_summary.json"
    if summary.exists():
        data = json.loads(summary.read_text(encoding="utf-8"))
        history = data.get("history") or []
        if history:
            return float(history[-1]["length_m"])
    return 0.041378916081297096  # synthesis value, fallback


def run_point(solver: OpenEMSSolver, length: float, ratio: float, rundir: Path) -> dict:
    inset = ratio * length
    project = Project(
        name=f"inset_{ratio:.3f}",
        substrate=SubstrateStackup.single("PTFE", H),
        patch=PatchGeometry(
            width_m=WIDTH_M, length_m=length, feed_mode="inset", feed_inset_m=inset
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=F_TARGET * 0.90, stop_hz=F_TARGET * 1.08, points=91),
    )
    rundir.mkdir(parents=True, exist_ok=True)
    solver.prepare(project, rundir)
    env = dict(os.environ)
    if "OPENEMS_ROOT" not in env:
        print("note: OPENEMS_ROOT is not set - simulations will fail unless the "
              "openEMS runtime is findable. Point it at the folder that holds "
              "openEMS.exe / CSXCAD.dll.")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_with_openems.py"), str(rundir / "sim.py")],
        cwd=str(rundir),
        capture_output=True,
        text=True,
        env=env,
    )
    (rundir / "run.stdout.log").write_text(
        (proc.stdout or "") + (proc.stderr or ""), encoding="utf-8"
    )
    record = {"inset_ratio": ratio, "inset_m": inset, "returncode": proc.returncode}
    if proc.returncode == 0:
        parsed = solver.parse_results(rundir)
        record.update(
            {
                "resonance_hz": parsed["resonance_hz"],
                "worst_match_db": parsed["worst_match_db"],
                "vswr": parsed["vswr_at_resonance"],
            }
        )
    return record


def main() -> int:
    length = (float(sys.argv[1]) / 1e3) if len(sys.argv) > 1 else converged_length_m()
    ratios = (
        tuple(float(x) for x in sys.argv[2].split(","))
        if len(sys.argv) > 2
        else (0.25, 0.30, 0.354, 0.40, 0.45)
    )

    print(f"length {length*1e3:.3f} mm | ratios {ratios}", flush=True)
    solver = OpenEMSSolver(loss_model="kappa")
    history = []
    for ratio in ratios:
        rundir = ROOT / "runs" / f"inset_{ratio:.3f}".replace(".", "p")
        record = run_point(solver, length, ratio, rundir)
        history.append(record)
        print("    " + json.dumps(record, default=str), flush=True)

    usable = [r for r in history if "vswr" in r and r["vswr"] == r["vswr"]]
    best = min(usable, key=lambda r: r["vswr"]) if usable else None
    summary = {
        "length_m": length,
        "target_hz": F_TARGET,
        "history": history,
        "best": best,
        "note": (
            "Feed tuning by empirical sweep. The analytic inset formula describes a "
            "coplanar inset line while this model drives a vertical probe (review item "
            "Y-19), so the sweep - not the formula - is the authority here."
        ),
    }
    out = ROOT / "runs" / "inset_tune_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"summary written to {out}", flush=True)
    if best:
        print(
            "best: inset ratio %.3f (%.3f mm) -> VSWR %.3f, |S11| %.2f dB at %.4f GHz"
            % (
                best["inset_ratio"],
                best["inset_m"] * 1e3,
                best["vswr"],
                best["worst_match_db"],
                best["resonance_hz"] / 1e9,
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
