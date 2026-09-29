"""B2 script options: the overlap-sweep knob must move exactly one value (the inset).

Structural checks only - no solver, no engine.  The deck-level contract (notch, line, port)
lives in the existing deck tests; this file guards the new ``--arm`` / ``--inset-delta-mm``
surface added for the optimization campaign.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "b2_coplanar_ab_test", ROOT / "scripts" / "b2_coplanar_ab_test.py")
b2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b2)


class TestInsetOverride(unittest.TestCase):
    def test_line_arm_carries_the_synthesised_inset_by_default(self) -> None:
        project, design = b2.build_project("line", 1e-4)
        self.assertAlmostEqual(project.patch.feed_inset_m, design.inset_depth_m, places=12)

    def test_delta_shifts_only_the_inset(self) -> None:
        base, _ = b2.build_project("line", 1e-4)
        shifted, _ = b2.build_project("line", 1e-4, inset_delta_m=0.5e-3)
        self.assertAlmostEqual(shifted.patch.feed_inset_m, base.patch.feed_inset_m + 0.5e-3, places=12)
        for field in ("width_m", "length_m", "feed_line_width_m"):
            self.assertEqual(getattr(shifted.patch, field), getattr(base.patch, field))

    def test_zero_delta_is_the_identity(self) -> None:
        base, _ = b2.build_project("line", 1e-4)
        same, _ = b2.build_project("line", 1e-4, inset_delta_m=0.0)
        self.assertEqual(base.patch.feed_inset_m, same.patch.feed_inset_m)

    def test_negative_inset_is_refused(self) -> None:
        design_inset = b2.build_project("line", 1e-4)[1].inset_depth_m
        with self.assertRaisesRegex(ValueError, "outside"):
            b2.build_project("line", 1e-4, inset_delta_m=-(design_inset + 1e-3))

    def test_inset_beyond_the_patch_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside"):
            b2.build_project("line", 1e-4, inset_delta_m=1.0)  # +1 m is absurd by design


if __name__ == "__main__":
    unittest.main()
