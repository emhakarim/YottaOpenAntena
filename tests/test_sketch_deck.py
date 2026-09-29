"""Sketch polygons -> generated deck: the first half of docs/sketch-to-deck.md."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openantenna.geometry.sketch import polygon_area, validate_polygon  # noqa: E402
from openantenna.model.project import Project  # noqa: E402
from openantenna.solvers.openems import OpenEMSSolver  # noqa: E402
from test_generated_deck_bindings import WHITELIST, _bound_and_used  # noqa: E402
from test_openems_gen import make_project  # noqa: E402

#: a 20 x 10 mm sheet in metres - the units the neutral model speaks
RECT_M = ((0.0, -0.005), (0.020, -0.005), (0.020, 0.005), (0.0, 0.005))


class TestPolygonValidation(unittest.TestCase):
    def test_a_simple_polygon_validates_and_normalises_duplicates(self):
        polygon = validate_polygon([(0, 0), (4, 0), (4, 0), (4, 4), (0, 0)])
        self.assertEqual(len(polygon), 3)
        self.assertAlmostEqual(polygon_area(polygon), 8.0)

    def test_near_duplicate_points_are_normalised_away(self):
        polygon = validate_polygon([(0, 0), (4, 0), (4 + 5e-10, 0.0), (4, 4)])
        self.assertEqual(len(polygon), 3)
        self.assertAlmostEqual(polygon_area(polygon), 8.0)

    def test_bad_shapes_are_refused_with_a_reason(self):
        many_points = [(index * 0.001, 0.5) for index in range(300)]
        cases = {
            "needs at least 3": [(0, 0), (1, 1)],
            "crosses itself": [(0, 0), (4, 4), (4, 0), (0, 4)],
            "finite": [(0, 0), (float("nan"), 1), (2, 2)],
            "sanity limit": [(0, 0), (999.0, 0), (0, 1)],
            "zero area": [(0, 0), (1, 0), (2, 0)],
            "cap": many_points,
        }
        for fragment, points in cases.items():
            with self.subTest(fragment=fragment):
                with self.assertRaises(ValueError) as caught:
                    validate_polygon(points)
                self.assertIn(fragment, str(caught.exception))

    def test_validation_messages_name_the_polygon(self):
        with self.assertRaises(ValueError) as caught:
            validate_polygon([(0, 0), (1, 1)], where="sketch polygon 2")
        self.assertIn("sketch polygon 2", str(caught.exception))

    def test_a_non_iterable_polygon_is_a_value_error(self):
        # red-team finding (Yotta §6s): validate_polygon(5) raised TypeError; the
        # documented contract is ValueError with a reason.
        with self.assertRaises(ValueError) as caught:
            validate_polygon(5)
        self.assertIn("iterable", str(caught.exception))


class TestProjectCarriesSketchPolygons(unittest.TestCase):
    def test_round_trip_and_backwards_compatible_files(self):
        project = replace(make_project(), sketch_polygons=(RECT_M,))
        data = project.to_dict()
        self.assertIn("sketch_polygons", data)
        again = Project.from_json(project.to_json())
        self.assertEqual(len(again.sketch_polygons), 1)
        self.assertEqual(again.sketch_polygons[0][1], (0.020, -0.005))
        plain = make_project()
        self.assertNotIn("sketch_polygons", plain.to_dict())

    def test_check_warns_about_the_additive_sheet(self):
        project = replace(make_project(), sketch_polygons=(RECT_M,))
        self.assertTrue(any("additive" in warning for warning in project.check()))


class TestDeckDrawsSketchPolygons(unittest.TestCase):
    def setUp(self):
        self.solver = OpenEMSSolver()

    def test_polygons_render_as_metal_with_snapping_and_compile(self):
        project = replace(make_project(), sketch_polygons=(RECT_M,))
        script = self.solver.render_script(project)
        self.assertIn('CSX.AddMetal("sketch")', script)
        self.assertIn("AddPolygon", script)
        self.assertIn(
            "SKETCH_POLYGONS = [[[0.0, 0.02, 0.02, 0.0], [-0.005, -0.005, 0.005, 0.005]]]",
            script,
            "the literal must be the [xs, ys] form AddPolygon wants, in metres",
        )
        compile(script, "sim.py", "exec")

    def test_the_deck_binding_sweep_sees_no_unbound_names(self):
        project = replace(make_project(), sketch_polygons=(RECT_M,))
        script = self.solver.render_script(project)
        bound, used = _bound_and_used(script)
        risky = sorted(used - bound - WHITELIST)
        self.assertEqual(risky, [], "the new deck block must not add unbound-local patterns")

    def test_a_plain_project_renders_an_empty_sketch_list(self):
        """The block is always rendered - it is a text template - so an empty list is
        what keeps it inert at run time."""
        script = self.solver.render_script(make_project())
        self.assertIn("SKETCH_POLYGONS = []", script)

    def test_a_polygon_outside_the_ground_plate_is_refused(self):
        outside = ((0.2, -0.005), (0.24, -0.005), (0.24, 0.005))
        project = replace(make_project(), sketch_polygons=(outside,))
        with self.assertRaises(ValueError) as caught:
            self.solver.render_script(project)
        self.assertIn("outside the ground plate", str(caught.exception))


class TestShapeConversion(unittest.TestCase):
    def test_closed_shapes_become_polygons_and_traces_are_skipped(self):
        from openantenna.geometry.sketch import shapes_to_polygons

        shapes = [
            {"kind": "block", "points": [[0, 0], [20, 0], [20, 10], [0, 10]], "thickness": "1.6"},
            {"kind": "polyline", "points": [[0, 12], [5, 15]], "closed": False},
        ]
        polygons, notes = shapes_to_polygons(shapes)
        self.assertEqual(len(polygons), 1)
        self.assertAlmostEqual(polygon_area(polygons[0]), 200e-6, places=12)  # 20x10 mm, in metres
        self.assertTrue(any("skipped" in note for note in notes))

    def test_a_circle_becomes_chords_like_the_dxf_reader(self):
        from openantenna.geometry.sketch import shapes_to_polygons

        shapes = [{"kind": "circle", "points": [[20, 15], [25, 15]]}]
        polygons, notes = shapes_to_polygons(shapes)
        self.assertEqual(notes, [])
        self.assertEqual(len(polygons[0]), 48)  # 48 chords, the closing point deduped


if __name__ == "__main__":
    unittest.main()
