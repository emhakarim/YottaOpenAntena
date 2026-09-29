"""Pure helpers of the overlap sweep: directory tags, delta parsing, winner pick."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "b2_overlap_sweep", ROOT / "scripts" / "b2_overlap_sweep.py")
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)


class TestTags(unittest.TestCase):
    def test_tags_are_stable(self) -> None:
        self.assertEqual(sweep.tag_for(-1.0), "m100")
        self.assertEqual(sweep.tag_for(-0.5), "m050")
        self.assertEqual(sweep.tag_for(0.0), "p000")
        self.assertEqual(sweep.tag_for(0.25), "p025")
        self.assertEqual(sweep.tag_for(1.0), "p100")

    def test_parse_deltas_ignores_whitespace_and_empties(self) -> None:
        self.assertEqual(
            sweep.parse_deltas(" -1.0, -0.5 ,0, 0.5,1.0 "), (-1.0, -0.5, 0.0, 0.5, 1.0))


class TestWinner(unittest.TestCase):
    def test_deepest_inside_the_band_wins(self) -> None:
        rows = [
            {"tag": "m100", "resonance_ghz": 2.51, "s11_db": -30.0},
            {"tag": "p000", "resonance_ghz": 2.44, "s11_db": -12.0},
            {"tag": "p050", "resonance_ghz": 2.45, "s11_db": -20.0},
        ]
        winner = sweep.pick_winner(rows)
        self.assertIsNotNone(winner)
        self.assertEqual(winner["tag"], "p050")

    def test_none_when_nobody_is_in_the_band(self) -> None:
        rows = [{"tag": "m100", "resonance_ghz": 2.39, "s11_db": -30.0},
                {"tag": "p100", "resonance_ghz": 2.51, "s11_db": -40.0}]
        self.assertIsNone(sweep.pick_winner(rows))

    def test_errors_and_missing_values_never_win(self) -> None:
        rows = [{"tag": "bad", "resonance_ghz": None, "s11_db": None},
                {"tag": "ok", "resonance_ghz": 2.45, "s11_db": -10.0}]
        winner = sweep.pick_winner(rows)
        self.assertIsNotNone(winner)
        self.assertEqual(winner["tag"], "ok")


if __name__ == "__main__":
    unittest.main()
