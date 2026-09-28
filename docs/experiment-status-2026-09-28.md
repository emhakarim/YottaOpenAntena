# Experiment status - 2026-09-28

## 1. The port fix is verified in production

`k1c` (port_refine A/B, 1e-4 / cap 400k) ran on the fixed tree and **both arms wrote `s11.csv`**
(4871 B each) with parsed resonances - the first batch case to produce a result since 22 Sep. The
run-time fix (`38c2d439`) is therefore confirmed on the real workload, not only on the proof deck.

## 2. Its verdict, computed mechanically (`yotta_tools/two_setting_verdict.py`)

```
verdict: REJECTED  (shift 0.301 %, band 0.2-1 %)
| run                | resonance [GHz] | |S11| [dB] | VSWR | samples | converged | timesteps |
| batch_k1c_prab_on  |          2.4427 |      -7.84 | 2.365 |     101 |     False |   400000 |
| batch_k1c_prab_off |          2.4353 |      -8.27 | 2.257 |     101 |     False |   400000 |
reasons: both runs hit the timestep cap before the end criteria -> not converged
NOT QUOTABLE
```

Read this carefully, because it is easy to misread: the observed `port_refine` effect is **0.30 %**,
which sits in the "shifted" band (0.2-1 %), *not* in the "acceptable" band. And it is **not quotable**,
for a reason that is now the main blocker:

## 3. The real blocker: nothing can ever be quoted under the current settings

The policy accepts a result by **stability between two settings** (`|df|/f <= 0.2 %`). But the engine's
end criteria is **never reached** at 1e-4 with a 400k-step cap - every arm so far has ended by hitting
the cap (timesteps = 400000, `converged = False`). Combined with the stricter interpretation now coded
in `two_setting_verdict.py` (a cap-limited run is not accepted), the pipeline can produce data but
**no quotable number at all**, no matter how many runs are queued.

Two ways out, and this needs a decision rather than more CPU:

1. **Calibrate a terminating criterion** (recommended): measure the energy level at which the resonance
   stops moving and adopt the lowest level that still holds `|df|/f <= 0.2 %`. This makes runs both
   quotable and 2-4x cheaper - it is item 1 of `docs/compute-roadmap.md`.
2. **Relax the tool to the policy as written**: accept stability between two settings even when both
   hit their caps, and report the cap as a caveat. Honest, but it means publishing numbers from runs we
   know did not settle.

Until one of these is chosen, queued reruns buy convergence evidence (do two settings agree?) but not
quotable results. Stating this now, before more CPU is spent, is the point of this note.

## 4. What is running

The remaining jobs were relaunched **detached** (so they survive the assistant session - an earlier
relaunch died with its parent after `k1c`):

```
k2c -> b1s1 -> b2e3 -> b2e4     (from the fixed tree, --timeout-s 14400, serial)
```

`k2c` started at 09:17; the log is `src22/repo/queue_rerun_weekend.log`, per-job logs in
`src22/repo/queue_logs/`, results land in `src22/repo/queue_results.json`.

## 5. Independent check

A separate verification pass recomputed the two `k1c` resonances from the raw CSVs (not from the
summary) and recorded its findings in `subagent_11_verify_k1c.md`; this note quotes only numbers that
survived that check.

## 6. Independent recomputation (2026-09-28)

The first verification attempt (a separate worker) failed on a provider error and returned nothing,
so the cross-check was redone here through a second, independent code path (plain `csv` + `math`,
not the verdict tool's parser). The numbers agree:

| run | points | deepest \|S11\| [dB] | at [GHz] | sample | at edge | end criteria | cap hit | last timestep |
|---|---|---|---|---|---|---|---|---|
| batch_k1c_prab_on | 101 | -7.84 | 2.4427 | 49 | no | never stated | yes | 400000 |
| batch_k1c_prab_off | 101 | -8.27 | 2.4353 | 48 | no | never stated | yes | 400000 |

Relative shift (band-mean denominator): **0.301 %** - identical to the verdict tool's 0.301 %.
Both runs ended by hitting the cap, so the verdict stands: **rejected, not quotable**.

