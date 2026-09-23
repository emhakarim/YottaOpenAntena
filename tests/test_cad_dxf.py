"""Tests for the minimal DXF reader, its rasteriser, and the dxf-inspect command."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openantenna.geometry.cad import rasterise_segments, read_dxf, stroke_fraction

REPO = Path(__file__).resolve().parent.parent


def write_dxf(path: Path, entities: str) -> Path:
    path.write_text(
        "0\nSECTION\n2\nENTITIES\n" + entities + "0\nENDSEC\n0\nEOF\n", encoding="utf-8"
    )
    return path


LINE = "0\nLINE\n8\n0\n10\n0\n20\n0\n11\n20\n21\n0\n"
CLOSED_SQUARE = (
    "0\nLWPOLYLINE\n8\n0\n70\n1\n"
    "10\n0\n20\n0\n10\n10\n20\n0\n10\n10\n20\n10\n10\n0\n20\n10\n"
)
CIRCLE = "0\nCIRCLE\n8\n0\n10\n5\n20\n5\n40\n3\n"
ARC = "0\nARC\n8\n0\n10\n0\n20\n0\n40\n5\n50\n0\n51\n90\n"


class TestDxfReading(unittest.TestCase):
    def test_a_line_becomes_one_segment(self):
        with tempfile.TemporaryDirectory() as folder:
            target = write_dxf(Path(folder) / "a.dxf", LINE)
            self.assertEqual(read_dxf(target), [((0.0, 0.0), (20.0, 0.0))])

    def test_a_closed_lwpolyline_adds_the_closing_segment(self):
        with tempfile.TemporaryDirectory() as folder:
            target = write_dxf(Path(folder) / "square.dxf", CLOSED_SQUARE)
            segments = read_dxf(target)
        self.assertEqual(len(segments), 4)
        self.assertEqual(segments[-1], ((0.0, 10.0), (0.0, 0.0)))

    def test_a_circle_is_polygonised_into_segments(self):
        with tempfile.TemporaryDirectory() as folder:
            target = write_dxf(Path(folder) / "c.dxf", CIRCLE)
            segments = read_dxf(target)
        self.assertEqual(len(segments), 48)
        xs = [x for start, end in segments for x in (start[0], end[0])]
        self.assertAlmostEqual(min(xs), 2.0, places=6)
        self.assertAlmostEqual(max(xs), 8.0, places=6)

    def test_an_arc_is_polygonised_and_a_file_with_no_supported_entity_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            arc = write_dxf(Path(folder) / "arc.dxf", ARC)
            xs = [x for start, end in read_dxf(arc) for x in (start[0], end[0])]
            self.assertAlmostEqual(max(xs), 5.0, places=3)
            self.assertAlmostEqual(min(xs), 0.0, places=6)
            empty = write_dxf(Path(folder) / "text.dxf", "0\nTEXT\n8\n0\n1\nhello\n")
            with self.assertRaises(ValueError) as caught:
                read_dxf(empty)
            self.assertIn("TEXT", str(caught.exception))

    def test_strokes_land_on_a_diagonal_band_and_the_cap_is_enforced(self):
        shape, rows = rasterise_segments([((0.0, 0.0), (10.0, 10.0))], 1.0)
        self.assertEqual(shape, (11, 11))
        struck = [(r, c) for r, row in enumerate(rows) for c, cell in enumerate(row) if cell]
        self.assertTrue(all(r == c for r, c in struck), struck[:5])
        self.assertGreater(stroke_fraction(rows), 0.0)
        with self.assertRaises(ValueError) as caught:
            rasterise_segments([((0.0, 0.0), (5000.0, 0.0))], 1.0)
        self.assertIn("2000", str(caught.exception))

    def test_the_command_reports_segments_and_grid_as_json(self):
        with tempfile.TemporaryDirectory() as folder:
            target = write_dxf(Path(folder) / "square.dxf", CLOSED_SQUARE)
            done = subprocess.run(
                [sys.executable, "-m", "openantenna.cli", "dxf-inspect", str(target),
                 "--cell-mm", "5", "--json"],
                cwd=REPO, capture_output=True, text=True,
            )
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["segments"], 4)
        self.assertEqual(payload["grid"]["cols"], 3)
        self.assertGreater(payload["stroke_fraction"], 0.0)


if __name__ == "__main__":
    unittest.main()
