"""Reference table for stored runs — every run judged against ONE kind of reference.

Why this tool exists (Yotta item Y-1): the generalisation table in the project
notes compared three geometries against the *cavity model* but the tutorial
geometry against a *measured* value.  Mixing reference types makes a "constant
bias" conclusion look stronger than the data supports.  This tool reads each run's
own ``project.json``, recomputes the analytic predictions for **that exact
geometry**, and prints one consistent table (cavity as the reference), so the
question "is the bias constant or geometry-dependent?" can be answered honestly.

No solver, no network: it works on stored run directories.

Usage (from the repository root)::

    python yotta_tools/reference_table.py                     # scans runs/
    python yotta_tools/reference_table.py runs/a runs/b       # explicit run dirs
    python yotta_tools/reference_table.py --out table.md --json table.json

A run directory is any folder containing ``project.json``; ``s11.csv`` and
``run_manifest.json`` are optional (without them the measured and convergence
columns stay empty instead of being guessed).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from openantenna.geometry.patch import resonant_frequency, resonant_frequency_cavity
from openantenna.materials.library import get_material
from openantenna.postproc.sparams import S11Trace

#: if the spread of delta-vs-cavity exceeds this (percentage points), the bias is
#: treated as geometry-dependent rather than a single systematic factor
SPREAD_THRESHOLD_PP = 1.0


def _dielectric_layer(document: dict) -> dict | None:
    layers = document.get("substrate", {}).get("layers", [])
    for layer in layers:
        if layer.get("role", "dielectric") == "dielectric":
            return layer
    return layers[0] if layers else None


def load_run(run_dir: Path) -> dict | None:
    """Read one run directory; returns None when it is not a project directory."""
    project_file = run_dir / "project.json"
    if not project_file.is_file():
        return None
    document = json.loads(project_file.read_text(encoding="utf-8"))
    layer = _dielectric_layer(document)
    patch = document.get("patch", {})
    if layer is None or not patch.get("width_m") or not patch.get("length_m"):
        return None

    material = get_material(layer["material"])
    epsilon_r = float(material.epsilon_r)
    height_m = float(layer["thickness_m"])
    width_m = float(patch["width_m"])
    length_m = float(patch["length_m"])

    record: dict = {
        "run": run_dir.name,
        "material": material.name,
        "epsilon_r": epsilon_r,
        "height_m": height_m,
        "width_m": width_m,
        "length_m": length_m,
        "cavity_hz": resonant_frequency_cavity(epsilon_r, height_m, width_m, length_m),
        "tl_hz": resonant_frequency(epsilon_r, height_m, width_m, length_m),
    }

    csv_path = run_dir / "s11.csv"
    if csv_path.is_file():
        trace = S11Trace.from_csv(csv_path)
        index = trace.worst_match_index()
        record.update(
            {
                "measured_hz": trace.frequencies_hz[index],
                "match_db": trace.db()[index],
                "vswr": trace.vswr()[index],
                "fractional_bw": trace.fractional_bandwidth(-10.0),
            }
        )
        record["delta_vs_cavity_pct"] = (record["measured_hz"] / record["cavity_hz"] - 1.0) * 100.0
        record["delta_vs_tl_pct"] = (record["measured_hz"] / record["tl_hz"] - 1.0) * 100.0

    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mesh = manifest.get("mesh", {})
        record["converged"] = mesh.get("converged", manifest.get("converged"))
        record["port_refine"] = mesh.get("port_refine")
        record["metal_edge_snapping"] = manifest.get("metal_edge_snapping")
    return record


def collect(paths: list[Path]) -> list[dict]:
    records: list[dict] = []
    for path in paths:
        if path.is_dir() and (path / "project.json").is_file():
            candidates = [path]
        else:
            candidates = sorted(p for p in path.iterdir() if p.is_dir()) if path.is_dir() else []
        for candidate in candidates:
            try:
                record = load_run(candidate)
            except Exception as exc:  # a broken run is a row, not a crash
                records.append(
                    {
                        "run": candidate.name,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            if record:
                records.append(record)
    return records


def verdict(records: list[dict]) -> str:
    deltas = [r["delta_vs_cavity_pct"] for r in records if "delta_vs_cavity_pct" in r]
    if len(deltas) < 2:
        return "Belum cukup run dengan s11.csv untuk menilai apakah bias konstan."
    spread = max(deltas) - min(deltas)
    mean = statistics.fmean(deltas)
    if spread > SPREAD_THRESHOLD_PP:
        return (
            f"Bias vs cavity BERGERAK antar-geometri (spread {spread:.2f} pp > {SPREAD_THRESHOLD_PP} pp; "
            f"rata-rata {mean:+.2f} %). Kalibrasi satu faktor belum didukung data."
        )
    return (
        f"Bias vs cavity relatif KONSTAN (spread {spread:.2f} pp <= {SPREAD_THRESHOLD_PP} pp; "
        f"rata-rata {mean:+.2f} %). Faktor koreksi tunggal layak dipertimbangkan."
    )


def render_markdown(records: list[dict], summary: str) -> str:
    lines = [
        "# Reference table (single reference: cavity model)",
        "",
        "_Generated by `yotta_tools/reference_table.py`. Predictions are recomputed from each "
        "run's own `project.json`; no value here is taken from memory._",
        "",
        "| run | eps_r | h [mm] | W x L [mm] | cavity [GHz] | TL [GHz] | measured [GHz] | \\|S11\\| [dB] | VSWR | delta vs cavity | delta vs TL | converged |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        def g(key: str, fmt: str = "-") -> str:
            value = r.get(key)
            return fmt.format(value) if value is not None else "-"

        lines.append(
            "| {run} | {er} | {h} | {wl} | {cav} | {tl} | {meas} | {db} | {vswr} "
            "| {dc} | {dt} | {conv} |".format(
                run=r["run"],
                er=f"{r['epsilon_r']:g}",
                h=f"{r['height_m'] * 1e3:.3f}",
                wl=f"{r['width_m'] * 1e3:.3f} x {r['length_m'] * 1e3:.3f}",
                cav=f"{r['cavity_hz'] / 1e9:.4f}",
                tl=f"{r['tl_hz'] / 1e9:.4f}",
                meas=g("measured_hz", "{:.4f}") if "measured_hz" not in r else f"{r['measured_hz'] / 1e9:.4f}",
                db=g("match_db", "{:.2f}"),
                vswr=g("vswr", "{:.3f}"),
                dc=g("delta_vs_cavity_pct", "{:+.2f} %"),
                dt=g("delta_vs_tl_pct", "{:+.2f} %"),
                conv=g("converged"),
            )
        )
    lines += ["", "## Verdict", "", summary, ""]
    lines += [
        "## How to read this",
        "",
        "* Every measured value is compared against **one** reference type (cavity), so rows are comparable.",
        "* `delta vs TL` is kept for information: it shows how far the transmission-line synthesis is from the solver.",
        "* A `converged: False` or missing value means the run cannot support a resonance claim yet.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare stored runs against a single analytic reference.")
    parser.add_argument("paths", nargs="*", default=["runs"], help="run directories (default: runs/)")
    parser.add_argument("--out", default="yotta_tools/reference_table.md")
    parser.add_argument("--json", dest="json_out", default="yotta_tools/reference_table.json")
    args = parser.parse_args(argv)

    paths = [Path(p) for p in (args.paths or ["runs"])]
    existing = [p for p in paths if p.exists()]
    if not existing:
        print(f"no run directories found (looked for: {', '.join(str(p) for p in paths)})", file=sys.stderr)
        return 1

    records = collect(existing)
    if not records:
        print("no project.json found in the given paths", file=sys.stderr)
        return 1

    summary = verdict(records)
    markdown = render_markdown(records, summary)
    Path(args.out).write_text(markdown, encoding="utf-8")
    Path(args.json_out).write_text(json.dumps({"runs": records, "verdict": summary}, indent=2), encoding="utf-8")
    print(markdown)
    print(f"\nwritten: {args.out} and {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
