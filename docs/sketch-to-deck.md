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
* **The GUI wiring landed** (2026-09-28 evening): the Sketch tab has an *Include sketch in
  simulations* switch; when ticked, the Simulate tab (and the project tree, and the batch
  queue) merges the closed shapes into the project it generates from.  Conversion rules as
  described above; open traces are skipped and counted in the note under the switch.
  Still not there: cutouts, per-shape priorities, and the geometric overlap check.
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

## Runtime smoke (for the run side - openEMS machine)

This is a smoke, not a result: a few thousand timesteps, to prove the binding accepts the
polygon metal and the run exits cleanly.  Render a deck that contains one sheet:

```python
from openantenna.model.project import (
    ArrayConfig, FrequencySweep, PatchGeometry, Project, SubstrateStackup,
)
from openantenna.solvers.openems import OpenEMSSolver

project = Project(
    name="sketch-smoke",
    substrate=SubstrateStackup.single("PTFE", 1.6e-3),
    patch=PatchGeometry(feed_mode="probe", width_m=30.7e-3, length_m=29.4e-3),
    array=ArrayConfig(nx=1, ny=1),
    sweep=FrequencySweep(start_hz=2.0e9, stop_hz=3.0e9, points=51),
    sketch_polygons=(((0.0, -0.005), (0.020, -0.005), (0.020, 0.005), (0.0, 0.005)),),
)
solver = OpenEMSSolver(max_timesteps=4000)      # smoke: a small cap, not a run
solver.prepare(project, "sketch_smoke_run")     # writes project.json + sim.py
```

Then run `python scripts/run_with_openems.py sketch_smoke_run/sim.py` and report: exit code,
any "Unused primitive" or polygon warnings in the log, and whether the `sketch` property
appears as used.  The step text tests cannot take - a rendered deck that the binding
accepts - is exactly this.
