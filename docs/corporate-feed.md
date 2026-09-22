# Corporate feed network (Phase 2 #5) - spec

**Status: not implemented.** This document is the specification, written before the work so the
result can be checked against it instead of against whatever got built.

## What it is for

Today `element_ports=True` gives one port per array element, and the generator **refuses** to
combine that with a printed feed line - deliberately, because a printed line feeding one element
is a different model from a network feeding all of them. Phase 2 #5 is that network: one input
port driving every element through printed lines and power dividers, so the array can be
simulated as it would actually be built.

## Model requirements

1. **One input port.** The network is excited at a single point (typically the ground-plane
   edge), so S11 means what a network analyser would measure at the connector.
2. **Per-element lines** with widths taken from the same Hammerstad-Jensen synthesis already in
   the package (`openantenna.geometry.patch.microstrip_width_for_impedance`), matching the
   element feed impedance the patch synthesis reports rather than a fixed 50 ohm.
3. **Divider geometry** realised as printed metal (quarter-wave transformers or tapered lines),
   not as an ideal circuit, unless the run is explicitly labelled as a circuit-level check.
4. **Mesh across every line**: at least four cells of the line width, and explicit lines at
   patch, notch and divider edges - otherwise the measurement is of the mesh, not the feed
   (this is the lesson behind review item Y-19).
5. **Port bookkeeping**: the model must record, in `run_manifest.json`, the input port, the
   number of divider stages, and the impedance level at each element.

## Verification protocol (what makes a result quotable)

* **Two settings**, per `docs/convergence-policy.md`: `EndCriteria` 1e-3 / cap 120k **and**
  1e-4 / cap 400k, accepted only when `|delta f| / f <= 0.2 %`.
* **Amplitude and phase balance across elements** reported next to S11 - a corporate feed is
  judged by how evenly it feeds, not only by its input match.
* **Comparison against the single-element reference**: the array's resonance should sit near the
  element's, and any shift must be attributed (mutual coupling, network loading, or geometry).
* **Element-edge minima rejected**: a "resonance" within the edge guard of the sweep is an
  artefact (`yotta_tools/two_stage_sweep.py`), not a mode.

## Honest limitations to state up front

* Printed divider tees have discontinuities that ideal lines do not model; if the divider is
  drawn as ideal lines the report must say so and the effect must be bounded, not ignored.
* Line-to-line coupling inside the network is included by the full-wave solve, but the network's
  own radiation and the substrate's surface waves are not separately quantified.
* Conductor loss is not modelled (PEC metals), so feed loss is a lower bound.
