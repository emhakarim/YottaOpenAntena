# Optimisation backlog — ranked by measured impact

Everything here is grounded in numbers produced during this project, not in guesses.
Where a gain is unknown, that is stated instead of estimated.

## A. Wall-clock (time per result)

| # | Item | Evidence for the gain | Cost / owner |
|---|---|---|---|
| **A1** | **Run policy: choose `EndCriteria` by purpose.** Exploration runs at 1e-2…1e-3, only the final design run at 1e-4/1e-5; **reject** (do not report) a resonance from a run that hit the step cap | The default settings did not finish in **2+ hours** on this machine (two runs killed at ~2.2 h CPU, no `s11.csv`), while a 3 000-step run completed in seconds | 1 session, Aksara + Yotta (protocol) |
| **A2** | **NF2FF only when needed** | Aksara's `f0a93ddc` (DFT-only recording) fixed the I/O blow-up; the earlier default wrote 12 near-field HDF5 files during the FDTD loop. Still on by default (`NF2FF_ENABLED = True`) | small, Aksara |
| **A3** | **Parallel independent cases** | Already done: `numthreads` does **not** exist in the official openEMS binding (verified — the knob had to be made a no-op fallback), so the lever is *process* parallelism. Two concurrent FDTD runs fit comfortably in 16 GB RAM | done / Yotta |
| **A4** | **Extend the OpenCL kernel to 3-D + PML + lumped port** | The 2-D kernel measures **9.19×** GPU-over-numpy (1.173e9 vs 1.276e8 cell-updates/s) and matches the analytic cavity to **0.031 %** — so the GPU is a real lever *for our own kernel*, unlike openEMS (no GPU path) | large; Phase 2/4 decision |
| **A5** | **Mesh economy:** use the cavity predictor (validated to 0.05 % against an independent solver) to place the geometry, then verify with a coarser mesh; quantify `port_refine` cost/benefit | Mesh refinement 15→25 cells/λ moved the resonance only 0.9 %; `port_refine` adds lines for an unknown gain until the A/B is run | small; Yotta (A/B) |
| **A6** | **Two-stage sweep:** coarse sweep to locate the resonance, fine sweep only near it | The S11 minimum is found from a 201-point sweep over 700 MHz, i.e. most points are far from resonance | small; Aksara |
| **A7** | **Re-justify the air margin (now 0.80 λ0 by default)** | The margin grew to give the absorber room; it also multiplies the cell count. A differential run at 0.4 λ0 vs 0.8 λ0 answers whether the extra cost buys anything | small; Yotta |

## B. Accuracy — the real blockers (from `docs/fabrication-gate.md`)

| # | Item | Why it matters | Cost / owner |
|---|---|---|---|
| **B1** | Close the construction bias (bisection "diff-and-swap" against the tutorial model) | Currently −2.3 % … −5.0 % versus the cavity prediction; it is the difference between "model output" and "design authority" | medium; Yotta |
| **B2** | Realise the *coplanar inset* feed (Y-19) | The synthesis formula describes an inset feed, the model builds a probe — so the formula cannot be validated at all until this exists | medium; Aksara |
| **B3** | Validate the loss path against a known Q (and decide on conductor loss — metals are PEC today) | Efficiency/gain numbers are optimistic and unverified | medium; Yotta + Aksara |
| **B4** | Benchmark #2 — waveguide TE10 with the **exact** reference `c/(2a) = 1499.0 MHz` | The cheapest credibility: nothing to argue about, tests the whole pipeline | small; Yotta (script ready) |

## C. Process (prevents regressions)

| # | Item | Evidence | Owner |
|---|---|---|---|
| **C1** | **Run a generated model before believing a feature** | The `numthreads` knob killed *every* generated model on the official openEMS build (`AssertionError: Unknown keyword arguments`); two static test suites passed while it was broken | rule already adopted; keep it |
| **C2** | CI job for the 195-test suite (no solver needed) | Would have caught the missing `runs/` mkdir and doc drift automatically | small; Aksara |
| **C3** | One log-file name convention (`run.stdout.log` vs whatever `parse_results` looks for) | `parse_results` reports "solver log not found" → convergence unknown even for good runs | tiny; Yotta (R-11) |
| **C4** | Board discipline: statuses updated in `tugas.md` | Two items looked "belum" while the code was already done (A-2, UNIT_CELL) | tiny; Aksara |

## D. Explicitly NOT worth optimising now

* **GPU for openEMS** — the published build has no GPU path; only a different solver would change that.
* **Gerber/KiCad import** — large, not a blocker, needs a scope decision first.
* **Web GUI** — the desktop choice stands until calibration is done.
* **Micro-optimising the pure-Python synthesis** — it runs in milliseconds; it is not on the critical path.

## Suggested order (impact per unit effort)

1. **A1 + C3** (biggest wall-clock win, tiny effort)
2. **B4** (cheapest credibility) then **B1** (unblocks the gate)
3. **B2** (makes the synthesis formula testable)
4. **C2** (stops regressions)
5. **A5/A7** (make the runs cheaper *without* losing accuracy)
6. **A4** (largest ceiling, largest effort)
