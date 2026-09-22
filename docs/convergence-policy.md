# Convergence policy — accept a result by its *stability*, not by an energy threshold

## The problem (measured, not theoretical)

openEMS stops on an **energy** criterion (`EndCriteria`, relative to the excitation) or on
the timestep cap. For this project's default patch model that criterion was **never met**:

| Run | Settings | Outcome |
|---|---|---|
| `selfcheck1` (2.45 GHz PTFE patch) | 1e-4, cap 400k, NF2FF on | killed after ~2.2 h CPU, no result |
| loss validation, PTFE case | defaults (1e-4, cap 400k) | killed after 2.8 h CPU |
| A/B `port_refine` arm "on" | 1e-4, cap 400k | killed after ~80 min |
| parallel batch (5 cases) | 1e-3, cap 200k | arm at 32k steps after 26 min → would cap out |

A high-Q, low-loss resonator simply rings for a long time; "energy below 1e-4" is a very
distant target. Keeping that criterion as the gate means **no patch resonance can ever be
quoted** — which is not a useful state, and it is what the owner asked to stop paying for.

## The policy (adopted 2026-09-22)

A resonance is **accepted** when it is stable between two different solver settings, and
**rejected** otherwise. Concretely:

1. Run the same case twice with two different stopping settings, e.g.
   `EndCriteria = 1e-2` and `EndCriteria = 1e-3` (or caps 60k and 120k with the same
   criterion). Everything else identical.
2. Accept when `|f_2 - f_1| / f_1 <= 0.2 %`; report the accepted value with both runs, their
   timestep counts and their wall-clock times.
3. Reject (do not quote) when the two disagree by more than 0.2 %, or when one of them
   produced no S11 minimum inside the swept band, or when the minimum sits at a band edge
   (`yotta_tools/two_stage_sweep.py` refuses that case automatically).
4. Keep 1e-4/400k for the *final* run only if it is affordable; it is no longer a
   precondition for reporting.

## Why this is the honest formulation

"Energy fell below a threshold" is a statement about the solver's internal state;
"the answer stopped moving when I refined the solver" is a statement about the *answer*.
The second is what a numerical result is supposed to demonstrate, and it is reproducible
by a third party with the two commands below.

## Commands (Yotta's machine)

```powershell
$env:OPENEMS_ROOT = 'C:\Users\User\openEMS'
py -3 yotta_tools/parallel_batch.py --preset port-refine --workers 2 --end-criteria 1e-2 --max-ts 60000
py -3 yotta_tools/parallel_batch.py --preset port-refine --workers 2 --end-criteria 1e-3 --max-ts 120000
# compare the two `runs/batch_port-refine_summary.json` files: |Δf|/f must be <= 0.2 %
```

## Termination rule (owner's instruction, 2026-09-22)

A run that is not on track to satisfy this policy within its budget is **terminated**
rather than left to burn CPU. The five runs killed on 2026-09-22 had consumed ~4 h of CPU
without producing an acceptable number — that is the case this rule exists for.
