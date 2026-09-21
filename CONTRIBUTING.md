# Contributing

## Getting set up

```powershell
# 1. Clone, then create the environment and install the optional analysis deps
git clone <repo-url> OpenAntenna
cd OpenAntenna
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

`bootstrap.ps1` creates `.venv`, installs the pinned analysis dependencies and,
if `OPENEMS_ROOT` points at an openEMS installation, installs the matching
solver wheels too. Everything except the solver is optional: the core and the
test suite run on a bare Python.

To run simulations you also need the openEMS Windows package (or a Linux build):

1. Download `openEMS_x64_*_msvc.zip` from
   <https://github.com/thliebig/openEMS-Project/releases> and unzip it, e.g. to
   `D:\OpenAntenna\tools\openEMS`.
2. Set the environment variable so the toolkit can find it:

   ```powershell
   $env:OPENEMS_ROOT = "D:\OpenAntenna\tools\openEMS"
   ```

   This is required because Python >= 3.8 does not search `PATH` for the native
   DLLs of extension modules. Never commit the solver directory.

## Repository layout

| Path | Contents |
|---|---|
| `openantenna/materials/` | material library, composite mixing rules, dispersion models |
| `openantenna/model/` | the neutral, solver-independent project model |
| `openantenna/geometry/` | analytic element and array geometry |
| `openantenna/solvers/` | solver adapters (openEMS today) |
| `openantenna/postproc/` | S-parameters, patterns, efficiency |
| `openantenna/sweep/`, `openantenna/store/` | sweep enumeration, result storage |
| `openantenna/cli.py` | command line entry point |
| `tests/` | standard-library `unittest` suite |
| `docs/` | architecture, materials, verification, licensing, roadmap |

## Ground rules

1. **Run the tests before opening a pull request.**

   ```powershell
   .venv\Scripts\python.exe -m unittest discover -s tests -v
   ```

2. **Keep the core dependency-free.** The core package and the tests import
   nothing outside the standard library. If a new dependency is genuinely
   unavoidable, propose it in an issue first and keep it behind an optional
   import so the core still works without it.

3. **Every behaviour change needs a test.** The suite has already caught real
   defects that would otherwise have shipped silently (a crash in the composite
   loss function, a sign-convention bug in the Debye fit). Geometry, material,
   generation and parsing changes are all testable without a solver — do that.

4. **Never claim more than you verified.** Use these words precisely:
   *observed*, *candidate*, *reproduced*, *confirmed*. A generated model is
   `"verified": false` until a real run produced results, and a run that hit the
   timestep cap is not converged. See `docs/verification.md` for the format.

5. **Respect the licensing boundary.** Do not vendor, copy or commit any part of
   openEMS, CSXCAD or nec2++. The MIT core drives them as external processes;
   see `docs/licensing.md`.

6. **No credentials, tokens, keys or personal paths** in commits. Prefer
   `OPENEMS_ROOT` and relative paths.

## Where changes usually belong

| You want to | Touch |
|---|---|
| add a substrate material | `materials/library.py` (+ row in `docs/materials.md`, + test) |
| add a mixing rule or fix one | `materials/mixing.py` (+ test proving bounds/monotonicity) |
| improve dispersion fitting | `materials/dispersion.py` (+ recovery test on synthetic data) |
| add an element shape | `geometry/` (+ dimension assertions against an analytic limit) |
| add a solver | `solvers/<name>.py` implementing `SolverAdapter`, + licensing note |
| change generated solver input | `solvers/openems.py` (+ a static-inspection test) |
| add a CLI command | `openantenna/cli.py` (+ a subprocess test in `tests/test_cli.py`) |

## Sharing simulation results

A run directory is self-describing:

```
runs/<name>/project.json      exact input document
runs/<name>/sim.py            generated model script
runs/<name>/run_manifest.json mesh, loss model, warnings, "verified": false
runs/<name>/s11.csv           parsed port result
runs/<name>/run.stdout.log    solver log (keep when reporting a discrepancy)
```

When reporting a result, attach `project.json`, `run_manifest.json`, `s11.csv`
and the solver log tail. A conclusion without its run manifest cannot be
reproduced by anyone else.
