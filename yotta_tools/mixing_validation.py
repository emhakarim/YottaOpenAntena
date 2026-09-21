"""Y-T3 tool — validate the composite mixing rules against MEASURED data.

This file lives OUTSIDE the ``openantenna`` package on purpose: the work split is
that the reviewer (Yotta) does not change package code.  It reads a CSV of
measured two-phase composites and compares the four mixing rules implemented in
``openantenna.materials.mixing`` with the measured effective permittivity, and
checks whether the measurement falls inside the Wiener bounds.

Usage (from the repository root)::

    python yotta_tools/mixing_validation.py                       # data/composite_measurements.csv
    python yotta_tools/mixing_validation.py path/to/table.csv
    python yotta_tools/mixing_validation.py table.csv --out yotta_tools/mixing_validation_report.md

Expected CSV header (one row per measured composite)::

    matrix_material,eps_matrix,filler_material,eps_filler,vf,freq_hz,eps_eff_measured,tand_measured,source_doi

Only ``eps_matrix, eps_filler, vf, eps_eff_measured`` are required; the rest may
be empty.  Rows with non-numeric or out-of-range values are reported and
skipped -- they are never silently "fixed".

This tool does NOT invent data.  If the CSV is missing it prints the schema and
exits non-zero.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from openantenna.materials import mixing
except Exception as exc:  # pragma: no cover - environment problem, reported to the user
    print(f"ERROR: cannot import openantenna from {REPO_ROOT}: {exc}", file=sys.stderr)
    print("Run this script from the repository root, or set PYTHONPATH to it.", file=sys.stderr)
    raise SystemExit(2)

REQUIRED = ("eps_matrix", "eps_filler", "vf", "eps_eff_measured")
MODELS = ("lichtenecker", "maxwell_garnett", "bruggeman")


def _num(row: dict, key: str) -> float:
    value = (row.get(key) or "").strip()
    if value == "":
        raise ValueError(f"{key} is empty")
    return float(value)


def load_rows(path: Path) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    problems: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for index, raw in enumerate(csv.DictReader(handle), start=2):
            label = raw.get("matrix_material") or f"row {index}"
            try:
                rec = {
                    "label": f"{label}/{raw.get('filler_material') or '?'}",
                    "eps_matrix": _num(raw, "eps_matrix"),
                    "eps_filler": _num(raw, "eps_filler"),
                    "vf": _num(raw, "vf"),
                    "measured": _num(raw, "eps_eff_measured"),
                    "freq_hz": (raw.get("freq_hz") or "").strip(),
                    "source": (raw.get("source_doi") or "").strip(),
                }
            except Exception as exc:
                problems.append(f"line {index}: {exc}")
                continue
            if not 0.0 <= rec["vf"] <= 1.0:
                problems.append(f"line {index}: vf={rec['vf']} outside [0, 1]")
                continue
            if rec["eps_matrix"] <= 0 or rec["eps_filler"] <= 0 or rec["measured"] <= 0:
                problems.append(f"line {index}: permittivities must be > 0")
                continue
            rows.append(rec)
    return rows, problems


def analyse(rows: list[dict]) -> tuple[list[dict], list[str], str]:
    results: list[dict] = []
    notes: list[str] = []
    for rec in rows:
        em, ef, vf = rec["eps_matrix"], rec["eps_filler"], rec["vf"]
        models = {name: float(getattr(mixing, name)(em, ef, vf)) for name in MODELS}
        lo, hi = (float(v) for v in mixing.wiener_bounds(em, ef, vf))
        inside = lo - 1e-9 <= rec["measured"] <= hi + 1e-9
        errors = {name: (value - rec["measured"]) / rec["measured"] * 100.0
                  for name, value in models.items()}
        best = min(errors, key=lambda k: abs(errors[k]))
        results.append({**rec, **models, "wiener_lower": lo, "wiener_upper": hi,
                        "inside_wiener": inside, "errors_pct": errors, "best_model": best})
        if not inside:
            notes.append(
                f"{rec['label']} (vf={vf:g}, f={rec['freq_hz'] or '?'}): measured "
                f"{rec['measured']:.4g} is OUTSIDE the Wiener bounds "
                f"[{lo:.4g}, {hi:.4g}] - check the phase assignment (host vs filler) "
                "or a third phase (voids)."
            )

    summary = "no rows"
    if results:
        means = {name: sum(abs(r["errors_pct"][name]) for r in results) / len(results)
                 for name in MODELS}
        worst = max(means, key=means.get)
        lines = [f"n = {len(results)} measured composites.",
                 "Mean |error| vs measurement: " + ", ".join(
                     f"{k} {v:.1f} %" for k, v in sorted(means.items(), key=lambda kv: kv[1])),
                 f"Best on average: {min(means, key=means.get)}; worst: {worst}."]
        if all(r["inside_wiener"] for r in results):
            lines.append("All measurements fall inside the Wiener bounds (consistent with a "
                         "two-phase homogenised description).")
        summary = "\n".join(lines)
    return results, notes, summary


def render(results: list[dict], problems: list[str], notes: list[str], summary: str) -> str:
    out = ["# Mixing-rule validation against measured composites (Y-T3)", "",
           "_Generated by `yotta_tools/mixing_validation.py`. Measured values come from the "
           "CSV supplied by the project; nothing here is estimated from memory._", ""]
    if results:
        out += ["| composite | vf | f [Hz] | measured | Wiener lo-hi | MG | Bruggeman | Lichtenecker | inside | best |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for r in results:
            out.append(
                f"| {r['label']} | {r['vf']:.3g} | {r['freq_hz'] or '-'} | {r['measured']:.4g} "
                f"| {r['wiener_lower']:.4g}-{r['wiener_upper']:.4g} "
                f"| {r['maxwell_garnett']:.4g} | {r['bruggeman']:.4g} | {r['lichtenecker']:.4g} "
                f"| {'yes' if r['inside_wiener'] else '**NO**'} | {r['best_model']} |")
        out += ["", "## Error vs measurement [%]", "",
                "| composite | Maxwell-Garnett | Bruggeman | Lichtenecker |", "|---|---|---|---|"]
        for r in results:
            e = r["errors_pct"]
            out.append(f"| {r['label']} | {e['maxwell_garnett']:+.1f} | {e['bruggeman']:+.1f} "
                       f"| {e['lichtenecker']:+.1f} |")
    out += ["", "## Summary", "", summary]
    if notes:
        out += ["", "## Outside the Wiener bounds", ""] + [f"* {n}" for n in notes]
    if problems:
        out += ["", "## Skipped rows", ""] + [f"* {p}" for p in problems]
    out += ["", "## Caveats", "",
            "* The mixing rules are quasi-static effective-medium estimates; agreement or "
            "disagreement here tests the *implementation*, not the physics of a given sample.",
            "* Fillers with high permittivity concentrate the field, so loss (tan delta) is not "
            "expected to follow the same ranking as the real permittivity.",
            "* A measurement outside the Wiener bounds is a signal (phase inversion, voids, "
            "percolation), not a bug - investigate before trusting the row.", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare measured composites with the mixing rules.")
    parser.add_argument("csv", nargs="?", default="data/composite_measurements.csv")
    parser.add_argument("--out", default="yotta_tools/mixing_validation_report.md")
    args = parser.parse_args(argv)

    path = Path(args.csv)
    if not path.is_file():
        print(f"CSV not found: {path}", file=sys.stderr)
        print("Required header:\n  matrix_material,eps_matrix,filler_material,eps_filler,vf,"
              "freq_hz,eps_eff_measured,tand_measured,source_doi", file=sys.stderr)
        return 1

    rows, problems = load_rows(path)
    if not rows:
        print("No usable rows in the CSV.", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    results, notes, summary = analyse(rows)
    report = render(results, problems, notes, summary)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"\nreport written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
