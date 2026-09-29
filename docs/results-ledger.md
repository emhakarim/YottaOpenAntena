# Results ledger - what may be quoted, and why

The single place that answers "may this number be quoted?". One row per candidate result, with the
evidence that decides it. The rules it applies are in `docs/convergence-policy.md` (Route A = both
runs converged; Route B = cap-limited pair with a caveat; Route B mesh variant = same cap, declared
setting). A number is quotable only while its verdict file says so.

**Status (2026-09-29): the first quotable results exist.** The B2 coplanar line feed and the probe
feed passed their cap-limit (Route B) truncation pairs: the resonance does not move between the 300k
and the ~400k run (`runs_b2/verdict_trunc_line.json`, `runs_b2/verdict_trunc_probe.json`). Everything
else in the register is still rejected - most of it because the answer DOES move with run length
(> 0.2 %), which is exactly what the pair test exists to reveal. Accepted rows must be quoted together
with the caveat the tool prints (the two caps, and the fact that the end criteria was never reached).

## Register

| candidate | raw value (f / depth) | pair, settings | shift | verdict file | status |
|---|---|---|---|---|---|
| **b2 line feed truncation** | 2.4390 GHz; -16.38 dB @300k vs **-28.94 dB @399,788** | Route B, caps 300000/399788 | **0.000 %** | `runs_b2/verdict_trunc_line.json` | **ACCEPTED - quotable with caveat** (resonance stable; depth still deepening at 300k) |
| **b2 probe feed truncation** | 2.3030 vs 2.3067 GHz; -3.04 vs -4.52 dB | Route B, caps 300000/400000 | **0.159 %** | `runs_b2/verdict_trunc_probe.json` | **ACCEPTED - quotable with caveat** |
| b2 line vs probe | 2.4390 vs 2.3030 GHz | different feeds (informational) | 5.735 % | `runs_b2/verdict_trunc_lvsp.json` | rejected (not a stability pair; feed comparison only) |
| b2e3 / b2e4 feed probe vs line | probe 2.3067 / -4.52 dB vs line 2.4390 / **-28.94 dB** | 1e-3 / 1e-4, cap ~400k | 5.576 % | `runs_b2/verdict_b2e3.json`, `runs_b2/verdict_probe_e3_vs_e4.json`, `runs_b2/verdict_line_e3_vs_e4.json` | rejected (strict); **the line remains the flagship match and is quotable now via its Route B pair above** |
| k1c port_refine on/off | 2.4427 / -7.84 dB vs 2.4353 / -8.27 dB | 1e-4, cap 400k both | 0.301 % | `runs/verdict_k1c.json` | rejected (strict) |
| k1c truncation pairs | on: 2.4573@300k vs 2.4427@400k; off: 2.4427 vs 2.4353 | Route B | 0.599 % / 0.301 % | `runs/verdict_truncB_on_vs_400k.json`, `runs/verdict_truncB_off_vs_400k.json` | rejected (shift > 0.2 %) |
| k2c loss FR-4 truncation pair | 2.0830 GHz (sweep edge) @300k vs 2.4133 @400k | Route B | - | `runs/verdict_truncB_loss_fr4.json` | rejected (minimum at a sweep edge - artefact) |
| k2c loss FR-4-none truncation pair | 2.8170 GHz (sweep edge) @300k vs 2.4133 | Route B | - | `runs/verdict_truncB_loss_fr4_none.json` | rejected (edge artefact) |
| k2c PTFE truncation pair | 2.4573 vs 2.4427 | Route B | 0.599 % | `runs/verdict_truncB_loss_ptfe.json` | rejected |
| b1s1 ground 0.25/0.50 | 2.4427 vs 2.1417 GHz | 1e-4, cap 400k both | 13.129 % | `runs/verdict_b1s1.json` | rejected (strict); large physical signal |
| b1s1 gm025 truncation pair | 2.4573 vs 2.4427 | Route B | 0.599 % | `runs/verdict_truncB_gm025.json` | rejected |
| b1s1 gm050 truncation pair | 2.0830 GHz (edge) vs 2.1417 | Route B | - | `runs/verdict_truncB_gm050.json` | rejected (edge artefact) |
| mesh 15 vs 20 (same cap) | 2.4573 vs 2.4206 GHz | mesh pair, cap 300k | 1.5047 % | `runs/verdict_mesh_pair.json` | rejected (shift > 0.2 %; the mesh20 arm actually met the -40 dB energy criterion at 32,148 steps - the tool labels clean early stops "unverified", fix queued) |
| mesh15 vs k1c 400k | 2.4573 vs 2.4427 | Route B | 0.599 % | `runs/verdict_mesh15_vs_400k.json` | rejected |

## Three facts that travel with the register

- **Determinism is not convergence.** The list is now five families long: (1) the k2c PTFE arm
  reproduces the k1c port_refine-on arm bit for bit (2.4427 GHz / -7.84 dB); (2) b2e4 probe
  reproduces b2e3 probe (2.3067 / -4.52, VSWR 3.926); (3) b2e4 line reproduces b2e3 line
  (2.4390 / -28.94, VSWR 1.074, 399788 steps both); (4) the default configuration at 300k was
  produced by four different batches (prab_on, loss_ptfe, gm025, mesh15) with **byte-identical
  `s11.csv`** (sha256 prefix 9609B3905F4F); (5) the same at 400k by three batches (k1c_prab_on,
  k2c_loss_ptfe, b1s1_gm025; prefix F7DBFAB2AB64). Repeating a configuration proves reproducibility,
  never stability; the verdict tool refuses same-cap repeats for precisely that reason.
- **The first quotable results.** b2 line: f_res 2.4390 GHz, -28.94 dB / VSWR 1.07 at cap 399,788
  (`runs_b2/verdict_trunc_line.json`, shift 0.000 %; caveat: caps 300000/399788, end criteria never
  reached). b2 probe: 2.3067 GHz, -4.52 dB at cap 400k (0.159 %; same caveat). The line is the best
  match the project has produced and is now quotable **with the caveat**, not as a converged result.
- **The mesh question is open and matters (~1.5 %).** mesh20 stopped cleanly at 32,148 steps having
  met the -40 dB energy criterion and lands at 2.4206 GHz; the cap-limited mesh15 (default mesh)
  sits at 2.4573 GHz. A third of the campaign exists precisely to close this; the mesh verdict row
  stays rejected until a proper pair is possible.

## How a row changes state

1. A pair is run and `two_setting_verdict` is applied (with `--truncation-pair`, and
   `--differing-setting mesh` for mesh pairs).
2. The verdict JSON lands next to the run; the row here records its path, the shift and the status.
3. Accepted rows must be quoted together with the caveat the tool prints. Raw numbers without an
   accepted verdict stay out of any report.
