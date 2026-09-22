# Calibration record (Phase 1 close-out)

Everything in this file is measured on this machine with openEMS v0.37.0-rc2. Each
number names **the reference it was measured against** and **the construction recipe
it belongs to**; mixing references in one table is what produced a wrong conclusion
earlier (see "Corrections" below).

## 1. What is calibrated, and what is not

| Layer | State | Evidence |
|---|---|---|
| Analytic layer (synthesis, cavity predictor, mixing rules, dispersion) | **accurate to <= 0.1 %** against closed-form and against an independent re-implementation | golden-value tests: dipole D = 1.6409, Balanis Ex. 14.1 (W 11.850, eps_eff 1.9715, dL 0.8110, L 9.053 mm), cavity predictor cross-checked at 112 grid points to 0.000000 % |
| Solver-model layer (our generated FDTD model vs an independent model of the same antenna) | **2 - 5 % low**, geometry/recipe dependent | separating experiment and construction A/B below |
| Design targeting (does the fabricated dimension land on the wanted f0?) | **<= 0.02 %** after the tuning loop | `runs/auto_tune_summary.json`, three iterations |

The distinction matters: the tool can place a design on a target frequency very
precisely, but the absolute accuracy of any single untuned model is a few percent.

## 2. Model bias against a single reference (the cavity predictor)

Same construction recipe per row (default mesh, ground margin 0.25 lambda0, metal-edge
snapping on, air margin 0.80 lambda0):

| Geometry | W/h | our FDTD | cavity prediction | deviation |
|---|---|---|---|---|
| 2.45 GHz, eps_r 2.1, h 1.6 mm | 30.7 | 2.2810 GHz | 2.4007 GHz | **-4.99 %** |
| 5.80 GHz, eps_r 2.2, h 0.787 mm | 26.0 | 5.3841 GHz | 5.6615 GHz | **-4.90 %** |
| 5.80 GHz, eps_r 4.4, h 1.6 mm | 9.8 | 5.1962 GHz | 5.4189 GHz | **-4.11 %** |

The bias is **not a single constant**: with a different recipe the same comparison
gives -2.31 % (tutorial geometry, 40 x 32 mm, eps_r 3.38, mesh 20 cells/lambda,
4 substrate cells, ground margin 0.098 lambda0). The spread across recipes is 2.7
percentage points.

## 3. Construction A/B: which recipe element matters

Tutorial geometry, everything except one setting held fixed:

| Setting | Resonance | vs cavity | Timesteps |
|---|---|---|---|
| port_refine = off | 2.3641 GHz | -2.97 % | 23,424 |
| port_refine = on | 2.3504 GHz | -3.53 % | 24,180 |

Earlier, on the same geometry with all other settings equal: metal-edge snapping moved
the resonance from 2.330 to 2.380 GHz (a 2.1-point change), while boundary type (PML vs
MUR), PML depth, domain size and mesh grading changed nothing measurable (all 2.330 GHz).

**Reading:** of the construction elements tested, metal-edge snapping is the big one
(half of the original 4.31 % gap), port refinement is a ~0.6 % effect, and the rest of
the solver settings are irrelevant at this level.

## 4. Design targeting: the tuning loop

PTFE 2.45 GHz patch, default recipe, target 2.4500 GHz, tolerance 0.1 %:

| Iteration | patch length | inset | refined resonance | error | VSWR |
|---|---|---|---|---|---|
| 1 (synthesis) | 41.379 mm | 11.196 mm | 2.5232 GHz | **+2.99 %** | 1.035 |
| 2 | 38.433 mm | 11.530 mm | 2.4582 GHz | **+0.333 %** | 1.199 |
| 3 | 38.561 mm | 11.568 mm | 2.4496 GHz | **-0.018 %** | 1.098 |

Converged in three FDTD runs. The sub-grid refinement (parabolic interpolation around
the |S11| minimum) is what makes this possible: the raw sweep grid at 101 points only
locates the minimum to ~0.4 %.

**Per-recipe correction for this case:** the tuned length is **0.9316 x** the
analytically synthesised length. That factor is a property of *this geometry and this
recipe*; it must not be reused blindly for another design.

## 5. Sources of uncertainty that no amount of solver tuning removes

1. **Material data.** PTFE datasheets give eps_r 2.0 - 2.1; that 5 % spread alone moves
   the resonance by ~1.2 %. Home-made composites are worse.
2. **Analytic-model disagreement.** The transmission-line and cavity predictors differ
   by 2 - 3.8 % for the same geometry, so "the synthesis is wrong" is only meaningful
   relative to a chosen predictor.
3. **Conductor loss is not modelled** (metals are ideal PEC), so efficiency numbers
   exclude ohmic loss.
4. **Waveport/feed realisation.** Our feed is a vertical lumped port (probe). A
   coplanar inset line is a different structure and is not modelled yet.

## 6. Corrections made to earlier claims in this project

| Claim | Status |
|---|---|
| "The bias is not explained by mesh, feed loading or the air domain" | **stands**: each was varied and none moved the resonance materially |
| "The 7.8 % offset is mostly metal-edge snapping" | **half of it** (4.31 % -> 2.26 % on that recipe) |
| "The bias is roughly constant per recipe, -4.1 to -5.0 %" | **withdrawn**: it mixed two reference types; with one reference the spread is 2.7 points |
| "port_refine breaks the model" | **withdrawn**: the failures were `WinError 32` file locks caused by an orphaned child process of an earlier launch still holding the run directory (killing a launcher does not kill its child). Port refinement itself is fine - see section 3. |

## 7. How to reproduce any row here

```powershell
$env:OPENEMS_ROOT = "<folder with openEMS.exe>"
python scripts/generalisation_test.py            # section 2
python scripts/construction_ab_test.py           # section 3 (metal-edge snapping)
python scripts/port_refine_ab_test.py            # section 3 (port refinement)
python scripts/auto_tune.py 2.45 0.1 5           # section 4
```

Every run keeps its `project.json`, `run_manifest.json` (recipe, mesh, loss model,
convergence) and `s11.csv`, so a number can always be traced back to its inputs.
