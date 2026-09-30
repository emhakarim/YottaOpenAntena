# Results ledger - what may be quoted, and why

The single place that answers "may this number be quoted?". One row per candidate result, with the
evidence that decides it. The rules it applies are in `docs/convergence-policy.md` (Route A = both
runs converged; Route B = cap-limited pair with a caveat; Route B mesh variant = same cap, declared
setting). A number is quotable only while its verdict file says so.

**Status (2026-09-30): three quotable results - line, probe, and the tuned m050 - plus an accepted
mesh pair on the winner.** The B2 line and probe passed their Route B truncation pairs
(`runs_b2/verdict_trunc_line.json`, `runs_b2/verdict_trunc_probe.json`); the overlap campaign's m050
passed its Route B pair (`runs_b2/overlap/followup/verdict_m050_sweep300000_vs_400000.json`) and its
mesh pair came back Route A with no caveat (`runs/verdict_winE_mesh.json`). Everything else in the
register is rejected - most of it because the answer DOES move with run length (> 0.2 %), which is
exactly what the pair test exists to reveal. Route B rows must be quoted together with the caveat the
tool prints (the two caps, and the fact that the end criteria was never reached).

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
| mesh 15 vs 20 (same cap) | 2.4573 (cap-limited) vs 2.4206 (converged) GHz | mesh pair, cap 300k | 1.5047 % | `runs/verdict_mesh_pair.json` | rejected - mixed stop conditions (mesh20 confirmed CONVERGED at 32,148 steps after the 2026-09-29 parser fix; a clean mesh pair needs equal stop conditions on both arms; pre-fix copy kept as `runs/verdict_mesh_pair_pre-fix.json`) |
| mesh15 vs k1c 400k | 2.4573 vs 2.4427 | Route B | 0.599 % | `runs/verdict_mesh15_vs_400k.json` | rejected |
| **m050 winner truncation pair (step D)** | 2.4280 GHz; -16.90 dB @300k vs 2.4316 GHz; **-26.96 dB @399,788** | Route B, caps 300000/399788 | **0.151 %** | `runs_b2/overlap/followup/verdict_m050_sweep300000_vs_400000.json` | **ACCEPTED - quotable with caveat** (tuned overlap -0.5 mm; depth still deepening at 300k) |
| **m050 winner mesh pair (step E)** | 2.4280 GHz in both meshes; -11.2 / -6.79 dB | Route A "stability", both converged (1,481,436 / 32,034 steps) | **0.000 %** | `runs/verdict_winE_mesh.json` | **ACCEPTED - quotable, no tool caveat** (101-point grid: sub-grid drift not resolved) |

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
- **The mesh question is closed (2026-09-30) - the ~1.5 % gap was geometry-specific.** On the winner
  geometry both meshes converge to the SAME resonance: mesh15 at 1,481,436 steps and mesh20 at
  32,034 steps both report 2.4280 GHz (shift 0.000 %; `runs/verdict_winE_mesh.json`, Route A, no
  caveat). The base-geometry gap (2.4573 vs 2.4206 GHz) does not reproduce on the tuned design.
  The old mesh-variant register row stays rejected as history; the winner pair is the row to cite.

## How a row changes state

1. A pair is run and `two_setting_verdict` is applied (with `--truncation-pair`, and
   `--differing-setting mesh` for mesh pairs).
2. The verdict JSON lands next to the run; the row here records its path, the shift and the status.
3. Accepted rows must be quoted together with the caveat the tool prints. Raw numbers without an
   accepted verdict stay out of any report.

## Campaign log: steps A + D + E - overlap sweep, winner confirmation, mesh close-out (2026-09-29/30)

Run on the line feed, cap 300000 @ 1e-4, band 2.4-2.5 GHz, two workers; per-point runs, logs and the
summary live under `runs_b2/overlap/` (`sweep_summary.json`, `winner.txt`). Every point is
cap-limited (`converged=false`), so **none of these numbers may be quoted** - the sweep only
screens. The baseline point doubles as a determinism check and reproduces the accepted line-feed
resonance (2.4390 GHz).

