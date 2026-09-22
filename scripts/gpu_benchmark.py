"""Measure the GPU FDTD path against the CPU, and validate it against physics.

Two measurements and one acceptance test:

1. **Throughput** - the same 2-D TMz update on the OpenCL device and on numpy (CPU),
   reported as cell-updates per second, so the comparison is like-for-like.
2. **Validation** - a square PEC cavity, whose resonance is known analytically
   (f11 = c/2 * sqrt(2) / a).  A kernel that reproduces it is doing electromagnetics;
   one that merely runs proves nothing.

Usage:
    python scripts/gpu_benchmark.py [--cells N] [--steps N]
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openantenna.gpu import gpu_available, opencl_devices

C0 = 299792458.0
EPS0 = 8.8541878128e-12
MU0 = 4.0e-7 * math.pi


def cpu_reference(cells: int, steps: int, dx: float = 1.0e-3) -> dict:
    """The same scheme on the CPU with numpy: the bandwidth-bound baseline."""
    nx = ny = cells + 1
    dt = 1.0 / (C0 * math.sqrt(2.0) / dx)
    ch = dt / (MU0 * dx)
    ce = dt / (EPS0 * dx)
    ez = np.zeros((ny, nx), dtype=np.float32)
    hx = np.zeros((ny, nx), dtype=np.float32)
    hy = np.zeros((ny, nx), dtype=np.float32)

    started = time.perf_counter()
    for _ in range(steps):
        hy[0:-1, 0:-1] += ch * (ez[1:, 0:-1] - ez[0:-1, 0:-1])
        hx[0:-1, 0:-1] -= ch * (ez[0:-1, 1:] - ez[0:-1, 0:-1])
        ez[1:-1, 1:-1] += ce * (
            (hy[1:-1, 1:-1] - hy[0:-2, 1:-1]) - (hx[1:-1, 1:-1] - hx[1:-1, 0:-2])
        )
    elapsed = time.perf_counter() - started
    return {
        "device": "numpy/CPU (float32)",
        "cells": nx * ny,
        "steps": steps,
        "wall_seconds": elapsed,
        "cell_updates_per_second": (nx * ny * steps) / max(elapsed, 1e-9),
    }


def main() -> int:
    cells, steps = 400, 2000
    if "--cells" in sys.argv:
        cells = int(sys.argv[sys.argv.index("--cells") + 1])
    if "--steps" in sys.argv:
        steps = int(sys.argv[sys.argv.index("--steps") + 1])

    devices = opencl_devices()
    print("OpenCL devices:")
    for index, device in enumerate(devices):
        print(
            f"  [{index}] {device['name']} ({device['type']}) - {device['compute_units']} CU, "
            f"{device['clock_mhz']} MHz, {device['global_mem_mb']} MB, "
            f"local {device['local_mem_kb']} KB, fp64={device['fp64']}"
        )
    if not devices:
        print("No OpenCL device: nothing to measure. The toolkit works without this path.")
        return 0

    from openantenna.gpu import opencl_fdtd

    print("\nrunning the GPU throughput measurement ...")
    gpu = opencl_fdtd.throughput(cells=cells, steps=steps)
    print("  " + json.dumps(gpu, default=str))

    print("running the CPU (numpy) reference at the same grid ...")
    cpu = cpu_reference(cells=cells, steps=steps)
    print("  " + json.dumps(cpu, default=str))

    ratio = gpu["cell_updates_per_second"] / cpu["cell_updates_per_second"]
    print(f"\nGPU/CPU throughput ratio: {ratio:.2f}x")

    print("\nvalidating the kernel against an analytic cavity resonance ...")
    validation = opencl_fdtd.cavity_resonance(size_m=0.1, cells=60, steps=20000)
    print("  " + json.dumps(validation, default=str))

    out = ROOT / "runs" / "gpu_benchmark.json"
    out.write_text(
        json.dumps(
            {
                "devices": devices,
                "gpu_throughput": gpu,
                "cpu_throughput": cpu,
                "gpu_over_cpu": ratio,
                "cavity_validation": validation,
                "note": (
                    "FDTD is memory-bandwidth bound. An integrated GPU shares the system "
                    "memory bus with the CPU, so a ratio near or below 1 is expected here; "
                    "a discrete GPU with dedicated VRAM is where this path pays off. The "
                    "cavity check is the acceptance test for the kernel itself."
                ),
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nsummary written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
