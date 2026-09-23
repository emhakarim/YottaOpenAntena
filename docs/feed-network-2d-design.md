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
