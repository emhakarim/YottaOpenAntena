"""Tests for the corporate-feed drawing plan (Phase 2 #5b, package half)."""

from __future__ import annotations

import types
import unittest

from openantenna.geometry.feed import (
    FeedSegment,
    plan_corporate_feed_geometry,
    segment_counts,
)
from openantenna.postproc.feed_network import synthesise_corporate_feed


def _width_of(impedance_ohm: float) -> float:
    """A deterministic stand-in for the microstrip width function."""
    return round(3.0e-3 * (50.0 / impedance_ohm), 9)


def _feed(n_elements: int = 4) -> object:
    return synthesise_corporate_feed(
        n_elements=n_elements,
        frequency_hz=2.45e9,
        epsilon_eff=1.9,
        z0_ohm=50.0,
    )


def _stub(n_elements: int, levels: int, section_length_m: float = 20.0e-3) -> object:
    """A feed-shaped object that never went through synthesis, for refusal paths."""
    return types.SimpleNamespace(
        n_elements=n_elements,
        levels=levels,
        z0_ohm=50.0,
        stage_impedance_ohm=70.7,
        section_length_m=section_length_m,
        design_frequency_hz=2.45e9,
        epsilon_eff=1.9,
    )


class TestCorporateFeedPlan(unittest.TestCase):
    def test_counts_follow_the_binary_tree(self):
        """Per level: one transformer per parent, two arms per parent."""
        plan = plan_corporate_feed_geometry(_feed(4), 60.0e-3, _width_of)
        counts = segment_counts(plan)
        self.assertEqual(counts["trunk"], 1)
        self.assertEqual(counts["transformer"], 3)  # 2**2 - 1 = one per parent, all levels
        self.assertEqual(counts["arm"], 6)  # 2**1 + 2**2: arms exist on every level

    def test_a_non_power_of_two_feed_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            plan_corporate_feed_geometry(_stub(6, 2), 60.0e-3, _width_of)
        self.assertIn("power-of-two", str(caught.exception))

    def test_tree_is_symmetric_about_x_zero(self):
        plan = plan_corporate_feed_geometry(_feed(4), 60.0e-3, _width_of)
        arms = [s for s in plan.segments if s.role == "arm"]
        self.assertEqual(len(arms) % 2, 0)
        for arm in arms:
            mirrored = FeedSegment(
                -arm.x0, arm.y0, -arm.x1, arm.y1, arm.width_m, arm.level, arm.role
            )
            self.assertIn(mirrored, arms, f"no mirror for {arm}")

    def test_transformers_keep_the_quarter_wave_length(self):
        feed = _feed(8)
        plan = plan_corporate_feed_geometry(feed, 70.0e-3, _width_of)
        for segment in plan.segments:
            if segment.role == "transformer":
                length = abs(segment.y1 - segment.y0)
                self.assertAlmostEqual(length, feed.section_length_m, places=12)

    def test_widths_come_from_the_caller_width_function(self):
        feed = _feed(4)
        plan = plan_corporate_feed_geometry(feed, 60.0e-3, _width_of)
        for segment in plan.segments:
            expected = _width_of(
                feed.stage_impedance_ohm if segment.role == "transformer" else feed.z0_ohm
            )
            self.assertAlmostEqual(segment.width_m, expected, places=12)

    def test_arm_ends_reach_the_element_pitches(self):
        pitch = 60.0e-3
        levels = 2
        plan = plan_corporate_feed_geometry(_feed(4), pitch, _width_of)
        # only the outermost level's arm ends are the element feeds; parent centres share
        # the same depth and must not be mistaken for leaves
        tips = sorted(
            segment.x1
            for segment in plan.segments
            if segment.role == "arm" and segment.level == levels
        )
        self.assertEqual(
            [round(x / pitch, 9) for x in tips],
            [-1.5, -0.5, 0.5, 1.5],
            "element feeds must sit on the pitches, centred on x=0",
        )

    def test_bad_geometry_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            plan_corporate_feed_geometry(_feed(4), -1.0, _width_of)
        with self.assertRaises(ValueError):
            plan_corporate_feed_geometry(
                _stub(4, 2, section_length_m=0.0), 60.0e-3, _width_of
            )

    def test_rectangles_cover_every_segment_with_its_width(self):
        plan = plan_corporate_feed_geometry(_feed(4), 60.0e-3, _width_of)
        rects = plan.rectangles()
        self.assertEqual(len(rects), len(plan.segments))
        for segment, rect in zip(plan.segments, rects):
            if segment.x0 == segment.x1:  # vertical
                self.assertAlmostEqual(rect[2] - rect[0], segment.width_m, places=12)
                self.assertAlmostEqual(
                    rect[3] - rect[1], abs(segment.y1 - segment.y0), places=12
                )
            else:  # horizontal
                self.assertAlmostEqual(rect[3] - rect[1], segment.width_m, places=12)
                self.assertAlmostEqual(
                    rect[2] - rect[0], abs(segment.x1 - segment.x0), places=12
                )
            self.assertEqual(rect[5], segment.role)

    def test_bounds_contain_every_rect(self):
        plan = plan_corporate_feed_geometry(_feed(4), 60.0e-3, _width_of)
        x_min, y_min, x_max, y_max = plan.bounds()
        for x0, y0, x1, y1, _level, _role in plan.rectangles():
            self.assertLessEqual(x_min, x0)
            self.assertLessEqual(y_min, y0)
            self.assertGreaterEqual(x_max, x1)
            self.assertGreaterEqual(y_max, y1)
        self.assertLessEqual(y_max, 0.0, "the tree grows downward from the input at y=0")


if __name__ == "__main__":
    unittest.main()
