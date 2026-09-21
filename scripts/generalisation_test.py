"""Generalisation test: is the model-construction bias a constant factor?

Review item 13.4 (Yotta): the construction bias measured on one geometry does not
tell us whether it is a constant that can be calibrated once, or a
geometry-dependent error that requires per-design tuning.  The two answers imply
different roadmaps, so this script repeats the comparison on several geometries:

    2.45 GHz, eps_r 2.10, h 1.60 mm   (PTFE, the original case)
    5.80 GHz, eps_r 2.20, h 0.787 mm  (RT/duroid-class laminate)
    5.80 GHz, eps_r 4.40, h 1.60 mm   (FR-4-class laminate)

For each: our synthesis produces the patch, our generator builds the model with
default settings, the solver runs, and the measured resonance is compared with the
transmission-line and cavity predictions.

Usage:
    python scripts/generalisation_test.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repository root (portable, no absolute paths)
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import (
    resonant_frequency,
    resonant_frequency_cavity,
    synthesize_patch,
)
from openantenna.materials.library import BUILTIN_MATERIALS, Material
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

GEOMETRIES = [
    ("ptfe_245", 2.45e9, 2.10, 1.600e-3, 4.0e-4),
    ("duroid_580", 5.80e9, 2.20, 0.787e-3, 9.0e-4),
    ("fr4_580", 5.80e9, 4.40, 1.600e-3, 2.0e-2),
]


def main() -> int:
    results = []
    for tag, f0, eps_r, height, tan_d in GEOMETRIES:
        material_name = f"gen-{tag}"
        BUILTIN_MATERIALS[material_name] = Material(
            name=material_name,
            epsilon_r=eps_r,
            tan_delta=tan_d,
            source_note=f"generalisation test substrate: eps_r {eps_r}, tan_d {tan_d}",
        )
        design = synthesize_patch(f0, eps_r, height)
        project = Project(
            name=f"gen_{tag}",
            substrate=SubstrateStackup.single(material_name, height),
            patch=PatchGeometry(
                width_m=design.width_m,
                length_m=design.length_m,
                feed_mode="inset",
                feed_inset_m=design.inset_depth_m,
            ),
            array=ArrayConfig(nx=1, ny=1),
            sweep=FrequencySweep(start_hz=f0 * 0.85, stop_hz=f0 * 1.12, points=101),
        )
        solver = OpenEMSSolver(loss_model="kappa")  # defaults, snapping on
        rundir = ROOT / "runs" / f"gen_{tag}"
        rundir.mkdir(parents=True, exist_ok=True)
        solver.prepare(project, rundir)

        env = dict(os.environ)
        if "OPENEMS_ROOT" not in env:
            print("note: OPENEMS_ROOT is not set - simulations will fail unless the "
                  "openEMS runtime is findable. Point it at the folder that holds "
                  "openEMS.exe / CSXCAD.dll.")
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

        tl = resonant_frequency(eps_r, height, design.width_m, design.length_m)
        cavity = resonant_frequency_cavity(eps_r, height, design.width_m, design.length_m)
        record = {
            "tag": tag,
            "target_hz": f0,
            "epsilon_r": eps_r,
            "height_m": height,
            "patch_width_m": design.width_m,
            "patch_length_m": design.length_m,
            "width_over_height": design.width_m / height,
            "eps_eff": design.epsilon_eff,
            "transmission_line_hz": tl,
            "cavity_hz": cavity,
            "returncode": proc.returncode,
        }
        if proc.returncode == 0:
            parsed = solver.parse_results(rundir)
            measured = parsed["resonance_hz"]
            record.update(
                {
                    "measured_hz": measured,
                    "vswr": parsed["vswr_at_resonance"],
                    "converged": parsed["converged"],
                    "delta_vs_target_percent": (measured - f0) / f0 * 100.0,
                    "delta_vs_cavity_percent": (measured - cavity) / cavity * 100.0,
                    "delta_vs_tl_percent": (measured - tl) / tl * 100.0,
                }
            )
        results.append(record)
        print("    " + json.dumps(record, default=str), flush=True)

    out = ROOT / "runs" / "generalisation_summary.json"
    out.write_text(
        json.dumps(
            {
                "results": results,
                "note": (
                    "delta_vs_cavity_percent is the key column: a roughly constant value "
                    "means the construction bias can be calibrated once; a varying value "
                    "means per-geometry tuning is required."
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
