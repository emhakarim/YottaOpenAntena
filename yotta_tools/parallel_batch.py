"""Run several solver cases concurrently on one machine (Yotta's batch runner).

Why: FDTD is memory-light and this machine sits at ~18 % CPU with 15.9 GB RAM, so a
batch of independent cases finishes in roughly the time of the slowest case instead of
the sum of all cases.  Every case gets its own run directory, its own log written
unbuffered (`python -u`), and its result is parsed with the project's own
``parse_results`` so convergence travels with the number.

Two safety rules learned the hard way in this project:
  * one run directory per case, cleaned before use -> no Windows file-lock failures;
  * child processes are tracked and killed on timeout -> no orphaned solver holding a
    directory, which is what caused a previous `WinError 32`.

Usage::

    python yotta_tools/parallel_batch.py --preset air-margin --workers 4
    python yotta_tools/parallel_batch.py --preset ground-margin --workers 4
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from openantenna.geometry.patch import resonant_frequency_cavity, resonant_frequency
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

ER = 2.1
H = 1.6e-3
WIDTH = 0.049142672841793994
LENGTH = 0.041378916081297096


def project(name: str, material: str = "PTFE", height_m: float = H) -> Project:
    return Project(
        name=name,
        substrate=SubstrateStackup.single(material, height_m),
        patch=PatchGeometry(width_m=WIDTH, length_m=LENGTH, feed_mode="inset"),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.083e9, stop_hz=2.817e9, points=101),
    )


#: each preset is one variable per pair - the whole point of the experiment
PRESETS: dict[str, list[dict]] = {
    "air-margin": [
        {"name": "air040", "label": "air margin 0.40 lambda0", "kwargs": {"air_margin_lambda": 0.40}},
        {"name": "air080", "label": "air margin 0.80 lambda0 (current default)", "kwargs": {"air_margin_lambda": 0.80}},
    ],
    "ground-margin": [
        # domain held constant at the air040/ground025 value: DOM = GROUND/2 + air*lambda_min
        {"name": "gm025", "label": "ground 0.25 lambda0, domain 140.3 mm",
         "kwargs": {"ground_margin_lambda": 0.25, "air_margin_lambda": 0.80}},
        {"name": "gm050", "label": "ground 0.50 lambda0, SAME domain",
         "kwargs": {"ground_margin_lambda": 0.50, "air_margin_lambda": 0.513}},
    ],
    "port-refine": [
        # A-1: the one variable is the port-region refinement.  Both arms must use the
        # SAME EndCriteria/cap (see --end-criteria / --max-ts): the 1e-4 + 400k default did
        # not converge on this machine in three separate attempts.
        {"name": "prab_on", "label": "port_refine on", "kwargs": {"port_refine": True}},
        {"name": "prab_off", "label": "port_refine off", "kwargs": {"port_refine": False}},
    ],
    "loss-validation": [
        # B3, taken over from the cancelled PTFE pair: the loss MODEL is the variable, the
        # far-field box is needed because radiation efficiency is the observable.
        {"name": "loss_ptfe", "label": "PTFE tanD 4e-4 through kappa",
         "kwargs": {"nf2ff": True, "loss_model": "kappa"}, "material": "PTFE"},
        {"name": "loss_fr4", "label": "FR-4 tanD 2e-2 through kappa",
         "kwargs": {"nf2ff": True, "loss_model": "kappa"}, "material": "FR-4"},
        {"name": "loss_fr4_none", "label": "FR-4 with the loss model switched off",
         "kwargs": {"nf2ff": True, "loss_model": "none"}, "material": "FR-4"},
    ],
}


def run_case(case: dict, workers_timeout: float, common: dict) -> dict:
    rundir = REPO_ROOT / "runs" / f"batch_{case['name']}"
    if rundir.exists():
        shutil.rmtree(rundir, ignore_errors=True)
    kwargs = {**common, **case["kwargs"]}
    solver = OpenEMSSolver(**kwargs)
    solver.prepare(project(case["name"], material=case.get("material", "PTFE")), rundir)

    log_path = rundir / "run.stdout.log"
    started = time.time()
    with log_path.open("wb") as log:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(rundir / "sim.py")],
            cwd=str(rundir),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=dict(os.environ),
        )
    return {"case": case, "rundir": rundir, "proc": proc, "t0": started, "log": log_path, "solver": solver}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run independent solver cases concurrently.")
    parser.add_argument("--preset", required=True, choices=sorted(PRESETS))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--end-criteria", type=float, default=1e-3)
    parser.add_argument("--max-ts", type=int, default=20000)
    parser.add_argument("--timeout-s", type=float, default=3600.0)
    args = parser.parse_args()

    if not os.environ.get("OPENEMS_ROOT"):
        print("ERROR: OPENEMS_ROOT is not set", file=sys.stderr)
        return 2

    common = {
        "nf2ff": False,          # far-field is not needed for a resonance A/B and costs time
        "end_criteria": args.end_criteria,
        "max_timesteps": args.max_ts,
    }
    cases = PRESETS[args.preset]
    print(f"preset {args.preset}: {len(cases)} cases, {args.workers} at a time")
    cavity = resonant_frequency_cavity(ER, H, WIDTH, LENGTH)
    tl = resonant_frequency(ER, H, WIDTH, LENGTH)
    print(f"reference: cavity {cavity/1e9:.4f} GHz | transmission-line {tl/1e9:.4f} GHz\n")

    running: list[dict] = []
    pending = list(cases)
    done: list[dict] = []
    while pending or running:
        while pending and len(running) < args.workers:
            case = pending.pop(0)
            print(f"  start {case['name']}: {case['label']}")
            running.append(run_case(case, args.timeout_s, common))
        time.sleep(2.0)
        for entry in list(running):
            code = entry["proc"].poll()
            deadline = time.time() - entry["t0"] > args.timeout_s
            if code is None and not deadline:
                continue
            if code is None:
                entry["proc"].kill()
                code = "timeout"
            entry["proc"].wait(timeout=30)
            elapsed = time.time() - entry["t0"]
            record = {
                "case": entry["case"]["name"],
                "label": entry["case"]["label"],
                "returncode": code,
                "runtime_s": round(elapsed, 1),
                "kwargs": {k: v for k, v in entry["solver"].__dict__.items() if isinstance(v, (int, float, bool, str))},
            }
            try:
                parsed = entry["solver"].parse_results(entry["rundir"])
                record.update(
                    {
                        "resonance_hz": parsed["resonance_hz"],
                        "delta_vs_cavity_pct": (parsed["resonance_hz"] / cavity - 1.0) * 100.0,
                        "worst_match_db": parsed["worst_match_db"],
                        "vswr": parsed["vswr_at_resonance"],
                        "converged": parsed.get("converged"),
                        "convergence_note": parsed.get("convergence_note"),
                    }
                )
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            done.append(record)
            running.remove(entry)
            print(f"  done  {record['case']}: rc={code} {record.get('resonance_hz', float('nan'))/1e9:.4f} GHz "
                  f"({record.get('delta_vs_cavity_pct', float('nan')):+.2f} %) converged={record.get('converged')}")

    summary = {
        "preset": args.preset,
        "settings": {"end_criteria": args.end_criteria, "max_timesteps": args.max_ts, "nf2ff": False, "port_refine": True},
        "reference_cavity_hz": cavity,
        "cases": done,
    }
    out = REPO_ROOT / "runs" / f"batch_{args.preset}_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    print("\n| case | resonance [GHz] | vs cavity | |S11| [dB] | VSWR | converged | runtime [s] |")
    print("|---|---|---|---|---|---|---|")
    for r in done:
        print("| {case} | {f} | {d} | {db} | {v} | {c} | {t} |".format(
            case=r["case"],
            f=f"{r['resonance_hz']/1e9:.4f}" if "resonance_hz" in r else "-",
            d=f"{r['delta_vs_cavity_pct']:+.2f} %" if "delta_vs_cavity_pct" in r else "-",
            db=f"{r['worst_match_db']:.2f}" if "worst_match_db" in r else "-",
            v=f"{r['vswr']:.3f}" if "vswr" in r else "-",
            c=r.get("converged"),
            t=r["runtime_s"],
        ))
    if len(done) == 2 and all(r.get("converged") for r in done) and all("resonance_hz" in r for r in done):
        delta = abs(done[0]["resonance_hz"] - done[1]["resonance_hz"]) / done[0]["resonance_hz"] * 100
        print(f"\nspread between the two settings: {delta:.2f} %")
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
