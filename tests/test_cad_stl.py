"""Tests for the STL reader and staircase rasteriser (Phase 4, CAD import)."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from openantenna.geometry.cad import (
    Mesh,
    occupancy_fraction,
    read_ascii_stl,
    read_binary_stl,
    read_stl,
    staircase_occupancy,
)

CUBE_TRIANGLES = [
    # two triangles per face of a unit cube, enough to make the reader's job unambiguous
    ((0, 0, 0), (1, 0, 0), (1, 1, 0)),
    ((0, 0, 0), (1, 1, 0), (0, 1, 0)),
    ((0, 0, 1), (1, 1, 1), (1, 0, 1)),
    ((0, 0, 1), (0, 1, 1), (1, 1, 1)),
    ((0, 0, 0), (0, 1, 0), (0, 1, 1)),
    ((0, 0, 0), (0, 1, 1), (0, 0, 1)),
    ((1, 0, 0), (1, 1, 1), (1, 1, 0)),
    ((1, 0, 0), (1, 0, 1), (1, 1, 1)),
    ((0, 0, 0), (1, 0, 1), (1, 0, 0)),
    ((0, 0, 0), (0, 0, 1), (1, 0, 1)),
    ((0, 1, 0), (1, 1, 1), (0, 1, 1)),
    ((0, 1, 0), (1, 1, 0), (1, 1, 1)),
]


def _write_binary(path: Path, triangles) -> None:
    payload = b"openantenna-test".ljust(80, b"\0")
    payload += struct.pack("<I", len(triangles))
    for a, b, c in triangles:
        payload += struct.pack("<12fH", 0, 0, 1, *a, *b, *c, 0)
    path.write_bytes(payload)


def _write_ascii(path: Path, triangles) -> None:
    lines = ["solid cube"]
    for a, b, c in triangles:
        lines.append("  facet normal 0 0 1")
        lines.append("    outer loop")
        for point in (a, b, c):
            lines.append(f"      vertex {point[0]} {point[1]} {point[2]}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid cube")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestStlReading(unittest.TestCase):
    def test_binary_stl_round_trips(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "cube.stl"
            _write_binary(target, CUBE_TRIANGLES)
            mesh = read_binary_stl(target)
        self.assertEqual(mesh.triangle_count, 12)
        low, high = mesh.bounds()
        self.assertEqual(low, (0.0, 0.0, 0.0))
        self.assertEqual(high, (1.0, 1.0, 1.0))
        self.assertEqual(mesh.size(), (1.0, 1.0, 1.0))

    def test_ascii_stl_round_trips(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "cube.stl"
            _write_ascii(target, CUBE_TRIANGLES)
            mesh = read_ascii_stl(target)
        self.assertEqual(mesh.triangle_count, 12)
        self.assertEqual(mesh.size(), (1.0, 1.0, 1.0))

    def test_the_format_is_chosen_by_measurement_not_by_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "cube.dat"
            _write_binary(binary, CUBE_TRIANGLES)
            self.assertEqual(read_stl(binary).triangle_count, 12)
            ascii_ = Path(folder) / "cube.dat2"
            _write_ascii(ascii_, CUBE_TRIANGLES)
            self.assertEqual(read_stl(ascii_).triangle_count, 12)

    def test_a_file_whose_header_lies_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "broken.stl"
            payload = b"x".ljust(80, b"\0") + struct.pack("<I", 999)
            target.write_bytes(payload)
            with self.assertRaises(ValueError) as caught:
                read_binary_stl(target)
            self.assertIn("refusing to guess", str(caught.exception))

    def test_missing_file_is_a_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            read_stl(Path("does_not_exist.stl"))

    def test_a_truncated_ascii_file_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "short.stl"
            target.write_text("solid s\n  vertex 0 0 0\n", encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                read_ascii_stl(target)
            self.assertIn("not a whole number of triangles", str(caught.exception))


class TestStaircase(unittest.TestCase):
    def test_the_grid_covers_the_mesh_bounds(self):
        mesh = Mesh(tuple(CUBE_TRIANGLES))
        (n_x, n_y), rows = staircase_occupancy(mesh, 0.25)
        self.assertEqual((n_x, n_y), (5, 5))
        self.assertEqual(len(rows[0]), n_x)
        self.assertTrue(any(any(row) for row in rows), "the mesh must occupy something")

    def test_a_finer_cell_does_not_lose_the_mesh(self):
        mesh = Mesh(tuple(CUBE_TRIANGLES))
        _shape_coarse, coarse = staircase_occupancy(mesh, 0.5)
        _shape_fine, fine = staircase_occupancy(mesh, 0.2)
        self.assertGreaterEqual(occupancy_fraction(coarse), 0.1)
        self.assertGreaterEqual(occupancy_fraction(fine), 0.0)

    def test_bad_inputs_are_refused(self):
        mesh = Mesh(tuple(CUBE_TRIANGLES))
        with self.assertRaises(ValueError):
            staircase_occupancy(mesh, 0.0)
        with self.assertRaises(ValueError):
            staircase_occupancy(mesh, 0.5, plane="ab")
        with self.assertRaises(ValueError):
            staircase_occupancy(Mesh(()), 0.5)


if __name__ == "__main__":
    unittest.main()
