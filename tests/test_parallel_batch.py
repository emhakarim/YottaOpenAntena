"""Step E prep: parallel_batch must be able to cut a mesh pair on the sweep winner."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "parallel_batch_mod", ROOT / "yotta_tools" / "parallel_batch.py")
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)

from openantenna.geometry.patch import synthesize_patch  # noqa: E402


class TestInsetDelta(unittest.TestCase):
    def test_base_geometry_unchanged_without_delta(self) -> None:
        p = pb.project("t")
        self.assertIsNone(p.patch.feed_inset_m)

    def test_delta_shifts_inset_exactly_like_the_b2_driver(self) -> None:
        design = synthesize_patch(2.45e9, 2.1, 1.6e-3, "inset")
        p = pb.project("t", inset_delta_m=0.5e-3)
        self.assertAlmostEqual(p.patch.feed_inset_m, design.inset_depth_m + 0.5e-3, places=12)
        self.assertAlmostEqual(p.patch.width_m, design.width_m, places=15)
        self.assertAlmostEqual(p.patch.feed_line_width_m, design.feed_line_width_m, places=15)

    def test_out_of_bounds_delta_raises(self) -> None:
        with self.assertRaises(ValueError):
            pb.project("t", inset_delta_m=0.05)   # +50 mm >> patch length
        with self.assertRaises(ValueError):
            pb.project("t", inset_delta_m=-0.02)  # -20 mm -> negative inset

    def test_cli_accepts_inset_delta_mm(self) -> None:
        # argparse runs before the OPENEMS_ROOT check: an unknown flag would exit via
        # SystemExit instead of returning 2, so rc == 2 proves the flag parsed.
        env = {k: v for k, v in os.environ.items() if k != "OPENEMS_ROOT"}
        with mock.patch.dict(os.environ, env, clear=True):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = pb.main(["--preset", "mesh-stability", "--inset-delta-mm", "0.5"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
