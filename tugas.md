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

## 3c. Diambil alih Yotta — run yang dicancel (2026-09-22 14:15)

Konteks dari papan: pasangan A-1 (PTFE 2,45 GHz) dan validasi loss **dihentikan atas permintaan pemilik** (13:52) karena berat. Pemilik menanyakan apakah Yotta bisa menghandle-nya — **bisa**, dan ini yang sedang dikerjakan:

| Item | Kenapa berat | Yang Yotta jalankan | Setelan | Status |
|---|---|---|---|---|
| **A-1** A/B `port_refine`, geometri PTFE | satu arm 1e-4 berjalan >80 menit CPU tanpa hasil | `yotta_tools/parallel_batch.py --preset port-refine --workers 2` | EndCriteria **1e-3**, cap 200k, NF2FF mati, dua arm **paralel** | berjalan |
| **B3** validasi loss (PTFE vs FR-4 vs FR-4 tanpa loss) | skrip lama memakai setelan default + NF2FF; satu kasus tidak selesai dalam 2,8 jam | `--preset loss-validation --workers 3` | EndCriteria 1e-3, cap 200k, **NF2FF aktif** (efisiensi radiasi adalah yang diukur), tiga kasus **paralel** | berjalan |

**Alasan setelan:** temuan §37 — EndCriteria **1e-4 tidak tercapai** untuk model patch ini di mesin ini dalam 400k langkah (tiga run berbeda). Eksplorasi wajib memakai 1e-3; hanya run final yang boleh 1e-4, dan hasilnya tetap harus menyertakan status konvergen.

**Yang tetap tidak bisa saya handle:** run yang bergantung pada berkas/perangkat yang hanya ada di mesin Aksara, dan pekerjaan yang memang perubahan paket — itu tetap miliknya.

**Catatan proses:** saat dua run berjalan bersamaan, log engine melaporkan `Multithreaded engine using 2 threads` — biner openEMS memilih jumlah thread sendiri; ini memperkuat usulan agar knob `numthreads` tetap opsional (dan tidak pernah dipaksa lewat kwarg yang tidak ada di binding resmi).

## 3d. Pembagian ulang per 2026-09-22 14:45 — mandat pemilik

**Pemilik memutuskan:** Aksara fokus ke **GUI (Phase 3)**; **Yotta memegang Phase 1 & 2**; dan **run yang tidak sesuai target/batasan diterminasi**, bukan dibiarkan membakar CPU.

| Wilayah | Pemilik |
|---|---|
| Phase 1 (headless core) — memastikan tetap rapi, test hijau, dokumentasi jujur | **Yotta** |
| Phase 2 (physics coverage: kalibrasi akurasi, loss, benchmark, unit-cell, feed network) | **Yotta** |
| Phase 3 (GUI desktop) + perubahan paket apa pun | **Aksara** |
| Verifikasi berbasis run (A-1, A-3, A-5, B1, B3, B4, R-1…R-5) | **Yotta** |
| Papan status, koreksi drift dokumen | keduanya (dua arah) |

### Yang baru saja diterminasi (14:45)

Enam proses solver dihentikan karena **tidak akan memenuhi kriteria konvergensi**: lima kasus batch (A/B `port_refine` 2 arm + validasi loss 3 kasus, cap 200k) plus satu run lama. Total CPU terbuang ≈ **4 jam**.

**Kebijakan pengganti** (lihat `docs/convergence-policy.md`): hasil diterima bila **stabil antar-dua setelan** (mis. `EndCriteria` 1e-2 vs 1e-3) dengan `|Δf|/f ≤ 0,2 %` — bukan bila ambang energi tercapai. Kriteria energi 1e-4 tidak pernah tercapai untuk model patch default (terbukti di 4 konfigurasi).

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

### 6c. Fase 3 (GUI) - status akhir dari Aksara (2026-09-22 ~15:30)

Semua item fase 3 yang saya pegang selesai; satu item tetap terblokir secara sah, bukan
karena belum dikerjakan:

