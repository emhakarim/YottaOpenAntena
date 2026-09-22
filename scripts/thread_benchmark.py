"""Measure FDTD wall time against thread count on this machine.

Why this exists: openEMS is CPU-only (no CUDA/OpenCL), so the GPU in a laptop cannot
speed up the solver.  What *can* help is the number of CPU threads, and openEMS prints
its own guess ("Best performance found using N threads") which is measured on a short
warm-up and is often pessimistic.

This script runs the same model with a fixed thread count several times and reports
wall time per thread setting, so the choice is based on measurement instead of a
default.

Notes:
* run it on an otherwise idle machine, and do not run two instances at once;
* the model is deliberately coarse and short (mesh 10 cells/lambda, 5 sweep points) so
  the whole benchmark finishes quickly; the *scaling* is what transfers, not the
  absolute seconds.

Usage:
    python scripts/thread_benchmark.py [threads,csv] [--mesh N] [--points N]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


def parse_args(argv: list[str]) -> tuple[list[int], int, int]:
    threads = [0, 1, 4, 8, 16]
    mesh, points = 10, 5
    positional = [a for a in argv if not a.startswith("--")]
    if positional:
        threads = [int(x) for x in positional[0].split(",") if x.strip()]
    if "--mesh" in argv:
        mesh = int(argv[argv.index("--mesh") + 1])
    if "--points" in argv:
        points = int(argv[argv.index("--points") + 1])
    return threads, mesh, points


def main() -> int:
    threads, mesh, points = parse_args(sys.argv[1:])
    design = synthesize_patch(F0, ER, H)
    project = Project(
        name="thread_benchmark",
        substrate=SubstrateStackup.single("PTFE", H),
        patch=PatchGeometry(
            width_m=design.width_m,
            length_m=design.length_m,
            feed_mode="inset",
            feed_inset_m=design.inset_depth_m,
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=F0 * 0.9, stop_hz=F0 * 1.1, points=points),
    )

    env = dict(os.environ)
    env.setdefault("OPENEMS_ROOT", os.environ.get("OPENEMS_ROOT", ""))
    records = []
    for count in threads:
        solver = OpenEMSSolver(
            mesh_cells_per_wavelength=mesh,
            numthreads=count,
            nf2ff=False,  # irrelevant here and it costs recording time
        )
        rundir = ROOT / "runs" / f"threadbench_{count}"
        rundir.mkdir(parents=True, exist_ok=True)
        solver.prepare(project, rundir)
        started = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_with_openems.py"), str(rundir / "sim.py")],
            cwd=str(rundir),
            capture_output=True,
            text=True,
            env=env,
        )
        elapsed = time.perf_counter() - started
        (rundir / "run.stdout.log").write_text(
            (proc.stdout or "") + (proc.stderr or ""), encoding="utf-8"
        )
        record = {
            "numthreads": count,
            "wall_s": round(elapsed, 1),
            "returncode": proc.returncode,
        }
        if proc.returncode == 0:
            parsed = solver.parse_results(rundir)
            record["timesteps"] = parsed.get("timesteps")
            record["converged"] = parsed.get("converged")
        records.append(record)
        print("    " + json.dumps(record), flush=True)

    baseline = next((r["wall_s"] for r in records if r["numthreads"] == 1 and r["returncode"] == 0), None)
    if baseline:
        for record in records:
            record["speedup_vs_1_thread"] = round(baseline / record["wall_s"], 2)

    out = ROOT / "runs" / "thread_benchmark.json"
    out.write_text(
        json.dumps(
            {
                "records": records,
                "note": (
                    "Wall time for the same model at different thread counts. Use the "
                    "fastest setting as the default for this machine's runs; remember "
                    "that running sweep jobs in parallel multiplies the demand, so "
                    "choose max_workers and numthreads together."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"summary written to {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
