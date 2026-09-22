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

Anything less is recorded but marked **not usable**, with the missing field named.

## Route status - measured, not assumed (2026-09-22)

| Route | Outcome |
|---|---|
| Research subagents (3 dispatched, web_search) | **all three failed** after 40-69 s: the platform's model service returned errors. No output was produced |
| Browser agent (`autoglm run`) | **blocked**: needs the owner's configuration (pick Chrome or Edge, install the AutoGLM extension, approve `auto_approve`). Even configured, it cannot read a paywalled results section |
| `web_search` (native) | returns site-level URLs and mangles `site:` filters (one query came back with baking-recipe results) |
| `autoglm-websearch` skill (local token) | **works** - returns deep article links; this is the route to use |
| `autoglm-open-link` skill | works, but extraction quality varies: on the first attempt it returned the article's **reference list** instead of its body, so a single read is not enough |

**Conclusion: the literature route is viable but not yet productive.** No geometry, substrate or
frequency may be quoted from this page yet - every entry below is snippet level.

## Candidates found (snippet level only - NOT usable yet)

| Candidate | Why promising | Missing to promote it |
|---|---|---|
| "Bandwidth Enhancement of An Inset-Fed Rectangular Patch" (article.sapub.org, open access) - snippet cites 3.09-3.17 GHz, 80 MHz bandwidth | inset-fed **rectangular** patch, open access | W/L, epsilon_r, h, inset depth, and whether the resonance is measured |
| "Inset Fed Rectangular Patch Antenna Design for ISM Band" (IJPSAT 2023, open access, `ijpsat.org/index.php/ijpsat/article/view/5777`) | inset-fed rectangular patch, ISM band | the read returned only the reference list; the body must be re-fetched |
| "Comparison of return loss calculations with measurements" (journals.riverpublishers.com) | a direct model-vs-measurement comparison | full text: which models, which geometries, the quoted errors |
| "A design rule for inset-fed rectangular microstrip patch antenna" (ResearchGate PDF) | gives the inset-depth rule we use as an estimate | its verification against measurement |
| MDPI "Optimization Design of a Novel Slotted Microstrip..." (2017, open access) | single-layer single-patch resonance analysis | the patch is slotted: usable only as a *rejected* example |

Rejected on sight: circularly-polarised PIER design, metasurfaces, arrays, social-media posts.

## What this changes about the plan

Reading several open-access articles properly (search -> fetch -> verify the body -> extract five
fields) is a **slow loop with an uncertain yield**, and the two fastest routes are currently shut
(subagents failing, browser agent unconfigured). The better anchor for this project is therefore:

1. **Analytic references** (cavity model, microstrip synthesis) - already in place, independent of
   the solver, and enough for gate #5's two-topology requirement.
2. **The owner's own measurement** - a fabricated patch measured on a VNA. That is ground truth for
   the geometries the project actually cares about, and it does not depend on anyone's paywall.
3. Literature cases as **additional** anchors once someone reads them properly (a task a human can
   do faster than this loop).

## How these feed the calibration

Collected cases become `RunSample` entries in `openantenna/postproc/calibration.py` once *our*
model has been run on the **same geometry** (converged settings, machine time). Until then this
page is a *source list*, not a calibration: no bias number is claimed from a paper alone.
