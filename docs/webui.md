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
