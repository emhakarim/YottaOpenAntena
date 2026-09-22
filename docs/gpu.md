# GPU path (`openantenna.gpu`)

Optional. Everything in the core toolkit and its test suite keeps working on a machine
with no GPU, no OpenCL runtime and no `pyopencl`; the GPU path is an extra, not a
dependency.

## Why this exists

openEMS is CPU-only — that is an ecosystem limit, not a property of the user's machine
(see [capabilities-and-comparison.md](capabilities-and-comparison.md)). If a GPU is to
accelerate the *simulation* rather than the display, it has to run a different FDTD
kernel. This package is that kernel, built in OpenCL so it works on AMD, Intel and
NVIDIA hardware, including cheap and integrated GPUs.

## What is implemented, and what is not

| Implemented | Not implemented (must not be implied) |
|---|---|
| 2-D TMz FDTD (Ez, Hx, Hy), staggered leapfrog | 3-D geometry |
| PEC outer walls | CPML / any absorbing boundary |
| Soft source, point probe | Lumped ports, wave ports, excitation matching a microstrip feed |
| Homogeneous, non-dispersive material | Dispersive (\(\varepsilon_r(\omega)\)) and lossy media |
| Device-side probe trace (one host copy per run) | Conductor loss, thin-sheet models |
| Validated against an analytic cavity | Arrays, unit cells, far-field / NF2FF |

The honest status is: **a validated 2-D kernel with measured throughput**, not a
replacement for the openEMS adapter.

## Validation: the cavity test is the acceptance criterion

A square PEC cavity of side \(a\) has an exact spectrum,
\(f_{mn}=\frac{c}{2}\sqrt{(m/a)^2+(n/b)^2}\). A kernel that reproduces it is doing
electromagnetics; one that merely runs proves nothing.

Measured on the reference machine (openCL, AMD `gfx90c`), \(a = 100\) mm, 60 cells per
side (61×61 grid), 20000 steps:

| Quantity | Value |
|---|---|
| Measured resonance (TM11) | 2.1205151 GHz |
| Analytic \(c/2\sqrt{2}/a\) | 2.1198528 GHz |
| **Relative error** | **0.031 %** |
| Courant factor used | 1.000000 |

The spectral peak is refined by a parabolic fit, otherwise the record length alone
locates the resonance only to one FFT bin (~0.6 % here).

Run it yourself:

```powershell
python -m unittest tests.test_gpu_fdtd -v          # skips cleanly without a GPU
python scripts/gpu_benchmark.py --cells 600 --steps 800
```

## Throughput: measured, and honest about the baseline

Grid 601×601 (361201 cells), 800 steps, float32, measured with the queue drained
(`finish()`) so the clock includes the GPU work:

| Engine | Throughput |
|---|---|
| OpenCL on `gfx90c` (integrated) | **~293 MCells/s** (291–295 over 3 runs) |
| numpy float32, same scheme/CPU | 12.3 MCells/s |
| Ratio | ~24× |

Two caveats, both important:

* The CPU baseline here is **numpy**, not openEMS's tuned C++ kernel. "24× faster than
  numpy" is not "24× faster than openEMS". A like-for-like comparison against openEMS on
  the same problem is the next measurement and has **not** been done.
* Both figures were measured while two openEMS runs were occupying ~10 of 16 CPU cores.
  An integrated GPU shares the system memory bus with the CPU, so memory traffic from
  those jobs can slow the GPU path down. Re-measure on an idle machine before quoting
  these numbers.

## Two defects this path produced, and what they teach

Both were found by re-measuring rather than by reading the code:

1. **`RepeatedKernelRetrieval`** — reaching for kernels by attribute
   (`self.program.update_e`) re-creates the kernel object on every call, costing ~2 ms
   of pure overhead. Symptoms: a 61×61 grid and a 301×301 grid took the same time per
   step (2001 µs and 2057 µs), i.e. the GPU appeared ~100× slower than it is. After
   caching the kernel objects: 294 µs and 387 µs per step. The test suite also went from
   169 s to 27 s.
2. **Asynchronous timing** — the first throughput measurement stopped the clock without
   draining the queue, reporting the enqueue time only. It gave 1061 MCells/s, which
   re-measurement could not reproduce (293 MCells/s).

The lesson, recorded because it nearly produced a false conclusion: a performance claim
that is not reproduced at least twice is not evidence.

## Hardware note

An integrated GPU shares memory bandwidth with the CPU, so the ceiling here is the
system memory bus. The same kernel should scale to a cheap discrete GPU, which has
dedicated VRAM and several times the bandwidth — that is where this path pays off, and
the code needs no changes to get there. FP64 is available on this device but is far
slower than FP32; the kernel uses FP32 deliberately, since FDTD error is dominated by
numerical dispersion rather than by the mantissa.

## Roadmap to something usable for real antenna work

In dependency order. Each step needs its own validation against analysis or openEMS, and
none of it is implied by the current state.

1. Like-for-like benchmark vs the openEMS CPU kernel on the same geometry.
2. CPML absorbing boundaries (without them, only closed problems like cavities work).
3. Lumped port + microstrip feed.
4. 3-D geometry from the existing neutral model (patch / array).
5. Lossy and dispersive materials (the Debye machinery already exists in
   `openantenna.materials.dispersion`).
6. A 2-D fast mode for exploratory scans, and GPU post-processing (array factor over
   large angle grids) — both cheap and useful before 3-D.
