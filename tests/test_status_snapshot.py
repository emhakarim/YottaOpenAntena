"""Tests for the live-status tool.

The bug frozen here cost five hours of silence: a killed run leaves its last progress line in its log
for ever, so a tool that trusts the text reports dead runs as live. A monitoring job was built on top
of that and therefore never fired. Liveness now comes from the log's modification time.
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

from yotta_tools import status_snapshot


def write_engine_log(path: Path, step: int, speed: float, cap: int = 400_000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"[@  10m00s] Timestep: {step:,} || Speed: {speed:.1f} MC/s (2.0e-02 s/TS) || Energy: ~1e-11\n",
        encoding="utf-8",
    )
    return path


def test_engine_state_reads_the_last_timestep_and_speed() -> None:
    lines = ["Timestep:      12345 || Speed:  10.0 MC/s", "Timestep:      67890 || Speed:  32.5 MC/s"]
    assert status_snapshot.engine_state(lines) == {"step": 67890, "speed_mc_s": 32.5}


def test_b2_progress_line_is_parsed_including_commas() -> None:
    line = ("[progress] [####----]  14.3% of the 400,000-step cap  step 57,358/400,000  "
            "16.0 MCells/s  elapsed 22m03s  worst case 2h11m more")
    state = status_snapshot.b2_state([line])
    assert state == {"step": 57358, "cap": 400000, "speed_mc_s": 16.0, "eta_left": "2h11m"}


def test_pct_handles_missing_values() -> None:
    assert status_snapshot.pct(None, 400_000) == "-"
    assert status_snapshot.pct(200_000, None) == "-"
    assert status_snapshot.pct(200_000, 400_000) == "50.0 %"


def test_a_stale_log_is_reported_as_not_live(tmp_path: Path, monkeypatch) -> None:
    """The exact situation that fooled the first watcher."""
    monkeypatch.setattr(status_snapshot, "REPO", tmp_path)
    log = write_engine_log(tmp_path / "runs" / "batch_dead" / "run.stdout.log", 146_356, 32.5)
    old = time.time() - (2 * status_snapshot.STALE_AFTER_S)
    os.utime(log, (old, old))

    assert status_snapshot.main([]) == 0
    snapshot = json.loads((tmp_path / "runs" / "status_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["live_count"] == 0
    assert snapshot["runs"][0]["live"] is False
    assert snapshot["runs"][0]["log_age_s"] >= status_snapshot.STALE_AFTER_S


def test_a_fresh_log_is_reported_as_live(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(status_snapshot, "REPO", tmp_path)
    write_engine_log(tmp_path / "runs" / "batch_live" / "run.stdout.log", 200_000, 30.0)

    assert status_snapshot.main([]) == 0
    snapshot = json.loads((tmp_path / "runs" / "status_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["live_count"] == 1
    assert snapshot["runs"][0]["live"] is True
    assert snapshot["runs"][0]["progress"] == "50.0 %"


def test_the_cap_is_stated_as_a_ceiling_not_a_countdown(tmp_path: Path, monkeypatch) -> None:
    """A run stopping earlier on its own end criteria is normal, so the note must say so."""
    monkeypatch.setattr(status_snapshot, "REPO", tmp_path)
    write_engine_log(tmp_path / "runs" / "batch_live" / "run.stdout.log", 1_000, 30.0)
    status_snapshot.main([])
    snapshot = json.loads((tmp_path / "runs" / "status_snapshot.json").read_text(encoding="utf-8"))
    assert "EndCriteria" in snapshot["note"]
    assert math.isclose(snapshot["runs"][0]["step"] / snapshot["runs"][0]["cap"], 0.0025, rel_tol=1e-3)
