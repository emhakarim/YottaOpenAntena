"""Tests for rectangular patch synthesis (transmission-line model)."""

from __future__ import annotations

import math
import unittest

from openantenna.geometry import patch

C0 = 299792458.0
F0 = 2.45e9
ER = 2.1        # PTFE
H = 1.6e-3      # 1.6 mm


class TestPrimitives(unittest.TestCase):
    def test_free_space_wavelength(self):
        self.assertAlmostEqual(patch.wavelength0(F0), C0 / F0, places=12)

    def test_effective_permittivity_is_between_one_and_er(self):
        width = patch.patch_width(F0, ER)
        ereff = patch.effective_permittivity(ER, H, width)
        self.assertGreater(ereff, 1.0)
        self.assertLess(ereff, ER)

    def test_fringing_extension_is_positive(self):
        width = patch.patch_width(F0, ER)
        ereff = patch.effective_permittivity(ER, H, width)
        self.assertGreater(patch.delta_length(H, ereff, width), 0.0)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            patch.patch_width(0.0, ER)
        with self.assertRaises(ValueError):
            patch.effective_permittivity(ER, -1.0, 0.05)


class TestSynthesis(unittest.TestCase):
    def test_ptfe_patch_dimensions_are_plausible(self):
        design = patch.synthesize_patch(F0, ER, H)
        # ~49 mm x ~41 mm for a 2.45 GHz patch on 1.6 mm PTFE
        self.assertAlmostEqual(design.width_m * 1e3, 49.1, delta=1.5)
        self.assertAlmostEqual(design.length_m * 1e3, 41.4, delta=1.5)

    def test_resonance_check_is_self_consistent(self):
        """The synthesis and the resonance check use the same formulas, so the
        achieved frequency must reproduce the target almost exactly."""
        design = patch.synthesize_patch(F0, ER, H)
        self.assertAlmostEqual(design.achieved_frequency_hz, F0, delta=1e4)

    def test_higher_permittivity_shrinks_the_patch(self):
        ptfe = patch.synthesize_patch(F0, 2.1, H)
        ceramic = patch.synthesize_patch(F0, 10.0, H)
        self.assertLess(ceramic.width_m, ptfe.width_m)
        self.assertLess(ceramic.length_m, ptfe.length_m)

    def test_thicker_substrate_widens_the_bandwidth_estimate(self):
        thin = patch.synthesize_patch(F0, ER, 0.8e-3)
        thick = patch.synthesize_patch(F0, ER, 3.2e-3)
        self.assertGreater(
            thick.fractional_bandwidth_est, thin.fractional_bandwidth_est
        )

    def test_electrically_thick_substrate_raises_a_warning(self):
        design = patch.synthesize_patch(F0, ER, 5.0e-3)
        self.assertTrue(any("thick" in w.lower() for w in design.warnings))

    def test_high_permittivity_raises_a_warning(self):
        design = patch.synthesize_patch(F0, 20.0, H)
        self.assertTrue(any("eps_r" in w or "high" in w.lower() for w in design.warnings))

    def test_summary_mentions_the_dimensions(self):
        text = patch.synthesize_patch(F0, ER, H).summary()
        self.assertIn("patch W x L", text)
        self.assertIn("cavity cross-chk", text)
        self.assertIn("self-consistency", text)

    def test_cavity_cross_check_is_a_different_number(self):
        """Y-04: the old 'resonance check' merely re-ran the synthesis formula.

        The cavity model uses sqrt(eps_r) > sqrt(eps_eff), so it predicts a LOWER
        frequency than the synthesis: 2.4007 GHz against a 2.45 GHz target here.
        It is an independent number, not an identity.
        """
        design = patch.synthesize_patch(F0, ER, H)
        self.assertAlmostEqual(design.achieved_frequency_hz, F0, delta=1e4)
        self.assertLess(design.frequency_cavity_hz, F0)
        self.assertAlmostEqual(design.frequency_cavity_hz / 1e9, 2.4007, delta=0.01)
        self.assertLess(design.frequency_error_hz, 0.0)

    def test_epsilon_r_at_or_below_one_is_rejected_for_every_feed_mode(self):
        """Y-10: this used to return NaN for edge feed and raise for inset."""
        for mode in ("inset", "edge", "probe"):
            with self.assertRaises(ValueError):
                patch.synthesize_patch(F0, 1.0, H, mode)

    def test_narrow_line_correction_is_applied_below_one_over_h(self):
        """Y-12: Hammerstad's narrow-line term must raise eps_eff below W/h = 1."""
        wide = patch.effective_permittivity(2.2, 1e-3, 5e-3)   # W/h = 5
        narrow = patch.effective_permittivity(2.2, 1e-3, 0.5e-3)  # W/h = 0.5
        self.assertGreater(narrow, 1.0)
        self.assertLess(narrow, 2.2)
        self.assertGreater(wide, 1.0)

    def test_balanis_example_14_1_golden_values(self):
        """Golden values from Balanis, Antenna Theory, Example 14.1.

        eps_r = 2.2, h = 1.588 mm, f = 10 GHz.  Book: W = 11.86 mm, eps_eff = 1.972,
        dL = 0.811 mm, L = 9.06 mm.  Tolerances cover the book's rounding.
        """
        design = patch.synthesize_patch(10.0e9, 2.2, 1.588e-3)
        self.assertAlmostEqual(design.width_m * 1e3, 11.850, delta=0.06)
        self.assertAlmostEqual(design.epsilon_eff, 1.9715, delta=0.005)
        self.assertAlmostEqual(design.delta_l_m * 1e3, 0.8110, delta=0.02)
        self.assertAlmostEqual(design.length_m * 1e3, 9.053, delta=0.09)

    def test_transmission_line_and_cavity_predictions_are_locked(self):
        """Lock the ~2 % gap between the two analytic models.

        A silent change to either formula would move these numbers; the gap is the
        quantity that shows the synthesis is model-dependent (review item Y-T4e).
        """
        design = patch.synthesize_patch(F0, ER, H)
        self.assertAlmostEqual(design.achieved_frequency_hz / 1e9, 2.4500, delta=0.002)
        self.assertAlmostEqual(design.frequency_cavity_hz / 1e9, 2.4007, delta=0.003)
        gap_percent = (
            (design.frequency_cavity_hz - design.achieved_frequency_hz)
            / design.achieved_frequency_hz
            * 100.0
        )
        self.assertAlmostEqual(gap_percent, -2.0, delta=0.3)


class TestFeedHelpers(unittest.TestCase):
    def test_inset_depth_stays_inside_the_patch(self):
        design = patch.synthesize_patch(F0, ER, H)
        self.assertGreaterEqual(design.inset_depth_m, 0.0)
        self.assertLessEqual(design.inset_depth_m, 0.5 * design.length_m)

    def test_inset_depth_helper_never_returns_negative(self):
        depth = patch.inset_depth_for_input_resistance(0.041, 0.049, ER, 50.0)
        self.assertGreaterEqual(depth, 0.0)

    def test_ground_plane_grows_with_margin(self):
        small = patch.ground_plane_size(0.05, 0.04, F0, margin_lambda=0.1)
        large = patch.ground_plane_size(0.05, 0.04, F0, margin_lambda=0.5)
        self.assertLess(small[0], large[0])
        self.assertLess(small[1], large[1])
        self.assertGreater(small[0], 0.05)


if __name__ == "__main__":
    unittest.main()
