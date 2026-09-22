# K-1 verdict: the port_refine A/B is REJECTED (and why that is the useful answer)

Run 2026-09-22, PTFE patch (2.45 GHz design), `yotta_tools/parallel_batch.py --preset port-refine`,
two settings per the convergence policy in `docs/convergence-policy.md`:

| arm | setting A: `EndCriteria` 1e-2, cap 60k | setting B: `EndCriteria` 1e-3, cap 120k | \|Δf\|/f |
|---|---|---|---|
| `port_refine` off | 2.0830 GHz (1220 s, rc 0) | 2.8170 GHz (1386 s, rc 0) | +35.2 % |
| `port_refine` on | 2.8170 GHz (1377 s, rc 0) | 2.0830 GHz (3183 s, rc 0) | −26.1 % |

**Verdict: rejected.** The acceptance rule is `|Δf|/f ≤ 0.2 %` between the two settings; the
measured disagreement is two orders of magnitude larger, and it is not even consistent *within*
one setting (the two arms swap their minima between settings).

## Why the numbers are worthless - and this is the finding

1. **`2.8170 GHz` is the sweep edge.** The sweep is 2.45 GHz ± 20 %, so `f_max = 2.9400 GHz`
   and the grid step is 4.9 MHz; 2.8170 GHz sits **two steps from the edge**. The project's own
   guard (`yotta_tools/two_stage_sweep.py`) rejects a minimum closer than `EDGE_STEPS = 2` to
   either edge, precisely because such a "resonance" is a boundary artefact, not a mode.
2. **`2.0830 GHz` is a transient artefact.** It is 15 % below the design frequency and it moves
   with the step cap, which is the signature of a not-yet-settled FFT window. Both settings hit
   their caps (60k and 120k steps) and neither met `EndCriteria`.
3. The design frequency is 2.45 GHz. **Neither arm puts a minimum anywhere near it.**

So the A/B measured the run's own convergence error, not the effect of `port_refine`. Per the
project's reporting rule, no resonance number from this experiment may be quoted as a result -
only as evidence of what the settings fail to deliver.

## What this establishes (the useful part)

* `port_refine` has **no** effect that survives the two-setting check at 60k/120k steps. If it
  has an effect at all, it is smaller than the convergence error of these runs.
* The step caps are the binding constraint for this geometry: 60k and 120k steps both terminate
  before the fields settle. A resonance claim for this patch needs the *final-run* settings
  (`EndCriteria` 1e-4, cap 400k) that `docs/convergence-policy.md` reserves for exactly this.
* The edge guard in `two_stage_sweep.py` did its job: had it been absent, this experiment would
  have "found" a 2.8170 GHz resonance and been wrong.

## Debye vs kappa: what the engine showed and what it did not

Companion run: identical PTFE substrate, identical loss level `tan(delta) = 0.02`, one arm with
the constant-conductivity model and one with a single-pole Debye handed to the engine
(`eps_inf = 2.1`, `eps_delta = 0.084`, `tau = 64.96 ps`).

* **The engine uses the dispersive material.** openEMS prints
  `--- Drude/Lorentz Dispersive Material Extension --- / Max. Dispersion Order N = 1`, which is
  the acceptance evidence that the pole reached the FDTD kernel (see
  `docs/dispersive-substrates.md`).
* **The S11 did not separate the two models** at these settings: kappa 2.0825 GHz / −12.49 dB vs
  Debye 2.0825 GHz / −12.48 dB (Δ = +0.01 dB, Δf = 0.000 %). Both arms sit on the same
  under-converged transient, so this is *not* a validation of either loss model - it is the same
  convergence ceiling as above, seen from the other side.
* Honest status: the Debye **path** is proven (engine-accepted, unit-tested); a **quantitative**
  kappa-vs-Debye separation still needs converged runs and is not claimed.
