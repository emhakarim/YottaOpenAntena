"""A/B for the coplanar inset feed (B2 / Y-19): probe vs printed line.

One variable changes - how the feed is realised - with geometry, substrate, mesh settings,
boundary, excitation and stop criteria held identical.

    python scripts/b2_coplanar_ab_test.py                 # write both decks, run nothing
    python scripts/b2_coplanar_ab_test.py --run           # prepare, run, summarise
    python scripts/b2_coplanar_ab_test.py --run --end-criteria 1e-3
    python scripts/b2_coplanar_ab_test.py --arm line --inset-delta-mm -0.5 --run   # sweep point
    python scripts/b2_coplanar_ab_test.py --arm line --feed-x-offset-mm 5 --run   # 2-D feed check

The structural side is already verified by tests (the deck contains the notch, the line and
a port at the line end, and the mesh is refined across the line).  What is **not** claimed
until this runs: whether the coplanar feed moves the resonance, and by how much.  Read
``docs/experiment-coplanar-inset.md`` for the decision thresholds, which are fixed before
the numbers are seen - the project's rule.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FREQUENCY_HZ = 2.45e9
MATERIAL = "PTFE"
HEIGHT_M = 1.6e-3

ARMS = {
    # arm name -> line width: 0.0 means "no printed line" (the explicit probe state; None
    # would mean "let the synthesis decide", which is what made both arms identical once).
    "probe": 0.0,
    "line": "synthesised",
}


def build_project(
    arm: str,
    end_criteria: float,
    inset_delta_m: float = 0.0,
    feed_x_offset_m: float = 0.0,
):
    from openantenna.geometry.patch import synthesize_patch
    from openantenna.model.project import (
        ArrayConfig,
        FrequencySweep,
        PatchGeometry,
        Project,
        SubstrateStackup,
    )

    design = synthesize_patch(FREQUENCY_HZ, 2.1, HEIGHT_M, "inset")
    width = design.feed_line_width_m if ARMS[arm] == "synthesised" else ARMS[arm]
    inset_m = design.inset_depth_m + inset_delta_m
    if not 0.0 <= inset_m <= design.length_m:
        raise ValueError(
            "inset %.3f mm is outside [0, patch length %.3f mm] - the overlap must stay on the "
            "patch" % (inset_m * 1e3, design.length_m * 1e3)
        )
    return Project(
        name=f"b2_{arm}",
        substrate=SubstrateStackup.single(MATERIAL, HEIGHT_M),
        patch=PatchGeometry(
            width_m=design.width_m,
            length_m=design.length_m,
            feed_mode="inset",
            feed_inset_m=inset_m,
            feed_line_width_m=width,
            feed_x_offset_m=feed_x_offset_m or None,
        ),
        array=ArrayConfig(nx=1, ny=1, spacing_x_lambda0=0.5, spacing_y_lambda0=0.5),
        sweep=FrequencySweep.fractional(FREQUENCY_HZ, 0.15, points=201),
    ), design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(Path("runs") / "b2_coplanar"))
    parser.add_argument("--run", action="store_true", help="run the decks instead of only writing them")
    parser.add_argument("--arm", choices=("probe", "line", "both"), default="both",
                        help="which feed arm(s) to write/run; the overlap sweep runs the line arm only")
    parser.add_argument("--inset-delta-mm", type=float, default=0.0,
                        help="shift the synthesised inset depth by this many millimetres "
                             "(overlap sweep; the only value this knob moves is the inset)")
    parser.add_argument("--feed-x-offset-mm", type=float, default=0.0,
                        help="lateral feed offset across the patch width (validation of the "
                             "2-D feed; 0 = centreline, the historical model)")
    parser.add_argument("--end-criteria", type=float, default=1e-3)
    parser.add_argument("--max-ts", type=int, default=400000,
                        help="timestep cap carried into the deck (MAX_TS); Route B needs two caps")
    args = parser.parse_args(argv)

    from openantenna.solvers.openems import OpenEMSSolver

    solver = OpenEMSSolver(end_criteria=args.end_criteria, max_timesteps=args.max_ts)
    status = solver.available()
    print(f"solver available: {status.available} - {status.detail}")

    arms = list(ARMS) if args.arm == "both" else [args.arm]
    inset_delta_m = args.inset_delta_mm / 1e3
    feed_x_offset_m = args.feed_x_offset_mm / 1e3
    prepared = {}
    for arm in arms:
        try:
            project, design = build_project(
                arm, args.end_criteria, inset_delta_m, feed_x_offset_m
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        rundir = Path(args.out) / arm
        path = solver.prepare(project, rundir)
        prepared[arm] = path
        # print the value the *project* carries, not the synthesis: the probe arm
        # deliberately has none, and a log that says otherwise is a lie.
        carried = project.patch.feed_line_width_m
        label = "(none - vertical probe)" if carried is None else f"{carried * 1e3:.3f} mm"
        offset_note = (
            ""
            if not project.patch.feed_x_offset_m
            else f", feed_x_offset={project.patch.feed_x_offset_m * 1e3:+.2f} mm"
        )
        print(f"  {arm:5}: feed_line_width={label}, "
              f"inset={project.patch.feed_inset_m * 1e3:.3f} mm{offset_note} -> {path}")

    if not args.run:
        print("\nwritten only.  On a machine with openEMS:")
        for arm, path in prepared.items():
            print(f"  python -u {path / solver.script_name}")
        return 0

    if not status.available:
        print("cannot run: the solver is not available here", file=sys.stderr)
        return 1

    for arm, path in prepared.items():
        print(f"\nrunning {arm} ...")
        run = solver.run(path)
        if run.status != "ok":
            print(f"  {arm} FAILED: {run.log[-600:]}", file=sys.stderr)
            return 1
        parsed = solver.parse_results(path)
        print(
            f"  {arm:5}: resonance {parsed['resonance_hz'] / 1e9:.4f} GHz, "
            f"|S11| {parsed['worst_match_db']:.2f} dB, VSWR {parsed['vswr_at_resonance']:.3f}, "
            f"converged={parsed.get('converged')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
