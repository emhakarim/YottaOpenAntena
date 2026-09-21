# Architecture

## Layers

```
                    +-------------------------------+
                    |  CLI  (openantenna/cli.py)    |   Phase 1 entry point
                    +---------------+---------------+
                                    |
        +---------------------------+---------------------------+
        |                                                       |
+-------v--------+                                   +----------v---------+
| neutral model  |  model/project.py                 |  sweep engine      |
| (JSON, no      |  substrate, patch, array,         |  sweep/engine.py   |
|  solver detail)|  frequency sweep                  +----------+---------+
+-------+--------+                                              |
        |                                                       |
        |              +----------------------------------------+
        |              |
+-------v--------------v--------+        +------------------------+
| geometry synthesis            |        | material layer         |
| geometry/patch.py (TL model)  |        | materials/library.py   |
| geometry/array.py (layout+AF) |<------>| materials/mixing.py    |
+---------------+--------------+        | materials/dispersion.py|
                |                       +------------------------+
                |
+---------------v---------------+
| solver adapter                |   solvers/base.py  (contract)
| solvers/openems.py            |   solvers/openems.py (render/prepare/run/parse)
+---------------+---------------+
                |  generated script + project.json  (file-based boundary)
                v
        +----------------+        +--------------------------+
        | external solver|  --->  | post-processing          |
        | openEMS (GPLv3)|        | postproc/sparams.py      |
        +----------------+        | postproc/patterns.py     |
                                  +-------------+------------+
                                                |
                                  +-------------v------------+
                                  | result store (sqlite3)   |
                                  | store/results.py         |
                                  +--------------------------+
```

## Design rules

1. **The neutral model is the single source of truth.** `model/project.py`
   contains no solver-specific concept. Adapters translate outward; no adapter
   concept is allowed to leak inward.
2. **Solver adapters are separated by a process boundary.** An adapter renders
   an input deck, runs the solver as a subprocess, and parses files. See
   `docs/licensing.md`.
3. **Availability is reported, never assumed.** `SolverAdapter.available()`
   probes the runtime and returns a reason string. `run()` raises
   `SolverUnavailableError` rather than returning placeholder data.
4. **Two levels of validation.** Bad physics is a construction error
   (`ValueError`); questionable engineering is a warning string
   (`Project.check()`), so a 0.7-lambda spacing stays legal but is flagged.
5. **Standard library only in Phase 1.** No numpy/scipy in the core or the
   tests. This keeps the toolkit usable on a bare Python, keeps the test suite
   fast, and forces the numerical definitions to be explicit rather than
   hidden behind a library call. Numeric acceleration can be added later behind
   the same interfaces.
6. **Fabrication-impacting numbers are labelled.** Synthesis output states that
   the transmission-line model is a first-order aid and must be confirmed with a
   full-wave run.

## Module map

| Path | Responsibility |
|---|---|
| `openantenna/materials/library.py` | `Material` dataclass, built-in library, loss terms, complex permittivity |
| `openantenna/materials/mixing.py` | two-phase composite mixing rules + validity warnings |
| `openantenna/materials/dispersion.py` | Debye / Lorentz / Drude models, 1-pole Debye fitting |
| `openantenna/model/project.py` | neutral project model, validation, JSON round-trip |
| `openantenna/geometry/patch.py` | rectangular patch synthesis (transmission-line model) |
| `openantenna/geometry/array.py` | element positions, array layout, array factor |
| `openantenna/solvers/base.py` | adapter contract, `SolverRun`, subprocess execution |
| `openantenna/solvers/openems.py` | openEMS script generation, availability probe, result parsing |
| `openantenna/postproc/sparams.py` | S11 trace, VSWR, return loss, bandwidth, Touchstone I/O |
| `openantenna/postproc/patterns.py` | element pattern, pattern multiplication, directivity, efficiency budget |
| `openantenna/sweep/engine.py` | sweep axes, job enumeration, dry-run manifest |
| `openantenna/store/results.py` | sqlite3 run records |
| `openantenna/cli.py` | argparse CLI |

## Where the GUI will plug in

The GUI (Phase 3) must be a *client* of the same package: it should call the
CLI-equivalent functions in-process and never reach into solver scripts. The
natural seams are:

* `model.Project` in / `PatchDesign` + `ArrayLayout` out for the geometry editor;
* `materials.mixing.compare_models()` for the composite explorer;
* `solvers.openems.OpenEMSSolver.prepare()` + a worker thread calling `run()`;
* `postproc.sparams.S11Trace` for the plotting layer.

Nothing in the core needs to change for that, which is the point of keeping the
model neutral.
