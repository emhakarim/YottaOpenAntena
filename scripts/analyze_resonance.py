"""Distinguish the patch resonance from the |S11| minimum.

Review item N-04 warned that the minimum of |S11| is not necessarily the natural
resonance of the patch: the feed and its reactance contribute.  This script reads
S11 traces that already exist and reports, per run:

* the frequency of minimum |S11| (what the tuning loop chased),
* the frequency of maximum Re(Zin) (the classic series-resonance indicator),
* the first frequency where Im(Zin) crosses zero (either direction - for a
  series resonator X passes through zero going from positive to negative as the
  frequency rises through resonance, so the direction is reported, not assumed),
* the analytic predictions for the geometry recorded in that run's project.json.

A machine-readable summary is written to ``runs/resonance_analysis.json`` so the
numbers quoted in ``docs/verification.md`` are archived alongside the runs that
produced them (review item S-4).  The geometry comes from each run's own
``project.json`` rather than from constants (review item S-2), so this also works
for the tutorial geometry.

Usage:
    python scripts/analyze_resonance.py [run_dir ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openantenna.geometry.patch import resonant_frequency, resonant_frequency_cavity
from openantenna.materials.library import get_material
from openantenna.model.project import Project
from openantenna.postproc.sparams import S11Trace

DEFAULT_RUNS = [
    "patch_ptfe_v4",
    "gp_0p25",
    "gp_0p50",
    "gp_1p00",
    "tune_it3",
    "anchor_generator_on_tutorial",
]


def crossing_zero(freqs, values) -> tuple[float | None, str]:
    """First sampled zero crossing, with its direction reported explicitly."""
    for i in range(1, len(values)):
        a, b = values[i - 1], values[i]
        if a == 0.0:
            return freqs[i - 1], "exact"
        if a < 0.0 < b:
            direction = "capacitive->inductive"
        elif a > 0.0 > b:
            direction = "inductive->capacitive"
        else:
            continue
        span = b - a
        if span == 0:
            return freqs[i], direction
        return freqs[i - 1] + (0.0 - a) * (freqs[i] - freqs[i - 1]) / span, direction
    return None, "none"


def geometry_from(run_dir: Path) -> dict | None:
    """Read the run's own project.json and the material it names."""
    project_file = run_dir / "project.json"
    if not project_file.exists():
        return None
    try:
        project = Project.from_json(project_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    layer = (project.substrate.dielectric_layers() or project.substrate.layers)[0]
    try:
        epsilon_r = get_material(layer.material).epsilon_r
    except KeyError:
        epsilon_r = None
    return {
        "material": layer.material,
        "epsilon_r": epsilon_r,
        "height_m": layer.thickness_m,
        "width_m": project.patch.width_m,
        "length_m": project.patch.length_m,
        "center_hz": project.sweep.center_hz,
    }


def analyse(run_dir: Path) -> dict | None:
    csv_path = run_dir / "s11.csv"
    if not csv_path.exists():
        print(f"{run_dir.name:<34} no s11.csv")
        return None
    trace = S11Trace.from_csv(csv_path)
    freqs = trace.frequencies_hz
    zin = trace.impedance_ohm()

    min_index = trace.worst_match_index()
    max_r_index = max(range(len(zin)), key=lambda i: zin[i].real)
    x_zero, x_direction = crossing_zero(freqs, [z.imag for z in zin])

    record = {
        "run": run_dir.name,
        "s11_min_hz": freqs[min_index],
        "s11_min_db": trace.db()[min_index],
        "vswr_at_min": trace.vswr()[min_index],
        "max_re_z_hz": freqs[max_r_index],
        "max_re_z_ohm": zin[max_r_index].real,
        "im_z_zero_hz": x_zero,
        "im_z_zero_direction": x_direction,
        "r_at_s11_min_ohm": zin[min_index].real,
        "x_at_s11_min_ohm": zin[min_index].imag,
    }

    geometry = geometry_from(run_dir)
    if geometry and geometry["epsilon_r"] and geometry["width_m"] and geometry["length_m"]:
        record["geometry"] = geometry
        record["analytic_transmission_line_hz"] = resonant_frequency(
            geometry["epsilon_r"], geometry["height_m"], geometry["width_m"], geometry["length_m"]
        )
        record["analytic_cavity_hz"] = resonant_frequency_cavity(
            geometry["epsilon_r"], geometry["height_m"], geometry["width_m"], geometry["length_m"]
        )

    print(
        f"{run_dir.name:<34} |S11|min {record['s11_min_hz']/1e9:.4f} GHz | "
        f"maxReZ {record['max_re_z_hz']/1e9:.4f} GHz | ImZ=0 "
        f"{('%.4f GHz' % (x_zero/1e9)) if x_zero else 'none'} ({x_direction})"
    )
    if "analytic_cavity_hz" in record:
        print(
            f"{'':<34} analytic: TL {record['analytic_transmission_line_hz']/1e9:.4f} GHz, "
            f"cavity {record['analytic_cavity_hz']/1e9:.4f} GHz"
        )
    return record


def main() -> int:
    names = sys.argv[1:] or DEFAULT_RUNS
    runs_dir = ROOT / "runs"
    records = []
    for name in names:
        record = analyse(runs_dir / name)
        if record:
            records.append(record)
        print()
    out = runs_dir / "resonance_analysis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "runs": records,
                "note": (
                    "If max Re(Z) coincides with the |S11| minimum and Im(Z) crosses zero "
                    "next to it, the minimum is the series resonance of the patch, not a "
                    "feed artefact."
                ),
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"summary written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
