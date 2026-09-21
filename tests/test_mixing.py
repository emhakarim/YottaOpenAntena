"""Tests for the two-phase composite mixing rules (stdlib unittest)."""

from __future__ import annotations

import unittest

from openantenna.materials import mixing

MATRIX = 2.1   # PTFE
FILLER = 80.0  # high-permittivity ceramic filler


class TestWienerBounds(unittest.TestCase):
    def test_upper_is_not_below_lower(self):
        lower = float(mixing.wiener_lower(MATRIX, FILLER, 0.3))
        upper = float(mixing.wiener_upper(MATRIX, FILLER, 0.3))
        self.assertLessEqual(lower, upper)

    def test_bounds_bracket_the_constituents(self):
        lower = float(mixing.wiener_lower(MATRIX, FILLER, 0.3))
        upper = float(mixing.wiener_upper(MATRIX, FILLER, 0.3))
        self.assertGreater(lower, MATRIX)
        self.assertLess(upper, FILLER)

    def test_helper_matches_the_two_functions(self):
        lower, upper = mixing.wiener_bounds(MATRIX, FILLER, 0.3)
        self.assertAlmostEqual(float(lower), float(mixing.wiener_lower(MATRIX, FILLER, 0.3)))
        self.assertAlmostEqual(float(upper), float(mixing.wiener_upper(MATRIX, FILLER, 0.3)))


class TestModelMonotonicity(unittest.TestCase):
    """Every mixing rule must grow with filler content when eps_f > eps_m."""

    def test_lichtenecker_monotonic(self):
        values = [float(mixing.lichtenecker(MATRIX, FILLER, vf)) for vf in (0.1, 0.2, 0.4)]
        self.assertEqual(values, sorted(values))
        self.assertGreater(values[0], MATRIX)
        self.assertLess(values[-1], FILLER)

    def test_maxwell_garnett_monotonic(self):
        values = [float(mixing.maxwell_garnett(MATRIX, FILLER, vf)) for vf in (0.1, 0.2, 0.4)]
        self.assertEqual(values, sorted(values))

    def test_bruggeman_monotonic(self):
        values = [float(mixing.bruggeman(MATRIX, FILLER, vf)) for vf in (0.1, 0.2, 0.4)]
        self.assertEqual(values, sorted(values))

    def test_maxwell_garnett_inside_wiener_bounds(self):
        """Spherical inclusions must land between the series and parallel bounds."""
        for vf in (0.1, 0.3, 0.4):
            lower = float(mixing.wiener_lower(MATRIX, FILLER, vf))
            upper = float(mixing.wiener_upper(MATRIX, FILLER, vf))
            value = float(mixing.maxwell_garnett(MATRIX, FILLER, vf))
            self.assertGreaterEqual(value, lower - 1e-9, msg=f"vf={vf}")
            self.assertLessEqual(value, upper + 1e-9, msg=f"vf={vf}")


class TestComparisonHelper(unittest.TestCase):
    def test_compare_models_returns_a_rendered_table(self):
        result = mixing.compare_models(MATRIX, FILLER, 0.3, frequency_hz=1.0e9)
        self.assertIsInstance(result, dict)
        table = mixing.format_comparison_table(result)
        self.assertIsInstance(table, str)
        self.assertGreater(len(table), 20)

    def test_loss_estimate_returns_a_dict(self):
        out = mixing.estimate_effective_tan_delta(
            MATRIX, FILLER, 0.3, tan_delta_matrix=0.0004, tan_delta_filler=0.001
        )
        self.assertIsInstance(out, dict)
        self.assertTrue(out)


class TestValidityWarnings(unittest.TestCase):
    def test_percolation_warning_triggers_only_when_high(self):
        self.assertIsNone(mixing.percolation_warning(0.05))
        self.assertIsNotNone(mixing.percolation_warning(0.6))

    def test_maxwell_wagner_warning_is_low_frequency_only(self):
        self.assertIsNotNone(mixing.maxwell_wagner_warning(1.0e3))
        self.assertIsNone(mixing.maxwell_wagner_warning(1.0e9))

    def test_quasi_static_warning_accepts_physical_inputs(self):
        """Must not raise; the message content is covered by its own docstring."""
        result = mixing.quasi_static_warning(1.0e9, 1.0e-6, FILLER)
        self.assertTrue(result is None or isinstance(result, str))


class TestInputValidation(unittest.TestCase):
    def test_volume_fraction_out_of_range_is_rejected(self):
        with self.assertRaises(ValueError):
            mixing.lichtenecker(MATRIX, FILLER, 1.5)

    def test_negative_volume_fraction_is_rejected(self):
        with self.assertRaises(ValueError):
            mixing.wiener_upper(MATRIX, FILLER, -0.1)


if __name__ == "__main__":
    unittest.main()
