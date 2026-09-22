"""Loss validation: does the dielectric-loss model produce credible efficiency?

There is no measurement available, so this is *not* an absolute validation.  What it
does test is a falsifiable prediction with a large expected effect:

    two substrates with the same geometry, differing by a factor of 50 in loss
    tangent (PTFE tan_d=4e-4 vs FR-4 tan_d=2e-2), must produce very different
    radiation efficiencies, and switching the loss model off for FR-4 must recover
    a nearly lossless result.

If the efficiencies came out equal, the loss path would be broken.  If they differ in
the expected direction and by a plausible order of magnitude, the path is at least
active and quantitatively sane - which is the strongest claim available without a
measurement.

Usage:
    python scripts/loss_validation.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import synthesize_patch
from openantenna.materials.library import BUILTIN_MATERIALS, Material
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

F0 = 2.45e9
CASES = [
    # tag, epsilon_r, height_m, tan_delta, loss_model
    ("ptfe_lossy", 2.10, 1.600e-3, 4.0e-4, "kappa"),
    ("fr4_lossy", 4.40, 1.600e-3, 2.0e-2, "kappa"),
    ("fr4_lossless", 4.40, 1.600e-3, 2.0e-2, "none"),
]


def build(tag: str, eps_r: float, height: float, tan_d: float) -> Project:
    name = f"loss-{tag}"
    BUILTIN_MATERIALS[name] = Material(
        name=name,
        epsilon_r=eps_r,
        tan_delta=tan_d,
        source_note="loss-validation substrate",
    )
    design = synthesize_patch(F0, eps_r, height)
    return Project(
        name=f"lossval_{tag}",
        substrate=SubstrateStackup.single(name, height),
        patch=PatchGeometry(
            width_m=design.width_m,
            length_m=design.length_m,
            feed_mode="inset",
            feed_inset_m=design.inset_depth_m,
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=F0 * 0.85, stop_hz=F0 * 1.15, points=101),
    )


def run_case(tag: str, eps_r: float, height: float, tan_d: float, loss_model: str) -> dict:
    project = build(tag, eps_r, height, tan_d)
    solver = OpenEMSSolver(loss_model=loss_model, nf2ff=True)
    rundir = ROOT / "runs" / f"lossval_{tag}"
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

    record = {
        "tag": tag,
        "epsilon_r": eps_r,
        "tan_delta": tan_d,
        "loss_model": loss_model,
        "returncode": proc.returncode,
    }
    if proc.returncode == 0:
        parsed = solver.parse_results(rundir)
        record.update(
            {
                "resonance_hz": parsed.get("resonance_refined_hz"),
                "vswr": parsed.get("vswr_at_resonance"),
                "converged": parsed.get("converged"),
            }
        )
        farfield = parsed.get("farfield")
        if isinstance(farfield, list) and farfield:
            nearest = min(farfield, key=lambda row: abs(row["frequency_hz"] - F0))
            record.update(
                {
                    "directivity_dbi": nearest["directivity_dbi"],
                    "radiation_efficiency": nearest["radiation_efficiency"],
                    "radiated_power_w": nearest["radiated_power_w"],
                    "accepted_power_w": nearest["accepted_power_w"],
                }
            )
        else:
            record["farfield"] = farfield
    return record


def main() -> int:
    records = []
    for tag, eps_r, height, tan_d, loss_model in CASES:
        record = run_case(tag, eps_r, height, tan_d, loss_model)
        records.append(record)
        print("    " + json.dumps(record, default=str), flush=True)

    out = ROOT / "runs" / "loss_validation_summary.json"
    out.write_text(
        json.dumps(
            {
                "records": records,
                "prediction": (
                    "PTFE (tan_d 4e-4) must show a radiation efficiency close to 1; "
                    "FR-4 (tan_d 2e-2) must show a clearly lower one; FR-4 with the loss "
                    "term switched off must return to a nearly lossless efficiency."
                ),
                "status": "not an absolute validation - no measurement was used",
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
