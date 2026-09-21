"""A4: the generated model must refine the mesh around the lumped port.

The port feeds a load across the substrate; discretising it with the coarse
free-space cell adds series inductance and is a candidate for the residual
construction bias (Yotta review item A4).  These tests pin the behaviour and the
ability to switch it off for an A/B run.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openantenna.model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver


def _project() -> Project:
    return Project(
        name="port-refine-probe",
        substrate=SubstrateStackup.single("PTFE", 1.6e-3),
        patch=PatchGeometry(
            width_m=0.049142672841793994,
            length_m=0.041378916081297096,
            feed_mode="inset",
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.083e9, stop_hz=2.817e9, points=101),
    )


class TestPortRefinement(unittest.TestCase):
    def test_the_script_refines_the_port_region(self):
        script = OpenEMSSolver().render_script(_project())
        self.assertIn("PORT_REFINE = True", script)
        self.assertIn('np.linspace(FEED_X - _port_half, FEED_X + _port_half, 5)', script)
        self.assertIn('np.linspace(FEED_Y - _port_half, FEED_Y + _port_half, 5)', script)
        self.assertIn("PORT REFINE:", script)

    def test_refinement_can_be_switched_off_for_an_ab_test(self):
        script = OpenEMSSolver(port_refine=False).render_script(_project())
        self.assertIn("PORT_REFINE = False", script)

    def test_manifest_records_the_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            OpenEMSSolver().prepare(_project(), root)
            manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["mesh"]["port_refine"])

            OpenEMSSolver(port_refine=False).prepare(_project(), root / "off")
            off = json.loads((root / "off" / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(off["mesh"]["port_refine"])


if __name__ == "__main__":
    unittest.main()
