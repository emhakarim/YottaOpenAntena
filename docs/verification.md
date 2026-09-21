# Verification log

What has actually been executed, and what the outcome was. Status words follow a
strict scale:

* **observed** â€” directly present in a log, a run, or the source;
* **candidate** â€” could explain the symptom but was not reproduced;
* **reproduced** â€” the same material symptom was produced again;
* **confirmed** â€” reproduced *and* removing the cause removes the symptom.

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

## Issue 1 â€” every S11 value was NaN (confirmed)

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

## Issue 2 â€” timestep collapse from thin metal (confirmed)

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
and stop coincide) â€” the standard openEMS idiom. Regression test:
`test_metal_is_a_thin_sheet`.

## Issue 3 â€” `estimate_effective_tan_delta()` crashed (confirmed)

**Observed evidence.** `NameError: name 'em' is not defined`, raised by
`materials/mixing.py`. The same defect surfaced as a non-zero exit code from
`openantenna.cli mix`.

**Cause.** Three names in the returned dictionary were never defined
(`em`, `ef`, `eps_volume`); the computed locals were `eps_m_complex`,
`eps_f_complex` and `tan_vol`.

**Fix.** Reference the actual locals. The CLI `mix` command now runs.

## Issue 4 â€” Debye fit reported meaningless residuals (confirmed)

**Observed evidence.** Fitting synthetic data generated from a *known* Debye
model (eps_inf 2.1, delta_eps 0.4, tau 1e-8) recovered the parameters correctly
but reported `rmse_total = 0.129` â€” far too large for exact-model data.

**Cause.** Sign convention mismatch. Callers supply `eps''` as a positive loss
term (that is what `_lsq_for_tau` fits and what `apparent_tan_delta()` returns),
while `debye_eps()` returns a negative imaginary part. The residual loop
subtracted `model.imag` directly, inflating every imaginary residual by about
`2*eps''`.

**Fix.** Compare against `-model.imag`. Regression test:
`test_fit_residual_is_small`.

## Calibration progress

### Mesh convergence â€” first data point (2026-09-21)

| Run | Mesh | Cells | Resonance | \|S11\| | VSWR | Fractional BW |
|---|---|---|---|---|---|
| v4 | 15 cells/lambda, 8 substrate cells | 15,876 | 2.260 GHz | âˆ’13.32 dB | 1.550 | 0.995 % |
| v5 | 25 cells/lambda, 12 substrate cells | 124,620 | 2.280 GHz | âˆ’15.12 dB | 1.425 | 1.188 % |

Refining the mesh by roughly 8x in cell count moved the resonance by **+0.9 %**
(2.260 â†’ 2.280 GHz) and improved the match. A mesh-induced numerical-dispersion
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
| v4 | none | 2.260 GHz | âˆ’13.32 dB | 0.995 % |
| calib_loss_kappa | kappa = 1.168e-4 S/m | 2.270 GHz | âˆ’14.44 dB | 1.157 % |

The loss term measurably changes the result and widens the band â€” the expected
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

## Separating experiment: our generator vs the tutorial on identical geometry

The sharpest test proposed in review (N-04 / Y-T1).  The openEMS-shipped tutorial
model, unmodified, resonates at 2.435 GHz.  Feeding **our** generator the tutorial
geometry and substrate:

| Measurement | Resonance | Notes |
|---|---|---|
| tutorial script, unmodified | 2.435 GHz | external reference, \|S11\| -27 dB |
| **our generator, same geometry** | **2.330 GHz** | \|S11\| -24.9 dB, VSWR 1.12, converged (54,136 steps) |
| cavity model, same geometry | 2.4363 GHz | agrees with the tutorial to 0.05 % |
| transmission-line model, same geometry | 2.5134 GHz | too high |

**Supported conclusion:** on identical geometry our model sits **-4.3 %** below an
independent implementation.  The bias is therefore in **our model construction**
(tuning settings, port, mesh lines) - not in the patch geometry and not in
openEMS itself.  The cavity model proved to be the better analytic predictor here.

### Ground-plane margin (N-01) - measured, hypothesis eliminated

Ground margin 0.25 / 0.50 / 1.00 lambda0 with everything else fixed:
2.260 / 2.220 / 2.150 GHz.  A larger ground plane moves the resonance **down**
monotonically and had not saturated at 1.0 lambda0, so the finite ground plane is
not the cause of the deficit (it actually raises the resonance relative to a large
ground).  The effect is real (~5 %) and is now a knob
(`--ground-margin-lambda`).

### Is the |S11| minimum the patch resonance?

`scripts/analyze_resonance.py` reads stored traces and compares max Re(Zin), the
Im(Zin) zero crossing and the |S11| minimum.  In every run the three coincide to
within one sweep step (R ~ 33-35 ohm), so the minimum **is** the patch resonance,
not a feed artefact.  Convergence state is now reported per run (`converged`,
`timesteps`) instead of being invisible.

