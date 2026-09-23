"""Tests for the OBJ reader and the format dispatcher."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openantenna.geometry.cad import read_mesh, read_obj

CUBE_OBJ = """# a unit cube
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
v 0 0 1
v 1 0 1
v 1 1 1
v 0 1 1
vn 0 0 1
f 1//1 2//1 3//1 4//1
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
"""


class TestObjReading(unittest.TestCase):
    def test_a_quad_cube_becomes_twelve_triangles(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "cube.obj"
            target.write_text(CUBE_OBJ, encoding="utf-8")
            mesh = read_obj(target)
        self.assertEqual(mesh.triangle_count, 12)
        self.assertEqual(mesh.size(), (1.0, 1.0, 1.0))

    def test_negative_indices_are_relative(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "tri.obj"
            target.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\n", encoding="utf-8")
            mesh = read_obj(target)
        self.assertEqual(mesh.triangle_count, 1)
        self.assertEqual(mesh.bounds()[1], (1.0, 1.0, 0.0))

    def test_an_out_of_range_index_is_refused_with_the_line_number(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "bad.obj"
            target.write_text("v 0 0 0\nv 1 0 0\nf 1 2 9\n", encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                read_obj(target)
            self.assertIn(":3:", str(caught.exception))

    def test_a_file_with_no_faces_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "points.obj"
            target.write_text("v 0 0 0\nv 1 0 0\n", encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                read_obj(target)
            self.assertIn("no faces", str(caught.exception))

    def test_the_dispatcher_picks_obj_for_obj_and_stl_for_stl(self):
        with tempfile.TemporaryDirectory() as folder:
            obj = Path(folder) / "thing.obj"
            obj.write_text(CUBE_OBJ, encoding="utf-8")
            self.assertEqual(read_mesh(obj).triangle_count, 12)
            ascii_stl = Path(folder) / "thing.stl"
            ascii_stl.write_text(
                "solid s\n  facet normal 0 0 1\n    outer loop\n"
                "      vertex 0 0 0\n      vertex 1 0 0\n      vertex 0 1 0\n"
                "    endloop\n  endfacet\nendsolid s\n",
                encoding="utf-8",
            )
            self.assertEqual(read_mesh(ascii_stl).triangle_count, 1)


if __name__ == "__main__":
    unittest.main()
