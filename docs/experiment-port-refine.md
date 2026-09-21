# Experiment: does port-region mesh refinement move the resonance? (Yotta item A4)

**Hypothesis.** The lumped port feeds a load across the substrate.  If the lateral
cell around it is the coarse free-space cell (~λ/15), the excitation is discretised
badly and the port contributes series inductance — a candidate for the residual
construction bias (currently **−2.3 % … −5.0 %** against the cavity prediction,
see `yottakomen.md` §19.2).

**Design rule: one variable changes.**  Same project, same mesh density, same
margin/boundary/snapping — only `port_refine` differs.

## 1. Generate both models

```python
from pathlib import Path
from openantenna.model.project import ArrayConfig, FrequencySweep, PatchGeometry, Project, SubstrateStackup
from openantenna.solvers.openems import OpenEMSSolver

def project(name: str) -> Project:
    return Project(
        name=name,
        substrate=SubstrateStackup.single("PTFE", 1.6e-3),
        patch=PatchGeometry(width_m=0.049142672841793994, length_m=0.041378916081297096, feed_mode="inset"),
        array=ArrayConfig(nx=1, ny=1),
        sweep=FrequencySweep(start_hz=2.083e9, stop_hz=2.817e9, points=101),
    )

OpenEMSSolver(port_refine=True).prepare(project("a4_on"), Path("runs/a4_on"))
OpenEMSSolver(port_refine=False).prepare(project("a4_off"), Path("runs/a4_off"))
```

Then run each generated `sim.py` through the committed launcher:

```powershell
$env:OPENEMS_ROOT = "<folder holding openEMS.exe / CSXCAD.dll>"
python scripts/run_with_openems.py runs\a4_on\sim.py
python scripts/run_with_openems.py runs\a4_off\sim.py
```

**Do the same pair on the tutorial geometry** (`scripts/generator_anchor_test.py`
already holds the tutorial parameters), so the result is not tied to one patch.

## 2. Read the result with the reference table

```powershell
python yotta_tools/reference_table.py runs\a4_on runs\a4_off
```

It recomputes the cavity prediction from each run's own `project.json`, so both
rows are compared against **one** reference type, and it prints whether the bias is
constant or moving.  Also copy the `converged` / timestep numbers from each
`run_manifest.json` (`docs/verification.md` rule: a run that did not converge
cannot support a resonance claim).

## 3. Decision thresholds (agree before looking at the numbers)

| Outcome | Meaning | Action |
|---|---|---|
| Δf ≥ 0.5 % between on/off | the port discretisation matters | keep `port_refine=True` as default, cite it in the bias explanation, record the run |
| 0.2 % ≤ Δf < 0.5 % | marginal | keep the default (cheap), but do **not** use it to explain the remaining bias |
| Δf < 0.2 % | cosmetic for this geometry | write the hypothesis as **gugur** in `docs/verification.md` (do not delete it) |

## 4. Cost to watch

Refinement adds mesh lines, so the cell count and runtime rise.  Report both
(`timesteps`, wall-clock) next to Δf: a 0.1 % accuracy gain for a 3× runtime is a
bad trade unless it also improves the *convergence* of the S11 minimum.

## 5. What would falsify the hypothesis

* The tutorial geometry shows the same residual bias **without** any port-region
  sensitivity → then the remaining difference is structural (ground footprint,
  feed realisation, mesh-line placement), not discretisation of the excitation.
