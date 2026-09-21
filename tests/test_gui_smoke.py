"""Smoke test for the desktop GUI.

The GUI needs PySide6 plus a Qt platform plugin.  This test runs Qt with the
``offscreen`` platform so it works on a machine without a display, and it skips
cleanly when PySide6 is not installed - the core must never depend on the GUI.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAVE_PYSIDE = True
except Exception:  # pragma: no cover - depends on the environment
    HAVE_PYSIDE = False


@unittest.skipUnless(HAVE_PYSIDE, "PySide6 is not installed; the core does not need it")
class TestMainWindow(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        from openantenna.gui.main_window import MainWindow

        return MainWindow()

    def test_window_builds_with_four_tabs(self):
        window = self._window()
        tabs = window.centralWidget()
        self.assertEqual(tabs.count(), 4)
        titles = [tabs.tabText(i) for i in range(tabs.count())]
        self.assertEqual(
            titles, ["Material & composite", "Design", "Simulate", "Results"]
        )
        window.close()

    def test_material_tab_lists_the_built_ins(self):
        window = self._window()
        material_tab = window.centralWidget().widget(0)
        self.assertGreaterEqual(material_tab.table.rowCount(), 7)
        window.close()

    def test_composite_evaluation_produces_output(self):
        window = self._window()
        material_tab = window.centralWidget().widget(0)
        material_tab.evaluate()
        text = material_tab.mix_output.toPlainText()
        self.assertIn("Wiener", text)
        window.close()

    def test_design_tab_synthesises_a_patch(self):
        window = self._window()
        design_tab = window.centralWidget().widget(1)
        design_tab.synthesise()
        text = design_tab.summary.toPlainText()
        self.assertIn("patch W x L", text)
        window.close()

    def test_design_tab_builds_a_project(self):
        window = self._window()
        design_tab = window.centralWidget().widget(1)
        project = design_tab.current_project()
        self.assertEqual(project.array.nx, 4)
        self.assertGreater(project.patch.width_m or 0.0, 0.0)
        window.close()


if __name__ == "__main__":
    unittest.main()
