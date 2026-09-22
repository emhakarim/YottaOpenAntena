"""Tests for the corporate feed analysis (Phase 2 #5).

The results are properties of a *matched* tree at its design frequency, so they can be asserted
exactly: a matched load must see no reflection, and an element mismatch must come back inverted.
The scikit-rf cross-check is optional and skipped when that package is absent.

Nothing here claims the feed is drawn in the solver model - it is not, and the generator says so.
"""

from __future__ import annotations

import importlib.util
import unittest

from openantenna.postproc.feed_network import (
    skrf_cross_check,
    combine_with_elements,
    synthesise_corporate_feed,
)



class TestSynthesis(unittest.TestCase):
    def test_a_power_of_two_elements_gives_one_section_per_level(self):
        for n, levels in ((2, 1), (4, 2), (16, 4)):
            with self.subTest(n=n):
                feed = synthesise_corporate_feed(n, 2.45e9, 3.32)
                self.assertEqual(feed.levels, levels)
                self.assertAlmostEqual(feed.stage_impedance_ohm, 50.0 / 2 ** 0.5, places=9)

    def test_the_section_is_a_quarter_wave_in_the_guide(self):
        feed = synthesise_corporate_feed(4, 2.45e9, 3.32)
        expected = 299792458.0 / (2.45e9 * 3.32 ** 0.5) / 4.0
        self.assertAlmostEqual(feed.section_length_m, expected, places=12)

    def test_a_non_power_of_two_is_refused_rather_than_padded(self):
        with self.assertRaises(ValueError) as ctx:
            synthesise_corporate_feed(6, 2.45e9, 3.32)
        self.assertIn("power of two", str(ctx.exception))

    def test_single_element_and_bad_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            synthesise_corporate_feed(1, 2.45e9, 3.32)
        with self.assertRaises(ValueError):
            synthesise_corporate_feed(4, 0.0, 3.32)


class TestMatchBehaviour(unittest.TestCase):
    def test_a_matched_load_sees_no_reflection(self):
        feed = synthesise_corporate_feed(4, 2.45e9, 3.32)
        self.assertAlmostEqual(abs(feed.input_reflection(complex(50.0, 0.0))), 0.0, places=12)

    def test_an_element_mismatch_comes_back_inverted_for_an_odd_level_count(self):
        """2 elements = one level: Z_in = Z0**2 / Z_e, so Gamma_in = -Gamma_e."""
        feed = synthesise_corporate_feed(2, 2.45e9, 3.32)
        z_element = complex(75.0, 0.0)  # VSWR 1.5
        gamma_element = (z_element - 50.0) / (z_element + 50.0)
        self.assertAlmostEqual(feed.input_reflection(z_element), -gamma_element, places=12)

    def test_an_even_level_count_returns_the_element_reflection_unchanged(self):
        """4 elements = two levels: the two inversions cancel, so Gamma_in = Gamma_e.

        This is the case the first version of the module got wrong; the scikit-rf cross-check is
        what exposed it.
        """
        feed = synthesise_corporate_feed(4, 2.45e9, 3.32)
        z_element = complex(75.0, 0.0)
        gamma_element = (z_element - 50.0) / (z_element + 50.0)
        self.assertAlmostEqual(feed.input_reflection(z_element), gamma_element, places=12)

    def test_combining_reports_the_worst_element(self):
        feed = synthesise_corporate_feed(2, 2.45e9, 3.32)
        good = 0.1 + 0.0j
        bad = 0.25 + 0.0j
        matrix = [[good, 0.0j], [0.0j, bad]]
        report = combine_with_elements(matrix, feed, 2.45e9)
        self.assertEqual(report["n_elements"], 2)
        self.assertAlmostEqual(report["worst_input_reflection"], 0.25, places=9)
        self.assertAlmostEqual(report["worst_input_vswr"], 1.6666667, places=6)
        self.assertIn("not drawn", report["note"])

    def test_combining_at_the_wrong_frequency_is_refused(self):
        feed = synthesise_corporate_feed(2, 2.45e9, 3.32)
        with self.assertRaises(ValueError) as ctx:
            combine_with_elements([[0.1 + 0j, 0j], [0j, 0.1 + 0j]], feed, 2.5e9)
        self.assertIn("design frequency", str(ctx.exception))

    def test_a_mismatched_port_count_is_refused(self):
        feed = synthesise_corporate_feed(4, 2.45e9, 3.32)
        with self.assertRaises(ValueError) as ctx:
            combine_with_elements([[0.1 + 0j]], feed, 2.45e9)
        self.assertIn("designed for 4", str(ctx.exception))

    def test_an_active_element_is_refused_rather_than_converted(self):
        feed = synthesise_corporate_feed(2, 2.45e9, 3.32)
        with self.assertRaises(ValueError) as ctx:
            combine_with_elements([[1.2 + 0j, 0j], [0j, 0.1 + 0j]], feed, 2.45e9)
        self.assertIn("|S| >= 1", str(ctx.exception))

@unittest.skipUnless(
    importlib.util.find_spec("skrf") is not None, "scikit-rf is not installed"
)
class TestSkrfCrossCheck(unittest.TestCase):
    def test_the_library_agrees_after_renormalisation(self):
        for n in (2, 4, 16):
            feed = synthesise_corporate_feed(n, 2.45e9, 3.32)
            for z_load in (complex(50.0, 0.0), complex(75.0, 0.0), complex(35.0, 5.0)):
                with self.subTest(n=n, z=z_load):
                    self.assertAlmostEqual(
                        abs(
                            skrf_cross_check(feed, z_load) - feed.input_reflection(z_load)
                        ),
                        0.0,
                        places=6,
                    )


if __name__ == "__main__":
    unittest.main()
