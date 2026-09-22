# Dispersive (Debye) substrates

**Status: supported and verified in the real engine** (openEMS 0.37.0-rc2 / CSXCAD 0.7.0-rc2).

An earlier finding in this project claimed the installed CSXCAD has *no* dispersive-material
API, so a Debye dielectric could only be approximated by a constant conductivity. **That was
wrong**, and the way it was wrong is worth recording: the inspection looked at the `CSXCAD`
top level and at a `CSPropMaterial` instance. The dispersive classes live in the
**`CSXCAD.CSProperties` submodule**, and they are reachable only through the sequence below.

## The recipe

```python
from CSXCAD import CSProperties

substrate = CSProperties.CSPropDebyeMaterial(CSX.GetParameterSet(), "substrate")
substrate.SetDispersionOrder(1)                       # number of poles: N
substrate.SetDispersiveMaterialProperty(0,            # pole index - 0-based!
                                        eps_delta=...,  # eps_s - eps_inf
                                        eps_relax=...)  # tau [s]
substrate.SetMaterialProperty(epsilon=..., mue=...)   # eps_inf (and mu_inf)
CSX.AddProperty(substrate)                            # REQUIRED: registers the property
substrate.AddBox(...)                                 # geometry, as for any material
```

Three traps, all of them silent:

1. **`SetDispersiveMaterialProperty(order, **kw)` - the first argument is the pole index, not
   a value.** Passing a value gives `IndexError: Invalid dispersive media order requested`.
   Poles are 0-based in Python (`EpsilonDelta_1` in the XML is order 0 here).
2. **`CSX.AddProperty` is mandatory.** Without it the property never enters the structure, the
   model XML contains an empty `<Properties />` and nothing tells you why.
3. **Property names are Debye-specific**: `eps_delta` and `eps_relax` (Lorentz uses
   `eps_plasma`, `eps_pole_freq`, `eps_relax`; `mue_*` variants exist for magnetic poles).

## What the engine reports

With the pole set, openEMS prints on startup:

```
--- Drude/Lorentz Dispersive Material Extension ---
Max. Dispersion Order N = 1
#7: Drude/Lorentz Dispersive Material Extension (0)
```

That line is the acceptance evidence: the engine registered a dispersive material with order 1.

## Where the values come from

* If the material carries a Debye description in the library
  (`dispersion={"model": "debye", "eps_inf":, "delta_eps":, "tau_s":}`), it is used verbatim.
* Otherwise a single pole is placed at `omega*tau = 1` at the reference frequency with
  `eps_delta = 2*tan_delta*eps_r`, which reproduces the requested `tan(delta)` there - the
  same loss level as `loss_model="kappa"`, so the two models can be compared fairly.
  Above the relaxation the Debye loss falls as 1/f, below it rises: that is the physical
  behaviour the constant-conductivity model cannot have.

## Relation to `yotta_tools/loss_fit.py`

`loss_fit` remains useful for engines *without* dispersion support: it quantifies how well a
banded constant-kappa approximation tracks a Debye (worst case ~36 % near a relaxation peak
with 5 bands over 1-6 GHz, <12 % with 17) and can recover `(eps_s, eps_inf, tau)` from
tabulated `tan(delta)(f)`. With a dispersive engine available, prefer this native path.
