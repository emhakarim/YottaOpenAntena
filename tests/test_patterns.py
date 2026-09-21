"""Golden-value and contract tests for the far-field helpers.

Review items covered: Y-02 (element-pattern contract), Y-06 (aperture bound
validity), Y-08 (|S11| <= 1), Y-13 (directivity accuracy).
"""

from __future__ import annotations

import math
import unittest

from openantenna.postproc import patterns


class TestElementPatternContract(unittest.TestCase):
    def test_dipole_element_works_inside_pattern_product(self):
        value = patterns.array_pattern_product(
            [(0.0, 0.0)],
            2.45e9,
            math.pi / 2.0,
            0.0,
            element_pattern=patterns.dipole_element,
        )
        self.assertAlmostEqual(value, 1.0, places=6)

    def test_dipole_element_ignores_phi(self):
        for phi in (0.0, math.pi / 3.0, math.pi):
            self.assertAlmostEqual(
                patterns.dipole_element(math.pi / 2.0, phi),
                patterns.dipole_element(math.pi / 2.0, 0.0),
                places=12,
            )

    def test_raw_dipole_pattern_still_reads_the_second_argument_as_length(self):
        """The historical signature is preserved, and documented as different."""
        with self.assertRaises(ValueError):
            patterns.dipole_element_pattern(math.pi / 2.0, 0.0)


class TestDirectivityGoldenValues(unittest.TestCase):
    def _theta_grid(self, n=361):
        return [math.pi * i / (n - 1) for i in range(n)]

    @staticmethod
    def _phi_grid(n=5):
        """A closed phi grid spanning 0..2*pi (the pattern is periodic here)."""
        return [2.0 * math.pi * i / (n - 1) for i in range(n)]

    def test_short_dipole_directivity_is_1_5(self):
        thetas = self._theta_grid()
        d = patterns.directivity_from_pattern(
            thetas, self._phi_grid(), lambda theta, phi: math.sin(theta)
        )
        self.assertAlmostEqual(d, 1.5, delta=0.02)

    def test_half_wave_dipole_directivity_is_1_641(self):
        thetas = self._theta_grid()
        d = patterns.directivity_from_pattern(
            thetas, self._phi_grid(), lambda theta, phi: patterns.dipole_element(theta, phi)
        )
        self.assertAlmostEqual(d, 1.641, delta=0.04)

    def test_isotropic_source_is_1(self):
        d = patterns.directivity_from_pattern(
            self._theta_grid(181), self._phi_grid(), lambda theta, phi: 1.0
        )
        self.assertAlmostEqual(d, 1.0, delta=0.01)


class TestApertureValidity(unittest.TestCase):
    def test_small_aperture_is_rejected(self):
        with self.assertRaises(ValueError):
            patterns.aperture_directivity(0.049142, 0.041379, 2.45e9)

    def test_small_aperture_can_be_forced(self):
        value = patterns.aperture_directivity(0.049142, 0.041379, 2.45e9, allow_small=True)
        self.assertAlmostEqual(10.0 * math.log10(value), 2.32, delta=0.05)

    def test_large_aperture_is_accepted(self):
        value = patterns.aperture_directivity(0.5, 0.5, 2.45e9)
        self.assertGreater(value, 1.0)


class TestEfficiencyBudget(unittest.TestCase):
    def test_unphysical_reflection_is_rejected(self):
        with self.assertRaises(ValueError):
            patterns.efficiency_budget(1.0, 1.0, s11=1.2)

    def test_lossless_matched_case(self):
        budget = patterns.efficiency_budget(1.0, 1.0, s11=0.0)
        self.assertAlmostEqual(budget["total_efficiency"], 1.0, places=9)

    def test_mismatch_reduces_total_efficiency(self):
        budget = patterns.efficiency_budget(1.0, 1.0, s11=0.5)
        self.assertAlmostEqual(budget["mismatch_factor"], 0.75, places=9)


if __name__ == "__main__":
    unittest.main()
