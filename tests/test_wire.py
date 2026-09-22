"""Phase 2 #6 foundation: the neutral wire model.

These tests pin the *geometry and its guards*.  They deliberately assert nothing
about impedance or gain, because those need a solver — claiming them here would be
exactly the kind of fabrication the project forbids.
"""

from __future__ import annotations

import unittest

from openantenna.geometry.wire import (
    MAX_RADIUS_RATIO,
    WireDesign,
    synthesize_dipole,
    synthesize_monopole,
    wavelength0,
)


class TestDipoleSynthesis(unittest.TestCase):
    def test_half_wave_length_is_half_a_wavelength(self):
        f = 2.45e9
        design = synthesize_dipole(f)
        self.assertAlmostEqual(design.length_m, 0.5 * wavelength0(f), places=12)
        self.assertAlmostEqual(design.length_lambda, 0.5, places=12)
        self.assertAlmostEqual(design.length_m * 1e3, 61.182, delta=0.01)

    def test_centre_fed_dipole_gets_an_odd_segment_count(self):
        design = synthesize_dipole(2.45e9, segments=30)  # even -> bumped to 31
        self.assertEqual(design.segments, 31)
        self.assertEqual(design.segments % 2, 1)

    def test_feed_gap_is_one_segment(self):
        design = synthesize_dipole(2.45e9, segments=31)
        self.assertAlmostEqual(design.feed_gap_m, design.length_m / 31, places=12)

    def test_a_shortened_design_carries_a_warning(self):
        design = synthesize_dipole(2.45e9, length_factor=0.47)
        self.assertEqual(len(design.warnings), 1)
        self.assertIn("end-effect", design.warnings[0])

    def test_absurd_length_factors_are_rejected(self):
        for bad in (0.1, 0.9):
            with self.assertRaises(ValueError):
                synthesize_dipole(2.45e9, length_factor=bad)


class TestMonopoleSynthesis(unittest.TestCase):
    def test_quarter_wave_monopole(self):
        design = synthesize_monopole(2.45e9)
        self.assertAlmostEqual(design.length_lambda, 0.25, places=12)
        self.assertTrue(design.ground_plane)

    def test_monopole_allows_an_even_segment_count(self):
        design = synthesize_monopole(2.45e9, segments=20)  # no centre segment needed
        self.assertEqual(design.segments, 20)


class TestGuards(unittest.TestCase):
    def test_thick_wires_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            synthesize_dipole(2.45e9, radius_m=MAX_RADIUS_RATIO * 0.0612)
        self.assertIn("thin-wire", str(ctx.exception))

    def test_round_trip_through_a_dict(self):
        design = synthesize_dipole(5.8e9, radius_m=0.5e-3, length_factor=0.48)
        restored = WireDesign.from_dict(design.to_dict())
        self.assertEqual(restored.to_dict(), design.to_dict())

    def test_summary_states_that_it_predicts_no_impedance(self):
        text = synthesize_dipole(2.45e9).summary()
        self.assertIn("must come from a solver", text)
        self.assertIn("0.5000 lambda0", text)


if __name__ == "__main__":
    unittest.main()
