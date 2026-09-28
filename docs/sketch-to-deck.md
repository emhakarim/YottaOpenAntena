# Sketch to deck - the first half of the bridge (2026-09-28)

The GUI can draw (Sketch tab) and the generator can build an openEMS deck.  This page is the
written boundary between the two, because "the drawing is simulated" is exactly the kind of
claim that is easy to make and wrong to mean.

## What the deck does with a sketch (v1, implemented)

* `Project.sketch_polygons` (metres, closed, validated in `geometry/sketch.py`) are carried
  through the neutral model JSON; files without the key stay valid, and the key is omitted
  when there are no polygons.
* The generator draws every polygon as an **additive, zero-thickness PEC sheet** on the patch
  plane (z = 0): `AddPolygon(..., norm_dir=2, elevation=0.0, priority=3)`, with
  `AddEdges2Grid` snapping when metal-edge snapping is on.  The manifest records the count.
* A polygon point outside the ground plate is **refused** with the point named - a sheet
  floating over the air region is a drawing accident, not a design, and clamping it quietly
  would change the drawing.
* Validation happens at construction (`geometry/sketch.py`): >= 3 distinct points, finite
  coordinates, a +/- 5 m sanity bound (units are metres; the sketch draws millimetres),
  a 256-point cap, no self-intersection, non-zero area.  Consecutive duplicate points
  (including the closing one) are normalised away, not refused.

## What it deliberately does not do yet (the honest boundary)

* **The parametric patch remains the driven element.**  The sketch adds metal; it does not
  replace the patch.  Overlap between a sketched sheet and the patch or the feed is not
  *resolved* (openEMS priorities make the result well-defined for the solver, not
  meaningful for you); a geometric overlap check is on the list.
* **A block's thickness is not used.**  Sheets are zero-thickness PEC; the drawn z extent
  stays a sketch field only.
* **The GUI does not push the sketch into Simulate yet.**  Next: conversion of drawn shapes
  to polygons (closed polygon / rectangle / block footprint to polygon; circle to chords,
  as the DXF reader polygonises it; open trace refused), an "include sketch" switch, and
  the merge into the project the solver tab hands over.
* **No netlist, no ports, no cutouts** from the sketch: one driven port from the parametric
  feed only.

## Reproduce

```
python -m unittest discover -s tests -p "test_sketch_deck.py"
```

The deck test renders a script with one 20 x 10 mm sheet and checks the metal call, the
polygon literal (in metres), the snapping path and that the generated file compiles.  The
binding sweep from `test_generated_deck_bindings` runs over the same script, so the new deck
block is held to the unbound-local rule that the B2 incident froze.
