# Results ledger - what may be quoted, and why

The single place that answers "may this number be quoted?". One row per candidate result, with the
evidence that decides it. The rules it applies are in `docs/convergence-policy.md` (Route A = both
runs converged; Route B = cap-limited pair with a caveat; Route B mesh variant = same cap, declared
setting). A number is quotable only while its verdict file says so.

**Status today (2026-09-28 16:40): there are no quotable results yet.** Every candidate below is
either rejected or still waiting for its Route B pair. That is not a failure of the runs - the runs
now produce complete results - it is the acceptance rule doing its job until tonight's truncation
chains finish.

## Register

| candidate | raw value (f / depth) | pair, settings | shift | verdict file | status |
|---|---|---|---|---|---|
| k1c port_refine on/off | 2.4427 / -7.84 dB vs 2.4353 / -8.27 dB | 1e-4, cap 400k both | 0.301 % | `runs/verdict_k1c.json` | rejected (strict); Route B pair running |
| k2c loss on/off (FR-4) | 2.4133 GHz both; -0.45 vs -0.27 dB | 1e-4, cap 400k both | 0.000 % | `runs/verdict_k2c_fr4.json` | rejected (strict); no 300k partner yet |
| k2c PTFE vs FR-4 | 2.4427 vs 2.4133 GHz | 1e-4, cap 400k both | 1.209 % | `runs/verdict_k2c_mat.json` | rejected (strict) |
| b1s1 ground 0.25 vs 0.50 | 2.4427 vs 2.1417 GHz | 1e-4, cap 400k both | 13.129 % | `runs/verdict_b1s1.json` | rejected (strict); large physical signal |
| b2e3 feed probe vs line | 2.3067 / -4.52 dB vs 2.4390 / **-28.94 dB** | 1e-3, cap ~400k both | 5.576 % | `runs_b2/verdict_b2e3.json` | rejected (strict); **flagship candidate** |
| b2e4 (1e-4) | line arm still running | 1e-4, cap 400k | - | - | pending |

## Two facts that travel with the register

- **Determinism is not convergence.** The k2c PTFE arm reproduces the k1c port_refine-on arm bit for
  bit (2.4427 GHz / -7.84 dB). Repeating a configuration proves reproducibility, never stability; the
  verdict tool refuses same-cap repeats for exactly that reason.
- **The best match the project has produced is the coplanar line feed** (-28.94 dB, VSWR 1.07 at
  2.4390 GHz, b2e3). It becomes quotable only when the truncation pair (300k vs the 400k e4 run) says
  the answer does not move with run length.

## How a row changes state

1. A pair is run and `two_setting_verdict` is applied (with `--truncation-pair`, and
   `--differing-setting mesh` for mesh pairs).
2. The verdict JSON lands next to the run; the row here records its path, the shift and the status.
3. Accepted rows must be quoted together with the caveat the tool prints (caps, and the fact that the
   end criteria was never reached). Raw numbers without an accepted verdict stay out of any report.
