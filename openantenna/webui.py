"""Local web UI (prototype): the modeling half, offline and stdlib only.

Run:  python -m openantenna.webui   ->  127.0.0.1:8077

The desktop GUI's reasons were "offline, solver local, no server".  A server bound to
127.0.0.1 keeps the first two and trades the third for a look we can style with CSS; every
asset the page loads comes from this process - nothing external, ever.  The page covers the
Modeling tab's core (parameters, blocks, DXF export, solver-grid preview, patch synthesis);
the solver tabs are the next step (progress via polling).

The API reuses the same package functions the desktop tab calls, so the two front ends
cannot drift: /api/resolve, /api/dxf, /api/grid, /api/patch.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .geometry.cad import dxf_text, rasterise_segments, stroke_fraction
from .geometry.params import ParameterError, ParameterTable, evaluate_expression
from .geometry.sketch import shapes_to_polygons


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


_ROUTES = {
    "/api/resolve": _resolve,
    "/api/dxf": _dxf,
    "/api/grid": _grid,
    "/api/patch": _patch,
}

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenAntenna Studio - local web UI</title>
<style>
  :root {
    --bg: #1e1f22; --panel: #2b2d31; --panel2: #313338; --border: #3a3d42;
    --text: #e6e6e6; --muted: #a8adb5; --accent: #4c8bf5; --danger: #ff7b72;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 "Segoe UI", Inter, system-ui, sans-serif; }
  header { padding: 18px 22px 6px; }
  h1 { font-size: 18px; margin: 0 0 2px; font-weight: 600; }
  .sub { color: var(--muted); font-size: 12.5px; }
  main { display: grid; grid-template-columns: 380px 1fr; gap: 14px; padding: 14px 22px 26px; align-items: start; }
  @media (max-width: 900px) { main { grid-template-columns: 1fr; } }
  section { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; margin-bottom: 14px; }
  h2 { font-size: 12.5px; margin: 0 0 8px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }
  label { color: var(--muted); font-size: 12px; }
  input, select { background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 7px; padding: 5px 8px; font: inherit; font-size: 13px; width: 100%; }
  input:focus, select:focus { outline: none; border-color: var(--accent); }
  input.num, .num { font-family: Consolas, "Cascadia Mono", monospace; font-variant-numeric: tabular-nums; }
  button { background: var(--panel2); color: var(--text); border: 1px solid var(--border); border-radius: 7px; padding: 6px 12px; font: inherit; font-size: 13px; cursor: pointer; }
  button:hover { border-color: var(--accent); }
  button.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
  button.primary:hover { background: #5d97f7; }
  button.mini { padding: 2px 8px; font-size: 12px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 4px 6px; font-size: 12.5px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; }
  td.err { color: var(--danger); }
  .row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
  .row > label { white-space: nowrap; }
  .fields { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 8px; }
  .fields label { font-size: 11px; }
  #canvasWrap { background: #232428; border: 1px solid var(--border); border-radius: 10px; padding: 8px; }
  canvas { width: 100%; height: 420px; display: block; border-radius: 6px; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
  #status { min-height: 20px; color: var(--muted); font-size: 12.5px; margin-top: 8px; white-space: pre-wrap; }
  #status.error { color: var(--danger); }
  .result { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin-top: 8px; }
  .kv { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 7px 9px; }
  .kv .k { color: var(--muted); font-size: 11.5px; }
  .kv .v { font-family: Consolas, monospace; font-size: 14px; }
  footer { color: var(--muted); font-size: 12px; padding: 0 22px 20px; }
</style>
</head>
<body>
<header>
  <h1>OpenAntenna Studio - local web UI <span style="color:var(--muted);font-weight:400;font-size:13px">(prototype)</span></h1>
  <div class="sub">Offline and stdlib-only: this page and its data are served by your own Python process on 127.0.0.1, using the same core functions as the desktop tab. Nothing external is loaded.</div>
</header>
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
      <div class="sub">Corners and thickness accept parameter expressions; corners are evaluated when the block is added, the thickness stays a definition.</div>
    </section>
    <section>
      <h2>Shapes</h2>
      <table><thead><tr><th>shape</th><th>vertices</th><th>bounds (mm)</th><th>thickness</th><th></th></tr></thead><tbody id="shapesBody"></tbody></table>
      <div class="actions"><button onclick="clearShapes()">Clear all</button></div>
      <div class="sub">Closed shapes ride into generated decks via the desktop tab's include switch; here they export as DXF and preview on the solver grid.</div>
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
      <div id="status"></div>
    </section>
  </div>
</main>
<footer>offline - served by your own python - shapes in millimetres - DXF carries no units by convention</footer>
<script>
const state = { parameters: [["L", "30"], ["W", "20"], ["h_sub", "1.6"]], shapes: [], grid: null };
const $ = (id) => document.getElementById(id);

function setStatus(text, isError) {
  const el = $("status");
  el.textContent = text || "";
  el.className = isError ? "error" : "";
}

async function post(path, payload) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const body = await response.json();
  return { ok: response.ok, body: body };
}

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

async function addBlock() {
  const corners = [$("bx0").value, $("by0").value, $("bx1").value, $("by1").value].map((s) => s.trim() || "0");
  const result = await post("/api/resolve", { parameters: state.parameters, expressions: corners });
  if (!result.ok) { setStatus(result.body.error, true); return; }
  const problems = result.body.evaluate_errors.filter(Boolean);
  if (problems.length) { setStatus("could not add the block: " + problems.join("; "), true); return; }
  const x0 = result.body.evaluated[0], y0 = result.body.evaluated[1], x1 = result.body.evaluated[2], y1 = result.body.evaluated[3];
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
  ctx.strokeStyle = "#4c8bf5";
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
    ctx.stroke();
  });

  if (!state.shapes.length && !state.grid) {
    ctx.fillStyle = "#a8adb5";
    ctx.font = "13px Segoe UI";
    ctx.fillText("No shapes yet - add a block on the left.", 24, 32);
  }
  ctx.fillStyle = "#a8adb5";
  ctx.font = "12px Consolas, monospace";
  ctx.fillText("millimetres", width - 90, height - 8);
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

renderParams();
renderShapes();
drawCanvas();
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


def make_server(host: str = "127.0.0.1", port: int = 8077) -> ThreadingHTTPServer:
    """Bind and return the server (tests use port 0 for an ephemeral one)."""
    return ThreadingHTTPServer((host, int(port)), _Handler)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="openantenna.webui",
        description="local web UI for the modeling half (offline, standard library only)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address (keep it on localhost)")
    parser.add_argument("--port", type=int, default=8077)
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port)
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