## Construction A/B: the cause of the 4.31 % offset, found and half-fixed

Five construction settings were varied one at a time on the tutorial geometry
(40 x 32 mm, eps_r 3.38, h 1.524 mm; tutorial reference 2.435 GHz):

| Configuration | Resonance | vs tutorial |
|---|---|---|
| ours (PML_8, margin 0.20/0.30) | 2.330 GHz | -4.31 % |
| MUR boundary | 2.330 GHz | -4.31 % |
| PML_8, margin 0.80/0.80 (domain ~200 mm) | 2.330 GHz | -4.31 % |
| MUR + big domain | 2.330 GHz | -4.31 % |
| quasi-uniform mesh (smoothing 1.01) | 2.330 GHz | -4.31 % |
| **metal edges snapped (`AddEdges2Grid`, new default)** | **2.380 GHz** | **-2.26 %** |
| metal edges NOT snapped (explicit control) | 2.330 GHz | -4.31 % |

Two conclusions, both evidence-backed:

1. **The entire numerical-settings class is eliminated.** Boundary type, PML depth,
domain size and mesh grading leave the resonance pinned at exactly 2.330 GHz
(within the 10 MHz sweep step). No amount of solver tuning explains the offset.
2. **Metal-edge snapping accounts for about half of it.** A degenerate
(zero-thickness) patch sheet can be snapped to the neighbouring cell, which
changes the effective patch size. Calling `FDTD.AddEdges2Grid(...)` on the ground
and on every patch - the practice used by the openEMS tutorial - moves the
resonance from 2.330 to 2.380 GHz. This is now the generator default and is covered
by a test.

Residual gap: -2.26 % (2.380 vs 2.435 GHz). Still open, and no longer attributed
to solver settings. Remaining structural candidates: the ground-plane footprint
(the tutorial uses 60 x 60 mm; our single-margin knob produces 64 x 56 mm for this
patch), the feed realisation, and mesh-line placement details.

## Generalisation: is the construction bias a constant factor?

Three geometries, identical construction settings (default mesh, ground margin
0.25 lambda0, metal-edge snapping on), each compared with the cavity predictor:

| Geometry | Cavity prediction | Measured (our generator) | Deviation vs cavity |
|---|---|---|---|
| 2.45 GHz, eps_r 2.1, h 1.6 mm (W/h 30.7) | 2.4007 GHz | 2.28100 GHz | **-4.99 %** |
| 5.80 GHz, eps_r 2.2, h 0.787 mm (W/h 26.0) | 5.6615 GHz | 5.38414 GHz | **-4.90 %** |
| 5.80 GHz, eps_r 4.4, h 1.6 mm (W/h 9.8) | 5.4189 GHz | 5.19622 GHz | **-4.11 %** |

The spread is small: -4.1 to -5.0 % across a 2.4x range in frequency, a 2.1x range in
eps_r and a 3.1x range in W/h.  That supports a **single systematic factor** rather than
a geometry-dependent one, so a one-off calibration is defensible *for a fixed
construction recipe*.

One measurement does not fit a universal constant: the tutorial-geometry anchor gave
**-2.31 %** (2.380 vs 2.4363 GHz), but that run used a different recipe (mesh 20
cells/lambda, 4 substrate cells, ground margin 0.098 lambda0).  Combined with the
measured ground-margin sensitivity (~1.3 % per doubling), the factor is best read as
*constant for a given recipe*.

**Practical consequence:** calibrate once per construction recipe and verify it; keep
the synthesis -> simulate -> correct loop (`scripts/auto_tune.py`, converged in three
runs) as the authoritative workflow, because it does not depend on which recipe was
calibrated.

Earlier in this document a two-point result was read as "the bias is
geometry-dependent".  The third point and the recipe difference show that reading was
premature; it is corrected here.
## Test suite

```
python -m unittest discover -s tests
Ran 128 tests in 3.6s
OK
```

Tests are standard-library only and do not require a solver, numpy or a network.
The openEMS tests parse and statically inspect a generated script; they
deliberately do **not** claim to have executed it.

## Open, unverified items

* The generated openEMS model is **not** calibrated to better than about 2 %: the
  separating experiment and the construction A/B narrowed the offset against an
  independent implementation from -4.31 % to -2.26 %. The residual is attributed
  to structural differences (ground footprint, feed realisation, mesh-line
  placement), not to solver settings, which were eliminated as a class.
* Dielectric loss is represented as an equivalent conductivity, but has never
  been validated against a reference with a known Q or against measurement; use
  it for relative comparisons only.
* Array behaviour (mutual coupling, unit-cell/periodic mode) has never been
  simulated.
* `store/results.py` is wired into `sweep run` and covered by the sweep-runner
  tests; there is no separate CLI `run` command yet.

## Issue 5 â€” the 7.8 % resonance offset: candidate elimination (2026-09-21)

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
