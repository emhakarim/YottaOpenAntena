"""Tests for the Phase 4 optimiser (stdlib-only differential evolution)."""

from __future__ import annotations

import math
import unittest

from openantenna.sweep.optimise import differential_evolution


def _sphere(params):
    return sum(value * value for value in params.values())


class TestDifferentialEvolution(unittest.TestCase):
    def test_finds_the_minimum_of_a_sphere(self):
        result = differential_evolution(
            _sphere,
            {"x": (-5.0, 5.0), "y": (-5.0, 5.0)},
            seed=7,
            max_generations=120,
        )
        self.assertLess(result.best_value, 1e-8)
        self.assertLess(abs(result.best_params["x"]), 1e-3)
        self.assertLess(abs(result.best_params["y"]), 1e-3)
        self.assertEqual(result.failed_evaluations, 0)

    def test_bounds_are_respected_when_the_minimum_lies_outside_them(self):
        result = differential_evolution(
            _sphere, {"x": (2.0, 4.0)}, seed=3, max_generations=80
        )
        self.assertGreaterEqual(result.best_params["x"], 2.0)
        self.assertLessEqual(result.best_params["x"], 4.0)
        self.assertAlmostEqual(result.best_params["x"], 2.0, places=2)

    def test_the_same_seed_gives_the_same_answer(self):
        first = differential_evolution(_sphere, {"x": (-3.0, 3.0)}, seed=11, max_generations=40)
        second = differential_evolution(_sphere, {"x": (-3.0, 3.0)}, seed=11, max_generations=40)
        self.assertEqual(first.best_params, second.best_params)
        self.assertEqual(first.history, second.history)

    def test_a_different_seed_is_allowed_to_differ(self):
        first = differential_evolution(_sphere, {"x": (-3.0, 3.0)}, seed=1, max_generations=40)
        second = differential_evolution(_sphere, {"x": (-3.0, 3.0)}, seed=2, max_generations=40)
        self.assertLess(first.best_value, 1e-6)
        self.assertLess(second.best_value, 1e-6)

    def test_failed_evaluations_are_counted_and_reported(self):
        def flaky(params):
            if params["x"] < 0.0:
                raise RuntimeError("no solution here")
            return abs(params["x"] - 1.0)

        result = differential_evolution(flaky, {"x": (-5.0, 5.0)}, seed=5, max_generations=60)
        self.assertGreater(result.failed_evaluations, 0)
        self.assertIn("failed", result.notes)
        self.assertFalse(result.all_evaluations_failed)
        self.assertAlmostEqual(result.best_params["x"], 1.0, places=2)

    def test_an_objective_that_always_fails_is_flagged_not_hidden(self):
        def broken(params):
            raise ValueError("always")

        result = differential_evolution(broken, {"x": (0.0, 1.0)}, seed=1, max_generations=10)
        self.assertTrue(result.all_evaluations_failed)
        self.assertIn("do not read", result.notes)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            differential_evolution(_sphere, {})
        with self.assertRaises(ValueError):
            differential_evolution(_sphere, {"x": (1.0, 1.0)})
        with self.assertRaises(ValueError):
            differential_evolution(_sphere, {"x": (0.0, 1.0)}, popsize=2)
        with self.assertRaises(ValueError):
            differential_evolution(_sphere, {"x": (0.0, 1.0)}, max_generations=0)

    def test_the_history_is_monotone(self):
        result = differential_evolution(_sphere, {"x": (-4.0, 4.0)}, seed=9, max_generations=50)
        for earlier, later in zip(result.history, result.history[1:]):
            self.assertLessEqual(later, earlier + 1e-12)
        self.assertLessEqual(len(result.history), result.generations + 1)

    def test_rosenbrock_is_reached_from_a_loose_start(self):
        def rosenbrock(params):
            x, y = params["x"], params["y"]
            return (1.0 - x) ** 2 + 100.0 * (y - x * x) ** 2

        result = differential_evolution(
            rosenbrock,
            {"x": (-3.0, 3.0), "y": (-3.0, 3.0)},
            seed=4,
            max_generations=400,
            popsize=20,
        )
        self.assertLess(result.best_value, 1e-6)
        self.assertTrue(math.isfinite(result.best_value))


if __name__ == "__main__":
    unittest.main()
