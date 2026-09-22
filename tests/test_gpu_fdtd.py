"""Tests for the optional GPU path.

These skip cleanly when pyopencl or an OpenCL device is missing, because the core
toolkit must never depend on a GPU.  When a device *is* present, the cavity test runs
the kernel against an exact analytic answer (a square PEC cavity, f11 = c/2*sqrt(2)/a)
- that is the acceptance test for the whole GPU chain: staggered update, Courant
factor, PEC walls, soft source, probe and FFT.
"""

from __future__ import annotations

import unittest

from openantenna.gpu import gpu_available, opencl_devices


class TestDeviceProbe(unittest.TestCase):
    def test_probe_never_raises_and_returns_a_list(self):
        devices = opencl_devices()
        self.assertIsInstance(devices, list)
        for device in devices:
            self.assertIn("name", device)
            self.assertIn("compute_units", device)
            self.assertGreaterEqual(device["compute_units"], 1)


@unittest.skipUnless(gpu_available(), "no OpenCL device available")
class TestCavityValidation(unittest.TestCase):
    def test_square_cavity_resonance_matches_the_analytic_value(self):
        from openantenna.gpu import opencl_fdtd

        result = opencl_fdtd.cavity_resonance(size_m=0.1, cells=60, steps=20000)
        self.assertLess(
            abs(result["relative_error_percent"]),
            2.0,
            msg=f"measured {result['measured_hz']/1e9:.4f} GHz vs analytic "
            f"{result['analytic_hz']/1e9:.4f} GHz",
        )
        self.assertLessEqual(result["courant_factor"], 1.0 + 1e-6)
        self.assertGreater(result["cell_updates_per_second"], 0.0)

    def test_smaller_grid_rejects_nonsense_parameters(self):
        from openantenna.gpu import opencl_fdtd

        with self.assertRaises(ValueError):
            opencl_fdtd.OpenCLFDTD2D(4, 4, 1e-3)
        with self.assertRaises(ValueError):
            opencl_fdtd.OpenCLFDTD2D(32, 32, 0.0)


if __name__ == "__main__":
    unittest.main()
