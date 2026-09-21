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

## Calibration progress

### Mesh convergence — first data point (2026-09-21)

| Run | Mesh | Cells | Resonance | \|S11\| | VSWR | Fractional BW |
|---|---|---|---|---|---|
| v4 | 15 cells/lambda, 8 substrate cells | 15,876 | 2.260 GHz | −13.32 dB | 1.550 | 0.995 % |
| v5 | 25 cells/lambda, 12 substrate cells | 124,620 | 2.280 GHz | −15.12 dB | 1.425 | 1.188 % |

Refining the mesh by roughly 8x in cell count moved the resonance by **+0.9 %**
(2.260 → 2.280 GHz) and improved the match. A mesh-induced numerical-dispersion
offset of this size cannot account for the 7.8 % gap to the 2.45 GHz synthesis
target, so **mesh dispersion is eliminated as the dominant candidate** for this
geometry. Remaining candidates: feed loading (inset/probe) and bias in the
transmission-line synthesis model, which the literature documents as a
few-percent downward bias.

### Dielectric loss is now in the model

`--loss-model kappa` maps the material loss tangent to an equivalent constant
conductivity, exact at the sweep centre and drifting as 1/f:
`kappa = 2*pi*f0*eps0*eps_r*tan_delta`. For PTFE on 1.6 mm at 2.45 GHz that is
`1.168e-4 S/m`. `--loss-model none` builds a lossless substrate.

Differential run, identical geometry and mesh (lossless v4 vs lossy):

| Run | Loss | Resonance | \|S11\| | Fractional BW |
|---|---|---|---|---|
| v4 | none | 2.260 GHz | −13.32 dB | 0.995 % |
| calib_loss_kappa | kappa = 1.168e-4 S/m | 2.270 GHz | −14.44 dB | 1.157 % |

The loss term measurably changes the result and widens the band — the expected
direction for a partially mismatched antenna, where added loss improves the
match and lowers Q. This demonstrates that the loss path is **active**; it does
**not** validate the absolute loss value (that needs a reference with a known Q
or a measurement).

## Issue 6 - air-domain / absorber proximity (candidate eliminated)

| Run | Air margin (side / top) | Domain (mm) | Cells | Resonance | \|S11\| | VSWR |
|---|---|---|---|---|---|---|
| v4 (reference) | 0.20 / 0.30 lambda | 149 x 141 x 52 | 15,876 | 2.260 GHz | -13.32 dB | 1.550 |
| air_margin_0.5 | 0.50 / 0.60 lambda | 209 x 201 x 112 | 121,900 | 2.220 GHz | -17.64 dB | 1.302 |

Enlarging the domain by ~3.8x (PML pushed 2.5x further away) moved the resonance
**down** by 1.8 % - the opposite of what is needed to explain a 7.8 % deficit -
while improving the match. The "PML is too close" hypothesis is eliminated.

Status after this batch: **mesh refinement, feed loading and air-domain
proximity are all eliminated** as explanations for the offset on this geometry.
The remaining candidate is bias in the analytic synthesis itself for a very wide
patch (W/h = 30.7, W = 0.40 lambda0, eps_eff evaluated as 2.016 against a
substrate eps_r of 2.1). That is a *candidate*, not a confirmed cause; the
engineering response is a tuning loop (`scripts/auto_tune.py`) that corrects the
synthesis empirically and records every iteration, rather than chasing unbounded
accuracy out of a closed-form model.

## Tuning loop: the synthesis offset is corrected empirically (2026-09-21)

With mesh refinement, feed loading and air-domain proximity all eliminated as
explanations (Issues 1-6 above), the residual offset is an attribute of the
analytic synthesis for this very wide patch.  The engineering answer is a tuning
loop (``scripts/auto_tune.py``): synthesise, simulate, measure, rescale the length
by ``f_measured / f_target``, repeat.

| Iteration | Patch length | Resonance | Offset | \|S11\| | VSWR |
|---|---|---|---|---|---|
| 1 (synthesis) | 41.379 mm | 2.266 GHz | -7.5 % | -12.54 dB | 1.618 |
| 2 | 38.275 mm | 2.389 GHz | -2.5 % | -10.64 dB | 1.832 |
| 3 | 37.319 mm | **2.426 GHz** | **-1.0 %** | -10.27 dB | 1.884 |

