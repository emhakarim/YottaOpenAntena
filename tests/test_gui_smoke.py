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


    def test_simulate_tab_shows_a_progress_bar_that_says_what_it_measures(self):
        window = self._window()
        simulate_tab = window.centralWidget().widget(2)
        bar = simulate_tab.progress_bar
        self.assertEqual(bar.value(), 0)
        self.assertEqual(bar.maximum(), 100)
        # the label must not let "6 %" read as "barely started"
        self.assertIn("step cap", bar.format())
        window.close()

    def test_worker_maps_solver_progress_to_a_percentage(self):
        from pathlib import Path

        from openantenna.gui.worker import SimulateWorker
        from openantenna.solvers.progress import SolverProgress

        window = self._window()
        project = window.centralWidget().widget(1).current_project()
        worker = SimulateWorker(project, Path("runs"))
        worker._cap_steps = 400000
        seen: list[int] = []
        worker.progress_value.connect(seen.append)
        worker._on_progress(SolverProgress(timestep=100000, elapsed_s=100.0))
        worker._on_progress(SolverProgress(timestep=400000, elapsed_s=400.0))
        # clamped to 100 even if the solver overshoots its own cap
        worker._on_progress(SolverProgress(timestep=999999, elapsed_s=900.0))
        self.assertEqual(seen, [25, 100, 100])
        window.close()


    def test_simulate_tab_exposes_the_ab_knobs(self):
        """R-6: an A/B must not require hand-editing a generated script.

        The knobs exist in the library and the CLI; the GUI was the missing piece.  The
        checkboxes must start at the library defaults (no drift) and their state must
        reach the worker through ``_solver_kwargs``.
        """
        from openantenna.solvers.openems import OpenEMSSolver

        window = self._window()
        simulate_tab = window.centralWidget().widget(2)
        library = OpenEMSSolver()

        self.assertEqual(simulate_tab.port_refine.isChecked(), library.port_refine)
        self.assertEqual(simulate_tab.edge_snapping.isChecked(), library.metal_edge_snapping)
        self.assertEqual(simulate_tab.nf2ff.isChecked(), library.nf2ff)

        kwargs = simulate_tab._solver_kwargs()
        for name in ("port_refine", "metal_edge_snapping", "nf2ff"):
            self.assertEqual(kwargs[name], getattr(library, name), name)

        # flipping a box must change what the worker receives
        simulate_tab.port_refine.setChecked(not library.port_refine)
        simulate_tab.nf2ff.setChecked(not library.nf2ff)
        flipped = simulate_tab._solver_kwargs()
        self.assertEqual(flipped["port_refine"], not library.port_refine)
        self.assertEqual(flipped["nf2ff"], not library.nf2ff)
        window.close()


if __name__ == "__main__":
    unittest.main()
