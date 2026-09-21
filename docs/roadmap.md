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
| Test suite | 128 tests, all passing |
| Documentation | this set |
| **Accuracy calibration of the generated model** | **open** |
| **Dielectric loss in the generated solver model** | **open** |
| Result plotting (optional, needs matplotlib) | open |

### Known open items in Phase 1

1. **Model accuracy.** A first PTFE patch run gave a resonance ~7 % below the
   transmission-line prediction and a weak match (|S11| ~ -13 dB). Mesh density,
   feed geometry and port placement all need calibration against a reference
   case before synthesis numbers can be trusted as design authority.
2. **Dielectric loss is not yet in the solver model.** The generator writes
   `kappa = 0` and records the loss tangent only as a comment. For a composite
   material study this is the important gap: openEMS needs either a dispersive
   material definition or an equivalent conductivity to represent tan delta.
3. **One port only.** An NxM array is generated as geometry with a single port;
   a corporate feed network and per-element ports are not modelled.
4. **No convergence control exposed.** Timestep cap and end criteria are
   hard-coded constants, and a run that hits the step cap is not flagged in the
   results (only in the solver log).

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
