# Incident: the heavy-run queue, 2026-09-22

One night of queued FDTD work, four jobs, and three separate causes of loss. Written down because
each cause was invisible until hours had been spent, and two of them were mistakes in the tooling
rather than in the physics.

## What was launched, and how it ended

| Job | Settings | Outcome |
|---|---|---|
| `k1c` K-1 converged (`port_refine` A/B) | 1e-4 / 400k | **killed at 36.6 %**, `rc=timeout`, no result |
| `k2c` loss validation (PTFE kappa, FR-4 kappa, FR-4 none) | 1e-4 / 400k | **killed at 31-55 %**, `rc=timeout`, no result |
| `b1s1` B1 ground-footprint swap | 1e-4 / 400k | **killed at 46-49 %**, `rc=timeout`, no result |
| `arr2` 2x2 array coupling S-matrix | 1e-3 / 120k | **passed end to end**: 4 ports, one run each, ~250-360 s per port, matrix assembled |
| `B2` coplanar-feed A/B (handed over from Aksara) | 1e-3 and 1e-4, probe vs line | **no result**: `probe` arms died after the FDTD, `line` arms never ran |

## Cause 1 - the harness timeout default (tooling, mine)

`parallel_batch.py` kills a case after `--timeout-s`, whose default is **3600 s**. The queue called it
without that flag. A 1e-4 / 400k run needs roughly 2.7 h at 30 MCells/s, so every batch case was killed
at a third to a half of the way through. Evidence is in each job log:

```
done  prab_on: rc=timeout nan GHz (+nan %) converged=None
```

**Fix:** the queue now passes `--timeout-s 14400` explicitly, and a test asserts that every job driving
the harness overrides the default and uses a value of at least three hours.

## Cause 2 - a job that "completed" in two seconds (tooling, mine, earlier)

The first launch used the project venv (3.12), which has no CSXCAD, so every generated `sim.py` died on
import; the harness returned 0 and the queue reported four *completed* jobs that had produced nothing.

**Fix:** jobs that finish in under 60 s are recorded as `failed-fast` with the tail of their log
attached, never as success. Two tests cover it.

## Cause 3 - an unbound port variable in the package (B2, Aksara's path)

The `probe` arms of B2 ran the full 400k-step FDTD (**3230.82 s** each) and then died *before* writing
`s11.csv`:

```
UnboundLocalError: cannot access local variable 'port' where it is not associated with a value
  File "...\runs_b2\b2_e3\probe\sim.py", line 478, in main
    port.CalcPort(sim_path, freqs, FEED_Z0)
```

The port object is created on one path and re-bound inside a block that this configuration skips,
while the post-processing call at the end of `main()` runs regardless. Same class as the earlier
`element_ports` `NameError`, and again invisible to text-based tests: only running the rendered script
exposes it. The `line` arms were never started (their directories hold only `project.json`,
`run_manifest.json`, `sim.py`).

**Reported** with the traceback in `yottakomen.md` §42 and queued for Aksara in `tugas.md` §6h. B2 cannot
be rerun until the binding is fixed - rerunning it now would burn another 54 minutes per arm for nothing.

## A lesson that is worth more than the fix

A run that dies **after** the FDTD has already paid the expensive part, and the engine's raw port data
is on disk (`openems_run/port_ut_1`, `port_it_1`, ~4.6 kB each). Two consequences:

* a cheap **pre-flight check** of the rendered deck (bind every port on every path, or better: execute
  the deck's port-selection section with the engine stubbed) would have caught this in seconds instead
  of after 54 minutes;
* the post-processing (port DFT, then the frequency sweep) is separable from the FDTD, so a *resumable*
  post-processing step would turn a crash like this from "lose the whole run" into "re-run a few
  seconds of work". That is a real optimisation to consider next to the corporate-feed work, not a
  promise made here.

## Monitoring, and why it stayed silent

The first watcher polled every 30 minutes and stayed silent, correctly, because the status tool it read
reported dead runs as live: a killed run leaves its last progress line in its log for ever. The tool now
derives liveness from the log's modification time and prints `N live / M stale`, marking each stale row.

## State at the time of writing

* `b1s1` relaunched 22:13 with the corrected timeout; `k1c` and `k2c` chained to start when it finishes.
* `arr2` finished; its numbers are pipeline evidence only (1e-3/120k, convergence not verified).
* `B2` blocked on the package fix; `arr2`'s 4x4 follow-up (16 runs) not started.
