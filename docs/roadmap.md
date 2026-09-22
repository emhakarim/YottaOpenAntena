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
| Test suite | 180 tests, all passing (see docs/verification.md for the running count) |
| Documentation | this set |
| **Accuracy calibration of the generated model** | **open** |
| **Dielectric loss in the generated solver model** | **open** |
| Result plotting (optional, needs matplotlib) | open |

### Known open items in Phase 1

1. **Model accuracy.** Against an independent implementation our model first sat
   4.31 % low; adding metal-edge snapping (`AddEdges2Grid`, the practice the openEMS
   tutorial uses) recovered about half of that, to 2.26 %. Solver settings
   (boundary, PML depth, domain size, mesh grading) were eliminated as a class.
   The residual is attributed to structural differences - ground footprint, feed
   realisation, mesh-line placement. See `docs/verification.md`.
2. **Dielectric loss is implemented but not validated in absolute terms.** The
   generator maps the loss tangent onto an equivalent conductivity
   (`--loss-model kappa` | `none`), exact at the sweep centre and drifting as 1/f;
   the generated script prints the implied tan delta at the sweep edges. No
   reference with a known Q has been used yet, so loss results are valid for
   relative comparisons only.
3. **One port only.** An NxM array is generated as geometry with a single port;
   a corporate feed network and per-element ports are not modelled.
4. **Generation-time contract is complete; runtime ergonomics are not.** Boundary
   type, PML cells, mesh density, smoothing ratio, air and ground margins, loss
   model, metal-edge snapping, timestep cap and end criteria are all knobs, they
   are recorded in `run_manifest.json`, and `converged`/`timesteps` are reported
   with the parsed results. Still missing: live progress streaming during a long
   run, and a flag for a run that was stopped early.

## Phase 2 â€” physics coverage

* Dielectric-loss modelling (dispersive material from measured data / fitted
  Debye parameters) and a loss-verification case.
* Accuracy calibration and a reference-case regression test against a published
  or tutorial result.
* Unit-cell / periodic boundary mode for infinite-array studies.
* Finite 4x4 array with mutual-coupling extraction (S-matrix) and a coupling
  report.
* Feed network analysis with scikit-rf and a corporate-feed generator.
* Wire antennas via nec2++ with the same neutral model (second adapter, proving
  the abstraction).
* Convergence reporting: flag runs that hit the timestep cap or miss the end
  criteria.

## Phase 3 â€” desktop GUI (started)

* PySide6 shell: project tree, material/stackup editor, geometry editor, 3-D
  viewport (PyVista), result plots (matplotlib), run queue with progress.
* Composite explorer UI: mixing-rule spread, warnings, sensitivity sweeps.
* Batch/sweep UI over the existing sweep engine.

Done so far: four-tab window (material/composite, design, simulate, results), a
worker thread so simulations do not block the event loop, and an offscreen smoke
test. Not done: 3-D viewer, live solver log, batch UI, packaging.

## Phase 4 â€” depth and packaging

* Optimisation (differential evolution / CMA-ES over the sweep engine) and
  surrogate models.
* Measurement import and comparison workflow (Touchstone in, overlay with
  simulation, error metrics).
* Packaging (PyInstaller), CI, contribution guide, example gallery.
