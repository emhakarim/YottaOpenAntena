"""Sequential heavy-run queue for the machine that owns the CPU work.

Why a queue and not "launch everything": this box has 12 cores / 20 threads and 15.9 GB.  Each
openEMS instance picks its own thread count, so running three heavy batches at once makes all of
them slower and can exhaust RAM.  The queue therefore runs one job at a time, in priority order,
and records a result line per job so a later session can read the outcome without re-deriving it.

Safety rules built in (the owner's mandate: off-target runs are terminated, not left burning):
  * every job has a wall-clock limit; on expiry the whole process tree is killed and the job is
    recorded as ``terminated`` - it is never counted as a result;
  * a job whose summary reports no converged case is recorded as ``rejected``;
  * run directories are unique per job (``--tag``) so no two harnesses share one (WinError 32).

Usage:

    python -m yotta_tools.heavy_queue                 # run the default queue
    python -m yotta_tools.heavy_queue --list          # show the plan
    python -m yotta_tools.heavy_queue --only k1c b1s1 # run a subset
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PY = sys.executable
BATCH = HERE / "parallel_batch.py"
ARRAY = REPO / "scripts" / "array_smatrix.py"
CONCURRENCY_LIMIT = 0  # start only when no other openEMS process is running (serialize the heavy queue)

#: (name, description, command, wall-clock limit in hours)
JOBS: List[Dict[str, object]] = [
    {
        "name": "k1c",
        "what": "K-1 converged: port_refine A/B at EndCriteria 1e-4 / cap 400k (the final-run setting)",
        "cmd": [PY, str(BATCH), "--preset", "port-refine", "--workers", "2",
                "--end-criteria", "1e-4", "--max-ts", "400000",
        "--timeout-s", "14400", "--tag", "k1c_"],
        "hours": 6.0,
        "summary": "runs/batch_k1c_port-refine_summary.json",
    },
    {
        "name": "k2c",
        "what": "K-2 converged: dielectric-loss validation (PTFE kappa / FR-4 kappa / FR-4 none)",
        "cmd": [PY, str(BATCH), "--preset", "loss-validation", "--workers", "2",
                "--end-criteria", "1e-4", "--max-ts", "400000",
        "--timeout-s", "14400", "--tag", "k2c_"],
        "hours": 8.0,
        "summary": "runs/batch_k2c_loss-validation_summary.json",
    },
    {
        "name": "b1s1",
        "what": "B1 swap S1: ground-plane footprint 0.25 vs 0.50 lambda0 at the final setting",
        "cmd": [PY, str(BATCH), "--preset", "ground-margin", "--workers", "2",
                "--end-criteria", "1e-4", "--max-ts", "400000",
        "--timeout-s", "14400", "--tag", "b1s1_"],
        "hours": 6.0,
        "summary": "runs/batch_b1s1_ground-margin_summary.json",
    },
    {
        "name": "arr2",
        "what": "Phase 2 #4 pipeline check: 2x2 array coupling S-matrix (4 runs, one driven port each)",
        "cmd": [PY, str(ARRAY), "--nx", "2", "--ny", "2", "--end-criteria", "1e-3", "--max-ts", "120000",
                "--out", "runs/array2", "--run"],
        "hours": 8.0,
        "summary": "runs/array2/smatrix_summary.json",
    },
    # B2 rerun: the package fix (896e10f5) resolved the unbound s11 port that killed the
    # probe arms after a full FDTD.  Two settings, same two arms, per docs/convergence-policy.md;
    # the earlier attempt burned 3230 s per probe arm and never wrote s11.csv.
    {
        "name": "b2e3",
        "what": "B2 rerun (feed coplanar probe vs line), EndCriteria 1e-3",
        "cmd": [PY, str(REPO / "scripts" / "b2_coplanar_ab_test.py"),
                "--run", "--end-criteria", "1e-3", "--out", "runs_b2/b2_e3"],
        "hours": 6.0,
        "summary": "runs_b2/b2_e3",
    },
    {
        "name": "b2e4",
        "what": "B2 rerun (feed coplanar probe vs line), EndCriteria 1e-4 / cap 400k",
        "cmd": [PY, str(REPO / "scripts" / "b2_coplanar_ab_test.py"),
                "--run", "--end-criteria", "1e-4", "--out", "runs_b2/b2_e4"],
        "hours": 6.0,
        "summary": "runs_b2/b2_e4",
    },
]


def active_solver_processes() -> int:
    """Number of openEMS processes currently running.

    Uses PowerShell, not ``tasklist``: a tasklist filter silently returns nothing on some
    localised Windows builds, and an under-count starts this queue on top of a run that is
    already using the machine - which is exactly the contention the queue exists to avoid.
    """
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process -Name openEMS -ErrorAction SilentlyContinue | Measure-Object).Count"],
            capture_output=True, text=True, timeout=90,
        ).stdout
        return int(out.strip() or 0)
    except Exception:
        return 0


def wait_for_room(limit: int = CONCURRENCY_LIMIT, timeout_s: float = 12 * 3600) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        running = active_solver_processes()
        if running <= limit:
            print(f"[queue] room available ({running} openEMS processes running)", flush=True)
            return
        print(f"[queue] waiting: {running} openEMS processes still running", flush=True)
        time.sleep(120)
    print("[queue] WARNING: waited the full timeout; starting anyway", flush=True)


def run_job(job: Dict[str, object], logdir: Path) -> Dict[str, object]:
    name = str(job["name"])
    log = logdir / f"{name}.log"
    limit_s = float(job["hours"]) * 3600.0  # type: ignore[arg-type]
    started = time.time()
    print(f"[queue] {name}: {job['what']}", flush=True)
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    with open(log, "w", encoding="utf-8") as handle:
        proc = subprocess.Popen([str(x) for x in job["cmd"]],  # type: ignore[arg-type]
                                cwd=str(REPO), env=env, stdout=handle, stderr=subprocess.STDOUT,
                                text=True)
        try:
            returncode = proc.wait(timeout=limit_s)
            status = "completed" if returncode == 0 else f"exit {returncode}"
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=60)
            returncode = None
            status = f"terminated after {job['hours']} h (wall-clock limit)"
    elapsed = time.time() - started
    entry: Dict[str, object] = {
        "job": name, "what": job["what"], "status": status,
        "wall_s": round(elapsed, 1), "log": str(log), "summary": None,
    }
    # A solver job cannot finish in seconds.  If it does, it failed at startup (wrong
    # interpreter without CSXCAD, missing deck, ...) and an rc of 0 must NOT be read as
    # success - that mistake made an earlier queue report four "completed" jobs that had
    # produced nothing at all.
    if elapsed < 60.0:
        entry["status"] = f"failed-fast ({entry['status']} in {elapsed:.1f} s)"
        try:
            tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-6:]
            entry["log_tail"] = [line.strip()[:160] for line in tail]
        except Exception:
            pass

    summary_rel = job.get("summary")
    if summary_rel:
        summary_path = REPO / str(summary_rel)
        if summary_path.is_file():
            try:
                data = json.loads(summary_path.read_text(encoding="utf-8"))
                entry["summary"] = str(summary_path)
                cases = data.get("cases", [])
                entry["cases"] = [
                    {"case": c.get("case"), "resonance_hz": c.get("resonance_hz"),
                     "converged": c.get("converged"), "runtime_s": c.get("runtime_s")}
                    for c in cases
                ]
                accepted = [c for c in entry["cases"] if c.get("converged") is True]  # type: ignore[union-attr]
                entry["accepted_cases"] = len(accepted)
                entry["verdict"] = "usable" if accepted else "rejected (no converged case)"
            except Exception as exc:  # a broken summary must not kill the queue
                entry["summary_error"] = f"{type(exc).__name__}: {exc}"
        else:
            entry["summary_error"] = "summary file not written (job did not finish)"
    return entry


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sequential heavy-run queue.")
    parser.add_argument("--list", action="store_true", help="print the plan and exit")
    parser.add_argument("--only", nargs="*", help="run only these job names")
    parser.add_argument("--logdir", default=str(HERE.parent / "queue_logs"))
    parser.add_argument("--results", default=str(HERE.parent / "queue_results.json"))
    parser.add_argument("--no-wait", action="store_true", help="do not wait for other solver processes")
    args = parser.parse_args(argv)

    jobs = [j for j in JOBS if not args.only or j["name"] in args.only]
    if args.list or not jobs:
        for job in jobs:
            print(f"  {job['name']:6s} [{job['hours']:>3} h] {job['what']}")
        return 0

    logdir = Path(args.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    results_path = Path(args.results)
    results: List[Dict[str, object]] = []
    if results_path.is_file():
        try:
            results = json.loads(results_path.read_text(encoding="utf-8"))
        except Exception:
            results = []

    for job in jobs:
        if not args.no_wait:
            wait_for_room()
        entry = run_job(job, logdir)
        results.append(entry)
        results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"[queue] {entry['job']}: {entry['status']} in {entry['wall_s']} s", flush=True)
    print(f"[queue] done; results in {results_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

