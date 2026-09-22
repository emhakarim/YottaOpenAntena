# Measured references from the literature (gate condition 2)

Gate condition 2 needs the model compared against an **independent** reference on at least two
topologies.  Our own analytic references (cavity model, microstrip synthesis) are independent of
the solver, but they share our assumptions; a *measured* design from the literature is the next
strongest anchor, and it is the only one that can catch a systematic error in those assumptions.

## Rules for accepting a published case (decided before collecting, not after)

A case may be used as a reference only if **all** of the following are readable:

| Required | Why |
|---|---|
| Patch **W and L** in mm | the resonance is set by the geometry |
| **Feed realisation** (inset depth, probe, or line width) | probe vs coplanar inset moves the resonance; see `docs/experiment-coplanar-inset.md` |
| Substrate **epsilon_r**, **h**, and its **tolerance or provenance** | the permittivity spread alone is about 1 %, which is the accuracy ceiling |
| A **measured** resonance (not only simulated) | a simulated number is not independent of us |
| Instrument, or at least "measured" stated | a number of unknown origin cannot anchor anything |

Anything less is recorded in the table but marked **not usable**, with the missing field named.
Cases that are arrays, metasurfaces, or fully flexible/textile are out of scope until the
generator models them.

## What a published case can and cannot settle

* **Can**: reveal a *systematic* bias of the model on a geometry we did not invent (our analytic
  references cannot do that).
* **Cannot**: prove 0.1 % accuracy - the paper's own permittivity uncertainty is usually larger
  than that. A comparison inherits that uncertainty and must be reported with it.
* **Cannot**: be quoted from an abstract alone. Most results sections are paywalled; if only the
  abstract was readable, the case is marked partial and the extracted numbers are attributed to
  the abstract, not to the full paper.

## Cases collected

_Being collected by the browser agent; each entry will carry: source + DOI/URL, geometry,
substrate, measured frequency, completeness verdict, and exactly which fields were readable._

| # | Source (DOI/URL) | Geometry | Substrate | Measured f | Verdict |
|---|---|---|---|---|---|
| — | _(pending)_ | | | | |

## How these feed the calibration

Collected cases become `RunSample` entries in `openantenna/postproc/calibration.py` once *our*
model has been run on the **same geometry** (the runs need converged settings, so they go to the
machine with capacity - Yotta's, per the current division).  Until those runs exist, this table
is a *source list*, not a calibration: no bias number is claimed from a paper alone.
