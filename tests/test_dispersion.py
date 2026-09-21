"""Tests for the Debye / Lorentz / Drude dispersion models and the Debye fit."""

from __future__ import annotations

import math
import unittest

from openantenna.materials import dispersion
from openantenna.materials.library import Material, complex_relative_permittivity

EPS_INF = 2.1
DELTA_EPS = 0.4
TAU = 1.0e-8


class TestDebye(unittest.TestCase):
    def test_static_limit_recovers_eps_s(self):
        value = dispersion.debye_eps(1.0e-3, EPS_INF, DELTA_EPS, TAU, 0.0)
        self.assertAlmostEqual(value.real, EPS_INF + DELTA_EPS, places=2)

    def test_high_frequency_limit_recovers_eps_inf(self):
        value = dispersion.debye_eps(1.0e14, EPS_INF, DELTA_EPS, TAU, 0.0)
        self.assertAlmostEqual(value.real, EPS_INF, places=2)

    def test_loss_is_maximal_around_the_relaxation_frequency(self):
        f_relax = 1.0 / (2.0 * math.pi * TAU)
        at_relax = abs(dispersion.debye_eps(f_relax, EPS_INF, DELTA_EPS, TAU, 0.0).imag)
        far_below = abs(dispersion.debye_eps(f_relax / 100.0, EPS_INF, DELTA_EPS, TAU, 0.0).imag)
        far_above = abs(dispersion.debye_eps(f_relax * 100.0, EPS_INF, DELTA_EPS, TAU, 0.0).imag)
        self.assertGreater(at_relax, far_below)
        self.assertGreater(at_relax, far_above)

    def test_real_part_decreases_with_frequency(self):
        low = dispersion.debye_eps(1.0e6, EPS_INF, DELTA_EPS, TAU, 0.0).real
        high = dispersion.debye_eps(1.0e9, EPS_INF, DELTA_EPS, TAU, 0.0).real
        self.assertLess(high, low)

    def test_dc_conductivity_adds_loss(self):
        without = dispersion.debye_eps(1.0e8, EPS_INF, DELTA_EPS, TAU, 0.0)
        with_sigma = dispersion.debye_eps(1.0e8, EPS_INF, DELTA_EPS, TAU, 1.0e-3)
        self.assertGreater(abs(with_sigma.imag), abs(without.imag))


class TestLorentzAndDrude(unittest.TestCase):
    def test_lorentz_shows_a_resonance(self):
        at_res = abs(dispersion.lorentz_eps(1.0e9, 2.0, 1.0, 1.0e9, 5.0e7).imag)
        off_res = abs(dispersion.lorentz_eps(5.0e9, 2.0, 1.0, 1.0e9, 5.0e7).imag)
        self.assertGreater(at_res, off_res)

    def test_drude_is_metallic_at_low_frequency(self):
        value = dispersion.drude_eps(1.0e9, 1.0, 1.0e12, 1.0e10)
        self.assertLess(value.real, 0.0)

    def test_invalid_frequency_is_rejected(self):
        with self.assertRaises(ValueError):
            dispersion.debye_eps(0.0, EPS_INF, DELTA_EPS, TAU, 0.0)
        with self.assertRaises(ValueError):
            dispersion.drude_eps(-1.0, 1.0, 1.0e12)


