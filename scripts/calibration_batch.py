"""Calibration batch for the openEMS patch model.

Runs four comparison cases and one external anchor, then writes a summary:

1. loss differential - the same geometry with the dielectric-loss model ON,
   to be compared against the already-recorded lossless run (runs/patch_ptfe_v4);
2. feed study - three inset depths (near-edge, half of the synthesis estimate,
   1.5x the estimate) to see whether feed loading moves the resonance;
3. external anchor - the openEMS-shipped ``Simple_Patch_Antenna.py`` tutorial,
   patched only to dump its S11 to CSV, to check whether an independent model of
   the same class of antenna lands where ours does.

Nothing here is called "calibrated" automatically; the summary only records what
was measured.
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
RUNS = ROOT / "runs"
LOG_PATH = RUNS / "calibration_batch.log"
WRAPPER = ROOT / "scripts" / "run_with_openems.py"
PY = sys.executable


def log(message: str) -> None:
    print(message, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def base_project(name: str, inset_m=None) -> tuple[Project, object]:
    design = synthesize_patch(F0, ER, H)
    project = Project(
        name=name,
        substrate=SubstrateStackup.single("PTFE", H),
        patch=PatchGeometry(
            width_m=design.width_m,
            length_m=design.length_m,
            feed_mode="inset",
            feed_inset_m=inset_m,
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.0e9, stop_hz=3.0e9, points=101),
    )
    return project, design


def run_case(name: str, project: Project, solver: OpenEMSSolver, rundir: Path) -> dict:
    rundir.mkdir(parents=True, exist_ok=True)
    solver.prepare(project, rundir)
    env = dict(os.environ)
    env.setdefault("OPENEMS_ROOT", os.environ.get("OPENEMS_ROOT", ""))
    proc = subprocess.run(
        [PY, str(WRAPPER), str(rundir / "sim.py")],
        cwd=str(rundir),
        capture_output=True,
        text=True,
        env=env,
    )
    (rundir / "run.stdout.log").write_text(
        (proc.stdout or "") + (proc.stderr or ""), encoding="utf-8"
    )
    record: dict = {"case": name, "returncode": proc.returncode}
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
    except Exception as exc:  # parsing failure is itself a result
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def patch_tutorial() -> Path:
    """Copy the shipped tutorial and append a CSV dump of its S11."""
    openems_root = os.environ.get("OPENEMS_ROOT", "")
    if not openems_root:
        raise RuntimeError("OPENEMS_ROOT must point at the openEMS installation")
    source = Path(openems_root) / "python" / "Tutorials" / "Simple_Patch_Antenna.py"
    target_dir = RUNS / "tutorial_anchor"
    target_dir.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    dump = (
        "\nimport csv as _csv\n"
        'with open(os.path.join(Sim_Path, "s11_tutorial.csv"), "w", newline="") as _fh:\n'
        '    _w = _csv.writer(_fh)\n'
        '    _w.writerow(["freq_hz", "s11_re", "s11_im"])\n'
        "    for _f, _s in zip(f, s11):\n"
        "        _w.writerow([repr(float(_f)), repr(float(_s.real)), repr(float(_s.imag))])\n"
        'print("WROTE S11 CSV TO", Sim_Path)\n'
    )
    marker = "s11_dB = 20.0*np.log10(np.abs(s11))"
    if marker not in text:
        raise RuntimeError("tutorial layout changed; CSV patch marker not found")
    text = text.replace(marker, marker + "\n" + dump, 1)
    target = target_dir / "Simple_Patch_Antenna_patched.py"
    target.write_text(text, encoding="utf-8")
    return target


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")
    log("=== calibration batch start ===")

    design = synthesize_patch(F0, ER, H)
    log(
        "synthesis: W=%.3f mm L=%.3f mm eps_eff=%.4f dL=%.4f mm inset=%.3f mm"
        % (
            design.width_m * 1e3,
            design.length_m * 1e3,
            design.epsilon_eff,
            design.delta_l_m * 1e3,
            design.inset_depth_m * 1e3,
        )
    )

    summary: dict = {
        "reference": {
            "note": "lossless, 15 cells/lambda, 8 substrate cells (already recorded)",
            "resonance_hz": 2.26e9,
            "worst_match_db": -13.32,
            "fractional_bandwidth": 0.009952640387972899,
        },
        "cases": [],
    }

    cases = [
        (
            "loss_kappa",
            OpenEMSSolver(loss_model="kappa"),
            base_project("calib_loss_kappa")[0],
        ),
        ("feed_inset_edge", OpenEMSSolver(), base_project("calib_feed_edge", 1e-6)[0]),
        (
            "feed_inset_half",
            OpenEMSSolver(),
            base_project("calib_feed_half", 0.5 * design.inset_depth_m)[0],
        ),
        (
            "feed_inset_1p5x",
            OpenEMSSolver(),
            base_project("calib_feed_1p5x", 1.5 * design.inset_depth_m)[0],
        ),
    ]

    for name, solver, project in cases:
        log(f"--- case {name} ---")
        record = run_case(name, project, solver, RUNS / f"calib_{name}")
        summary["cases"].append(record)
        log("    " + json.dumps(record, default=str))

    log("--- external anchor: shipped tutorial ---")
    try:
        tutorial = patch_tutorial()
        env = dict(os.environ)
        env.setdefault("OPENEMS_ROOT", os.environ.get("OPENEMS_ROOT", ""))
        proc = subprocess.run(
            [PY, str(WRAPPER), str(tutorial)],
            cwd=str(tutorial.parent),
            capture_output=True,
            text=True,
            env=env,
        )
        (tutorial.parent / "run.stdout.log").write_text(
            (proc.stdout or "") + (proc.stderr or ""), encoding="utf-8"
        )
        csv_path = None
        for candidate in Path(os.environ.get("TEMP", r"C:\Windows\Temp")).glob("Simp_Patch/s11_tutorial.csv"):
            csv_path = candidate
        anchor: dict = {
            "case": "tutorial_anchor",
            "returncode": proc.returncode,
            "design_note": "openEMS-shipped 2.4 GHz patch tutorial, model unchanged",
        }
        if csv_path and csv_path.exists():
            from openantenna.postproc.sparams import S11Trace

            trace = S11Trace.from_csv(csv_path)
            index = trace.worst_match_index()
            anchor.update(
                {
                    "resonance_hz": trace.frequencies_hz[index],
                    "worst_match_db": trace.db()[index],
                    "vswr": trace.vswr()[index],
                    "fractional_bandwidth": trace.fractional_bandwidth(-10.0),
                    "csv": str(csv_path),
                }
            )
        else:
            anchor["error"] = "tutorial S11 CSV not found"
        summary["cases"].append(anchor)
        log("    " + json.dumps(anchor, default=str))
    except Exception as exc:
        log(f"    anchor failed: {type(exc).__name__}: {exc}")
        summary["cases"].append({"case": "tutorial_anchor", "error": str(exc)})

    (RUNS / "calibration_summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    log("=== calibration batch done, summary at runs/calibration_summary.json ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
