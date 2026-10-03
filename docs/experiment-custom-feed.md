# Experiment: custom excitation point - differential pair

Status: prepared 2026-10-03 (Aksara); to be launched by Yotta.

**Question.** `Project.custom_feed_x_m/y_m` (web UI: "custom feed point") renders the
excitation as a probe at an explicit point on metal, whatever `feed_mode` says.  The guard
(point-on-metal, corporate refusal) and the deck wiring are render-tested; the open
question is whether the custom path *reproduces the trusted probe-centre run*, and only
then whether moving the point moves the resonance.  This pair answers the first question;
the second is a follow-up with no reference to lean on.

**Method (one variable).** Two runs of the same script and settings, differing only in how
the probe at the patch centre is expressed:

| arm | run dir | feed | point | settings |
|---|---|---|---|---|
| reference (A) | `runs_b2/cf_ref/probe` | classic probe arm | implicit centre (0, 0) | 1e-4, cap 300000 |
| custom (B) | `runs_b2/cf_00/probe` | custom feed | explicit (0.0, 0.0) mm | identical |

Commands (one per arm):

```
python scripts/b2_coplanar_ab_test.py --arm probe --out runs_b2/cf_ref --end-criteria 1e-4 --max-ts 300000 --run
python scripts/b2_coplanar_ab_test.py --arm probe --out runs_b2/cf_00 --custom-feed-mm 0,0 --end-criteria 1e-4 --max-ts 300000 --run
```

**Read-out.** `yotta_tools/two_setting_verdict --a runs_b2/cf_ref/probe --b
runs_b2/cf_00/probe`.  Both runs are expected to be cap-limited at the same cap, so the
verdict is a strict rejection and the reported relative shift is the measurement, not a
quote.  If the two decks differ only in the custom flag, the expected shift is 0.000 %
(this doubles as a determinism check).

**Interpretation, fixed before the numbers.**

- |df|/f <= 0.2 %: the custom path reproduces the classic probe within screening
  resolution.  Custom-feed results may travel with the same caveats as the probe baseline.
- |df|/f > 0.2 %: the two excitations are not interchangeable.  Before any interpretation,
  diff the two decks (port coordinates, `port_refine` cells, mesh around the port) - a
  structural difference must be understood, not averaged over.
- The reference arm doubles as a determinism cross-check against the historical probe
  quote (~2.3067 GHz / ~-4.5 dB).

**Follow-ups (not scheduled).** Custom off-centre vs probe-with-inset at the same point
(`--custom-feed-mm x,y` vs `--arm probe` plus a matching inset); a custom point on a drawn
sketch polygon (exercises the even-odd guard in a real run); mirrored lateral points.
