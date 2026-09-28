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


## 7. k2c completed - the post-processing path works on every arm class (2026-09-28 12:54)

`k2c` (dielectric-loss validation: PTFE / FR-4 with loss / FR-4 without loss, 1e-4, cap 400k) finished
in 3.03 h. All three arms wrote `s11.csv` **and** the NF2FF products (`nf2ff_pattern.csv`,
`nf2ff_summary.csv`) - so the whole post-processing chain, not only the S11 write, is confirmed on
every arm class that used to die silently.

| arm | resonance [GHz] | deepest |S11| [dB] | VSWR | samples | converged | timesteps |
|---|---|---|---|---|---|---|---|
| loss_ptfe | 2.4427 | -7.84 | 2.365 | 101 | no | 400000 |
| loss_fr4 | 2.4133 | -0.45 | 38.4 | 101 | no | 400000 |
| loss_fr4_none | 2.4133 | -0.27 | 63.4 | 101 | no | 400000 |

**Mechanical verdicts** (`yotta_tools/two_setting_verdict.py`):

- loss on/off (fr4 vs fr4_none): shift **0.000 %** - yet *rejected*, because both arms are cap-limited
  (`runs/verdict_k2c_fr4.json`).
- material change (ptfe vs fr4): shift **1.209 %**, band "large shift (>=1 %)" - also rejected,
  cap-limited (`runs/verdict_k2c_mat.json`).

**Two things worth stating plainly.**

*Determinism is not convergence.* The PTFE arm reads 2.4427 GHz / -7.84 dB, bit-identical to the `k1c`
port_refine-on arm run hours earlier. Repeating a configuration reproduces it exactly - valuable for
reproducibility, useless as evidence of numerical convergence. The acceptance policy must never be fed
a same-configuration repeat: it would show a 0.000 % shift and look "stable" while proving nothing
about the mesh or the end criteria.

*The loss effect is second order at this mesh.* Enabling FR-4 loss moves the deepest |S11| from -0.27
to -0.45 dB at an unchanged 2.4133 GHz; switching the substrate from PTFE to FR-4 moves the resonance
by 1.209 % and costs ~7.4 dB of match depth. Both agree with ordinary expectation, and both remain
**hypotheses** here, because every run is cap-limited and therefore not quotable.

`b1s1` is in flight (timesteps 123k/132k at 35 min of wall time), then `b2e3` and `b2e4`; estimated
completion around 18:00.

## 8. b1s1 and b2e3 finished; b2e4 in flight (2026-09-28 16:03)

Four of the five relaunched jobs are now done. Every one of them wrote `s11.csv` - including `b2e3`,
which is the exact job that died at 01:19 on 23 Sep with `UnboundLocalError`. The fix is now proven on
all four job classes that used to fail.

| job | wall | result files | verdict |
|---|---|---|---|
| k1c | 1.59 h | 2 arms | rejected - cap-limited, 0.301 % |
| k2c | 3.03 h | 3 arms + NF2FF | rejected - cap-limited (0.000 % / 1.209 %) |
| b1s1 | 1.76 h | 2 arms | rejected - cap-limited, **13.129 %** |
| b2e3 | 1.63 h | 2 arms | rejected - cap-limited, **5.576 %** |

### b1s1 - ground-plane footprint 0.25 lambda0 vs 0.50 lambda0

| run | resonance [GHz] | deepest |S11| [dB] | VSWR | timesteps |
|---|---|---|---|---|---|
| gm025 | 2.4427 | -7.84 | 2.365 | 400000 |
| gm050 | 2.1417 | -5.62 | 3.197 | 400000 |

A 13.1 % resonance shift when the ground plane is doubled. The 0.25 lambda0 ground is only marginally
larger than the patch, so edge diffraction dominates - but this remains a **hypothesis**, because both
arms are cap-limited.

### b2e3 - feed coplanar probe vs line (EndCriteria 1e-3), 201-point sweep

| run | resonance [GHz] | deepest |S11| [dB] | VSWR | timesteps |
|---|---|---|---|---|---|
| probe | 2.3067 | -4.52 | 3.926 | 400000 |
| line | 2.4390 | **-28.94** | **1.074** | 399788 |

The feed implementation moves the resonance by 5.6 % and the match depth by 24 dB - the best-matched
result the project has produced. Both arms are still cap-limited and therefore **not quotable**; the
line feed is, however, the strongest physical signal seen so far and the natural first candidate for
the calibrated-criterion rerun.

### b2e4 - in flight

Started 15:41. The probe arm reported 165,326 / 400,000 steps at 56.6 MCells/s with energy -10.5 dB
(the run stops early at -40 dB); the line arm follows. Estimated completion ~17:20-17:30.

## 9. Route B adopted and automated (2026-09-28, 16:26)

The owner approved the truncation-stability route. It is now the written policy, code, and a running
experiment, in that order:

- **Policy** - `docs/convergence-policy.md` gained **Route B**: two runs that both stopped at their
  caps, with the caps at least 5 % apart, are accepted when their resonances agree within 0.2 % and
  neither minimum sits on a sweep edge. The accepted value must be quoted *with* the caveat: both
  truncation levels, and the fact that the end criteria was never reached. A same-cap repeat is
  rejected by construction - it demonstrates determinism, not stability.
- **Tool** - `yotta_tools/two_setting_verdict.py --truncation-pair` implements Route B and prints the
  caveat; four new tests cover the accepted pair, the same-cap rejection, the too-large shift, and the
  CLI switch. Suite: 468 tests OK (skipped=36). Commit `deabbefd`.
- **Runs, automated** - three detached chains run back to back after `b2e4`: a 300k port-refine pair
  against the existing 400k runs, its Route B verdicts, then a 300k B2 feed pair (line/probe) against
  the 400k `b2e4` runs and its verdicts. Expected to finish around 20:30; the monitor reports the
  verdicts or, if the provider keeps refusing, the files are waiting regardless.

**What Route B does not bound.** It shows the answer no longer moves when the run is *lengthened*. It
says nothing yet about the **mesh** - a finer mesh could still move the resonance. A mesh-sensitivity
check (two mesh densities on the flagship configuration) is therefore the next required step after the
first accepted number, and it is recommended in those words rather than implied.

**Flagship candidate.** The coplanar line feed: deepest match of the project so far, -28.94 dB
(VSWR 1.07) at 2.4390 GHz, 5.6 % below the probe arm's resonance. Its Route B verdict is what turns it
from the strongest signal into the first quotable result.

**Provenance.** The 300k chains run from `src22/repo`, which predates the corporate-feed implementation
on `main`; B2 does not use that mode, so results stay comparable with `b2e3`/`b2e4`.
