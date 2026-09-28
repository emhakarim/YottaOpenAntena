"""Tests for the named-parameter expressions behind the sketch's "add parameter" table."""

from __future__ import annotations

import unittest

from openantenna.geometry.params import (
    ParameterError,
    ParameterTable,
    UnknownName,
    evaluate_expression,
)


class TestExpressionEvaluation(unittest.TestCase):
    def test_precedence_and_parentheses(self):
        self.assertAlmostEqual(evaluate_expression("1 + 2 * 3", {}), 7.0)
        self.assertAlmostEqual(evaluate_expression("(1 + 2) * 3", {}), 9.0)
        self.assertAlmostEqual(evaluate_expression("2 ** 3 ** 2", {}), 512.0)  # right-associative

    def test_unary_minus_binds_like_python(self):
        self.assertAlmostEqual(evaluate_expression("-2 ** 2", {}), -4.0)
        self.assertAlmostEqual(evaluate_expression("-(2 + 3)", {}), -5.0)

    def test_names_resolve_and_unknown_names_say_which(self):
        self.assertAlmostEqual(evaluate_expression("L / 2", {"L": 20.0}), 10.0)
        with self.assertRaises(UnknownName) as caught:
            evaluate_expression("L + w", {"L": 20.0})
        self.assertIn("'w'", str(caught.exception))

    def test_division_by_zero_and_non_real_powers_are_refused(self):
        with self.assertRaises(ParameterError) as caught:
            evaluate_expression("1 / 0", {})
        self.assertIn("division by zero", str(caught.exception))
        with self.assertRaises(ParameterError):
            evaluate_expression("(-1) ** 0.5", {})

    def test_calls_attributes_strings_and_other_syntax_are_refused(self):
        for hostile in ("__import__('os')", "a.b", "[1, 2]", "'text'", "2 if 1 else 3", "{1: 2}"):
            with self.subTest(expression=hostile):
                with self.assertRaises(ParameterError):
                    evaluate_expression(hostile, {})

    def test_booleans_are_not_numbers(self):
        with self.assertRaises(ParameterError):
            evaluate_expression("True", {})

    def test_pathological_nesting_is_a_parameter_error_not_a_crash(self):
        for depth in (500, 5000):
            with self.subTest(depth=depth):
                expression = "(" * depth + "1" + ")" * depth
                with self.assertRaises(ParameterError):
                    evaluate_expression(expression, {})


class TestParameterTable(unittest.TestCase):
    def test_forward_references_resolve(self):
        table = ParameterTable([("h", "L / 8"), ("L", "30")])
        values, errors = table.resolve()
        self.assertEqual(errors, {})
        self.assertAlmostEqual(values["L"], 30.0)
        self.assertAlmostEqual(values["h"], 3.75)

    def test_circular_references_are_reported_not_guessed(self):
        table = ParameterTable([("a", "b + 1"), ("b", "a + 1")])
        values, errors = table.resolve()
        self.assertEqual(values, {})
        self.assertIn("a", errors)
        self.assertIn("b", errors)
        self.assertIn("circular", errors["a"])

    def test_a_syntax_error_is_reported_per_name_without_killing_the_rest(self):
        table = ParameterTable([("good", "2"), ("bad", "2 +")])
        values, errors = table.resolve()
        self.assertAlmostEqual(values["good"], 2.0)
        self.assertIn("bad", errors)

    def test_set_replaces_in_place_and_remove_deletes(self):
        table = ParameterTable([("L", "10"), ("W", "L")])
        table.set("L", "20")
        values, _ = table.resolve()
        self.assertAlmostEqual(values["W"], 20.0)
        self.assertEqual([name for name, _ in table.entries], ["L", "W"])
        table.remove("L")
        self.assertEqual([name for name, _ in table.entries], ["W"])

    def test_an_invalid_name_is_flagged(self):
        table = ParameterTable([("2bad", "1")])
        values, errors = table.resolve()
        self.assertEqual(values, {})
        self.assertIn("2bad", errors)


if __name__ == "__main__":
    unittest.main()
