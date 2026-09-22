# Desktop GUI (Phase 3)

A Qt (PySide6) desktop application. Not a web dashboard: the solver runs locally as a
subprocess, the plots are native, and there is nothing to deploy. Every panel calls the
same functions the CLI calls, so the GUI cannot drift away from the scriptable core.

```powershell
.venv\Scripts\python.exe -m pip install PySide6-Essentials
python -m openantenna.gui
```

## The four tabs

| Tab | What it does |
|---|---|
| **Material & composite** | The built-in material library (reference values, not measurements), plus a two-phase composite explorer: mixing models, their validity warnings, and a sensitivity plot of ε_eff against filler loading with the Wiener bounds and the current operating point marked |
| **Design** | Patch synthesis from the transmission-line model; array parameters; a **2-D layout drawn to scale** or a **3-D preview** of the same model; the array-factor cut; and **save/load of the neutral project JSON** (the same document the CLI reads) |
| **Simulate** | Mesh, substrate cells, loss model, and the three A/B knobs (`port_refine`, `edge_snapping`, `nf2ff`); generate, run in a worker thread; a **progress bar driven by the solver's own timestep lines**; and a **sequential batch queue** |
| **Results** | Load a run directory: S11 with its metrics, the run's own provenance (mesh, substrate, knobs, stop criteria, convergence), the far-field cut and summary, an **A/B overlay** of a second run with the resonance shift, and a warning when a number is physically impossible |

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
  footprint.
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
check the figures that come out (axes, patches, curves). PySide6 is optional: without it
the tests skip and the core is unaffected.
