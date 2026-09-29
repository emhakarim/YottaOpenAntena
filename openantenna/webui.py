"""Local web UI (prototype): modeling + simulate + results, offline and stdlib only.

Run:  python -m openantenna.webui   ->  127.0.0.1:8077

The desktop GUI's reasons were "offline, solver local, no server".  A server bound to
127.0.0.1 keeps the first two and trades the third for a look we can style with CSS; every
asset the page loads comes from this process - nothing external, ever.  The owner has made
this the primary front end; the desktop app stays as an option (same core functions).

The API reuses the same package functions the desktop tabs call, so the front ends cannot
drift: /api/resolve, /api/dxf, /api/grid, /api/patch, /api/generate, /api/run,
/api/run_status, /api/results.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .geometry.cad import dxf_text, rasterise_segments, stroke_fraction
from .geometry.params import ParameterError, ParameterTable, evaluate_expression
from .geometry.sketch import shapes_to_polygons
from .solvers.openems import OpenEMSSolver


def _resolve(payload):
    """Resolve a parameter table and evaluate expressions against it."""
    table = ParameterTable()
    for entry in payload.get("parameters", []):
        pair = list(entry) + ["", ""]
        table.set(str(pair[0]).strip(), str(pair[1]).strip())
    values, errors = table.resolve()
    evaluated = []
    evaluate_errors = []
    for text in payload.get("expressions", []):
        try:
            evaluated.append(evaluate_expression(str(text).strip(), values))
        except ParameterError as exc:
            evaluated.append(None)
            evaluate_errors.append(str(exc))
    return {
        "values": values,
        "errors": errors,
        "evaluated": evaluated,
        "evaluate_errors": evaluate_errors,
    }, None


def _polygon_segments(polygons):
    segments = []
    for polygon in polygons:
        count = len(polygon)
        for index in range(count):
            segments.append((polygon[index], polygon[(index + 1) % count]))
    return segments


def _dxf(payload):
    """Closed shapes -> DXF text (the same writer the desktop tab uses)."""
    polygons, notes = shapes_to_polygons(payload.get("shapes", []))
    if not polygons:
        return None, "nothing to export: closed shapes only - " + (
            "; ".join(notes) or "no shapes given"
        )
    layer = str(payload.get("layer") or "sketch")
    entities = [("polyline", list(polygon), True) for polygon in polygons]
    return {
        "dxf": dxf_text(entities, layer=layer),
        "notes": notes,
        "polygons": len(polygons),
    }, None


def _grid(payload):
    """Closed shapes -> which solver-grid cells their edges would cross."""
    cell_mm = float(payload.get("cell_mm", 2.0) or 2.0)
    if cell_mm <= 0.0:
        return None, "cell size must be positive"
    polygons, notes = shapes_to_polygons(payload.get("shapes", []))
    if not polygons:
        return None, "nothing to rasterise: closed shapes only - " + (
            "; ".join(notes) or "no shapes given"
        )
    segments = _polygon_segments(polygons)
    try:
        shape, rows = rasterise_segments(segments, cell_mm * 1e-3)
    except ValueError as exc:
        return None, "grid view refused: %s" % exc
    xs = [x for start, end in segments for x in (start[0], end[0])]
    ys = [y for start, end in segments for y in (start[1], end[1])]
    return {
        "cols": shape[0],
        "rows": shape[1],
        "cells": ["".join("1" if cell else "0" for cell in row) for row in rows],
        "stroke_fraction": stroke_fraction(rows),
        "x_min_mm": min(xs) * 1e3,
        "y_min_mm": min(ys) * 1e3,
        "cell_mm": cell_mm,
        "notes": notes,
    }, None


def _patch(payload):
    """Patch synthesis, the same numbers the Design tab shows."""
    from .geometry.patch import synthesize_patch

    frequency_hz = float(payload.get("frequency_ghz", 2.45) or 2.45) * 1e9
    epsilon_r = float(payload.get("epsilon_r", 2.1) or 2.1)
    height_m = float(payload.get("height_mm", 1.6) or 1.6) * 1e-3
    feed_mode = str(payload.get("feed") or "inset")
    try:
        design = synthesize_patch(frequency_hz, epsilon_r, height_m, feed_mode)
    except ValueError as exc:
        return None, str(exc)
    return {
        "width_mm": design.width_m * 1e3,
        "length_mm": design.length_m * 1e3,
        "inset_mm": design.inset_depth_m * 1e3,
        "feed_line_width_mm": design.feed_line_width_m * 1e3,
        "warnings": list(design.warnings),
    }, None


def _solver_kwargs_from(payload):
    return {
        "mesh_cells_per_wavelength": int(payload.get("mesh_cells", 15) or 15),
        "substrate_cells": int(payload.get("substrate_cells", 8) or 8),
        "loss_model": str(payload.get("loss_model") or "kappa"),
        "port_refine": bool(payload.get("port_refine", True)),
        "metal_edge_snapping": bool(payload.get("edge_snapping", True)),
        "nf2ff": bool(payload.get("nf2ff", False)),
        "max_timesteps": int(payload.get("max_timesteps", 400000) or 400000),
        "end_criteria": float(payload.get("end_criteria", 1e-4) or 1e-4),
    }


def _project_from(payload):
    """Build the neutral project from the page's fields (the same shape the Design tab makes)."""
    from .materials.library import get_material
    from .model.project import (
        ArrayConfig,
        FrequencySweep,
        PatchGeometry,
        Project,
        SubstrateStackup,
    )

    frequency_hz = float(payload.get("frequency_ghz", 2.45) or 2.45) * 1e9
    material_name = str(payload.get("material") or "PTFE")
    height_m = float(payload.get("height_mm", 1.6) or 1.6) * 1e-3
    width_m = float(payload.get("width_mm") or 0.0) * 1e-3
    length_m = float(payload.get("length_mm") or 0.0) * 1e-3
    points = int(payload.get("sweep_points", 201) or 201)
    try:
        get_material(material_name)
    except KeyError:
        raise ValueError(
            "unknown material %r - use a built-in name such as PTFE, FR-4 or RO4003C"
            % material_name
        ) from None
    project = Project(
        name=str(payload.get("name") or "web-design"),
        substrate=SubstrateStackup.single(material_name, height_m),
        patch=PatchGeometry(
            width_m=width_m or None,
            length_m=length_m or None,
            feed_mode=str(payload.get("feed") or "inset"),
        ),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep.fractional(frequency_hz, 0.15, points=points),
    )
    shapes = payload.get("shapes") or []
    polygons, _notes = shapes_to_polygons(shapes)
    merged = replace(project, sketch_polygons=tuple(polygons)) if polygons else project
    return merged


