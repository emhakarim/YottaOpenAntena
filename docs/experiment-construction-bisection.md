# Experiment: bisection of the construction bias (diff-and-swap against the tutorial model)

**Goal.** Localise the residual construction bias measured at **−2.26 %** (tutorial geometry,
after metal-edge snapping) and **−4.99 %** (2.45 GHz PTFE patch) against the cavity
prediction. Candidate causes suggested so far — mesh density, feed position, PML/air
margin, boundary type, mesh smoothing — have all been **eliminated by measurement**;
metal-edge snapping recovered half the original −4.31 %. What remains is the model
*construction* itself.

**Method: replace one element at a time with the tutorial's version and watch the
resonance.** The openEMS-shipped `Simple_Patch_Antenna.py` is the reference: it lands
within ~1.5 % of its own design frequency and agrees with the cavity model to 0.05 %.

## 0. Rules that make the result publishable

1. **One variable per run.** Everything else (geometry, mesh settings, boundary, feed)
   stays byte-identical; the run manifests must differ in exactly one field.
2. **Two-setting convergence per point** (see `docs/convergence-policy.md`):
   `EndCriteria` 1e-2 (cap 60k) **and** 1e-3 (cap 120k). A point counts only when the two
   agree within **0.2 %**; otherwise it is a rejected data point, reported as such.
3. **Report the resonance with steps + wall-clock + convergence verdict**, never the bare number.
4. Runs are launched through `yotta_tools/parallel_batch.py` with a distinct `--tag`, so no
   two harnesses share a run directory.

## 1. Reference points (already measured, keep them)

| Model | Resonance | vs cavity |
|---|---|---|
| tutorial script, unmodified | 2.435 GHz | reference |
| our generator on the tutorial geometry | 2.380 GHz (after snapping) | −2.26 % |
| our generator on the 2.45 GHz PTFE patch | 2.281 GHz | −4.99 % |

## 2. Swap list — in this order (cheapest first)

| # | Element | Ours | Tutorial | Why it is a candidate |
|---|---|---|---|---|
| S1 | **Ground/substrate footprint** | patch + 2 × 0.25 λ0 | 60 × 60 mm on a 40 × 32 mm patch (≈ +0.25 λ0 each side at 2.4 GHz) | the finite ground plane changes the edge condition; ours is at the small end |
| S2 | **Port definition** | `AddLumpedPort(1, 50, [x,y,-h], [x,y,0], 'z', 1.0, edges2grid="xy")` | check the tutorial's exact call and port priority | a lumped port's electrical length/priority changes the feed discontinuity |
| S3 | **Mesh lines** | `linspace` + `AddLine` at patch edges | tutorial resolution (~5 mm, 4 substrate cells) | line *placement* (not density) shifts the discretised geometry |
| S4 | **Excitation / time stepping** | `SetGaussExcite(F0, 0.5·F0)`, `NrTS` 400k, `EndCriteria` 1e-4 | tutorial's settings | a wider band or a different stop rule changes the FFT window |
| S5 | **Material priorities** | air 0, substrate 1, metals 2/3, port 5 | tutorial's priorities | overlapping primitives resolve by priority; a wrong ordering silently moves a boundary |

Procedure per step: run A = ours, run B = ours-with-that-one-element-replaced. Record
`Δf = f_B − f_A`. Stop when a swap moves the resonance by ≥ 1 % — that element is then the
dominant contributor for that geometry.

## 3. Decision tree

```
Δf(S1) ≥ 1 %        -> ground-plane edge condition is the cause; sweep ground margin
                       (0.25 / 0.5 / 1.0 λ0) with the domain held constant
Δf(S2) ≥ 1 %        -> feed/port model is the cause; then B2 (coplanar inset) becomes the
                       fix, not just a feature
Δf(S3) ≥ 1 %        -> discretisation of the patch edges; refine only the metal-edge lines
Δf(S4) ≥ 1 %        -> time/frequency window; fix the settings and re-measure the bias
no swap ≥ 1 %       -> the bias is distributed; then calibrate empirically per geometry and
                       state the validity range (the honest fallback)
```

## 4. What "done" looks like

A single sentence that survives review, e.g.: *"the residual −2.26 % is dominated by the
ground-plane edge condition (S1); after using 0.5 λ0 per side on two geometries the
resonance lands within 1 % of the cavity prediction at both settings."* — or the equally
acceptable *"no single construction element dominates; the bias is geometry-dependent and
must be calibrated per design."*

Either outcome closes the gate-fabrication condition #2 (construction bias closed or
calibrated), which is currently the project's biggest blocker.
