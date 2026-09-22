"""A/B test for the port-region mesh refinement (review item A4 / task A-1).

Yotta added ``port_refine=True``: the mesh is refined in a small box around the
lumped port.  Refining near a feed is not automatically an improvement - it changes
the local discretisation of the port, it lowers the global timestep, and it can move
the *matched* resonance - so the only honest question is what it does to the numbers.

This script runs two geometries twice each, with everything except ``port_refine``
identical, and reports resonance (raw and sub-grid refined), |S11|, VSWR, the
convergence state and the timestep count.

Geometries:
    tutorial   40 x 32 mm, eps_r 3.38, h 1.524 mm, inset 10 mm, margin 0.098 lambda0
    ptfe245    the 2.45 GHz PTFE (eps_r 2.1) patch from the synthesis, margin 0.25

Usage:
    python scripts/port_refine_ab_test.py [tutorial] [ptfe245]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import resonant_frequency_cavity, synthesize_patch
from openantenna.materials.library import BUILTIN_MATERIALS, Material
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

TUTORIAL = dict(
    name="tutorial",
    width_m=40e-3,
    length_m=32e-3,
    epsilon_r=3.38,
    height_m=1.524e-3,
    tan_delta=1.0e-3,
    inset_m=10e-3,
    ground_margin_lambda=12e-3 / (299792458.0 / 2.45e9),
    mesh_cells=20,
    substrate_cells=4,
    center_hz=2.35e9,
)
PTFE = dict(
    name="ptfe245",
    width_m=None,          # from the synthesis
    length_m=None,
    epsilon_r=2.1,
    height_m=1.6e-3,
    tan_delta=4.0e-4,
    inset_m=None,          # analytic inset
    ground_margin_lambda=0.25,
    mesh_cells=15,
    substrate_cells=8,
    center_hz=2.45e9,
)


def build(spec: dict) -> tuple[Project, float, float]:
    material_name = f"ab-{spec['name']}"
    BUILTIN_MATERIALS[material_name] = Material(
        name=material_name,
        epsilon_r=spec["epsilon_r"],
        tan_delta=spec["tan_delta"],
        source_note="A/B test substrate",
    )
    if spec["width_m"] is None:
        design = synthesize_patch(spec["center_hz"], spec["epsilon_r"], spec["height_m"])
        width, length = design.width_m, design.length_m
        inset = spec["inset_m"] or design.inset_depth_m
    else:
        width, length = spec["width_m"], spec["length_m"]
        inset = spec["inset_m"]
    project = Project(
        name=f"portrefine_{spec['name']}",
        substrate=SubstrateStackup.single(material_name, spec["height_m"]),
        patch=PatchGeometry(
            width_m=width, length_m=length, feed_mode="inset", feed_inset_m=inset
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(
            start_hz=spec["center_hz"] * 0.85, stop_hz=spec["center_hz"] * 1.15, points=101
        ),
    )
    return project, width, length


def run_case(spec: dict, port_refine: bool) -> dict:
    project, width, length = build(spec)
    solver = OpenEMSSolver(
        mesh_cells_per_wavelength=spec["mesh_cells"],
        substrate_cells=spec["substrate_cells"],
        ground_margin_lambda=spec["ground_margin_lambda"],
        loss_model="kappa",
        port_refine=port_refine,
    )
    tag = f"portrefine_{spec['name']}_on" if port_refine else f"portrefine_{spec['name']}_off"
    rundir = ROOT / "runs" / tag
    # Start from a clean directory.  On Windows, FDTD.Run(cleanup=True) tries to
    # delete the previous run's port files, and a stale handle from an interrupted
    # attempt makes that fail with WinError 32 - which looks like a physics failure
    # but is a file lock.  Clearing the directory here avoids the whole class.
    if rundir.exists():
        shutil.rmtree(rundir)
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

    cavity = resonant_frequency_cavity(spec["epsilon_r"], spec["height_m"], width, length)
    record = {
        "geometry": spec["name"],
        "port_refine": port_refine,
        "width_m": width,
        "length_m": length,
        "cavity_hz": cavity,
        "returncode": proc.returncode,
    }
    if proc.returncode == 0:
        parsed = solver.parse_results(rundir)
        measured = parsed.get("resonance_refined_hz") or parsed["resonance_hz"]
        record.update(
            {
                "resonance_grid_hz": parsed["resonance_hz"],
                "resonance_refined_hz": measured,
                "worst_match_db": parsed["worst_match_db"],
                "vswr": parsed["vswr_at_resonance"],
                "converged": parsed["converged"],
                "timesteps": parsed["timesteps"],
                "delta_vs_cavity_percent": (measured - cavity) / cavity * 100.0,
            }
        )
    return record


def main() -> int:
    wanted = sys.argv[1:] or ["tutorial", "ptfe245"]
    if len(wanted) == 1 and "," in wanted[0]:
        # accept both "a b" and "a,b" so a launcher cannot silently pass one bad key
        wanted = [item.strip() for item in wanted[0].split(",") if item.strip()]
    specs = {"tutorial": TUTORIAL, "ptfe245": PTFE}
    unknown = [key for key in wanted if key not in specs]
    if unknown:
        raise SystemExit(f"unknown geometry key(s): {unknown}; known: {sorted(specs)}")
    records = []
    for key in wanted:
        for flag in (True, False):
            record = run_case(specs[key], flag)
            records.append(record)
            print("    " + json.dumps(record, default=str), flush=True)

    out = ROOT / "runs" / "port_refine_ab_summary.json"
    out.write_text(
        json.dumps(
            {
                "records": records,
                "criterion": (
                    "Interpretation: if |delta_vs_cavity| changes materially between "
                    "on and off, port refinement matters for this geometry; if it does "
                    "not, keep it off (it lowers the timestep and costs runtime)."
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
