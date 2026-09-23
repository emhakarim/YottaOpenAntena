# Examples

Three runnable recipes plus the CLI equivalents.  None of them needs a solver, and none needs an
optional dependency - they run on a bare interpreter with the package installed.

| Example | What it shows | Command |
|---|---|---|
| 1 | synthesise a 2.45 GHz patch on PTFE, then tune the length against the cavity predictor | `python examples/01_patch_tuning.py` |
| 2 | plan a 1-by-8 corporate feed: levels, quarter-wave section, rectangles, extent | `python examples/02_feed_plan_1d.py` |
| 3 | plan the two-layer 4-by-4 tree and prove the layers do not overlap | `python examples/03_feed_plan_2d.py` |

`tests/test_examples.py` runs all three under the test suite, so an example that stops working is a
test failure rather than a stale document.

## The same things from the CLI

```
openantenna optimise --target-hz 2.45e9 --predictor cavity --json tuned.json
openantenna feed-plan --rows 4 --cols 4 --pitch-mm 60 --json feed.json
openantenna feed-plan --rows 1 --cols 4 --pitch-mm 60
openantenna material list
openantenna design patch --frequency-hz 2.45e9
```

`optimise` prints which analytic predictor produced the number and says outright that it is a
targeting result, not a measurement.  `feed-plan` prints the collision count per layer - a non-zero
count means the layout is not buildable and the tool says so.

## What the examples deliberately do not claim

* No example asserts solver accuracy.  The model bias is 2-5 % and is documented in
  `docs/calibration.md`; only a run can settle it.
* The 2-D tree is drawing geometry.  Its row segments follow the element grid, so lambda/4 padding
  is still open (`docs/feed-network-2d-design.md`).
* The feed layer sits inside the substrate in the generated deck, which is a stackup decision, not a
  free choice.
