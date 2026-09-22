# Experiment: coplanar inset feed vs vertical probe (B2 / Y-19)

**Question.** The synthesis formula used by `openantenna.geometry.patch` describes a
*coplanar inset* feed. Until now the generator realised a **vertical probe** at the inset
position, so that formula could not be validated at all. This experiment changes exactly one
thing - how the feed is realised - and measures the difference.

**Status: handed to Yotta.** The structural side (the deck really contains a notched patch, a
printed line and a port at the line end, and the mesh is refined across the line) is covered
by tests. Whether the feed *moves the resonance* is not claimed until the runs exist.

## Protocol

```powershell
# on a machine with openEMS and OPENEMS_ROOT set
python scripts/b2_coplanar_ab_test.py --run --end-criteria 1e-3
```

Two arms, identical in everything except the feed:

| Arm | `feed_line_width_m` | What the deck contains |
|---|---|---|
| `probe` | `None` | legacy vertical lumped port from ground to patch at the inset position |
| `line` | synthesised (5.101 mm on PTFE h = 1.6 mm) | notched patch, printed microstrip line, port at the **outer end** of that line |

Held constant: substrate (PTFE, 1.6 mm), patch W × L from the same synthesis, array (1 × 1),
mesh resolution and smoothing, boundary, excitation, `max_timesteps`, and the stop criteria.
One variable, therefore, and only one.

## Decision thresholds (fixed before the numbers are seen)

* **|Δf| < 0.2 %** - the feed realisation does not matter at this geometry; keep the probe
  (simpler) and record that the formula's feed assumption is not the limiting factor.
* **0.2 % ≤ |Δf| < 1 %** - the feed matters but is second-order; report both, and state which
  one the fabrication gate should use.
* **|Δf| ≥ 1 %** - the feed realisation dominates the model's accuracy for this geometry; the
  coplanar model becomes the default for any design that will be built with an inset feed.

## What to report (per arm, and it must be complete)

* resonance, |S11| at resonance, VSWR, timesteps, **`converged`**, and wall time;
* the generator's own `FEED:` and `FEED MESH:` lines from the run log, so the reader can see
  which geometry produced the number;
* the stop criteria actually used, and - per `docs/convergence-policy.md` - whether the answer
  is stable between two settings (`end_criteria` 1e-3 and 1e-3/2, for instance).

## Known limitations, stated up front

* Only **one port** is modelled. An N × M array still needs a feed network and one port per
  element; that is Phase 2 #4, which Aksara is now working on.
* The inset depth is the transmission-line estimate, not a tuned value; the arm comparison is
  a differential measurement, not a claim that either arm is matched.
* The notch width equals the line width (no gap on each side). A gapped notch is a follow-up
  variant if the differential run shows the feed matters.
