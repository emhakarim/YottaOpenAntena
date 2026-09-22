"""Tests for the heavy-run queue.

Two mistakes on 2026-09-22 are frozen here as tests, because both were invisible until the runs had
already burned hours:

* the queue called the batch harness without `--timeout-s`, so its 3600 s default killed three jobs
  at 36-55 % progress and the results were empty;
* a job that exits in seconds was still reported as `completed` (it had failed at startup, e.g. an
  interpreter without CSXCAD), which made an earlier queue claim four jobs it never ran.
"""

from __future__ import annotations

import sys
from pathlib import Path

from yotta_tools import heavy_queue


def test_every_batch_job_overrides_the_harness_timeout() -> None:
    """The 3600 s harness default is far too short for a 1e-4 / 400k converged run."""
    batch_jobs = [job for job in heavy_queue.JOBS if "parallel_batch.py" in " ".join(map(str, job["cmd"]))]
    assert batch_jobs, "expected the queue to drive the batch harness at least once"
    for job in batch_jobs:
        cmd = [str(x) for x in job["cmd"]]  # type: ignore[arg-type]
        assert "--timeout-s" in cmd, f"{job['name']}: relies on the harness default timeout"
        timeout = float(cmd[cmd.index("--timeout-s") + 1])
        assert timeout >= 10_800, f"{job['name']}: {timeout:.0f} s is too short for a 400k-step run"


def test_jobs_and_tags_are_unique() -> None:
    names = [job["name"] for job in heavy_queue.JOBS]
    assert len(names) == len(set(names))
    tags = []
    for job in heavy_queue.JOBS:
        cmd = [str(x) for x in job["cmd"]]  # type: ignore[arg-type]
        if "--tag" in cmd:
            tags.append(cmd[cmd.index("--tag") + 1])
    assert len(tags) == len(set(tags)), "two jobs would share a run directory and clobber each other"


def test_every_job_has_a_wall_clock_limit_and_a_summary_path() -> None:
    for job in heavy_queue.JOBS:
        assert float(job["hours"]) > 0, f"{job['name']}: no wall-clock limit"
        assert str(job["summary"]).endswith(".json")


def test_plan_lists_without_running_anything() -> None:
    assert heavy_queue.main(["--list"]) == 0


def test_a_job_that_ends_in_seconds_is_flagged_not_trusted(tmp_path: Path) -> None:
    """An rc of 0 after two seconds means a startup failure, not success."""
    entry = heavy_queue.run_job(
        {"name": "instant", "what": "exits immediately",
         "cmd": [sys.executable, "-c", "print('nothing was simulated')"],
         "hours": 0.01, "summary": None},
        tmp_path,
    )
    assert str(entry["status"]).startswith("failed-fast"), entry["status"]
    assert entry["log_tail"], "the tail of the log must travel with the failure"


def test_a_real_failure_keeps_its_exit_code(tmp_path: Path) -> None:
    entry = heavy_queue.run_job(
        {"name": "boom", "what": "fails", "cmd": [sys.executable, "-c", "raise SystemExit(3)"],
         "hours": 0.01, "summary": None},
        tmp_path,
    )
    assert "exit 3" in str(entry["status"])
