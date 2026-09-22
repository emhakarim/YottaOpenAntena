"""A/B test of model-construction settings on the tutorial geometry.

The separating experiment showed that our generator lands 4.3 % below the
openEMS-shipped tutorial model on identical geometry, so the bias is in our model
*construction*.  This script varies one construction setting at a time, on the
tutorial geometry, to find which one costs the difference:

    ours            PML_8, margins 0.20/0.30 lambda, smoothing 1.4
    mur             same, but MUR boundaries (what the tutorial uses)
    bigdomain       PML_8, but margins 0.80/0.80 lambda (domain ~200 mm)
    tutorial_like   MUR + big domain

Reference: the unmodified tutorial model resonated at 2.435 GHz.

Usage:
    python scripts/construction_ab_test.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import resonant_frequency_cavity
from openantenna.materials.library import BUILTIN_MATERIALS, Material
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

WIDTH_X = 40e-3
LENGTH_Y = 32e-3
EPS_R = 3.38
H_SUB = 1.524e-3
TAN_D = 1.0e-3
MARGIN_GROUND = 12e-3 / (299792458.0 / 2.45e9)
INSET = LENGTH_Y / 2.0 - 6e-3
TUTORIAL_REFERENCE_HZ = 2.435e9

CONFIGS = {
    "ours": dict(boundary="PML", pml_cells=8, air_margin_lambda=0.20, air_top_lambda=0.30),
    "mur": dict(boundary="MUR", air_margin_lambda=0.20, air_top_lambda=0.30),
    "bigdomain": dict(boundary="PML", pml_cells=8, air_margin_lambda=0.80, air_top_lambda=0.80),
    "tutorial_like": dict(boundary="MUR", air_margin_lambda=0.80, air_top_lambda=0.80),
    # The tutorial meshes with a uniform 5 mm grid and no smoothing; we grow the
    # cells away from the structure with SmoothMeshLines(1.4).  Grading changes
    # the local numerical dispersion, so test a quasi-uniform mesh explicitly.
    "uniformmesh": dict(
        boundary="PML", air_margin_lambda=0.20, air_top_lambda=0.30, mesh_smoothing_ratio=1.01
    ),
    # Metal-edge snapping OFF (we add AddEdges2Grid by default, like the tutorial).
    "no_edge_snap": dict(
        boundary="PML", air_margin_lambda=0.20, air_top_lambda=0.30, metal_edge_snapping=False
    ),
}


def main() -> int:
    BUILTIN_MATERIALS["tutorial-substrate"] = Material(
        name="tutorial-substrate",
        epsilon_r=EPS_R,
        tan_delta=TAN_D,
        source_note="openEMS tutorial substrate (eps_r 3.38, tan_d 1e-3)",
    )
    project = Project(
        name="construction_ab",
        substrate=SubstrateStackup.single("tutorial-substrate", H_SUB),
        patch=PatchGeometry(
            width_m=WIDTH_X, length_m=LENGTH_Y, feed_mode="inset", feed_inset_m=INSET
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=1.8e9, stop_hz=2.9e9, points=111),
    )

    results = []
    wanted = sys.argv[1].split(",") if len(sys.argv) > 1 else list(CONFIGS)
    for label in wanted:
        kwargs = CONFIGS[label]
        solver = OpenEMSSolver(
            mesh_cells_per_wavelength=20,
            substrate_cells=4,
            ground_margin_lambda=MARGIN_GROUND,
            loss_model="kappa",
            **kwargs,
        )
        rundir = ROOT / "runs" / f"ab_{label}"
        rundir.mkdir(parents=True, exist_ok=True)
        solver.prepare(project, rundir)

        env = dict(os.environ)
        env.setdefault("OPENEMS_ROOT", os.environ.get("OPENEMS_ROOT", ""))
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

        record = {"config": label, "settings": kwargs, "returncode": proc.returncode}
        if proc.returncode == 0:
            parsed = solver.parse_results(rundir)
            record.update(
                {
                    "resonance_hz": parsed["resonance_hz"],
                    "worst_match_db": parsed["worst_match_db"],
                    "vswr": parsed["vswr_at_resonance"],
                    "converged": parsed["converged"],
                    "timesteps": parsed["timesteps"],
                    "delta_vs_tutorial_percent": (
                        (parsed["resonance_hz"] - TUTORIAL_REFERENCE_HZ)
                        / TUTORIAL_REFERENCE_HZ
                        * 100.0
                    ),
                }
            )
        results.append(record)
        print("    " + json.dumps(record, default=str), flush=True)

    out = ROOT / "runs" / "construction_ab_summary.json"
    previous: dict = {}
    if out.exists():
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
        except ValueError:
            previous = {}
    merged = {row["config"]: row for row in previous.get("results", [])}
    for row in results:
        merged[row["config"]] = row
    out.write_text(
        json.dumps(
            {
                "tutorial_reference_hz": TUTORIAL_REFERENCE_HZ,
                "cavity_prediction_hz": resonant_frequency_cavity(EPS_R, H_SUB, WIDTH_X, LENGTH_Y),
                "results": list(merged.values()),
                "note": (
                    "One construction setting varies per row. Whichever row closes the gap "
                    "to the tutorial reference identifies the bias source; if none does, the "
                    "difference lies in something not varied here."
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
