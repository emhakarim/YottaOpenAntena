"""A6: the two-stage sweep planner must refuse edge minima instead of dressing them up.

The edge case is not hypothetical: one of my own batch runs reported 2.817 GHz, which is
exactly the sweep's upper limit — a boundary artifact that looked like a resonance.
"""

from __future__ import annotations

import importlib.util
import math
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "yotta_tools" / "two_stage_sweep.py"


def _load():
    spec = importlib.util.spec_from_file_location("yotta_two_stage", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _trace(minimum_index: int, n: int = 21, f0: float = 2.0e9, span: float = 0.5e9):
    """A synthetic |S11| trace (dB) with its minimum at `minimum_index`."""
    samples = []
    for i in range(n):
        f = f0 - span / 2 + span * i / (n - 1)
        depth = -25.0 + abs(i - minimum_index) * 0.8
        samples.append((f, depth))
    return samples


class TestTwoStageSweep(unittest.TestCase):
    def setUp(self):
        self.tool = _load()

    def test_interior_minimum_gives_a_centred_window(self):
        result = self.tool.plan(_trace(10), span_fraction=0.10)
        self.assertEqual(result["status"], "ok")
        rec = result["recommended"]
        self.assertLess(rec["start_hz"], result["minimum_hz"])
        self.assertGreater(rec["stop_hz"], result["minimum_hz"])
        self.assertLess(rec["stop_hz"] - rec["start_hz"], result["coarse_span_hz"])
        self.assertLess(result["cost_ratio_vs_full"], 0.25)

    def test_edge_minimum_is_refused(self):
        for index in (0, 20):
            result = self.tool.plan(_trace(index))
            self.assertEqual(result["status"], "invalid-edge-minimum")
            self.assertIn("boundary artifact", result["reason"])
            self.assertNotIn("recommended", result)

    def test_near_edge_minimum_is_also_refused(self):
        # index 1 of 21 sits inside the 1 % edge zone
        result = self.tool.plan(_trace(1))
        self.assertEqual(result["status"], "invalid-edge-minimum")

    def test_thin_data_is_refused(self):
        result = self.tool.plan(_trace(2, n=3))
        self.assertEqual(result["status"], "insufficient-data")

    def test_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "s11.csv"
            lines = ["freq_hz,s11_re,s11_im"]
            for f, db in _trace(8):
                magnitude = 10 ** (db / 20.0)
                lines.append(f"{f:.6e},{magnitude:.9e},0.0")
            csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            samples = self.tool.load_s11(csv_path)
            self.assertEqual(len(samples), 21)
            result = self.tool.plan(samples)
            self.assertEqual(result["status"], "ok")
            self.assertAlmostEqual(result["minimum_db"], -25.0, places=2)


if __name__ == "__main__":
    unittest.main()
