# Benchmark and reference cases

The point of this file is to answer the one question a sceptical reader asks first:
**"how do I know any of these numbers are right?"**  Every row states what is
being checked, what the reference is, and whether the check currently passes.

Status words follow `docs/verification.md`: a check is only claimed when something
was actually executed.

## 1. Analytic references (no solver needed — standard library only)

| # | Quantity | Reference value | Where the check lives | Status |
|---|---|---|---|---|
| B1 | Isotropic directivity | 1.0 | `tests/test_patterns.py` (golden) | passing |
| B2 | Short-dipole directivity | 1.5 | `tests/test_patterns.py` | passing |
| B3 | Half-wave dipole directivity | 1.6409 (exact integral; Balanis quotes 1.643) | `tests/test_patterns.py` | passing |
| B4 | Rectangular patch, Balanis Ex. 14.1 (εr 2.2, h 1.588 mm, 10 GHz) | W 11.86 mm, ε_eff 1.972, L 9.06 mm | `tests/test_patch.py` (`test_balanis_example_14_1_golden_values`) | passing (±1 %) |
| B5 | ΔL coefficient | 0.412 h form | `tests/test_patch.py` | passing |
| B6 | Narrow-line Hammerstad term | +0.04(1−W/h)² | `tests/test_patch.py` | passing |
| B7 | Two-element λ/2 array factor | null at θ=90°, max 2 at θ=0° | `tests/test_array.py` | passing |
| B8 | Uniform 4×4 broadside array factor | 16 | `tests/test_array.py` | passing |
| B9 | Loss-tangent sign convention | ε″ < 0, tan δ > 0 | `tests/test_dispersion.py` | passing |
| B10 | Debye 1-pole fit round-trip on exact data | parameters recovered, rmse ~1e-9 | `tests/test_dispersion.py` | passing |

These are *implementation* checks: they pin the code against textbook formulas.
They say nothing about the accuracy of the field solver.

## 2. Solver references (need openEMS + OPENEMS_ROOT)

| # | Case | Reference | Result so far | Status |
|---|---|---|---|---|
| S1 | openEMS-shipped `Simple_Patch_Antenna.py`, unmodified | its own 2.4 GHz design | 2.435 GHz, −27 dB, VSWR 1.09 | executed |
| S2 | **our generator on the tutorial geometry** | S1 | 2.380 GHz (−2.26 % after metal-edge snapping; was −4.31 %) | executed, bias isolated |
| S3 | our generator on the 2.45 GHz PTFE patch | cavity model 2.4007 GHz | 2.260–2.280 GHz | executed, **not calibrated** |
| S4 | mesh refinement (15 → 25 cells/λ, 8× cells) | — | +0.9 % shift | executed |
| S5 | feed-inset sweep (0.5× / 1× / 1.5×) | — | ±1.3 % resonance shift | executed |
| S6 | air-domain margin (0.20 → 0.50 λ) | — | −1.8 % (hypothesis eliminated) | executed |
| S7 | ground-plane margin (0.25 / 0.50 / 1.00 λ) | — | 2.260 / 2.220 / 2.150 GHz | executed, confound remains |
| S8 | boundary/mesh-smoothing A/B (PML/MUR, smoothing 1.01) | — | invariant (−4.31 % in all) | executed |
| S9 | port-region mesh refinement (`port_refine`, A4) | — | **not yet run** | generated, untested |

## 3. What is still missing (agreed plan)

1. **A second geometry for S2** — is the remaining −2.26 % a constant factor or
   geometry-dependent?  Script: `scripts/generalisation_test.py`.
2. **A benchmark set, not a single anchor.** The minimum credible set for a
   planar-antenna tool: rectangular patch (have it), **inverted-F antenna**,
   **microstrip line (ε_eff / Z0)**, **Wilkinson power divider**, and one
   measurement-backed case.  Only the first exists today.
3. **Near-to-far-field (NF2FF)** in the generated model, so `postproc/patterns.py`
   (currently analytic only) can be compared with a solver field.  Without it no
   gain / pattern claim from the solver is possible.
4. **Convergence acceptance**: record in the manifest whether `EndCriteria` was
   met, and refuse to report a resonance from a run that hit the timestep cap.

## 4. Honest summary

Today the tool is a **verified calculator** (B1–B10, standard library) wrapped
around an **uncalibrated field model** (S2–S3: −2.26 % residual construction bias,
no measurement anchor).  Anything about resonance, efficiency or gain from the
solver should be read as a model output under test, not as a design authority.

## 5. Benchmark #2 — rectangular waveguide, TE10 cutoff (exact reference)

**Why this case.** It has an **exact** closed-form reference, `f_c = c / (2a)`, with no
fringing, no feed geometry and no dielectric — so it isolates the solver + mesh +
post-processing pipeline from the synthesis approximations.  A second, *independent*
topology is exactly what the benchmark gap needs (masukan Gemini; §3 di atas).

**Protocol** (standalone openEMS script, in the style of the tutorial anchor):

| Parameter | Value |
|---|---|
| guided medium | air (εr = 1) |
| cross-section | a = 100 mm (broad), b = 50 mm |
| analytic cutoff | **f_c = c / (2a) = 1499.0 MHz** |
| length | ≥ λg/2 at the probe frequency |
| walls | PEC on the four side walls; PML or MUR at the two ends |
| probes | point/lumped excitation below and above cutoff, read transmitted power |

**Acceptance criteria**

* f = 0.9·f_c → transmission ≲ −30 dB (evanescent),
* f = 1.3·f_c → transmission ≥ −1 dB (propagating),
* the −3 dB edge lands within **1 %** of 1499.0 MHz,
* the run reports `converged: true` and its mesh resolution in the manifest.

**Why it is worth the effort:** it exercises `prepare → run → parse` on a geometry
whose answer nobody can argue about, which is the cheapest way to earn the
credibility the project notes itself as missing.

## 6. Benchmark #3 (candidate) — microstrip line, ε_eff

A 50 Ω microstrip line has an analytic `ε_eff` (Hammerstad wide-line form, already
implemented as `geometry.patch.effective_permittivity`, plus its narrow-line
correction) and a well-known `Z0` (Wheeler/Hammerstad closed forms, **not yet in the
package**).  Blockers: the generator has no transmission-line port (the same missing
capability as Y-19, coplanar inset feed), so this benchmark needs that work first.

Order to do them: **#2 (waveguide) → Y-19 (line port) → #3 (microstrip line)**.

