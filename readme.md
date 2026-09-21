# OpenAntenna Studio

An open-source antenna analysis and design toolkit — a free alternative in
spirit to commercial full-wave packages, built as a modern front-end over
established open-source solvers.

**Status: Phase 1 (headless core). There is no GUI yet.**

## What this is (and is not)

| | |
|---|---|
| **Is** | A neutral parametric design model, a composite-material explorer (mixing rules, dispersion fitting, sensitivity), analytic element/array geometry synthesis, an openEMS model generator and result parser, a sweep engine and a result store — all scriptable from one CLI. |
| **Is not (yet)** | A GUI, a verified EM solver, an impedance-matching engine, a ready-to-fabricate design authority. |

Phase 1 deliberately runs on the **Python standard library only**. There is no
third-party import in the core or in the test suite, so the toolkit works on a
bare Python installation. External solvers and plotting libraries are optional
and are used through separate processes or later phases.

## Install

```powershell
# 1. Python environment (any Python >= 3.10)
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install numpy matplotlib pytest scikit-rf   # optional, for analysis/plots

# 2. Solver (optional, only to actually run simulations)
#    Download the official Windows package and unzip it somewhere:
#    https://github.com/thliebig/openEMS-Project/releases  -> openEMS_x64_*_msvc.zip
#    Then install its Python wheels that match your Python version:
#    <openems>/python/csxcad-*-cp3XX-cp3XX-win_amd64.whl
#    <openems>/python/openems-*-cp3XX-cp3XX-win_amd64.whl
#    Finally point the toolkit at the folder that holds openEMS.exe / CSXCAD.dll:
$env:OPENEMS_ROOT = "D:\OpenAntenna\tools\openEMS"
```

On Windows the generated model script needs `OPENEMS_ROOT` because Python >= 3.8
no longer searches `PATH` for the native DLLs of extension modules. The
generated script registers the folder with `os.add_dll_directory()` itself.

## Use

```powershell
python -m openantenna.cli --help
python -m openantenna.cli material list
python -m openantenna.cli mix --matrix 2.1 --filler 80 --vf 0.3
python -m openantenna.cli design patch --freq 2.45e9 --material PTFE --h 0.0016
python -m openantenna.cli design array --nx 4 --ny 4 --freq 2.45e9 --material PTFE --h 0.0016
python -m openantenna.cli solver status
python -m openantenna.cli gen-openems --freq 2.45e9 --material PTFE --h 0.0016 --out runs\patch1
python -m openantenna.cli sweep dry-run --axis substrate.layers.0.thickness_m=0.0008,0.0016,0.0032 --out runs\sweep1
```

`gen-openems` writes a runnable openEMS script but never runs it:

```powershell
# on a machine with openEMS installed, with OPENEMS_ROOT set:
python runs\patch1\sim.py
```

## Tests

```powershell
python -m unittest discover -s tests -v     # stdlib, no dependencies needed
python -m pytest tests -q                   # same suite via pytest, if installed
```

## Desktop GUI (Phase 3, preview)

The GUI is a **desktop application** (Qt via PySide6), not a web dashboard: the
solver runs locally as a subprocess, plots are native, and there is no server to
deploy. It is a thin client of the same functions the CLI calls.

```powershell
.venv\Scripts\python.exe -m pip install PySide6-Essentials
python -m openantenna.gui
```

Four tabs: **Material & composite** (library + mixing rules with their validity
warnings), **Design** (patch synthesis, array layout, array-factor plot),
**Simulate** (mesh and loss settings, generate, run in a worker thread),
**Results** (load a run directory, plot S11, read the metrics).

Status: the window builds and is covered by an offscreen smoke test, but it has
not yet been used for real work — no 3-D viewer, no live solver log.

## Project notes

* [`aksarakomen.md`](aksarakomen.md) — working notes from the developing agent
  (Aksara), including every measurement, every fixed defect and the open
  calibration questions.
* `yottakomen.md` — review notes from the evaluating agent (Yotta).

## Honesty rules this project follows

* A model that was only generated is reported as **generated**, never as
  verified. `run_manifest.json` carries `"verified": false` until a real run
  produces results.
* A simulation that did not run never yields numbers. The adapter raises instead
  of inventing results.
* The `mix` output carries the validity limits of the underlying mixing rules as explicit warnings, because those rules are quasi-static
  effective-medium approximations, not measurements.

## Documentation

* [docs/architecture.md](docs/architecture.md) — layers, module map, data flow
* [docs/materials.md](docs/materials.md) — built-in materials, mixing rules, validity limits
* [docs/verification.md](docs/verification.md) — what has actually been verified, and how
* [docs/licensing.md](docs/licensing.md) — MIT core, external GPL solvers, process boundary
* [docs/roadmap.md](docs/roadmap.md) — phases and open work

## Licence

MIT for this project. The solvers it drives keep their own licences and are
invoked as separate processes. See [docs/licensing.md](docs/licensing.md).
