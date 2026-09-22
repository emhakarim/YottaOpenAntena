# Fabrication gate — when may a solver number be called design authority?

The project says, correctly, that it is **not** yet a design authority.  This file
makes that statement checkable: every condition below must hold before a simulated
resonance, efficiency or gain may be used to cut hardware.

| # | Condition | How it is demonstrated |
|---|---|---|
| 1 | **Run converged** — EndCriteria reached, not the timestep cap | `run_manifest.json` records `converged: true`; the timestep count is reported with every quoted number |
| 2 | **Construction bias closed or calibrated** | \|Δf\| vs an *independent* reference ≤ 1 %, **on at least two topologies**, or a correction factor applied with a written validity range (`yotta_tools/reference_table.py` prints the spread) |
| 3 | **Feed realisation matches what will be built** | probe vs coplanar inset stated explicitly (Y-19); the matching topology in the model is the one on the board |
| 4 | **Loss path validated** | dielectric loss checked against a known-Q reference or a measurement; conductor loss either modelled or explicitly waived in writing (today: metals are PEC) |
| 5 | **Benchmark set passed** | ≥ 2 independent topologies inside their stated tolerance (`docs/benchmarks.md`): today 1 of 2 |
| 6 | **Sensitivity reported** | mesh, ground-plane margin and feed-position sweeps show the operating point is not sitting on a steep slope |
| 7 | **Match achieved at the design frequency** | VSWR ≤ 2 after feed tuning, with R and X at resonance reported (not just \|S11\|) |
| 8 | **Artifacts archived** | `project.json`, `run_manifest.json`, `s11.csv`, `resonance_analysis.json` and the exact generator settings kept together |

## Status today (2026-09-21)

| # | Status |
|---|---|
| 1 | **partial** — manifest records `converged`, but no run is rejected automatically when it is false |
| 2 | **no** — residual bias −2.3 % … −5.0 % versus the cavity prediction; two topologies disagree |
| 3 | **no** — model realises a probe; the synthesis describes a coplanar inset |
| 4 | **no** — loss path active but never validated against a known Q; conductor loss absent (PEC) |
| 5 | **1 of 2** — tutorial anchor only; waveguide benchmark specified but not run |
| 6 | **partial** — mesh (0.9 %), feed (1.3 %) and ground-margin sweeps exist; the ground sweep still carries a confound |
| 7 | **yes at the tuned point** — VSWR 1.11 reported after feed tuning |
| 8 | **partial** — project/manifest/s11 kept; `resonance_analysis.json` now written |

**Conclusion:** conditions 2, 3 and 4 are the blockers.  Until they are met, every
solver number stays a *model output under test* — useful for comparing designs, not
for promising a frequency on a datasheet.

## Status re-scored (2026-09-22, with the day's evidence)

| # | Status | Change since 21 Sep |
|---|---|---|
| 1 | **partial** | unchanged - the coupling reader and the CLI refuse unconverged numbers, but runs are still not rejected automatically |
| 2 | **no** | unchanged - residual bias open; needs converged runs |
| 3 | **partial** | **was no** - the generator can now realise the coplanar inset (notched patch + printed line + port at the line end, mesh refined across the line); the differential run is with Yotta |
| 4 | **no** | unchanged - dielectric loss is native (Debye) but never validated against a known Q; metals are still PEC |
| 5 | **yes** | **was 1 of 2** - the TE10 waveguide benchmark passed (-0.0036 dB at 1.3 f_c) |
| 6 | **partial** | unchanged - the ground-margin sweep still carries a confound |
| 7 | **yes at the tuned point** | unchanged |
| 8 | **partial** | unchanged |

**Score: 4.0 / 8 = 50 %** (was 3.0 / 8 = 37.5 %).

**Blockers unchanged:** conditions **2** and **4** - both need converged runs, which is the real
bottleneck on this machine. Until they clear, every solver number stays *a model output under
test*: fine for comparing designs, not for promising a frequency on a datasheet.