| tag | inset delta | f_res (GHz) | \|S11\| (dB) | VSWR |
|---|---|---|---|---|
| m100 | -1.0 mm | 2.4316 | -16.858 | 1.335 |
| **m050 - winner** | **-0.5 mm** | **2.4280** | **-16.901** | **1.333** |
| p000 - baseline | 0.0 mm | 2.4390 | -16.376 | 1.358 |
| p050 | +0.5 mm | 2.4390 | -16.391 | 1.357 |
| p100 | +1.0 mm | 2.4426 | -16.020 | 1.376 |

Winner = m050 (deepest |S11| with f_res inside the 2.40-2.50 GHz window). Step D re-ran it at cap
400000 and the truncation pair came back **ACCEPTED** (shift **0.151 %** <= 0.20 %; caps
300000/399788): 2.4280 GHz / -16.90 dB / VSWR 1.333 at 300k vs 2.4316 GHz / **-26.96 dB** /
VSWR 1.094 at 399,788 - the third quotable result, under the usual Route B caveat that the end
criteria was never reached (`runs_b2/overlap/followup/verdict_m050_sweep300000_vs_400000.json`).

**Step E (2026-09-30 00:54) - mesh pair on the winner: ACCEPTED, no caveat.** Equal stop conditions
by construction: both arms reached the 1e-4 end criteria (mesh15 at 1,481,436 steps, -40.10 dB;
mesh20 at 32,034 steps), so the pair is Route A "stability" (`runs/verdict_winE_mesh.json`). Both
meshes put the resonance at **2.4280 GHz - shift 0.000 %**, so the ~1.5 % mesh gap seen on the base
geometry does NOT reproduce on the tuned winner. Quoting note: 101-point grid (7.34 MHz step,
sub-grid drift not resolved); depths differ between meshes (-11.2 / -6.79 dB).

## Reference design (m050) - the campaign deliverable, consolidated

The optimization plan's deliverable was "a matched reference design at 2.45 GHz quoted with an
accepted truncation verdict + an accepted mesh verdict + full provenance". That is the row set below;
this section is the one place to read the design's parameters.

**Geometry** (as built; `runs/batch_winE_mesh15|20/project.json`, `runs_b2/overlap/followup/m050/line`):
- Patch 49.1427 x 41.3789 mm with a coplanar **line** feed (50-ohm line width 5.1005 mm), inset
  **14.1578 mm** = the synthesised 14.6578 mm minus the swept 0.50 mm overlap winner.
- PTFE substrate 1.60 mm; ground margin 0.25 lambda0; loss model kappa; sweep 2.083-2.817 GHz.

**Quotable numbers (with their accepted verdicts):**
1. **Resonance, Route B pair** (caps 300000/399788): 2.4280 GHz / -16.90 dB / VSWR 1.333 at 300k;
   2.4316 GHz / **-26.96 dB** / VSWR 1.094 at 399,788; shift **0.151 %** -
   `runs_b2/overlap/followup/verdict_m050_sweep300000_vs_400000.json`. Caveat: the end criteria was
   never reached at either cap.
2. **Mesh stability, Route A pair** (both converged): mesh15 at 1,481,436 steps and mesh20 at 32,034
   steps both report **2.4280 GHz**, shift **0.000 %** - `runs/verdict_winE_mesh.json`, no tool caveat
   (grid note: 101 points, 7.34 MHz step).

**Honest notes when quoting:**
- At the confirmation cap the depth (-26.96 dB) is comparable to, and slightly shallower than, the
  base-geometry line feed (-28.94 dB at 399,788); the tuned point's gains are the accepted mesh
  verdict and the swept-neighbourhood evidence, not a deeper match at 400k.
- f_res at the quote cap sits just inside the [2.43, 2.47] GHz window (lower edge). If closer
  centring at 2.45 GHz is wanted, plan step C (patch-length nudge, 1-2 points plus full
  re-verification) is the next campaign slot - not scheduled.
