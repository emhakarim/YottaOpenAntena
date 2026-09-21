"""Tests for the S-parameter helpers, focused on the review findings.

Covers Y-05 (phase-less traces must not produce a fake impedance) and Y-15
(the Touchstone reference impedance must be honoured).
"""

from __future__ import annotations

import cmath
import tempfile
import unittest
from pathlib import Path

from openantenna.postproc.sparams import S11Trace, read_touchstone


class TestPhaseContract(unittest.TestCase):
    def test_magnitude_only_trace_has_no_phase(self):
        trace = S11Trace.from_magnitude_db([2.4e9, 2.45e9, 2.5e9], [-3.0, -20.0, -6.0])
        self.assertFalse(trace.has_phase)

    def test_impedance_is_refused_without_phase(self):
        trace = S11Trace.from_magnitude_db([2.4e9, 2.45e9, 2.5e9], [-3.0, -20.0, -6.0])
        with self.assertRaises(ValueError):
            trace.impedance_ohm()

    def test_magnitude_and_phase_trace_allows_impedance(self):
        trace = S11Trace.from_magnitude_phase_db(
            [2.4e9, 2.45e9, 2.5e9], [-3.0, -20.0, -6.0], [180.0, 0.0, 90.0]
        )
        self.assertTrue(trace.has_phase)
        self.assertEqual(len(trace.impedance_ohm()), 3)

    def test_vswr_and_bandwidth_still_work_without_phase(self):
        trace = S11Trace.from_magnitude_db([2.4e9, 2.45e9, 2.5e9], [-3.0, -20.0, -6.0])
        self.assertAlmostEqual(trace.vswr()[1], (1 + 0.1) / (1 - 0.1), places=9)
        self.assertTrue(trace.bandwidth_below(-10.0))


class TestResonanceRefinement(unittest.TestCase):
    def test_parabolic_fit_recovers_an_off_grid_minimum(self):
        """0.1 % targeting needs sub-grid resolution: with 10 MHz steps a raw
        minimum is only located to about 0.4 %."""
        start, step, depth, width = 2.400e9, 10.0e6, 30.0, 20.0e6
        true_minimum = 2.4673e9
        frequencies = [start + i * step for i in range(11)]
        # A resonance dip: |S11| is most negative at the resonance and rises away
        # from it, so the dB curve is concave UP with a vertex at true_minimum.
        magnitudes_db = [
            -depth + depth * ((f - true_minimum) / width) ** 2 for f in frequencies
        ]
        trace = S11Trace(
            frequencies, [complex(10.0 ** (db / 20.0), 0.0) for db in magnitudes_db]
        )
        refined, grid_step, curvature = trace.refine_resonance()
        # the raw grid minimum is 2.470 GHz (0.11 % away); the fit must do better
        self.assertAlmostEqual(refined / 1e9, 2.4673, places=6)
        self.assertLess(abs(refined - true_minimum) / true_minimum, 1e-6)
        self.assertAlmostEqual(grid_step, step, places=3)
        # second derivative of the dB dip: 2*depth/width^2
        self.assertAlmostEqual(curvature, 2.0 * depth / width ** 2, delta=abs(curvature) * 0.01)

    def test_refinement_is_reported_in_parsed_results(self):
        rows = ["freq_hz,s11_re,s11_im"]
        for i in range(11):
            frequency = 2.400e9 + i * 10.0e6
            magnitude_db = -30.0 + 30.0 * ((frequency - 2.4673e9) / 20.0e6) ** 2
            rows.append(f"{frequency:.6e},{10.0 ** (magnitude_db / 20.0):.9e},0.0")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s11.csv"
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            from openantenna.solvers.openems import OpenEMSSolver

            parsed = OpenEMSSolver().parse_results(tmp)
        self.assertAlmostEqual(parsed["resonance_refined_hz"] / 1e9, 2.4673, places=6)
        self.assertAlmostEqual(parsed["resonance_grid_step_hz"], 10.0e6, places=1)
        self.assertIn("resonance_curvature_db_per_hz2", parsed)


class TestTouchstoneReferenceImpedance(unittest.TestCase):
    def test_reference_impedance_is_read_and_used(self):
        content = "# Hz S RI R 75\n2.4e9 0.1 0.0\n2.45e9 -0.2 0.1\n2.5e9 0.05 -0.05\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.s1p"
            path.write_text(content, encoding="utf-8")
            trace = read_touchstone(path)
        self.assertAlmostEqual(trace.reference_impedance_ohm, 75.0)
        sample = complex(-0.2, 0.1)
        expected = 75.0 * (1.0 + sample) / (1.0 - sample)
        impedance = trace.impedance_ohm()[1]
        self.assertAlmostEqual(impedance.real, expected.real, places=9)
        self.assertAlmostEqual(impedance.imag, expected.imag, places=9)

    def test_default_reference_is_50_ohm(self):
        content = "# Hz S RI R 50\n2.4e9 0.1 0.0\n2.45e9 0.05 0.0\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.s0p"
            path.write_text(content, encoding="utf-8")
            trace = read_touchstone(path)
        self.assertAlmostEqual(trace.reference_impedance_ohm, 50.0)

    def test_round_trip_through_touchstone_keeps_the_trace(self):
        trace = S11Trace.from_magnitude_phase_db(
            [2.0e9, 2.2e9, 2.4e9], [-2.0, -18.0, -5.0], [150.0, 10.0, -60.0]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roundtrip.s1p"
            trace.write_touchstone(path, z0_ohm=50.0)
            reloaded = read_touchstone(path)
        for original, restored in zip(trace.s11, reloaded.s11):
            self.assertAlmostEqual(original.real, restored.real, places=8)
            self.assertAlmostEqual(original.imag, restored.imag, places=8)


if __name__ == "__main__":
    unittest.main()