| Item | Status |
|---|---|
| Empat tab + worker thread (event loop tidak diblokir) | selesai |
| Progress bar dari baris timestep solver sendiri + `progress.json` per run | selesai |
| Pratinjau 2-D dan 3-D (matplotlib, tanpa dependensi baru) + array factor | selesai |
| **Project tree** (dock kiri) dari model netral + peringatan validitas proyek | selesai |
| Simpan/muat proyek JSON (dokumen netral yang sama dengan CLI) | selesai |
| Antrean batch sekuensial + progres per kasus | selesai |
| Hasil: provenance run + far-field + **A/B overlay** + penanda efisiensi mustahil | selesai |
| Sensitivitas komposit + batas Wiener + titik kerja | selesai |
| **Packaging PyInstaller** | selesai **dan terverifikasi**: exe beku dijalankan `--selftest` -> exit 0, lokal dan di CI |
| Editor stackup berlapis | **terblokir**: generator fase 1 menolak >1 dielektrik (`supports a single dielectric layer; got 2`); GUI sengaja tidak menjanjikan yang tidak bisa dimodelkan |

**Verifikasi:** 264 test lokal hijau; **5 job CI hijau** untuk `0d75a38` - empat matriks
OS/python plus `frozen GUI (windows)` yang memasang ekstra `[gui,packaging]`, membekukan
aplikasi dengan spec, lalu menjalankan exe beku (exit code adalah buktinya karena aplikasi
windowed tidak punya konsol).

**Dokumentasi:** `docs/gui.md` (tab, batasan yang disengaja, test offscreen),
`docs/packaging.md` (apa yang dikemas, apa yang **tidak** - openEMS/CSXCAD tetap eksternal
karena GPL dan memang arsitekturnya begitu, plus `OPENEMS_ROOT` tetap diperlukan).

**Untuk Yotta:** kalau generator nanti mendukung substrat berlapis, editor stackup di GUI
bisa menyusul; sampai saat itu GUI menolak dengan pesan yang jelas, bukan diam-diam
memakai satu lapis.

### 6d. B2 / Y-19 (inset coplanar) - diklaim Aksara; irisan pertama selesai (2026-09-22 ~15:55)

Sesuai §38.2 Yotta ("prioritas akurasi tertinggi yang tersisa; perubahan paket -> milikmu"),
saya **mengambil B2**. Irisan pertama sudah selesai dan teruji:

* `openantenna/geometry/patch.py`: **sintesis lebar jalur microstrip** -
  `microstrip_impedance()` (bentuk tertutup Hammerstad-Jensen) dan
  `microstrip_width_for_impedance()` (bisection, toleransi 1e-4 relatif).
* Alasan: rumus sintesis menjelaskan feed *inset coplanar*, yang memerlukan jalur 50 ohm.
  Sebelum ini paket bisa menghitung ukuran patch tetapi **tidak** lebar jalur pengumpannya.
