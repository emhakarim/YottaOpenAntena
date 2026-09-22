# Data-collection playbook (supporting literature)

**Who this is for:** an agent (or person) with better literature access than the one that wrote it.
**What it unblocks:** review item **Y-T3 / Y-6** - validating the four mixing rules against *measured*
two-phase composites - and, secondarily, external anchors for the loss and calibration work.

**Why it is written down at all:** the work stopped for an honest reason, and the reason is recorded
here so the next attempt does not repeat it. The search provider available at the time returned only
domain-level URLs, so article pages could not be opened, so no value was ever verified. Snippet values
were collected into `data/composite_measurements_candidates.md` and then **deliberately not promoted**
to `data/composite_measurements.csv`. Two of the values are traceable to a named paper (C1, C3); the
rest are weaker leads. None of them may be used as data until they pass the checks in §4.

---

## 1. Definition of done

The task is done when **`data/composite_measurements.csv` exists and every row in it passes §4**, and
this command runs without a single skipped-row complaint:

```
python yotta_tools/mixing_validation.py data/composite_measurements.csv
```

(The validator's default argument is already that path; rows with problems are reported and
skipped - never silently "fixed".)

A smaller honest file beats a bigger doubtful one. **A row you could not verify is a row you leave
out** - not a row you guess, and not a row you mark "probably".

## 2. Exact file schema

The first nine columns are the validator's canonical header, verbatim (it reads by column name and
**skips rows it cannot parse**, so do not rename them):

```
matrix_material,eps_matrix,filler_material,eps_filler,vf,freq_hz,eps_eff_measured,tand_measured,source_doi
```

Everything after `source_doi` is provenance for the report and the audit trail; append it in this
order so files written by different agents stay comparable:

```
method,temperature_c,eps_matrix_source,eps_filler_source,source_title,source_authors,source_year,source_locator,verification,verified_by,verified_on,notes
```

| column | what it must contain | why it is required |
|---|---|---|
| `matrix_material`, `filler_material` | material names, e.g. `PTFE`, `CaTiO3` | the label the report prints |
| `eps_matrix` | permittivity of the pure matrix **at the same frequency** | inversion input (required) |
| `eps_filler` | permittivity of the pure filler at the same frequency | **the field that blocked Y-T3**; without it the rules cannot be inverted (required) |
| `vf` | **volume** fraction of filler, a number in [0, 1] - `0.50`, never `50` | mixing rules are volume-based and the validator rejects `vf` outside [0, 1] (required) |
| `freq_hz` | measurement frequency in Hz | the rules are quasi-static; a 1 MHz value may not be compared with a 10 GHz one |
| `eps_eff_measured` | relative permittivity of the composite as measured | the target the rules must reproduce (required) |
| `tand_measured` | loss tangent at the same frequency | optional; leave empty if not given |
| `source_doi` | DOI of the paper the value came from | APA-7 citation in the report is generated from this |
| `eps_matrix_source` | DOI + locator, or `project library` (PTFE = 2.1 etc.) | traceability |
| `eps_filler_source` | DOI + locator, or `same paper` | filler values often come from a *different* paper than the composite - say which |
| `method` | e.g. `resonant cavity`, `waveguide`, `SPDR` | tells the reader how much to trust it |
| `temperature_c` | usually 25 | dispersion and loss are temperature-dependent |
| `source_title` … `source_year` | full citation fields | completeness when a DOI is missing |
| `source_locator` | e.g. `Table 3, 50 vol% row` or `Fig. 5, read at 10 GHz` | a reviewer must be able to find the number, not just the article |
| `verification` | `two-source`, `single-source`, `read-from-figure` | see §4 |
| `verified_by`, `verified_on` | who/when | audit trail |
| `notes` | conversions, caveats, discrepancies | everything a reader would otherwise have to guess |

## 3. How to obtain the sources

Work in this order; stop as soon as you have the full text with the table.

1. **DOI resolution first.** `https://doi.org/<doi>` gives the publisher landing page. The DOI is in
   the candidate list for C3 (`Appl. Phys. Lett. 95, 062903`, 2009); find the rest from the titles.
2. **Free and authoritative before paywalled.** Manufacturer datasheets (e.g. Rogers laminate data
   sheets give `eps_r` and `tan delta` with frequency) and **NIST** metrology publications are free,
   citable and usually better documented than a random journal table.
3. **Open-access mirrors**: publisher OA versions, arXiv, institutional repositories, ResearchGate
   full-text uploads. Read pages with the page-reading tool; if a raw source URL
   (`raw.githubusercontent.com`) returns empty, fetch it with a plain HTTP client instead.
4. **PDFs**: if you get a PDF, extract tables with the PDF reader rather than retyping; retyping is
   where digits get transposed.
