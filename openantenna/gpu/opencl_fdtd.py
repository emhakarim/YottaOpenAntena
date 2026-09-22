"""A small, validated OpenCL FDTD solver (2-D TMz).

Scope, deliberately limited:

* two dimensions, TMz polarisation (Ez, Hx, Hy) -> the cheapest kernel that still
  solves a real Maxwell problem;
* homogeneous, non-dispersive material, PEC outer walls;
* float32 arithmetic (FP64 works on this hardware but is far slower, and FDTD error
  is dominated by numerical dispersion, not by the mantissa);
* a soft source and a point probe, which is exactly what a resonance measurement needs.

The validation is the point of this module: a square PEC cavity has an exact
spectrum, ``f_mn = c/2 * sqrt((m/a)^2 + (n/b)^2)``, so the kernel's answer can be
checked against physics instead of against itself.  See
:func:`cavity_resonance` and ``tests/test_gpu_fdtd.py``.

What is NOT here yet (and must not be implied): CPML absorbers, lumped ports,
dispersive/lossy materials, 3-D geometry.  Those are the steps that would make this a
usable engine; the honest status today is "validated 2-D kernel with measured
throughput".
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import numpy as np

C0 = 299792458.0
EPS0 = 8.8541878128e-12
MU0 = 4.0e-7 * math.pi

_KERNEL_SOURCE = """
__kernel void update_h(__global float *ez, __global float *hx, __global float *hy,
                       const float ch, const int nx, const int ny)
{
    int i = get_global_id(0);
    int j = get_global_id(1);
    if (i >= nx - 1 || j >= ny - 1) return;
    int idx = j * nx + i;
    hy[idx] += ch * (ez[idx + 1] - ez[idx]);
    hx[idx] -= ch * (ez[idx + nx] - ez[idx]);
}

__kernel void update_e(__global float *ez, __global float *hx, __global float *hy,
                       const float ce, const int nx, const int ny)
{
    int i = get_global_id(0);
    int j = get_global_id(1);
    if (i < 1 || j < 1 || i >= nx - 1 || j >= ny - 1) return;
    int idx = j * nx + i;
    ez[idx] += ce * ((hy[idx] - hy[idx - 1]) - (hx[idx] - hx[idx - nx]));
}

__kernel void add_source(__global float *ez, const float value, const int idx)
{
    ez[idx] += value;
}

