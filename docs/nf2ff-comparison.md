# NF2FF far-field vs the analytic helpers (R-5, executed 2026-09-30)

Purpose: close board item R-5 - "compare the solver NF2FF pattern with
`postproc/patterns.py`" - with a reproducible command, verbatim numbers and
honest limits.

## Method

`yotta_tools/nf2ff_compare.py <run-dir>...` reads run directories produced with
`nf2ff=True` (`nf2ff_pattern.csv` + `nf2ff_summary.csv`) and:

1. finds the pattern peak (grid: theta 0..180 step 2 deg, phi 0..360 step 5 deg);
2. **recomputes the directivity from the exported pattern** with
   `openantenna.postproc.patterns.directivity_from_pattern` (trapezoidal
   integration over the same grid) and compares it with openEMS's own `Dmax`
   from `nf2ff_summary.csv` - the cross-check that ties the solver far field to
   the analytic helper library;
3. reports the -3 dB half-angle of the phi = 0 / phi = 90 cuts (interpolated on
   the 2-degree grid) and the backside level.

Executed on the two k2c loss-arm runs (base patch geometry, PTFE and FR-4):

```
python yotta_tools/nf2ff_compare.py runs/batch_k2c_loss_ptfe runs/batch_k2c_loss_fr4
```

## Results (verbatim from the run directories)

| run | peak | D recomputed | openEMS Dmax @2.45 GHz | agreement | theta=180 level |
|---|---|---|---|---|---|
| batch_k2c_loss_ptfe | theta = 2 deg, phi = 90 deg | 5.4923 lin (7.398 dBi) | 5.594 lin (7.483 dBi) | 0.085 dB (1.8 % linear) | -14.7 dB |
| batch_k2c_loss_fr4 | theta = 84 deg, phi = 105 deg | 1.7463 lin (2.421 dBi) | 1.787 lin (2.52 dBi) | ~0.1 dB (2.3 % linear) | -5.2 dB |

- PTFE: -3 dB half-angles ~17.4 deg (phi = 0) / ~20.0 deg (phi = 90); horizon
  (theta = 90) max ~-5.8 dB. The main lobe is broadside-ish and roughly
  rotationally symmetric near the top - consistent with a patch above a ground
  plane. `eta_rad` is `nan` in the summary (the accepted-power term comes out
  negative on this arm, so the budget is skipped - flagged, not hidden).
- FR-4: this arm is deeply mismatched (VSWR ~38 at its minimum, from the
  2026-09-28 report), and its pattern peaks near the horizon (theta ~ 84 deg).
  That is exactly the class of number the "impossible efficiency" flag exists
  for; the pattern of a near-total reflector is not a meaningful antenna
  pattern, and it is reported here only as an internal-consistency check (the
  two directivity routes still agree).

## What this establishes, and what it does not

- **Established:** the far-field chain works end to end - openEMS NF2FF box ->
  `nf2ff_pattern.csv` -> the project's own integration helper - and the two
  independent directivity computations agree within ~1-4 % (grid-resolution
  level, 2-deg x 5-deg). `patterns.directivity_from_pattern` is exercised on
  real solver data, not only on the golden dipole tests.
- **Not established:** a patch-*shape* comparison against an analytic model.
  `postproc/patterns.py` has no patch element pattern; this comparison is
  consistency + bounds, not shape-vs-theory. A future slice could add a
  cavity-model patch pattern if pattern claims are needed near band edges.
- For quoting: these are internal-consistency numbers for the far-field
  pipeline. They are **not** measurement-backed; the fabrication gate still
  applies (`docs/fabrication-gate.md`).
