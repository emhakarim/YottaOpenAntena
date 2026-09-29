"""Multi-layer dielectric stackup -> deck: one material box per layer (plan item #1).

The single-layer path is untouched: the patch-side (top) layer keeps the name "substrate",
the same constants, and the same mesh; the extra layers are additive boxes below it, and
every layer interface becomes an exact mesh line.  Two honest gates: the dispersive
(debye) loss model is single-layer and refuses, and a stacked project without explicit
patch dimensions refuses too, because the synthesis formulas assume one dielectric.
"""

from __future__ import annotations

import ast
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openantenna.materials.library import get_material  # noqa: E402
from openantenna.model.project import LayerSpec, Project, SubstrateStackup  # noqa: E402
from openantenna.solvers.openems import EPS0, OpenEMSSolver  # noqa: E402
from test_generated_deck_bindings import WHITELIST, _bound_and_used  # noqa: E402
from test_openems_gen import make_project  # noqa: E402


def make_stacked() -> Project:
    """FR-4 below, PTFE at the patch - a two-layer stackup with explicit patch dimensions."""
    project = make_project()
    project.substrate = SubstrateStackup(
        layers=[
            LayerSpec(material="FR-4", thickness_m=0.8e-3),  # bottom
            LayerSpec(material="PTFE", thickness_m=0.8e-3),  # top, at the patch
        ]
    )
    project.patch.width_m = 30.7e-3
    project.patch.length_m = 29.4e-3
    return project


def _literal(script: str, name: str):
    match = re.search(r"^\s*%s = (\[.*\])$" % re.escape(name), script, re.MULTILINE)
    assert match, "literal %s not found in the deck" % name
    return ast.literal_eval(match.group(1))


class TestStackedSubstrateDeck(unittest.TestCase):
    def setUp(self):
        self.solver = OpenEMSSolver()

    def test_two_layers_render_one_box_each_with_correct_extents(self):
        script = self.solver.render_script(make_stacked())
        self.assertIn("MULTI_LAYER = True", script)
        top_z = float(re.search(r"^SUBSTRATE_TOP_Z = ([0-9eE.+-]+)", script, re.MULTILINE).group(1))
        self.assertAlmostEqual(top_z, -0.8e-3, places=12)
        extra = _literal(script, "SUBSTRATE_EXTRA")
        self.assertEqual(len(extra), 1)
        z0, z1, eps, kappa, mu = extra[0]
        self.assertAlmostEqual(z0, -1.6e-3, places=12)
        self.assertAlmostEqual(z1, -0.8e-3, places=12)
        fr4 = get_material("FR-4")
        self.assertAlmostEqual(eps, fr4.epsilon_r, places=12)
        self.assertAlmostEqual(mu, fr4.mu_r, places=12)
        expected_kappa = (
            2.0 * math.pi * make_stacked().sweep.center_hz * EPS0 * fr4.epsilon_r * fr4.tan_delta
        )
        self.assertAlmostEqual(kappa, expected_kappa, places=6)

    def test_interface_line_is_added_and_the_deck_compiles(self):
        script = self.solver.render_script(make_stacked())
        match = re.search(r"if MULTI_LAYER:\n    mesh\.AddLine\(\"z\", (\[[0-9eE.,; +\-]*\])\)", script)
        self.assertTrue(match, "the interface mesh line is missing")
        interfaces = ast.literal_eval(match.group(1))
        self.assertEqual(len(interfaces), 1)
        self.assertAlmostEqual(interfaces[0], -0.8e-3, places=12)
        compile(script, "sim.py", "exec")
        bound, used = _bound_and_used(script)
        self.assertEqual(sorted(used - bound - WHITELIST), [])

    def test_single_layer_deck_stays_on_the_old_path(self):
        script = self.solver.render_script(make_project())
        self.assertIn("MULTI_LAYER = False", script)
        self.assertEqual(_literal(script, "SUBSTRATE_EXTRA"), [])
        self.assertNotIn("substrate_2", script)
        # the top-layer bottom equals the full thickness for a single layer (old value)
        top_z = float(re.search(r"^SUBSTRATE_TOP_Z = ([0-9eE.+-]+)", script, re.MULTILINE).group(1))
        self.assertAlmostEqual(top_z, -1.6e-3, places=12)

    def test_debye_and_unsynthesised_stackups_are_refused(self):
        with self.assertRaises(ValueError) as caught:
            OpenEMSSolver(loss_model="debye").render_script(make_stacked())
        self.assertIn("single-layer", str(caught.exception))
        unsynthesised = make_stacked()
        unsynthesised.patch.width_m = None
        unsynthesised.patch.length_m = None
        with self.assertRaises(ValueError) as caught:
            self.solver.render_script(unsynthesised)
        self.assertIn("explicit patch dimensions", str(caught.exception))

    def test_lossless_model_zeroes_the_extra_kappa(self):
        script = OpenEMSSolver(loss_model="none").render_script(make_stacked())
        extra = _literal(script, "SUBSTRATE_EXTRA")
        self.assertEqual(extra[0][3], 0.0)

    def test_manifest_records_every_layer(self):
        with tempfile.TemporaryDirectory() as folder:
            run = self.solver.prepare(make_stacked(), Path(folder) / "run")
            manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
        layers = manifest["substrate"]["layers"]
        self.assertEqual([entry["material"] for entry in layers], ["FR-4", "PTFE"])
        self.assertEqual(len(layers), 2)


if __name__ == "__main__":
    unittest.main()