5. **When the text is behind a paywall**: do not substitute the abstract's rounded claim ("about 12")
   for the table value. Either find another paper for the same composite, or leave the row out and
   record the attempt in `notes` of `data/composite_measurements_candidates.md`.

Record for every row: *where* the number is (table/figure), *at what frequency*, and *by what method*.

## 4. Verification rules (the part that makes the file usable)

* **Snippet is not a source.** A search-result snippet never satisfies §2. If that is all you have,
  the row stays in the candidates file.
* **Two independent sources** for the same composite, or mark the row `single-source`. Single-source
  rows may be *reported* but must never carry a conclusion on their own.
* **Read from a figure** is allowed only with `verification=read-from-figure`, an estimated
  uncertainty in `notes` ("read at 10 GHz, +/-3 %"), and the figure number in `source_locator`.
* **Recompute the Wiener bounds** (they are derived from `vf`, `eps_matrix`, `eps_filler` by
  `yotta_tools.mixing_validation`) and reject any row where
  `eps_eff_measured` falls outside them. Physics says that cannot happen; if it does, you have a
  transcription error, a wrong `vf`, a wrong phase role, or a different frequency.
* **Frequency consistency**: `eps_matrix`, `eps_filler` and `eps_eff_measured` must be at
  `frequency_hz`. A DC or 1 MHz filler permittivity (BaTiO3 is ~2000 DC and much lower at GHz)
  mixed with a 10 GHz composite value is a silent, large error.
* **`vf` is a fraction, not a percentage.** `0.50`, not `50`; the validator rejects anything outside
  [0, 1]. Papers often give *weight* percent: convert with the densities of both phases and record the
  densities and the conversion in `notes`.

## 5. Candidate leads, and exactly what each is missing

From `data/composite_measurements_candidates.md` (snippet-level; treat as leads, not data):

| id | composite | measured | missing before it can be used |
|---|---|---|---|
| C1 | PTFE / CaTiO3, vf 0.50, 10 GHz | eps_r 12, tan d 8.5e-4 | `eps_filler`, DOI. **Best candidate**: PTFE is in the project library (2.1), and the measured 12 is already high enough to be interesting |
| C2 | PTFE / (TiO2+CaTiO3), vf 0.46, 10 GHz | eps_r 7.42, tan d 0.0022 | `eps_filler`, DOI, exact author/year |
| C3 | Polyethylene / ceramic, vf 0.40, 8 GHz | eps_r 12.1, tan d 0.004 | `eps_filler`, PE permittivity at 8 GHz, DOI (APL 95, 062903, Subodh 2009) |
| C4 | HDPE / BNT, vf 0.40, 7 GHz | eps_r 10, tan d 7e-4 | `eps_filler`, HDPE permittivity, DOI |
| C5 | polymer / MgTiO3, vf 0.50 | eps_r 3.2 | matrix identity, frequency, both pure-phase values, DOI |
| C6 | epoxy / BaTiO3 | eps_r 466.8 | `vf`, frequency, `eps_filler` at that frequency, DOI |

## 6. What the analysis will do with the finished file

`yotta_tools/mixing_validation.py` inverts each rule for the filler permittivity and reports, per row:
the filler value each rule *requires* to reproduce the measurement, plus the spread across rules and
the Wiener bounds. Two known behaviours to expect, and **neither is an error**:

* **Maxwell-Garnett has no solution** for high-contrast composites - it saturates (around 8.4 for C1's
  parameters), so no filler value can produce the measured 12. "No solution" is the result.
* **Lichtenecker** typically lands closest for ceramic-filled polymers; Bruggeman sits between;
  **Wiener bounds** are the sanity envelope, not a predictor.

Report the spread honestly: a wide spread means the data cannot distinguish the rules, which is a
finding, not a failure. The earlier inversion run (before this block) gave, for C1, a Lichtenecker
filler value of 68.6 and a Bruggeman value of 34.0 with MG unsaturated - if the verified row later
gives a very different picture, say so rather than smoothing it over.

## 7. Secondary targets (cheaper, still valuable)

* **Loss anchor**: a manufacturer datasheet value (`eps_r`, `tan delta`, frequency) for a laminate the
  project can model gives an external check on the `--loss-model kappa`/`debye` work. Free to obtain.
* **Calibration anchor**: a *measured* patch resonance with its geometry and substrate, to compare
  against the 2.26 % residual the project currently carries. Record the same fields as §2, with
  `verification` per §4.

## 8. Handover checklist

1. `data/composite_measurements.csv` written with the verbatim header from §2.
2. Every row passes §4 (bounds recomputed, frequency consistent, verification label set).
3. `python yotta_tools/mixing_validation.py data/composite_measurements.csv` runs clean (no skipped rows).
4. Rows that could **not** be verified: left out, with the attempt noted in
   `data/composite_measurements_candidates.md`.
5. Commit message states how many rows were added and from which sources; push, and say in the
   report which conclusions are supported by measured data and which are not.
