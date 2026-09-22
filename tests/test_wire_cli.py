"""Phase 2 #6 usability: the wire path must be reachable from the CLI.

`openantenna wire` synthesises a dipole/monopole, writes a NEC2 deck, and only runs the
engine when one is available (and `--run` was asked for).  The deck must be written even
when no engine exists, because deck generation is pure computation.
"""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from openantenna.cli import EXIT_OK, cmd_wire
from openantenna.solvers.nec2 import DECK_NAME


def _args(**overrides) -> argparse.Namespace:
    base = dict(
        freq=2.45e9,
        radius_mm=1.0,
        length_factor=0.5,
        ground_plane=False,
        out=None,
        run=False,
        binary=None,
        timeout_s=60.0,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class TestWireCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / "wire"

    def tearDown(self):
        self._tmp.cleanup()

    def test_dipole_deck_is_written_without_an_engine(self):
        code = cmd_wire(_args(out=str(self.out), binary=str(self.out / "no_such_engine")))
        self.assertEqual(code, EXIT_OK)
        deck = (self.out / DECK_NAME).read_text(encoding="utf-8")
        self.assertIn("GW 1,31,", deck)
        self.assertIn("EX 0,1,16,0,1.0,0.0", deck)
        self.assertTrue(deck.rstrip().endswith("EN"))

    def test_monopole_uses_the_ground_plane_card(self):
        cmd_wire(_args(out=str(self.out), ground_plane=True, length_factor=0.25,
                       binary=str(self.out / "no_such_engine")))
        deck = (self.out / DECK_NAME).read_text(encoding="utf-8")
        self.assertIn("GN 1", deck)
        self.assertIn("GW 1,21,0.,0.,0.,", deck)

    def test_run_without_an_engine_still_writes_the_deck(self):
        code = cmd_wire(_args(out=str(self.out), run=True, binary=str(self.out / "nope")))
        self.assertEqual(code, EXIT_OK)
        self.assertTrue((self.out / DECK_NAME).is_file())

    def test_nonsense_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            cmd_wire(_args(out=str(self.out), length_factor=0.9))


if __name__ == "__main__":
    unittest.main()
