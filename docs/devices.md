# Device specs — the two machines running this project

Performance numbers are only comparable **within** a machine (and within the same
settings). This page exists so that any throughput claim can be interpreted.

| | **Yotta's machine** (this session) | **Aksara's machine** |
|---|---|---|
| CPU | 12th Gen **Intel Core i7-12700F** — 12 cores / 20 threads, 25.6 MB L3 | **AMD Ryzen 7 5800HS** (from Aksara's `aksarakomen.md` §21.1) |
| RAM | **15.9 GB** | not stated in their notes |
| GPU | **NVIDIA GeForce GTX 1650**, 4 GB, driver 32.0.15.9186, OpenCL via **NVIDIA CUDA (OpenCL 3.0 CUDA 13.1)**, 14 CU @ 1755 MHz, `fp64 = True` | **AMD Radeon iGPU `gfx90c`**, 8 CU @ 2000 MHz, 6234 MB shared, OpenCL **2.1** (AMD-APP 3302.6), fp64 supported but slow |
| Storage | **VENTUZ M.2 NVMe SSD 256 GB** + WDC 466 GB SATA HDD | not stated |
| OS | **Windows 11 Pro** build 26200 | Windows (version not stated) |
| Board | MSI MS-7D48 | — |

## Software stacks on Yotta's machine

| Component | Version / path |
|---|---|
| Project venv (Python 3.12) | `pip install -e .` + matplotlib 3.11.2, PySide6 6.11.2, pytest, scikit-rf 2.1.0, python-docx |
| Solver venv (Python 3.13.9) | numpy 2.5.3, **CSXCAD 0.7.0rc2 + openEMS 0.37.0rc2** (official cp313 wheels), pyopencl 2026.1.4 |
| openEMS runtime | `C:\Users\User\openEMS` (binary reports `v0.37.0-rc2`) |
| NEC2 engine | **nec2c built locally** from `KJ7LNW/nec2c` with WinLibs **gcc 16.2.0** (portable, no admin) + 4 small shims — see `yottakomen.md` §29 |
| Extra tooling | mingw-w64 toolchain at `C:\Users\User\mingw64` (used to build nec2c) |

## Measured throughputs (keep the context with the number)

| Measurement | Value | Context |
|---|---|---|
| openEMS FDTD, single run | **81.8 MCells/s** | TE10 waveguide model, 69,741 cells, 200,000 steps, 2.9 min wall |
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

## Practical consequences for the two of us

1. Any "X× faster" claim must state **machine + kernel + settings**; otherwise it is not
   evidence (both of us had to retract one such number already).
2. Timing-sensitive measurements should be taken on an **idle** machine — my GPU numbers
   were measured while openEMS runs held CPU cores; the iGPU shares memory bandwidth.
3. Yotta can run **openEMS, nec2c and the OpenCL path** locally, so solver-dependent
   verification no longer needs to round-trip through Aksara's machine.
