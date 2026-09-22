"""Main window: material/composite explorer, design synthesis, simulation, results.

The window is deliberately a thin client of the package API.  Anything that
could be done by the CLI is done by calling the same underlying functions, so the
GUI cannot drift away from the scriptable core.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..geometry.array import array_factor_plane, build_array_layout
from ..geometry.patch import synthesize_patch
from ..materials.library import get_material, list_material_names
from ..materials.mixing import (
    compare_models,
    estimate_effective_tan_delta,
    format_comparison_table,
    maxwell_wagner_warning,
    percolation_warning,
    quasi_static_warning,
)
from ..model.project import (
    ArrayConfig,
    FrequencySweep,
    PatchGeometry,
    Project,
    SubstrateStackup,
)
from ..postproc.sparams import S11Trace
from ..solvers.openems import OpenEMSSolver
from .worker import GenerateWorker, SimulateWorker


def _plot_canvas():
    """Create a matplotlib canvas that works with and without a display."""
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(5, 3), tight_layout=True)
    canvas = FigureCanvasQTAgg(figure)
    return figure, canvas


class MaterialTab(QWidget):
    """Browse the material library and explore two-phase composites."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        table_group = QGroupBox("Material library (built-in reference values, not measurements)")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["name", "eps_r", "mu_r", "tan delta", "sigma [S/m]", "kind"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.table)
        layout.addWidget(table_group)

        mix_group = QGroupBox("Composite explorer (matrix + filler)")
        mix_layout = QHBoxLayout(mix_group)
        form = QFormLayout()
        self.matrix = QDoubleSpinBox()
        self.matrix.setRange(1.0, 1000.0)
        self.matrix.setValue(2.1)
        self.filler = QDoubleSpinBox()
        self.filler.setRange(1.0, 5000.0)
        self.filler.setValue(80.0)
        self.volume_fraction = QDoubleSpinBox()
        self.volume_fraction.setRange(0.0, 0.95)
        self.volume_fraction.setSingleStep(0.05)
        self.volume_fraction.setValue(0.30)
        self.tan_matrix = QDoubleSpinBox()
        self.tan_matrix.setDecimals(6)
        self.tan_matrix.setRange(0.0, 1.0)
        self.tan_matrix.setValue(0.0004)
        self.tan_filler = QDoubleSpinBox()
        self.tan_filler.setDecimals(6)
        self.tan_filler.setRange(0.0, 1.0)
        self.tan_filler.setValue(0.001)
        self.mix_freq = QDoubleSpinBox()
        self.mix_freq.setRange(0.001, 100.0)
        self.mix_freq.setValue(2.45)
        self.mix_freq.setSuffix(" GHz")
        self.particle_size = QDoubleSpinBox()
        self.particle_size.setDecimals(3)
        self.particle_size.setRange(0.001, 1000.0)
        self.particle_size.setValue(1.0)
        self.particle_size.setSuffix(" um")
        form.addRow("matrix eps_r", self.matrix)
        form.addRow("filler eps_r", self.filler)
        form.addRow("filler volume fraction", self.volume_fraction)
        form.addRow("matrix tan delta", self.tan_matrix)
        form.addRow("filler tan delta", self.tan_filler)
        form.addRow("frequency", self.mix_freq)
        form.addRow("filler particle size", self.particle_size)
        mix_layout.addLayout(form)

        right = QVBoxLayout()
        self.evaluate_button = QPushButton("Evaluate mixing rules")
        self.evaluate_button.clicked.connect(self.evaluate)
        right.addWidget(self.evaluate_button)
        self.mix_output = QTextEdit()
        self.mix_output.setReadOnly(True)
        right.addWidget(self.mix_output)
        mix_layout.addLayout(right)
        layout.addWidget(mix_group)

        self.reload()

    def reload(self) -> None:
        names = list_material_names()
        self.table.setRowCount(len(names))
        for row, name in enumerate(names):
            material = get_material(name)
            values = [
                material.name,
                f"{material.epsilon_r:g}",
                f"{material.mu_r:g}",
                f"{material.tan_delta:g}",
                f"{material.conductivity_s_per_m:g}",
                material.kind,
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def evaluate(self) -> None:
        matrix = self.matrix.value()
        filler = self.filler.value()
        vf = self.volume_fraction.value()
        frequency = self.mix_freq.value() * 1e9
        lines = []
        try:
            lines.append(format_comparison_table(compare_models(matrix, filler, vf, frequency_hz=frequency)))
            loss = estimate_effective_tan_delta(
                matrix,
                filler,
                vf,
                tan_delta_matrix=self.tan_matrix.value(),
                tan_delta_filler=self.tan_filler.value(),
            )
            lines.append("\nEffective loss tangent (order-of-magnitude bounds)")
            for key in ("tan_delta_series", "tan_delta_parallel", "lower_bound", "upper_bound"):
                if key in loss:
                    lines.append(f"  {key:24s}: {loss[key]}")
            notes = loss.get("notes") or []
            if notes:
                lines.append("\nLimits of these estimates:")
                lines.extend(f"  - {note}" for note in notes)
            warnings = [
                percolation_warning(vf),
                maxwell_wagner_warning(frequency),
                quasi_static_warning(frequency, self.particle_size.value() * 1e-6, filler),
            ]
            relevant = [w for w in warnings if w]
            if relevant:
                lines.append("\nWARNINGS")
                lines.extend(f"  ! {w}" for w in relevant)
        except Exception as exc:
            lines.append(f"error: {type(exc).__name__}: {exc}")
        self.mix_output.setPlainText("\n".join(lines))


class DesignTab(QWidget):
    """Patch synthesis and array layout, with an array-factor plot."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        params = QGroupBox("Design parameters")
        form = QFormLayout(params)
        self.frequency = QDoubleSpinBox()
        self.frequency.setRange(0.1, 60.0)
        self.frequency.setDecimals(4)
        self.frequency.setValue(2.45)
        self.frequency.setSuffix(" GHz")
        self.material = QComboBox()
        self.material.addItems([n for n in list_material_names() if get_material(n).kind == "dielectric"])
        self.material.setCurrentText("PTFE")
        self.height = QDoubleSpinBox()
        self.height.setRange(0.01, 20.0)
        self.height.setDecimals(3)
        self.height.setValue(1.6)
        self.height.setSuffix(" mm")
        self.feed = QComboBox()
        self.feed.addItems(["inset", "edge", "probe"])
        self.nx = QSpinBox()
        self.nx.setRange(1, 64)
        self.nx.setValue(4)
        self.ny = QSpinBox()
        self.ny.setRange(1, 64)
        self.ny.setValue(4)
        self.spacing = QDoubleSpinBox()
        self.spacing.setRange(0.2, 1.5)
        self.spacing.setSingleStep(0.05)
        self.spacing.setValue(0.5)
        self.spacing.setSuffix(" lambda0")
        form.addRow("frequency", self.frequency)
        form.addRow("substrate", self.material)
        form.addRow("substrate thickness", self.height)
        form.addRow("feed", self.feed)
        form.addRow("array nx", self.nx)
        form.addRow("array ny", self.ny)
        form.addRow("element spacing", self.spacing)
        layout.addWidget(params)

        button = QPushButton("Synthesise")
        button.clicked.connect(self.synthesise)
        layout.addWidget(button)

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        layout.addWidget(self.summary)

        try:
            self.figure, self.canvas = _plot_canvas()
            layout.addWidget(self.canvas)
        except Exception as exc:  # matplotlib is optional
            self.figure = None
            self.canvas = None
            layout.addWidget(QLabel(f"Plotting unavailable: {exc}"))

    def current_project(self) -> Project:
        frequency = self.frequency.value() * 1e9
        material_name = self.material.currentText()
        height = self.height.value() * 1e-3
        design = synthesize_patch(frequency, get_material(material_name).epsilon_r, height, self.feed.currentText())
        return Project(
            name="gui-design",
            substrate=SubstrateStackup.single(material_name, height),
            patch=PatchGeometry(
                width_m=design.width_m,
                length_m=design.length_m,
                feed_mode=self.feed.currentText(),
                feed_inset_m=design.inset_depth_m or None,
            ),
            array=ArrayConfig(
                nx=self.nx.value(),
                ny=self.ny.value(),
                spacing_x_lambda0=self.spacing.value(),
                spacing_y_lambda0=self.spacing.value(),
            ),
            sweep=FrequencySweep.fractional(frequency, 0.15, points=201),
        )

    def synthesise(self) -> None:
        frequency = self.frequency.value() * 1e9
        material_name = self.material.currentText()
        epsilon_r = get_material(material_name).epsilon_r
        height = self.height.value() * 1e-3
        design = synthesize_patch(frequency, epsilon_r, height, self.feed.currentText())
        layout = build_array_layout(
            ArrayConfig(
                nx=self.nx.value(),
                ny=self.ny.value(),
                spacing_x_lambda0=self.spacing.value(),
                spacing_y_lambda0=self.spacing.value(),
            ),
            frequency,
            design,
        )
        project = self.current_project()
        lines = [design.summary(), "", layout.summary()]
        warnings = project.check()
        if warnings:
            lines.append("")
            lines.extend(f"project note: {w}" for w in warnings)
        lines.append("")
        lines.append(
            "Reminder: the transmission-line model is a first-order design aid and the "
            "generated model is not calibrated yet. Confirm with a simulation."
        )
        self.summary.setPlainText("\n".join(lines))

        if self.figure is None:
            return  # matplotlib missing; the numeric summary above is still shown
        axes = self.figure.add_subplot(111)
        axes.clear()
        samples = array_factor_plane(layout.positions_m, frequency, n_points=361, plane="e")
        axes.plot([a for a, _ in samples], [v for _, v in samples])
        axes.set_title(f"Array factor, E-plane, {self.nx.value()}x{self.ny.value()} @ {self.frequency.value():g} GHz")
        axes.set_xlabel("theta [deg]")
        axes.set_ylabel("normalised [dB]")
        axes.set_ylim(-40, 2)
        axes.grid(True)
        self.canvas.draw_idle()


class SimulateTab(QWidget):
    """Generate the openEMS model and run it, without blocking the window."""

    def __init__(self, design_tab: DesignTab) -> None:
        super().__init__()
        self.design_tab = design_tab
        layout = QVBoxLayout(self)

        settings = QGroupBox("Solver settings")
        form = QFormLayout(settings)
        self.mesh_cells = QSpinBox()
        self.mesh_cells.setRange(4, 60)
        self.mesh_cells.setValue(15)
        self.substrate_cells = QSpinBox()
        self.substrate_cells.setRange(2, 40)
        self.substrate_cells.setValue(8)
        self.loss_model = QComboBox()
        self.loss_model.addItems(["kappa", "none"])
        self.rundir = QLineEdit(str(Path.cwd() / "runs" / "gui_run"))
        self._workers: list = []
        browse = QPushButton("Browse ...")
        browse.clicked.connect(self.pick_directory)
        form.addRow("mesh cells / wavelength", self.mesh_cells)
        form.addRow("cells across substrate", self.substrate_cells)
        form.addRow("dielectric loss model", self.loss_model)

        # A/B knobs (review item R-6 / A-7).  They have existed in the library and in the
        # CLI all along, but the GUI could not set them, so an A/B needed a hand-edited
        # script -- exactly the manual step the board wants removed.  The initial state is
        # taken from the adapter itself so the GUI cannot drift from the library default.
        library_defaults = OpenEMSSolver()
        self.port_refine = QCheckBox("refine the mesh around the lumped port")
        self.port_refine.setChecked(library_defaults.port_refine)
        self.edge_snapping = QCheckBox("snap metal edges onto the grid")
        self.edge_snapping.setChecked(library_defaults.metal_edge_snapping)
        self.nf2ff = QCheckBox("record a near-to-far-field box (costs a far-field pass)")
        self.nf2ff.setChecked(library_defaults.nf2ff)
        form.addRow(self.port_refine)
        form.addRow(self.edge_snapping)
        form.addRow(self.nf2ff)
        form.addRow("run directory", self.rundir)
        form.addRow("", browse)
        layout.addWidget(settings)

        row = QHBoxLayout()
        self.status_button = QPushButton("Check solver")
        self.status_button.clicked.connect(self.check_solver)
        self.generate_button = QPushButton("Generate model")
        self.generate_button.clicked.connect(self.generate)
        self.run_button = QPushButton("Run simulation")
        self.run_button.clicked.connect(self.simulate)
        for widget in (self.status_button, self.generate_button, self.run_button):
            row.addWidget(widget)
        layout.addLayout(row)

        # Progress of the *solver*, taken from its own timestep lines.  The value is a
        # percentage of the step cap, which is an upper bound: a run normally stops on
        # the energy criterion long before it (the tutorial run finished at 6 % of its
        # cap).  The format text says so, because a bare "6 %" reads like "barely
        # started", which is a misreading that actually happened.
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(
            "%p% of the step cap (a run usually stops earlier, on energy)"
        )
        layout.addWidget(self.progress_bar)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

    def _solver_kwargs(self) -> dict:
        return {
            "mesh_cells_per_wavelength": self.mesh_cells.value(),
            "substrate_cells": self.substrate_cells.value(),
            "loss_model": self.loss_model.currentText(),
            "port_refine": self.port_refine.isChecked(),
            "metal_edge_snapping": self.edge_snapping.isChecked(),
            "nf2ff": self.nf2ff.isChecked(),
        }

    def pick_directory(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose a run directory")
        if chosen:
            self.rundir.setText(chosen)

    def check_solver(self) -> None:
        status = OpenEMSSolver(**self._solver_kwargs()).available()
        self.log.append(f"available : {status.available}")
        self.log.append(f"binary    : {status.binary_path or '-'}")
        self.log.append(f"detail    : {status.detail}")

    def _begin_work(self) -> bool:
        """Disable the buttons while a worker runs; one worker at a time (G-2)."""
        for widget in (self.status_button, self.generate_button, self.run_button):
            widget.setEnabled(False)
        if not self.rundir.text().strip():
            self.log.append(
                "FAILED: the run directory is empty (an empty path would silently write "
                "into the current working directory)"
            )
            self._end_work()
            return False
        return True

    def _end_work(self) -> None:
        for widget in (self.status_button, self.generate_button, self.run_button):
            widget.setEnabled(True)

    def _track(self, worker) -> None:
        """Hold a reference until the thread finishes, then release it.

        Overwriting ``self.worker`` while a QThread is still running can destroy the
        thread from under Qt - review item G-2.
        """
        self._workers.append(worker)

        def _cleanup() -> None:
            self._end_work()
            if worker in self._workers:
                self._workers.remove(worker)
            worker.deleteLater()

        worker.finished.connect(_cleanup)
        worker.start()

    def generate(self) -> None:
        if not self._begin_work():
            return
        self.log.append("generating model ...")
        worker = GenerateWorker(
            self.design_tab.current_project(),
            Path(self.rundir.text()),
            **self._solver_kwargs(),
        )
        worker.done.connect(lambda path: self.log.append(f"model written: {path}"))
        worker.failed.connect(lambda message: self.log.append(f"FAILED: {message}"))
        self._track(worker)

    def simulate(self) -> None:
        if not self._begin_work():
            return
        self.log.append("starting simulation (the window stays responsive) ...")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(
            "%p% of the step cap (a run usually stops earlier, on energy)"
        )
        worker = SimulateWorker(
            self.design_tab.current_project(),
            Path(self.rundir.text()),
            **self._solver_kwargs(),
        )
        worker.progress.connect(self.log.append)
        worker.progress_value.connect(self.progress_bar.setValue)
        worker.done.connect(self._finished)
        worker.failed.connect(self._failed)
        self._track(worker)

    def _finished(self, payload: dict) -> None:
        results = payload["results"]
        self.progress_bar.setFormat(
            "finished at %p% of the step cap (stopped on the energy criterion)"
        )
        self.log.append(
            "done: resonance %.4f GHz, |S11| %.2f dB, VSWR %.3f"
            % (
                results["resonance_hz"] / 1e9,
                results["worst_match_db"],
                results["vswr_at_resonance"],
            )
        )

    def _failed(self, message: str) -> None:
        self.log.append(f"FAILED: {message}")


class ResultsTab(QWidget):
    """Load a run directory and plot its S11 curve."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self.path = QLineEdit(str(Path.cwd() / "runs"))
        browse = QPushButton("Open run directory ...")
        browse.clicked.connect(self.pick)
        load = QPushButton("Load s11.csv")
        load.clicked.connect(self.load)
        row.addWidget(self.path)
        row.addWidget(browse)
        row.addWidget(load)
        layout.addLayout(row)

        self.metrics = QTextEdit()
        self.metrics.setReadOnly(True)
        self.metrics.setMaximumHeight(150)
        layout.addWidget(self.metrics)

        try:
            self.figure, self.canvas = _plot_canvas()
            layout.addWidget(self.canvas)
        except Exception as exc:  # matplotlib is optional
            self.figure = None
            self.canvas = None
            layout.addWidget(QLabel(f"Plotting unavailable: {exc}"))

    def pick(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose a run directory")
        if chosen:
            self.path.setText(chosen)

    def load(self) -> None:
        candidate = Path(self.path.text())
        csv_path = candidate / "s11.csv" if candidate.is_dir() else candidate
        try:
            trace = S11Trace.from_csv(csv_path)
            index = trace.worst_match_index()
            bands = trace.bandwidth_below(-10.0)
            impedance = trace.impedance_ohm()
            lines = [
                f"file              : {csv_path}",
                f"points            : {len(trace.frequencies_hz)}",
                f"resonance         : {trace.frequencies_hz[index] / 1e9:.4f} GHz",
                f"|S11| at resonance: {trace.db()[index]:.2f} dB   VSWR {trace.vswr()[index]:.3f}",
                f"Zin at resonance  : {impedance[index].real:.2f} "
                f"{impedance[index].imag:+.2f}j ohm",
            ]
            for start, stop, width in bands:
                lines.append(
                    f"-10 dB band       : {start / 1e9:.4f} - {stop / 1e9:.4f} GHz"
                    f"  ({width / 1e6:.1f} MHz)"
                )
            fractional = trace.fractional_bandwidth(-10.0)
            if fractional:
                lines.append(f"fractional BW     : {fractional * 100:.2f} %")
            lines.append("")
            lines.append(
                "Model output, not a measurement. See run_manifest.json for the mesh and "
                "loss model used."
            )
        except Exception as exc:
            # All of the above is inside the try: impedance_ohm() deliberately raises
            # for a phase-less trace (review item G-5), and an exception escaping into
            # the Qt event loop would go uncaught.
            QMessageBox.warning(self, "Cannot load", f"{type(exc).__name__}: {exc}")
            return
        self.metrics.setPlainText("\n".join(lines))

        if self.figure is None:
            return  # matplotlib missing; the metrics above are still shown
        axes = self.figure.add_subplot(111)
        axes.clear()
        axes.plot([f / 1e9 for f in trace.frequencies_hz], trace.db())
        axes.axhline(-10.0, linestyle="--", linewidth=0.8)
        axes.set_xlabel("frequency [GHz]")
        axes.set_ylabel("|S11| [dB]")
        axes.set_title("Input matching")
        axes.grid(True)
        self.canvas.draw_idle()


class MainWindow(QMainWindow):
    """Four tabs, one per stage of the workflow."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OpenAntenna Studio - Phase 1 core, GUI preview")
        self.resize(1040, 780)

        self.design_tab = DesignTab()
        tabs = QTabWidget()
        tabs.addTab(MaterialTab(), "Material & composite")
        tabs.addTab(self.design_tab, "Design")
        tabs.addTab(SimulateTab(self.design_tab), "Simulate")
        tabs.addTab(ResultsTab(), "Results")
        self.setCentralWidget(tabs)

        status = self.statusBar()
        status.showMessage(
            "Phase 1 core: geometry/material results are analytic, the solver model is not calibrated yet."
        )


def run_gui(argv: list[str] | None = None) -> int:
    app = QApplication(list(argv) if argv else sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
