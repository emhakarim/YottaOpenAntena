"""A/B experiment: does port-region mesh refinement move the resonance? (Yotta R-1 / A4)

Runs the SAME project twice with exactly one difference — ``port_refine`` on/off —
and reports resonance, |S11|, VSWR, convergence and runtime for both arms, using the
project's own parse_results so the numbers carry their convergence status.

Speed knobs (recorded in the summary so nobody mistakes a fast run for a converged one):
``--end-criteria`` and ``--max-ts`` exist because a default-convergence run takes tens of
minutes; the A/B question is *relative*, so both arms use the same settings.

Usage (needs openEMS; set OPENEMS_ROOT):

    python scripts/ab_port_refine.py [--end-criteria 1e-3] [--max-ts 60000] [--nf2ff]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repository root (portable, no absolute paths)
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import resonant_frequency_cavity, resonant_frequency
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

ER = 2.1
H = 1.6e-3
WIDTH = 0.049142672841793994
LENGTH = 0.041378916081297096
F0 = 2.45e9


def project(name: str) -> Project:
    return Project(
        name=name,
        substrate=SubstrateStackup.single("PTFE", H),
        patch=PatchGeometry(width_m=WIDTH, length_m=LENGTH, feed_mode="inset"),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.083e9, stop_hz=2.817e9, points=101),
    )


def run_arm(label: str, port_refine: bool, args) -> dict:
    rundir = ROOT / "runs" / f"ab_portrefine_{label}"
    solver = OpenEMSSolver(
        port_refine=port_refine,
        nf2ff=args.nf2ff,
        end_criteria=args.end_criteria,
        max_timesteps=args.max_ts,
    )
    solver.prepare(project(f"ab_{label}"), rundir)

    env = dict(os.environ)
    if "OPENEMS_ROOT" not in env:
        print("ERROR: OPENEMS_ROOT is not set", file=sys.stderr)
        raise SystemExit(2)
    started = time.time()
    proc = subprocess.run(
        [sys.executable, str(rundir / "sim.py")],
        cwd=str(rundir),
        capture_output=True,
        text=True,
        env=env,
    )
    elapsed = time.time() - started
    (rundir / "run.stdout.log").write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")

    record = {"arm": label, "port_refine": port_refine, "returncode": proc.returncode,
              "runtime_s": round(elapsed, 1)}
    try:
        parsed = solver.parse_results(rundir)
        record.update(
            {
                "resonance_hz": parsed["resonance_hz"],
                "worst_match_db": parsed["worst_match_db"],
                "vswr": parsed["vswr_at_resonance"],
                "converged": parsed.get("converged"),
                "convergence_note": parsed.get("convergence_note"),
                "iterations": parsed.get("iterations"),
            }
        )
    except Exception as exc:  # a failed arm is a result, not a crash
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B port_refine on the PTFE patch geometry.")
    parser.add_argument("--end-criteria", type=float, default=1e-3)
    parser.add_argument("--max-ts", type=int, default=60000)
    parser.add_argument("--nf2ff", action="store_true", help="enable the far-field box (slower)")
    args = parser.parse_args()

    cavity = resonant_frequency_cavity(ER, H, WIDTH, LENGTH)
    tl = resonant_frequency(ER, H, WIDTH, LENGTH)
    print(f"reference: cavity {cavity/1e9:.4f} GHz | transmission-line {tl/1e9:.4f} GHz")
    print(f"settings : end_criteria={args.end_criteria:g} max_ts={args.max_ts} nf2ff={args.nf2ff}")

    records = [run_arm("on", True, args), run_arm("off", False, args)]
    for rec in records:
        if "resonance_hz" in rec:
            rec["delta_vs_cavity_pct"] = (rec["resonance_hz"] / cavity - 1.0) * 100.0
        print(json.dumps(rec, default=str))

    with_res = [r for r in records if "resonance_hz" in r]
    summary = {
        "question": "does port-region mesh refinement move the resonance?",
        "reference_cavity_hz": cavity,
        "reference_tl_hz": tl,
        "settings": {"end_criteria": args.end_criteria, "max_timesteps": args.max_ts, "nf2ff": args.nf2ff},
        "arms": records,
    }
    if len(with_res) == 2 and all(r.get("converged") for r in with_res):
        delta = abs(with_res[0]["resonance_hz"] - with_res[1]["resonance_hz"]) / with_res[0]["resonance_hz"]
        summary["delta_fraction"] = delta
        summary["verdict"] = (
            "port refinement MATTERS (>= 0.5 %)" if delta >= 0.005
            else "marginal (0.2-0.5 %)" if delta >= 0.002
            else "cosmetic for this geometry (< 0.2 %) -> write the hypothesis as gugur"
        )
    else:
        summary["verdict"] = "not conclusive: at least one arm did not converge or produced no result"
    (ROOT / "runs" / "ab_port_refine_summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print("\nverdict:", summary["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
