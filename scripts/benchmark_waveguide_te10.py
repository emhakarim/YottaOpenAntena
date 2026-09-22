"""Benchmark #2 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â rectangular waveguide, TE10 cutoff (exact analytic reference).

Why this benchmark exists (see `docs/benchmarks.md` Ãƒâ€šÃ‚Â§5): the cutoff frequency of an
air-filled rectangular waveguide has an EXACT closed form,

    f_c = c / (2a)          a = broad dimension

so it tests the solver + mesh + post-processing pipeline against a number nobody can
argue about ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no fringing, no feed geometry, no dielectric.  A second, independent
topology is exactly what the benchmark gap needs.

Model: a = 100 mm, b = 50 mm, length 200 mm, air filled.
PEC on the four side walls, PML on the two ends, a small z-directed lumped port at
z = 0 as the source and a second one at z = 150 mm as the receiver.  Below f_c the
mode is evanescent (transmission collapses); above f_c it propagates.

    f_c = c / (2 * 0.1) = 1.499 GHz

Acceptance criteria (from the benchmark doc):
  * transmission at 0.9 f_c  <= -30 dB,
  * transmission at 1.3 f_c  >= -1 dB,
  * the -3 dB edge within 1 % of 1499.0 MHz,
  * the run reports how many timesteps it used and whether EndCriteria was met.

Usage (needs openEMS; set OPENEMS_ROOT to the folder holding openEMS.exe):

    python scripts/benchmark_waveguide_te10.py [out_dir]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

def _register_openems() -> None:
    """Register the native DLLs, then import the solver inside ``main()``.

    Both steps are deferred on purpose: this module must import cleanly on a machine
    without openEMS, which ``tests/test_repo_paths.py::test_modules_import_cleanly``
    enforces.  (Caught in review: the first version called ``sys.exit`` at import.)
    """
    if os.name == "nt":
        root = os.environ.get("OPENEMS_ROOT", "")
        if not root or not os.path.isdir(root):
            raise SystemExit(
                "ERROR: OPENEMS_ROOT must point at the folder holding openEMS.exe / CSXCAD.dll"
            )
        os.add_dll_directory(root)
        os.environ["PATH"] = root + os.pathsep + os.environ.get("PATH", "")


C0 = 299792458.0  # vacuum speed of light [m/s], the same value the solver reports

A = 100e-3          # broad dimension (x)  -> f_c = 1.499 GHz
B = 50e-3           # narrow dimension (y)
LENGTH = 200e-3     # guide length (z)
F_C = C0 / (2.0 * A)
F_MIN, F_MAX = 1.0e9, 3.0e9
N_FREQ = 101
MAX_TS = 200000
END_CRITERIA = 1e-4


def main() -> int:
    _register_openems()
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runs") / "benchmark_te10"
    out_dir.mkdir(parents=True, exist_ok=True)

    FDTD = openEMS(NrTS=MAX_TS, EndCriteria=END_CRITERIA)
    FDTD.SetGaussExcite(2.0e9, 1.5e9)
    FDTD.SetBoundaryCond(["PEC", "PEC", "PEC", "PEC", "PML_8", "PML_8"])

    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(1.0)
    t = 1e-3

    CSX.AddMaterial("air").AddBox([-A / 2, -B / 2, 0], [A / 2, B / 2, LENGTH], priority=0)
    # The guide walls ARE the domain boundary: x and y are set to PEC just below.  The
    # earlier version added 1 mm thick PEC boxes inside this outline, which shrank the
    # air channel to 98 x 48 mm and moved the real cutoff to 1529.6 MHz while the script
    # still compared against c/(2*100 mm) = 1499.0 MHz.

    # Modal (TE10) ports.  The previous z-directed lumped port with edges2grid="xy"
    # produced "CalcVoltageIntegral: Error, only a 1D/line integration is allowed" every
    # timestep and a field energy of exactly zero, so no transmission could be measured.
    # An *excited* port needs a non-zero length along the propagation direction, which
    # openEMS reports as "Port length in excitation direction may not be zero if port is
    # excited!".  One mesh cell (t = 1 mm) is enough; the receiving port is a plane.
    port_in = FDTD.AddRectWaveGuidePort(
        1, [-A / 2, -B / 2, 0.0], [A / 2, B / 2, t], "z", A, B, "TE10", 1
    )
    port_out = FDTD.AddRectWaveGuidePort(
        2, [-A / 2, -B / 2, LENGTH], [A / 2, B / 2, LENGTH], "z", A, B, "TE10", 0
    )

    # The port planes must sit on mesh lines -- openEMS's own example
    # (python/Tutorials/Rect_WaveGuide.py) adds them explicitly.  Without this the probe
    # boxes never land on the grid, no `port_ut_*` file is written, and CalcPort dies
    # with FileNotFoundError even though the FDTD run itself succeeds.
    mesh.AddLine("z", [0.0, t])
    mesh.AddLine("z", [LENGTH - t, LENGTH])

    mesh.AddLine("x", np.linspace(-A / 2, A / 2, 21))
    mesh.AddLine("y", np.linspace(-B / 2, B / 2, 11))
    mesh.AddLine("z", np.linspace(0, LENGTH, 41))
    mesh.SmoothMeshLines("all", C0 / F_MAX / 20.0, 1.4)

    print(f"TE10 cutoff (analytic): f_c = c/(2a) = {F_C / 1e9:.4f} GHz  (a = {A * 1e3:.1f} mm)")
    sim_path = str(out_dir / "openems_run")
    FDTD.Run(sim_path, verbose=3, cleanup=True)

    freqs = np.linspace(F_MIN, F_MAX, N_FREQ)
    port_in.CalcPort(sim_path, freqs, 50.0)
    port_out.CalcPort(sim_path, freqs, 50.0)
    s21 = port_out.uf_ref / port_in.uf_inc
    s21_db = 20.0 * np.log10(np.maximum(np.abs(s21), 1e-12))

    csv_path = out_dir / "s21.csv"
    with csv_path.open("w", encoding="utf-8") as handle:
        handle.write("freq_hz,s21_re,s21_im,s21_db\n")
        for f, value, db in zip(freqs, s21, s21_db):
            handle.write(f"{f:.6e},{value.real:.9e},{value.imag:.9e},{db:.6f}\n")

    # the -3 dB edge, linearly interpolated
    edge = None
    for i in range(1, len(s21_db)):
        if s21_db[i - 1] < -3.0 <= s21_db[i]:
            span = s21_db[i] - s21_db[i - 1]
            edge = freqs[i - 1] + (-3.0 - s21_db[i - 1]) * (freqs[i] - freqs[i - 1]) / span
            break

    at_0p9 = float(np.interp(0.9 * F_C, freqs, s21_db))
    at_1p3 = float(np.interp(1.3 * F_C, freqs, s21_db))
    verdict = {
        "analytic_cutoff_hz": F_C,
        "measured_3db_edge_hz": None if edge is None else float(edge),
        "edge_error_percent": None if edge is None else (edge / F_C - 1.0) * 100.0,
        "s21_at_0p9fc_db": at_0p9,
        "s21_at_1p3fc_db": at_1p3,
        "passes": bool(edge is not None and abs(edge / F_C - 1.0) <= 0.01
                       and at_0p9 <= -30.0 and at_1p3 >= -1.0),
        "n_timesteps": MAX_TS,
        "end_criteria": END_CRITERIA,
        "note": "check run_manifest/logs for whether EndCriteria was met before the cap",
    }
    (out_dir / "benchmark_te10_summary.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict, indent=2))
    print(f"wrote {csv_path} and benchmark_te10_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
