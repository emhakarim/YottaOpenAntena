"""Example 3 - plan the two-layer 4-by-4 tree and check it does not overlap itself.

Run:  python examples/03_feed_plan_2d.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from openantenna.geometry.feed2d import plan_h_tree_2d
from openantenna.geometry.patch import microstrip_width_for_impedance
from openantenna.postproc.feed_network import synthesise_corporate_feed

ROWS = COLS = 4
PITCH_M = 60.0e-3
FREQUENCY_HZ = 2.45e9
EPSILON_R = 3.4
HEIGHT_M = 1.6e-3


def main() -> int:
    epsilon_eff = (EPSILON_R + 1.0) / 2.0
    section = synthesise_corporate_feed(
        n_elements=COLS, frequency_hz=FREQUENCY_HZ, epsilon_eff=epsilon_eff
    )

    def width_of(impedance_ohm: float) -> float:
        return microstrip_width_for_impedance(EPSILON_R, HEIGHT_M, impedance_ohm)

    plan = plan_h_tree_2d(
        rows=ROWS,
        cols=COLS,
        pitch_x_m=PITCH_M,
        pitch_y_m=PITCH_M,
        width_of=width_of,
        section_length_m=section.section_length_m,
        epsilon_eff=epsilon_eff,
        frequency_hz=FREQUENCY_HZ,
        leaf_offset_y_m=-1.6e-3,
    )
    print(f"grid           : {ROWS} x {COLS}, pitch {PITCH_M * 1e3:.0f} mm")
    print(f"layers         : {', '.join(plan.layers_present())}")
    for layer in plan.layers_present():
        print(
            "  %-12s : %3d rectangles, %d overlapping"
            % (layer, len(plan.rectangles(layer)), len(plan.collisions(layer)))
        )
    print(f"channel        : y = {plan.channel_y_m * 1e3:.3f} mm (routing runs below the array)")
    print(
        "input (port)   : (%.3f, %.3f) mm"
        % (plan.input_point[0] * 1e3, plan.input_point[1] * 1e3)
    )
    print(f"leaves         : {len(plan.leaves)} element feed points")
    if any(plan.collisions(layer) for layer in plan.layers_present()):
        print("WARNING: overlapping metal - do not build this layout")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
