"""Tests for streaming solver progress (progress.json + the progress bar).

The sample lines are copied verbatim from a completed run
(``runs/portrefine_tutorial_on/run.stdout.log``), so the parser is pinned against real
solver output rather than against output invented for the test.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openantenna.solvers import progress as prog
from openantenna.solvers.base import SolverAdapter, SolverRun, SolverStatus

SAMPLE = (
    "[@     2m28s] Timestep:        18655 || Speed:   39.8 MC/s (7.388e-03 s/TS) "
    "|| Energy: ~1.07e-18 (-31.89dB)"
)
SAMPLE_2 = (
    "[@     3m11s] Timestep:        24180 || Speed:   41.8 MC/s (7.028e-03 s/TS) "
    "|| Energy: ~1.32e-19 (-40.99dB)"
)
FINAL_SPEED = "Speed: 37.18 MCells/s"


class TestParsing(unittest.TestCase):
    def test_parses_a_real_progress_line(self):
        p = prog.parse_line(SAMPLE)
        self.assertEqual(p.timestep, 18655)
        self.assertAlmostEqual(p.speed_mcells_s, 39.8)
        self.assertAlmostEqual(p.energy_db, -31.89)
        self.assertAlmostEqual(p.elapsed_s, 2 * 60 + 28.0)

    def test_parses_the_final_summary_line(self):
        p = prog.parse_line(FINAL_SPEED)
        self.assertIsNone(p.timestep)
        self.assertAlmostEqual(p.speed_mcells_s, 37.18)

    def test_ignores_lines_without_progress(self):
        for line in ("", "openEMS - verbose level 3", "   | (C) 2010-2026 T. Liebig", "----"):
            self.assertTrue(prog.parse_line(line).is_empty())
            self.assertFalse(prog.has_progress(line))


class TestBar(unittest.TestCase):
    def test_fraction_is_relative_to_the_step_cap(self):
        p = prog.SolverProgress(
            timestep=100000, elapsed_s=100.0, speed_mcells_s=10.0, energy_db=-30.0
        )
        text = prog.format_bar(p, 400000)
        self.assertIn("25.0%", text)
        self.assertIn("100,000/400,000", text)
        self.assertIn("-30.0 dB", text)

    def test_fraction_clamps_past_the_cap(self):
        p = prog.SolverProgress(timestep=500000, elapsed_s=10.0)
        self.assertIn("100.0%", prog.format_bar(p, 400000))

    def test_missing_cap_does_not_crash(self):
        text = prog.format_bar(prog.SolverProgress(timestep=10), None)
        self.assertIn("0.0%", text)

    def test_eta_uses_the_observed_rate_only(self):
        p = prog.SolverProgress(timestep=1000, elapsed_s=10.0)
        self.assertAlmostEqual(prog.eta_to_cap(p, 4000), 30.0)
        # no elapsed time, or no timestep -> no honest estimate
        self.assertIsNone(prog.eta_to_cap(prog.SolverProgress(timestep=1000), 4000))
        self.assertIsNone(prog.eta_to_cap(p, None))

    def test_duration_formatting(self):
        self.assertEqual(prog.format_duration(45), "45s")
        self.assertEqual(prog.format_duration(148), "2m28s")
        self.assertEqual(prog.format_duration(3720), "1h02m")


class TestPrinter(unittest.TestCase):
    def test_writes_progress_json_on_every_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            printer = prog.ProgressPrinter(path, cap_steps=400000, stream=io.StringIO())
            printer.feed(SAMPLE)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["timestep"], 18655)
            self.assertAlmostEqual(payload["percent_of_cap"], 100.0 * 18655 / 400000, places=3)
            self.assertIn("bar", payload)
            self.assertEqual(printer.feed("just noise"), None)
            self.assertEqual(printer.updates, 1)

    def test_keeps_the_last_known_value_for_fields_a_line_omits(self):
        with tempfile.TemporaryDirectory() as tmp:
            printer = prog.ProgressPrinter(
                Path(tmp) / "progress.json", cap_steps=400000, stream=io.StringIO()
            )
            printer.feed(SAMPLE)
            printer.feed(FINAL_SPEED)
            payload = json.loads((Path(tmp) / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["timestep"], 18655)  # from the earlier line
            self.assertAlmostEqual(payload["speed_mcells_s"], 37.18)  # updated

    def test_piped_output_gets_whole_lines_not_a_carriage_return_bar(self):
        stream = io.StringIO()
        printer = prog.ProgressPrinter(None, cap_steps=400000, stream=stream)
        printer.feed(SAMPLE)
        text = stream.getvalue()
        self.assertTrue(text.startswith("[progress] "))
        self.assertTrue(text.endswith("\n"))
        self.assertNotIn("\r", text)

    def test_the_bar_states_that_the_cap_is_not_the_finish_line(self):
        """A bare "6 %" reads like "barely started"; that misreading actually happened.

        The tutorial run finished at 6.0 % of its 400000-step cap because it stopped on
        the energy criterion, so the label has to say so explicitly.
        """
        text = prog.format_bar(
            prog.SolverProgress(timestep=24180, elapsed_s=191.0, energy_db=-40.99), 400000
        )
        self.assertIn("6.0% of the 400,000-step cap", text)
        self.assertIn("cap is an upper bound, not the finish line", text)


class TestProgressCallback(unittest.TestCase):
    def test_on_progress_receives_every_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen = []
            SolverAdapter._execute(
                [
                    sys.executable,
                    "-u",
                    "-c",
                    "print('[@     0m01s] Timestep:        1000 || Speed:   40.0 MC/s "
                    "|| Energy: ~1e-18 (-31.0dB)')",
                ],
                Path(tmp),
                None,
                on_progress=seen.append,
            )
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].timestep, 1000)
        self.assertAlmostEqual(seen[0].energy_db, -31.0)


class TestStreamingExecute(unittest.TestCase):
    @staticmethod
    def _child(argv_lines: list[str]) -> list[str]:
        body = "\n".join(f"print({line!r})" for line in argv_lines)
        return [sys.executable, "-u", "-c", body]

    def test_log_is_captured_and_progress_json_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = Path(tmp)
            run = SolverAdapter._execute(
                self._child([SAMPLE, "noise", FINAL_SPEED]),
                rundir,
                None,
                progress_path=rundir / "progress.json",
                total_steps=400000,
            )
            self.assertEqual(run.status, "ok")
            self.assertIn("Timestep", run.log)
            self.assertIsNotNone(run.duration_s)
            payload = json.loads((rundir / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["timestep"], 18655)
            self.assertAlmostEqual(payload["speed_mcells_s"], 37.18)

    def test_a_failing_child_is_reported_as_failed_with_its_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = SolverAdapter._execute(
                [sys.executable, "-u", "-c", "print('boom'); raise SystemExit(3)"],
                Path(tmp),
                None,
            )
            self.assertEqual(run.status, "failed")
            self.assertEqual(run.returncode, 3)
            self.assertIn("boom", run.log)

    def test_timeout_kills_the_child_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = SolverAdapter._execute(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                Path(tmp),
                0.5,
            )
            self.assertEqual(run.status, "failed")
            self.assertIn("timeout", run.log)


class TestOpenemsAdapterWiring(unittest.TestCase):
    """The adapter must stream with -u and point the progress file at the run dir."""

    def test_run_passes_progress_path_and_unbuffered_interpreter(self):
        from openantenna.solvers.openems import OpenEMSSolver

        solver = OpenEMSSolver()
        with tempfile.TemporaryDirectory() as tmp:
            rundir = Path(tmp)
            (rundir / solver.script_name).write_text("# fake script\n", encoding="utf-8")
            captured = {}

            def fake_execute(argv, run_path, timeout_s, **kwargs):
                captured["argv"] = argv
                captured["kwargs"] = kwargs
                return SolverRun(rundir=run_path, status="ok", returncode=0, log="")

            with mock.patch.object(
                OpenEMSSolver,
                "available",
                return_value=SolverStatus(name="openems", available=True, detail="ok"),
            ), mock.patch.object(OpenEMSSolver, "_execute", staticmethod(fake_execute)):
                run = solver.run(rundir)

        self.assertEqual(run.status, "ok")
        self.assertIn("-u", captured["argv"])
        self.assertEqual(captured["kwargs"]["progress_path"], rundir / "progress.json")
        self.assertEqual(captured["kwargs"]["total_steps"], solver.max_timesteps)
        self.assertTrue(captured["kwargs"]["echo_progress"])


if __name__ == "__main__":
    unittest.main()
