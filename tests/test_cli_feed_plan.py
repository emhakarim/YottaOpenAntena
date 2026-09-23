"""CLI tests for `feed-plan`: the corporate-feed drawing plan without a solver."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openantenna import cli


class TestFeedPlanCommand(unittest.TestCase):
    def test_a_2d_grid_reports_the_two_layer_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "plan.json"
            code = cli.main(
                ["feed-plan", "--rows", "4", "--cols", "4", "--pitch-mm", "60", "--json", str(target)]
            )
            self.assertEqual(code, 0)
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["kind"], "openantenna.feed-plan.2d")
        self.assertEqual(payload["n_leaves"], 16)
        self.assertEqual(sorted(payload["layers"]), ["feed", "patch", "via"])
        self.assertEqual(sum(payload["collisions"].values()), 0)
        self.assertLess(payload["input_point_mm"][1], payload["channel_y_mm"])
        self.assertTrue(payload["notes"])

    def test_a_single_row_uses_the_1d_planner(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "plan.json"
            code = cli.main(
                ["feed-plan", "--rows", "1", "--cols", "4", "--pitch-mm", "60", "--json", str(target)]
            )
            self.assertEqual(code, 0)
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["kind"], "openantenna.feed-plan.1d")
        self.assertEqual(payload["n_elements"], 4)
        self.assertGreater(payload["n_rectangles"], 0)

    def test_a_pitch_too_short_for_the_row_tree_fails_cleanly(self):
        code = cli.main(["feed-plan", "--rows", "4", "--cols", "4", "--pitch-mm", "20"])
        self.assertEqual(code, 1, "a refused geometry must exit non-zero, not raise")

    def test_a_non_power_of_two_count_fails_cleanly(self):
        code = cli.main(["feed-plan", "--rows", "1", "--cols", "3", "--pitch-mm", "60"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
