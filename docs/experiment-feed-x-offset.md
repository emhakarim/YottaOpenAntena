# Experiment: lateral feed offset (2-D feed) - differential pair

Status: launched 2026-09-30 ~20:05 (owner-requested validation of the 2-D feed panel).

**Question.** The model now allows a lateral feed offset across the patch width
(``PatchGeometry.feed_x_offset_m``; web UI: "lateral offset").  The geometry wiring is
render-tested; the open question is whether the resonance responds, and by how much.

**Method (one variable).** Two runs of the same script and settings, differing only in the
offset (the project's differential rule):

| arm | run dir | feed | offset | settings |
|---|---|---|---|---|
| centre (A) | `runs_b2/fx_off0/line` | inset line, synthesised width/inset | 0.0 mm | 1e-4, cap 300000 |
| offset (B) | `runs_b2/fx_off5/line` | identical | +5.0 mm | identical |

Command per arm:

```
python scripts/b2_coplanar_ab_test.py --arm line --out runs_b2/fx_off0 --feed-x-offset-mm 0 --end-criteria 1e-4 --max-ts 300000 --run
python scripts/b2_coplanar_ab_test.py --arm line --out runs_b2/fx_off5 --feed-x-offset-mm 5 --end-criteria 1e-4 --max-ts 300000 --run
```

**Read-out.** `yotta_tools/two_setting_verdict --a runs_b2/fx_off0/line --b
runs_b2/fx_off5/line` (plain invocation; both runs are expected to be cap-limited at the
same cap, so the verdict will be a strict rejection - the reported relative shift is the
measurement, not a quote).  Automated by `fx_validate_chain.ps1`; sentinel
`runs_b2/fx_offset_done.txt`.

**Interpretation, fixed before the numbers.** Screening-grade; no quotable claim either way.

- |df|/f <= 0.2 %: the feed's lateral position is resonance-neutral at these caps, and the
  centreline baseline carries over to off-centre feeds (within screening resolution).
- |df|/f > 0.2 %: a real sensitivity exists; future quotes that use off-centre feeds must
  carry this pair, and the fidelity question (how the physical SMA/pin sits) gets sharper.
- The arm A run doubles as a determinism cross-check against the sweep's p000 point (same
  geometry/settings; expect ~2.4280 GHz / ~-16.9 dB at cap 300k).

**Follow-ups (not scheduled):** a mirrored offset (-5 mm), a probe-mode pair, and - if the
effect is material - a finer offset series around the centre.
