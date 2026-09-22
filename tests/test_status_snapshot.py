"""Tests for the live-status tool.

The bug frozen here cost five hours of silence: a killed run leaves its last progress line in its log
for ever, so a tool that trusts the text reports dead runs as live. A monitoring job was built on top
of that and therefore never fired. Liveness now comes from the log's modification time.

Written with ``unittest`` only (CI has no pytest and no optional dependencies).
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from yotta_tools import status_snapshot


def write_engine_log(path: Path, step: int, speed: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"[@  10m00s] Timestep: {step:,} || Speed: {speed:.1f} MC/s (2.0e-02 s/TS) || Energy: ~1e-11\n",
        encoding="utf-8",
    )
    return path


class TestParsing(unittest.TestCase):
    def test_engine_state_reads_the_last_timestep_and_speed(self) -> None:
        lines = ["Timestep:      12345 || Speed:  10.0 MC/s",
                 "Timestep:      67890 || Speed:  32.5 MC/s"]
        self.assertEqual(status_snapshot.engine_state(lines), {"step": 67890, "speed_mc_s": 32.5})

    def test_b2_progress_line_is_parsed_including_commas(self) -> None:
        line = ("[progress] [####----]  14.3% of the 400,000-step cap  step 57,358/400,000  "
                "16.0 MCells/s  elapsed 22m03s  worst case 2h11m more")
        self.assertEqual(
            status_snapshot.b2_state([line]),
            {"step": 57358, "cap": 400000, "speed_mc_s": 16.0, "eta_left": "2h11m"},
        )

    def test_pct_handles_missing_values(self) -> None:
        self.assertEqual(status_snapshot.pct(None, 400_000), "-")
        self.assertEqual(status_snapshot.pct(200_000, None), "-")
        self.assertEqual(status_snapshot.pct(200_000, 400_000), "50.0 %")


class TestLiveness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def snapshot(self) -> dict:
        with mock.patch.object(status_snapshot, "REPO", self.repo):
            self.assertEqual(status_snapshot.main([]), 0)
        return json.loads((self.repo / "runs" / "status_snapshot.json").read_text(encoding="utf-8"))

    def test_a_stale_log_is_reported_as_not_live(self) -> None:
        """The exact situation that fooled the first watcher."""
        log = write_engine_log(self.repo / "runs" / "batch_dead" / "run.stdout.log", 146_356, 32.5)
        old = time.time() - (2 * status_snapshot.STALE_AFTER_S)
        os.utime(log, (old, old))

        snapshot = self.snapshot()
        self.assertEqual(snapshot["live_count"], 0)
        self.assertFalse(snapshot["runs"][0]["live"])
        self.assertGreaterEqual(snapshot["runs"][0]["log_age_s"], status_snapshot.STALE_AFTER_S)

    def test_a_fresh_log_is_reported_as_live(self) -> None:
        write_engine_log(self.repo / "runs" / "batch_live" / "run.stdout.log", 200_000, 30.0)

        snapshot = self.snapshot()
        self.assertEqual(snapshot["live_count"], 1)
        self.assertTrue(snapshot["runs"][0]["live"])
        self.assertEqual(snapshot["runs"][0]["progress"], "50.0 %")

    def test_the_cap_is_stated_as_a_ceiling_not_a_countdown(self) -> None:
        write_engine_log(self.repo / "runs" / "batch_live" / "run.stdout.log", 1_000, 30.0)

        snapshot = self.snapshot()
        self.assertIn("EndCriteria", snapshot["note"])
        row = snapshot["runs"][0]
        self.assertTrue(math.isclose(row["step"] / row["cap"], 0.0025, rel_tol=1e-3))

    def test_live_count_reaches_the_file(self) -> None:
        """A monitoring job reads live_count out of the JSON, so it must be written, not printed."""
        write_engine_log(self.repo / "runs" / "batch_live" / "run.stdout.log", 10_000, 30.0)
        write_engine_log(self.repo / "runs" / "batch_dead" / "run.stdout.log", 10_000, 30.0)
        dead = self.repo / "runs" / "batch_dead" / "run.stdout.log"
        old = time.time() - (3 * status_snapshot.STALE_AFTER_S)
        os.utime(dead, (old, old))

        snapshot = self.snapshot()
        self.assertEqual(snapshot["live_count"], 1)
        self.assertEqual(snapshot["stale_count"], 1)


if __name__ == "__main__":
    unittest.main()