def _generate(payload):
    """Write the deck (and manifest) for the current fields; no solver needed."""
    project = _project_from(payload)
    solver = OpenEMSSolver(**_solver_kwargs_from(payload))
    rundir_text = str(payload.get("rundir") or "").strip() or "runs/web_run"
    prepared = solver.prepare(project, Path(rundir_text))
    return {
        "rundir": str(prepared),
        "project_json": str(prepared / solver.project_name),
        "script": str(prepared / solver.script_name),
        "manifest": str(prepared / "run_manifest.json"),
        "warnings": project.check(),
        "sketch_polygons": len(project.sketch_polygons),
    }, None


# --------------------------------------------------------------- run state machine

_RUN_LOCK = threading.Lock()
_RUN: dict = {
    "status": "idle",  # idle | running | done | failed
    "rundir": None,
    "cap": None,
    "started_at": None,
    "finished_at": None,
    "progress": None,
    "error": None,
    "summary": None,
}
_RUN_RUNNER = None  # tests inject a deterministic runner here


def set_run_runner(runner) -> None:
    """Install a runner for tests: ``runner(rundir, solver_kwargs, on_progress) -> summary``."""
    global _RUN_RUNNER
    _RUN_RUNNER = runner


def _real_runner(rundir: Path, solver_kwargs: dict, on_progress) -> dict:
    """The production runner: the same adapter call the desktop worker makes."""
    solver = OpenEMSSolver(**solver_kwargs)
    _RUN["cap"] = getattr(solver, "max_timesteps", None)
    run = solver.run(rundir, on_progress=on_progress)
    if run.status != "ok":
        log_tail = (getattr(run, "log", "") or "")[-1200:]
        raise RuntimeError(
            "the solver exited with code %s; log tail:\n%s"
            % (getattr(run, "returncode", "?"), log_tail)
        )
    return solver.parse_results(rundir)


def _run_worker(rundir: Path, solver_kwargs: dict) -> None:
    runner = _RUN_RUNNER or _real_runner

    def on_progress(snapshot) -> None:
        cap = _RUN.get("cap")
        timestep = getattr(snapshot, "timestep", None)
        percent = (
            min(100, int(round(100.0 * timestep / cap))) if (cap and timestep) else None
        )
        _RUN["progress"] = {
            "timestep": timestep,
            "energy_db": getattr(snapshot, "energy_db", None),
            "elapsed_s": getattr(snapshot, "elapsed_s", None),
            "percent": percent,
            "at": time.time(),
        }

    try:
        summary = runner(rundir, solver_kwargs, on_progress)
    except Exception as exc:
        with _RUN_LOCK:
            _RUN.update(
                status="failed",
                error="%s: %s" % (type(exc).__name__, exc),
                finished_at=time.time(),
            )
        return
    with _RUN_LOCK:
        _RUN.update(status="done", summary=summary, finished_at=time.time(), progress=None)


def _run(payload):
    """Start a simulation for an already-generated deck; one at a time."""
    rundir = str(payload.get("rundir") or "").strip()
    if not rundir:
        return None, "a run directory is required (generate the model first)"
    with _RUN_LOCK:
        state = _RUN["status"]
    if state == "running":
        return None, "a run is already in progress - wait for it to finish"
    path = Path(rundir)
    if not (path / "sim.py").exists():
        return None, "no sim.py in %s - generate the model first" % path
    solver_kwargs = _solver_kwargs_from(payload)
    thread = threading.Thread(target=_run_worker, args=(path, solver_kwargs), daemon=True)
    with _RUN_LOCK:
        _RUN.update(
            status="running",
            rundir=str(path),
            started_at=time.time(),
            finished_at=None,
            error=None,
            summary=None,
            progress=None,
        )
    thread.start()
    return {"status": "running", "rundir": str(path)}, None


def _run_status(payload=None):
    """The run's state; while running, the solver's own progress.json is preferred."""
    with _RUN_LOCK:
        snapshot = dict(_RUN)
    progress = snapshot.get("progress")
    if snapshot["status"] == "running" and snapshot.get("rundir"):
        progress_path = Path(snapshot["rundir"]) / "progress.json"
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            progress = progress or None
    return {
        "status": snapshot["status"],
        "rundir": snapshot["rundir"],
        "started_at": snapshot["started_at"],
        "finished_at": snapshot["finished_at"],
        "progress": progress,
        "error": snapshot["error"],
        "summary": snapshot["summary"],
    }, None


def _manifest_summary(run_dir: Path):
    path = run_dir / "run_manifest.json"
    if not path.exists():
        return {"note": "run_manifest.json not found (was this produced by the generator?)"}
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {"note": "run_manifest.json is not readable"}
    substrate = meta.get("substrate") or {}
    mesh = meta.get("mesh") or {}
    return {
        "solver": meta.get("solver"),
        "generator_version": meta.get("generator_version"),
        "substrate": substrate.get("material"),
        "thickness_mm": (substrate.get("thickness_m") or 0.0) * 1e3,
        "boundary": meta.get("boundary"),
        "mesh_cells": mesh.get("cells_per_wavelength"),
        "substrate_cells": mesh.get("substrate_cells"),
        "port_refine": mesh.get("port_refine"),
        "nf2ff": meta.get("nf2ff"),
        "loss_model": (meta.get("dielectric_loss") or {}).get("model"),
        "max_timesteps": meta.get("max_timesteps"),
        "warnings": meta.get("warnings") or [],
    }


def _farfield_text(run_dir: Path):
    try:
        from .postproc.farfield import read_summary as read_farfield_summary
        from .postproc.farfield import summary_text as farfield_summary_text

        points = read_farfield_summary(run_dir)
    except (OSError, ValueError, FileNotFoundError):
        return None
    if not points:
        return None
    return farfield_summary_text(points)


