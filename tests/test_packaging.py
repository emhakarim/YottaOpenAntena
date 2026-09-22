"""Guards for the frozen-GUI packaging.

A packaging change is easy to get silently wrong (a spec that pulls in the solver, a
launcher that no longer matches the console script, a `--selftest` that stops working).
These checks are textual and cheap; the real verification is `scripts/build_gui.py`, which
builds and runs the frozen executable.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = REPO_ROOT / "packaging" / "openantenna-gui.spec"
LAUNCHER = REPO_ROOT / "packaging" / "gui_launcher.py"
BUILDER = REPO_ROOT / "scripts" / "build_gui.py"


class TestPackaging(unittest.TestCase):
    def test_spec_launcher_and_builder_exist(self):
        for path in (SPEC, LAUNCHER, BUILDER):
            self.assertTrue(path.is_file(), f"{path} is missing")

    def test_spec_excludes_the_solver_and_the_tools_folder(self):
        """The frozen app must not carry openEMS (GPL) or the local tools/ directory."""
        text = SPEC.read_text(encoding="utf-8")
        self.assertIn('excludes=["openEMS", "CSXCAD", "tools"]', text)
        self.assertIn("gui_launcher.py", text)

    def test_launcher_matches_the_declared_console_script(self):
        launcher = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("from openantenna.gui import main", launcher)
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('openantenna-gui = "openantenna.gui:main"', pyproject)

    def test_pyinstaller_is_declared_as_a_build_extra(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("packaging = [", pyproject)
        self.assertIn("pyinstaller", pyproject)

    def test_builder_verifies_the_frozen_binary(self):
        """The builder must run the frozen app, not only claim the build succeeded."""
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn("--selftest", text)
        self.assertIn("probe.returncode", text)

    def test_documentation_states_the_solver_is_not_bundled(self):
        doc = (REPO_ROOT / "docs" / "packaging.md").read_text(encoding="utf-8")
        self.assertIn("openEMS", doc)
        self.assertIn("OPENEMS_ROOT", doc)

    def test_selftest_flag_returns_zero_on_a_source_checkout(self):
        """`--selftest` is the verification hook: it must work without a solver."""
        try:
            from openantenna.gui.main_window import run_gui
        except ImportError:  # PySide6 missing
            self.skipTest("PySide6 is not installed")
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        self.assertEqual(run_gui(["openantenna-gui", "--selftest"]), 0)


if __name__ == "__main__":
    unittest.main()
