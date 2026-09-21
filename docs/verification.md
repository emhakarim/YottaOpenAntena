# Verification log

What has actually been executed, and what the outcome was. Status words follow a
strict scale:

* **observed** — directly present in a log, a run, or the source;
* **candidate** — could explain the symptom but was not reproduced;
* **reproduced** — the same material symptom was produced again;
* **confirmed** — reproduced *and* removing the cause removes the symptom.

## Environment

Run on Windows, Python 3.13.15 (venv), openEMS v0.37.0-rc2 (official Windows
package `openEMS_x64_v0.37.0-rc2_msvc.zip`, 59.7 MB, from
`https://github.com/thliebig/openEMS-Project/releases`).

Installed into the venv from the packages's own wheels:
`csxcad-0.7.0rc2-cp313-cp313-win_amd64.whl`, `openems-0.37.0rc2-cp313-cp313-win_amd64.whl`,
plus numpy / scipy / matplotlib / pytest / scikit-rf / h5py.

### Import failure on Windows (observed -> confirmed)

```
ImportError: DLL load failed while importing CSXCAD: The specified module could not be found.
```

`PATH` did not help. Cause: since Python 3.8, extension modules do not search
`PATH` for dependent DLLs. Counterfactual check: calling
`os.add_dll_directory(r"...\tools\openEMS")` before the import makes both
`CSXCAD` and `openEMS` import cleanly. Fix is in the adapter and in every
generated script (`OPENEMS_ROOT`).

## Issue 1 — every S11 value was NaN (confirmed)

**Symptom.** The first generated model ran to completion (200,000 timesteps,
146 s) and wrote a `s11.csv` in which all 101 rows were `nan`.

**Observed evidence.**

```
Operator_Ext_UPML::Create_UPML: Warning: Not enough lines in direction: 2, resetting to PEC
Warning: Unused primitive (type: Box) detected in property: port_excite_1!
FDTD simulation size: 41x41x7 --> 11767 FDTD cells
DEBUG uf_inc max: 0.0        (diagnostic re-run with cleanup disabled)
RuntimeWarning: invalid value encountered in divide
```

**Cause.** The generated mesh covered only the substrate and the metal; there
was no air region, so the absorbing boundary had nothing to absorb, openEMS fell
back to a PEC box, and the lumped-port excitation box was never mapped onto the
grid. With no incident wave, `uf_inc = 0` and `S11 = 0/0`.

**Fix.** Add an explicit air domain (`AIRBOX_LAMBDA`, `AIR_TOP_LAMBDA`) with
mesh lines covering it, place structure edges on the mesh, and pass
`edges2grid="xy"` to `AddLumpedPort`.

**Counterfactual.** With the fix the same model produced 101/101 finite S11
values. Both guards are now regression tests
(`test_port_is_snapped_to_the_grid`, `test_meshing_covers_an_air_region`).

## Issue 2 — timestep collapse from thin metal (confirmed)

**Observed evidence.**

```
FDTD timestep is: 6.48321e-14 s
openEMS::SetupFDTD: Warning, the timestep seems to be very small --> long simulation. Check your mesh!?
```

**Cause.** Modelling the patch as a box with a physical 35 um thickness created
35 um mesh cells, which drives the FDTD timestep. The simulation covered only
~16 ns of physical time and the S11 curve was not converged (a spurious
2.27 GHz minimum with |S11| = -12.6 dB, versus a 2.45 GHz design target).

**Fix.** Model metal as an infinitely thin sheet (a degenerate box whose start
and stop coincide) — the standard openEMS idiom. Regression test:
`test_metal_is_a_thin_sheet`.

## Issue 3 — `estimate_effective_tan_delta()` crashed (confirmed)

**Observed evidence.** `NameError: name 'em' is not defined`, raised by
`materials/mixing.py`. The same defect surfaced as a non-zero exit code from
`openantenna.cli mix`.

**Cause.** Three names in the returned dictionary were never defined
(`em`, `ef`, `eps_volume`); the computed locals were `eps_m_complex`,
`eps_f_complex` and `tan_vol`.

**Fix.** Reference the actual locals. The CLI `mix` command now runs.

## Issue 4 — Debye fit reported meaningless residuals (confirmed)

**Observed evidence.** Fitting synthetic data generated from a *known* Debye
model (eps_inf 2.1, delta_eps 0.4, tau 1e-8) recovered the parameters correctly
but reported `rmse_total = 0.129` — far too large for exact-model data.

**Cause.** Sign convention mismatch. Callers supply `eps''` as a positive loss
term (that is what `_lsq_for_tau` fits and what `apparent_tan_delta()` returns),
while `debye_eps()` returns a negative imaginary part. The residual loop
subtracted `model.imag` directly, inflating every imaginary residual by about
`2*eps''`.

**Fix.** Compare against `-model.imag`. Regression test:
`test_fit_residual_is_small`.

## Test suite

```
python -m unittest discover -s tests
Ran 82 tests in 2.8s
OK
```

Tests are standard-library only and do not require a solver, numpy or a network.
The openEMS tests parse and statically inspect a generated script; they
deliberately do **not** claim to have executed it.

## Open, unverified items

* The generated openEMS model has **not** been calibrated against an independent
  reference. A ~7 % resonance shift and a weak match were observed on the first
  converged-looking case; this is unexplained, not fixed.
* Dielectric loss is not represented in the generated solver model
  (`kappa = 0`); no loss validation has been performed.
* Array behaviour (mutual coupling, unit-cell/periodic mode) has never been
  simulated.
* `store/results.py` has unit-level coverage only; it is not yet wired into a
  CLI run path.
