# Roadmap

## Phase 1 â€” headless core (current)

Goal: a scriptable, dependency-free core that can design a patch, lay out an
array, explore composite materials, and drive a real solver â€” with honest
reporting of what is and is not verified.

| Item | State |
|---|---|
| Neutral project model + JSON round-trip | done |
| Material library + loss terms | done |
| Composite mixing rules + validity warnings | done |
| Debye/Lorentz/Drude models + 1-pole Debye fit | done (one residual-reporting bug found by tests and fixed) |
| Patch synthesis (transmission-line model) | done |
| Array layout, array factor, pattern cuts | done |
| openEMS generator (prepare / render / run / parse) | done, end-to-end run achieved |
| S11 metrics, Touchstone I/O, pattern/efficiency helpers | done |
| Sweep engine (dry-run enumeration) | done |
| sqlite result store | done (wired into `sweep run`) |
| CLI | done |
| Test suite | **305 tests, 2 skipped** (CI: `.github/workflows/tests.yml`; see docs/verification.md) |
| Documentation | this set |
| **Accuracy calibration of the generated model** | **open** |
| **Dielectric loss in the generated solver model** | **kappa done; native Debye done** (see docs/dispersive-substrates.md) |
| Result plotting | done (`openantenna plot`, matplotlib optional) |

### Known open items in Phase 1

1. **Model accuracy.** Against an independent implementation our model first sat
   4.31 % low; adding metal-edge snapping (`AddEdges2Grid`, the practice the openEMS
   tutorial uses) recovered about half of that, to 2.26 %. Solver settings
   (boundary, PML depth, domain size, mesh grading) were eliminated as a class.
   The residual is attributed to structural differences - ground footprint, feed
   realisation, mesh-line placement. See `docs/verification.md`.
2. **Dielectric loss: implemented (two ways), validation still open.** The generator can
   map the loss tangent onto an equivalent conductivity (`--loss-model kappa`) or hand a
   **dispersive single-pole Debye** material to the engine (`--loss-model debye`, see
   `docs/dispersive-substrates.md`; an earlier claim that CSXCAD had no dispersive API was
   wrong). A loss-verification batch against a reference with a known Q has not been run to
   convergence yet, so loss numbers are still for relative comparisons only.
3. **Feeds: per-element ports done, corporate network open.** `element_ports=True` creates
   one lumped port per array element and dumps them all (`port_<n>.csv`), and
   `yotta_tools/port_matrix.py` assembles the coupling S-matrix from one run per driven port
   (see `docs/array-s-matrix.md`). A corporate feed network - one input driving every element
   through printed lines - is **not** modelled; `element_ports` with a printed line is refused
   until it exists (spec: `docs/corporate-feed.md`).
4. **Generation-time contract is complete; runtime ergonomics are not.** Boundary
   type, PML cells, mesh density, smoothing ratio, air and ground margins, loss
   model, metal-edge snapping, timestep cap and end criteria are all knobs, they
   are recorded in `run_manifest.json`, and `converged`/`timesteps` are reported
   with the parsed results. Still missing: live progress streaming during a long
   run, and a flag for a run that was stopped early.

## Phase 2 â€” physics coverage

* Dielectric-loss modelling - **done**: native dispersive Debye substrate
  (`--loss-model debye`) plus a banded-kappa fallback with a measured error
  (`yotta_tools/loss_fit.py`). Loss *validation* to convergence is still open.
* Accuracy calibration and a reference-case regression test against a published
  or tutorial result - **regression done** (waveguide TE10 benchmark passes; patch anchor
  recorded), calibration waits on converged runs (see `docs/experiment-k1-verdict.md`).
* Unit-cell / periodic boundary mode for infinite-array studies - **done** (PEC/PMC walls).
* Finite 4x4 array with mutual-coupling extraction (S-matrix) and a coupling
  report - **ports + assembly done** (`element_ports`, `yotta_tools/port_matrix.py`);
  the 4x4 run itself is queued (16 converged runs).
* Feed network analysis with scikit-rf and a corporate-feed generator - **open**
  (spec drafted in `docs/corporate-feed.md`).
* Wire antennas via nec2++ with the same neutral model (second adapter, proving
  the abstraction) - **done** (adapter + a locally built nec2c engine).
* Convergence reporting: flag runs that hit the timestep cap or miss the end
  criteria - **done** (table/CSV/JSON columns plus an unconverged counter).

## Phase 3 â€” desktop GUI (started)

* PySide6 shell: project tree, material/stackup editor, geometry editor, 3-D
  viewport (PyVista), result plots (matplotlib), run queue with progress.
* Composite explorer UI: mixing-rule spread, warnings, sensitivity sweeps.
* Batch/sweep UI over the existing sweep engine.

Done so far: four-tab window (material/composite, design, simulate, results); a worker
thread so simulations do not block the event loop; offscreen smoke tests; a solver
progress bar driven by the solver's own timestep lines (plus `progress.json` per run); a
to-scale array preview beside the array-factor plot **and a 3-D preview of the same
model** (plain matplotlib, no new dependency; PyVista remains an option for the owner to
decide); a **project tree dock** that mirrors the neutral model and its validity warnings; run provenance and the far-field cut in the results tab plus an **A/B overlay**
comparing two runs on one panel with the resonance shift in MHz and %; project save/load
through the neutral model JSON; a sensitivity plot of the mixing models against the
Wiener bounds; and a sequential batch queue with per-case progress. Not done: packaging
(PyInstaller); a stacked-dielectric stackup editor is blocked until the Phase 1 generator
supports more than one dielectric layer (it currently refuses, honestly).

## Phase 4 â€” depth and packaging

* Optimisation (differential evolution / CMA-ES over the sweep engine) and
  surrogate models.
* Measurement import and comparison workflow (Touchstone in, overlay with
  simulation, error metrics).
* Packaging (PyInstaller), CI, contribution guide, example gallery.
