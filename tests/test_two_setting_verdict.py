"""Tests for the two-setting verdict tool.

The point of these tests is that the *policy* is enforced by code: a rejected experiment must come
out rejected with a stated reason, and a missing file must be an error rather than a quiet zero.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from yotta_tools.two_setting_verdict import RunData, main, verdict

F_MIN = 2.2e9
F_MAX = 2.7e9


def make_run(base: Path, name: str, min_at: int, *, samples: int = 101, converged: bool = True,
             edge: bool = False) -> Path:
    """Write one synthetic run directory: a Lorentzian dip at ``min_at`` plus an engine log."""
    directory = base / name
    directory.mkdir(parents=True)
    index = 0 if edge else min_at
    frequencies = [F_MIN + i * (F_MAX - F_MIN) / (samples - 1) for i in range(samples)]
    lines = ["freq_hz,s11_re,s11_im"]
    for i, frequency in enumerate(frequencies):
        depth_db = -25.0 * math.exp(-((i - index) ** 2) / (2 * 3.0**2))
        magnitude = 10 ** (depth_db / 20.0)
        lines.append(f"{frequency:.6e},{magnitude:.9e},0.0")
    (directory / "s11.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (directory / "run_summary.json").write_text(json.dumps({
        "solver": "openEMS", "project": name,
        "f_min_hz": F_MIN, "f_max_hz": F_MAX, "n_freq": samples,
        "s11_csv": str(directory / "s11.csv"),
    }), encoding="utf-8")
    if converged:
        log = "Timestep: 42000 || Speed: 40.0 MC/s || Energy: ~1e-20\n"
        log += "RunFDTD: End criteria reached after 42000 iterations\n"
    else:
        log = "Timestep: 400000 || Speed: 40.0 MC/s || Energy: ~1e-18\n"
        log += ("RunFDTD: Warning: Max. number of timesteps was reached before the end-criteria "
                "of -20dB was reached.\n")
    (directory / "run.stdout.log").write_text(log, encoding="utf-8")
    return directory


def test_stable_pair_is_accepted_and_quotable(tmp_path: Path) -> None:
    a = RunData(make_run(tmp_path, "setting_a", 500, samples=1001))
    b = RunData(make_run(tmp_path, "setting_b", 501, samples=1001))  # 0.5 MHz = 0.02 %
    result = verdict(a, b)
    assert result["verdict"] == "accepted"
    assert result["quotable"] is True
    assert result["relative_shift_pct"] < 0.2
    assert result["runs"][0]["converged"] is True
    assert result["runs"][0]["timesteps"] == 42000


def test_shift_above_tolerance_is_rejected(tmp_path: Path) -> None:
    a = RunData(make_run(tmp_path, "setting_a", 50))
    b = RunData(make_run(tmp_path, "setting_b", 51))  # 5 MHz of 500 MHz = 0.21 %
    result = verdict(a, b)
    assert result["verdict"] == "rejected"
    assert result["quotable"] is False
    assert result["relative_shift_pct"] > 0.2
    assert any("between the two settings" in reason for reason in result["reasons"])


def test_edge_minimum_is_rejected_even_when_the_two_runs_agree(tmp_path: Path) -> None:
    """The K-1 trap: both settings can agree on an artefact."""
    a = RunData(make_run(tmp_path, "setting_a", 0, edge=True))
    b = RunData(make_run(tmp_path, "setting_b", 0, edge=True))
    result = verdict(a, b)
    assert result["verdict"] == "rejected"
    assert result["relative_shift_pct"] == pytest.approx(0.0)
    assert any("sweep edge" in reason for reason in result["reasons"])


def test_cap_hit_run_is_rejected_as_unconverged(tmp_path: Path) -> None:
    a = RunData(make_run(tmp_path, "setting_a", 500, samples=1001, converged=True))
    b = RunData(make_run(tmp_path, "setting_b", 500, samples=1001, converged=False))
    result = verdict(a, b)
    assert result["verdict"] == "rejected"
    assert result["runs"][1]["converged"] is False
    assert result["runs"][1]["timesteps"] == 400000
    assert any("not converged" in reason for reason in result["reasons"])


def test_unverifiable_convergence_is_not_treated_as_converged(tmp_path: Path) -> None:
    directory = make_run(tmp_path, "setting_a", 500, samples=1001)
    (directory / "run.stdout.log").write_text("Timestep: 10\n", encoding="utf-8")
    run = RunData(directory)
    assert run.converged is None
    assert run.convergence_note.startswith("engine log has no convergence statement")


def test_s11_and_vswr_are_computed_from_the_dip(tmp_path: Path) -> None:
    run = RunData(make_run(tmp_path, "setting_a", 500, samples=1001))
    assert run.s11_db[500] == pytest.approx(-25.0, abs=0.01)
    assert run.vswr[500] == pytest.approx((1 + 10 ** (-25 / 20)) / (1 - 10 ** (-25 / 20)), rel=1e-6)
    assert run.resonance_hz == pytest.approx(F_MIN + 500 * (F_MAX - F_MIN) / 1000)


def test_missing_s11_is_an_error_not_a_zero(tmp_path: Path) -> None:
    directory = make_run(tmp_path, "setting_a", 50)
    (directory / "s11.csv").unlink()
    with pytest.raises(FileNotFoundError, match="a missing file is an error, not a zero"):
        RunData(directory)


def test_wrong_columns_are_rejected(tmp_path: Path) -> None:
    directory = make_run(tmp_path, "setting_a", 50)
    (directory / "s11.csv").write_text("freq_hz,re,im\n2.4e9,0.1,0.0\n2.5e9,0.2,0.0\n2.6e9,0.3,0.0\n",
                                       encoding="utf-8")
    with pytest.raises(ValueError, match="missing column"):
        RunData(directory)


def test_cli_returns_two_on_a_broken_input_and_zero_on_a_rejection(tmp_path: Path) -> None:
    a = make_run(tmp_path, "setting_a", 50)
    b = make_run(tmp_path, "setting_b", 51)
    assert main(["--a", str(a), "--b", str(b)]) == 0  # rejected, and that is a valid outcome
    empty = tmp_path / "nothing_here"
    empty.mkdir()
    assert main(["--a", str(a), "--b", str(empty)]) == 2


def test_json_output_records_the_rules_and_carries_the_verdict(tmp_path: Path) -> None:
    a = RunData(make_run(tmp_path, "setting_a", 500, samples=1001))
    b = RunData(make_run(tmp_path, "setting_b", 500, samples=1001))
    out = tmp_path / "verdict.json"
    assert main(["--a", str(a.dir), "--b", str(b.dir), "--json", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["verdict"] == "accepted"
    assert payload["rules"].startswith("docs/convergence-policy.md")
    assert payload["edge_steps"] == 2
