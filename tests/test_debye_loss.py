"""Phase 2 #1, native path: a dispersive (Debye) substrate handed to openEMS.

The earlier "CSXCAD has no dispersive API" conclusion was wrong - the classes live in the
CSXCAD.CSProperties submodule.  These tests pin the emitted model, the pole derivation, and
the fact that the loss models stay separate.
"""

from __future__ import annotations

import math
import re
import unittest
from unittest import mock

from openantenna.materials.library import Material
from openantenna.model.project import FrequencySweep, Project, SubstrateStackup
from openantenna.solvers.openems import OpenEMSSolver

F0 = 2.45e9


def _project(material_name: str) -> Project:
    return Project(
        name="debye-probe",
        substrate=SubstrateStackup(layers=[{"material": material_name, "thickness_m": 1.6e-3}]),
        sweep=FrequencySweep(start_hz=F0 * 0.8, stop_hz=F0 * 1.2, points=41),
    )


def _const(text: str, name: str) -> float:
    match = re.search(rf"^{name} = ([0-9.eE+-]+)", text, re.MULTILINE)
    assert match, f"{name} not found in the generated script"
    return float(match.group(1))


class TestDebyeEmission(unittest.TestCase):
    def test_script_uses_the_dispersive_api_correctly(self):
        text = OpenEMSSolver(loss_model="debye").render_script(_project("PTFE"))
        self.assertIn("from CSXCAD import CSProperties as _CSProp", text)
        self.assertIn('CSPropDebyeMaterial(CSX.GetParameterSet(), "substrate")', text)
        self.assertIn("SetDispersionOrder(1)", text)
        # the pole index comes first, and it is 0-based
        self.assertIn(
            "SetDispersiveMaterialProperty(0, eps_delta=DEBYE_EPS_DELTA, eps_relax=DEBYE_TAU)", text
        )
        self.assertIn("CSX.AddProperty(substrate)", text, "the property must be registered")
        self.assertIn('LOSS_MODEL = "debye"', text)

    def test_pole_reproduces_the_requested_loss_at_the_centre(self):
        text = OpenEMSSolver(loss_model="debye").render_script(_project("PTFE"))
        eps_inf = _const(text, "DEBYE_EPS_INF")
        delta = _const(text, "DEBYE_EPS_DELTA")
        tau = _const(text, "DEBYE_TAU")
        w = 2.0 * math.pi * F0
        tan = (w * tau * delta) / (eps_inf * (1.0 + (w * tau) ** 2) + delta)
        self.assertAlmostEqual(tan, 4.0e-4, delta=4.0e-4 * 0.02)
        self.assertAlmostEqual(tau, 1.0 / w, delta=1.0 / w * 1e-9, msg="relaxation at omega*tau=1")

    def test_library_dispersion_is_used_verbatim(self):
        explicit = Material(
            name="PTFE-debye",
            epsilon_r=2.1,
            tan_delta=4.0e-4,
            kind="dielectric",
            dispersion={"model": "debye", "eps_inf": 2.05, "delta_eps": 0.12, "tau_s": 3.0e-11},
        )
        with mock.patch("openantenna.materials.library.get_material", return_value=explicit):
            text = OpenEMSSolver(loss_model="debye").render_script(_project("PTFE-debye"))
        self.assertAlmostEqual(_const(text, "DEBYE_EPS_INF"), 2.05)
        self.assertAlmostEqual(_const(text, "DEBYE_EPS_DELTA"), 0.12)
        self.assertAlmostEqual(_const(text, "DEBYE_TAU"), 3.0e-11)

    def test_lossless_substrate_gets_no_pole(self):
        lossless = Material(name="lossless", epsilon_r=2.1, tan_delta=0.0, kind="dielectric")
        with mock.patch("openantenna.materials.library.get_material", return_value=lossless):
            text = OpenEMSSolver(loss_model="debye").render_script(_project("lossless"))
        self.assertAlmostEqual(_const(text, "DEBYE_EPS_DELTA"), 0.0)
        self.assertIn("lossless substrate", text)
        self.assertIn('elif LOSS_MODEL == "debye" and DEBYE_EPS_DELTA > 0:', text)


class TestOtherModelsAreUnaffected(unittest.TestCase):
    def test_kappa_script_has_no_dispersive_material(self):
        text = OpenEMSSolver(loss_model="kappa").render_script(_project("FR-4"))
        self.assertNotIn('LOSS_MODEL = "debye"', text)
        self.assertIn('LOSS_MODEL = "kappa"', text)
        self.assertGreater(_const(text, "KAPPA_SUB"), 0.0)

    def test_none_is_still_lossless(self):
        text = OpenEMSSolver(loss_model="none").render_script(_project("FR-4"))
        self.assertAlmostEqual(_const(text, "KAPPA_SUB"), 0.0)
        self.assertNotIn('LOSS_MODEL = "debye"', text)

    def test_unknown_model_is_rejected(self):
        with self.assertRaises(ValueError):
            OpenEMSSolver(loss_model="drude")


if __name__ == "__main__":
    unittest.main()


