"""Air-domain / absorber-proximity test.

Remaining candidate for the 2.45 GHz patch model resonating at ~2.26 GHz after
mesh refinement and feed loading were both eliminated.  The tutorial model that
does hit its design frequency uses a far more generous air domain, so this test
varies only the air margin (0.20/0.30 lambda -> 0.50/0.60 lambda) and keeps the
geometry, mesh density and feed identical to the reference run.

Usage:
    python scripts/air_margin_test.py [margin_lambda] [top_lambda]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repository root (portable, no absolute paths)
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
    margin = float(sys.argv[1]) if len(sys.argv) > 1 else 0.50
    top = float(sys.argv[2]) if len(sys.argv) > 2 else 0.60

    design = synthesize_patch(F0, ER, H)
    project = Project(
        name=f"air_margin_{margin:g}",
        substrate=SubstrateStackup.single("PTFE", H),
        patch=PatchGeometry(
            width_m=design.width_m,
            length_m=design.length_m,
            feed_mode="inset",
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.0e9, stop_hz=3.0e9, points=101),
    )

    solver = OpenEMSSolver(air_margin_lambda=margin, air_top_lambda=top)
    rundir = ROOT / "runs" / f"air_margin_{margin:g}".replace(".", "p")
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

    record = {
        "case": f"air_margin_{margin:g}",
        "air_margin_lambda": margin,
        "air_top_lambda": top,
        "returncode": proc.returncode,
    }
    try:
        parsed = solver.parse_results(rundir)
        record.update(
            {
                "resonance_hz": parsed["resonance_hz"],
                "worst_match_db": parsed["worst_match_db"],
                "vswr": parsed["vswr_at_resonance"],
                "fractional_bandwidth": parsed["fractional_bandwidth"],
            }
        )
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"

    out = ROOT / "runs" / "air_margin_summary.json"
    existing = []
    if out.exists():
        existing = json.loads(out.read_text(encoding="utf-8")).get("cases", [])
    existing.append(record)
    out.write_text(json.dumps({"reference_resonance_hz": 2.26e9, "cases": existing}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
