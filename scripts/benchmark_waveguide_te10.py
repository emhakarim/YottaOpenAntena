"""Benchmark #2 — rectangular waveguide, TE10 cutoff (exact analytic reference).

Rewritten after two failed attempts with lumped ports (openEMS: "Lumped Element snapping
failed! Dimension is: 0", S21 = NaN).  A hollow waveguide needs a **waveguide port**, and
the official openEMS tutorial `python/Tutorials/Rect_Waveguide.py` shows exactly how:

    FDTD.SetBoundaryCond([0, 0, 0, 0, 3, 3])          # PEC on x/y, PML on z
    FDTD.AddRectWaveGuidePort(nr, start, stop, 'z', a, b, 'TE10', excite)

No metal boxes are needed for the walls - the PEC boundary condition is the wall.

Why this benchmark: the cutoff frequency of an air-filled rectangular waveguide is
exactly `f_c = c / (2a)`, so the whole pipeline (mesh -> field -> ports -> S-params) is
tested against a number nobody can argue about.

    a = 100 mm  ->  f_c = 1498.96 MHz

Acceptance criteria (docs/benchmarks.md §5):
  * S21 at 0.9 f_c <= -30 dB (evanescent),
  * S21 at 1.3 f_c >= -1 dB (propagating),
  * the -3 dB edge within 1 % of f_c,
  * the run reports its timestep count and whether EndCriteria was met.

Usage (needs openEMS; set OPENEMS_ROOT):

    python scripts/benchmark_waveguide_te10.py [out_dir]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

if os.name == "nt":
    _root = os.environ.get("OPENEMS_ROOT")
    if _root and os.path.isdir(_root):
        os.add_dll_directory(_root)
        os.environ["PATH"] = _root + os.pathsep + os.environ.get("PATH", "")
    else:
        sys.exit("ERROR: OPENEMS_ROOT must point at the folder holding openEMS.exe / CSXCAD.dll")

from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import C0

A = 100e-3            # broad dimension (x) -> f_c = C0 / (2a)
B = 50e-3             # narrow dimension (y)
LENGTH = 200e-3       # guide length (z)
F_C = C0 / (2.0 * A)
F_START, F_STOP = 1.2e9, 3.0e9
F_0 = 0.5 * (F_START + F_STOP)
N_FREQ = 201
MAX_TS = 60000
END_CRITERIA = 1e-3


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runs") / "benchmark_te10"
    out_dir.mkdir(parents=True, exist_ok=True)

    lambda0 = C0 / F_0
    mesh_res = lambda0 / 30.0

    FDTD = openEMS(NrTS=MAX_TS, EndCriteria=END_CRITERIA)
    FDTD.SetGaussExcite(F_0, 0.5 * (F_STOP - F_START))
    # PEC on x and y (the guide walls), PML on z (the two ends)
    FDTD.SetBoundaryCond([0, 0, 0, 0, 3, 3])

    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(1.0)

    mesh.AddLine("x", [0, A])
    mesh.AddLine("y", [0, B])
    mesh.AddLine("z", [0, LENGTH])

    ports = []
    start = [0, 0, 10 * mesh_res]
    stop = [A, B, 15 * mesh_res]
    mesh.AddLine("z", [start[2], stop[2]])
    ports.append(FDTD.AddRectWaveGuidePort(0, start, stop, "z", A, B, "TE10", 1))

    start = [0, 0, LENGTH - 10 * mesh_res]
    stop = [A, B, LENGTH - 15 * mesh_res]
    mesh.AddLine("z", [start[2], stop[2]])
    ports.append(FDTD.AddRectWaveGuidePort(1, start, stop, "z", A, B, "TE10"))

    mesh.SmoothMeshLines("all", mesh_res, ratio=1.4)

    print(f"TE10 cutoff (analytic): f_c = c/(2a) = {F_C/1e9:.4f} GHz  (a = {A*1e3:.1f} mm)")
    print(f"mesh: {mesh_res*1e3:.2f} mm (lambda0/30 at {F_0/1e9:.2f} GHz), max {MAX_TS} steps, EndCriteria {END_CRITERIA:g}")

    sim_path = str(out_dir / "openems_run")
    FDTD.Run(sim_path, cleanup=True)

    freqs = np.linspace(F_START, F_STOP, N_FREQ)
    for port in ports:
        port.CalcPort(sim_path, freqs)
    s11 = ports[0].uf_ref / ports[0].uf_inc
    s21 = ports[1].uf_ref / ports[0].uf_inc
    s21_db = 20.0 * np.log10(np.maximum(np.abs(s21), 1e-12))

    csv_path = out_dir / "s21.csv"
    with csv_path.open("w", encoding="utf-8") as handle:
        handle.write("freq_hz,s21_re,s21_im,s21_db\n")
        for f, value, db in zip(freqs, s21, s21_db):
            handle.write(f"{f:.6e},{value.real:.9e},{value.imag:.9e},{db:.6f}\n")

    edge = None
    for i in range(1, len(s21_db)):
        if s21_db[i - 1] < -3.0 <= s21_db[i]:
            span = s21_db[i] - s21_db[i - 1]
            edge = float(freqs[i - 1] + (-3.0 - s21_db[i - 1]) * (freqs[i] - freqs[i - 1]) / span)
            break

    at_0p9 = float(np.interp(0.9 * F_C, freqs, s21_db))
    at_1p3 = float(np.interp(1.3 * F_C, freqs, s21_db))
    # convergence: openEMS writes the taken timesteps into the run summary
    timesteps = None
    summary_path = Path(sim_path) / "run_summary.json"
    if summary_path.is_file():
        try:
            timesteps = json.loads(summary_path.read_text(encoding="utf-8")).get("nrTS")
        except Exception:
            timesteps = None

    verdict = {
        "analytic_cutoff_hz": F_C,
        "measured_3db_edge_hz": edge,
        "edge_error_percent": None if edge is None else (edge / F_C - 1.0) * 100.0,
        "s21_at_0p9fc_db": at_0p9,
        "s21_at_1p3fc_db": at_1p3,
        "passes": bool(
            edge is not None
            and abs(edge / F_C - 1.0) <= 0.01
            and at_0p9 <= -30.0
            and at_1p3 >= -1.0
        ),
        "timesteps": timesteps,
        "max_timesteps": MAX_TS,
        "end_criteria": END_CRITERIA,
        "note": "a run that reached max_timesteps without meeting EndCriteria is not converged",
    }
    (out_dir / "benchmark_te10_summary.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict, indent=2))
    print(f"wrote {csv_path} and benchmark_te10_summary.json")
    return 0 if verdict["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
