# CST reference intake (gate condition 2)

The owner has CST Studio Suite results. That is the **best available independent reference** the
project can get without a measurement: CST is a full-wave commercial solver, so it is independent
of both our analytic formulas (cavity / transmission line) *and* of our openEMS setup. Comparing
the two isolates our model's bias from our choice of solver.

**Honest limit, stated up front:** CST is a *solver* reference, not a *measurement*. It can find
that our model or mesh is wrong; it cannot find that both are wrong in the same way (for example if
the substrate permittivity we both assume is off). Only a VNA measurement closes that gap.

## What to send, per design

| Field | Why it is needed | Example |
|---|---|---|
| **S11 vs frequency** | the quantity compared | Touchstone `.s1p` (best) or CSV with `freq_hz, re, im` |
| **Patch W and L** (mm) | sets the resonance | `W 38.04, L 29.44` |
| **Feed** | probe vs coplanar inset changes the resonance | `inset, depth 11.0 mm, line width 5.1 mm` or `probe at centre` |
| **Substrate** | epsilon_r spread is the accuracy ceiling | `PTFE, eps_r 2.1, h 1.6 mm, tan_d 0.0002` |
| **Ground size** (mm) | it radiates; size affects the resonance | `110 x 103` |
| **CST setup** | reproducibility | mesh cells/wavelength or lines per wavelength, boundary, port type, frequency sweep, solver (time/frequency domain) |
| **Whether it converged** | the project refuses to quote unconverged numbers | CST's own convergence/accuracy note, adaptive mesh passes |

If a field is unknown, write "unknown" - do not estimate it. A guessed epsilon_r turns a clean
comparison into an unexplainable bias.

## What will be done with it

1. Parse the S11 with the same reader and the same metric the project uses everywhere
   (`S11Trace`, minimum |S11| with sub-grid refinement) - so the two solvers are compared on
   identical terms, not on two different definitions of "resonance".
2. Build a `RunSample` per design with the CST number as the **reference** and our model's number
   as the measurement, in `openantenna/postproc/calibration.py`.
3. Report per topology: bias %, and the spread across topologies.

## What the result will mean

| Outcome | Reading |
|---|---|
| worst \|bias\| <= 1 % on **>= 2 topologies** | **gate condition 2 satisfied** - with the topologies and frequencies named, and nothing else licensed |
| bias larger, but consistent across topologies | a correction factor with a written validity range |
| bias different per topology | the model is not yet trustworthy outside the cases measured; the disagreement itself is the finding |

## Still needed for the other gates

* **Gate 4** (loss validated against a known Q) still needs a measurement or a known-Q reference;
  CST can supply the *model* side of that, not the reference side.
* **Gate 3** (feed realisation) is being settled by the coplanar-inset differential that Yotta is
  running.

## Where to put the files

Drop them under `D:\OpenAntenna\runs\cst_reference\<design_name>\` (one folder per design) with the
S11 file named `cst_s11.s1p` or `cst_s11.csv`, plus a `cst_model.md` in the same folder filled from
the table above. That keeps the data next to the runs it will be compared against, and the notes
travel with the file.
