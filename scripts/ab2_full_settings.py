"""A-1 done properly: both arms with FULL settings (EndCriteria 1e-4, 400k steps).

The earlier batch used 20k steps and produced non-converged runs (one read the sweep
edge).  Those numbers were rejected per the project's own reporting rule.  NF2FF is now
opt-in, so both arms run identical and reasonably fast without the far-field cost.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from openantenna.geometry.patch import resonant_frequency_cavity, resonant_frequency
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

ER, H = 2.1, 1.6e-3
WIDTH = 0.049142672841793994
LENGTH = 0.041378916081297096

ARMS = (("on", True), ("off", False))


def project(name: str) -> Project:
    return Project(
        name=name,
        substrate=SubstrateStackup.single("PTFE", H),
        patch=PatchGeometry(width_m=WIDTH, length_m=LENGTH, feed_mode="inset"),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.083e9, stop_hz=2.817e9, points=101),
    )


def main() -> int:
    if not os.environ.get("OPENEMS_ROOT"):
        print("ERROR: OPENEMS_ROOT is not set", file=sys.stderr)
        return 2
    cavity = resonant_frequency_cavity(ER, H, WIDTH, LENGTH)
    tl = resonant_frequency(ER, H, WIDTH, LENGTH)
    print(f"reference: cavity {cavity/1e9:.4f} GHz | transmission-line {tl/1e9:.4f} GHz")

    records = []
    for label, refine in ARMS:
        rundir = Path("runs") / f"ab2_{label}"
        if rundir.exists():
            import shutil
            shutil.rmtree(rundir, ignore_errors=True)
        solver = OpenEMSSolver(
            port_refine=refine,
            nf2ff=False,
            end_criteria=1e-4,
            max_timesteps=400000,
        )
        rundir = solver.prepare(project(f"ab2_{label}"), rundir)
        print(f"arm {label}: starting FDTD (EndCriteria 1e-4, cap 400k) ...")
        started = time.time()
        proc = subprocess.run(
            [sys.executable, "-u", str(rundir / "sim.py")],
            cwd=str(rundir),
            capture_output=True,
            text=True,
            env=dict(os.environ),
        )
        elapsed = time.time() - started
        (rundir / "run.stdout.log").write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
        record = {"arm": label, "returncode": proc.returncode, "runtime_s": round(elapsed, 1)}
        try:
            parsed = solver.parse_results(rundir)
            record.update(
                {
                    "resonance_hz": parsed["resonance_hz"],
                    "delta_vs_cavity_pct": (parsed["resonance_hz"] / cavity - 1.0) * 100.0,
                    "worst_match_db": parsed["worst_match_db"],
                    "vswr": parsed["vswr_at_resonance"],
                    "converged": parsed.get("converged"),
                    "convergence_note": parsed.get("convergence_note"),
                    "iterations": parsed.get("iterations"),
                }
            )
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)
        print(f"  {label}: {json.dumps(record, default=str)[:160]}")

    (Path("runs") / "ab2_summary.json").write_text(
        json.dumps(
            {"reference_cavity_hz": cavity, "reference_tl_hz": tl, "arms": records}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
