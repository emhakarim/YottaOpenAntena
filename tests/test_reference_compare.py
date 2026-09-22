"""Tests for the external-reference comparison (CST vs our model).

The critical property: **both sides are reduced with the same metric**.  A test that only checked
"a bias came out" would pass even if the two sides used different definitions of the resonance, so
these tests pin the metric equality directly.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openantenna.postproc.calibration import calibrate
from openantenna.postproc.reference_compare import (
    compare_design,
    compare_folder,
    compare_traces,
    load_reference,
    resonance_of,
)
from openantenna.postproc.sparams import S11Trace


def write_csv(path: Path, points: list[tuple[float, float, float]]) -> None:
    lines = ["freq_hz,s11_re,s11_im"]
    for f, re, im in points:
        lines.append(f"{f:.6e},{re:.6e},{im:.6e}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_touchstone(path: Path, points: list[tuple[float, float, float]]) -> None:
    """Minimal 1-port Touchstone: frequency in Hz (no unit line), magnitude/angle in degrees."""
    lines = []
    for f, re, im in points:
        magnitude = (re * re + im * im) ** 0.5
        angle = 57.29577951308232 * __import__("math").atan2(im, re)
        lines.append(f"{f:.6e} {magnitude:.6e} {angle:.6e}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dip(centre_hz: float, depth_db: float) -> list[tuple[float, float, float]]:
    """A synthetic resonance: three points with the minimum at the centre."""
    step = 0.025e9
    out = []
    for offset, level in ((-step, depth_db + 18.0), (0.0, depth_db), (step, depth_db + 18.0)):
        magnitude = 10 ** (level / 20.0)
        out.append((centre_hz + offset, magnitude, 0.0))
    return out


class TestMetricEquality(unittest.TestCase):
    def test_both_sides_use_the_same_reduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference_path = root / "cst_s11.s1p"
            ours_path = root / "s11.csv"
            write_touchstone(reference_path, dip(2.4500e9, -25.0))
            write_csv(ours_path, dip(2.4375e9, -22.0))

            reference = load_reference(reference_path)
            ours = S11Trace.from_csv(ours_path)

            reference_hz, _ = resonance_of(reference)
            our_hz, _ = resonance_of(ours)
            sample = compare_traces(reference, ours, "demo")

        # the sample must carry exactly those two numbers, not a re-derivation
        self.assertAlmostEqual(sample.reference_hz, reference_hz)
        self.assertAlmostEqual(sample.measured_hz, our_hz)
        self.assertIn("same metric", sample.notes)
        self.assertNotEqual(reference_hz, our_hz)

    def test_a_known_offset_shows_up_as_that_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_touchstone(root / "cst_s11.s1p", dip(2.45e9, -25.0))
            write_csv(root / "s11.csv", dip(2.45e9 * 0.99, -20.0))
            sample = compare_traces(
                load_reference(root / "cst_s11.s1p"),
                S11Trace.from_csv(root / "s11.csv"),
                "demo",
            )
        self.assertAlmostEqual(sample.bias_percent, -1.0, places=2)


class TestDesignFolders(unittest.TestCase):
    def _design(self, root: Path, name: str, *, our_centre: float, converged: bool = True):
        design = root / name
        run = design / "run"
        run.mkdir(parents=True)
        write_touchstone(design / "cst_s11.s1p", dip(2.45e9, -25.0))
        write_csv(run / "s11.csv", dip(our_centre, -22.0))
        (run / "run_summary.json").write_text(
            json.dumps({"converged": converged, "timesteps": 5000}), encoding="utf-8"
        )
        return design

    def test_a_complete_design_is_compared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._design(root, "ptfe_245", our_centre=2.4375e9)
            sample = compare_design(root / "ptfe_245")
        self.assertEqual(sample.topology, "ptfe_245")
        self.assertTrue(sample.converged)
        self.assertAlmostEqual(sample.bias_percent, -0.51, delta=0.15)

    def test_a_missing_our_side_is_reported_not_invented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            design = root / "incomplete"
            design.mkdir()
            write_touchstone(design / "cst_s11.s1p", dip(2.45e9, -25.0))
            with self.assertRaises(FileNotFoundError) as ctx:
                compare_design(design)
        self.assertIn("nothing to compare against", str(ctx.exception))

    def test_a_folder_yields_one_sample_per_design_and_feeds_calibrate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._design(root, "ptfe_245", our_centre=2.4375e9)
            self._design(root, "fr4_245", our_centre=2.4005e9)
            (root / "broken").mkdir()
            samples = compare_folder(root)
            report = calibrate([s for s in samples if s.converged])

        self.assertEqual(len(samples), 3)
        broken = next(s for s in samples if s.topology == "broken")
        self.assertIn("incomplete", broken.notes)
        self.assertEqual(len(report.samples), 2)
        self.assertIn("ptfe_245", report.per_topology)
        self.assertIn("fr4_245", report.per_topology)

    def test_an_unconverged_our_side_is_carried_as_unconverged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._design(root, "ptfe_245", our_centre=2.4375e9, converged=False)
            sample = compare_design(root / "ptfe_245")
        self.assertFalse(sample.converged)


if __name__ == "__main__":
    unittest.main()
