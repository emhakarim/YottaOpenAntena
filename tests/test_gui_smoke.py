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


    def test_design_tab_shows_a_layout_preview_next_to_the_array_factor(self):
        """G-8: the plot must show the geometry it describes, not only a curve."""
        window = self._window()
        design_tab = window.centralWidget().widget(1)
        if design_tab.figure is None:
            self.skipTest("matplotlib is not installed")
        design_tab.synthesise()
        axes = design_tab.figure.axes
        self.assertGreaterEqual(len(axes), 2, "expected a geometry panel and a factor panel")
        geometry = axes[0]
        # 4x4 patches plus the substrate outline
        self.assertGreaterEqual(len(geometry.patches), 17)
        self.assertEqual(geometry.get_aspect(), 1.0)
        window.close()

    def test_results_tab_reports_provenance_and_far_field(self):
        """The run's own files must be summarised: settings, convergence, far field."""
        import json
        import tempfile
        from pathlib import Path

        window = self._window()
        results_tab = window.centralWidget().widget(3)
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "s11.csv").write_text(
                "freq_hz,s11_re,s11_im\n"
                "2.40e9,-0.30,0.10\n"
                "2.45e9,-0.02,0.01\n"
                "2.50e9,-0.35,0.12\n",
                encoding="utf-8",
            )
            (run / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "substrate": {"material": "PTFE", "epsilon_r": 2.1, "thickness_m": 0.0016},
                        "mesh": {"cells_per_wavelength": 15},
                        "boundary": "PML",
                        "pml_cells": 8,
                        "port_refine": True,
                        "metal_edge_snapping": True,
                        "nf2ff": False,
                        "end_criteria": 1e-4,
                        "max_timesteps": 400000,
                    }
                ),
                encoding="utf-8",
            )
            (run / "run_summary.json").write_text(
                json.dumps({"converged": True, "timesteps": 24180}), encoding="utf-8"
            )
            (run / "nf2ff_summary.csv").write_text(
                "freq_hz,directivity_lin,directivity_dbi,prad_w,p_acc_w,eta_rad\n"
                "2.45e9,4.145114,6.175364,1.46e-29,2.66e-29,0.548602\n",
                encoding="utf-8",
            )
            (run / "nf2ff_pattern.csv").write_text(
                "theta_deg,phi_deg,e_norm\n"
                "0.0,0.0,0.1\n"
                "90.0,0.0,1.0\n"
                "180.0,0.0,0.2\n"
                "0.0,90.0,0.3\n"
                "90.0,90.0,0.7\n",
                encoding="utf-8",
            )
            results_tab.path.setText(str(run))
            results_tab.load()
            text = results_tab.metrics.toPlainText()
            if results_tab.figure is not None:
                self.assertTrue(
                    any(getattr(axis, "name", "") == "polar" for axis in results_tab.figure.axes),
                    "a pattern CSV must produce a polar cut",
                )

        self.assertIn("resonance", text)
        self.assertIn("port_refine True", text)
        self.assertIn("converged=True", text)
        self.assertIn("24180", text)
        self.assertIn("substrate", text)
        window.close()


    def test_results_tab_flags_an_impossible_efficiency(self):
        """eta_rad > 1 is physically impossible: the panel must say so, not print it.

        The real tutorial run reports eta_rad = 55.15 at its own resonance, so this is an
        observed case, not a hypothetical one.
        """
        import json
        import tempfile
        from pathlib import Path

        window = self._window()
        results_tab = window.centralWidget().widget(3)
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "s11.csv").write_text(
                "freq_hz,s11_re,s11_im\n"
                "2.40e9,-0.30,0.10\n"
                "2.45e9,-0.02,0.01\n"
                "2.50e9,-0.35,0.12\n",
                encoding="utf-8",
            )
            (run / "nf2ff_summary.csv").write_text(
                "freq_hz,directivity_lin,directivity_dbi,prad_w,p_acc_w,eta_rad\n"
                "2.45e9,4.145114,6.175364,1.28e-27,2.33e-29,55.1513\n",
                encoding="utf-8",
            )
            results_tab.path.setText(str(run))
            results_tab.load()
            text = results_tab.metrics.toPlainText()

        self.assertIn("WARNING: radiation efficiency outside (0, 1]", text)
        self.assertIn("55.15", text)
        window.close()

    def test_results_tab_does_not_cry_wolf_for_a_valid_efficiency(self):
        """A sane efficiency (0.55) must not trigger the warning."""
        import tempfile
        from pathlib import Path

        window = self._window()
        results_tab = window.centralWidget().widget(3)
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "s11.csv").write_text(
                "freq_hz,s11_re,s11_im\n"
                "2.40e9,-0.30,0.10\n"
                "2.45e9,-0.02,0.01\n"
                "2.50e9,-0.35,0.12\n",
                encoding="utf-8",
            )
            (run / "nf2ff_summary.csv").write_text(
                "freq_hz,directivity_lin,directivity_dbi,prad_w,p_acc_w,eta_rad\n"
                "2.45e9,4.145114,6.175364,1.28e-29,2.33e-29,0.5513\n",
                encoding="utf-8",
            )
            results_tab.path.setText(str(run))
            results_tab.load()
            text = results_tab.metrics.toPlainText()

        self.assertNotIn("WARNING: radiation efficiency", text)
        window.close()

    def test_a_bad_run_directory_reports_without_blocking(self):
        """Regression: a single-point CSV made `load()` show a *modal* dialog and the
        whole suite hung.  The failure must surface in the panel and return."""
        import tempfile
        from pathlib import Path

        window = self._window()
        results_tab = window.centralWidget().widget(3)
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "s11.csv").write_text(
                "freq_hz,s11_re,s11_im\n2.45e9,-0.02,0.01\n", encoding="utf-8"
            )
            results_tab.path.setText(str(run))
            results_tab.load()  # must return; if this blocks, the suite hangs
            text = results_tab.metrics.toPlainText()

        self.assertIn("Cannot load s11.csv", text)
        self.assertIn("at least two frequency points", text)
        window.close()


    def test_material_tab_plots_the_sensitivity_of_the_mixture(self):
        """The composite explorer must show the models *and* the Wiener bounds."""
        window = self._window()
        material_tab = window.centralWidget().widget(0)
        if material_tab.figure is None:
            self.skipTest("matplotlib is not installed")
        material_tab.evaluate()
        axes = material_tab.figure.axes[0]
        # three model curves plus the operating-point marker
        self.assertGreaterEqual(len(axes.lines), 4)
        self.assertIsNotNone(axes.get_legend())
        window.close()

    def test_design_tab_round_trips_a_project_document(self):
        """Save/load uses the neutral model, so the CLI and the GUI share one document."""
        import json
        import tempfile
        from pathlib import Path

        window = self._window()
        design_tab = window.centralWidget().widget(1)
        design_tab.nx.setValue(6)
        design_tab.ny.setValue(3)
        design_tab.spacing.setValue(0.65)
        design_tab.frequency.setValue(5.8)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "p.json"
            design_tab.save_project(str(target))
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["kind"], "openantenna.project")
            self.assertEqual(payload["array"]["nx"], 6)

            design_tab.nx.setValue(2)
            design_tab.ny.setValue(2)
            design_tab.spacing.setValue(0.3)
            design_tab.frequency.setValue(1.0)
            design_tab.load_project(str(target))

        self.assertEqual(design_tab.nx.value(), 6)
        self.assertEqual(design_tab.ny.value(), 3)
        self.assertAlmostEqual(design_tab.spacing.value(), 0.65, places=3)
        self.assertAlmostEqual(design_tab.frequency.value(), 5.8, places=3)
        self.assertIn("loaded project", design_tab.summary.toPlainText())
        window.close()


    def test_simulate_tab_queues_cases_and_names_their_directories(self):
        """The batch queue snapshots the design and pre-computes each run directory."""
        window = self._window()
        simulate_tab = window.centralWidget().widget(2)
        self.assertEqual(simulate_tab.queue_table.rowCount(), 0)

        simulate_tab.add_to_queue()
        simulate_tab.add_to_queue()
        self.assertEqual(simulate_tab.queue_table.rowCount(), 2)
        self.assertEqual(simulate_tab.queue_table.item(0, 0).text(), "queue01")
        self.assertTrue(
            simulate_tab.queue_table.item(0, 2).text().endswith("case01_queue01"),
            simulate_tab.queue_table.item(0, 2).text(),
        )
        self.assertEqual(len(simulate_tab._queue), 2)

        simulate_tab.queue_table.selectRow(0)
        simulate_tab.remove_selected()
        self.assertEqual(simulate_tab.queue_table.rowCount(), 1)
        self.assertEqual(len(simulate_tab._queue), 1)

        simulate_tab.clear_queue()
        self.assertEqual(simulate_tab.queue_table.rowCount(), 0)
        self.assertEqual(simulate_tab._queue, [])
        window.close()

    def test_running_an_empty_queue_starts_nothing(self):
        window = self._window()
        simulate_tab = window.centralWidget().widget(2)
        simulate_tab.run_queue()
        self.assertEqual(simulate_tab._workers, [], "no worker for an empty queue")
        self.assertIn("queue is empty", simulate_tab.log.toPlainText())
        window.close()


    def test_results_tab_overlays_a_second_run_and_reports_the_shift(self):
        """An A/B overlay: both curves on one panel plus the resonance shift in numbers."""
        import tempfile
        from pathlib import Path

        window = self._window()
        results_tab = window.centralWidget().widget(3)
        with tempfile.TemporaryDirectory() as tmp:
            run_a = Path(tmp) / "a"
            run_b = Path(tmp) / "b"
            run_a.mkdir()
            run_b.mkdir()
            (run_a / "s11.csv").write_text(
                "freq_hz,s11_re,s11_im\n"
                "2.40e9,-0.30,0.10\n2.45e9,-0.02,0.01\n2.50e9,-0.35,0.12\n",
                encoding="utf-8",
            )
            (run_b / "s11.csv").write_text(
                "freq_hz,s11_re,s11_im\n"
                "2.40e9,-0.20,0.05\n2.475e9,-0.02,0.01\n2.55e9,-0.25,0.09\n",
                encoding="utf-8",
            )
            results_tab.path.setText(str(run_a))
            results_tab.compare_path.setText(str(run_b))
            results_tab.load()
            text = results_tab.metrics.toPlainText()
            if results_tab.figure is not None:
                labels = [line.get_label() for line in results_tab.figure.axes[0].lines]
                # A's curve, the -10 dB threshold line, and B's overlay
                self.assertIn("B", labels, labels)
                self.assertGreaterEqual(len(labels), 3)
            results_tab.clear_compare()
            self.assertEqual(results_tab.compare_path.text(), "")

        self.assertIn("A/B compare", text)
        self.assertIn("shift", text)
        window.close()

    def test_loading_a_stacked_substrate_warns_instead_of_collapsing_it(self):
        """The generator refuses >1 dielectric layer, so the GUI must say so on load."""
        import json
        import tempfile
        from pathlib import Path

        window = self._window()
        design_tab = window.centralWidget().widget(1)
        data = design_tab.current_project().to_dict()
        data["substrate"]["layers"] = [
            {"material": "PTFE", "thickness_m": 0.0008, "role": "dielectric"},
            {"material": "FR4", "thickness_m": 0.0008, "role": "dielectric"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "stacked.json"
            target.write_text(json.dumps(data), encoding="utf-8")
            design_tab.load_project(str(target))
            text = design_tab.summary.toPlainText()

        self.assertIn("2 dielectric layers", text)
        self.assertIn("effective-medium", text)
        window.close()


    def test_design_tab_can_show_a_3d_preview_of_the_same_model(self):
        """The 3-D preview draws the same layout: no new dependency, no separate model."""
        window = self._window()
        design_tab = window.centralWidget().widget(1)
        if design_tab.figure is None:
            self.skipTest("matplotlib is not installed")
        design_tab.view_mode.setCurrentText("3-D preview")
        design_tab.synthesise()
        self.assertEqual(design_tab.figure.axes[0].name, "3d")
        # the substrate slab, the ground plate and 4x4 patches are all collections
        self.assertGreaterEqual(len(design_tab.figure.axes[0].collections), 18)
        window.close()


    def test_project_tree_shows_the_current_design(self):
        """The tree describes the model: substrate, patch, array and sweep."""
        window = self._window()
        tree = window.project_tree
        self.assertGreaterEqual(tree.topLevelItemCount(), 1)
        root = tree.topLevelItem(0)
        sections = [root.child(i).text(0) for i in range(root.childCount())]
        for expected in ("Substrate", "Patch", "Array", "Sweep"):
            self.assertIn(expected, sections)
        substrate = root.child(sections.index("Substrate"))
        self.assertIn("total thickness", [substrate.child(i).text(0) for i in range(substrate.childCount())])
        window.close()

    def test_project_tree_follows_design_changes(self):
        """Changing the design must refresh the tree without a manual call."""
        window = self._window()
        design_tab = window.centralWidget().widget(1)
        design_tab.nx.setValue(6)
        design_tab.ny.setValue(2)
        design_tab.synthesise()

        root = window.project_tree.topLevelItem(0)
        array_node = next(
            root.child(i) for i in range(root.childCount()) if root.child(i).text(0) == "Array"
        )
        self.assertEqual(array_node.text(1), "6 x 2")
        self.assertEqual(array_node.child(0).text(1), "12")
        window.close()

    def test_project_tree_marks_the_projects_own_warnings(self):
        """If the model reports a validity warning, the tree must show it."""
        window = self._window()
        design_tab = window.centralWidget().widget(1)
        # an electrically thick substrate is a real, computed warning
        design_tab.frequency.setValue(0.9)
        design_tab.height.setValue(12.0)
        design_tab.synthesise()
        expected = len(design_tab.current_project().check())

        root = window.project_tree.topLevelItem(0)
        labels = [root.child(i).text(0) for i in range(root.childCount())]
        if expected:
            self.assertIn("Warnings", labels)
            warnings_node = root.child(labels.index("Warnings"))
            self.assertEqual(warnings_node.text(1), str(expected))
        else:
            self.assertNotIn("Warnings", labels)
        window.close()


    def test_project_tree_shows_the_feed_line_width(self):
        """B2/Y-19: the tree must show the feed line the generator will draw."""
        window = self._window()
        root = window.project_tree.topLevelItem(0)
        patch_node = next(
            root.child(i) for i in range(root.childCount()) if root.child(i).text(0) == "Patch"
        )
        labels = [patch_node.child(i).text(0) for i in range(patch_node.childCount())]
        self.assertIn("feed line width", labels)
        window.close()


    def test_results_tab_shows_a_coupling_matrix_from_port_folders(self):
        """Phase 2 #4 toolkit side: the GUI must show coupling, not only the API."""
        import json
        import tempfile
        from pathlib import Path
        from test_port_matrix_reader import write_port

        window = self._window()
        results_tab = window.centralWidget().widget(3)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "array"
            for driven in (1, 2, 3):
                run = folder / f"port{driven}"
                run.mkdir(parents=True)
                for port in (1, 2, 3):
                    write_port(
                        run / f"port_{port}.csv",
                        incident=1 + 0j,
                        reflected=(0.2 + 0.1j) if port == driven else (0.05 + 0j),
                    )
                (run / "run_summary.json").write_text(
                    json.dumps({"converged": True, "timesteps": 1000}), encoding="utf-8"
                )
            results_tab.coupling_path.setText(str(folder))
            results_tab.load_coupling()
            rows = results_tab.coupling_table.rowCount()
            off_diagonal = results_tab.coupling_table.item(0, 1).text()
            note = results_tab.coupling_note.text()

        self.assertEqual(rows, 3)
        # 0.05 is -26.0 dB
        self.assertTrue(off_diagonal.startswith("-26"), off_diagonal)
        self.assertIn("Worst coupling", note)
        self.assertIn("converged", note)
        window.close()

    def test_a_coupling_folder_without_port_runs_reports_instead_of_guessing(self):
        import tempfile
        from pathlib import Path

        window = self._window()
        results_tab = window.centralWidget().widget(3)
        with tempfile.TemporaryDirectory() as tmp:
            results_tab.coupling_path.setText(str(Path(tmp)))
            results_tab.load_coupling()
            note = results_tab.coupling_note.text()
        self.assertIn("coupling not loaded", note)
        self.assertIn("port<N>", note)
        window.close()


if __name__ == "__main__":
    unittest.main()
