"""Deck-builder wiring tests for the corporate feed tree (Phase 2 #5b, builder half)."""

from __future__ import annotations

import ast
import unittest

from openantenna.solvers.openems import OpenEMSSolver

try:
    from test_openems_gen import make_project
except ImportError:  # pragma: no cover - direct execution
    from tests.test_openems_gen import make_project  # type: ignore


def _corporate_project(nx: int = 1, ny: int = 4):
    project = make_project(nx=nx, ny=ny)
    project.patch.feed_mode = "corporate"
    project.patch.feed_inset_m = 0.0
    project.patch.feed_line_width_m = 0.0
    return project


def _tree_rectangles(script: str) -> list[tuple[float, float, float, float]]:
    """Pull the drawn rectangles back out of the rendered deck."""
    for node in ast.walk(ast.parse(script)):
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", None) == "_tree_rects" for target in node.targets
        ):
            return [tuple(float(value) for value in rect) for rect in ast.literal_eval(node.value)]
    raise AssertionError("the rendered deck never assigns _tree_rects")


def _constant(script: str, name: str) -> float:
    """Read a numeric constant the deck defines, without duplicating the builder's maths."""
    for line in script.splitlines():
        if line.startswith(f"{name} = "):
            return float(line.split("=", 1)[1].split("#")[0].strip())
    raise AssertionError(f"{name} not found in the rendered deck")


class TestCorporateFeedDeck(unittest.TestCase):
    def test_a_power_of_two_row_draws_the_tree(self):
        script = OpenEMSSolver().render_script(_corporate_project(1, 4))
        self.assertIn('CSX.AddMetal("feed_tree")', script)
        self.assertIn("FEED TREE:", script)
        self.assertEqual(script.count("_tree.AddBox("), 1, "one AddBox inside the loop")
        rects = _tree_rectangles(script)
        self.assertGreater(len(rects), 0)
        compile(script, "sim.py", "exec")

    def test_drawn_rectangles_match_the_tree_structure(self):
        """trunk(1) + transformers(2**L - 1) + arms(2**(L+1) - 2) = 3*2**L - 2 for n = 2**L."""
        for n_elements in (2, 4, 8):
            with self.subTest(n_elements=n_elements):
                script = OpenEMSSolver().render_script(_corporate_project(1, n_elements))
                drawn = _tree_rectangles(script)
                self.assertEqual(len(drawn), 3 * n_elements - 2)
                leaf_y = -_constant(script, "L_PATCH") / 2.0
                ground_y = _constant(script, "GROUND_Y")
                # arm rectangles are centred on the leaf line, so their top edge sits half a
                # line width above it - the tolerance is 5 mm against ~3 mm printed lines
                self.assertLessEqual(
                    max(rect[3] for rect in drawn),
                    leaf_y + 0.005,
                    "no tree metal meaningfully above the element feed edge",
                )
                self.assertGreater(
                    min(rect[1] for rect in drawn),
                    -ground_y / 2.0,
                    "no tree metal off the ground plane",
                )

    def test_a_2d_grid_now_draws_the_two_layer_tree(self):
        """Phase 2 #5b: the 2-D grid is implemented, so the old refusal must be gone."""
        script = OpenEMSSolver().render_script(_corporate_project(2, 2))
        self.assertIn('CSX.AddMetal("feed_layer")', script)
        self.assertIn('CSX.AddMetal("row_trees")', script)
        self.assertIn('CSX.AddMetal("feed_risers")', script)
        self.assertIn("FEED TREE 2D:", script)
        compile(script, "sim.py", "exec")

    def test_a_2d_grid_that_is_not_power_of_two_per_axis_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            OpenEMSSolver().render_script(_corporate_project(2, 3))
        self.assertIn("power-of-two", str(caught.exception))

    def test_non_power_of_two_counts_are_refused(self):
        with self.assertRaises(ValueError) as caught:
            OpenEMSSolver().render_script(_corporate_project(1, 3))
        self.assertIn("power-of-two", str(caught.exception))

    def test_element_ports_with_a_tree_is_refused_not_faked(self):
        project = _corporate_project(1, 4)
        with self.assertRaises(ValueError) as caught:
            OpenEMSSolver(element_ports=True).render_script(project)
        self.assertIn("not wired yet", str(caught.exception))

    def test_unknown_feed_mode_is_refused(self):
        project = _corporate_project(1, 4)
        project.patch.feed_mode = "waveguide"
        with self.assertRaises(ValueError) as caught:
            OpenEMSSolver().render_script(project)
        self.assertIn("unknown feed_mode", str(caught.exception))

    def test_the_other_feed_modes_still_render(self):
        for mode in ("inset", "edge", "probe"):
            with self.subTest(mode=mode):
                project = make_project()
                project.patch.feed_mode = mode
                script = OpenEMSSolver().render_script(project)
                compile(script, "sim.py", "exec")
                self.assertEqual(
                    _tree_rectangles(script),
                    [],
                    "non-corporate modes must draw no tree metal (the block is text, not a branch)",
                )


if __name__ == "__main__":
    unittest.main()
