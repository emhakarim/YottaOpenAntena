"""Tests for yotta_tools/nf2ff_compare.py (R-5 far-field cross-check helper)."""

from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yotta_tools.nf2ff_compare import analyse, half_angle_deg


class TestNf2ffCompare(unittest.TestCase):
    def _write_run(self, folder, amplitude_fn):
        run = Path(folder)
        lines = ["theta_deg,phi_deg,e_norm"]
        for theta in range(0, 181, 2):
            for phi in range(0, 361, 5):
                lines.append("%.3f,%.3f,%.9e" % (theta, phi, amplitude_fn(theta, phi)))
        (run / "nf2ff_pattern.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (run / "nf2ff_summary.csv").write_text(
            "freq_hz,directivity_lin,directivity_dbi,prad_w,p_acc_w,eta_rad\n"
            "2.45e9,1.0,0.0,1e-3,1e-3,1.0\n",
            encoding="utf-8",
        )
        return run

    def test_isotropic_pattern_recomputes_directivity_one(self):
        with tempfile.TemporaryDirectory() as folder:
            run = self._write_run(folder, lambda t, p: 1.0)
            record = analyse(run)
        # trapezoid integration on the 2-degree grid lands within ~5e-4 of 1.0
        self.assertAlmostEqual(record["directivity_recomputed_lin"], 1.0, delta=1e-3)
        self.assertEqual(record["grid"], [91, 73])

    def test_short_dipole_shape_recomputes_one_point_five(self):
        # |sin(theta)| amplitude integrates to D = 1.5 exactly (short dipole).
        with tempfile.TemporaryDirectory() as folder:
            run = self._write_run(folder, lambda t, p: abs(math.sin(math.radians(t))))
            record = analyse(run)
        self.assertAlmostEqual(record["directivity_recomputed_lin"], 1.5, delta=0.02)

    def test_half_angle_interpolates_between_grid_points(self):
        data = {(t, 0.0): (1.0 if t < 30 else 0.1) for t in (0, 10, 20, 30)}
        got = half_angle_deg(data, sorted({k[0] for k in data}), 0.0, 0)
        self.assertAlmostEqual(got, 23.25, places=2)

    def test_summary_rows_are_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            run = self._write_run(folder, lambda t, p: 1.0)
            record = analyse(run)
        self.assertEqual(len(record["summary"]), 1)
        self.assertAlmostEqual(record["summary"][0]["directivity_dbi"], 0.0)


if __name__ == "__main__":
    unittest.main()
