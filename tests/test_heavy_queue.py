"""Tests for the heavy-run queue.

Two mistakes on 2026-09-22 are frozen here as tests, because both were invisible until the runs had
already burned hours:

* the queue called the batch harness without `--timeout-s`, so its 3600 s default killed three jobs
  at 36-55 % progress and the results were empty;
* a job that exits in seconds was still reported as `completed` (it had failed at startup, e.g. an
  interpreter without CSXCAD), which made an earlier queue claim four jobs it never ran;
* a job can exit zero and still leave no artefacts (2026-09-28 risk audit, finding #1), so the
  declared result location is verified - a summary file, or arm by arm for directory summaries -
  and a zero-exit job without artefacts is downgraded to `completed-without-result`.

Written with ``unittest`` only: CI runs the suite with no optional dependencies.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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


class TestArtefactVerification(unittest.TestCase):
    """The 2026-09-28 risk audit, finding #1: an exit code is not an artefact."""

    def _make_arm(self, parent: Path, name: str, rows: int = 5, *, with_csv: bool = True,
                  with_summary_json: bool = True) -> Path:
        arm = parent / name
        arm.mkdir(parents=True, exist_ok=True)
        if with_csv:
            lines = ["freq_hz,s11_re,s11_im"] + [f"{2.0e9 + i * 1e6},0.1,-0.0" for i in range(rows)]
            (arm / "s11.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        if with_summary_json:
            (arm / "run_summary.json").write_text('{"solver": "openEMS"}', encoding="utf-8")
        return arm

    def test_directory_summary_verifies_each_arm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_arm(root, "line")
            self._make_arm(root, "probe")
            entry: dict = {"job": "b2x", "what": "dir arms", "status": "completed", "summary": None}
            heavy_queue.collect_summary({"name": "b2x", "summary": str(root)}, entry)
            self.assertEqual(entry["summary"], str(root))
            self.assertEqual(len(entry["arms"]), 2)  # type: ignore[arg-type]
            self.assertNotIn("summary_error", entry)
            self.assertEqual(entry["status"], "completed", "verified artefacts keep the status")

    def test_directory_summary_with_a_missing_arm_downgrades_the_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_arm(root, "line")
            self._make_arm(root, "probe", with_csv=False)
            entry: dict = {"job": "b2x", "what": "dir arms", "status": "completed", "summary": None}
            heavy_queue.collect_summary({"name": "b2x", "summary": str(root)}, entry)
            self.assertIn("probe", str(entry.get("summary_error", "")))
            self.assertEqual(entry["status"], "completed-without-result")

    def test_a_declared_summary_that_was_never_written_downgrades_the_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            entry: dict = {"job": "x", "what": "never wrote", "status": "completed", "summary": None}
            heavy_queue.collect_summary({"name": "x", "summary": str(Path(tmp) / "nope.json")}, entry)
            self.assertIn("not found", str(entry.get("summary_error", "")))
            self.assertEqual(entry["status"], "completed-without-result")

    def test_a_terminated_job_is_not_re_flagged(self) -> None:
        # terminated jobs are already never counted as results; the downgrade is only for
        # jobs that claimed success (status == "completed")
        with tempfile.TemporaryDirectory() as tmp:
            entry: dict = {"job": "x", "what": "killed",
                           "status": "terminated after 6 h (wall-clock limit; taskkill)", "summary": None}
            heavy_queue.collect_summary({"name": "x", "summary": str(Path(tmp) / "nope.json")}, entry)
            self.assertTrue(str(entry["status"]).startswith("terminated"))


class TestKillTree(unittest.TestCase):
    """The 2026-09-28 risk audit, finding #2: a direct kill leaves orphan workers."""

    def test_windows_kill_uses_taskkill_on_the_tree(self) -> None:
        calls: list = []

        class _Done:
            returncode = 0

        def fake_run(cmd, **kwargs):  # noqa: ANN001 - test double
            calls.append([str(x) for x in cmd])
            return _Done()

        fake_proc = SimpleNamespace(pid=4242, kill=lambda: calls.append(["direct"]))
        with mock.patch.object(heavy_queue.subprocess, "run", fake_run):
            note = heavy_queue.kill_process_tree(fake_proc, platform="nt")  # type: ignore[arg-type]
        self.assertEqual(calls[0], ["taskkill", "/PID", "4242", "/T", "/F"])
        self.assertIn("taskkill", note)

    def test_posix_kill_falls_back_to_a_direct_kill(self) -> None:
        fake_proc = SimpleNamespace(pid=4242, kill=lambda: None)
        with mock.patch("yotta_tools.heavy_queue.os.getpgid", create=True, return_value=777), \
                mock.patch("yotta_tools.heavy_queue.os.killpg", create=True, side_effect=OSError("nope")):
            note = heavy_queue.kill_process_tree(fake_proc, platform="posix")  # type: ignore[arg-type]
        self.assertIn("direct kill", note)


if __name__ == "__main__":
    unittest.main()
