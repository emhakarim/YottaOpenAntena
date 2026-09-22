"""A/B for the coplanar inset feed (B2 / Y-19): probe vs printed line.

One variable changes - how the feed is realised - with geometry, substrate, mesh settings,
boundary, excitation and stop criteria held identical.

    python scripts/b2_coplanar_ab_test.py                 # write both decks, run nothing
    python scripts/b2_coplanar_ab_test.py --run           # prepare, run, summarise
    python scripts/b2_coplanar_ab_test.py --run --end-criteria 1e-3

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
    # arm name -> line width in metres (None keeps the legacy vertical probe)
    "probe": None,
    "line": "synthesised",
}


def build_project(arm: str, end_criteria: float):
    from openantenna.geometry.patch import synthesize_patch
    from openantenna.model.project import (
        ArrayConfig,
        FrequencySweep,
        PatchGeometry,
        Project,
        SubstrateStackup,
    )

    design = synthesize_patch(FREQUENCY_HZ, 2.1, HEIGHT_M, "inset")
    width = design.feed_line_width_m if ARMS[arm] == "synthesised" else None
    return Project(
        name=f"b2_{arm}",
        substrate=SubstrateStackup.single(MATERIAL, HEIGHT_M),
        patch=PatchGeometry(
            width_m=design.width_m,
            length_m=design.length_m,
            feed_mode="inset",
            feed_inset_m=design.inset_depth_m,
            feed_line_width_m=width,
        ),
        array=ArrayConfig(nx=1, ny=1, spacing_x_lambda0=0.5, spacing_y_lambda0=0.5),
        sweep=FrequencySweep.fractional(FREQUENCY_HZ, 0.15, points=201),
    ), design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(Path("runs") / "b2_coplanar"))
    parser.add_argument("--run", action="store_true", help="run the decks instead of only writing them")
    parser.add_argument("--end-criteria", type=float, default=1e-3)
    args = parser.parse_args(argv)

    from openantenna.solvers.openems import OpenEMSSolver

    solver = OpenEMSSolver(end_criteria=args.end_criteria)
    status = solver.available()
    print(f"solver available: {status.available} - {status.detail}")

    prepared = {}
    for arm in ARMS:
        project, design = build_project(arm, args.end_criteria)
        rundir = Path(args.out) / arm
        path = solver.prepare(project, rundir)
        prepared[arm] = path
        # print the value the *project* carries, not the synthesis: the probe arm
        # deliberately has none, and a log that says otherwise is a lie.
        carried = project.patch.feed_line_width_m
        label = "(none - vertical probe)" if carried is None else f"{carried * 1e3:.3f} mm"
        print(f"  {arm:5}: feed_line_width={label}, inset={design.inset_depth_m * 1e3:.3f} mm -> {path}")

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
