"""Phase 2 item 1, engine-limited path: piecewise-kappa loss model + Debye recovery."""

from __future__ import annotations

import math
import unittest

from yotta_tools import loss_fit

# A representative lossy substrate: FR-4-like.
EPS_S = 4.6
EPS_INF = 4.0
TAU = 1.0 / (2.0 * math.pi * 2.0e9)  # relaxation at 2 GHz


class TestDebyeBasics(unittest.TestCase):
    def test_loss_tangent_peaks_near_relaxation(self):
        peak = max(
            (loss_fit.debye_tan_delta(f, EPS_S, EPS_INF, TAU) for f in [1e8 * 1.05**k for k in range(60)])
        )
        at_relaxation = loss_fit.debye_tan_delta(1.0 / (2.0 * math.pi * TAU), EPS_S, EPS_INF, TAU)
        self.assertGreater(peak, 0.0)
        self.assertLess(abs(peak - at_relaxation) / peak, 0.05)

    def test_loss_tangent_decays_far_above_relaxation(self):
        low = loss_fit.debye_tan_delta(1e8, EPS_S, EPS_INF, TAU)
        high = loss_fit.debye_tan_delta(1e12, EPS_S, EPS_INF, TAU)
        self.assertLess(high, low)


class TestKappaRoundTrip(unittest.TestCase):
    def test_kappa_reproduces_its_own_tangent(self):
        f0 = 2.45e9
        tan = loss_fit.debye_tan_delta(f0, EPS_S, EPS_INF, TAU)
        kappa = loss_fit.kappa_for_tan_delta(f0, EPS_INF, tan)
        # kappa is flat, so the tangent it represents falls as 1/f - exactly the model
        # openantenna/solvers/openems.py uses.
        for f in (1.0e9, 2.45e9, 6.0e9):
            got = kappa / (2.0 * math.pi * f * loss_fit.EPS0 * EPS_INF)
            self.assertAlmostEqual(got, tan * f0 / f, places=12)

    def test_zero_frequency_is_rejected(self):
        with self.assertRaises(ValueError):
            loss_fit.kappa_for_tan_delta(0.0, EPS_INF, 0.01)


class TestPiecewise(unittest.TestCase):
    BAND = [1.0e9, 1.5e9, 2.0e9, 3.0e9, 4.0e9, 6.0e9]
    GRID = [f for f in (1.0e9 * (6.0 ** (k / 40.0)) for k in range(41))]

    def test_more_bands_never_help_less(self):
        three = loss_fit.piecewise_kappa(self.BAND[::2], EPS_S, EPS_INF, TAU)
        five = loss_fit.piecewise_kappa(self.BAND, EPS_S, EPS_INF, TAU)
        e3 = loss_fit.piecewise_error(self.GRID, three, EPS_S, EPS_INF, TAU)[0]
        e5 = loss_fit.piecewise_error(self.GRID, five, EPS_S, EPS_INF, TAU)[0]
        self.assertLessEqual(e5, e3 + 1e-12, "adding band edges must not make it worse")

    def test_error_is_quantified_and_bounded(self):
        bands = loss_fit.piecewise_kappa(self.BAND, EPS_S, EPS_INF, TAU)
        worst, mean, points = loss_fit.piecewise_error(self.GRID, bands, EPS_S, EPS_INF, TAU)
        self.assertEqual(len(points), len(self.GRID))
        self.assertGreater(mean, 0.0, "the approximation is not exact - that is the point")
        # 5 bands over 1-6 GHz cannot follow the relaxation peak (2 GHz) - the honest
        # expectation is a worst case in the tens of percent, and the module's job is to
        # quantify it, not to hide it.
        self.assertLess(worst, 0.45)
        self.assertGreater(worst, 0.25, "if it were tiny, this test banding would be wrong")

    def test_refining_bands_near_the_peak_actually_helps(self):
        edges = [1.0e9 * (6.0 ** (k / 16.0)) for k in range(17)]  # 17 bands, same span
        bands = loss_fit.piecewise_kappa(edges, EPS_S, EPS_INF, TAU)
        worst, _mean, _pts = loss_fit.piecewise_error(self.GRID, bands, EPS_S, EPS_INF, TAU)
        self.assertLess(worst, 0.12, "17 bands over the same span track the peak closely")

    def test_bands_must_be_increasing(self):
        with self.assertRaises(ValueError):
            loss_fit.piecewise_kappa([2e9, 1e9], EPS_S, EPS_INF, TAU)
        with self.assertRaises(ValueError):
            loss_fit.piecewise_kappa([1e9], EPS_S, EPS_INF, TAU)


class TestDebyeRecovery(unittest.TestCase):
    GRID = [1.0e9 * (8.0 ** (k / 30.0)) for k in range(31)]

    def test_recovers_a_known_relaxation(self):
        tans = [loss_fit.debye_tan_delta(f, EPS_S, EPS_INF, TAU) for f in self.GRID]
        eps_s, eps_inf, tau, residual = loss_fit.fit_debye(self.GRID, tans, eps_inf_hint=EPS_INF)
        self.assertAlmostEqual(tau, TAU, delta=TAU * 0.25, msg="tau should be recovered")
        self.assertAlmostEqual(eps_s, EPS_S, delta=0.35, msg="eps_s should be recovered")
        self.assertLess(residual, 0.01)

    def test_fit_rejects_a_short_series(self):
        with self.assertRaises(ValueError):
            loss_fit.fit_debye([1e9, 2e9], [0.01, 0.02])


if __name__ == "__main__":
    unittest.main()
