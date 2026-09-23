"""Example 2 - plan a 1-by-8 corporate feed and show what the deck builder would draw.

Run:  python examples/02_feed_plan_1d.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from openantenna.geometry.feed import plan_corporate_feed_geometry
from openantenna.geometry.patch import microstrip_width_for_impedance
from openantenna.postproc.feed_network import synthesise_corporate_feed

N_ELEMENTS = 8
PITCH_M = 60.0e-3
FREQUENCY_HZ = 2.45e9
EPSILON_R = 3.4
HEIGHT_M = 1.6e-3


def main() -> int:
    epsilon_eff = (EPSILON_R + 1.0) / 2.0
    feed = synthesise_corporate_feed(
        n_elements=N_ELEMENTS, frequency_hz=FREQUENCY_HZ, epsilon_eff=epsilon_eff
    )

    def width_of(impedance_ohm: float) -> float:
        return microstrip_width_for_impedance(EPSILON_R, HEIGHT_M, impedance_ohm)

    plan = plan_corporate_feed_geometry(feed, PITCH_M, width_of)
    print(f"elements       : {N_ELEMENTS} in one row, pitch {PITCH_M * 1e3:.0f} mm")
    print(f"levels         : {feed.levels}, section {feed.section_length_m * 1e3:.3f} mm (lambda/4)")
    print(f"segments       : {len(plan.segments)}")
    print(f"rectangles     : {len(plan.rectangles())}")
    bounds = plan.bounds()
    print(
        "bounds         : x %.2f..%.2f mm, y %.2f..%.2f mm"
        % (bounds[0] * 1e3, bounds[2] * 1e3, bounds[1] * 1e3, bounds[3] * 1e3)
    )
    print("NOTE: drawing geometry only; segment lengths follow the element grid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
