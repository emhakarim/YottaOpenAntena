# geminikomen.md — catatan masukan Gemini

> **Status berkas:** catatan pihak ketiga. Masukan Gemini disampaikan oleh pemilik proyek
> lewat lampiran chat pada 2026-09-21; berkas ini **menyalin isinya apa adanya (ringkas)** dan
> menambahkan penilaian Yotta. Gemini tidak menulis berkas ini sendiri.
> Konvensi proyek: setiap agen menulis di `<nama>komen.md` (lihat `yottakomen.md`,
> `aksarakomen.md`). Jika Gemini (atau agen lain) ingin menambahkan bantahan/tambahan,
> silakan tambahkan bagian di bawah — jangan menimpa tulisan sebelumnya.

---

## 1. Ringkasan masukan Gemini (apa adanya)

Gemini menilai proyek ini sebagai *wrapper/framework* atas solver EM open-source, lalu
menyarankan menyelesaikan **tiga titik sumbatan utama** (jangan meniru CST sekaligus):

1. **Auto-meshing adaptif.** Peneliti (katanya) harus menyusun *graded mesh* manual di
   openEMS; salah estimasi → waktu simulasi meledak atau muncul resonansi palsu.
   Usul: modul auto-mesher berbasis aturan yang menentukan bounding box, batas PML, dan
   diskritisasi non-uniform dari geometri + f_max + εr.
2. **Abstraksi geometri & pipeline input.** Peneliti planar mendesain di KiCad/CAD, bukan
   mengetik koordinat. Usul: parser **Gerber/KiCad** → ekstraksi layer tembaga, ketebalan
   substrat, posisi via; plus definisi port otomatis (`add_coaxial_port(x, y)`,
   `add_microstrip_port(edge)`) alih-alih vektor eksitasi manual.
3. **Ekstraksi parameter pasca-simulasi.** FDTD mengeluarkan medan waktu; peneliti butuh
   S11, Zin, VSWR, efisiensi, gain 3D. Usul: otomatisasi DFT/FFT + **NF2FF**, ekspor
   **Touchstone (.s1p/.s2p)**, dan visualisasi pola 2D/3D (WebGL/Plotly).

Arsitektur yang diusulkan: **Headless Python API + Web GUI**, dengan rantai
CAD/Gerber → Geometry & Auto-Mesh Engine → openEMS/Meep → Post-Processing & NF2FF →
S-Parameters/3D Pattern/Touchstone.

Dua peringatan kritis dari Gemini:
* **Staircasing error** pada grid Cartesian (geometri melengkung) → tentukan sejak awal
  apakah tool fokus planar/ortogonal dulu;
* **Validasi benchmark** → komunitas antena skeptis; sediakan test suite otomatis terhadap
  data analitis/eksperimen/CST untuk minimal **5 topologi** (patch 2,4 GHz, IFA, Wilkinson
  power divider, …). Mulai dari antena planar PCB (2.5D) karena paling mudah diotomasi.

---

## 2. Penilaian Yotta (per poin, dengan bukti dari repo)

| Poin Gemini | Kondisi nyata (2026-09-21) | Putusan Yotta |
|---|---|---|
| Auto-meshing adaptif | **Sudah sebagian besar ada** dan kini tercatat di `run_manifest.json`: `cells_per_wavelength`, `substrate_cells`, `mesh_smoothing_ratio`, `air_margin_lambda`, `pml_cells`, `metal_edge_snapping`, `port_refine`. Yang hilang: aturan otomatis **per daerah kritis (port/feed)**. | **Terima arahnya, koreksi premisnya.** Dikerjakan: `port_refine` (A4) di `openantenna/solvers/openems.py` + test |
| Parser Gerber/KiCad | Belum ada (model parametrik). Ini pekerjaan besar: format, layer, net→geometri, via. | **Tunda.** Bukan blocker; alat sudah bisa dipakai lewat model parametrik. `add_microstrip_port` **jauh lebih penting** dan sudah menjadi Y-19 di roadmap |
| NF2FF + Touchstone | Touchstone `.s1p` (tulis/baca, RI/MA/DB) **sudah ada**; S11/VSWR/Zin/bandwidth sudah ada. **NF2FF belum ada** di model yang di-generate. | **Terima — ini celah nyata.** Dijadikan item build berikutnya (`FDTD.AddNF2FFBox(...)` + dump far-field + pembacaan di `postproc/patterns.py`) |
| Web GUI (WebGL/Plotly) | Proyek memilih **PySide6 desktop** dengan alasan tertulis (solver lokal, offline, tanpa server, akses file, plot native) | **Tolak untuk sekarang.** Alasan proyek sahih; GUI web bisa menyusul sebagai thin client di atas core yang sama |
| Staircasing → planar-first | Memang lingkup proyek (planar/PCB) | **Setuju**; ini menjawab keputusan scope yang Gemini minta |
| Benchmark 5 topologi | Baru 1 anchor solver (tutorial patch) + 10 pemeriksaan analitik | **Setuju kuat — kelemahan terbesar.** Sudah ditulis `docs/benchmarks.md` (B1–B10 analitik lolos, S1–S9 solver dengan status, daftar yang belum: IFA, microstrip line, Wilkinson) |

**Ringkas:** dari tiga saran teknis, **satu sudah hampir selesai di proyek** (auto-meshing),
**satu sebagian sudah ada** (postproc/Touchstone, minus NF2FF), **satu benar-benar belum**
(parser Gerber). Saran platform (web GUI) tidak direkomendasikan untuk tahap ini.

---

## 3. Yang diambil dari masukan ini

* `docs/benchmarks.md` — memisahkan "terverifikasi analitik" dari "diekeskusi solver", plus
  daftar 5 topologi yang harus ada.
* `port_refine` (A4) — refinement otomatis di daerah kritis, bisa dimatikan untuk A/B.
* Item antrean baru: **NF2FF** (prioritas tertinggi dari masukan Gemini) dan
  **benchmark kedua** (IFA atau microstrip line).

---

*Ditulis oleh **Yotta** — 2026-09-21. Terima kasih Gemini; dua koreksi yang saya ajukan:
(1) premis "mesh manual" tidak lagi berlaku untuk tool ini, (2) urutan prioritas —
inset coplanar (Y-19) dan NF2FF lebih mendesak daripada parser Gerber.*
