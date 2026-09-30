# Local web UI (prototype, 2026-09-29)

A second front end for the **modeling half** of the tool: a single page served by the
package itself, in the standard library, on localhost.  It exists because the owner asked
whether a web-based GUI would look better than the desktop one - this answers with
something runnable instead of a promise.

```powershell
python -m openantenna.webui          # -> 127.0.0.1:8077   (--host/--port to override)
```

## The contract

* **Offline, stdlib only.** The page and every asset it loads come from your own Python
  process; no CDN, no external fonts, no telemetry.  The default bind is `127.0.0.1`.
* **One core, two front ends.** Every endpoint calls the same package functions the desktop
  tab calls (`geometry.params`, `geometry.sketch`, `geometry.cad`, `geometry.patch`), so
  the two cannot drift; the shape-to-polygon conversion lives in
  `geometry.sketch.shapes_to_polygons` for exactly that reason.
* **No server state.** Requests are stateless; the page holds the model and posts it.

## What v0 covers (and what it does not)

| Covered | Not yet |
|---|---|
| Parameter table (name = expression, live resolve, errors per row) | Freehand drawing tools (the desktop tab has them) |
| **+ Add block** by numbers, corners as expressions | Solver tabs (Generate/Run, progress, results) - next step, progress via polling |
| DXF export (the same writer; closed shapes only, skips are listed) | Batch queue / sweep / optimise surfaces |
| Solver-grid preview (the same rasteriser as the desktop grid view) | Packaged distribution story |

## API (all `POST`, JSON in/out)

| Endpoint | Body | Returns |
|---|---|---|
| `/api/resolve` | `parameters`, `expressions` | resolved values, per-name errors, evaluated expressions |
| `/api/dxf` | `shapes`, `layer` | DXF text (closed shapes; skipped shapes are explained) |
| `/api/grid` | `shapes`, `cell_mm` | cell counts, rows as `0/1` strings, stroke fraction, bounds |
| `/api/patch` | `frequency_ghz`, `epsilon_r`, `height_mm`, `feed` | patch synthesis numbers + warnings |

Errors are data with a 400 status and a human message - a broken polygon refuses, never a
stack trace.

## Tests

```powershell
python -m unittest discover -s tests -p "test_webui.py"
```

The tests bind an ephemeral port, drive every endpoint through real HTTP, assert the page
contains no external references (the offline contract), and read the exported DXF back
with the same reader the Import tab uses.

## Simulate and Results (since 2026-09-29 evening)

The owner made this the **primary front end**; the desktop app stays as an option, and both
drive the same core functions.

* **Simulate** builds the neutral project from the page's fields (or explicit W/L), merges
  the Modeling shapes when the include switch is on, writes the deck plus manifest
  (`/api/generate`), then runs it through the same adapter call the desktop worker makes
  (`/api/run`, one run at a time).  Progress comes from the solver's own `progress.json`
  plus the adapter's on-progress snapshots (`/api/run_status`).  There is deliberately no
  cancel button yet - stopping the server process stops the run, and the desktop app never
  had a cancel either.
* **Results** (`/api/results`) reads a run directory: the S11 curve and metrics, the
  provenance block from `run_manifest.json`, the -10 dB bands, and the far-field table when
  NF2FF ran.  Every number is model output; the provenance block names the mesh and loss
  model used.
* Tests cover the generate path offline (deck + manifest + sketch count), a synthetic run
  directory for results, and the run state machine through an injected runner
  (`webui.set_run_runner`) - nothing needs a solver in CI.

## Cancellation (2026-09-29 night)

The Run panel now has **Cancel run** (`/api/run_cancel`): the server sets a cancel event and
the adapter's `_execute` kills the solver **process tree** (Windows `taskkill /T`, because
`openEMS.exe` is a child of the script process - killing only the script leaves an orphan
burning CPU).  The run status becomes `cancelled`; the page stops polling and says plainly
that no results were written.  Tested at both levels: the adapter (a real subprocess, stopped
by the event) and the web state machine (an injected runner that honours the event).

## One-command start

```powershell
python scripts/start_webui.py                      # port 8077, opens the browser
python scripts/start_webui.py --no-browser --port 8080
```

The script sets `OPENEMS_ROOT` from `tools/openEMS` when it exists, binds localhost, and
refuses loudly when the port is already taken (two servers on one port would split
connections and serve a stale page - the Windows double-bind footgun).

## Drawing canvas, port placement, and materials (2026-09-30)

The Modeling tab's canvas is now interactive (the canvas only builds ``state.shapes``;
the server already consumed that list for the grid preview, DXF export and the Simulate
include switch, so nothing below adds a new write path):

* **Tools**: rectangle (drag), polygon (click vertices, double-click / Enter closes),
  trace (open polyline - DXF only), circle (drag centre -> rim), 1 mm snapping, undo,
  Esc cancels. Shapes feed the solver-grid preview, DXF export and deck include
  exactly like the numeric "+ Add block".
* **Port placement**: the Port & feed panel sets the feed mode, an inset-depth override
  (mm; empty = generator synthesis) and the line width. With "patch + port aid" on,
  the synthesised patch and its centreline are drawn, and the port marker can be
  dragged (tool "port") or typed; ``feed_inset_mm`` / ``feed_line_width_mm`` flow into
  the generator (bounded by the patch length). Arbitrary off-centre ports need
  generator work - next slice.
* **Materials**: the built-in dielectric library is injected into the page at serve
  time; picking one shows eps_r / tan_delta / source note and sets the Simulate
  material. Custom (user-defined) materials are a later slice.

Review findings fixed with this slice:

* **F2**: a valid-JSON body that is not an object now answers
  ``400 the request body must be a JSON object`` instead of dropping the connection;
* **F1**: the run progress bar reads its cap from the deck's ``run_manifest.json``,
  so a run-time ``max_timesteps`` can no longer make the bar report nonsense
  percentages (baked-cap semantics unchanged; documented in the Simulate tab).
