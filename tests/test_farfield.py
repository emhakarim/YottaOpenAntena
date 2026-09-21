"""Tests for the far-field reader and the independent directivity integration."""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from openantenna.postproc import farfield


def half_wave_dipole(theta_deg: float) -> float:
    """|E| of a thin half-wave dipole, normalised to 1 at theta = 90 degrees."""
    theta = math.radians(theta_deg)
    sin_theta = math.sin(theta)
    if abs(sin_theta) < 1e-12:
        return 0.0
    return abs((math.cos(math.pi / 2.0 * math.cos(theta))) / sin_theta)


def write_pattern(path: Path, thetas, phis) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write("theta_deg,phi_deg,e_norm\n")
        for theta in thetas:
            for phi in phis:
                handle.write(f"{theta:.3f},{phi:.3f},{half_wave_dipole(theta):.9e}\n")


class TestPatternIntegration(unittest.TestCase):
    def test_half_wave_dipole_directivity_from_a_solver_grid(self):
        """Golden value 1.6409 on the grid the generated model actually writes
        (2 deg in theta, 5 deg in phi)."""
        thetas = [2.0 * i for i in range(91)]
        phis = [5.0 * i for i in range(73)]  # 0 .. 360, endpoint duplicated
        grid = [[half_wave_dipole(t) for _ in phis] for t in thetas]
        directivity = farfield.directivity_from_pattern_grid(thetas, phis, grid)
        self.assertAlmostEqual(directivity, 1.6409, delta=0.05)

    def test_grid_too_small_is_rejected(self):
        with self.assertRaises(ValueError):
            farfield.directivity_from_pattern_grid([0.0], [0.0], [[1.0]])


class TestReader(unittest.TestCase):
    def test_summary_round_trip(self):
        rows = [
            "freq_hz,directivity_lin,directivity_dbi,prad_w,p_acc_w,eta_rad",
            "2.200000e+09,5.000000e+00,6.989700e+00,1.000000e-03,1.250000e-03,8.000000e-01",
            "2.450000e+09,7.000000e+00,8.450980e+00,2.000000e-03,2.500000e-03,8.000000e-01",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / farfield.SUMMARY_NAME
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            points = farfield.read_summary(path)
        self.assertEqual(len(points), 2)
        self.assertAlmostEqual(points[1].frequency_hz, 2.45e9)
        self.assertAlmostEqual(points[1].directivity_linear, 7.0)
        self.assertAlmostEqual(points[1].radiation_efficiency, 0.8)
        text = farfield.summary_text(points, reference_hz=2.45e9)
        self.assertIn("2.4500", text)

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                farfield.read_summary(Path(tmp) / "nothing.csv")

    def test_pattern_round_trip(self):
        thetas = [0.0, 90.0, 180.0]
        phis = [0.0, 180.0, 360.0]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / farfield.PATTERN_NAME
            write_pattern(path, thetas, phis)
            t_read, p_read, grid, _ = farfield.read_pattern(path)
        self.assertEqual(t_read, thetas)
        self.assertEqual(p_read, phis)
        self.assertEqual(len(grid), 3)
        self.assertEqual(len(grid[0]), 3)
        self.assertAlmostEqual(grid[1][0], 1.0, places=9)

    def test_directory_path_is_accepted(self):
        rows = [
            "freq_hz,directivity_lin,directivity_dbi,prad_w,p_acc_w,eta_rad",
            "2.450000e+09,6.000000e+00,7.781513e+00,1.000000e-03,1.000000e-03,1.000000e+00",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / farfield.SUMMARY_NAME).write_text("\n".join(rows) + "\n", encoding="utf-8")
            points = farfield.read_summary(tmp)
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0].radiation_efficiency, 1.0)


if __name__ == "__main__":
    unittest.main()
