"""Phase 1 (result plotting): `openantenna plot` must turn a stored run into a PNG.

Skipped when matplotlib is absent, so the CI job (stdlib only) stays green.
"""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path

from openantenna.cli import EXIT_ERROR, EXIT_OK, cmd_plot

HAVE_MPL = importlib.util.find_spec("matplotlib") is not None

TRACE = """freq_hz,s11_re,s11_im
2.30e9,-0.30,0.0
2.35e9,-0.20,0.0
2.40e9,-0.05,0.0
2.45e9,-0.15,0.0
2.50e9,-0.40,0.0
"""


class TestPlotCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self._tmp.name) / "run"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _args(self, **overrides) -> argparse.Namespace:
        base = dict(run=str(self.run_dir), csv=None, out=str(self.run_dir / "plot.png"), dpi=100)
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_missing_csv_is_a_clean_error(self):
        self.assertEqual(cmd_plot(self._args()), EXIT_ERROR)

    def test_unreadable_csv_is_a_clean_error(self):
        (self.run_dir / "s11.csv").write_text("not,a,trace\n", encoding="utf-8")
        self.assertEqual(cmd_plot(self._args()), EXIT_ERROR)

    @unittest.skipUnless(HAVE_MPL, "matplotlib is not installed (CI runs stdlib only)")
    def test_plot_is_written(self):
        (self.run_dir / "s11.csv").write_text(TRACE, encoding="utf-8")
        out = self.run_dir / "plot.png"
        self.assertEqual(cmd_plot(self._args(out=str(out))), EXIT_OK)
        self.assertTrue(out.is_file())
        self.assertGreater(out.stat().st_size, 2000, "a real PNG with two panels")

    @unittest.skipUnless(HAVE_MPL, "matplotlib is not installed (CI runs stdlib only)")
    def test_custom_csv_name_is_honoured(self):
        (self.run_dir / "other.csv").write_text(TRACE, encoding="utf-8")
        out = self.run_dir / "plot2.png"
        self.assertEqual(cmd_plot(self._args(csv="other.csv", out=str(out))), EXIT_OK)
        self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
