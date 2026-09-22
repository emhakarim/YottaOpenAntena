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

## Retrieval routes, and which one works

| Route | Status |
|---|---|
| `autoglm-websearch` skill (local token service) | **works** - returns deep article links |
| `web_search` (native) | works, but often returns site-level URLs and handles `site:` filters poorly |
| Browser agent (`autoglm run`) | **blocked**: needs the owner's configuration (choose Chrome/Edge, install the AutoGLM extension, approve `auto_approve`). It cannot read paywalled full texts anyway |
| Reading a page | `autoglm-open-link`, once a deep URL is known |

## Candidates found (snippet level only - NOT usable yet)

Nothing here has been read in full, so **no geometry, substrate or frequency from this list may be
quoted**.  Each entry names what it would take to promote it.

| Candidate | Why it is promising | What is missing to promote it |
|---|---|---|
| "Bandwidth Enhancement of An Inset-Fed Rectangular Patch" (article.sapub.org, open access) - snippet cites 3.09-3.17 GHz, 80 MHz bandwidth | inset-fed **rectangular** patch, open access, measured bandwidth stated | patch W/L, substrate epsilon_r + h, inset depth, and whether the resonance is measured |
| "Comparison of return loss calculations with measurements" (journals.riverpublishers.com) | a direct model-vs-measurement comparison - exactly the model-error track | full text: which models, which geometries, the quoted errors |
| "Evaluation of the effect of bending on the resonance" (journals.sagepub.com) | quantifies resonance shift vs a physical parameter | full text (likely paywalled) |
| "A design rule for inset-fed rectangular microstrip patch antenna" (ResearchGate PDF) | gives the inset-depth rule we use as an estimate | the verification against measurement, if any |
| MDPI "Optimization Design of a Novel Slotted Microstrip..." (2017, open access) | single-layer single-patch resonant-frequency analysis | the patch is slotted: usable only as a *rejected* example unless the plain baseline is given |

Rejected on sight: PIER circularly-polarised design (not a plain rectangular patch), any
metasurface/array paper, social-media posts.

## How these feed the calibration

Collected cases become `RunSample` entries in `openantenna/postproc/calibration.py` once *our*
model has been run on the **same geometry** (the runs need converged settings, so they go to the
machine with capacity).  Until those runs exist, this table is a *source list*, not a calibration:
no bias number is claimed from a paper alone.
