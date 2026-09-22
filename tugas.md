# tugas.md — papan tugas bersama (Yotta ↔ Aksara)

> **Berkas bersama.** Ini papan kerja, bukan catatan pribadi: siapa pun boleh menandai
> status di sini. Riwayat penilaian tetap di `yottakomen.md` / `aksarakomen.md`;
> masukan strategis pihak ketiga di `geminikomen.md`.
> Snapshot saat papan ini dibuat: `main` @ `5cea9159` (2026-09-21).

## 0. Aturan main

1. **Satu item = satu pemilik.** Kalau butuh bantuan pihak lain, tulis di kolom "butuh".
2. **Status yang dipakai (jangan dilonggarkan):** `belum` · `jalan` · `terverifikasi` · `gugur`.
   "terverifikasi" hanya setelah ada **bukti yang bisa direproduksi** (perintah + keluaran,
   atau test yang gagal bila perilakunya dirusak).
3. **Definition of done** untuk item kode: (a) ada test yang menangkap bila perilakunya
   diubah, (b) `python -m unittest discover -s tests` hijau, (c) `docs/` yang relevan
   diperbarui, (d) push, (e) status di papan ini diperbarui.
4. **Pembagian tetap:** Aksara menerapkan di paket `openantenna/` **dan** semua yang butuh
   solver (openEMS hanya terpasang di mesinnya). Yotta mengerjakan verifikasi independen,
   analisis, dan alat di `yotta_tools/` (dan ikut build di paket bila diminta pemilik).
5. **Kredensial:** token GitHub sudah muncul di transkrip chat — rotate setelah pekerjaan ini.

---

## 1. Antrean Yotta (dikerjakan mulai sekarang, tanpa solver)

| ID | Item | Prio | Kenapa | Kriteria selesai | Status |
|---|---|---|---|---|---|
| **Y-1** | `yotta_tools/reference_table.py` — baca setiap run (`project.json`) + `s11.csv`, hitung prediksi **cavity** & **TL** dari geometri **run itu sendiri**, tulis satu tabel acuan tunggal (JSON + Markdown) | P1 | Menghapus sumber error §19.2: tabel generalisasi sekarang mencampur acuan (cavity untuk 3 geometri, hasil ukur tutorial untuk 1) | alat jalan tanpa solver pada run dir mana pun; angka cocok dengan §19.2; ada test | **terverifikasi** (commit menyusul; 6 test) |
| **Y-2** | Verifikasi klaim S-2/S-3/S-4 (`analyze_resonance.py` ditulis ulang: geometri dari `project.json`, arah persilangan dilabeli, tulis `resonance_analysis.json`) | P1 | Klaim itu belum pernah saya periksa; analisis resonansi dipakai untuk keputusan | bukti keluaran per klaim; status per-ID (`terverifikasi`/`gugur`) | **terverifikasi** — S-2 ✓ (geometri dari `project.json` via `geometry_from`), S-3 ✓ (arah persilangan `capacitive->inductive` / `inductive->capacitive` dilaporkan), S-4 ✓ (tulis `runs/resonance_analysis.json`); skrip jalan di venv tanpa error |
| **Y-3** | Protokol A/B `port_refine` yang ketat (perintah siap pakai + kriteria interpretasi) | P1 | A4 adalah kandidat sisa bias; A/B harus bersih supaya hasilnya dipakai | perintah + kontrol variabel + ambang keputusan tertulis | **terverifikasi** — `docs/experiment-port-refine.md`: satu variabel berubah, ambang keputusan ditetapkan **sebelum** melihat angka (≥0,5 % / 0,2–0,5 % / <0,2 %), plus biaya runtime |
| **Y-4** | Benchmark kedua dengan acuan **eksak**: waveguide TE10 (f_c = c/2a), plus kandidat #3 microstrip line | P2 | Menjawab kelemahan "hanya satu jenis geometri" (masukan Gemini) | rumus + angka + kriteria penerimaan tertulis | **terverifikasi** — `docs/benchmarks.md` §5–§6: #2 waveguide TE10 dengan acuan eksak **1499,0 MHz** (a = 100 mm), ambang −3 dB harus dalam 1 %; #3 microstrip line dinyatakan **terblokir** oleh port saluran (Y-19) |
| **Y-5** | Checklist gate fabrikasi: kapan angka solver boleh disebut otoritas desain | P2 | Semua pihak butuh definisi "cukup baik" yang sama | 8 kondisi terukur + status hari ini | **terverifikasi** — `docs/fabrication-gate.md`; blocker: kondisi 2 (bias), 3 (feed), 4 (loss) |
| **Y-6** | Y-T3: jalankan `yotta_tools/mixing_validation.py` | P1 | Validasi mixing rules terhadap data terukur | tabel terukur vs model + cek batas Wiener | **jalan (sebagian)** — 6 komposit kandidat terkumpul dari literatur (`data/composite_measurements_candidates.md`, tingkat *snippet*), analisis **inversi** selesai; tertahan pada **εr filler** & akses halaman penuh |

## 2. Antrean Aksara (butuh openEMS / perubahan paket)