Converged within 1 % in **three** FDTD runs.  The practical consequence: for this
geometry the transmission-line synthesis needs a **-9.8 % length correction**
(41.379 -> 37.319 mm) before the design resonates where intended.

Caveat that must travel with this result: the loop tunes the *resonance* only.
The match at the converged point is VSWR 1.88, so the feed needs its own tuning
(``scripts/tune_inset.py``).  Nothing here validates the absolute accuracy of the
model; it makes the model usable by correcting a known bias.

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
  converged-looking case; mesh refinement was ruled out as the dominant cause,
  and a feed study plus an external tutorial anchor are the next measurements.
* Dielectric loss is represented as an equivalent conductivity, but has never
  been validated against a reference with a known Q or against measurement; use
  it for relative comparisons only.
* Array behaviour (mutual coupling, unit-cell/periodic mode) has never been
  simulated.
* `store/results.py` has unit-level coverage only; it is not yet wired into a
  CLI run path.

## Issue 5 — the 7.8 % resonance offset: candidate elimination (2026-09-21)

Four measurements were run. The reference is the lossless 2.45 GHz PTFE patch
(W = 49.143 mm, L = 41.379 mm, eps_eff = 2.0164, dL = 0.854 mm, inset = 14.658 mm).

| Test | Variable | Resonance | \|S11\| | VSWR | Verdict |
|---|---|---|---|---|---|
| v4 (reference) | 15 cells/lambda, 8 substrate cells | 2.260 GHz | -13.32 dB | 1.550 | baseline |
| v5 | 25 cells/lambda, 12 substrate cells (8x the cells) | 2.280 GHz | -15.12 dB | 1.425 | mesh refinement moves it +0.9 % only |
| feed half | inset 7.33 mm (0.5x estimate) | 2.290 GHz | -6.99 dB | 2.619 | match collapses, resonance does not move |
| feed 1.5x | inset 21.99 mm (1.5x estimate) | 2.260 GHz | -0.58 dB | 29.71 | match collapses, resonance does not move |
| feed edge | inset ~ 0 (radiating edge) | aborted | - | - | see note below |
| **tutorial anchor** | **openEMS-shipped Simple_Patch_Antenna.py, unmodified** | **2.435 GHz** | **-27.02 dB** | **1.093** | design frequency 2.4 GHz: +1.5 %, excellent match |

Two conclusions are supported by this table:

1. **Mesh dispersion is not the cause.** An 8x refinement moved the resonance by
   0.9 %, far too little to explain 7.8 %.
2. **Feed loading is not the cause.** Sweeping the inset over a 3x range moved
   the resonance by at most 1.3 % while the match changed from -13 dB to -0.6 dB.
   (The inset estimate is therefore directionally sound: the synthesised value
   gave the best match of the three.)
3. **The solver and the workflow are capable of the accuracy we are missing.**
   The unmodified openEMS tutorial model of the same class of antenna landed on
   2.435 GHz against a 2.4 GHz design with -27 dB and VSWR 1.09.

The remaining difference therefore sits in **our** model construction, not in
openEMS, the mesh or the feed. Remaining candidates, in order of leverage:

* **air domain / absorber proximity** - our margin is 0.20 lambda on the sides
  and 0.30 lambda above; the tutorial's domain is far more generously meshed in
  the vertical direction (45 z cells vs our 21). A too-close PML loads the
  antenna and pulls the resonance down.
* **wide-patch validity of the transmission-line synthesis** - at W/h = 30.7 and
  W = 0.40 lambda0 the patch is outside the range where the Hammerstad-type
  fringe and eps_eff fits were validated, and eps_eff came out at 2.016, *below*
  the substrate eps_r of 2.1, which lengthens the synthesised patch.

Note on the aborted edge case: feeding exactly at the radiating edge (inset ~ 0)
did not converge in a reasonable time (10 minutes with no result vs ~4 minutes
for the other cases) and was terminated deliberately. That configuration is
degenerate for a lumped-port feed and should be modelled differently (e.g. an
edge-feed transmission line) rather than by pushing the inset to zero.
