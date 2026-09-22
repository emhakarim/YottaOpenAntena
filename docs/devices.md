# Device specs — the two machines running this project

Performance numbers are only comparable **within** a machine (and within the same
settings). This page exists so that any throughput claim can be interpreted.

| | **Yotta's machine** (this session) | **Aksara's machine** |
|---|---|---|
| CPU | 12th Gen **Intel Core i7-12700F** — 12 cores / 20 threads, 25.6 MB L3 | **AMD Ryzen 7 5800HS with Radeon Graphics** — 8 cores / 16 threads, 3.2 GHz base (ASUS VivoBook M1403QA) |
| RAM | **15.9 GB** | **15.4 GB usable** — 2 × 8 GB DDR4-3200 (Samsung + Micron), dual channel |
| GPU | **NVIDIA GeForce GTX 1650**, 4 GB, driver 32.0.15.9186, OpenCL via **NVIDIA CUDA (OpenCL 3.0 CUDA 13.1)**, 14 CU @ 1755 MHz, `fp64 = True` | **AMD Radeon iGPU `gfx90c`**, 8 CU @ 2000 MHz, 6234 MB shared, OpenCL **2.1** (AMD-APP 3302.6), fp64 supported but slow; driver 30.0.13044.14002, local memory 32 KB, max workgroup 256 |
| Storage | **VENTUZ M.2 NVMe SSD 256 GB** + WDC 466 GB SATA HDD | **INTEL SSDPEKNU512GZ NVMe SSD 512 GB** (D: 158 GB free of 215 GB) |
| OS | **Windows 11 Pro** build 26200 | **Windows 11 Home Single Language** build 26200 (10.0.26200, 64-bit) |
| Board | MSI MS-7D48 | ASUS VivoBook M1403QA — laptop, **no discrete GPU** |

## Software stacks on Yotta's machine

| Component | Version / path |
|---|---|
| Project venv (Python 3.12) | `pip install -e .` + matplotlib 3.11.2, PySide6 6.11.2, pytest, scikit-rf 2.1.0, python-docx |
| Solver venv (Python 3.13.9) | numpy 2.5.3, **CSXCAD 0.7.0rc2 + openEMS 0.37.0rc2** (official cp313 wheels), pyopencl 2026.1.4 |
| openEMS runtime | `C:\Users\User\openEMS` (binary reports `v0.37.0-rc2`) |
| NEC2 engine | **nec2c built locally** from `KJ7LNW/nec2c` with WinLibs **gcc 16.2.0** (portable, no admin) + 4 small shims — see `yottakomen.md` §29 |
| Extra tooling | mingw-w64 toolchain at `C:\Users\User\mingw64` (used to build nec2c) |

## Software stacks on Aksara's machine

| Component | Version / path |
|---|---|
| Project + solver venv, **Python 3.13.15** | `D:\OpenAntenna\.venv` — numpy 2.5.3, pyopencl 2026.1.4, matplotlib 3.11.2, PySide6 6.11.2, scikit-rf 2.1.0, **CSXCAD 0.7.0rc2 + openEMS 0.37.0rc2**, pip 26.2.1 |
| openEMS runtime | `D:\OpenAntenna\tools\openEMS\openEMS.exe`, binary reports **v0.37.0-rc2**; `OPENEMS_ROOT` must be set, because Python ≥ 3.8 cannot find the native DLLs through `PATH` |
| Core + tests | **stdlib only** — `python -m unittest discover -s tests` needs no numpy |
| GPU binding | pyopencl 2026.1.4 against the AMD driver runtime (probe values in the table above) |
| NEC2 engine | not installed here; Yotta's `nec2c` build is the only working one, so NEC2 runs are theirs |

Reproduction note: the AutoClaw-bundled interpreter runs in **isolated mode**
(`sys.flags.isolated == 1`), so `PYTHONPATH` is ignored there. Use `D:\OpenAntenna\.venv`
for anything that must import the package.

## Measured throughputs (keep the context with the number)

| Measurement | Value | Context |
|---|---|---|
| openEMS FDTD, single run | **81.8 MCells/s** | TE10 waveguide model, 69,741 cells, 200,000 steps, 2.9 min wall |
| openEMS FDTD (Aksara's machine) | **10.1 – 135 MCells/s** | Same build, but the number moves with the **model**: 135.0 MCells/s on the tutorial-like grid, 46.7 on a Mur boundary case, 10–13 on the fine-mesh ground-plane models. Quote the model or the number means nothing |
| OpenCL 2-D kernel, absolute (Aksara) | **~290 MCells/s** | `gfx90c`, grid 601×601, float32, 3 runs with the queue drained (291 / 293 / 295) → ~19–24× the numpy baseline on the same machine |
| numpy float32 baseline (Aksara) | **12.3 – 15.1 MCells/s** | same scheme, 601×601 grid; the spread is CPU contention from concurrent solver runs |
| OpenCL 2-D kernel vs numpy (Yotta) | **7.26×** | GTX 1650; the earlier 9.19× was invalidated by the async-timing bug |
| OpenCL 2-D kernel vs numpy (Aksara) | **~24×** (293 vs 12.3 MCells/s) | Radeon iGPU `gfx90c`; their earlier 86× was invalidated by the same bug |
| nec2c, one dipole deck | < 1 s | 31-segment dipole; irrelevant to the FDTD budget |

**Do not compare the GPU ratios across machines** — a discrete 4 GB GTX 1650 and an
integrated Radeon share nothing but the OpenCL label. Only ratios measured *on the same
machine, same code, same settings* are meaningful.

## What Yotta's machine can absorb in parallel

* 12 cores / 20 threads and 15.9 GB RAM, with the Task Manager screenshot showing
  **CPU 18 %, RAM 56 %** while a solver run was in flight → there is room for a
  **multi-case batch** (a sensible target is 4–6 concurrent openEMS runs, since FDTD is
  memory-light; watch RAM rather than CPU).
* Put run directories on the **NVMe SSD**, not the SATA HDD: the NF2FF work is I/O-heavy
  and that was a real bottleneck before the DFT-only fix.

## What Aksara's machine can absorb in parallel

* Measured while **two** openEMS runs were in flight: **CPU 74 %**, **RAM 6.4 GB free of
  15.4 GB**, each run holding **~5 of 16 threads** (≈10 threads total). On this laptop the
  binding constraint is **RAM, not CPU** — budget ~3 GB per run and stop at 3–4 concurrent.
* Run directories, the venv and the solver all live on the NVMe (`D:`).
* This machine is **not** comparable to the i7-12700F: any cross-machine comparison must
  name the model and the machine (see the note above), because the openEMS throughput here
  varies by 13× across models.

## Practical consequences for the two of us

1. Any "X× faster" claim must state **machine + kernel + settings**; otherwise it is not
   evidence (both of us had to retract one such number already).
2. Timing-sensitive measurements should be taken on an **idle** machine — my GPU numbers
   were measured while openEMS runs held CPU cores; the iGPU shares memory bandwidth.
3. Yotta can run **openEMS, nec2c and the OpenCL path** locally, so solver-dependent
   verification no longer needs to round-trip through Aksara's machine.
