"""Main window: material/composite explorer, design synthesis, simulation, results.

The window is deliberately a thin client of the package API.  Anything that
could be done by the CLI is done by calling the same underlying functions, so the
GUI cannot drift away from the scriptable core.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..geometry.array import array_factor_plane, build_array_layout
from ..geometry.patch import synthesize_patch
from ..postproc.farfield import read_summary as read_farfield_summary
from ..postproc.farfield import summary_text as farfield_summary_text
from ..materials.library import get_material, list_material_names
from ..materials.mixing import (
    bruggeman,
    compare_models,
    estimate_effective_tan_delta,
    format_comparison_table,
    lichtenecker,
    maxwell_garnett,
    maxwell_wagner_warning,
    percolation_warning,
    quasi_static_warning,
    wiener_lower,
    wiener_upper,
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
from .worker import GenerateWorker, QueueWorker, SimulateWorker, _case_dirname


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

        try:
            self.figure, self.canvas = _plot_canvas()
            layout.addWidget(self.canvas)
        except Exception as exc:  # matplotlib is optional
            self.figure = None
            self.canvas = None
            layout.addWidget(QLabel(f"Plotting unavailable: {exc}"))

        self.reload()

    def _plot_sensitivity(self) -> None:
        """ε_eff against filler loading: the three models, the Wiener bounds, the point.

        The bounds matter as much as the curves: a candidate result outside them is not a
        mixing-rule prediction at all, it is an error.  The operating point of the form is
        marked so the plot answers "where am I" as well as "what if".
        """
        if self.figure is None:
            return
        matrix = self.matrix.value()
        filler = self.filler.value()
        fractions = [0.02 * step for step in range(31)]  # 0.00 .. 0.60
        models = {
            "Lichtenecker": lichtenecker,
            "Maxwell-Garnett": maxwell_garnett,
            "Bruggeman": bruggeman,
        }
        curves: dict[str, list[float]] = {name: [] for name in models}
        upper: list[float] = []
        lower: list[float] = []
        for vf in fractions:
            for name, function in models.items():
                try:
                    curves[name].append(float(complex(function(matrix, filler, vf)).real))
                except Exception:
                    curves[name].append(float("nan"))
            try:
                upper.append(float(complex(wiener_upper(matrix, filler, vf)).real))
                lower.append(float(complex(wiener_lower(matrix, filler, vf)).real))
            except Exception:
                upper.append(float("nan"))
                lower.append(float("nan"))

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.fill_between(fractions, lower, upper, alpha=0.15, label="Wiener bounds")
        for name, values in curves.items():
            axes.plot(fractions, values, linewidth=1.2, label=name)
        axes.axvline(
            self.volume_fraction.value(), color="0.4", linestyle="--", linewidth=0.8
        )
        axes.set_xlabel("filler volume fraction")
        axes.set_ylabel("effective eps_r")
        axes.set_title(f"Composite sensitivity (matrix {matrix:g}, filler {filler:g})")
        axes.grid(True, linewidth=0.4)
        axes.legend(fontsize=7)
        self.canvas.draw_idle()

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
        try:
            self._plot_sensitivity()
        except Exception as exc:  # a plotting problem must not withhold the numbers
            self.mix_output.append(f"plot failed: {type(exc).__name__}: {exc}")
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

    #: emitted whenever the design is (re)synthesised, so the project tree can follow
    design_changed = Signal()

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
        row = QHBoxLayout()
        row.addWidget(button)
        save = QPushButton("Save project ...")
        save.clicked.connect(self.save_project)
        load = QPushButton("Load project ...")
        load.clicked.connect(self.load_project)
        row.addWidget(save)
        row.addWidget(load)
        layout.addLayout(row)

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        layout.addWidget(self.summary)

        # The left panel can show the layout flat (readable for spacing) or as a 3-D
        # preview (readable for "what does this even look like").  Both are drawn from
        # the same model, so they cannot disagree.
        self.view_mode = QComboBox()
        self.view_mode.addItems(["2-D layout", "3-D preview"])
        layout.addWidget(self.view_mode)

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
                feed_line_width_m=design.feed_line_width_m or None,
            ),
            array=ArrayConfig(
                nx=self.nx.value(),
                ny=self.ny.value(),
                spacing_x_lambda0=self.spacing.value(),
                spacing_y_lambda0=self.spacing.value(),
            ),
            sweep=FrequencySweep.fractional(frequency, 0.15, points=201),
        )

    def save_project(self, target: str | None = None) -> None:
        """Write the neutral project model to JSON: the same document the CLI reads.

        ``target`` is optional so a round-trip can be tested without a file dialog.
        """
        if not target:
            target, _ = QFileDialog.getSaveFileName(
                self, "Save project", "project.json", "JSON (*.json)"
            )
            if not target:
                return
        try:
            payload = self.current_project().to_dict()
            Path(target).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            self.summary.append(f"saved project: {target}")
        except Exception as exc:
            self.summary.append(f"save failed: {type(exc).__name__}: {exc}")

    def load_project(self, source: str | None = None) -> None:
        """Read a project document back into the widgets, then re-synthesise."""
        if not source:
            source, _ = QFileDialog.getOpenFileName(
                self, "Load project", "project.json", "JSON (*.json)"
            )
            if not source:
                return
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
            project = Project.from_dict(data)
            layer = project.substrate.layers[0]
        except Exception as exc:
            self.summary.append(f"load failed: {type(exc).__name__}: {exc}")
            return
        dielectric_layers = [
            entry for entry in project.substrate.layers if entry.role == "dielectric"
        ]
        # A material that is not in the combo (e.g. a run-specific name such as
        # "ab-ptfe245") is left alone rather than silently replaced by the first entry.
        if self.material.findText(layer.material) >= 0:
            self.material.setCurrentText(layer.material)
        self.height.setValue(layer.thickness_m * 1e3)
        self.feed.setCurrentText(project.patch.feed_mode)
        self.nx.setValue(project.array.nx)
        self.ny.setValue(project.array.ny)
        self.spacing.setValue(project.array.spacing_x_lambda0)
        self.frequency.setValue(0.5 * (project.sweep.start_hz + project.sweep.stop_hz) / 1e9)
        self.synthesise()
        # after synthesise(), which rewrites the panel: the note must survive it
        self.summary.append(f"loaded project: {source}")
        if len(dielectric_layers) > 1:
            # Honest limitation, verified against the generator: it raises
            # "supports a single dielectric layer" rather than silently using one layer, so
            # the GUI must say that it can only edit one of them.
            self.summary.append(
                f"note: this file has {len(dielectric_layers)} dielectric layers; the GUI "
                "edits a single layer and the openEMS generator refuses a stacked "
                "dielectric (use an effective-medium eps_r first)."
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

        # Two panels: what the array *looks like* to scale, and what it radiates.
        # A single array-factor curve told the user nothing about the geometry it came
        # from, which is the one thing a layout preview is for.
        self.figure.clear()
        if self.view_mode.currentText() == "3-D preview":
            geometry_axes = self.figure.add_subplot(121, projection="3d")
            self._draw_geometry_3d(geometry_axes, design, layout, self.height.value())
        else:
            geometry_axes = self.figure.add_subplot(121)
            self._draw_geometry(geometry_axes, design, layout, self._corporate_plan())

        factor_axes = self.figure.add_subplot(122)
        samples = array_factor_plane(layout.positions_m, frequency, n_points=361, plane="e")
        factor_axes.plot([a for a, _ in samples], [v for _, v in samples])
        factor_axes.set_title(
            f"Array factor, E-plane, {self.nx.value()}x{self.ny.value()} @ "
            f"{self.frequency.value():g} GHz"
        )
        factor_axes.set_xlabel("theta [deg]")
        factor_axes.set_ylabel("normalised [dB]")
        factor_axes.set_ylim(-40, 2)
        factor_axes.grid(True)
        self.canvas.draw_idle()
        self.design_changed.emit()

    def _corporate_plan(self):
        """Feed-tree drawing plan for the current project, or None when it does not apply.

        Returns None for every case the deck builder also refuses (non-power-of-two counts, 2-D
        grids): the preview stays quiet rather than drawing something that cannot be built.
        """
        project = self.current_project()
        if project.patch.feed_mode != "corporate":
            return None
        from openantenna.geometry.feed import plan_corporate_feed_geometry
        from openantenna.geometry.patch import microstrip_width_for_impedance
        from openantenna.postproc.feed_network import synthesise_corporate_feed

        n_elements = int(project.array.nx * project.array.ny)
        if n_elements < 2 or (n_elements & (n_elements - 1)) != 0:
            return None
        if project.array.nx != 1 and project.array.ny != 1:
            return None
        lam0 = 299792458.0 / project.sweep.center_hz
        pitch = (
            project.array.spacing_x_lambda0 * lam0
            if project.array.nx > 1
            else project.array.spacing_y_lambda0 * lam0
        )
        feed = synthesise_corporate_feed(
            n_elements=n_elements,
            frequency_hz=project.sweep.center_hz,
            epsilon_eff=(project.substrate.epsilon_r + 1.0) / 2.0,
            z0_ohm=50.0,
        )

        def width_of(impedance_ohm: float) -> float:
            return microstrip_width_for_impedance(
                project.substrate.epsilon_r, project.substrate.total_thickness_m, impedance_ohm
            )

        return plan_corporate_feed_geometry(feed, pitch, width_of)

    @staticmethod
    def _draw_geometry_3d(axes, design, layout, substrate_mm: float) -> None:
        """A lightweight 3-D preview: ground plate, substrate slab, patch elements.

        Deliberately plain matplotlib so no new dependency enters the project: the
        roadmap's PyVista viewport stays an *option*, but a dependency that heavy is the
        owner's decision, not the GUI's.  The ground-plane footprint is approximate (the
        real one extends to the domain edge); the preview answers "what does the model
        look like", not "what does the mesh look like".
        """
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        def add_box(x0, y0, z0, dx, dy, dz, **kwargs):
            x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz
            faces = [
                [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
                [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
                [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
            ]
            axes.add_collection3d(Poly3DCollection(faces, **kwargs))

        half_x = layout.size_x_m * 1e3 / 2.0
        half_y = layout.size_y_m * 1e3 / 2.0
        height = max(substrate_mm, 0.05)

        # ground plane (thin plate under the substrate; footprint approximate)
        add_box(-half_x, -half_y, -height - 0.05, 2 * half_x, 2 * half_y, 0.05,
                facecolor="0.4", edgecolor="0.2", linewidth=0.4)
        # substrate slab
        add_box(-half_x, -half_y, -height, 2 * half_x, 2 * half_y, height,
                facecolor="tab:blue", alpha=0.25, edgecolor="tab:blue", linewidth=0.5)
        # patch elements on top of the slab
        width_mm = design.width_m * 1e3
        length_mm = design.length_m * 1e3
        for x_m, y_m in layout.positions_m:
            add_box(
                x_m * 1e3 - width_mm / 2.0,
                y_m * 1e3 - length_mm / 2.0,
                0.0,
                width_mm,
                length_mm,
                0.05,
                facecolor="tab:red",
                edgecolor="darkred",
                linewidth=0.5,
            )

        reach = max(half_x, half_y) * 1.15
        axes.set_xlim(-reach, reach)
        axes.set_ylim(-reach, reach)
        axes.set_zlim(-height - 0.4, 0.6)
        axes.set_xlabel("x [mm]")
        axes.set_ylabel("y [mm]")
        axes.set_zlabel("z [mm]")
        axes.set_title(
            f"3-D preview: {layout.element_count} patches on {height:.2f} mm substrate "
            "(footprint approximate)",
            fontsize=8,
        )

    @staticmethod
    def _draw_geometry(axes, design, layout, feed_plan=None) -> None:
        """Draw the array to scale in millimetres: one rectangle per patch element.

        The feed inset is *labelled*, not drawn as a point: the synthesised inset is a
        transmission-line estimate, and drawing an exact feed point would imply a
        precision the model does not have yet (the model still realises a probe).
        """
        from matplotlib.patches import Rectangle

        width_mm = design.width_m * 1e3
        length_mm = design.length_m * 1e3
        for x_m, y_m in layout.positions_m:
            axes.add_patch(
                Rectangle(
                    (x_m * 1e3 - width_mm / 2.0, y_m * 1e3 - length_mm / 2.0),
                    width_mm,
                    length_mm,
                    fill=False,
                    linewidth=0.9,
                )
            )
        axes.add_patch(
            Rectangle(
                (-layout.size_x_m * 1e3 / 2.0, -layout.size_y_m * 1e3 / 2.0),
                layout.size_x_m * 1e3,
                layout.size_y_m * 1e3,
                fill=False,
                linestyle=":",
                linewidth=0.7,
            )
        )
        reach = max(layout.size_x_m, layout.size_y_m) * 1e3
        axes.set_xlim(-reach, reach)
        axes.set_ylim(-reach, reach)
        axes.set_aspect("equal")
        axes.set_title(f"Layout: {layout.element_count} patches, {width_mm:.2f} x {length_mm:.2f} mm")
        axes.set_xlabel("x [mm]")
        axes.set_ylabel("y [mm]")
        axes.grid(True, linewidth=0.4)
        inset = getattr(design, "inset_depth_m", None)
        if inset:
            axes.text(
                0.02,
                0.98,
                f"feed: {design.feed_mode}, inset {inset * 1e3:.3f} mm (estimate)",
                transform=axes.transAxes,
                va="top",
                fontsize=7,
            )

        if feed_plan is not None:
            # Phase 2 #5b: the corporate tree as planned, in the plan's own frame (it grows in
            # -y from the input at the origin).  This shows the *shape and widths* the builder
            # will draw; it is not a claim about the board placement, which the deck resolves
            # from the ground-plane edge.
            rectangles = feed_plan.rectangles()
            for x0, y0, x1, y1 in ((r[0], r[1], r[2], r[3]) for r in rectangles):
                axes.add_patch(
                    Rectangle(
                        (x0 * 1e3, y0 * 1e3),
                        (x1 - x0) * 1e3,
                        (y1 - y0) * 1e3,
                        facecolor="none",
                        edgecolor="tab:orange",
                        linewidth=0.6,
                        linestyle="--",
                    )
                )
            axes.text(
                0.02,
                0.90,
                "feed tree: %d rectangles, %d levels (drawing plan)"
                % (len(rectangles), feed_plan.levels),
                transform=axes.transAxes,
                va="top",
                fontsize=7,
                color="tab:orange",
            )


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
        self._queue: list = []
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

        queue_group = QGroupBox("Batch queue (runs in order, one case at a time)")
        queue_layout = QVBoxLayout(queue_group)
        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["case", "frequency [GHz]", "run directory"])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.queue_table.setMaximumHeight(130)
        queue_layout.addWidget(self.queue_table)
        queue_row = QHBoxLayout()
        self.queue_add = QPushButton("Add current design")
        self.queue_add.clicked.connect(self.add_to_queue)
        self.queue_remove = QPushButton("Remove selected")
        self.queue_remove.clicked.connect(self.remove_selected)
        self.queue_clear = QPushButton("Clear")
        self.queue_clear.clicked.connect(self.clear_queue)
        self.queue_run = QPushButton("Run queue")
        self.queue_run.clicked.connect(self.run_queue)
        for widget in (self.queue_add, self.queue_remove, self.queue_clear, self.queue_run):
            queue_row.addWidget(widget)
        queue_layout.addLayout(queue_row)
        layout.addWidget(queue_group)

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

    def add_to_queue(self) -> None:
        """Queue the design as it is right now (a snapshot, not a live link)."""
        project = self.design_tab.current_project()
        index = len(self._queue)
        label = f"queue{index + 1:02d}"
        self._queue.append((label, project))
        centre_ghz = 0.5 * (project.sweep.start_hz + project.sweep.stop_hz) / 1e9
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        cells = (
            label,
            f"{centre_ghz:.4f}",
            str(Path(self.rundir.text()) / _case_dirname(index, label)),
        )
        for column, text in enumerate(cells):
            self.queue_table.setItem(row, column, QTableWidgetItem(text))

    def remove_selected(self) -> None:
        rows = sorted({i.row() for i in self.queue_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.queue_table.removeRow(row)
            del self._queue[row]

    def clear_queue(self) -> None:
        self.queue_table.setRowCount(0)
        self._queue.clear()

    def run_queue(self) -> None:
        if not self._queue:
            self.log.append("queue is empty")
            return
        if not self._begin_work():
            return
        self.log.append(f"running {len(self._queue)} queued case(s), one at a time ...")
        self.progress_bar.setValue(0)
        worker = QueueWorker(
            list(self._queue), Path(self.rundir.text()), **self._solver_kwargs()
        )
        worker.progress.connect(self.log.append)
        worker.progress_value.connect(self.progress_bar.setValue)
        worker.case_started.connect(
            lambda index, label: self.log.append(f"case {index + 1}: {label}")
        )
        worker.done.connect(self._queue_finished)
        worker.failed.connect(self._failed)
        self._track(worker)

    def _queue_finished(self, payload: list) -> None:
        for entry in payload:
            results = entry["results"]
            self.log.append(
                f"{entry['label']}: resonance {results['resonance_hz'] / 1e9:.4f} GHz, "
                f"|S11| {results['worst_match_db']:.2f} dB, "
                f"VSWR {results['vswr_at_resonance']:.3f}"
            )
        self.log.append(f"queue finished: {len(payload)} case(s)")

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

        # An A/B overlay: this project is full of on/off experiments (port_refine, air
        # margin, materials) and seeing them one at a time hides exactly the question
        # being asked - did the change move the resonance?
        compare_row = QHBoxLayout()
        self.compare_path = QLineEdit()
        self.compare_path.setPlaceholderText("optional: a second run directory to overlay (B)")
        compare_browse = QPushButton("Compare with ...")
        compare_browse.clicked.connect(self.pick_compare)
        compare_clear = QPushButton("Clear B")
        compare_clear.clicked.connect(self.clear_compare)
        compare_row.addWidget(self.compare_path)
        compare_row.addWidget(compare_browse)
        compare_row.addWidget(compare_clear)
        layout.addLayout(compare_row)

        # Coupling panel (Phase 2 #4, toolkit side).  Convention for the folder: one
        # subdirectory per driven port, named port<N> (port1, port2, ...), each holding the
        # run's port_<n>.csv files.  The driven port comes from the NAME, so it is explicit
        # rather than inferred - a wrong column is worse than no column.
        coupling_group = QGroupBox("Array coupling (per-port runs)")
        coupling_layout = QVBoxLayout(coupling_group)
        coupling_row = QHBoxLayout()
        self.coupling_path = QLineEdit()
        self.coupling_path.setPlaceholderText(
            "folder containing port1/, port2/, ... (one run per driven port)"
        )
        coupling_pick = QPushButton("Load coupling ...")
        coupling_pick.clicked.connect(self.pick_coupling)
        coupling_row.addWidget(self.coupling_path)
        coupling_row.addWidget(coupling_pick)
        coupling_layout.addLayout(coupling_row)
        self.coupling_table = QTableWidget(0, 0)
        self.coupling_table.setMaximumHeight(150)
        coupling_layout.addWidget(self.coupling_table)
        self.coupling_note = QLabel("")
        self.coupling_note.setWordWrap(True)
        coupling_layout.addWidget(self.coupling_note)
        layout.addWidget(coupling_group)

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

    def pick_compare(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose the second run directory")
        if chosen:
            self.compare_path.setText(chosen)

    def clear_compare(self) -> None:
        self.compare_path.clear()

    def pick_coupling(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose the per-port run folder")
        if chosen:
            self.coupling_path.setText(chosen)
            self.load_coupling()

    def load_coupling(self) -> None:
        """Assemble the coupling matrix from ``port<N>`` subfolders and show it as dB."""
        from ..postproc.port_matrix import assemble

        folder = Path(self.coupling_path.text().strip())
        try:
            runs = []
            for child in sorted(folder.iterdir()):
                name = child.name.lower()
                if child.is_dir() and name.startswith("port") and name[4:].isdigit():
                    runs.append((child, int(name[4:])))
            if not runs:
                raise ValueError(
                    "no port<N> subfolders found; each driven port needs its own run folder"
                )
            n_ports = max(port for _, port in runs)
            matrix = assemble(runs, n_ports=n_ports, require_convergence=True)
        except (ValueError, FileNotFoundError, OSError) as exc:
            self.coupling_note.setText(f"coupling not loaded: {type(exc).__name__}: {exc}")
            self.coupling_table.setRowCount(0)
            self.coupling_table.setColumnCount(0)
            return

        used_hz, values = matrix.at(self.last_frequency_hz())
        self.coupling_table.setRowCount(matrix.n_ports)
        self.coupling_table.setColumnCount(matrix.n_ports)
        self.coupling_table.setHorizontalHeaderLabels(
            [f"drv {n}" for n in range(1, matrix.n_ports + 1)]
        )
        self.coupling_table.setVerticalHeaderLabels(
            [f"to {n}" for n in range(1, matrix.n_ports + 1)]
        )
        for row in range(matrix.n_ports):
            for column in range(matrix.n_ports):
                magnitude = abs(values[row][column])
                db = 20.0 * math.log10(magnitude) if magnitude > 0 else float("-inf")
                item = QTableWidgetItem("self" if row == column else f"{db:.1f}")
                self.coupling_table.setItem(row, column, item)

        summary = matrix.coupling_summary(self.last_frequency_hz())
        self.coupling_note.setText(
            f"{matrix.n_ports} ports at {used_hz / 1e9:.4f} GHz (nearest sample). "
            f"Worst coupling {summary['worst_db']:.1f} dB, mean "
            f"{20.0 * math.log10(max(summary['mean_magnitude'], 1e-12)):.1f} dB. "
            "Values are dB |Sij|; a coupling number is only meaningful for runs that differ "
            "in one variable and converged."
        )

    def last_frequency_hz(self) -> float:
        """The design frequency, taken from the design tab so the panels agree."""
        try:
            design_tab = self.window().centralWidget().widget(1)
            return float(design_tab.frequency.value()) * 1e9
        except Exception:  # pragma: no cover - standalone use
            return 2.45e9

    @staticmethod
    def _summarise(trace: S11Trace) -> dict:
        """The numbers an A/B comparison needs, as numbers rather than as text."""
        index = trace.worst_match_index()
        return {
            "resonance_hz": float(trace.frequencies_hz[index]),
            "worst_db": float(trace.db()[index]),
            "vswr": float(trace.vswr()[index]),
            "fractional": trace.fractional_bandwidth(-10.0),
        }

    def _comparison_lines(self, csv_a: Path, csv_b: Path) -> list[str]:
        """Metric-vs-metric between run A and run B, with the shift called out."""
        summary_a = self._summarise(S11Trace.from_csv(csv_a))
        summary_b = self._summarise(S11Trace.from_csv(csv_b))
        shift_hz = summary_b["resonance_hz"] - summary_a["resonance_hz"]
        shift_pct = 100.0 * shift_hz / summary_a["resonance_hz"]
        lines = [
            "",
            "A/B compare (A = the run above, B = the overlay)",
            f"  resonance  A {summary_a['resonance_hz'] / 1e9:.4f} GHz   "
            f"B {summary_b['resonance_hz'] / 1e9:.4f} GHz   "
            f"shift {shift_hz / 1e6:+.1f} MHz ({shift_pct:+.3f} %)",
            f"  |S11|      A {summary_a['worst_db']:.2f} dB   B {summary_b['worst_db']:.2f} dB",
            f"  VSWR       A {summary_a['vswr']:.3f}   B {summary_b['vswr']:.3f}",
        ]
        if summary_a["fractional"] and summary_b["fractional"]:
            lines.append(
                f"  -10 dB BW  A {summary_a['fractional'] * 100:.2f} %   "
                f"B {summary_b['fractional'] * 100:.2f} %"
            )
        lines.append(
            "  Both curves are model output; a shift only means something if the two runs "
            "differ in one variable."
        )
        return lines

    def _notify(self, message: str) -> None:
        """Report a load failure **without blocking**.

        A modal ``QMessageBox.warning`` froze the whole test suite (and would freeze CI)
        the moment a test loaded a bad run directory: the dialog waits for input that never
        comes.  The message is written into the metrics panel as well, so it is visible
        even headless, and the popup is shown non-modally.
        """
        self.metrics.setPlainText(message)
        box = QMessageBox(self)
        box.setWindowTitle("Cannot load")
        box.setText(message)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setModal(False)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.show()

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
            lines.extend(
                self._run_details(candidate if candidate.is_dir() else candidate.parent)
            )
            compare = self.compare_path.text().strip()
            if compare:
                compare_trace_path = Path(compare)
                csv_b = (
                    compare_trace_path / "s11.csv"
                    if compare_trace_path.is_dir()
                    else compare_trace_path
                )
                lines.extend(self._comparison_lines(csv_path, csv_b))
            lines.append("")
            lines.append(
                "Model output, not a measurement. See run_manifest.json for the mesh and "
                "loss model used."
            )
        except Exception as exc:
            # All of the above is inside the try: impedance_ohm() deliberately raises
            # for a phase-less trace (review item G-5), and an exception escaping into
            # the Qt event loop would go uncaught.
            self._notify(f"Cannot load {csv_path.name}: {type(exc).__name__}: {exc}")
            return
        self.metrics.setPlainText("\n".join(lines))

        if self.figure is None:
            return  # matplotlib missing; the metrics above are still shown
        self.figure.clear()
        axes = self.figure.add_subplot(121)
        axes.plot([f / 1e9 for f in trace.frequencies_hz], trace.db())
        axes.axhline(-10.0, linestyle="--", linewidth=0.8)
        axes.set_xlabel("frequency [GHz]")
        axes.set_ylabel("|S11| [dB]")
        axes.set_title("Input matching")
        axes.grid(True)

        # A run with NF2FF enabled carries a far-field cut too; showing both in one place
        # is the point of a "results" tab (previously the far-field was invisible unless
        # the user opened the CSV by hand).
        compare = self.compare_path.text().strip()
        if compare:
            try:
                other = S11Trace.from_csv(
                    Path(compare) / "s11.csv" if Path(compare).is_dir() else Path(compare)
                )
                axes.plot(
                    [f / 1e9 for f in other.frequencies_hz],
                    other.db(),
                    linestyle="--",
                    linewidth=1.0,
                    label="B",
                )
                axes.legend(fontsize=7)
            except Exception as exc:  # the A panel must survive a bad B path
                self.metrics.append(f"\nB could not be plotted: {type(exc).__name__}: {exc}")

        pattern = self._pattern_cut(candidate if candidate.is_dir() else candidate.parent)
        if pattern is not None:
            theta_deg, gain_db, phi_deg = pattern
            pattern_axes = self.figure.add_subplot(122, projection="polar")
            pattern_axes.plot([t * 3.141592653589793 / 180.0 for t in theta_deg], gain_db)
            pattern_axes.set_title(f"Far field, phi = {phi_deg:g} deg", fontsize=9)
            pattern_axes.set_theta_zero_location("N")
            pattern_axes.set_rlabel_position(135)
            pattern_axes.grid(True, linewidth=0.4)
        self.canvas.draw_idle()

    @staticmethod
    def _run_details(run_dir: Path) -> list[str]:
        """Read the run's own provenance and far-field summary, if the files exist.

        Everything here comes from files the run wrote itself, so the panel says exactly
        what a reviewed number would need: mesh, substrate, the A/B knob settings, the stop
        criteria, and whether the run converged.
        """
        lines: list[str] = []
        manifest = run_dir / "run_manifest.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            substrate = data.get("substrate") or {}
            mesh = data.get("mesh") or {}
            if substrate or mesh:
                lines.append("")
                lines.append(
                    f"substrate         : {substrate.get('material', '?')} "
                    f"eps_r {substrate.get('epsilon_r', '?')}, "
                    f"h {float(substrate.get('thickness_m') or 0.0) * 1e3:.2f} mm"
                )
                lines.append(
                    f"mesh              : {mesh.get('cells_per_wavelength', '?')} "
                    f"cells/wavelength, boundary {data.get('boundary', '?')}, "
                    f"pml {data.get('pml_cells', '?')}"
                )
            if any(key in data for key in ("port_refine", "metal_edge_snapping", "nf2ff")):
                knobs = {
                    key: ("not recorded" if data.get(key) is None else data.get(key))
                    for key in ("port_refine", "metal_edge_snapping", "nf2ff")
                }
                lines.append(
                    f"A/B knobs         : port_refine {knobs['port_refine']}, "
                    f"edge_snapping {knobs['metal_edge_snapping']}, "
                    f"nf2ff {knobs['nf2ff']}"
                )
            if "end_criteria" in data or "max_timesteps" in data:
                lines.append(
                    f"stop criteria     : end_criteria {data.get('end_criteria')}, "
                    f"cap {data.get('max_timesteps')} steps"
                )
        summary = run_dir / "run_summary.json"
        if summary.exists():
            try:
                data = json.loads(summary.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            if "converged" in data or "timesteps" in data:
                lines.append(
                    f"convergence       : converged={data.get('converged', 'not recorded')}, "
                    f"timesteps={data.get('timesteps', 'not recorded')}"
                )
        far_field = run_dir / "nf2ff_summary.csv"
        if far_field.exists():
            try:
                points = read_farfield_summary(far_field)
                lines.append("")
                lines.append(farfield_summary_text(points))
                # An efficiency above 1 means the far-field data is not trustworthy (the
                # tutorial run reports eta_rad = 55 at its own resonance).  Showing the
                # number without saying so would be worse than not showing it at all.
                out_of_range = []
                for point in points:
                    fields = point.to_dict() if hasattr(point, "to_dict") else {}
                    # the dataclass calls it radiation_efficiency; the CSV column is eta_rad
                    eta = getattr(point, "radiation_efficiency", None)
                    if eta is None:
                        eta = fields.get("radiation_efficiency", fields.get("eta_rad"))
                    if eta is not None and not (0.0 < float(eta) <= 1.0):
                        out_of_range.append(float(eta))
                if out_of_range:
                    lines.append("")
                    lines.append(
                        "WARNING: radiation efficiency outside (0, 1] in this run "
                        f"(max {max(out_of_range):.3g}) - physically impossible, so treat "
                        "the far-field numbers as unconverged / not usable."
                    )
            except (OSError, ValueError) as exc:
                lines.append(f"far field         : tidak bisa dibaca ({exc})")
        progress = run_dir / "progress.json"
        if progress.exists():
            try:
                data = json.loads(progress.read_text(encoding="utf-8"))
                lines.append("")
                lines.append(f"progress (last)   : {data.get('bar', '?')}")
            except (OSError, ValueError):
                pass
        return lines

    @staticmethod
    def _pattern_cut(run_dir: Path):
        """Return the most-sampled phi cut of nf2ff_pattern.csv as (theta_deg, dB, phi).

        The file is a full theta/phi grid; plotting all of it as a single curve would be
        meaningless, so the cut with the most samples is used (the principal plane).
        """
        import csv
        import math
        from collections import defaultdict

        path = run_dir / "nf2ff_pattern.csv"
        if not path.exists():
            return None
        cuts: dict[float, list[tuple[float, float]]] = defaultdict(list)
        try:
            with path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    try:
                        theta = float(row["theta_deg"])
                        phi = float(row["phi_deg"])
                        magnitude = abs(float(row["e_norm"]))
                    except (KeyError, TypeError, ValueError):
                        continue
                    cuts[phi].append((theta, magnitude))
        except OSError:
            return None
        if not cuts:
            return None
        phi_deg, samples = max(cuts.items(), key=lambda item: len(item[1]))
        samples.sort()
        peak = max((magnitude for _, magnitude in samples), default=0.0)
        if peak <= 0.0:
            return None
        return (
            [theta for theta, _ in samples],
            [20.0 * math.log10(max(magnitude / peak, 1e-6)) for _, magnitude in samples],
            phi_deg,
        )


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
        tabs.addTab(SweepTab(), "Sweep")
        tabs.addTab(ImportTab(), "Import")
        self.setCentralWidget(tabs)

        # The project tree: a shell-style view of the *model* (not of the widgets), so it
        # cannot disagree with what will be simulated.  It refreshes from the design tab's
        # signal instead of being rebuilt by hand at every call site.
        self.project_tree = QTreeWidget()
        self.project_tree.setColumnCount(2)
        self.project_tree.setHeaderLabels(["property", "value"])
        self.project_tree.setMinimumWidth(270)
        dock = QDockWidget("Project", self)
        dock.setObjectName("projectDock")
        dock.setWidget(self.project_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.design_tab.design_changed.connect(self._refresh_project_tree)
        self._refresh_project_tree()

        status = self.statusBar()
        status.showMessage(
            "Phase 1 core: geometry/material results are analytic, the solver model is not calibrated yet."
        )

    def _refresh_project_tree(self) -> None:
        """Rebuild the tree from the design tab's current project.

        Values come from the neutral model, so the tree describes exactly what a run would
        use, including the project's own validity warnings.
        """
        tree = self.project_tree
        tree.clear()
        project = self.design_tab.current_project()
        root = QTreeWidgetItem([project.name, ""])
        tree.addTopLevelItem(root)

        substrate = QTreeWidgetItem(
            ["Substrate", f"{len(project.substrate.layers)} layer(s)"]
        )
        for index, layer in enumerate(project.substrate.layers, start=1):
            substrate.addChild(
                QTreeWidgetItem(
                    [
                        f"layer {index}: {layer.material}",
                        f"{layer.thickness_m * 1e3:.3f} mm, {layer.role}",
                    ]
                )
            )
        total_mm = sum(layer.thickness_m for layer in project.substrate.layers) * 1e3
        substrate.addChild(QTreeWidgetItem(["total thickness", f"{total_mm:.3f} mm"]))
        root.addChild(substrate)

        patch = QTreeWidgetItem(["Patch", ""])
        patch.addChild(QTreeWidgetItem(["width W", f"{project.patch.width_m * 1e3:.3f} mm"]))
        patch.addChild(QTreeWidgetItem(["length L", f"{project.patch.length_m * 1e3:.3f} mm"]))
        patch.addChild(QTreeWidgetItem(["feed", str(project.patch.feed_mode)]))
        if project.patch.feed_inset_m:
            patch.addChild(
                QTreeWidgetItem(["inset depth", f"{project.patch.feed_inset_m * 1e3:.3f} mm"])
            )
        if project.patch.feed_line_width_m:
            patch.addChild(
                QTreeWidgetItem(
                    ["feed line width", f"{project.patch.feed_line_width_m * 1e3:.3f} mm"]
                )
            )
        root.addChild(patch)

        array = QTreeWidgetItem(
            ["Array", f"{project.array.nx} x {project.array.ny}"]
        )
        array.addChild(
            QTreeWidgetItem(["elements", str(project.array.nx * project.array.ny)])
        )
        array.addChild(
            QTreeWidgetItem(["spacing x", f"{project.array.spacing_x_lambda0:.3f} lambda0"])
        )
        array.addChild(
            QTreeWidgetItem(["spacing y", f"{project.array.spacing_y_lambda0:.3f} lambda0"])
        )
        root.addChild(array)

        sweep = QTreeWidgetItem(["Sweep", ""])
        sweep.addChild(QTreeWidgetItem(["start", f"{project.sweep.start_hz / 1e9:.4f} GHz"]))
        sweep.addChild(QTreeWidgetItem(["stop", f"{project.sweep.stop_hz / 1e9:.4f} GHz"]))
        sweep.addChild(QTreeWidgetItem(["points", str(project.sweep.points)]))
        root.addChild(sweep)

        warnings = project.check()
        if warnings:
            warn_root = QTreeWidgetItem(["Warnings", str(len(warnings))])
            for message in warnings:
                warn_root.addChild(QTreeWidgetItem([message[:90], ""]))
            root.addChild(warn_root)
        tree.expandAll()


from .theme import apply_theme


def run_gui(argv: list[str] | None = None) -> int:
    """Start the GUI.

    ``--selftest`` builds the window, exercises the panels that need no solver, and exits
    without entering the event loop.  That is how a *frozen* build is verified: a windowed
    executable has no console, so its **exit code** is the evidence.
    """
    arguments = list(argv) if argv else list(sys.argv)
    if "--selftest" in arguments:
        return _gui_selftest(arguments)

    app = QApplication(arguments)
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


def _gui_selftest(arguments: list[str]) -> int:
    """Exercise the GUI without a display: 0 means the packaged app is functional."""
    try:
        app = QApplication.instance() or QApplication(arguments[:1])
        window = MainWindow()
        window.centralWidget().widget(0).evaluate()
        design_tab = window.centralWidget().widget(1)
        design_tab.view_mode.setCurrentText("3-D preview")
        design_tab.synthesise()
        simulate_tab = window.centralWidget().widget(2)
        simulate_tab.add_to_queue()
        window.close()
        del app
        return 0
    except Exception:  # pragma: no cover - only a broken build reaches this
        import traceback

        traceback.print_exc()
        return 1


class SweepTab(QWidget):
    """CST-style sweeping: a parameter table, run-all, and a results browser.

    The runner is the analytic model on purpose: it answers in milliseconds, so the panel is usable
    while a real solver sweep would still be queueing.  The numbers are *targeting* numbers and the
    status line says so; a solver-backed runner is the same interface with a slower callable.
    """

    def __init__(self) -> None:
        super().__init__()
        self.table = None
        self.epsilon_r = 3.4
        self.height_mm = 1.6

        layout = QVBoxLayout(self)
        form = QGroupBox("Parameters")
        form_layout = QVBoxLayout(form)
        self.parameter_table = QTableWidget(1, 2)
        self.parameter_table.setHorizontalHeaderLabels(["parameter", "values (comma separated)"])
        self.parameter_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.parameter_table.setItem(0, 0, QTableWidgetItem("length_mm"))
        self.parameter_table.setItem(0, 1, QTableWidgetItem("30.0, 31.0, 32.0, 33.0"))
        form_layout.addWidget(self.parameter_table)

        buttons = QHBoxLayout()
        self.add_row = QPushButton("Add parameter")
        self.add_row.clicked.connect(self._add_row)
        self.remove_row = QPushButton("Remove last")
        self.remove_row.clicked.connect(self._remove_row)
        self.mode = QComboBox()
        self.mode.addItems(["one at a time", "factorial"])
        self.generate = QPushButton("Generate table")
        self.generate.clicked.connect(self.generate_table)
        buttons.addWidget(self.add_row)
        buttons.addWidget(self.remove_row)
        buttons.addWidget(self.mode)
        buttons.addWidget(self.generate)
        form_layout.addLayout(buttons)
        layout.addWidget(form)

        actions = QHBoxLayout()
        self.run_all = QPushButton("Run all (analytic)")
        self.run_all.clicked.connect(self.run_all_runs)
        self.export = QPushButton("Export CSV")
        self.export.clicked.connect(self.export_csv)
        actions.addWidget(self.run_all)
        actions.addWidget(self.export)
        layout.addLayout(actions)

        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(["#", "parameters", "status", "resonance [GHz]"])
        self.results.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.results)

        self.figure, self.axes = _plot_canvas()
        layout.addWidget(self.figure.canvas)
        self.status = QLabel("Define parameters, generate the table, then run it.")
        layout.addWidget(self.status)

    def _add_row(self) -> None:
        row = self.parameter_table.rowCount()
        self.parameter_table.insertRow(row)
        self.parameter_table.setItem(row, 0, QTableWidgetItem("width_mm"))
        self.parameter_table.setItem(row, 1, QTableWidgetItem("40.0, 42.0"))

    def _remove_row(self) -> None:
        if self.parameter_table.rowCount() > 1:
            self.parameter_table.removeRow(self.parameter_table.rowCount() - 1)

    def _values(self) -> dict:
        values = {}
        for row in range(self.parameter_table.rowCount()):
            name_item = self.parameter_table.item(row, 0)
            value_item = self.parameter_table.item(row, 1)
            if name_item is None or value_item is None:
                continue
            name = name_item.text().strip()
            raw = value_item.text().replace(";", ",")
            series = [piece.strip() for piece in raw.split(",") if piece.strip()]
            if name and series:
                values[name] = [float(piece) for piece in series]
        return values

    def generate_table(self) -> None:
        from openantenna.sweep.table import SweepTable

        try:
            values = self._values()
            if not values:
                raise ValueError("no parameters with values")
            if self.mode.currentText() == "factorial":
                table = SweepTable.factorial(values)
            else:
                baseline = {name: series[0] for name, series in values.items()}
                table = SweepTable.one_at_a_time(baseline, values)
        except ValueError as exc:
            self.status.setText("table not generated: %s" % exc)
            return
        self.table = table
        self._refresh()
        self.status.setText(
            "%d runs (%s). Baseline is each parameter's first value." % (len(table), table.mode)
        )

    def _predict(self, params: dict) -> float:
        from openantenna.geometry.patch import (
            delta_length,
            effective_permittivity,
            patch_length,
            patch_width,
            resonant_frequency_cavity,
        )

        height_m = self.height_mm * 1e-3
        width_m = params.get("width_mm", patch_width(2.45e9, self.epsilon_r) * 1e3) * 1e-3
        epsilon_eff = effective_permittivity(self.epsilon_r, height_m, width_m)
        default_length = patch_length(
            2.45e9, epsilon_eff, delta_length(height_m, epsilon_eff, width_m)
        )
        length_m = params.get("length_mm", default_length * 1e3) * 1e-3
        return resonant_frequency_cavity(self.epsilon_r, height_m, width_m, length_m)

    def run_all_runs(self) -> None:
        from openantenna.sweep.table import run_table

        if self.table is None:
            self.status.setText("generate the table first")
            return
        run_table(self.table, lambda params, _record: {"resonance_hz": self._predict(params)})
        self._refresh()
        counts = self.table.status_counts()
        self.status.setText(
            "done %d, failed %d - analytic targeting numbers, not solver results"
            % (counts["done"], counts["failed"])
        )

    def export_csv(self) -> None:
        if self.table is None:
            self.status.setText("nothing to export yet")
            return
        target, _filter = QFileDialog.getSaveFileName(
            self, "Export sweep", "sweep.csv", "CSV (*.csv)"
        )
        if not target:
            return
        self.table.to_csv(target)
        self.status.setText("written to %s" % target)

    def _refresh(self) -> None:
        self.results.setRowCount(len(self.table))
        for row, record in enumerate(self.table):
            cells = [
                str(record.index),
                ", ".join("%s=%g" % item for item in record.params.items()),
                record.status,
                "%.6f" % (record.result["resonance_hz"] / 1e9)
                if "resonance_hz" in record.result
                else "",
            ]
            for column, text in enumerate(cells):
                self.results.setItem(row, column, QTableWidgetItem(text))

        self.axes.clear()
        drawn = False
        for name, points in self.table.summary("resonance_hz").items():
            if len(points) > 1:
                self.axes.plot(
                    [key for key, _values in points],
                    [values[0] / 1e9 for _key, values in points],
                    "o-",
                    label=name,
                )
                drawn = True
        self.axes.axhline(2.45, color="tab:orange", linestyle="--", linewidth=0.8, label="2.45 GHz")
        self.axes.set_xlabel("parameter value")
        self.axes.set_ylabel("predicted resonance [GHz]")
        self.axes.set_title("Sweep summary (analytic)")
        self.axes.grid(True, linewidth=0.4)
        if drawn:
            self.axes.legend(fontsize=7)
        self.figure.canvas.draw_idle()


class ImportTab(QWidget):
    """Read a CAD mesh (STL) and show what the solver grid would make of it.

    No new dependency: the STL reader and the staircase rasteriser are in openantenna.geometry.cad,
    and the picture uses the same matplotlib canvas the other tabs use.  The panel says out loud
    that a staircase approximation is coarser for slanted faces, because that is the number that
    travels with any result taken from this geometry.
    """

    def __init__(self) -> None:
        super().__init__()
        self.mesh = None

        layout = QVBoxLayout(self)
        controls = QGroupBox("CAD import")
        controls_layout = QHBoxLayout(controls)
        self.choose = QPushButton("Choose STL\u2026")
        self.choose.clicked.connect(self.choose_file)
        self.units = QComboBox()
        self.units.addItems(["mm", "m"])
        self.cell_mm = QDoubleSpinBox()
        self.cell_mm.setRange(0.1, 100.0)
        self.cell_mm.setValue(2.0)
        self.cell_mm.setSuffix(" mm")
        controls_layout.addWidget(self.choose)
        controls_layout.addWidget(QLabel("units"))
        controls_layout.addWidget(self.units)
        controls_layout.addWidget(QLabel("cell"))
        controls_layout.addWidget(self.cell_mm)
        layout.addWidget(controls)

        self.summary = QLabel("No mesh loaded. STL carries no units, so pick the one your CAD used.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.figure, self.axes = _plot_canvas()
        layout.addWidget(self.figure.canvas)

    def choose_file(self) -> None:
        from openantenna.geometry.cad import read_stl

        target, _filter = QFileDialog.getOpenFileName(self, "Open STL", "", "STL (*.stl);;All files (*)")
        if not target:
            return
        try:
            mesh = read_stl(target)
            factor = 1e-3 if self.units.currentText() == "mm" else 1.0
            self.mesh = mesh.scaled(factor)
        except (ValueError, FileNotFoundError, OSError) as exc:
            self.mesh = None
            self.summary.setText("could not read that file: %s" % exc)
            self.axes.clear()
            self.figure.canvas.draw_idle()
            return
        self.show_mesh(target)

    def show_mesh(self, source: str) -> None:
        from openantenna.geometry.cad import occupancy_fraction, staircase_occupancy

        mesh = self.mesh
        low, high = mesh.bounds()
        size_mm = [(high[index] - low[index]) * 1e3 for index in range(3)]
        cell_m = self.cell_mm.value() * 1e-3
        try:
            shape, rows = staircase_occupancy(mesh, cell_m)
        except ValueError as exc:
            self.summary.setText("%s: %s" % (source, exc))
            return
        self.summary.setText(
            "%s\ntriangles %d  |  size %.2f x %.2f x %.2f mm  |  grid %d x %d cells of %.2f mm  "
            "|  occupied %.1f %%\n"
            "NOTE: staircase discretisation - quote the cell size with any result; a slanted face "
            "is coarser than an axis-aligned one."
            % (
                source,
                mesh.triangle_count,
                size_mm[0],
                size_mm[1],
                size_mm[2],
                shape[0],
                shape[1],
                self.cell_mm.value(),
                occupancy_fraction(rows) * 100.0,
            )
        )
        self.axes.clear()
        self.axes.imshow(
            [[1.0 if cell else 0.0 for cell in row] for row in rows],
            origin="lower",
            cmap="Blues",
            interpolation="nearest",
        )
        self.axes.set_title("Staircase occupancy (xy)")
        self.axes.set_xlabel("x cells")
        self.axes.set_ylabel("y cells")
        self.figure.canvas.draw_idle()

