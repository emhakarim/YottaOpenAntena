# Heavy-run queue (handed over mid-flight, 2026-09-22 16:45)

The CPU-heavy work runs on the Yotta machine and takes hours. This note exists so the state is
readable without the session that started it.

## What is running

| Job | Question | Settings | Where the output lands |
|---|---|---|---|
| **B2 / Y-19** (2 batches) | does the coplanar feed shift the resonance? | `--end-criteria 1e-3` and `1e-4`, 2 arms (probe vs line) | `runs_b2/b2_e3`, `runs_b2/b2_e4`; logs in `b2_logs/` |
| **k1c** | does `port_refine` have an effect that survives the two-setting check? | `1e-4` / cap 400k, arms `prab_on`/`prab_off` | `runs/batch_k1c_*` |
| **k2c** | does kappa reproduce the requested tan(delta)? | `1e-4` / cap 400k, 3 cases | `runs/batch_k2c_*` |
| **b1s1** | is the construction bias dominated by the ground footprint? | `1e-4` / cap 400k, margin swap | `runs/batch_b1s1_*` |
| **arr2** | does the array S-matrix pipeline work end to end? | 2x2, `1e-3` / cap 120k, 4 runs | `runs/array2/smatrix_summary.json` |

The queue runs **one job at a time**; each job has a wall-clock limit and a run that misses it is
terminated and recorded as `terminated`, never counted as a result.

## How to read the outcome

* `queue_results.json` - one entry per job: status, wall-clock, per-case resonance/`converged`,
  and a verdict (`usable` only when at least one case converged).
* Per-job summaries: `runs/batch_<tag>_<preset>_summary.json` and `runs/array2/smatrix_summary.json`.
* Verdict rules: `docs/convergence-policy.md` (acceptance by stability between two settings) and
  `docs/experiment-k1-verdict.md` (the worked example of a rejection).

## Two incidents worth not repeating

1. **A job that "completed" in 2 seconds.** The queue had been launched with the *project* venv
   (3.12), which has no CSXCAD, so every generated `sim.py` died on import - and the harness
   reported exit code 0. Fix: run the queue with the **solver** venv (3.13) and treat any job
   that ends in under 60 s as `failed-fast`.
2. **A process probe that always said "0 running".** `tasklist /FI "IMAGENAME eq openEMS.exe"`
   returns nothing on this Windows build, and `Get-Process -Name openEMS` is *always* empty
   because pyopenEMS drives the C++ engine **inside the python process**. The queue now counts
   python processes whose command line is a generated `sim.py`.

## Resuming

```
python -m yotta_tools.heavy_queue --only k1c        # one job
python -m yotta_tools.heavy_queue --list            # the plan and its time budgets
python scripts/array_smatrix.py --nx 4 --ny 4 --run # the 4x4 follow-up (16 runs, resumable)
```

## Live status in one command

```
python yotta_tools/status_snapshot.py --log <b2_e3.log> --log <b2_e4.log>
```

It scans every `runs/batch_*/run.stdout.log` (the queue's jobs), reads the last timestep and
speed out of the engine output, prints one table and writes `runs/status_snapshot.json`. The
progress percentage is relative to the timestep cap - a run usually stops earlier, when its
`EndCriteria` is met - so read it as a ceiling, not a countdown.
