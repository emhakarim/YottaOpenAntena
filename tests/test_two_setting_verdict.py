"""Tests for the two-setting verdict tool.

The point of these tests is that the *policy* is enforced by code: a rejected experiment must come
out rejected with a stated reason, and a missing file must be an error rather than a quiet zero.

Written with ``unittest`` only: CI runs the suite with no optional dependencies, so a pytest-style
import here fails the whole job (that is exactly what happened on 2026-09-22).
"""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

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


class TestVerdict(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_stable_pair_is_accepted_and_quotable(self) -> None:
        a = RunData(make_run(self.base, "setting_a", 500, samples=1001))
        b = RunData(make_run(self.base, "setting_b", 501, samples=1001))  # 0.5 MHz = 0.02 %
        result = verdict(a, b)
        self.assertEqual(result["verdict"], "accepted")
        self.assertTrue(result["quotable"])
        self.assertLess(result["relative_shift_pct"], 0.2)
        self.assertTrue(result["runs"][0]["converged"])
        self.assertEqual(result["runs"][0]["timesteps"], 42000)

    def test_shift_above_tolerance_is_rejected(self) -> None:
        a = RunData(make_run(self.base, "setting_a", 50))
        b = RunData(make_run(self.base, "setting_b", 51))  # 5 MHz of 500 MHz = 0.21 %
        result = verdict(a, b)
        self.assertEqual(result["verdict"], "rejected")
        self.assertFalse(result["quotable"])
        self.assertGreater(result["relative_shift_pct"], 0.2)
        self.assertTrue(any("between the two settings" in reason for reason in result["reasons"]))

    def test_edge_minimum_is_rejected_even_when_the_two_runs_agree(self) -> None:
        """The K-1 trap: both settings can agree on an artefact."""
        a = RunData(make_run(self.base, "setting_a", 0, edge=True))
        b = RunData(make_run(self.base, "setting_b", 0, edge=True))
        result = verdict(a, b)
        self.assertEqual(result["verdict"], "rejected")
        self.assertAlmostEqual(result["relative_shift_pct"], 0.0)
        self.assertTrue(any("sweep edge" in reason for reason in result["reasons"]))

    def test_cap_hit_run_is_rejected_as_unconverged(self) -> None:
        a = RunData(make_run(self.base, "setting_a", 500, samples=1001, converged=True))
        b = RunData(make_run(self.base, "setting_b", 500, samples=1001, converged=False))
        result = verdict(a, b)
        self.assertEqual(result["verdict"], "rejected")
        self.assertFalse(result["runs"][1]["converged"])
        self.assertEqual(result["runs"][1]["timesteps"], 400000)
        self.assertTrue(any("not converged" in reason for reason in result["reasons"]))

    def test_unverifiable_convergence_is_not_treated_as_converged(self) -> None:
        directory = make_run(self.base, "setting_a", 500, samples=1001)
        (directory / "run.stdout.log").write_text("Timestep: 10\n", encoding="utf-8")
        run = RunData(directory)
        self.assertIsNone(run.converged)
        self.assertTrue(run.convergence_note.startswith("engine log has no convergence statement"))

    def test_s11_and_vswr_are_computed_from_the_dip(self) -> None:
        run = RunData(make_run(self.base, "setting_a", 500, samples=1001))
        self.assertAlmostEqual(run.s11_db[500], -25.0, delta=0.01)
        magnitude = 10 ** (-25 / 20)
        self.assertAlmostEqual(run.vswr[500], (1 + magnitude) / (1 - magnitude), delta=1e-4)
        self.assertAlmostEqual(run.resonance_hz, F_MIN + 500 * (F_MAX - F_MIN) / 1000, delta=1.0)

    def test_missing_s11_is_an_error_not_a_zero(self) -> None:
        directory = make_run(self.base, "setting_a", 50)
        (directory / "s11.csv").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "a missing file is an error, not a zero"):
            RunData(directory)

    def test_wrong_columns_are_rejected(self) -> None:
        directory = make_run(self.base, "setting_a", 50)
        (directory / "s11.csv").write_text(
            "freq_hz,re,im\n2.4e9,0.1,0.0\n2.5e9,0.2,0.0\n2.6e9,0.3,0.0\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing column"):
            RunData(directory)


class TestVerdictCli(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_cli_returns_two_on_a_broken_input_and_zero_on_a_rejection(self) -> None:
        a = make_run(self.base, "setting_a", 50)
        b = make_run(self.base, "setting_b", 51)
        self.assertEqual(main(["--a", str(a), "--b", str(b)]), 0)  # rejected is a valid outcome
        empty = self.base / "nothing_here"
        empty.mkdir()
        self.assertEqual(main(["--a", str(a), "--b", str(empty)]), 2)

    def test_json_output_records_the_rules_and_carries_the_verdict(self) -> None:
        a = make_run(self.base, "setting_a", 500, samples=1001)
        b = make_run(self.base, "setting_b", 500, samples=1001)
        out = self.base / "verdict.json"
        self.assertEqual(main(["--a", str(a), "--b", str(b), "--json", str(out)]), 0)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "accepted")
        self.assertTrue(payload["rules"].startswith("docs/convergence-policy.md"))
        self.assertEqual(payload["edge_steps"], 2)


if __name__ == "__main__":
    unittest.main()
