"""Tests for the heavy-run queue.

Two mistakes on 2026-09-22 are frozen here as tests, because both were invisible until the runs had
already burned hours:

* the queue called the batch harness without `--timeout-s`, so its 3600 s default killed three jobs
  at 36-55 % progress and the results were empty;
* a job that exits in seconds was still reported as `completed` (it had failed at startup, e.g. an
  interpreter without CSXCAD), which made an earlier queue claim four jobs it never ran.

Written with ``unittest`` only: CI runs the suite with no optional dependencies.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from yotta_tools import heavy_queue

BATCH_JOBS = [job for job in heavy_queue.JOBS if "parallel_batch.py" in " ".join(map(str, job["cmd"]))]


class TestJobSpecs(unittest.TestCase):
    def test_every_batch_job_overrides_the_harness_timeout(self) -> None:
        """The 3600 s harness default is far too short for a 1e-4 / 400k converged run."""
        self.assertTrue(BATCH_JOBS, "expected the queue to drive the batch harness at least once")
        for job in BATCH_JOBS:
            cmd = [str(x) for x in job["cmd"]]  # type: ignore[arg-type]
            with self.subTest(job=job["name"]):
                self.assertIn("--timeout-s", cmd, f"{job['name']}: relies on the harness default")
                timeout = float(cmd[cmd.index("--timeout-s") + 1])
                self.assertGreaterEqual(timeout, 10_800.0, f"{job['name']} is too short for 400k steps")

    def test_jobs_and_tags_are_unique(self) -> None:
        names = [job["name"] for job in heavy_queue.JOBS]
        self.assertEqual(len(names), len(set(names)))
        tags: list[str] = []
        for job in heavy_queue.JOBS:
            cmd = [str(x) for x in job["cmd"]]  # type: ignore[arg-type]
            if "--tag" in cmd:
                tags.append(cmd[cmd.index("--tag") + 1])
        self.assertEqual(len(tags), len(set(tags)), "two jobs would share a run directory")

    def test_every_job_has_a_wall_clock_limit_and_a_result_location(self) -> None:
        """Every job must say where its outcome lands; not every harness writes a JSON summary.

        The B2 rerun runs through `scripts/b2_coplanar_ab_test.py`, which reports in its stdout log
        instead of a summary file, so a ".json"-only assertion would be a false requirement.
        """
        for job in heavy_queue.JOBS:
            with self.subTest(job=job["name"]):
                self.assertGreater(float(job["hours"]), 0.0)
                self.assertTrue(str(job.get("summary") or "").strip(), "no result location declared")


class TestQueueBehaviour(unittest.TestCase):
    def test_plan_lists_without_running_anything(self) -> None:
        self.assertEqual(heavy_queue.main(["--list"]), 0)

    def test_a_job_that_ends_in_seconds_is_flagged_not_trusted(self) -> None:
        """An rc of 0 after two seconds means a startup failure, not success."""
        with tempfile.TemporaryDirectory() as tmp:
            entry = heavy_queue.run_job(
                {"name": "instant", "what": "exits immediately",
                 "cmd": [sys.executable, "-c", "print('nothing was simulated')"],
                 "hours": 0.01, "summary": None},
                Path(tmp),
            )
        self.assertTrue(str(entry["status"]).startswith("failed-fast"), entry["status"])
        self.assertTrue(entry["log_tail"], "the tail of the log must travel with the failure")

    def test_a_real_failure_keeps_its_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            entry = heavy_queue.run_job(
                {"name": "boom", "what": "fails",
                 "cmd": [sys.executable, "-c", "raise SystemExit(3)"],
                 "hours": 0.01, "summary": None},
                Path(tmp),
            )
        self.assertIn("exit 3", str(entry["status"]))


if __name__ == "__main__":
    unittest.main()
