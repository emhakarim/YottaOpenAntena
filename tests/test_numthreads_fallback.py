"""P0 regression: a generated model must still RUN on the published openEMS build.

openEMS 0.37.0-rc2 — the build the project's own verification document used — rejects
the ``numthreads`` keyword with ``AssertionError: Unknown keyword arguments``, so every
generated model died on line 1 of the FDTD setup.  Static tests could not see it; running
a generated model against a real install did.

The generator now asks for the keyword and falls back cleanly.  These tests pin that.
"""

from __future__ import annotations

import unittest

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
        name="numthreads-probe",
        substrate=SubstrateStackup.single("PTFE", 1.6e-3),
        patch=PatchGeometry(width_m=0.049, length_m=0.041, feed_mode="inset"),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.083e9, stop_hz=2.817e9, points=21),
    )


class TestNumThreadsFallback(unittest.TestCase):
    def test_the_script_asks_for_threads_and_catches_the_rejection(self):
        script = OpenEMSSolver().render_script(_project())
        self.assertIn("numthreads=NUM_THREADS", script)
        self.assertIn("except (TypeError, AssertionError) as _threads_exc:", script)
        self.assertIn("has no numthreads support", script)

    def test_the_plain_construction_is_always_present(self):
        script = OpenEMSSolver().render_script(_project())
        self.assertIn("FDTD = openEMS(NrTS=MAX_TS, EndCriteria=END_CRITERIA)\n", script)

    def test_forcing_threads_does_not_change_the_rendered_card_set(self):
        """The knob must not leak into the model geometry."""
        a = OpenEMSSolver().render_script(_project())
        b = OpenEMSSolver(numthreads=4).render_script(_project())
        strip = lambda text: [l for l in text.splitlines() if "THREADS" not in l and "numthreads" not in l]
        self.assertEqual(strip(a), strip(b))


if __name__ == "__main__":
    unittest.main()