def _results(payload):
    """Read a run directory: S11 curve + metrics + provenance + far field."""
    from .postproc.sparams import S11Trace

    rundir = Path(str(payload.get("rundir") or "").strip())
    csv_path = rundir / "s11.csv" if rundir.is_dir() else rundir
    if not csv_path.exists():
        return None, "no s11.csv at %s - run the simulation first" % csv_path
    try:
        trace = S11Trace.from_csv(csv_path)
        index = trace.worst_match_index()
        vswr = trace.vswr()
        bands = trace.bandwidth_below(-10.0)
        fractional = trace.fractional_bandwidth(-10.0)
    except Exception as exc:
        return None, "cannot load %s: %s: %s" % (csv_path.name, type(exc).__name__, exc)
    try:
        impedances = trace.impedance_ohm()
        zin = [float(impedances[index].real), float(impedances[index].imag)]
    except Exception:
        zin = None
    run_dir = rundir if rundir.is_dir() else rundir.parent
    curve = [
        [float(frequency), float(db)]
        for frequency, db in zip(trace.frequencies_hz, trace.db())
    ]
    return {
        "file": str(csv_path),
        "points": len(curve),
        "curve": curve,
        "resonance_ghz": trace.frequencies_hz[index] / 1e9,
        "worst_db": float(trace.db()[index]),
        "vswr": float(vswr[index]),
        "zin": zin,
        "bands": [[float(a), float(b), float(w)] for a, b, w in bands],
        "fractional": fractional,
        "provenance": _manifest_summary(run_dir),
        "farfield": _farfield_text(run_dir),
    }, None


def _solver(payload=None):
    """Is the openEMS engine reachable from this server?  (For the page's status chip.)"""
    status = OpenEMSSolver().available()
    return {
        "available": bool(status.available),
        "binary": status.binary_path,
        "detail": status.detail,
    }, None


