"""Tests for array layout and array-factor post-processing."""

from __future__ import annotations

import math
import unittest

from openantenna.geometry import array
from openantenna.geometry.patch import synthesize_patch
from openantenna.model.project import ArrayConfig

C0 = 299792458.0
F0 = 2.45e9
LAMBDA0 = C0 / F0


class TestElementPositions(unittest.TestCase):
    def test_two_by_two_grid_is_centred(self):
        points = array.element_positions(2, 2, 1.0, 1.0)
        self.assertEqual(len(points), 4)
        self.assertAlmostEqual(points[0][0], -0.5)
        self.assertAlmostEqual(points[0][1], -0.5)
        self.assertAlmostEqual(points[-1][0], 0.5)
        self.assertAlmostEqual(points[-1][1], 0.5)

    def test_uncentred_grid_starts_at_the_origin(self):
        points = array.element_positions(2, 1, 1.0, 1.0, centered=False)
        self.assertAlmostEqual(points[0][0], 0.0)

    def test_invalid_sizes_are_rejected(self):
        with self.assertRaises(ValueError):
            array.element_positions(0, 2, 1.0, 1.0)
        with self.assertRaises(ValueError):
            array.element_positions(2, 2, 0.0, 1.0)


class TestLayout(unittest.TestCase):
    def setUp(self):
        self.design = synthesize_patch(F0, 2.1, 1.6e-3)

    def test_four_by_four_at_half_wavelength(self):
        cfg = ArrayConfig(nx=4, ny=4, spacing_x_lambda0=0.5, spacing_y_lambda0=0.5)
        layout = array.build_array_layout(cfg, F0, self.design)
        self.assertEqual(layout.element_count, 16)
        self.assertEqual(len(layout.positions_m), 16)
        self.assertAlmostEqual(layout.dx_m, 0.5 * LAMBDA0, places=12)
        self.assertAlmostEqual(layout.grid_size_x_m, 3 * 0.5 * LAMBDA0, places=12)
        self.assertAlmostEqual(layout.element_width_m, self.design.width_m)

    def test_large_array_warns_about_unit_cell(self):
        cfg = ArrayConfig(nx=4, ny=4)
        layout = array.build_array_layout(cfg, F0, self.design)
        self.assertTrue(any("unit-cell" in w for w in layout.warnings))

    def test_over_half_wavelength_spacing_warns_about_grating_lobes(self):
        cfg = ArrayConfig(nx=4, ny=4, spacing_x_lambda0=0.7, spacing_y_lambda0=0.7)
        layout = array.build_array_layout(cfg, F0, self.design)
        self.assertTrue(any("grating" in w.lower() for w in layout.warnings))

    def test_half_wavelength_spacing_has_no_grating_warning(self):
        cfg = ArrayConfig(nx=2, ny=2, spacing_x_lambda0=0.5, spacing_y_lambda0=0.5)
        layout = array.build_array_layout(cfg, F0, self.design)
        self.assertFalse(any("grating" in w.lower() for w in layout.warnings))

    def test_element_length_over_y_pitch_is_flagged(self):
        """Y-07: the old overlap check compared only the element width."""
        cfg = ArrayConfig(nx=4, ny=4, spacing_x_lambda0=0.2, spacing_y_lambda0=0.2)
        layout = array.build_array_layout(cfg, F0, self.design)
        self.assertTrue(any("along y" in w for w in layout.warnings))
        self.assertTrue(any("along x" in w for w in layout.warnings))

    def test_roomy_array_has_no_overlap_warning(self):
        cfg = ArrayConfig(nx=4, ny=4, spacing_x_lambda0=0.5, spacing_y_lambda0=0.5)
        layout = array.build_array_layout(cfg, F0, self.design)
        self.assertFalse(any("overlap" in w for w in layout.warnings))

    def test_summary_reports_the_aperture(self):
        layout = array.build_array_layout(ArrayConfig(nx=4, ny=4), F0, self.design)
        text = layout.summary()
        self.assertIn("4 x 4", text)
        self.assertIn("aperture", text)


class TestArrayFactor(unittest.TestCase):
    def setUp(self):
        self.positions = array.element_positions(4, 4, 0.5 * LAMBDA0, 0.5 * LAMBDA0)

    def test_broadside_factor_equals_the_element_count(self):
        value = array.array_factor(self.positions, F0, 0.0, 0.0)
        self.assertAlmostEqual(abs(value), 16.0, places=6)

    def test_weights_length_is_validated(self):
        with self.assertRaises(ValueError):
            array.array_factor(self.positions, F0, 0.0, 0.0, weights=[1.0 + 0j])

    def test_plane_cut_is_normalised_and_complete(self):
        samples = array.array_factor_plane(self.positions, F0, n_points=91, plane="e")
        self.assertEqual(len(samples), 91)
        peak = max(value for _, value in samples)
        self.assertAlmostEqual(peak, 0.0, places=6)
        self.assertTrue(all(value <= 1e-9 for _, value in samples))

    def test_steering_moves_the_peak(self):
        """A beam steered to 30 degrees must peak near 30 degrees, not at 0."""
        samples = array.array_factor_plane(
            self.positions, F0, n_points=181, plane="e", scan_theta_rad=math.radians(30)
        )
        peak_angle = max(samples, key=lambda item: item[1])[0]
        self.assertLess(abs(peak_angle - 30.0), 2.0)

    def test_invalid_plane_is_rejected(self):
        with self.assertRaises(ValueError):
            array.array_factor_plane(self.positions, F0, plane="x")


if __name__ == "__main__":
    unittest.main()
