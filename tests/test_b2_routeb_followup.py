"""Step D driver: winner parsing, flag building, and the verdict path without an engine run."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "b2_routeb_followup", ROOT / "scripts" / "b2_routeb_followup.py")
followup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(followup)

S11 = ("freq_hz,s11_re,s11_im\n"
       "2.42e9,0.90,0.0\n"
       "2.43e9,0.50,0.0\n"
       "2.44e9,0.01,0.0\n"
       "2.45e9,0.60,0.0\n"
       "2.46e9,0.80,0.0\n")


def _write_pair_tree(base: Path, tag: str = "p000", follow_log: str | None = None) -> None:
    """Fake sweep + follow-up run dirs: same s11, logs capped at 300k / 400k by default."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "winner.txt").write_text(tag + "\n", encoding="utf-8")
    (base / "sweep_summary.json").write_text(
        json.dumps({"points": [{"tag": tag, "delta_mm": 0.0}]}), encoding="utf-8")
    for rel, cap, text in (
        (tag, 300000, None),
        (f"followup/{tag}", 400000, follow_log),
    ):
        run = base / rel / "line"
        run.mkdir(parents=True)
        (run / "s11.csv").write_text(S11, encoding="utf-8")
        content = text if text is not None else (
            "Max. number of timesteps was reached\n  Timestep: {:,}\n".format(cap))
        (run / "run.stdout.log").write_text(content, encoding="utf-8")


class TestHelpers(unittest.TestCase):
    def test_delta_from_tag(self) -> None:
        self.assertEqual(followup.delta_from_tag("m100"), -1.0)
        self.assertEqual(followup.delta_from_tag("m050"), -0.5)
        self.assertEqual(followup.delta_from_tag("p000"), 0.0)
        self.assertEqual(followup.delta_from_tag("p100"), 1.0)
        with self.assertRaises(ValueError):
            followup.delta_from_tag("x123")

    def test_read_winner_prefers_summary_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "overlap"
            base.mkdir()
            (base / "winner.txt").write_text("m100\n", encoding="utf-8")
            (base / "sweep_summary.json").write_text(
                json.dumps({"points": [{"tag": "m100", "delta_mm": -1.0}]}), encoding="utf-8")
            self.assertEqual(followup.read_winner(base), ("m100", -1.0))

    def test_read_winner_falls_back_to_tag_and_refuses_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "overlap"
            base.mkdir()
            (base / "winner.txt").write_text("p050\n", encoding="utf-8")
            self.assertEqual(followup.read_winner(base), ("p050", 0.5))
            with self.assertRaises(FileNotFoundError):
                followup.read_winner(Path(tmp) / "nowhere")

    def test_build_cmd_flags(self) -> None:
        cmd = followup.build_cmd(0.5, Path("X"), 400000, 1e-4)
        self.assertIn("--arm", cmd)
        self.assertEqual(cmd[cmd.index("--arm") + 1], "line")
        self.assertEqual(cmd[cmd.index("--inset-delta-mm") + 1], "0.5")
        self.assertEqual(cmd[cmd.index("--max-ts") + 1], "400000")
        self.assertIn("--run", cmd)


class TestMain(unittest.TestCase):
    def test_write_only_lists_command_without_creating_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "overlap"
            base.mkdir()
            (base / "winner.txt").write_text("p000\n", encoding="utf-8")
            rc = followup.main(["--base-out", str(base)])
            self.assertEqual(rc, 0)
            self.assertFalse((base / "followup").exists())

    def test_refuses_without_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc = followup.main(["--run", "--base-out", str(Path(tmp) / "overlap")])
            self.assertEqual(rc, 2)

    def test_engine_skip_and_route_b_verdict_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "runs_b2" / "overlap"
            _write_pair_tree(base)
            rc = followup.main(["--run", "--base-out", str(base)])
            self.assertEqual(rc, 0)
            verdict_path = base / "followup" / "verdict_p000_sweep300000_vs_400000.json"
            data = json.loads(verdict_path.read_text(encoding="utf-8"))
            self.assertEqual(data["verdict"], "accepted")
            self.assertEqual(data["policy_route"], "truncation")
            self.assertTrue(data["quotable"])
            self.assertIn("truncation-stable", data["quote_caveat"])
            sentinel = (base.parent / "overlap_followup_done.txt").read_text(encoding="utf-8")
            self.assertIn("verdict=accepted", sentinel)

    def test_mixed_stop_conditions_rejected_without_engine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "runs_b2" / "overlap"
            _write_pair_tree(base, follow_log="Time for 12,345 iterations\n")
            rc = followup.main(["--run", "--base-out", str(base)])
            self.assertEqual(rc, 0)
            verdict_path = base / "followup" / "verdict_p000_sweep300000_vs_400000.json"
            data = json.loads(verdict_path.read_text(encoding="utf-8"))
            self.assertEqual(data["verdict"], "rejected")
            self.assertFalse(data["quotable"])
            self.assertTrue(any("mixed stop conditions" in reason for reason in data["reasons"]))


if __name__ == "__main__":
    unittest.main()