// Records one probe sample on the device.  Reading the probe back to the host every
// step costs a blocking round trip (~ms), which dominated the first version of this
// module: 20000 steps took 169 s, of which the kernel was microseconds.
__kernel void record_probe(__global float *ez, __global float *trace, const int idx, const int n)
{
    trace[n] = ez[idx];
}
"""


class OpenCLFDTD2D:
    """2-D TMz FDTD on an OpenCL device.

    The class owns the device buffers, so a run happens entirely on the GPU: only the
    probe samples come back per step.
    """

    def __init__(self, nx: int, ny: int, dx: float, dy: Optional[float] = None, device_index: int = 0):
        try:
            import pyopencl as cl
        except Exception as exc:  # pragma: no cover - depends on the environment
            raise RuntimeError(f"pyopencl is required for the GPU path: {exc}") from exc

        if nx < 8 or ny < 8:
            raise ValueError("grid too small to be meaningful")
        if dx <= 0:
            raise ValueError("dx must be > 0")

        self.cl = cl
        self.nx = int(nx)
        self.ny = int(ny)
        self.dx = float(dx)
        self.dy = float(dy if dy is not None else dx)

        # Courant limit for the 2-D Yee scheme.
        self.dt = 1.0 / (C0 * math.sqrt(1.0 / self.dx ** 2 + 1.0 / self.dy ** 2))
        self.courant = C0 * self.dt * math.sqrt(1.0 / self.dx ** 2 + 1.0 / self.dy ** 2)

        platforms = cl.get_platforms()
        devices = [d for p in platforms for d in p.get_devices()]
        if not devices:
            raise RuntimeError("no OpenCL devices found")
        if device_index >= len(devices):
            raise ValueError(f"device_index {device_index} out of range ({len(devices)} devices)")
        self.device = devices[device_index]

        self.context = cl.Context([self.device])
        self.queue = cl.CommandQueue(self.context)
        self.program = cl.Program(self.context, _KERNEL_SOURCE).build()

        # Cache the kernel objects.  Reaching for them by attribute
        # (``self.program.update_e``) re-creates the kernel on every single call, which
        # costs ~2 ms of pure overhead: it made a 61x61 grid and a 301x301 grid take the
        # same time per step, i.e. the GPU looked ~100x slower than it is.  pyopencl
        # reports this as a RepeatedKernelRetrieval warning.
        self.k_update_h = cl.Kernel(self.program, "update_h")
        self.k_update_e = cl.Kernel(self.program, "update_e")
        self.k_add_source = cl.Kernel(self.program, "add_source")
        self.k_record_probe = cl.Kernel(self.program, "record_probe")

        shape = (self.ny, self.nx)
        self.ez = np.zeros(shape, dtype=np.float32)
        self.hx = np.zeros(shape, dtype=np.float32)
        self.hy = np.zeros(shape, dtype=np.float32)
        flags = cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR
        self.buf_ez = cl.Buffer(self.context, flags, hostbuf=self.ez)
        self.buf_hx = cl.Buffer(self.context, flags, hostbuf=self.hx)
        self.buf_hy = cl.Buffer(self.context, flags, hostbuf=self.hy)

        self._ch = np.float32(self.dt / (MU0 * self.dx))
        self._ce = np.float32(self.dt / (EPS0 * self.dx))

    # ------------------------------------------------------------------ stepping
    def step(self) -> None:
        """One full leapfrog step (H then E)."""
        global_size = (self.nx, self.ny)
        self.k_update_h(
            self.queue, global_size, None, self.buf_ez, self.buf_hx, self.buf_hy,
            self._ch, np.int32(self.nx), np.int32(self.ny),
        )
        self.k_update_e(
            self.queue, global_size, None, self.buf_ez, self.buf_hx, self.buf_hy,
            self._ce, np.int32(self.nx), np.int32(self.ny),
        )

    def add_source(self, index: int, value: float) -> None:
        self.k_add_source(self.queue, (1,), None, self.buf_ez, np.float32(value), np.int32(index))

    def record_probe(self, index: int, trace_buffer, sample_index: int) -> None:
        """Append one sample to a device-side trace (no host round trip)."""
        self.k_record_probe(
            self.queue, (1,), None, self.buf_ez, trace_buffer,
            np.int32(index), np.int32(sample_index),
        )

    def probe(self, index: int) -> float:
        """Read one field sample back immediately.

        Convenient for interactive use, but every call is a blocking round trip.  For a
        long trace use :meth:`record_probe` and copy once at the end.
        """
        out = np.zeros(1, dtype=np.float32)
        self.cl.enqueue_copy(self.queue, out, self.buf_ez, src_offset=4 * index, is_blocking=True)
        return float(out[0])

    def read_ez(self) -> np.ndarray:
        out = np.empty_like(self.ez)
        self.cl.enqueue_copy(self.queue, out, self.buf_ez, is_blocking=True)
        return out


def cavity_resonance(
    size_m: float = 0.1,
    cells: int = 100,
    steps: int = 20000,
    device_index: int = 0,
) -> Dict[str, float]:
    """Measure the dominant resonance of a square PEC cavity on the GPU.

    The analytic answer for a square cavity of side ``a`` is
    ``f11 = c/2 * sqrt(2) / a``.  Getting that back is the acceptance test for the
    whole kernel chain: staggered update, CFL condition, PEC walls, source, probe, FFT.

    Returns a dict with the measured and analytic frequencies, their relative error,
    the Courant factor actually used, and the wall-clock seconds for the run.
    """
    nx = ny = cells + 1  # PEC walls sit on the outer nodes -> cavity side = cells * dx
    dx = size_m / cells
    engine = OpenCLFDTD2D(nx, ny, dx, device_index=device_index)

    source_index = (ny // 4) * nx + (nx // 4)
    probe_index = (ny // 3) * nx + (2 * nx // 3)

    tau = 30.0 * engine.dt
    t0 = 4.0 * tau

    # The trace lives on the device and is copied back once: the first version read the
    # probe every step, which made a sub-second kernel take 169 s.
    cl = engine.cl
    trace_buffer = cl.Buffer(
        engine.context, cl.mem_flags.WRITE_ONLY | cl.mem_flags.ALLOC_HOST_PTR, size=4 * steps
    )

    import time

    started = time.perf_counter()
    for n in range(steps):
        t = n * engine.dt
        engine.add_source(source_index, math.exp(-(((t - t0) / tau) ** 2)))
        engine.step()
        engine.record_probe(probe_index, trace_buffer, n)
    samples = np.empty(steps, dtype=np.float32)
    cl.enqueue_copy(engine.queue, samples, trace_buffer, is_blocking=True)
    elapsed = time.perf_counter() - started
    samples = samples.astype(np.float64)

    window = np.hanning(steps)
    spectrum = np.abs(np.fft.rfft(samples * window))
    frequencies = np.fft.rfftfreq(steps, d=engine.dt)
    # ignore very low frequencies: the source pulse leaves a DC tail
    floor = np.searchsorted(frequencies, 0.5e9)
    peak = floor + int(np.argmax(spectrum[floor:]))
    # parabolic refinement of the spectral peak: the record length alone only locates
    # the resonance to one bin (1/T), which is ~0.6 % here
    measured = float(frequencies[peak])
    if 0 < peak < len(spectrum) - 1:
        y1, y2, y3 = spectrum[peak - 1], spectrum[peak], spectrum[peak + 1]
        curvature = y1 - 2.0 * y2 + y3
        if curvature != 0.0:
            delta = 0.5 * (y1 - y3) / curvature
            measured += delta * (frequencies[peak + 1] - frequencies[peak])
    analytic = C0 / (2.0 * size_m) * math.sqrt(2.0)

    return {
        "measured_hz": measured,
        "analytic_hz": analytic,
        "relative_error_percent": (measured - analytic) / analytic * 100.0,
        "courant_factor": engine.courant,
        "cell_updates_per_second": (nx * ny * steps) / max(elapsed, 1e-9),
        "wall_seconds": elapsed,
        "steps": steps,
        "cells": nx * ny,
        "device": engine.device.name,
    }


def throughput(
    cells: int = 400, steps: int = 2000, device_index: int = 0
) -> Dict[str, float]:
    """Raw cell-updates/second, for comparing this GPU against the CPU."""
    import time

    engine = OpenCLFDTD2D(cells + 1, cells + 1, 1e-3, device_index=device_index)
    started = time.perf_counter()
    for _ in range(steps):
        engine.step()
    elapsed = time.perf_counter() - started
    return {
        "device": engine.device.name,
        "cells": engine.nx * engine.ny,
        "steps": steps,
        "wall_seconds": elapsed,
        "cell_updates_per_second": (engine.nx * engine.ny * steps) / max(elapsed, 1e-9),
    }
