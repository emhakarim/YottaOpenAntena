"""Tests for the calibration pipeline (gate condition 2).

Synthetic samples on purpose: the point here is that the *conclusion* obeys the gate's rules,
not that a particular geometry has a particular bias.  The rules that must hold:

* an unconverged sample is excluded and reported;
* one topology is never enough to claim the gate, however good the number;
* a bias that disagrees between topologies yields a correction factor *with* a validity range,
  never a claim that the bias is constant.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openantenna.postproc.calibration import (
    GATE_TOLERANCE_PERCENT,
    RunSample,
    calibrate,
    sample_from_run,
)


def sample(topology: str, reference_ghz: float, measured_ghz: float, converged: bool = True):
    return RunSample(
        topology=topology,
        source="synthetic",
        reference_hz=reference_ghz * 1e9,
        measured_hz=measured_ghz * 1e9,
        converged=converged,
    )


class TestGateRules(unittest.TestCase):
    def test_bias_is_computed_against_the_reference(self):
        entry = sample("tutorial", 2.45, 2.40)
        self.assertAlmostEqual(entry.bias_percent, -2.0408, places=3)

    def test_two_topologies_inside_tolerance_satisfy_the_gate(self):
        report = calibrate([sample("tutorial", 2.45, 2.44), sample("ptfe", 2.45, 2.4355)])
        self.assertIn("SATISFIED", report.conclusion)
        self.assertIsNone(report.correction_factor)

    def test_one_topology_is_never_enough_for_the_gate(self):
        report = calibrate([sample("tutorial", 2.45, 2.44)])
        self.assertNotIn("SATISFIED on", report.conclusion)
        self.assertIn("at least two topologies", report.conclusion)

    def test_a_disagreeing_bias_gives_a_correction_factor_with_a_validity_range(self):
        report = calibrate(
            [
                sample("tutorial", 2.45, 2.40),  # -2.04 %
                sample("ptfe", 2.45, 2.32),  # -5.31 %
            ]
        )
        self.assertIn("NOT satisfied", report.conclusion)
        self.assertIsNotNone(report.correction_factor)
        self.assertIn("does not transfer", report.validity)
        self.assertGreater(report.spread, 2.0)

    def test_unconverged_samples_are_excluded_and_named(self):
        report = calibrate(
            [
                sample("tutorial", 2.45, 2.44),
                sample("ptfe", 2.45, 2.4355),
                sample("ground-plane", 2.45, 1.00, converged=False),
            ]
        )
        self.assertEqual(len(report.samples), 2)
        self.assertIn("unconverged", report.validity)
        self.assertIn("ground-plane", report.validity)

    def test_all_unconverged_is_an_error_not_an_empty_report(self):
        with self.assertRaises(ValueError):
            calibrate([sample("tutorial", 2.45, 2.44, converged=False)])

    def test_the_summary_states_the_tolerance_and_the_counts(self):
        report = calibrate([sample("tutorial", 2.45, 2.40), sample("ptfe", 2.45, 2.32)])
        text = report.summary()
        self.assertIn("tutorial", text)
        self.assertIn("ptfe", text)
        self.assertIn("spread across topologies", text)
        payload = report.to_dict()
        self.assertEqual(payload["gate_tolerance_percent"], GATE_TOLERANCE_PERCENT)
        self.assertEqual(len(payload["samples"]), 2)


class TestSampleFromRun(unittest.TestCase):
    def _run(self, root: Path, *, converged: bool, refined: bool) -> Path:
        run = root / "run"
        run.mkdir(parents=True, exist_ok=True)
        (run / "run_summary.json").write_text(
            json.dumps({"converged": converged, "timesteps": 1000}), encoding="utf-8"
        )
        if refined:
            (run / "resonance_analysis.json").write_text(
                json.dumps({"refined_hz": 2.4496e9, "resonance_hz": 2.4500e9}), encoding="utf-8"
            )
        else:
            (run / "s11.csv").write_text(
                "freq_hz,s11_re,s11_im\n"
                "2.40e9,-0.30,0.10\n2.45e9,-0.02,0.01\n2.50e9,-0.35,0.12\n",
                encoding="utf-8",
            )
        return run

    def test_prefers_the_refined_analysis_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(Path(tmp), converged=True, refined=True)
            entry = sample_from_run("tutorial", 2.4504e9, run)
        self.assertAlmostEqual(entry.measured_hz, 2.4496e9)
        self.assertTrue(entry.converged)
        self.assertIn("sub-grid refinement", entry.notes)

    def test_falls_back_to_the_raw_minimum_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(Path(tmp), converged=True, refined=False)
            entry = sample_from_run("tutorial", 2.45e9, run)
        self.assertAlmostEqual(entry.measured_hz, 2.45e9)
        self.assertIn("no sub-grid refinement", entry.notes)

    def test_an_unconverged_run_is_carried_as_unconverged(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(Path(tmp), converged=False, refined=True)
            entry = sample_from_run("tutorial", 2.45e9, run)
        self.assertFalse(entry.converged)


if __name__ == "__main__":
    unittest.main()
