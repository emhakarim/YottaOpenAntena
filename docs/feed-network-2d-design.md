# Design note: the 2-D corporate feed tree (Phase 2 #5b remainder)

Status: **open design item**, not an implementation gap.  The 1-D tree is built, wired into the
deck builder and previewed in the GUI; this note records why the 2-D case is not a mechanical
extension of it, so the next session starts from the analysis instead of rediscovering it.

## What is already done

| Piece | Where | Verified by |
|---|---|---|
| Feed synthesis (impedance, quarter-wave section, levels) | `openantenna/postproc/feed_network.py` | `tests/test_feed_network.py`, cross-checked against scikit-rf (`line.renormalize` + guide `gamma`) |
| Drawing plan (segments, junctions, rectangles, bounds) | `openantenna/geometry/feed.py` | `tests/test_feed_plan.py` (9) |
| Deck drawing (rectangles, metal-edge snapping, port at the trunk input) | `openantenna/solvers/openems.py` | `tests/test_corporate_feed_deck.py` (7) |
| 2-D layout preview overlay | `openantenna/gui/main_window.py` | structural + GUI smoke suite |

## Why 1-by-n works and n-by-m does not

The 1-D planner has one axis doing two jobs: it is both the **growth** axis (each level drops one
quarter-wave section) and the **spread** axis (the leaves sit at different positions along it).
That is exactly right for a row: the input is at the board edge, the tree grows towards the
elements, and the leaves land on the element pitches.

For an n-by-m array the second stage would have to *spread* its leaves along the row direction
while *growing* along the same direction, because a 1-D tree has no second dimension to grow in.
Two stacked 1-D trees cannot both do it: the column stage's outputs are points on one line, and a
row tree starting there would have to spread along that same line.

Real planar corporate feeds solve this with a genuinely two-dimensional topology:

- an **H-tree** (recursive H shapes), where each stage splits along one axis and the next stage
  splits along the other, with **orthogonal risers** connecting the stages;
- or a **series/comb** network, which is a different electrical design (not a corporate splitter)
  and would need its own synthesis.

## The decision the next session has to make

1. **Topology.** H-tree (keeps the corporate power split, more metal, more design freedom) or
   comb/series (less metal, different impedance behaviour, needs new synthesis).  The H-tree keeps
   `feed_network.py` as the single source of truth; the comb would not.
2. **Layer.** Feed on the same layer as the patches, or on a separate feed layer under the ground
   plane with vias (that changes the deck: a new metal sheet, via barrels, a different mesh).
3. **What the ports mean.** With a drawn network the array has **one** driven port at the trunk
   input, and the elements are loads.  A per-element port matrix (the coupling work) requires the
   network to be *absent*, because per-element ports inside a shorting network measure nothing
   useful.  The builder therefore keeps refusing `element_ports` together with a drawn tree, and
   that refusal is a design statement, not an unfinished feature.

## Recommended path

H-tree on the patch layer for the 4-by-4 case, in three steps:

1. extend `geometry/feed.py` with `plan_corporate_feed_2d`, reusing the 1-D planner for the two
   orthogonal stages (build each stage in its own frame, then place the second stage's frame at
   each first-stage output and add the risers);
2. extend the builder to consume it (the deck-side code is already generic: it draws rectangles);
3. check the mesh: tree segments are ~3 mm wide against a coarse cell of a few millimetres, so the
   metal-edge snapping is currently the *only* treatment the tree gets.  Whether that is enough is
   a question for a convergence run, not for a drawing change.

Steps 1 and 2 are mechanical once the topology is chosen; step 3 needs machine time.

## Measured layout budget (2026-09-23)

The first H-tree attempt (`geometry/feed2d.py`, parked) halved the element grid recursively and
ran its own **collision detector** over the resulting rectangles.  The detector is the useful part
of that attempt; the layout was wrong and it said so:

| Grid | pitch | segments | overlapping rectangle pairs |
|---|---|---|---|
| 2x2 | 60 mm | 14 | **7** |
| 4x4 | 60 mm | 62 | **19** |
| 4x4 | 90 mm | 62 | **19** |
| 4x4 | 120 mm | 62 | **19** |

The count is pitch-independent, which is the real finding: the collisions are **structural**, not
a spacing problem.  A recursive halving that lets each level choose its own depth cannot keep two
levels out of each other's way - not at any pitch.

### What a collision-free layout needs

Each stage needs its own band, and a band needs a direction the other stage is not using.  For a
4x4 at 60 mm pitch the numbers are:

* one quarter-wave section at 2.45 GHz, eps_eff ~1.95: **22.2 mm**;
* a column's row-tree needs 2 levels x 22.2 = **44.4 mm** of depth;
* the array itself spans 3 x 60 = **180 mm**;
* the ground plane currently reaches ~25 mm past the array edge.

So a single-layer tree does not fit: the row trees want 44.4 mm inside a 60 mm pitch (leaving
15.6 mm for the riser and clearance), and the column tree wants another 44.4 mm below the array
where only 25 mm are available.  Two ways out, both already anticipated above:

1. **Two conductor layers** (the approved path): the column tree on the feed layer below the
ground plane, the row trees on the patch layer, vertical risers between them.  Collision-free by
construction, because the two stages never share a plane.  Cost: a second metal sheet, riser boxes
through the substrate, a mesh that resolves the risers, and a ground-plane cavity where the feed
layer passes through.
2. **A larger element pitch** (>= 2 x 44.4 = 89 mm, i.e. >= 0.72 lambda0 at 2.45 GHz): keeps one
layer, but changes the array's grating-lobe behaviour, so it is an antenna decision, not a layout
decision.

### Acceptance test the next session should keep

`HTreePlan.collisions()` (overlapping rectangle pairs must be empty) plus `len(leaves) == rows*cols`
with the leaves on the element grid.  Those two caught the first attempt; they will catch the next
one if it regresses.
