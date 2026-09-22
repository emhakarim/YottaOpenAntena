"""Separating experiment: run OUR generator on the tutorial geometry.

Review item N-04 / Y-T1 sharpest test.  The openEMS-shipped
``Simple_Patch_Antenna.py`` model (unmodified) resonates at 2.435 GHz.  If our
generator, fed with exactly the tutorial's geometry and substrate, also lands near
2.435 GHz, then our *model construction* is sound and the offset seen on the
wide-patch PTFE geometry is specific to that geometry.  If it lands lower, the
bias is in our construction (mesh lines, port, domain).

Tutorial parameters (from the shipped script):
    patch 40 x 32 mm (40 mm along x, 32 mm along the resonant axis)
    substrate eps_r = 3.38, h = 1.524 mm, 60 x 60 mm footprint, tan_delta = 1e-3
    feed offset 6 mm from the patch centre along the resonant axis (50 ohm)
    mesh_res = 5 mm, substrate 4 cells, nrTS = 30000, end criteria 1e-4

Usage:
    python scripts/generator_anchor_test.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import resonant_frequency, resonant_frequency_cavity
from openantenna.materials.library import BUILTIN_MATERIALS, Material
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

# Tutorial geometry, expressed in our convention (length = resonant dimension).
WIDTH_X = 40e-3   # 40 mm along x
LENGTH_Y = 32e-3  # 32 mm along the resonant axis
EPS_R = 3.38
H_SUB = 1.524e-3
TAN_D = 1.0e-3
# Ground plane ~60 x 60 mm in the tutorial -> margin ~12 mm per side.
MARGIN_LAMBDA = 12e-3 / (299792458.0 / 2.45e9)
FEED_FROM_CENTRE = 6e-3
INSET = LENGTH_Y / 2.0 - FEED_FROM_CENTRE  # 10 mm from the radiating edge

TUTORIAL_REFERENCE_HZ = 2.435e9  # our measurement of the unmodified tutorial


def main() -> int:
    # Register the tutorial substrate so the generator can look it up by name.
    BUILTIN_MATERIALS["tutorial-substrate"] = Material(
        name="tutorial-substrate",
        epsilon_r=EPS_R,
        tan_delta=TAN_D,
        source_note="openEMS Simple_Patch_Antenna tutorial substrate (eps_r 3.38, tan_d 1e-3)",
    )

    project = Project(
        name="generator_anchor_tutorial_geometry",
        substrate=SubstrateStackup.single("tutorial-substrate", H_SUB),
        patch=PatchGeometry(
            width_m=WIDTH_X,
            length_m=LENGTH_Y,
            feed_mode="inset",
            feed_inset_m=INSET,
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=1.8e9, stop_hz=2.9e9, points=111),
    )

    solver = OpenEMSSolver(
        mesh_cells_per_wavelength=20,   # ~5 mm, matching the tutorial
        substrate_cells=4,              # matching the tutorial
        ground_margin_lambda=MARGIN_LAMBDA,
        loss_model="kappa",
    )
    rundir = ROOT / "runs" / "anchor_generator_on_tutorial"
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

    record: dict = {
        "case": "generator_on_tutorial_geometry",
        "returncode": proc.returncode,
        "geometry": {
            "width_x_m": WIDTH_X,
            "length_y_m": LENGTH_Y,
            "epsilon_r": EPS_R,
            "height_m": H_SUB,
            "tan_delta": TAN_D,
            "ground_margin_lambda": MARGIN_LAMBDA,
            "inset_m": INSET,
        },
        "tutorial_reference_hz": TUTORIAL_REFERENCE_HZ,
        "analytic_transmission_line_hz": resonant_frequency(EPS_R, H_SUB, WIDTH_X, LENGTH_Y),
        "analytic_cavity_hz": resonant_frequency_cavity(EPS_R, H_SUB, WIDTH_X, LENGTH_Y),
    }
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

    out = ROOT / "runs" / "anchor_generator_summary.json"
    out.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
