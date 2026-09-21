# Capabilities, and how this compares

This document states what OpenAntenna Studio can actually do today, what it
cannot, and how it relates to other open-source tools and to the published
literature. Capability claims are labelled:

* **implemented** — the code exists and is exercised by the test suite;
* **executed** — it has been run against real hardware/software at least once;
* **calibrated** — its numerical output has been checked against an independent
  reference. *Nothing in this project is calibrated yet.*

## 1. Capability matrix

| Capability | State | Evidence |
|---|---|---|
| Neutral, JSON-serialisable project model (substrate stackup, patch, array, sweep) | implemented | `model/project.py`, round-trip and validation tests |
| Material library with eps_r / mu_r / tan delta / conductivity / density | implemented | `materials/library.py`, 7 built-ins |
| Frequency-dependent material definitions (Debye / Lorentz / Drude) | implemented | `materials/dispersion.py`, tests |
| 1-pole Debye fit from measured (f, eps', eps'') data | implemented | `fit_debye_1pole`, recovery test on synthetic data |
| Two-phase composite mixing rules (Wiener bounds, Lichtenecker, Maxwell-Garnett, Bruggeman) | implemented | `materials/mixing.py`, monotonicity + bounds tests |
| Validity warnings (percolation, Maxwell-Wagner, quasi-static) | implemented | advisory text functions, tests |
| Composite loss bounds + field-concentration caveat | implemented | `estimate_effective_tan_delta`, notes returned |
| Rectangular patch synthesis (transmission-line model) | implemented | `geometry/patch.py`, dimension tests |
| Inset-feed depth estimate | implemented | crude closed form, documented as approximate |
| Array layout (N×M, spacing in lambda0, aperture size) | implemented | `geometry/array.py`, tests |
| Array factor + principal-plane cuts + steering | implemented | pattern tests incl. 30° steering peak |
| openEMS model generation (substrate, ground, patch/array, lumped port, PML, sweep, S11 output) | executed | 4 real runs, 101/101 finite S11 points |
| Solver availability probe that refuses to fabricate results | implemented | `SolverUnavailableError` test |
| S11 metrics: return loss, VSWR, impedance, −10 dB bandwidth, Touchstone I/O | implemented | `postproc/sparams.py`, tests |
| Far-field helpers: element pattern, pattern multiplication, directivity integral, efficiency budget | implemented | `postproc/patterns.py`, tests |
| Parameter sweep enumeration + dry-run manifest | implemented | `sweep/engine.py`, CLI test counts 6 jobs |
| Result store (sqlite3) | implemented | `store/results.py`; **not yet wired into a run path** |
| CLI (10 subcommands) | implemented | CLI tests |
| **Electromagnetic accuracy** | **not calibrated** | simulated 2.26 GHz vs 2.45 GHz target (−7.8 %) |
| **Dielectric loss in the solver model** | **not implemented** | generator writes `kappa = 0` |
| Array simulation, mutual coupling, unit-cell/periodic mode | **not implemented** | geometry + array factor only |
| GUI | **not implemented** | Phase 3 |

## 2. What this tool is, in one sentence

It is a **workflow and material-exploration front-end over openEMS**, not a new
field solver. The physics engine is openEMS (FDTD). The value added is: a
solver-neutral design model, quantitative composite-material exploration with
explicit validity limits, reproducibility (every run keeps its project document
and manifest), and honest verification states.

## 3. Comparison with other open-source options

| Tool | Method | Licence | GUI | Material parameterisation | Arrays | Relative position |
|---|---|---|---|---|---|---|
| **openEMS + AppCSXCAD** | FDTD | GPL-3.0 / LGPL-3.0 | yes (AppCSXCAD) | `SetMaterialProperty(epsilon, mue, kappa, sigma)`; dispersive material documented | geometry-level only | The engine we drive. AppCSXCAD is a geometry GUI; it does not do composite mixing rules, parameter sweeps or coupling reports |
| **Meep** | FDTD | GPL-3.0 | no (script-first) | strong dispersive/anisotropic support | scripting | More mature as a photonics library; steeper learning curve for RF antenna work |
| **Palace** | FEM | open source | no | FEM material assignment | yes | Higher-order FEM, closer to an HFSS-class engine; heavier to set up |
| **nec2++ / PyNEC** | MoM (NEC-2) | GPL-2.0 | no (library) | wire segments, limited dielectric | excellent for wire arrays | Planned second adapter here for wire antennas |
| **xnec2c** | MoM | GPL | GTK GUI | NEC cards | yes | Mature NEC GUI, but NEC-2 era workflow and no planar/dielectric stackup |
| **4NEC2 / MMANA-GAL** | MoM | freeware, not open source | yes | NEC cards | yes | Popular Windows tools; not open source, so not a platform to build on |
| **scikit-rf** | network/circuit | BSD-style | no | n/a | n/a | Complements us: S-parameter handling, calibration, feed networks |
| **Gmsh** | meshing | open source | yes | n/a | n/a | Candidate for CAD import into mesh-based solvers |

Published overviews of this landscape confirm the split we rely on: FDTD avoids
large matrix inversion and handles broadband problems naturally, while MoM/FEM
suit resonant and electrically small structures (Fedeli et al., 2019;
epsilonforge, 2025). Practical reports also show the flip side: users routinely
find openEMS results differ from measurement unless the model, ports and meshing
are done carefully (ResearchGate discussion on openEMS vs PCB trace antenna
measurements).

**Conclusion of the comparison:** the individual engines are strong and mature.
What is missing across the ecosystem is exactly what this project targets — a
modern, reproducible front-end with material-level design exploration and
documented validity limits. That is a workflow contribution, not a physics
contribution, and it should be described that way.

## 4. Where our observed numbers sit in the literature

Our first real run gave a resonance 7.8 % below the transmission-line
prediction. That is not automatically a bug, because the literature says the
transmission-line model is known to be biased:

* Sengupta (1983) notes the transmission-line model predicts a resonant
  frequency that is **lower** than measured and cannot account for the
  dependence of resonance on the patch aspect ratio (NASA ADS record).
* The widely used rule of thumb is that a patch designed for 100 MHz actually
  resonates near 96 MHz (antenna-theory.com) — a ~4 % downward shift.
* A practitioner report on a probe-fed patch designed for 900 MHz obtained
  869 MHz in a commercial full-wave tool — also ≈ 3–4 % low (ResearchGate).

So a few percent of downward shift is normal when moving from closed-form
synthesis to a full-wave model, and our 7.8 % is at the high end of that range.
Two candidate mechanisms remain unseparated: a coarse/non-uniform mesh
(numerical dispersion) and probe-feed loading, plus possible finite-ground-plane
effects. **This is a candidate explanation, not a confirmed root cause**, and it
is the next experiment to run (mesh-convergence + feed study, plus a comparison
against the openEMS-shipped `Simple_Patch_Antenna.py` tutorial for 2.4 GHz).

## 5. Composite substrates: what the literature says about the trade-off

The "high eps_r with low loss" goal is a well-studied tension, and the
literature frames it the same way this toolkit does:

* High-permittivity ceramic-polymer composites are pursued for substrate use,
  with the ideal substrate described as needing low dielectric loss, an
  *optimum* (not maximum) permittivity, and good thermal and mechanical
  properties (Subodh et al., 2009).
* Epoxy-type hosts are common but lossy by comparison — a recently published
  figure cites tan delta ≥ 0.02 for epoxy dielectrics, which is why
  filler engineering is needed (Calisir et al., 2025).
* Porous/ceramic-polymer routes are used to push permittivity and loss in
  opposite directions, at the cost of mechanical strength and process control
  (Zhang et al., 2025).
* High-permittivity, low-loss ceramics are marketed specifically for patch
  miniaturisation, i.e. the size/bandwidth/efficiency trade-off is the product
  (MWRF, ceramic substrate shrinks patch antenna).

None of the published results we found report a composite that raises eps_r
without paying in loss or bandwidth. That is consistent with the field-
concentration note printed by `estimate_effective_tan_delta()`: to raise eps_r
you add a high-permittivity phase, and that phase brings loss and dispersion.

## 6. Honest gaps

1. No independent calibration yet — no measured data, no cross-solver
   comparison, no reference-case regression. Until then, treat every simulated
   number as a model output under test.
2. Loss is absent from the solver model, so no efficiency or gain result from
   this tool is meaningful yet.
3. Arrays are geometry + array factor only; coupling is not computed.
4. The composite rules are quasi-static estimates; the toolkit prints their
   limits rather than pretending they are measurements.
5. Our own accuracy against a *measured* antenna has never been assessed.

## Sources (searched 2026-09-21)

* openEMS documentation, `Simple_Patch_Antenna` tutorial — https://docs.openems.de/python/openEMS/Tutorials/Simple_Patch_Antenna.html
* openEMS project (GPL-3.0) and Windows build — https://github.com/thliebig/openEMS-Project
* Fedeli, A. et al. (2019), *Open-Source Software for Electromagnetic Scattering*, MDPI — https://www.mdpi.com/
* epsilonforge (2025), *Open-Source Electromagnetic Simulation: FDTD, FEM, MoM* — https://www.epsilonforge.com/
* ResearchGate discussion, openEMS results vs measurement for a PCB trace antenna — https://www.researchgate.net/post/How_can_we_explain_the_fact_that_OpenEMS_simulation_results_differ_from_the_experimental_results_for_a_PCB_trace_antenna_test
* Sengupta, D. (1983), *The transmission line model for rectangular patch antennas* — https://ui.adsabs.harvard.edu/
* antenna-theory.com, *Microstrip (Patch) Antennas* (100 MHz design resonating near 96 MHz) — https://www.antenna-theory.com/
* ResearchGate, probe-fed patch designed 900 MHz resonating 869 MHz in a full-wave tool — https://www.researchgate.net/
* Subodh, G. et al. (2009), *Dielectric response of high permittivity polymer ceramic* — https://pubs.aip.org/
* Calisir, I. et al. (2025), *Designing a filler material to reduce dielectric loss in epoxy* — https://pubs.rsc.org/
* Zhang, K. et al. (2025), *Ultra-lightweight porous ceramic–polymer composites* — https://www.sciencedirect.com/
* MWRF, *Ceramic Substrate Shrinks Patch Antenna* — https://www.mwrf.com/

Page-level sources were retrieved through the AutoGLM search/open-link stack;
URLs are given as returned by the search provider. Where a claim rests on a
snippet rather than the full text, it is stated conservatively above.
