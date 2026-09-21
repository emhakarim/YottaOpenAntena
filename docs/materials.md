# Materials, composite mixing rules and their limits

## Built-in library

Values are **engineering reference values**, not certified measurements. The
`source_note` field on every built-in records where the number came from.

| Material | eps_r | tan delta | sigma (S/m) | Notes |
|---|---|---|---|---|
| air | 1.0 | 0 | 0 | by definition |
| PTFE (teflon) | 2.1 | 0.0004 | 0 | Dk 2.0–2.1, tan d ~0.0002–0.0004 (rfcafe.com lists 0.00028 @ 3 GHz; microwaves101.com lists Dk 2.1 / tan d 0.0004) |
| FR-4 | 4.4 | 0.02 | 0 | typical laminate; vendor- and frequency-dependent |
| RO4003C | 3.55 | 0.0027 | 0 | Rogers design values |
| RT/duroid 5880 | 2.2 | 0.0009 | 0 | Rogers design values |
| copper | 1.0 | 0 | 5.8e7 | bulk conductivity at room temperature |
| PEC | 1.0 | 0 | 1e30 | idealised; solver adapters should map this to a native PEC, not to kappa |

A material can also carry a frequency-dispersion model
(`{"model": "debye"|"lorentz"|"drude", ...}`), in which case
`complex_relative_permittivity()` evaluates the model instead of the static
`epsilon_r`.

Conduction loss is added on top of the bulk loss tangent:

```
tan_delta_total(f) = tan_delta + sigma / (2*pi*f*eps0*eps_r)
```

Note the frequency dependence: the same conductivity that dominates the loss at
100 MHz can be almost negligible at 6 GHz.

## Composite mixing rules

`materials/mixing.py` implements, for a two-phase composite (matrix + filler,
filler volume fraction `vf`):

| Model | Form | Character |
|---|---|---|
| Wiener upper | `vf*ef + (1-vf)*em` | parallel layering, hard upper bound |
| Wiener lower | `1 / (vf/ef + (1-vf)/em)` | series layering, hard lower bound |
| Lichtenecker | `em^(1-vf) * ef^vf` | logarithmic rule of mixtures |
| Maxwell-Garnett | spherical-inclusion EMA | dilute, asymmetric in the two phases |
| Bruggeman | symmetric effective medium | self-consistent, better at higher loading |

### Validity limits — read before using any number

These are **quasi-static, homogenised, effective-medium** results. They are only
defensible when *all* of the following hold:

1. every inclusion is much smaller than the wavelength in the surrounding
   medium and than the sample thickness;
2. the filler is statistically homogeneous, isotropic and disordered;
3. there is no percolating filler network — near and above the percolation
   threshold the true permittivity rises steeply and these rules undershoot
   badly;
4. interfacial (Maxwell-Wagner) polarisation is negligible — it is *not* at low
   frequencies, so below roughly 1 MHz the static picture fails;
5. there is no chemical interaction, no interphase layer, no voids, no moisture;
6. there are only two phases (air voids in a real laminate are a third phase).

`compare_models()` returns all of the above at once so the *spread between the
models* can be read as an uncertainty band, and three advisory functions
(`percolation_warning`, `maxwell_wagner_warning`, `quasi_static_warning`) emit
text when the inputs leave the defensible region. Those functions are warnings,
not physics models.

### Loss of a composite

`estimate_effective_tan_delta()` reports the series and parallel bounds of the
loss tangent and a volume-weighted reference number. This is an
order-of-magnitude estimate, not a model. The physically important point is
built into the returned notes:

> With a high-permittivity filler the electric field concentrates in the filler,
> so the *filler* loss dominates the composite loss, and a small volume fraction
> of a lossy high-eps filler can dominate the total. A volume-weighted average
> underestimates this.

This is the central engineering tension for the "high eps_r, low loss" goal: to
raise eps_r you must add a high-permittivity phase, and that phase usually brings
its own loss and its own dispersion. The toolkit's job is to expose that
trade-off quantitatively, not to hide it.

## Fitting measured data

`fit_debye_1pole(freqs, eps_real, eps_imag)` performs a grid search over the
relaxation time with a closed-form 2-parameter least-squares step for
`(eps_inf, delta_eps)` — no scipy required. The fit is unweighted, reports no
confidence interval, and is a curve fit; treat an out-of-range result as
numerical, not physical. Feed it measured permittivity data to obtain a
dispersive material model usable by a solver.

## Measurement over datasheet

Any design that depends on a material property must be validated against the
real batch of material. This matters most for home-made composites, where the
effective permittivity can drift by tens of percent between batches.
