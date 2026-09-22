"""Synthesis-to-tuning loop for the rectangular patch.

Why this exists: the analytic synthesis (transmission-line model) lands several
percent below the target frequency on this geometry, and the calibration batch
showed that neither mesh refinement nor feed loading explains it.  Instead of
hiding that offset, this script closes the loop the way an engineer would:

1. synthesise the geometry analytically;
2. simulate it;
3. measure the actual resonance;
4. rescale the patch length by ``f_measured / f_target`` (first order, because
   the resonance scales roughly as 1/L) and keep the feed at the same relative
   inset;
5. repeat until the offset is inside tolerance or the iteration budget runs out.

Every iteration is recorded, so the residual offset and the convergence stay
visible instead of being silently absorbed into a "magic" dimension.

Usage:
    python scripts/auto_tune.py [target_ghz] [tolerance_percent] [max_iterations]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import resonant_frequency_cavity, synthesize_patch
from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

MATERIAL = "PTFE"
ER = 2.1
H = 1.6e-3
SWEEP_FRACTION = 0.30  # wide enough to contain the shifted resonance


def build_project(name: str, length_m: float, inset_m: float, width_m: float, f_target: float) -> Project:
    return Project(
        name=name,
        substrate=SubstrateStackup.single(MATERIAL, H),
        patch=PatchGeometry(
            width_m=width_m,
            length_m=length_m,
            feed_mode="inset",
            feed_inset_m=inset_m,
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=f_target * (1 - SWEEP_FRACTION),
                             stop_hz=f_target * (1 + SWEEP_FRACTION),
                             points=121),
    )


def run_once(solver: OpenEMSSolver, project: Project, rundir: Path) -> dict:
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
    if proc.returncode != 0:
        raise RuntimeError(f"solver failed with code {proc.returncode}")
    return solver.parse_results(rundir)


def main() -> int:
    f_target = (float(sys.argv[1]) if len(sys.argv) > 1 else 2.45) * 1e9
    tolerance = (float(sys.argv[2]) if len(sys.argv) > 2 else 0.1) / 100.0
    max_iterations = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    # Optional starting point, so a loop can continue from an earlier converged
    # geometry instead of restarting from the analytic synthesis.
    start_length_m = (float(sys.argv[4]) / 1e3) if len(sys.argv) > 4 else None
    inset_ratio_override = float(sys.argv[5]) if len(sys.argv) > 5 else None

    design = synthesize_patch(f_target, ER, H)
    width = design.width_m
    length = design.length_m if start_length_m is None else start_length_m
    inset_ratio = (
        design.inset_depth_m / design.length_m
        if inset_ratio_override is None
        else inset_ratio_override
    )
    solver = OpenEMSSolver(loss_model="kappa")

    history: list[dict] = []
    print(f"target {f_target/1e9:.4f} GHz | tolerance {tolerance*100:.2f} % | "
          f"max {max_iterations} iterations", flush=True)

    for iteration in range(1, max_iterations + 1):
        inset = inset_ratio * length
        project = build_project(f"tune_it{iteration}", length, inset, width, f_target)
        rundir = ROOT / "runs" / f"tune_it{iteration}"
        print(f"--- iteration {iteration}: L = {length*1e3:.3f} mm, inset = {inset*1e3:.3f} mm",
              flush=True)
        parsed = run_once(solver, project, rundir)
        # The refined (sub-grid) resonance is the quantity a 0.1 % target needs; the
        # raw grid minimum is only good to one sweep step.
        measured = parsed.get("resonance_refined_hz") or parsed["resonance_hz"]
        offset = (measured - f_target) / f_target
        # N-04: the tuning loop corrects against the FDTD result, which sits below
        # both analytic models.  Printing the cavity prediction each iteration makes
        # that divergence visible instead of hidden, and records which model the
        # tuning used as its authority.
        cavity = resonant_frequency_cavity(ER, H, width, length)
        record = {
            "iteration": iteration,
            "length_m": length,
            "inset_m": inset,
            "resonance_hz": measured,
            "resonance_grid_min_hz": parsed["resonance_hz"],
            "grid_step_hz": parsed.get("resonance_grid_step_hz"),
            "fit_curvature_db_per_hz2": parsed.get("resonance_curvature_db_per_hz2"),
            "worst_match_db": parsed["worst_match_db"],
            "vswr": parsed["vswr_at_resonance"],
            "offset_percent": offset * 100.0,
            "converged": parsed.get("converged"),
            "convergence_note": parsed.get("convergence_note"),
            "cavity_prediction_hz": cavity,
            "cavity_gap_percent": (measured - cavity) / cavity * 100.0,
        }
        history.append(record)
        print("    " + json.dumps(record, default=str), flush=True)

        if abs(offset) <= tolerance:
            print(f"converged after {iteration} iteration(s)", flush=True)
            break
        # f ~ 1/L, so scale the length by the ratio of measured to target.
        length = length * (measured / f_target)

    summary = {
        "target_hz": f_target,
        "tolerance": tolerance,
        "material": MATERIAL,
        "epsilon_r": ER,
        "substrate_thickness_m": H,
        "history": history,
        "converged": bool(history and abs(history[-1]["offset_percent"]) / 100.0 <= tolerance),
        "note": (
            "Each iteration is a full FDTD run. The tuning loop corrects the synthesis "
            "offset empirically against the FDTD result; it does not validate the "
            "absolute accuracy of the model, and it must not be published as design "
            "authority until the ground-plane (N-01) and convergence (N-02) effects "
            "are resolved. cavity_prediction_hz shows where the independent cavity "
            "model lands, so the gap between models stays visible."
        ),
    }
    out = ROOT / "runs" / "auto_tune_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"summary written to {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
