"""Array S-matrix driver (Phase 2 #4, the CPU-heavy half).

Generates one model with a lumped port per array element, runs it once per driven port (the
driven port comes from ``OPENANTENNA_EXCITE_PORT``, so the deck never changes between runs), and
assembles the coupling matrix with ``yotta_tools.port_matrix``.

Design notes that matter for an overnight run:

* **Resumable.**  A run whose ``port_<n>.csv`` files are all present is skipped, so an interrupted
  queue can be restarted without redoing hours of work.
* **Bounded.**  Each run gets a wall-clock limit; on expiry the process is killed and the port is
  recorded as failed - a killed run is never silently treated as a result.
* **Honest.**  The convergence state of every run is carried into the summary, and the coupling
  numbers are reported next to it (see ``docs/array-s-matrix.md`` and
  ``docs/convergence-policy.md``).

Usage:

    python scripts/array_smatrix.py --nx 2 --ny 2 --run
    python scripts/array_smatrix.py --nx 4 --ny 4 --end-criteria 1e-4 --max-ts 400000 --run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from openantenna.model.project import (  # noqa: E402
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver  # noqa: E402
from yotta_tools import port_matrix  # noqa: E402


def build_project(nx: int, ny: int, material: str, thickness_m: float, f0_hz: float) -> Project:
    project = Project(
        name=f"array{nx}x{ny}",
        substrate=SubstrateStackup(layers=[{"material": material, "thickness_m": thickness_m}]),
        sweep=FrequencySweep(start_hz=f0_hz * 0.8, stop_hz=f0_hz * 1.2, points=101),
        array=ArrayConfig(nx=nx, ny=ny, spacing_x_lambda0=0.5, spacing_y_lambda0=0.5),
        patch=PatchGeometry(feed_mode="probe"),
    )
    # element ports are probe-style until the corporate feed exists (Phase 2 #5)
    project.patch.feed_line_width_m = 0.0
    return project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Array coupling S-matrix driver.")
    parser.add_argument("--nx", type=int, default=2)
    parser.add_argument("--ny", type=int, default=2)
    parser.add_argument("--material", default="PTFE")
    parser.add_argument("--thickness-mm", type=float, default=1.6)
    parser.add_argument("--f0-ghz", type=float, default=2.45)
    parser.add_argument("--end-criteria", type=float, default=1e-3)
    parser.add_argument("--max-ts", type=int, default=120000)
    parser.add_argument("--hours-per-run", type=float, default=3.0)
    parser.add_argument("--out", default="runs/array")
    parser.add_argument("--run", action="store_true", help="actually run (otherwise only prepare)")
    args = parser.parse_args(argv)

    f0 = args.f0_ghz * 1e9
    project = build_project(args.nx, args.ny, args.material, args.thickness_mm * 1e-3, f0)
    n_ports = args.nx * args.ny

    out_dir = (REPO / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    solver = OpenEMSSolver(
        element_ports=True,
        end_criteria=args.end_criteria,
        max_timesteps=args.max_ts,
    )
    rundir = solver.prepare(project, out_dir / "model")
    script = Path(rundir) / "sim.py"
    print(f"[array] {args.nx}x{args.ny} = {n_ports} ports; deck: {script}", flush=True)
    print(f"[array] settings: EndCriteria {args.end_criteria:g}, cap {args.max_ts} steps, "
          f"{args.material} {args.thickness_mm} mm, f0 {args.f0_ghz} GHz", flush=True)

    if not args.run:
        print("[array] prepared only (pass --run to execute)", flush=True)
        return 0

    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    runs = []
    for driven in range(1, n_ports + 1):
        run_dir = out_dir / f"port{driven}"
        run_dir.mkdir(parents=True, exist_ok=True)
        port_files = [run_dir / f"port_{i}.csv" for i in range(1, n_ports + 1)]
        if all(p.is_file() for p in port_files):
            print(f"[array] port {driven}: already done, skipping", flush=True)
            runs.append((run_dir, driven))
            continue
        work = run_dir / "sim.py"
        work.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
        env_run = dict(env)
        env_run["OPENANTENNA_EXCITE_PORT"] = str(driven)
        log = open(run_dir / "run.log", "w", encoding="utf-8")
        started = time.time()
        print(f"[array] port {driven}/{n_ports}: running", flush=True)
        proc = subprocess.Popen([sys.executable, str(work)], cwd=str(run_dir), env=env_run,
                                stdout=log, stderr=subprocess.STDOUT, text=True)
        try:
            rc = proc.wait(timeout=args.hours_per_run * 3600.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=60)
            rc = None
            print(f"[array] port {driven}: TERMINATED after {args.hours_per_run} h", flush=True)
        log.close()
        elapsed = round(time.time() - started, 1)
        missing = [p.name for p in port_files if not p.is_file()]
        print(f"[array] port {driven}: rc={rc} in {elapsed} s, missing={missing or 'none'}", flush=True)
        if rc == 0 and not missing:
            runs.append((run_dir, driven))

    if len(runs) < n_ports:
        print(f"[array] only {len(runs)}/{n_ports} runs usable - no matrix assembled", flush=True)
        (out_dir / "smatrix_summary.json").write_text(json.dumps(
            {"status": "incomplete", "usable_runs": len(runs), "n_ports": n_ports}, indent=2) + "\n",
            encoding="utf-8")
        return 1

    result = port_matrix.assemble(runs, n_ports=n_ports)
    summary = port_matrix.coupling_summary(result)
    payload = {
        "n_ports": n_ports,
        "nx": args.nx, "ny": args.ny, "material": args.material,
        "end_criteria": args.end_criteria, "max_timesteps": args.max_ts,
        "runs": result["runs"],
        "resonance_hz": summary["frequency_hz"],
        "s11_db": summary["s11_db"],
        "worst_coupling_db": summary["worst_coupling_db"],
        "note": "quote only if every run converged; see docs/convergence-policy.md",
    }
    (out_dir / "smatrix_summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[array] |S11| min {summary['s11_db']:.2f} dB at {summary['frequency_hz'] / 1e9:.4f} GHz; "
          f"worst coupling {summary['worst_coupling_db']:.2f} dB", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