_ROUTES = {
    "/api/resolve": _resolve,
    "/api/dxf": _dxf,
    "/api/grid": _grid,
    "/api/patch": _patch,
    "/api/generate": _generate,
    "/api/run": _run,
    "/api/run_status": _run_status,
    "/api/results": _results,
    "/api/solver": _solver,
}

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenAntenna Studio - local web UI</title>
<style>
  :root {
    --bg: #17181c; --surface: #202226; --panel: #232529; --panel2: #2b2e33; --border: #33363b;
    --text: #e8e9ec; --muted: #9aa0a9; --accent: #4c8bf5; --accent-soft: rgba(76,139,245,.16);
    --danger: #ff7b72; --ok: #76c494;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; color: var(--text);
    font: 14px/1.55 "Segoe UI", Inter, system-ui, sans-serif;
    background-color: var(--bg);
    background-image: radial-gradient(1100px 520px at 12% -12%, rgba(76,139,245,.09), transparent 62%);
    background-repeat: no-repeat;
  }
  ::selection { background: rgba(76,139,245,.35); }

  header { padding: 18px 22px 2px; }
  .brandrow { display: flex; align-items: center; gap: 13px; }
  .mark {
    width: 34px; height: 34px; border-radius: 10px; flex: 0 0 auto;
    display: grid; place-items: center;
    background: linear-gradient(160deg, #5d97f7, #3d76d8);
    box-shadow: 0 6px 16px rgba(76,139,245,.35), inset 0 1px 0 rgba(255,255,255,.25);
  }
  h1 { font-size: 19px; margin: 0; font-weight: 650; letter-spacing: .1px; }
  .badge { font-size: 11px; font-weight: 600; color: #cfe0ff; background: var(--accent-soft);
           border: 1px solid rgba(76,139,245,.45); border-radius: 999px; padding: 1px 9px; vertical-align: 2px; }
  .sub { color: var(--muted); font-size: 12.5px; margin-top: 1px; }
  .chips { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
  .chip { border: 1px solid var(--border); background: var(--panel); border-radius: 999px;
          padding: 3px 11px; font-size: 12px; color: var(--muted);
          font-family: Consolas, "Cascadia Mono", monospace; }
  .chip.ok  { color: #b9e4c9; border-color: rgba(118,196,148,.55); background: rgba(118,196,148,.08); }
  .chip.bad { color: #ffb4ae; border-color: rgba(255,123,114,.55); background: rgba(255,123,114,.08); }

  nav.tabs { display: flex; gap: 4px; margin: 12px 22px 0; padding: 4px; width: max-content;
             background: var(--surface); border: 1px solid var(--border); border-radius: 999px; }
  nav.tabs button { border: none; background: transparent; color: var(--muted); border-radius: 999px;
                    padding: 6px 18px; font: inherit; font-size: 13.5px; cursor: pointer; transition: all .15s ease; }
  nav.tabs button:hover { color: var(--text); }
  nav.tabs button.active { background: var(--accent-soft); color: #cfe0ff; font-weight: 600;
                           box-shadow: inset 0 0 0 1px rgba(76,139,245,.45); }

  main { display: grid; grid-template-columns: 400px 1fr; gap: 14px; padding: 14px 22px 26px; align-items: start; }
  @media (max-width: 980px) { main { grid-template-columns: 1fr; } }

  section {
    background: linear-gradient(180deg, rgba(255,255,255,.022), rgba(255,255,255,0)), var(--panel);
    border: 1px solid var(--border); border-radius: 12px; padding: 13px 15px; margin-bottom: 14px;
    box-shadow: 0 10px 26px rgba(0,0,0,.20);
  }
  h2 { display: flex; align-items: center; gap: 8px; font-size: 11.5px; margin: 0 0 10px;
       color: var(--muted); text-transform: uppercase; letter-spacing: .08em; font-weight: 650; }
  h2::before { content: ""; width: 3px; height: 12px; background: var(--accent); border-radius: 2px; }

  label { color: var(--muted); font-size: 12px; }
  input, select {
    background: #1b1c20; color: var(--text); border: 1px solid var(--border); border-radius: 8px;
    padding: 6px 9px; font: inherit; font-size: 13px; width: 100%; transition: border-color .15s ease, box-shadow .15s ease;
  }
  input:focus, select:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(76,139,245,.16); }
  input.num, .num { font-family: Consolas, "Cascadia Mono", monospace; font-variant-numeric: tabular-nums; }

  button { background: var(--panel2); color: var(--text); border: 1px solid var(--border); border-radius: 8px;
           padding: 6px 13px; font: inherit; font-size: 13px; cursor: pointer; transition: all .15s ease; }
  button:hover { border-color: var(--accent); color: #fff; }
  button:active { transform: translateY(1px); }
  button.primary { background: linear-gradient(180deg, #5d97f7, #4c8bf5); border-color: #4c8bf5; color: #fff;
                   font-weight: 600; box-shadow: 0 6px 14px rgba(76,139,245,.25), inset 0 1px 0 rgba(255,255,255,.22); }
  button.primary:hover { filter: brightness(1.08); }
  button.mini { padding: 2px 8px; font-size: 12px; }

  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 5px 6px; font-size: 12.5px; border-bottom: 1px solid rgba(51,54,59,.7); }
  th { color: var(--muted); font-weight: 600; }
  tr:last-child td { border-bottom: none; }
  td.err { color: var(--danger); }

  .row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
  .row > label { white-space: nowrap; }
  .fields { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; margin-bottom: 9px; }
  .fields.three { grid-template-columns: repeat(3, 1fr); }
  .fields label { font-size: 11px; }
  .checks { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin: 4px 0 10px; }
  .checks label { display: flex; gap: 6px; align-items: center; color: var(--text); font-size: 13px; }
  .checks input { width: auto; accent-color: var(--accent); }

  #canvasWrap { background: #1a1b1f; border: 1px solid var(--border); border-radius: 12px; padding: 8px; }
  canvas { width: 100%; height: 420px; display: block; border-radius: 8px; }
  canvas.chart { height: 330px; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }

  .hint { border: 1px solid var(--border); border-left: 3px solid var(--border); background: rgba(255,255,255,.02);
          border-radius: 8px; padding: 8px 11px; font-size: 12.5px; color: var(--muted);
          margin-top: 9px; white-space: pre-wrap; min-height: 20px; }
  .hint.error { border-left-color: var(--danger); color: #ffb4ae; }
  .hint.ok    { border-left-color: var(--ok); color: #b9e4c9; }

  .result { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin-top: 9px; }
  .kv { background: #1b1c20; border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px; }
  .kv .k { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }
  .kv .v { font-family: Consolas, monospace; font-size: 15px; margin-top: 1px; }

  .progress { height: 14px; background: #1b1c20; border: 1px solid var(--border); border-radius: 999px;
              overflow: hidden; margin-top: 10px; }
  .progress > div { height: 100%; width: 0%; background: linear-gradient(90deg, #4c8bf5, #7aa9ff);
                    border-radius: 999px; transition: width .35s ease; }

  pre { background: #17181c; border: 1px solid var(--border); border-radius: 10px; padding: 9px 11px;
        font-family: Consolas, "Cascadia Mono", monospace; font-size: 12px; color: var(--muted);
        white-space: pre-wrap; max-height: 260px; overflow: auto; margin: 9px 0 0; }
  footer { color: var(--muted); font-size: 12px; padding: 2px 22px 20px; }
</style>
</head>
<body>
<header>
  <div class="brandrow">
    <span class="mark" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 18 18"><path d="M9 15V9M9 9L4 4M9 9l5-5" stroke="#fff" stroke-width="1.8" stroke-linecap="round" fill="none"/></svg></span>
    <div>
      <h1>OpenAntenna Studio <span class="badge">web</span></h1>
      <div class="sub">Offline and stdlib-only - served by your own Python on 127.0.0.1, using the same core functions as the desktop app. Nothing external is loaded.</div>
    </div>
    <div class="chips">
      <span class="chip" id="chipPort">127.0.0.1:8077</span>
      <span class="chip" id="engineChip">engine: checking ...</span>
    </div>
  </div>
</header>
<nav class="tabs">
  <button class="tab active" data-view="modeling" onclick="showView('modeling')">Modeling</button>
  <button class="tab" data-view="simulate" onclick="showView('simulate')">Simulate</button>
  <button class="tab" data-view="results" onclick="showView('results')">Results</button>
</nav>

<div id="view-modeling">
<main>
  <div>
    <section>
      <h2>Patch design</h2>
      <div class="fields">
        <div><label for="f0">frequency (GHz)</label><input id="f0" class="num" value="2.45"></div>
        <div><label for="er">epsilon r</label><input id="er" class="num" value="2.1"></div>
        <div><label for="hh">height (mm)</label><input id="hh" class="num" value="1.6"></div>
        <div><label for="feed">feed</label><select id="feed"><option>inset</option><option>edge</option><option>probe</option></select></div>
      </div>
      <button class="primary" onclick="synthesise()">Synthesise</button>
      <div class="result" id="patchOut"></div>
      <div id="patchWarn" class="sub" style="margin-top:6px"></div>
    </section>
    <section>
      <h2>Parameters (by definition)</h2>
      <table><thead><tr><th style="width:30%">name</th><th style="width:42%">expression</th><th>value</th><th></th></tr></thead><tbody id="paramsBody"></tbody></table>
      <div class="actions"><button onclick="addParam()">+ Add parameter</button></div>
    </section>
    <section>
      <h2>Add block (numbers, CST-style)</h2>
      <div class="fields">
        <div><label for="bx0">x0</label><input id="bx0" class="num" value="0"></div>
        <div><label for="by0">y0</label><input id="by0" class="num" value="0"></div>
        <div><label for="bx1">x1</label><input id="bx1" class="num" value="L"></div>
        <div><label for="by1">y1</label><input id="by1" class="num" value="W"></div>
      </div>
      <div class="row">
        <label for="bth">thickness (mm)</label>
        <input id="bth" class="num" value="h_sub" style="max-width:130px">
        <button class="primary" onclick="addBlock()">+ Add block</button>
      </div>
      <div class="sub">Corners and thickness accept parameter expressions; corners are evaluated when the block is added.</div>
    </section>
    <section>
      <h2>Shapes</h2>
      <table><thead><tr><th>shape</th><th>vertices</th><th>bounds (mm)</th><th>thickness</th><th></th></tr></thead><tbody id="shapesBody"></tbody></table>
      <div class="actions"><button onclick="clearShapes()">Clear all</button></div>
      <div class="sub">Closed shapes are merged into generated decks when the Simulate tab's include switch is on.</div>
    </section>
  </div>
  <div>
    <section>
      <h2>Canvas</h2>
      <div id="canvasWrap"><canvas id="cv" width="940" height="420"></canvas></div>
      <div class="actions">
        <button onclick="showGrid()">Show solver grid</button>
        <button onclick="drawCanvas()">Outlines only</button>
        <button onclick="exportDxf()">Export DXF</button>
      </div>
      <div id="status" class="hint">ready. Add a block or draw, then preview on the solver grid.</div>
    </section>
  </div>
</main>
</div>

<div id="view-simulate" style="display:none">
<main>
  <div>
    <section>
      <h2>Design</h2>
      <div class="fields three">
        <div><label for="simName">name</label><input id="simName" value="web-design"></div>
        <div><label for="simF0">frequency (GHz)</label><input id="simF0" class="num" value="2.45"></div>
        <div><label for="simMat">material</label><input id="simMat" value="PTFE"></div>
        <div><label for="simH">height (mm)</label><input id="simH" class="num" value="1.6"></div>
        <div><label for="simFeed">feed</label><select id="simFeed"><option>probe</option><option>inset</option><option>edge</option></select></div>
        <div><label for="simPts">sweep points</label><input id="simPts" class="num" value="201"></div>
        <div><label for="simW">W (mm, optional)</label><input id="simW" class="num" value=""></div>
        <div><label for="simL">L (mm, optional)</label><input id="simL" class="num" value=""></div>
      </div>
      <div class="checks">
        <label><input type="checkbox" id="simInclude" checked> include sketch shapes</label>
      </div>
    </section>
    <section>
      <h2>Solver</h2>
      <div class="fields three">
        <div><label for="simMesh">mesh cells / wavelength</label><input id="simMesh" class="num" value="15"></div>
        <div><label for="simSub">substrate cells</label><input id="simSub" class="num" value="8"></div>
        <div><label for="simLoss">dielectric loss</label><select id="simLoss"><option>kappa</option><option>none</option></select></div>
        <div><label for="simCap">max timesteps</label><input id="simCap" class="num" value="400000"></div>
        <div><label for="simEnd">end criteria</label><input id="simEnd" class="num" value="0.0001"></div>
      </div>
      <div class="checks">
        <label><input type="checkbox" id="simRefine" checked> port refine</label>
        <label><input type="checkbox" id="simSnap" checked> edge snapping</label>
        <label><input type="checkbox" id="simNf2ff"> NF2FF</label>
      </div>
      <div class="row">
        <label for="simDir">run directory</label>
        <input id="simDir" class="num" value="runs/web_run">
      </div>
    </section>
  </div>
  <div>
    <section>
      <h2>Run</h2>
      <div class="actions">
        <button onclick="generateModel()">Generate model</button>
        <button class="primary" onclick="startRun()">Run simulation</button>
        <button onclick="stopPolling()">Stop watching</button>
      </div>
      <div class="progress"><div id="simBar"></div></div>
      <div id="simStatus" class="hint">idle. Generate the model, then run it. One run at a time; progress comes from the solver's own progress.json.</div>
      <pre id="simDetail"></pre>
    </section>
  </div>
</main>
</div>

<div id="view-results" style="display:none">
<main>
  <div>
    <section>
      <h2>Load a run</h2>
      <div class="row">
        <label for="resultsDir">run directory</label>
        <input id="resultsDir" class="num" value="runs/web_run">
      </div>
      <div class="actions"><button class="primary" onclick="loadResults()">Load results</button></div>
      <div class="result" id="resMetrics"></div>
      <pre id="resProvenance"></pre>
    </section>
    <section>
      <h2>Far field (if NF2FF ran)</h2>
      <pre id="resFarfield">no far-field data loaded</pre>
    </section>
  </div>
  <div>
    <section>
      <h2>S11</h2>
      <div id="canvasWrap"><canvas id="cv2" class="chart" width="940" height="330"></canvas></div>
      <pre id="resBands"></pre>
    </section>
  </div>
</main>
</div>

<footer>offline - served by your own python - model output, not a measurement - DXF carries no units by convention</footer>
<script>
const state = { parameters: [["L", "30"], ["W", "20"], ["h_sub", "1.6"]], shapes: [], grid: null };
const $ = (id) => document.getElementById(id);

function showView(name) {
  ["modeling", "simulate", "results"].forEach((view) => {
    $("view-" + view).style.display = view === name ? "" : "none";
  });
  document.querySelectorAll("nav.tabs button").forEach((button) => {
    button.className = button.dataset.view === name ? "tab active" : "tab";
  });
}

function setStatus(text, isError) {
  const el = $("status");
  el.textContent = text || "";
  el.className = isError ? "hint error" : "hint";
}

function setSimStatus(text, kind) {
  const el = $("simStatus");
  el.textContent = text || "";
  el.className = "hint" + (kind ? " " + kind : "");
}

async function post(path, payload) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const body = await response.json();
  return { ok: response.ok, body: body };
}

async function checkEngine() {
  const chip = $("engineChip");
  try {
    const result = await post("/api/solver", {});
    if (result.ok && result.body.available) {
      chip.textContent = "engine: openEMS ready";
      chip.className = "chip ok";
      chip.title = result.body.detail || "";
    } else {
      chip.textContent = "engine: not reachable";
      chip.className = "chip bad";
      chip.title = (result.body && result.body.detail) || "";
    }
  } catch (err) {
    chip.textContent = "engine: unknown";
    chip.className = "chip";
  }
}

// ---------------- modeling: parameters ----------------
function renderParams() {
  const body = $("paramsBody");
  body.innerHTML = "";
  state.parameters.forEach((entry, index) => {
    const tr = document.createElement("tr");
    const nameCell = document.createElement("td");
    const nameInput = document.createElement("input");
    nameInput.value = entry[0];
    nameInput.className = "num";
    nameInput.setAttribute("aria-label", "parameter name");
    nameInput.addEventListener("input", () => { state.parameters[index][0] = nameInput.value; scheduleResolve(); });
    nameCell.appendChild(nameInput);
    const exprCell = document.createElement("td");
    const exprInput = document.createElement("input");
    exprInput.value = entry[1];
    exprInput.className = "num";
    exprInput.setAttribute("aria-label", "parameter expression");
    exprInput.addEventListener("input", () => { state.parameters[index][1] = exprInput.value; scheduleResolve(); });
    exprCell.appendChild(exprInput);
    const valueCell = document.createElement("td");
    valueCell.className = "num";
    valueCell.id = "pv" + index;
    const removeCell = document.createElement("td");
    const remove = document.createElement("button");
    remove.textContent = "x";
    remove.className = "mini";
    remove.title = "remove this parameter";
    remove.addEventListener("click", () => { state.parameters.splice(index, 1); renderParams(); });
    removeCell.appendChild(remove);
    tr.append(nameCell, exprCell, valueCell, removeCell);
    body.appendChild(tr);
  });
  resolveParams();
}

let resolveTimer = null;
function scheduleResolve() {
  clearTimeout(resolveTimer);
  resolveTimer = setTimeout(resolveParams, 250);
}

async function resolveParams() {
  const result = await post("/api/resolve", { parameters: state.parameters, expressions: [] });
  if (!result.ok) { setStatus(result.body.error, true); return; }
  state.parameters.forEach((entry, index) => {
    const cell = $("pv" + index);
    if (!cell) return;
    const name = entry[0];
    if (result.body.errors[name]) { cell.textContent = "! " + result.body.errors[name]; cell.className = "num err"; }
    else if (result.body.values[name] !== undefined) { cell.textContent = Number(result.body.values[name]).toPrecision(6); cell.className = "num"; }
    else { cell.textContent = ""; cell.className = "num"; }
  });
}

function addParam() {
  state.parameters.push(["param" + (state.parameters.length + 1), "1.0"]);
  renderParams();
}

// ---------------- modeling: shapes ----------------
async function addBlock() {
  const corners = [$("bx0").value, $("by0").value, $("bx1").value, $("by1").value].map((s) => s.trim() || "0");
  const result = await post("/api/resolve", { parameters: state.parameters, expressions: corners });
  if (!result.ok) { setStatus(result.body.error, true); return; }
  const problems = result.body.evaluate_errors.filter(Boolean);
  if (problems.length) { setStatus("could not add the block: " + problems.join("; "), true); return; }
  const [x0, y0, x1, y1] = result.body.evaluated;
  if (x0 === x1 || y0 === y1) { setStatus("could not add the block: zero width or height after evaluating the corners", true); return; }
  const thickness = $("bth").value.trim() || "1.6";
  state.shapes.push({ kind: "block", points: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], thickness: thickness });
  state.grid = null;
  renderShapes();
  drawCanvas();
  setStatus("added a block: " + Math.abs(x1 - x0).toFixed(3) + " x " + Math.abs(y1 - y0).toFixed(3) + " mm, thickness " + thickness);
}

function renderShapes() {
  const body = $("shapesBody");
  body.innerHTML = "";
  state.shapes.forEach((shape, index) => {
    const tr = document.createElement("tr");
    const xs = shape.points.map((p) => p[0]);
    const ys = shape.points.map((p) => p[1]);
    const bounds = shape.kind === "circle"
      ? "r " + Math.hypot(shape.points[1][0] - shape.points[0][0], shape.points[1][1] - shape.points[0][1]).toFixed(2)
      : (Math.max.apply(null, xs) - Math.min.apply(null, xs)).toFixed(2) + " x " + (Math.max.apply(null, ys) - Math.min.apply(null, ys)).toFixed(2);
    [shape.kind, String(shape.points.length), bounds, shape.thickness || ""].forEach((text) => {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    });
    const removeCell = document.createElement("td");
    const remove = document.createElement("button");
    remove.textContent = "x";
    remove.className = "mini";
    remove.title = "remove this shape";
    remove.addEventListener("click", () => { state.shapes.splice(index, 1); state.grid = null; renderShapes(); drawCanvas(); });
    removeCell.appendChild(remove);
    tr.appendChild(removeCell);
    body.appendChild(tr);
  });
}

function clearShapes() { state.shapes = []; state.grid = null; renderShapes(); drawCanvas(); setStatus(""); }

// ---------------- modeling: canvas ----------------
function viewBounds() {
  if (state.grid) {
    return { x0: state.grid.x_min_mm, y0: state.grid.y_min_mm,
             x1: state.grid.x_min_mm + state.grid.cols * state.grid.cell_mm,
             y1: state.grid.y_min_mm + state.grid.rows * state.grid.cell_mm };
  }
  if (!state.shapes.length) return { x0: 0, y0: 0, x1: 50, y1: 50 };
  const xs = [], ys = [];
  state.shapes.forEach((s) => s.points.forEach((p) => { xs.push(p[0]); ys.push(p[1]); }));
  return { x0: Math.min.apply(null, xs), y0: Math.min.apply(null, ys), x1: Math.max.apply(null, xs), y1: Math.max.apply(null, ys) };
}

function drawCanvas() {
  const canvas = $("cv");
  const ctx = canvas.getContext("2d");
  const width = canvas.width, height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(51,54,59,.55)";
  ctx.lineWidth = 1;
  for (let gx = 0; gx < width; gx += 32) { ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, height); ctx.stroke(); }
  for (let gy = 0; gy < height; gy += 32) { ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(width, gy); ctx.stroke(); }

  const b = viewBounds();
  const pad = 24;
  const spanX = Math.max(1e-9, b.x1 - b.x0), spanY = Math.max(1e-9, b.y1 - b.y0);
  const scale = Math.min((width - 2 * pad) / spanX, (height - 2 * pad) / spanY);
  const ox = (width - spanX * scale) / 2 - b.x0 * scale;
  const oy = height - (height - spanY * scale) / 2 + b.y0 * scale;
  const X = (x) => ox + x * scale;
  const Y = (y) => oy - y * scale;

  if (state.grid) {
    ctx.fillStyle = "rgba(118, 196, 148, 0.30)";
    const c = state.grid.cell_mm;
    state.grid.cells.forEach((row, ri) => {
      for (let ci = 0; ci < row.length; ci++) {
        if (row.charAt(ci) === "1") {
          const x = state.grid.x_min_mm + ci * c, y = state.grid.y_min_mm + ri * c;
          ctx.fillRect(X(x), Y(y + c), Math.max(1, c * scale), Math.max(1, c * scale));
        }
      }
    });
  }

  ctx.lineWidth = 2;
  state.shapes.forEach((shape) => {
    ctx.beginPath();
    if (shape.kind === "circle") {
      const cx = shape.points[0][0], cy = shape.points[0][1];
      const r = Math.hypot(shape.points[1][0] - cx, shape.points[1][1] - cy);
      ctx.arc(X(cx), Y(cy), r * scale, 0, Math.PI * 2);
    } else {
      shape.points.forEach((p, i) => { if (i === 0) { ctx.moveTo(X(p[0]), Y(p[1])); } else { ctx.lineTo(X(p[0]), Y(p[1])); } });
      if (shape.closed || shape.kind === "block") ctx.closePath();
    }
    if (shape.kind === "block") { ctx.fillStyle = "rgba(76, 139, 245, 0.14)"; ctx.fill(); }
    ctx.strokeStyle = "#4c8bf5";
    ctx.shadowColor = "rgba(76,139,245,.55)";
    ctx.shadowBlur = 8;
    ctx.stroke();
    ctx.shadowBlur = 0;
  });

  if (!state.shapes.length && !state.grid) {
    ctx.fillStyle = "#9aa0a9";
    ctx.font = "13px Segoe UI";
    ctx.fillText("No shapes yet - add a block on the left.", 24, 34);
  }
  ctx.fillStyle = "#9aa0a9";
  ctx.font = "12px Consolas, monospace";
  ctx.fillText("millimetres", width - 92, height - 10);
}

async function showGrid() {
  if (!state.shapes.length) { setStatus("nothing to rasterise: add a block first", true); return; }
  const result = await post("/api/grid", { shapes: state.shapes, cell_mm: 2.0 });
  if (!result.ok) { setStatus(result.body.error, true); return; }
  state.grid = result.body;
  drawCanvas();
  const notes = state.grid.notes.length ? "  notes: " + state.grid.notes.join("; ") : "";
  setStatus(state.grid.cols + " x " + state.grid.rows + " cells of " + state.grid.cell_mm + " mm; edges cross " + (state.grid.stroke_fraction * 100).toFixed(1) + " % of the grid" + notes);
}

async function exportDxf() {
  if (!state.shapes.length) { setStatus("nothing to export: add a block first", true); return; }
  const result = await post("/api/dxf", { shapes: state.shapes, layer: "sketch" });
  if (!result.ok) { setStatus(result.body.error, true); return; }
  const blob = new Blob([result.body.dxf], { type: "application/dxf" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "sketch.dxf";
  document.body.appendChild(link);
  link.click();
  link.remove();
  const notes = result.body.notes.length ? "  notes: " + result.body.notes.join("; ") : "";
  setStatus("exported " + result.body.polygons + " polygon(s) as DXF (millimetres by convention)" + notes);
}

async function synthesise() {
  const result = await post("/api/patch", { frequency_ghz: $("f0").value, epsilon_r: $("er").value, height_mm: $("hh").value, feed: $("feed").value });
  if (!result.ok) { setStatus(result.body.error, true); return; }
  const out = $("patchOut");
  out.innerHTML = "";
  [["width", result.body.width_mm.toFixed(2) + " mm"], ["length", result.body.length_mm.toFixed(2) + " mm"],
   ["inset depth", result.body.inset_mm.toFixed(2) + " mm"], ["line width", result.body.feed_line_width_mm.toFixed(2) + " mm"]].forEach((pair) => {
    const box = document.createElement("div");
    box.className = "kv";
    const k = document.createElement("div"); k.className = "k"; k.textContent = pair[0];
    const v = document.createElement("div"); v.className = "v"; v.textContent = pair[1];
    box.append(k, v);
    out.appendChild(box);
  });
  $("patchWarn").textContent = result.body.warnings.join("  ") || "";
}

// ---------------- simulate ----------------
function simPayload() {
  return {
    name: $("simName").value, frequency_ghz: $("simF0").value, material: $("simMat").value,
    height_mm: $("simH").value, feed: $("simFeed").value, sweep_points: $("simPts").value,
    width_mm: $("simW").value, length_mm: $("simL").value,
    mesh_cells: $("simMesh").value, substrate_cells: $("simSub").value, loss_model: $("simLoss").value,
    port_refine: $("simRefine").checked, edge_snapping: $("simSnap").checked, nf2ff: $("simNf2ff").checked,
    max_timesteps: $("simCap").value, end_criteria: $("simEnd").value,
    rundir: $("simDir").value,
    shapes: $("simInclude").checked ? state.shapes : [],
  };
}

async function generateModel() {
  setSimStatus("generating ...");
  const result = await post("/api/generate", simPayload());
  if (!result.ok) { setSimStatus(result.body.error, "error"); return; }
  $("resultsDir").value = result.body.rundir;
  const lines = [
    "written: " + result.body.rundir,
    "script:  " + result.body.script,
    "sketch polygons in the deck: " + result.body.sketch_polygons,
  ];
  if (result.body.warnings.length) lines.push("warnings:\n  " + result.body.warnings.join("\n  "));
  setSimStatus("model generated.\n" + lines.join("\n"), "ok");
}

let pollTimer = null;
function stopPolling() {
  if (pollTimer !== null) { clearInterval(pollTimer); pollTimer = null; }
}

async function startRun() {
  setSimStatus("starting ...");
  const result = await post("/api/run", simPayload());
  if (!result.ok) { setSimStatus(result.body.error, "error"); return; }
  setSimStatus("running " + result.body.rundir + " - progress follows; this can take a long while.", "ok");
  stopPolling();
  pollTimer = setInterval(pollRun, 1500);
}

async function pollRun() {
  const result = await post("/api/run_status", {});
  if (!result.ok) return;
  const snapshot = result.body;
  const progress = snapshot.progress || {};
  if (progress.percent !== null && progress.percent !== undefined) { $("simBar").style.width = progress.percent + "%"; }
  if (progress.timestep) {
    $("simDetail").textContent = "step " + progress.timestep + (progress.energy_db !== null && progress.energy_db !== undefined ? "  energy " + progress.energy_db + " dB" : "") + (progress.elapsed_s ? "  elapsed " + Math.round(progress.elapsed_s) + " s" : "");
  }
  if (snapshot.status === "done") {
    stopPolling();
    $("simBar").style.width = "100%";
    setSimStatus("done.\n" + JSON.stringify(snapshot.summary, null, 1), "ok");
    if (snapshot.rundir) { $("resultsDir").value = snapshot.rundir; }
  }
  if (snapshot.status === "failed") {
    stopPolling();
    setSimStatus("FAILED: " + snapshot.error, "error");
  }
}

// ---------------- results ----------------
async function loadResults() {
  const result = await post("/api/results", { rundir: $("resultsDir").value });
  if (!result.ok) { $("resMetrics").innerHTML = ""; $("resProvenance").textContent = result.body.error; return; }
  const body = result.body;
  const out = $("resMetrics");
  out.innerHTML = "";
  const metrics = [
    ["resonance", body.resonance_ghz.toFixed(4) + " GHz"],
    ["|S11| min", body.worst_db.toFixed(2) + " dB"],
    ["VSWR", body.vswr.toFixed(3)],
    ["points", String(body.points)],
  ];
  if (body.fractional) metrics.push(["-10 dB BW", (body.fractional * 100).toFixed(2) + " %"]);
  metrics.forEach((pair) => {
    const box = document.createElement("div");
    box.className = "kv";
    const k = document.createElement("div"); k.className = "k"; k.textContent = pair[0];
    const v = document.createElement("div"); v.className = "v"; v.textContent = pair[1];
    box.append(k, v);
    out.appendChild(box);
  });
  const provenance = body.provenance || {};
  $("resProvenance").textContent = Object.keys(provenance).map((key) => key + ": " + JSON.stringify(provenance[key])).join("\n");
  $("resFarfield").textContent = body.farfield || "no far-field data in this run (NF2FF was off, or the run predates it)";
  $("resBands").textContent = body.bands.length
    ? body.bands.map((band) => "-10 dB band: " + (band[0] / 1e9).toFixed(4) + " - " + (band[1] / 1e9).toFixed(4) + " GHz  (" + (band[2] / 1e6).toFixed(1) + " MHz)").join("\n")
    : "no -10 dB band in this sweep";
  drawS11(body.curve, body.resonance_ghz);
}

function drawS11(curve, resonanceGhz) {
  const canvas = $("cv2");
  const ctx = canvas.getContext("2d");
  const width = canvas.width, height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  if (!curve || !curve.length) {
    ctx.fillStyle = "#9aa0a9";
    ctx.font = "13px Segoe UI";
    ctx.fillText("Load a run to see the S11 curve.", 24, 34);
    return;
  }
  const padL = 64, padR = 20, padT = 18, padB = 40;
  const xs = curve.map((p) => p[0] / 1e9);
  const ys = curve.map((p) => p[1]);
  const xMin = Math.min.apply(null, xs), xMax = Math.max.apply(null, xs);
  const yMin = Math.min(Math.min.apply(null, ys) - 3, -30);
  const yMax = Math.max(Math.max.apply(null, ys) + 2, -5);
  const X = (x) => padL + (x - xMin) / Math.max(1e-9, xMax - xMin) * (width - padL - padR);
  const Y = (y) => padT + (yMax - y) / Math.max(1e-9, yMax - yMin) * (height - padT - padB);

  ctx.strokeStyle = "rgba(51,54,59,.75)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const x = xMin + (xMax - xMin) * i / 4;
    ctx.beginPath(); ctx.moveTo(X(x), padT); ctx.lineTo(X(x), height - padB); ctx.stroke();
    const y = yMin + (yMax - yMin) * i / 4;
    ctx.beginPath(); ctx.moveTo(padL, Y(y)); ctx.lineTo(width - padR, Y(y)); ctx.stroke();
  }
  ctx.strokeStyle = "#3a3d42";
  ctx.strokeRect(padL, padT, width - padL - padR, height - padT - padB);
  ctx.fillStyle = "#9aa0a9";
  ctx.font = "11px Consolas, monospace";
  for (let i = 0; i <= 4; i++) {
    const x = xMin + (xMax - xMin) * i / 4;
    ctx.fillText(x.toFixed(2), X(x) - 16, height - padB + 14);
    const y = yMin + (yMax - yMin) * i / 4;
    ctx.fillText(y.toFixed(1), 12, Y(y) + 3);
  }
  ctx.fillText("GHz", width - padR - 26, height - padB + 14);
  ctx.fillText("dB", 12, padT + 10);

  ctx.strokeStyle = "rgba(154,160,169,.8)";
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(padL, Y(-10));
  ctx.lineTo(width - padR, Y(-10));
  ctx.stroke();
  ctx.setLineDash([]);

  const gradient = ctx.createLinearGradient(0, padT, 0, height - padB);
  gradient.addColorStop(0, "rgba(76,139,245,.30)");
  gradient.addColorStop(1, "rgba(76,139,245,.02)");
  ctx.beginPath();
  ctx.moveTo(X(xs[0]), Y(ys[0]));
  curve.forEach((point, index) => { if (index > 0) ctx.lineTo(X(point[0] / 1e9), Y(point[1])); });
  ctx.lineTo(X(xs[xs.length - 1]), height - padB);
  ctx.lineTo(X(xs[0]), height - padB);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.strokeStyle = "#4c8bf5";
  ctx.lineWidth = 2;
  ctx.shadowColor = "rgba(76,139,245,.55)";
  ctx.shadowBlur = 8;
  ctx.beginPath();
  curve.forEach((point, index) => {
    const px = X(point[0] / 1e9), py = Y(point[1]);
    if (index === 0) { ctx.moveTo(px, py); } else { ctx.lineTo(px, py); }
  });
  ctx.stroke();
  ctx.shadowBlur = 0;

  if (resonanceGhz) {
    let best = 0;
    curve.forEach((point, index) => { if (Math.abs(point[0] / 1e9 - resonanceGhz) < Math.abs(curve[best][0] / 1e9 - resonanceGhz)) best = index; });
    const mx = X(xs[best]), my = Y(ys[best]);
    ctx.fillStyle = "#ffd166";
    ctx.beginPath(); ctx.arc(mx, my, 4, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#e8e9ec";
    ctx.font = "12px Consolas, monospace";
    const label = resonanceGhz.toFixed(4) + " GHz";
    ctx.fillText(label, Math.min(mx + 8, width - padR - 92), Math.max(my - 8, padT + 12));
  }
}

// ---------------- boot ----------------
renderParams();
renderShapes();
drawCanvas();
drawS11([], null);
checkEngine();
const initialView = (location.hash || "").replace("#", "");
if (["modeling", "simulate", "results"].indexOf(initialView) >= 0) { showView(initialView); }
</script>
</body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    server_version = "OpenAntennaWeb/0.1"

    def _send(self, status, content_type, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        if self.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", INDEX_HTML.encode("utf-8"))
            return
        self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        handler = _ROUTES.get(self.path)
        if handler is None:
            self._send(404, "application/json", b'{"error": "unknown endpoint"}')
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self._send(400, "application/json", b'{"error": "the request body is not JSON"}')
            return
        try:
            result, error = handler(payload)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            result, error = None, "%s: %s" % (type(exc).__name__, exc)
        if error is not None:
            self._send(400, "application/json", json.dumps({"error": error}).encode("utf-8"))
            return
        self._send(200, "application/json", json.dumps(result).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        pass  # a local tool page does not need per-request console noise


class _Server(ThreadingHTTPServer):
    """A server that refuses to share its port.

    On Windows, SO_REUSEADDR lets a second process bind the same port and then split
    incoming connections with the first - a silent double-bind that cost an evening of
    "why is the old page still being served?".  Refusing loudly beats splitting quietly.
    """

    allow_reuse_address = False


def make_server(host: str = "127.0.0.1", port: int = 8077) -> ThreadingHTTPServer:
    """Bind and return the server (tests use port 0 for an ephemeral one)."""
    return _Server((host, int(port)), _Handler)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="openantenna.webui",
        description="local web UI for the modeling half (offline, standard library only)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address (keep it on localhost)")
    parser.add_argument("--port", type=int, default=8077)
    args = parser.parse_args(argv)
    try:
        server = make_server(args.host, args.port)
    except OSError as exc:
        print("cannot bind %s:%d - %s" % (args.host, args.port, exc))
        print("another instance may already be running; stop it, or pass --port.")
        return 1
    host, port = server.server_address[:2]
    print("OpenAntenna local web UI (offline, stdlib only) -> 127.0.0.1:%d" % port)
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
