"""CLI tests for `optimise`: analytic targeting, no solver."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openantenna import cli


class TestOptimiseCommand(unittest.TestCase):
    def test_the_cavity_predictor_hits_a_2_45_ghz_target(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "opt.json"
            code = cli.main(
                [
                    "optimise",
                    "--target-hz", "2.45e9",
                    "--predictor", "cavity",
                    "--json", str(target),
                ]
            )
            self.assertEqual(code, 0)
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["kind"], "openantenna.optimise")
        self.assertLess(payload["relative_error"], 1e-6)
        self.assertAlmostEqual(payload["predicted_hz"] / 2.45e9, 1.0, places=6)
        self.assertIn("not a solver", payload["warning"])

    def test_the_two_predictors_disagree_so_the_choice_matters(self):
        lengths = {}
        for predictor in ("cavity", "transmission-line"):
            with tempfile.TemporaryDirectory() as folder:
                target = Path(folder) / "opt.json"
                self.assertEqual(
                    cli.main(
                        [
                            "optimise",
                            "--target-hz", "2.45e9",
                            "--predictor", predictor,
                            "--json", str(target),
                        ]
                    ),
                    0,
                )
                lengths[predictor] = json.loads(target.read_text(encoding="utf-8"))["length_tuned_m"]
        relative = abs(lengths["cavity"] - lengths["transmission-line"]) / lengths["cavity"]
        self.assertGreater(relative, 1e-3, "the two models should not agree to a tenth of a percent")

    def test_bad_inputs_exit_cleanly(self):
        self.assertEqual(cli.main(["optimise", "--target-hz", "0"]), 1)
        self.assertEqual(cli.main(["optimise", "--target-hz", "2.45e9", "--height-mm", "0"]), 1)
        self.assertEqual(
            cli.main(["optimise", "--target-hz", "2.45e9", "--length-span", "1.5"]), 1
        )


if __name__ == "__main__":
    unittest.main()
