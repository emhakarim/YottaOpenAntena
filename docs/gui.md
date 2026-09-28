# Desktop GUI (Phase 3)

A Qt (PySide6) desktop application. Not a web dashboard: the solver runs locally as a
subprocess, the plots are native, and there is nothing to deploy. Every panel calls the
same functions the CLI calls, so the GUI cannot drift away from the scriptable core.

```powershell
.venv\Scripts\python.exe -m pip install PySide6-Essentials
python -m openantenna.gui
```

## The eight tabs

A **project tree** dock sits on the left of the window: substrate layers, patch dimensions
and feed, array configuration, sweep range, and the project's own validity warnings. It is
rebuilt from the neutral model whenever the design is re-synthesised, so it always
describes what a run would use rather than what the widgets happen to say.

| Tab | What it does |
|---|---|
| **Material & composite** | The built-in material library (reference values, not measurements), plus a two-phase composite explorer: mixing models, their validity warnings, and a sensitivity plot of ε_eff against filler loading with the Wiener bounds and the current operating point marked |
| **Design** | Patch synthesis from the transmission-line model; array parameters; a **2-D layout drawn to scale** or a **3-D preview** of the same model (with camera presets and a rotate/zoom hint); the array-factor cut; and **save/load of the neutral project JSON** (the same document the CLI reads) |
| **Simulate** | Mesh, substrate cells, loss model, and the three A/B knobs (`port_refine`, `edge_snapping`, `nf2ff`); generate, run in a worker thread; a **progress bar driven by the solver's own timestep lines**; and a **sequential batch queue** |
| **Results** | Load a run directory: S11 with its metrics, the run's own provenance (mesh, substrate, knobs, stop criteria, convergence), the far-field cut and summary, an **A/B overlay** of a second run with the resonance shift, the **coupling matrix** assembled from `port_<n>.csv` folders, and a warning when a number is physically impossible |
| **Sweep** | A parameter table (factorial or one-at-a-time), run-all against the analytic predictor, a results table with per-row status, a resonance-versus-parameter plot from the table's own summary, and CSV export; the status line states the numbers are targeting values, not solver results |
| **Import** | Read a CAD file - **STL** (ASCII or binary), **OBJ**, or a **DXF outline** - choose its units and cell size, and see what the solver grid would use: the **staircase occupancy** for a mesh, the **stroked edges** for an outline, drawn on the same canvas style as the other tabs |
| **Optimise** | Target a resonance frequency by searching the patch length with the stdlib differential-evolution optimiser, **naming the analytic predictor** it used and stating that the number is a targeting result, not a measurement |
| **Sketch** | Draw shapes and feed traces on a millimetre grid - trace, polygon, rectangle, circle, line, and **blocks** (a brick footprint plus a thickness) - with snapping, a **parameter table** (name = expression, CST-style: a block's thickness can be `h_sub`, and `h_sub` can be `L/8`), a shape list with undo/clear, a **3-D view** of the same sketch, **DXF export/import**, and a grid view of which solver cells the edges cross. Stated plainly: the sketch leaves as DXF; wiring a sketch into the solver deck is a separate, bigger change and is not claimed yet |

## Things that are deliberate, not missing

* **The progress bar is a percentage of the step cap, and it says so.** The cap (400 000
  steps by default) is a ceiling, not a target: the tutorial run ended at 6.0 % of its cap
  because it met the energy criterion. A bare "6 %" reads like "barely started", which
  happened once and cost an evening of confusion.
* **No modal dialogs on automated paths.** A modal message box froze the whole test suite
  (and would freeze CI) when a test loaded a bad run directory. Failures are written into
  the panel and shown non-modally.
* **A/B comparisons state that a shift is only meaningful if one variable changed.**
* **Multiple dielectric layers are refused, not silently collapsed.** The GUI warns on
  load, and the Phase 1 generator raises `supports a single dielectric layer; got 2` — the
  honest behaviour until the stackup is collapsed to an effective medium.
* **The 3-D preview is plain matplotlib.** The roadmap lists a PyVista viewport; that is a
  heavy dependency and therefore the owner's decision, not the GUI's. The preview shows
  the ground plate, substrate slab and patch elements with an explicitly approximate
  footprint, plus four camera presets (iso, front, top, side) and a rotate/zoom hint, so the
  same model can be inspected from more than one angle without a new dependency.
* **The Import tab never trusts the file extension.** The format is decided by inspecting
  the file: a text head holding a DXF `ENTITIES`/`SECTION` pair goes to the DXF reader;
  everything else goes to the mesh reader, which itself measures whether an STL is binary
  or ASCII rather than believing the name.
* **Import shows a staircase, not the mesh.** STL and OBJ carry no units, so the tab asks
  which one your CAD used, and the occupancy it draws is a staircase approximation of the
  true surface - a slanted face is coarser than an axis-aligned one. The number and that
  caveat are printed together.
* **A DXF is an outline, not a surface.** The tab strokes the edges onto the solver grid
  and says outright that these are the cells the edges cross, not filled metal, because a
  DXF has no surface to fill.
* **The Sketch tab says what it does not do.** It draws, previews on the solver grid and
  exports DXF - but the solver deck still comes from the parametric model, and the panel
  states that the bridge from a sketch to a non-parametric deck is not built yet -
  the package half of that bridge now exists (`Project.sketch_polygons` to additive PEC
  sheets, `docs/sketch-to-deck.md`); the GUI wiring is the remaining half.
* **Parameters are definitions, not copies.** A block keeps the *expression* for its
  thickness, resolved each time it is shown or exported, so changing `h_sub` moves every
  block that uses it - the point of CST's "add parameter", and the reason a sketch can be
  edited instead of redrawn.  The expression language is deliberately tiny (numbers, names,
  `+ - * / **`, parentheses): a sketch must never be able to execute anything.
* **The Optimise tab reports targeting, not measurement.** It names the predictor and says
  the number is where the chosen model wants the design to sit - the same wording the
  `optimise` CLI uses, so the two cannot drift apart.
* **An impossible radiation efficiency is flagged.** The tutorial run reports
  `eta_rad = 55` at its own resonance; the panel prints the number *and* says it is
  physically impossible, so nobody quotes it by accident.

## Testing

The GUI is covered by offscreen smoke tests (`QT_QPA_PLATFORM=offscreen`), which run in the
same stdlib suite as the core:

```powershell
python -m unittest tests.test_gui_smoke -v
```

Those tests build the real window, exercise each panel with synthetic run directories, and
check the figures that come out (axes, patches, curves). They drive the Import tab through
the same `load`/`show_loaded` path a click uses, for both a mesh and a DXF outline, and walk
all four 3-D camera presets in a real window, and the sketch tab draws through the same click handler the canvas calls, exports a DXF and reads it back with the reader the Import tab uses. PySide6 is optional: without it the tests skip
and the core is unaffected - so CI has a **separate job that installs PySide6 and runs the
GUI tests**, otherwise a GUI bug could pass the suite unnoticed.
