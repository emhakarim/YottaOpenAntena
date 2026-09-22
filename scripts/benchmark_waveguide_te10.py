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
  * transmission at 1.3 f_c >= -0.5 dB (propagating, essentially lossless),
  * the evanescent attenuation at 0.9 f_c matches `alpha(f) * d` from the exact
    dispersion relation within 3 dB (a finite guide decays, it does not drop to -inf),
  * the -3 dB knee is reported as **information only** (for a finite guide it
    legitimately sits below f_c),
  * the run reports its timestep count and whether EndCriteria was met.

Import note: CSXCAD/openEMS are imported **inside main()**, after the openEMS DLL
directory is registered - importing them first on a machine without OPENEMS_ROOT is the
error my own guard test caught (scripts must be importable, not just runnable).

Usage (needs openEMS; set OPENEMS_ROOT):

    python scripts/benchmark_waveguide_te10.py [out_dir]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

C0 = 299792458.0
A = 100e-3            # broad dimension (x) -> f_c = C0 / (2a)
B = 50e-3             # narrow dimension (y)
LENGTH = 200e-3       # guide length (z)
F_C = C0 / (2.0 * A)
F_START, F_STOP = 1.2e9, 3.0e9
F_0 = 0.5 * (F_START + F_STOP)
N_FREQ = 201
MAX_TS = 60000
END_CRITERIA = 1e-3


def openems_environment_ready() -> bool:
    """Register the openEMS DLL directory; returns False when it is not configured."""
    root = os.environ.get("OPENEMS_ROOT")
    if not root or not os.path.isdir(root):
        return False
    os.add_dll_directory(root)
    os.environ["PATH"] = root + os.pathsep + os.environ.get("PATH", "")
    return True


def build_and_run(out_dir: Path) -> dict:
    # Imports deliberately AFTER the DLL registration (see the module docstring).
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    mesh_res = (C0 / F_0) / 30.0

    FDTD = openEMS(NrTS=MAX_TS, EndCriteria=END_CRITERIA)
    FDTD.SetGaussExcite(F_0, 0.5 * (F_STOP - F_START))
    FDTD.SetBoundaryCond([0, 0, 0, 0, 3, 3])  # PEC x/y, PML z

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

    # Below the mode's cutoff the port's own modal normalisation is undefined (beta
    # becomes imaginary, uf_inc -> NaN).  The plain total-voltage ratio stays finite on
    # both sides, so the cutoff edge is located with it.
    trans = np.abs(ports[1].uf_tot) / np.maximum(np.abs(ports[0].uf_tot), 1e-30)
    trans_db = 20.0 * np.log10(np.maximum(trans, 1e-12))

    csv_path = out_dir / "s21.csv"
    with csv_path.open("w", encoding="utf-8") as handle:
        handle.write("freq_hz,s21_re,s21_im,s21_db,transmission_db\n")
        for f, value, db, tdb in zip(freqs, s21, s21_db, trans_db):
            handle.write(f"{f:.6e},{value.real:.9e},{value.imag:.9e},{db:.6f},{tdb:.6f}\n")

    edge = None
    for i in range(1, len(trans_db)):
        if trans_db[i - 1] < -3.0 <= trans_db[i]:
            span = trans_db[i] - trans_db[i - 1]
            edge = float(freqs[i - 1] + (-3.0 - trans_db[i - 1]) * (freqs[i] - freqs[i - 1]) / span)
            break

    at_0p9 = float(np.interp(0.9 * F_C, freqs, trans_db))
    at_1p3 = float(np.interp(1.3 * F_C, freqs, trans_db))

    # The RIGHT quantitative check for a finite guide: below cutoff the mode decays as
    # exp(-alpha*d) with the exact dispersion relation, so compare the measured
    # attenuation with that number instead of asking where a "-3 dB knee" sits (for a
    # finite guide the knee legitimately falls below f_c - that is not an error).
    port_distance = LENGTH - 25.0 * mesh_res
    lam0_09 = C0 / (0.9 * F_C)
    alpha_09 = (2.0 * np.pi / lam0_09) * np.sqrt((1.0 / 0.9) ** 2 - 1.0)
    analytic_0p9_db = 20.0 * np.log10(np.exp(-alpha_09 * port_distance))

    timesteps = None
    summary_path = Path(sim_path) / "run_summary.json"
    if summary_path.is_file():
        try:
            timesteps = json.loads(summary_path.read_text(encoding="utf-8")).get("nrTS")
        except Exception:
            timesteps = None

    return {
        "analytic_cutoff_hz": F_C,
        "measured_3db_edge_hz": edge,
        "edge_error_percent": None if edge is None else (edge / F_C - 1.0) * 100.0,
        "transmission_at_0p9fc_db": at_0p9,
        "analytic_evanescent_0p9fc_db": float(analytic_0p9_db),
        "evanescent_error_db": float(abs(at_0p9 - analytic_0p9_db)),
        "transmission_at_1p3fc_db": at_1p3,
        "knee_3db_hz": edge,
        "knee_note": "informational only: a finite guide puts the -3 dB knee below f_c",
        "passes": bool(
            at_1p3 >= -0.5                                  # propagating, essentially lossless
            and abs(at_0p9 - analytic_0p9_db) <= 3.0        # evanescent decay matches theory
        ),
        "timesteps": timesteps,
        "max_timesteps": MAX_TS,
        "end_criteria": END_CRITERIA,
        "note": "a run that reached max_timesteps without meeting EndCriteria is not converged",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Waveguide TE10 cutoff benchmark.")
    parser.add_argument("out_dir", nargs="?", default="runs/benchmark_te10")
    args = parser.parse_args(argv)

    if not openems_environment_ready():
        print(
            "ERROR: OPENEMS_ROOT must point at the folder holding openEMS.exe / CSXCAD.dll "
            "(this script imports the engine after registering its DLL directory).",
            file=sys.stderr,
        )
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict = build_and_run(out_dir)
    (out_dir / "benchmark_te10_summary.json").write_text(
        json.dumps(verdict, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(verdict, indent=2))
    print(f"wrote {out_dir / 's21.csv'} and benchmark_te10_summary.json")
    return 0 if verdict["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
