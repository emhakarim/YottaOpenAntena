"""Phase 2 #6: the NEC2 adapter, verified without a NEC2 engine.

A *fake* engine (a tiny script the test writes itself) stands in for nec2c, so the whole
adapter contract is exercised: deck rendering, binary resolution, deck delivery on stdin,
output capture, parsing, and the honest failure paths.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from openantenna.geometry.wire import synthesize_dipole, synthesize_monopole
from openantenna.solvers.base import SolverUnavailableError
from openantenna.solvers.nec2 import DECK_NAME, OUTPUT_NAME, Nec2Solver

CANNED_OUTPUT = """\
                             ------- FREQUENCY --------
FREQUENCY : 2.4500E+03 MHz

                          --------- ANTENNA INPUT PARAMETERS ---------
  TAG   SEG       VOLTAGE (VOLTS)         CURRENT (AMPS)         IMPEDANCE (OHMS)        ADMITTANCE (MHOS)     POWER
  No:   No:     REAL      IMAGINARY     REAL      IMAGINARY     REAL      IMAGINARY    REAL       IMAGINARY   (WATTS)
    1    16  1.0000E+00  0.0000E+00  1.3500E-02 -7.9000E-03  7.3130E+01  4.2540E+01  1.3500E-02  7.9000E-03  6.7000E-03

                           -------- CURRENTS AND LOCATION --------

EFFICIENCY    =  100.00 Percent
"""

FAKE_ENGINE = '''\
import sys
from pathlib import Path
data = sys.stdin.read()
Path("engine_input.txt").write_text(data, encoding="utf-8")
sys.stdout.write(CANNED)
'''


def _make_fake_engine(root: Path) -> Path:
    """Create a stand-in for nec2c that works on Windows *and* POSIX.

    The adapter invokes `[binary]` with the deck on stdin, so the stand-in has to be an
    executable.  On Windows that is a .bat; elsewhere a +x shell script.  (The CI job
    caught the Windows-only version: it passed on windows-latest and failed on
    ubuntu-latest.)
    """
    script = root / "fake_engine.py"
    script.write_text(
        FAKE_ENGINE.replace("CANNED", repr(CANNED_OUTPUT)),
        encoding="utf-8",
    )
    if os.name == "nt":
        wrapper = root / "fake_nec2.bat"
        wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{script}"\r\n', encoding="utf-8")
    else:
        wrapper = root / "fake_nec2.sh"
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}"\n', encoding="utf-8")
        wrapper.chmod(0o755)
    return wrapper


class TestDeckRendering(unittest.TestCase):
    def test_dipole_deck_has_the_core_cards(self):
        design = synthesize_dipole(2.45e9)
        deck = Nec2Solver().render_deck(design)
        self.assertIn("GW 1,31,", deck)
        self.assertIn("GE 0", deck)
        # EX: type, tag, SEGMENT, unused integer, voltage, phase (nec2c free format)
        self.assertIn("EX 0,1,16,0,1.0,0.0", deck)
        self.assertIn("FR 0,1,0,0,2450.000000,0.0", deck)
        self.assertTrue(deck.rstrip().endswith("EN"))
        self.assertIn(f"{-design.length_m / 2:.6f}", deck)  # spans -L/2 .. +L/2
        self.assertIn(f"{design.radius_m:.6f}", deck)
        self.assertTrue(deck.isascii(), "NEC2 decks must stay ASCII")

    def test_monopole_deck_uses_a_ground_plane_and_starts_at_zero(self):
        design = synthesize_monopole(2.45e9)
        deck = Nec2Solver().render_deck(design)
        self.assertIn("GN 1", deck)
        self.assertIn("GW 1,21,0.,0.,0.,", deck)


class TestAvailabilityHonesty(unittest.TestCase):
    def test_missing_engine_is_reported_not_faked(self):
        status = Nec2Solver(binary=None).available()
        if status.available:
            self.skipTest("a real NEC2 engine is on PATH; the miss path cannot be tested here")
        self.assertIn("NEC2_BIN", status.detail)

    def test_run_without_an_engine_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            solver = Nec2Solver(binary=str(Path(tmp) / "does_not_exist"))
            design = synthesize_dipole(2.45e9)
            with self.assertRaises(SolverUnavailableError):
                solver.run(tmp)

    def test_prepare_rejects_a_project_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TypeError) as ctx:
                Nec2Solver().prepare(object(), tmp)
            self.assertIn("WireDesign", str(ctx.exception))


class TestEndToEndWithAFakeEngine(unittest.TestCase):
    def test_run_then_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = _make_fake_engine(root)
            solver = Nec2Solver(binary=str(engine))
            self.assertTrue(solver.available().available)

            design = synthesize_dipole(2.45e9)
            rundir = solver.prepare(design, root / "run")
            self.assertTrue((rundir / DECK_NAME).exists())

            run = solver.run(rundir, timeout_s=60)
            self.assertEqual(run.status, "ok")
            self.assertTrue((rundir / OUTPUT_NAME).exists())

            # the deck really was delivered to the engine on stdin
            delivered = (rundir / "engine_input.txt").read_text(encoding="utf-8")
            self.assertIn("GW 1,31,", delivered)
            self.assertIn("EN", delivered)

            parsed = solver.parse_results(rundir)
            self.assertAlmostEqual(parsed["frequency_hz"] / 1e9, 2.45, places=6)
            self.assertAlmostEqual(parsed["resistance_ohm"], 73.13, places=2)
            self.assertAlmostEqual(parsed["reactance_ohm"], 42.54, places=2)
            self.assertAlmostEqual(parsed["vswr_50_ohm"], 2.184, delta=0.01)
            self.assertEqual(parsed["efficiency_percent"], 100.0)
            self.assertEqual(parsed["n_frequencies"], 1)

    def test_parse_without_an_output_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                Nec2Solver().parse_results(tmp)

    def test_parse_of_a_crashed_run_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / OUTPUT_NAME).write_text("*** the deck was rejected ***\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                Nec2Solver().parse_results(tmp)


if __name__ == "__main__":
    unittest.main()
