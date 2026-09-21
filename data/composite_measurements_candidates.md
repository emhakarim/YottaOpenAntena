# Candidate measured composites for Y-T3 (snippet-level — NOT yet verified data)

Purpose: collect measured two-phase composites from open literature so the four mixing
rules can be checked against reality (`yotta_tools/mixing_validation.py`).

**Status: candidates only.** Every row below comes from a **search snippet**, not from
the full text — the search provider used here returns domain-level URLs, so the article
pages could not be opened. Nothing here is a substitute for the full text, and the file
`data/composite_measurements.csv` should only be created once the values are verified
against the sources.

## 1. Candidates

| # | Composite | vf | measured εr | tan δ | f | Matrix | Filler | Source (snippet) | Missing |
|---|---|---|---|---|---|---|---|---|---|
| C1 | PTFE / CaTiO₃ | 0.50 | **12** | 8.5e-4 | 10 GHz | PTFE | CaTiO₃ | Hu 2011, *Microwave dielectric properties of PTFE/CaTiO₃* (ScienceDirect) | εr filler, DOI |
| C2 | PTFE / (TiO₂+CaTiO₃) | 0.46 | **7.42** | 0.0022 | 10 GHz | PTFE | TiO₂+CaTiO₃ | 2026 ResearchGate record, "Effects of CaTiO₃ loading on PTFE/TiO₂" | εr filler, DOI |
| C3 | Polyethylene / ceramic | 0.40 | **12.1** | 0.004 | 8 GHz | PE | ceramic (unspecified in snippet) | Subodh 2009, *Dielectric response of high permittivity polymer ceramic composite*, Appl. Phys. Lett. 95, 062903 | εr filler, matrix PE value, DOI |
| C4 | HDPE / BNT ceramic | 0.40 | **10** | 7e-4 | 7 GHz | HDPE | BNT | Zhang 2015 (scientific.net) | εr filler, matrix HDPE value, DOI |
| C5 | Polymer / MgTiO₃ | 0.50 | **3.2** | – | – | polymer (unspecified) | MgTiO₃ (micro-filler) | ResearchGate record | matrix + filler εr, frequency, DOI |
| C6 | Epoxy / BaTiO₃ | low | **466.8** | – | – | epoxy | BaTiO₃ | ACS 2022, "Obtaining greatly improved dielectric constant in BaTiO₃–epoxy" | vf value, εr filler, frequency, DOI |

Only C1 and C2 have a matrix whose permittivity the project's own library defines
(PTFE = 2.1), so those two can already be used for a partial analysis (§2).

## 2. Partial analysis — the inverse question, answered with the project's own models

Instead of guessing the filler permittivity, ask: **which filler εr would each model need
in order to reproduce the measurement?** (numerical inversion of `materials.mixing`,
matrix = PTFE from the project library; bisection over εf ∈ [1, 20000]).

| Case | Lichtenecker | Maxwell-Garnett | Bruggeman | Wiener upper bound |
|---|---|---|---|---|
| **C1** (vf 0.50, measured 12) | εf = **68.6** | **no solution** (MG saturates ≈ 8.4 at vf = 0.5) | εf = **34.0** | εf ≥ **21.9** |
| **C2** (vf 0.46, measured 7.42) | εf = **32.7** | εf = **1332** | εf = **20.4** | εf ≥ **13.7** |

Three findings that are worth keeping:

1. **The models' implied filler permittivity differs by a factor of 2–40.**  The honest
   output of a composite study is therefore a *band* (which `compare_models` already
   reports as `spread`), not a single number — now demonstrated on measured data.
2. **C1 is outside Maxwell-Garnett's reach.**  At vf = 0.5 the MG rule saturates at
   ε ≈ εm·(1+2vf)/(1−vf) ≈ 8.4 for this matrix, so a measured 12 cannot be produced by
   spherical, non-interacting, dilute inclusions.  That is the textbook signature of
   agglomeration/clustering — consistent with the project's own percolation and
   high-contrast warnings.