class TestDebyeFit(unittest.TestCase):
    """Recover known Debye parameters from synthetic data."""

    def setUp(self):
        self.freqs = [10.0 ** (6.0 + 4.0 * i / 24.0) for i in range(25)]
        values = [dispersion.debye_eps(f, EPS_INF, DELTA_EPS, TAU, 0.0) for f in self.freqs]
        self.eps_real = [v.real for v in values]
        self.eps_imag = [abs(v.imag) for v in values]

    def test_fit_recovers_the_relaxation_time(self):
        result = dispersion.fit_debye_1pole(self.freqs, self.eps_real, self.eps_imag)
        self.assertTrue(result.is_physical)
        ratio = result.params.tau_s / TAU
        self.assertGreater(ratio, 0.5)
        self.assertLess(ratio, 2.0)

    def test_fit_residual_is_small(self):
        result = dispersion.fit_debye_1pole(self.freqs, self.eps_real, self.eps_imag)
        self.assertLess(result.rmse_total, 0.05)

    def test_complex_wrapper_round_trips(self):
        """Y-01: the wrapper used to forward eps'' with the wrong sign.

        debye_eps() returns a negative imaginary part while fit_debye_1pole()
        expects a positive loss term; the wrapper must convert, not forward.
        """
        freqs = [10.0 ** (6.0 + 4.0 * i / 24.0) for i in range(25)]
        samples = [dispersion.debye_eps(f, EPS_INF, DELTA_EPS, TAU, 0.0) for f in freqs]
        result = dispersion.fit_debye_from_complex(freqs, samples)
        self.assertTrue(result.is_physical)
        self.assertLess(result.rmse_total, 0.01)
        self.assertAlmostEqual(result.params.eps_inf, EPS_INF, delta=0.05)
        self.assertAlmostEqual(result.params.delta_eps, DELTA_EPS, delta=0.05)
        ratio = result.params.tau_s / TAU
        self.assertGreater(ratio, 0.5)
        self.assertLess(ratio, 2.0)

    def test_fit_result_is_serialisable(self):
        result = dispersion.fit_debye_1pole(self.freqs, self.eps_real, self.eps_imag)
        payload = result.to_dict()
        self.assertIn("params", payload)
        self.assertIn("tau_s", payload["params"])


class TestLossSignConvention(unittest.TestCase):
    def test_passive_material_has_negative_imaginary_part(self):
        """Mutation guard T-3: the sign of tan delta must not flip.

        With the eps = eps' - j*eps'' convention, a passive lossy material must have
        a NEGATIVE imaginary part and a POSITIVE loss tangent.
        """
        from openantenna.materials.library import Material, complex_relative_permittivity

        lossy = Material(name="lossy", epsilon_r=4.4, tan_delta=0.02)
        eps = complex_relative_permittivity(lossy, 1.0e9)
        self.assertLess(eps.imag, 0.0)
        self.assertAlmostEqual(-eps.imag / eps.real, 0.02, places=12)

        lossless = Material(name="lossless", epsilon_r=4.4, tan_delta=0.0)
        self.assertEqual(complex_relative_permittivity(lossless, 1.0e9).imag, 0.0)

    def test_conduction_loss_has_the_same_sign(self):
        from openantenna.materials.library import Material, complex_relative_permittivity

        conductor = Material(name="c", epsilon_r=1.0, conductivity_s_per_m=5.8e7, kind="conductor")
        eps = complex_relative_permittivity(conductor, 1.0e9)
        self.assertLess(eps.imag, 0.0)


class TestMaterialsWithDispersion(unittest.TestCase):
    def test_dispersive_material_ignores_the_static_epsilon(self):
        material = Material(
            name="composite-A",
            epsilon_r=6.0,
            tan_delta=0.002,
            dispersion={
                "model": "debye",
                "eps_inf": 4.0,
                "delta_eps": 2.0,
                "tau_s": 1.0e-9,
                "sigma_dc_s_per_m": 0.0,
            },
        )
        low = complex_relative_permittivity(material, 1.0e6)
        high = complex_relative_permittivity(material, 1.0e12)
        self.assertGreater(low.real, high.real)
        self.assertAlmostEqual(high.real, 4.0, places=1)

    def test_static_material_uses_epsilon_and_loss_tangent(self):
        material = Material(name="PTFE-like", epsilon_r=2.1, tan_delta=4e-4)
        value = complex_relative_permittivity(material, 3.0e9)
        self.assertAlmostEqual(value.real, 2.1, places=9)
        self.assertAlmostEqual(abs(value.imag), 2.1 * 4e-4, places=9)


if __name__ == "__main__":
    unittest.main()
