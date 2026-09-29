# Phase-2 optimization plan: line feed -> matched reference design (2.45 GHz)

Status: planned, gated on tonight's Route B verdicts (2026-09-28). One quotable point beats ten
tuned-but-unstable ones, so the campaign below only starts once the line-fed geometry has an accepted
truncation verdict.

## Where we start

- The strongest match the project has measured is the coplanar **line feed**: -28.94 dB, VSWR 1.07 at
  2.4390 GHz (b2e3, cap-limited). That is 0.45 % below the 2.45 GHz band centre - close enough that
  tuning is a refinement, not a rescue.
- The probe feed at the same coarse settings gives -4.52 dB (b2e3/b2e4). The line wins by ~24 dB; this
  is a design choice, not a convergence question.
- Existing tools: `scripts/auto_tune.py` (fixes resonance by rescaling patch length, records every
  iteration) and `scripts/tune_inset.py` (sweeps the inset ratio at the converged length, reports |S11|
  and VSWR at resonance). Note from tune_inset's own docstring: the model drives a **vertical lumped
  port** while the inset formula describes a coplanar line (review item Y-19) - the sweep is empirical
  by necessity.

## Preconditions (before spending sweep hours)

1. `runs_b2/verdict_trunc_line.json` is accepted under Route B (line feed truncation-stable within
   0.2 %). If rejected, stability work comes first; tuning a moving number wastes machine time.
2. Every sweep point keeps its own run directory and its own row in the results ledger; geometry
   snapshotted per point.

## Campaign (one variable at a time; same cap everywhere)

- **A. Overlap sweep on the line feed.** ~5 points, 0.5 mm steps around the current overlap,
  cap 300k at EndCriteria 1e-4, 2 workers. Output: |S11| and f_res vs overlap.
  Pick the deepest |S11| whose f_res sits inside [2.40, 2.50] GHz.
- **B. Optional fine step.** Only if the optimum sits at a sweep edge: 3-4 points at 0.25 mm.
- **C. Resonance nudge.** If the best point's f_res is outside [2.43, 2.47] GHz, nudge patch length by
  half of auto_tune.py's usual correction (the line feed loads the edge less than the probe), 1-2
  points.
- **D. Confirmation pair.** Re-run the winner at cap 400k; read with
  `two_setting_verdict --truncation-pair` (winner@300k vs winner@400k). This is the verdict that makes
  the tuned number quotable.
- **E. Mesh check.** 15 vs 20 cells/lambda0 at the winner (`--differing-setting mesh`), same cap.

## Execution mechanics, as built (2026-09-29)

- **Step A** runs as `scripts/b2_overlap_sweep.py` (5 points m100..p100, 2 workers, cap 300k @ 1e-4;
  per-point run dirs under `runs_b2/overlap/<tag>/line`). Sweep numbers are **screening only**, not
  quotable; the winner is the deepest |S11| whose f_res sits inside [2.40, 2.50] GHz.
- **Step D** is automated by `scripts/b2_routeb_followup.py`: it reads `runs_b2/overlap/winner.txt`,
  re-runs the winner deck at cap 400k (300k vs 400k = 25 % apart, satisfying the >= 5 % rule), and
  writes the verdict to `runs_b2/overlap/followup/verdict_<tag>_sweep300000_vs_400000.json` plus the
  sentinel `runs_b2/overlap_followup_done.txt`. The launcher `followup_chain.ps1` is fired
  automatically by `wait_then_followup.ps1` once the sweep sentinel lands (guarded by
  `runs_b2/overlap_followup_launched.lock`). Refuses without a winner; idempotent when the follow-up
  run already exists.
- **Step E** rides `yotta_tools/parallel_batch.py` with the `--inset-delta-mm <winner>` knob: the
  mesh15/mesh20 arms mirror the b2 line-arm build (synthesised width/length/line width;
  `feed_inset_m` = 14.658 mm base + delta), so the pair is cut on the winner geometry. Read with
  `two_setting_verdict --truncation-pair --differing-setting mesh`. Both arms must share the stop
  condition: mesh15 is the slow arm (~399.8k steps needed at 1e-4 on the base geometry), so choose a
  cap where both arms end the same way; a mixed stop pair is rejected by the verdict rules.

## Budget and stop rules

- Measured classes: b2e4-class arms ~50 min at 400k (~40 min at 300k); patch-class arms up to ~1.5 h.
  Campaign total ~8-12 points, about one to two overnight sessions with 2 workers.
- Stop rules: (i) |S11| <= -15 dB and f_res in [2.43, 2.47] GHz -> go to D; (ii) if two consecutive
  fine steps move |S11| by < 1 dB, the model is at its resolution floor - document and stop;
  (iii) any point that times out fails fast; no silent retries.

## Deliverable

A **matched reference design** at 2.45 GHz quoted with: accepted truncation verdict + accepted mesh
verdict + full provenance (geometry, cap levels, verdict file paths) in the results ledger.
