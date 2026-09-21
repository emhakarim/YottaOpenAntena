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