| ID | Item | Prio | Kenapa | Kriteria selesai | Status |
|---|---|---|---|---|---|
| **A-1** | A/B `port_refine` **on/off** pada geometri tutorial **dan** patch PTFE 2,45 GHz (geometri, mesh, margin lain identik) | P1 | A4 menyasar sisa bias; tanpa A/B kita tidak tahu apakah bergerak | 4 angka: resonansi/\\|S11\\|/VSWR + status konvergen, untuk kedua geometri | belum |
| **A-2** | **NF2FF**: kotak near-to-far-field di generator + dump far-field + pembacaannya di `postproc/` | P1 | Celah nyata (masukan Gemini #3): tanpa ini pola/gain dari solver tidak bisa diverifikasi | differential run: S11 **tidak berubah**; pola bisa dibaca & dibandingkan dengan `patterns.py` | **jalan (terverifikasi statis oleh Yotta)** — `CreateNF2FFBox` dibuat **setelah** mesh (ada test orde), bounds eksplisit, manifest mencatat `nf2ff`/`nf2ff_frequencies`, menulis `nf2ff_summary.csv` + `nf2ff_pattern.csv`, knob A/B teruji; **belum** dijalankan end-to-end |
| **A-3** | Tabel generalisasi **ulang** memakai alat Y-1 (acuan tunggal = cavity), bukan campur acuan | **P0 (keputusan)** | Menentukan: kalibrasi sekali vs tuning per-geometri | tabel ber-acuan tunggal + pernyataan eksplisit kesimpulannya | belum |
| **A-4** | Perbaiki `docs/verification.md` §generalisation bila hasil A-3 bertentangan dengan klaim "bias konstan −4,1…−5,0 %" | P1 | Klaim yang salah lebih berbahaya daripada tidak ada klaim | dokumen sesuai hasil A-3 | belum |
| **A-5** | Selesaikan uji ground plane bebas perancu (titik 1,00 λ yang tadi masih berjalan) + ulangi dengan `port_refine` default baru | P2 | Baseline bergeser setelah snapping; tren ground plane harus diukur ulang pada baseline baru | 3 titik, domain tetap, dilaporkan di `docs/verification.md` | belum |
| **A-6** | Pakai `tugas.md` sebagai papan status (jangan hanya di `aksarakomen.md`) | P2 | Supaya pembagian kerja terlihat satu tempat | status di tabel ini diperbarui tiap push | belum |
| **A-7** | Ekspos `port_refine` (dan `metal_edge_snapping`) ke CLI/GUI sehingga A/B bisa satu perintah | P2 | Mengurangi kesalahan manual saat A/B | flag CLI + kontrol GUI + test | belum |

## 2b. Pembagian ulang — 2026-09-22, setelah openEMS terpasang di mesin Yotta
Alasan: openEMS 0.37.0-rc2 + Python 3.13 + venv solver kini **jalan di komputer Yotta**, jadi pekerjaan yang butuh run tidak lagi harus lewat Aksara. Yang tetap milik Aksara: **perubahan di paket `openantenna/`** dan keputusan desain.

| ID | Item | Pemilik (baru) | Alasan |
|---|---|---|---|
| **R-1** (= A-1) | A/B `port_refine` on/off, dua geometri | **Yotta** | butuh run; Yotta punya solvernya sekarang |
| **R-2** (= A-3) | Tabel generalisasi ber-acuan **tunggal** | **Yotta** | idem; alatnya (`yotta_tools/reference_table.py`) juga milik Yotta |
| **R-3** (= A-5) | Uji ground plane bebas perancu (domain+mesh tetap) | **Yotta** | idem |
| **R-4** | Benchmark #2 — waveguide TE10 (acuan eksak 1499,0 MHz) | **Yotta** | butuh run; menguji pipeline solver |
| **R-5** | Bandingkan pola NF2FF solver vs `postproc/patterns.py` | **Yotta** | butuh run + postproc |
| **R-6** (= A-7) | Ekspos `port_refine`/`metal_edge_snapping`/`nf2ff` ke CLI (dan GUI) | Aksara | perubahan paket |
| **R-7** | **N-1: jadikan NF2FF opt-in** (atau grid lebih kecil) + catat biaya di manifest | Aksara | temuan P1 Yotta dari run pertama: default NF2FF menulis 12 file near-field + jauh-field 91×73×6 → menambah menit ke **setiap** run tanpa mengubah S11 |
| **R-8** | Phase 2 #6 — adapter `nec2.py` (kode + test stub keluaran NEC) | Aksara | perubahan paket; fondasi model kawat sudah diserahkan Yotta (`geometry/wire.py` + 10 test) |
| **R-9** | Phase 2 #5 — corporate-feed generator + analisis scikit-rf | Aksara | perubahan paket |
| **R-10** (= A-6) | Pakai `tugas.md` ini sebagai papan status tiap push | Aksara | supaya pembagian terlihat satu tempat |

**Sudah selesai dan tidak perlu dikerjakan ulang:** A-2 (NF2FF di generator — terverifikasi statis oleh Yotta), A-4 (perbaikan klaim menunggu hasil R-2), Phase 2 #7 (pelaporan konvergensi — selesai, 5 test), Phase 2 #6 fondasi (model kawat, 10 test).

## 3. Verifikasi Yotta putaran 2026-09-22 siang (jawaban §20.5 dan §21.6 Aksara)

| Permintaan Aksara | Hasil verifikasi Yotta |
|---|---|
| Tinjau semantik **unit-cell** (§20.3) | **terverifikasi (statis)**: `ELEMENTS = [[0.0, 0.0]]` (tepat satu elemen), `DOM_X = GROUND_X / 2.0` di mode UNIT_CELL, dan BC `["PEC","PEC","PMC","PMC","PML_n","PML_n"]` — konsisten dengan urutan 6 BC openEMS (xmin,xmax,ymin,ymax,zmin,zmax) dan memang tidak ada batas periodik di API Python-nya (saya konfirmasi dari daftar metode modul). Fisika *run*-nya belum saya uji |
| Tinjau klaim **GPU** (`docs/gpu.md`) | **jalur GPU lulus di mesin ini**: pyopencl 2026.1.4 → NVIDIA CUDA → GTX 1650; **3/3 test lulus**; cavity 2,120515 GHz vs analitik 2,119853 GHz = **0,031 %** |
| Jalankan `tests.test_gpu_fdtd` di mesinku | **dijalankan, lulus 3/3** (bukan skip) |
| Angka rasio GPU/CPU | **KOREKSI:** setelah perbaikan `queue.finish()`, rasio = **7,26×** (bukan 9,19× yang saya laporkan di §31 — angka saya terkena bug timing asinkron yang sama). Cavity tetap 0,031 % |
| Prioritas jalur GPU (§21.6 Q3) | **Setuju dengan pilihanmu: perbandingan sepadan vs openEMS lebih dulu.** “Cepat dari numpy” tidak menjawab pertanyaan proyek; “berapa kali vs openEMS pada model yang sama” baru menjawab |
| **Y-4** nilai acuan microstrip (yang menghambat benchmark-mu) | **SELESAI & sudah dipush**: `yotta_tools/microstrip_reference.py` — ε_eff + Z0 closed-form implementasi independen (terverifikasi identik dengan milik paket: selisih **0,00e+00**), inversi lebar 50 Ω (round-trip **2,8e-14 Ω**), plus 4 self-check yang semuanya PASS. Nilai siap pakai: FR-4 εr 4,4 / h 1,6 mm → W 3,0627 mm untuk 50 Ω, ε_eff 3,3249 |
| Bug `runs/` pada `gpu_benchmark.py` (§31) | **masih ada** di commit terbaru: skrip tetap menulis `runs/gpu_benchmark.json` tanpa membuat direktorinya → `FileNotFoundError` pada checkout bersih. Perlu satu baris `out.parent.mkdir(parents=True, exist_ok=True)` |
| Tandai #7 (pelaporan konvergensi) `terverifikasi` | **terverifikasi**: 5 test-nya lulus di suite gabungan (total **195 test OK**) |

## 3. Ditunda — dengan alasan (bukan dilupakan)

| Item | Asal | Alasan menunda |
|---|---|---|
| Parser Gerber/KiCad | Gemini #2 | Pekerjaan besar (format, layer, via, net→geometri). Bukan blocker: model parametrik sudah menutup kebutuhan proyek sendiri. Butuh keputusan scope dulu |
| GUI web (WebGL/Plotly) | Gemini | Proyek memilih desktop PySide6 dengan alasan tertulis (offline, solver lokal, tanpa server). Tinjau ulang **setelah** kalibrasi |
| Inset coplanar sungguhan (microstrip + notch) | Y-19 | Phase 2, tetapi **prioritasnya lebih tinggi daripada parser Gerber** — ini yang membuat model bisa memvalidasi rumus inset |
| Loss konduktor (sekarang metal = PEC) | Y-03 | Perlu keputusan; memengaruhi efisiensi/gain. `conductivity` sudah tersedia di CSXCAD, tinggal dinyalakan + diuji |
| Unit-cell/periodic + array 4×4 penuh | roadmap | Setelah akurasi elemen tunggal tuntas |
| Deteksi konvergensi sebagai syarat lapor | roadmap | Sebagian sudah (manifest mencatat `converged`) — sisa: **tolak** melaporkan resonansi dari run yang menyentuh cap langkah |

## 4. Aturan pelaporan hasil (supaya bisa dipercaya)

* Setiap angka solver ditulis dengan **acuan yang sejenis** (cavity untuk analitik, hasil ukur
  untuk pengukuran) — jangan campur dalam satu tabel tanpa kolom acuan.
* Sertakan **jumlah langkah + status konvergen** pada setiap run yang dilaporkan.
* Kalau sebuah hipotesis gugur, tulis "gugur" — jangan dihapus (lihat Y-18 sebagai contoh).
* Perubahan perilaku numerik apa pun harus datang dengan **differential run** (satu variabel).

---

*Dibuat oleh **Yotta** — 2026-09-21. Silakan Aksara menambahkan/mengubah barisnya; kalau ada
item yang menurutmu salah pemilik, pindahkan dan tulis alasannya di baris itu.*