3. **C1 also needs εf ≥ 21.9 just to sit inside the Wiener bounds**, i.e. the measurement
   is only admissible for a filler that is at least ~10× the matrix permittivity.

## 3. What is needed to promote these to verified rows

* **filler εr** for each composite (usually stated in the paper text or its table 1);
* **matrix εr used by the authors** (not assumed);
* **DOI** for each row;
* ideally the measurement frequency and method (resonant cavity / waveguide / free space).

## 4. Workarounds (pick one)

1. **User supplies the sources**: a DOI, URL or PDF for C1–C4 (2–4 papers is enough) →
   the numbers get read from the full text and the official CSV is written.
2. **Accept snippet-level rows** and label them as such in the CSV (a `confidence`
   column) — weaker, but usable if clearly marked.
3. **Skip Y-T3 for now**: nothing else in the project depends on it; the mixing rules stay
   "internally tested, externally unvalidated" (a statement the project already makes).

---

*Compiled by **Yotta** — 2026-09-21. All measured values above are quoted from search
snippets with the source named; none are from memory.*

---

## 5. Cara mengambil sumbernya (daftar link & kata kunci)

Yang saya butuhkan dari tiap berkas: **εr filler**, **εr matriks yang dipakai penulis**, **vf**, **εr & tan δ terukur**, dan **frekuensinya**. Bentuk berkas apa saja cukup: PDF, tangkapan layar tabelnya, atau angkanya diketik + sitasi.

| # | Berkas yang dicari | Sumber yang terlihat | Kata kunci pencarian |
|---|---|---|---|
| C1 | Hu et al., *Microwave dielectric properties of PTFE/CaTiO₃* | sciencedirect.com | `PTFE CaTiO3 microwave dielectric properties Hu 2011 50 vol% permittivity 12 loss tangent` |
| C2 | *Effects of CaTiO₃ loading on the properties of PTFE/TiO₂ composites* | researchgate.net | `Effects of CaTiO3 loading PTFE/TiO2 composite 46 vol% dielectric constant 7.42` |
| C3 | Subodh, Deepu, Mohanan, Sebastian (2009), *Dielectric response of high permittivity polymer ceramic composite with low loss tangent*, Appl. Phys. Lett. **95**(6), 062903 | pubs.aip.org · ui.adsabs.harvard.edu · **ir.niist.res.in** (repositori institusi — biasanya gratis) | `Subodh 2009 Dielectric response high permittivity polymer ceramic composite 062903` |
| C4 | Zhang et al. (2015), komposit **BNT–HDPE** | scientific.net | `BNT HDPE ceramic polymer composite 40 vol% permittivity 10 loss tangent 0.0007 7 GHz` |
| C5 | Efek ukuran filler **MgTiO₃** pada komposit | researchgate.net | `MgTiO3 ceramic filler dimensional effect composite 50 vol% dielectric constant 3.2` |
| C6 | *Obtaining greatly improved dielectric constant in BaTiO₃–epoxy* (2022) | pubs.acs.org | `Obtaining greatly improved dielectric constant BaTiO3 epoxy composite 466.8 volume fraction` |
| C7 | **Bonus paling berharga:** NIST, *Broadband Dielectric Metrology for Polymer Composite Films* — di snippet disebut data terukur **mengikuti aturan pencampuran logaritmik**, jadi paper ini kemungkinan memuat data terukur + parameter fit sekaligus | tsapps.nist.gov (biasanya gratis) | `NIST Broadband Dielectric Metrology for Polymer Composite Films logarithmic mixing rule` |

**Prioritas kalau hanya bisa mengambil 2–3 berkas:** **C3** (repositori institusi — kemungkinan besar bebas unduh), **C1**, dan **C7** (NIST). Tiga itu sudah cukup untuk menulis `data/composite_measurements.csv` yang sah dan menjalankan `yotta_tools/mixing_validation.py`.

Format nama berkas bebas; cukup sebut nomor kandidatnya (mis. `C1_hu2011.pdf`). Kalau ada URL penuh, kirim saja — saya buka sendiri.
