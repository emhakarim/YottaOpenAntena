"""CLI tests for `cad-inspect`."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from openantenna import cli

TRIANGLES = [((0, 0, 0), (10, 0, 0), (10, 8, 0)), ((0, 0, 0), (10, 8, 0), (0, 8, 0))]


def _binary_stl(path: Path) -> None:
    payload = b"cli-test".ljust(80, b"\0") + struct.pack("<I", len(TRIANGLES))
    for a, b, c in TRIANGLES:
        payload += struct.pack("<12fH", 0, 0, 1, *a, *b, *c, 0)
    path.write_bytes(payload)


class TestCadInspect(unittest.TestCase):
    def test_it_reports_geometry_and_the_grid(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "plate.stl"
            _binary_stl(source)
            target = Path(folder) / "report.json"
            code = cli.main(["cad-inspect", str(source), "--cell-mm", "2", "--json", str(target)])
            self.assertEqual(code, 0)
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["kind"], "openantenna.cad-inspect")
        self.assertEqual(payload["triangles"], 2)
        # the mesh is in mm by default, so 10 mm of plate is 0.01 m of grid
        self.assertAlmostEqual(payload["size_m"][0], 0.01, places=9)
        self.assertIn("staircase", payload["warning"])
        self.assertGreater(payload["occupied_fraction"], 0.0)

    def test_a_bad_file_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as folder:
            broken = Path(folder) / "broken.stl"
            broken.write_text("solid s\n", encoding="utf-8")
            self.assertEqual(cli.main(["cad-inspect", str(broken)]), 1)

    def test_a_missing_file_exits_cleanly(self):
        self.assertEqual(cli.main(["cad-inspect", "definitely_missing.stl"]), 1)


    def test_the_units_switch_changes_the_scale(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "plate.stl"
            _binary_stl(source)
            sizes = {}
            # in metres the same plate is 10 m across, so it needs a coarser cell than the grid
            # guard allows at 1 mm - the guard refusing that is the behaviour under test elsewhere
            for units, cell_mm in (("mm", "2"), ("m", "10")):
                target = Path(folder) / f"report_{units}.json"
                self.assertEqual(
                    cli.main(
                        [
                            "cad-inspect",
                            str(source),
                            "--units",
                            units,
                            "--cell-mm",
                            cell_mm,
                            "--json",
                            str(target),
                        ]
                    ),
                    0,
                )
                sizes[units] = json.loads(target.read_text(encoding="utf-8"))["size_m"][0]
        self.assertAlmostEqual(sizes["mm"], 0.01, places=9)
        self.assertAlmostEqual(sizes["m"], 10.0, places=9)


if __name__ == "__main__":
    unittest.main()
