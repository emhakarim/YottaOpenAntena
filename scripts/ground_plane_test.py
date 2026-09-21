"""Ground-plane size test (review item N-01).

The previous margin test enlarged the *domain / PML*, not the *ground plane*.  The
ground plane is itself part of the radiating structure, and its margin has been a
hard-coded 0.25 lambda0 that nobody ever swept.  This script holds the patch, the
mesh density and the feed fixed, and varies only the ground-plane margin.

Usage:
    python scripts/ground_plane_test.py [margin1,margin2,...]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\OpenAntenna")
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import synthesize_patch
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

F0 = 2.45e9
ER = 2.1
H = 1.6e-3


def main() -> int:
    margins = (
        [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [0.25, 0.50, 1.00]
    )
    # Review item D/13.3: with the default setting the domain grows with the ground
    # plane, so a ground sweep also changes the domain and the mesh.  Passing a
    # large fixed air margin removes that confound: the absorber stays far away
    # while only the copper footprint changes.
    air_margin = float(sys.argv[2]) if len(sys.argv) > 2 else 0.20
    air_top = float(sys.argv[3]) if len(sys.argv) > 3 else 0.30
    design = synthesize_patch(F0, ER, H)
    print(f"patch {design.width_m*1e3:.3f} x {design.length_m*1e3:.3f} mm | margins {margins} "
          f"| air margin {air_margin}/{air_top} (fixed)", flush=True)

    results = []
    for margin in margins:
        tag = f"gp_{margin:.2f}".replace(".", "p")
        rundir = ROOT / "runs" / tag
        rundir.mkdir(parents=True, exist_ok=True)

        project = Project(
            name=tag,
            substrate=SubstrateStackup.single("PTFE", H),
            patch=PatchGeometry(
                width_m=design.width_m,
                length_m=design.length_m,
                feed_mode="inset",
                feed_inset_m=design.inset_depth_m,
            ),
            array=ArrayConfig(nx=1, ny=1),
            sweep=FrequencySweep(start_hz=2.0e9, stop_hz=3.0e9, points=101),
        )
        solver = OpenEMSSolver(
            ground_margin_lambda=margin,
            loss_model="kappa",
            air_margin_lambda=air_margin,
            air_top_lambda=air_top,
        )
        solver.prepare(project, rundir)

        env = dict(os.environ)
        env.setdefault("OPENEMS_ROOT", r"D:\OpenAntenna\tools\openEMS")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "run_with_openems.py"), str(rundir / "sim.py")],
            cwd=str(rundir),
            capture_output=True,
            text=True,
            env=env,
        )
        (rundir / "run.stdout.log").write_text(
            (proc.stdout or "") + (proc.stderr or ""), encoding="utf-8"
        )

        record = {"ground_margin_lambda": margin, "returncode": proc.returncode}
        if proc.returncode == 0:
            parsed = solver.parse_results(rundir)
            record.update(
                {
                    "resonance_hz": parsed["resonance_hz"],
                    "worst_match_db": parsed["worst_match_db"],
                    "vswr": parsed["vswr_at_resonance"],
                    "fractional_bandwidth": parsed["fractional_bandwidth"],
                    "converged": parsed["converged"],
                    "timesteps": parsed["timesteps"],
                }
            )
        results.append(record)
        print("    " + json.dumps(record, default=str), flush=True)

    out = ROOT / "runs" / "ground_plane_summary.json"
    out.write_text(
        json.dumps(
            {
                "reference": {"note": "air margin 0.20/0.30 lambda, ground margin 0.25 lambda"},
                "target_hz": F0,
                "results": results,
                "note": (
                    "Only the ground-plane margin varies; patch, feed and mesh density are "
                    "held fixed. A downward trend with a larger ground plane would support "
                    "the finite-ground hypothesis; a flat trend eliminates it."
                ),
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"summary written to {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