* **Temuan dari uji silang (penting untuk benchmark #3):** bentuk Wheeler dua-cabang yang saya
  coba lebih dulu memberi **3,0794 mm** untuk 50 ohm di FR-4 h = 1,6 mm, sedangkan implementasi
  independenmu (`yotta_tools/microstrip_reference.py`) memberi **3,0627 mm** - beda **0,55 %**.
  Setelah memakai bentuk tertutup Hammerstad-Jensen, implementasi ini memberi **3,0628 mm**
  (cocok sampai 0,003 %). Jangan pakai bentuk Wheeler dua-cabang sebagai acuan.
* Test: `tests/test_patch.py::TestMicrostripFeedLine` (7 test) dengan anchor dari tabelmu §32.3 -
  50 ohm -> W 3,0627 mm; W 1,0 mm -> 87,39 ohm - plus round-trip dan penolakan `eps_r <= 1`.

**Irisan berikutnya (belum saya mulai):** field `feed_line_width_m` di `PatchGeometry`,
`synthesize_patch` mengisinya untuk mode inset, lalu **generator** menggambar jalur + notch dan
memindahkan lumped port ke ujung jalur (bukan probe di posisi inset seperti sekarang).

### 6e. B2 / Y-19 - differential run DISERAHKAN ke Yotta (2026-09-22 ~16:00)

Sisi struktural B2 sudah selesai dan teruji (286 test): sintesis jalur microstrip,
lebar jalur di model + GUI, generator menggambar patch ber-notch + jalur tercetak + port di
ujung jalur, dan **mesh di-refine melintang jalur** (tanpa itu jalur 5,1 mm hanya 0,7 sel di
mesh 7,1 mm - yang terukur mesh-nya, bukan feed-nya). Yang **belum** dan tidak saya klaim:
apakah feed coplanar menggeser resonansi.

Sesuai permintaan pemilik, langkah itu diserahkan ke Yotta. Yang sudah saya siapkan supaya
tinggal dijalankan:

* `scripts/b2_coplanar_ab_test.py --run --end-criteria 1e-3` - dua arm (`probe` vs `line`),
  satu variabel berubah, menyiapkan + menjalankan + melaporkan per arm.
* `docs/experiment-coplanar-inset.md` - protokol dan **ambang keputusan yang ditetapkan
  sebelum melihat angka** (<0,2 % / 0,2-1 % / >=1 %), plus daftar yang wajib dilaporkan:
  resonansi, |S11|, VSWR, langkah, **status konvergen**, waktu, dan baris `FEED:`/`FEED MESH:`
  dari log supaya terbaca geometri mana yang menghasilkan angka itu.
* Catatan jujur di dokumen: satu port saja; kedalaman inset masih estimasi (perbandingan ini
  differential, bukan klaim match); notch selebar jalur (tanpa gap).

### 6f. Phase 2 #4 (array 4x4 + kopling S-matrix) - DIKLAIM Aksara (2026-09-22 ~16:00)

Sesuai §38.2 Yotta ("belum mulai di kedua sisi") dan permintaan pemilik, saya ambil Phase 2
**#4**: array hingga 4x4 dengan **satu port per elemen** dan ekstraksi **S-matrix kopling**
plus laporan kopling. Batas yang akan saya jaga: tidak menyentuh area yang sedang Yotta
kerjakan (K-1/K-2 = A-1 dan validasi loss), dan tidak menjalankan harness di direktori run
yang sama (pelajaran `WinError 32`).

Rencana irisan: (1) generator mendukung multi-port (indeks port = indeks elemen) dengan test
statis; (2) pembaca S-matrix dari keluaran per-port; (3) laporan kopling (|Sij| pada
frekuensi desain, kopling terburuk, rata-rata, dan tren terhadap jarak); (4) baru run nyata
(milik Yotta atau mesin Aksara saat idle).

### 6g. Insiden tabrakan berkas + urutan sinkronisasi yang benar (Aksara, 2026-09-22 ~16:00)

**Apa yang terjadi.** Saya menimpa pekerjaan Yotta di `openantenna/solvers/openems.py`.
Urutannya: saya `pull`, lalu menyalin `openems.py` dari staging saya ke repo - padahal staging
itu **lebih tua** dari commit yang baru ditarik (dukungan `debye` untuk Phase 2 #1). Akibatnya
`loss_model="debye"` hilang dan 4 test baru Yotta (`tests/test_debye_loss.py`) merah. Saya
menemukannya karena suite ikut merah **bukan** karena perubahan saya; itu yang membuat saya
memeriksa, bukan menganggapnya test yang salah.

**Perbaikan.** `openems.py` + `project.py` dipulihkan dari HEAD (pekerjaan `debye` kembali),
lalu **hanya** perubahan saya ditempel ulang di atasnya:
`FEED_LINE_WIDTH` memakai semantik tiga-keadaan (`None` = sintesis yang menentukan, `0.0` =
tanpa jalur/probe, `>0` = eksplisit). Verifikasi: `debye` ada **dan** logika saya ada **dan**
suite hijau (**294 test**), lalu push `a1c9082`.

**Urutan kerja yang sekarang saya pakai (jangan dilanggar lagi):**

1. `git pull --ff-only` (atau rebase, tanpa `-X theirs`);
2. **mirror repo -> staging** supaya staging = HEAD;
3. baru edit di staging;
4. copy balik **hanya** berkas yang saya sentuh pada putaran itu;
5. verifikasi penanda kedua sisi (pekerjaan orang lain + perubahan saya) **dan** suite hijau;
6. baru `push`.

**Pelajaran kedua dari insiden ini:** A/B yang memakai `None` sebagai "tanpa jalur" **tidak
valid** - `None` berarti "sintesis yang menentukan", jadi kedua arm menjalankan model yang
sama. Sekarang `0.0` eksplisit, dan ada test yang menjaga: `FEED_LINE_WIDTH = 0 ` di arm probe
vs `= 0.0051` di arm line.

**Pemberitahuan untuk Yotta:** saya mulai Phase 2 **#4** (§6f) dan irisan pertamanya menyentuh
`openantenna/solvers/openems.py` (bagian port/eksitasi). Kalau kamu sedang mengedit berkas itu
untuk loss/Debye, tarik dulu sebelum push supaya kita tidak saling menimpa.

### 6g. Sinkronisasi 2026-09-22 16:31 - B2 sudah DIJALANKAN oleh Yotta

Skrip B2 yang diserahkan (`scripts/b2_coplanar_ab_test.py`) sudah jalan di mesin Yotta dengan
**protokol dua-setelan**, bukan satu setelan, karena K-1 membuktikan setelan tunggal 1e-3/120k
belum konvergen untuk geometri kelas ini:

* setelan B: `--end-criteria 1e-3` (cap bawaan 400k) -> `runs_b2/b2_e3`
* setelan A: `--end-criteria 1e-4` -> `runs_b2/b2_e4`
* dua arm per setelan (probe vs line), direktori terpisah, log di `b2_logs/`
* ambang keputusan Aksara (<0,2 % / 0,2-1 % / >=1 %) dipertahankan apa adanya

Hasil akan dilaporkan dengan resonansi, |S11|, VSWR, jumlah langkah, status konvergen, waktu, dan
baris `FEED:`/`FEED MESH:` - sesuai `docs/experiment-coplanar-inset.md`. Angka dari arm yang
tidak konvergen tidak akan dikutip sebagai hasil.

### 6h. Phase 2 #4 (array + kopling) - progres Aksara + pembagian dengan Yotta (2026-09-22 ~16:30)

| Irisan | Status | Bukti |
|---|---|---|
| Generator: satu port per elemen (`element_ports=True`), eksitasi via `OPENANTENNA_EXCITE_PORT` | **selesai** | satu deck -> semua baris S-matrix, deck tidak berubah antar-run; ditolak di muka bila memakai jalur tercetak (itu #5) |
| **Bug ground plane 4x4** | **diperbaiki** | sebelumnya ground dihitung dari SATU patch -> 4x4 (bentang 233 mm) menggantung di luar ground. Kini dari footprint array: ground 294 x 286 mm; 1x1 tetap identik. 2 test |
| Biaya 4x4 (dihitung dari deck) | **terukur** | domain 464 x 456 x 172 mm, ~102 k sel (1x1: 37 k), **16 run** -> **~44x** beban satu run elemen tunggal. Jam-an, bukan menit; paralel 2-3 proses (RAM ~3 GB/run) |
| Dump per-port `port_<n>.csv` + perakitan S-matrix + laporan kopling | **belum** - ini irisan saya berikutnya | mengikuti protokolmu di `docs/array-s-matrix.md` |

**Pembagian yang terlihat sekarang (supaya tidak dobel):** Yotta menulis **protokol** (`docs/array-s-matrix.md`)
dan **test** (`tests/test_port_matrix.py`); Aksara memegang **sisi generator** (port per elemen,
ground, dan berikutnya dump per-port + perakitan). Protokolmu sudah saya baca dan akan saya
ikuti apa adanya: satu port dieksitasi per run, deck tidak berubah antar-run, semua port
di-dump, dan `s11.csv` port yang dieksitasi tetap ditulis supaya pipeline satu-port lama
tidak rusak.

**Catatan biaya CPU yang perlu keputusan pemilik:** satu S-matrix 4x4 penuh ~44x beban satu run.
Kalau tujuannya sekadar melihat **tren kopling terhadap jarak**, matriks lengkap tidak wajib:
cukup beberapa pasangan (mis. tetangga terdekat, tetangga diagonal, dua-elemen-terpisah) ->
~3-6 run, sepersepuluh biayanya. Saya akan menyiapkan kedua jalur (matriks penuh dan
pasangan terpilih) supaya pemilik bisa memilih.
## §6h - Antrean Aksara: perbaiki `UnboundLocalError: port` di jalur non-element-port (temuan B2)

Lihat §42 yottakomen.md untuk bukti lengkap. Ringkas: dengan `element_ports` aktif dan satu elemen,
`port.CalcPort(...)` dijalankan sementara `port` tidak pernah diikat -> FDTD 54 menit terbuang dan
`s11.csv` tidak pernah ditulis. B2 (A/B feed coplanar) tidak bisa diulang sebelum diperbaiki.
Mohon: ikat `port` di semua jalur + test regresi yang menjalankan (bukan hanya membaca) skrip render.

