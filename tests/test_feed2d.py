"""Tests for the two-layer corporate tree (Phase 2 #5b, 2-D half)."""

from __future__ import annotations

import unittest

from openantenna.geometry.feed2d import plan_h_tree_2d


def _width_of(impedance_ohm: float) -> float:
    return round(3.0e-3 * (50.0 / impedance_ohm), 9)


def _plan(rows: int, cols: int, pitch: float = 90.0e-3, offset: float = -20.0e-3):
    return plan_h_tree_2d(
        rows=rows,
        cols=cols,
        pitch_x_m=pitch,
        pitch_y_m=pitch,
        width_of=_width_of,
        section_length_m=22.19e-3,
        epsilon_eff=1.95,
        frequency_hz=2.45e9,
        leaf_offset_y_m=offset,
    )


class TestTwoLayerTree(unittest.TestCase):
    def test_the_4x4_case_is_planned_on_three_layers(self):
        plan = _plan(4, 4)
        self.assertEqual(len(plan.leaves), 16)
        self.assertEqual(plan.layers_present(), ("feed", "patch", "via"))

    def test_no_layer_has_rectangles_lying_on_each_other(self):
        for rows, cols in ((2, 2), (4, 4), (4, 2)):
            with self.subTest(rows=rows, cols=cols):
                plan = _plan(rows, cols)
                for layer in plan.layers_present():
                    self.assertEqual(
                        plan.collisions(layer), (), f"{rows}x{cols}: {layer} layer overlaps"
                    )

    def test_leaves_are_the_element_grid_on_the_feed_line(self):
        plan = _plan(4, 4, pitch=90.0e-3)
        expected = {
            (round((col - 1.5) * 90.0e-3, 9), round((row - 1.5) * 90.0e-3 - 20.0e-3, 9))
            for row in range(4)
            for col in range(4)
        }
        self.assertEqual({(round(x, 9), round(y, 9)) for x, y in plan.leaves}, expected)

    def test_each_row_tree_fits_inside_its_column_band(self):
        plan = _plan(4, 4, pitch=60.0e-3)
        self.assertLess(plan.depth_row_m, 60.0e-3)
        patch_rects = plan.rectangles("patch")
        pitch = 60.0e-3
        for rect in patch_rects:
            band = round((rect[0] + (3) * pitch / 2.0) // pitch)
            self.assertGreaterEqual(band, -1, "row tree metal must stay inside the array width")

    def test_the_column_tree_sits_below_the_array(self):
        plan = _plan(4, 4)
        self.assertLess(plan.channel_y_m, min(y for _x, y in plan.leaves))
        self.assertLess(plan.input_point[1], plan.channel_y_m)

    def test_a_pitch_too_short_for_the_row_tree_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            _plan(4, 4, pitch=30.0e-3)
        self.assertIn("column pitch", str(caught.exception))

    def test_non_power_of_two_counts_are_refused(self):
        with self.assertRaises(ValueError):
            _plan(4, 3)

    def test_bad_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            _plan(0, 4)
        with self.assertRaises(ValueError):
            _plan(1, 1)
        with self.assertRaises(ValueError):
            _plan(2, 2, pitch=-1.0)


if __name__ == "__main__":
    unittest.main()
