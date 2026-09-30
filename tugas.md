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

---

## §6i - Aksara, 2026-09-28: dokumen GUI mengejar kode (tab Import & Optimise)

**Selesai & dipush** (`7bb6663`, merge `95c9bcc`; CI **6/6 job success**; suite **464 test OK**):

| Item | Bukti |
|---|---|
| `examples/05_dxf_outline.py` | contoh menulis DXF-nya sendiri (garis luar 40x30 mm + lubang 5 mm), membacanya kembali, dan menunjukkan grid `21 x 16 sel @ 2 mm`; dijalankan oleh `tests/test_examples.py`, jadi contoh yang membusuk menjadi kegagalan test |
| `docs/examples.md` | tabel 5 contoh (sebelumnya menulis "three" padahal sudah ada empat), plus `dxf-inspect` di daftar CLI dan catatan bahwa DXF hanya outline |
| `docs/gui.md` | halaman kini menyesuaikan **7 tab** yang sebenarnya (dulu "four tabs", Import/Optimise tidak pernah disebut); ditambah catatan sengaja: staircase vs permukaan, DXF = sisi bukan logam terisi, Optimise = targeting bukan pengukuran, dan job CI khusus GUI |
| `MainWindow` docstring | "Four tabs, one per stage of the workflow" -> "Seven tabs, ..." |

**Bukti perintah:** `python examples/05_dxf_outline.py` -> `segments 52`, `bounds x 0..40 mm, y 0..30 mm`, `grid 21 x 16 cells`, `stroked 25.3 %`.

**Belum - item #1 rencana:** dielektrik bertumpuk di generator (membuka blokir editor stackup).
Itu perubahan template dek yang besar (satu kotak `substrate`, `H_TOTAL`, garis mesh
`linspace(-H_TOTAL, 0, ...)`, dan jalur Debye), jadi dikerjakan sebagai perubahan tersendiri,
bukan diselipkan ke push dokumentasi ini.

---

## §6j - Aksara, 2026-09-28 (malam): tab Sketch (gambar sendiri, ala CST) + pembagian tugas

**Selesai & dipush** (`6542564`; suite **474 test OK**; `--selftest` exit 0):

Tab **Sketch** (ke-8) - menggambar jalur/bentuk seperti di CST: alat `trace`, `polygon`,
`rectangle`, `circle`, `line`; snapping milimeter (bisa dimatikan); daftar bentuk + undo/clear;
**ekspor DXF** (`geometry.cad.write_dxf`, stdlib, round-trip dengan `read_dxf`), muat DXF
kembali ke sketcher, dan **grid view** yang menunjukkan sel solver yang disentuh gambar.

**Bukti:** `tests/test_gui_smoke.py::test_the_sketch_tab_draws_and_exports_a_dxf` menempuh
handler klik yang sama dengan kanvas (rectangle + trace + circle -> ekspor -> `read_dxf`
kembali 54 segmen); `tests/test_cad_dxf.py::TestDxfWriting` mengunci round-trip dan penolakan
(kosong / entitas tak dikenal / radius <= 0). Ekspektasi jumlah tab diperbarui sadar (7 -> 8).

**Batas jujur:** sketch **belum tersambung ke dek solver** - dek masih dari model parametrik.
Jembatan sketch -> dek non-parametrik adalah perubahan tersendiri dan tidak diklaim di panel.

### Pembagian tugas saat ini (per mandat 3d + keadaan malam ini)

| Wilayah | Pemilik | Item konkret berikutnya |
|---|---|---|
| Paket `openantenna/` + GUI | **Aksara** | **(1) dielektrik bertumpuk di generator** (item #1 rencana; membuka blokir editor stackup); (2) jembatan sketch -> dek; (3) `element_ports` + pohon feed |
| Run solver + verifikasi + `yotta_tools/` | **Yotta** | (a) **temuan audit queue-runner #1 (verifikasi artefak) & #2 (kill process tree) sebelum batch malam berikutnya** - usulan, karena itu alatmu; (b) rantai Route B 300k vs 400k; (c) mesh check setelah angka pertama diterima |
| Keputusan | **Pemilik** | kalibrasi kriteria terminasi (item 1 `docs/compute-roadmap.md`) |

**Yang saya minta dari Yotta:**

1. Tinjau klaim tab Sketch di atas - khususnya kalimat "belum tersambung ke dek"; kalau ada
   dokumen atau panel yang menyiratkan sebaliknya, itu bug yang harus ditandai.
2. Jalankan `python -m unittest tests.test_gui_smoke` di mesinmu kalau PySide6 tersedia
   (kalau tidak ada, bilang saja - CI sudah punya job GUI terpisah).
3. Konfirmasi #1/#2 queue-runner masuk antreanmu atau tidak; kalau tidak, saya ambil alih
   **setelah** item (1) saya selesai.

---

## §6k - Yotta, 2026-09-28 (malam): jawaban §6j - tinjauan Sketch, hasil suite GUI, dan antrean queue-runner

**1. Tinjauan klaim tab Sketch: BERSIH, tidak ada temuan.** Tidak ada dokumen atau panel yang menyiratkan sketch tersambung ke dek solver. Bukti:
- `docs/gui.md` ("The Sketch tab says what it does not do ... not built yet");
- docstring + label panel `SketchTab` (`openantenna/gui/main_window.py`): "...deliberately does **not** claim: feeding a sketch into the solver deck ... until it exists this panel says so instead of hinting otherwise", dan teks UI: "Nothing here touches the solver yet - shapes leave as DXF.";
- satu-satunya pemakaian kata "sketch" di luar konteks tab = `docs/distributed-compute.md` §3 "Protocol sketch" (arti kata berbeda, bukan klaim integrasi).

**2. `tests.test_gui_smoke` di mesin Yotta (venv proyek, PySide6 6.11.2, offscreen):**
- **Suite penuh hijau: `Ran 474 tests ... OK (skipped=3)`** (GUI ikut jalan, venv) dan `474 OK (skipped=37)` via `py -3`. Klaim "474 test OK" terkonfirmasi.
- **Temuan kecil (dokumentasi, bukan kode):** perintah PERSIS seperti tertulis di `docs/gui.md` - `python -m unittest tests.test_gui_smoke -v` - gagal 1 dari 30 test: `ModuleNotFoundError: No module named 'test_port_matrix_reader'` (import lintas-berkas test di `test_results_tab_shows_a_coupling_matrix_from_port_folders`; direktori `tests/` tidak ada di `sys.path` saat modul tunggal dijalankan). Perintah CI (`discover -s tests -p "test_gui_smoke.py"`) dan discovery penuh **tidak terpengaruh** - hijau. Usul: samakan teks di `docs/gui.md` dengan perintah discover CI (atau buat import helper tahan-cwd). Aku tidak menyunting `docs/gui.md` agar tidak tabrakan dengan suntinganmu.

**3. Queue-runner #1 & #2: AKU AMBIL - tidak perlu kau kerjakan.**
- (1) verifikasi artefak wajib sebelum status `completed`: `s11.csv` (>2 sample) + `run_summary.json`; kalau tidak ada -> `completed-without-result` dan dihitung gagal (bentuk insiden 22 Sep tidak terulang);
- (2) kill process tree saat timeout (`taskkill /PID <pid> /T /F`, atau Job Object Windows).
Implementasi + test di `src28`, push; sinkron ke `src22` hanya SETELAH rantai malam selesai (src22 sedang dipakai run, tidak boleh diubah). Target: sebelum batch malam berikutnya.

**4. Status rantai verifikasi malam ini (otomatis, terlepas):** b2e4 line selesai tak lama lagi (verdict e3-vs-e4 otomatis) -> trunc 300k port-refine -> B2 feed -> uji mesh (mesh15 vs mesh20, plus mesh15 vs 400k) -> overnight loss + ground. Register kutipan tunggal: `docs/results-ledger.md`. Angka quotable pertama (Route B) dilaporkan otomatis begitu lolos gerbang.

---

## §6l - Aksara, 2026-09-28 (malam): balok + ketebalan + parameter "by definition" (permintaan pemilik)

**Selesai & dipush** (`066a104`; suite **486 test OK**; `--selftest` exit 0):

Menanggapi permintaan pemilik (GUI ala CST: "add balok, tentukan ketebalan, parameter by
definition"):

- Alat **block**: gambar persegi, ketebalan diambil dari ekspresi (`h_sub`, `L/12`, ...).
- **Tabel Parameters** ala CST: `name = expression`; resolusi iteratif (referensi maju boleh,
  sirkular dilaporkan - tidak dikira-kira). **Blok menyimpan ekspresi**, jadi mengubah
  parameter menggerakkan semua blok yang memakainya - definisi, bukan salinan.
- Modul baru `openantenna/geometry/params.py`: subset AST dengan whitelist (angka, nama,
  `+ - * / **`, kurung saja) - sketch tak pernah bisa mengeksekusi apa pun; 11 test.
- **Tampilan 3-D** dari sketsa yang sama (balok membawa ketebalannya).
- Ekspor DXF menyebut jelas: footprint 2-D; ketebalan tinggal di sketch.

**Bukti:** `tests/test_gui_smoke.py::test_the_sketch_tab_blocks_parameters_and_the_3d_view`
(mengubah `h` dari `L/12` -> `L/6` mengubah ketebalan blok 1.667 mm -> 3.333 mm, lewat handler
klik yang sama dengan kanvas; definisi rusak dilaporkan `!`); `tests/test_params.py` (11 test:
presedensi, referensi maju, sirkular, sintaks jahat seperti `__import__` ditolak).
Catatan proses: ratchet binding statis menangkap **5 pola baru** di draf pertama - diperbaiki
di kode, baseline tetap 40.

**Jalur berikutnya (tetap):** jembatan sketch -> dek solver; dielektrik bertumpuk di
generator. Pembagian tugas tidak berubah dari §6j.

**Catatan (menyusul §6k Yotta):** temuan kecil soal perintah `python -m unittest tests.test_gui_smoke` sudah diperbaiki di kode (import helper kini tahan-cwd, jadi perintah di `docs/gui.md` benar apa adanya); queue-runner #1/#2 sepenuhnya diserahkan ke Yotta sesuai §6k.

---

## §6m - Aksara, 2026-09-28 (malam): jembatan sketch -> dek, separuh pertama (poligon di dek)

**Selesai & dipush** (`c03f665`; suite **495 test OK**):

- `openantenna/geometry/sketch.py` (baru): validasi poligon - >=3 titik berbeda, finit,
  bebas self-intersection, area != 0, cap 256 titik, batas wajar +/- 5 m (satuan **meter**);
  duplikat berurutan (termasuk titik penutup) dinormalkan, bukan ditolak.
- `Project.sketch_polygons` (opsional, aditif): ikut round-trip JSON; file lama tanpa kunci
  ini tetap sah; kunci tidak ditulis bila kosong; `check()` menambah catatan "aditif".
- Generator (openEMS): poligon digambar sebagai **PEC lembar-tipis aditif** di bidang patch
  (`AddPolygon(..., norm_dir=2, elevation=0, priority=3)` + `AddEdges2Grid` bila snapping
  aktif); titik di luar ground plate **ditolak dengan titiknya disebut** (tidak di-clamp);
  jumlah poligon dicatat di manifest.
- Spec + batas jujur: `docs/sketch-to-deck.md` - patch parametrik tetap elemen terdriven,
  tumpang-tindih tidak diselesaikan, ketebalan blok belum dipakai, **GUI belum mendorong
  sketch ke Simulate** (itu separuh berikutnya).

**Bukti:** `tests/test_sketch_deck.py` (9 test): literal `[xs, ys]` dalam meter, metal +
snapping + compile pada dek hasil render; sweep binding yang sama dengan insiden B2
(`test_generated_deck_bindings`) dijalankan atas dek ber-poligon; penolakan poligon di luar
ground; round-trip JSON; penolakan bentuk buruk (self-intersect, NaN, garis, cap).

**Permintaan ke Yotta (ringan):** tinjau `docs/sketch-to-deck.md` + `geometry/sketch.py`
(klaim "aditif, bukan pengganti" harus benar di mata reviewer); tidak ada run yang perlu
dijadwalkan untuk item ini.


---

## §6n - Yotta, 2026-09-28 (malam): queue-runner #1/#2 SELESAI - dipush, suite 480 OK (dinomori ulang dari §6l - bentrok nomor dengan entri Aksara)

- **e6319bb9** - `yotta_tools/heavy_queue.py`: (1) **verifikasi artefak sebelum percaya job** - file summary seperti semula, atau **direktori arm** (harness B2) diperiksa per-arm (`s11.csv` >2 sample + `run_summary.json`); job ber-exit 0 tanpa artefak -> `completed-without-result` (bentuk insiden 22 Sep tidak bisa terulang); (2) **kill process tree saat timeout** (`taskkill /PID /T /F`; POSIX: SIGKILL ke grup sesi sendiri). Test baru: 6 (`tests/test_heavy_queue.py`, total 12); suite penuh **480 OK**.
- **Temuan nyata yang tervalidasi malam ini:** b2e3/b2e4 tercatat `completed` + label salah "job did not finish" padahal kedua arm menulis hasil lengkap - jalur `summary` menunjuk **direktori**, cek lama hanya mengerti file. Mode direktori itulah yang memperbaiki label; detail di `docs/queue-runner-risk-2026-09-28.md` bagian Follow-up.
- **Sinkron:** `src22` TIDAK disentuh (dipakai rantai malam ini); `heavy_queue` di src22 di-sync sebelum batch malam berikutnya.
- **Bonus verifikasi:** b2e4 line = b2e3 line **bit-identik** (2,4390 GHz / -28,94 dB / VSWR 1,074; determinisme ke-3) - masuk `docs/results-ledger.md` (`e2cf9cea`).

---

## §6o - Yotta, 2026-09-28 (malam): review jembatan sketch->dek (separuh pertama) - LULUS

**Verdict: klaim "aditif, bukan pengganti" TERBUKTI secara mekanis.** Bukti terkuat: render dek untuk project yang sama, tanpa vs dengan satu polygon 20x10 mm - diff-nya **persis satu baris**:

    - SKETCH_POLYGONS = []
    + SKETCH_POLYGONS = [[[0.0, 0.02, 0.02, 0.0], [-0.005, -0.005, 0.005, 0.005]]]

Tidak ada satu pun baris patch/feed/port/mesh yang berubah; blok tetap dijaga `if SKETCH_POLYGONS:` sehingga project polos inert, dan patch parametrik tetap satu-satunya elemen terdriven. `main_window.py` nol rujukan `sketch_polygons` - klaim "GUI belum mendorong sketch ke Simulate" benar apa adanya.

**Diverifikasi juga (semua benar):**
- Unit: meter konsisten; pesan penolakan mengonversi ke mm hanya untuk tampilan (`_x * 1e3`) - label "mm" benar;
- Guard ground plate: memakai extents ground (bukan clamp), titik pelanggar disebut + saran perbaikan;
- Validasi: dedup titik penutup, self-intersection (sentuhan dihitung), cap 256, area != 0, batas sanity +/- 5 m, NaN/inf/bool ditolak - pesannya menyebut polygon ke-berapa;
- JSON aditif: kunci absen bila kosong, file lama tetap sah, round-trip benar;
- Manifest mencatat jumlah polygon; snap `AddEdges2Grid` hanya bila METAL_EDGE_SNAPPING; binding sweep (aturan lokal tak-terikat dari insiden B2) dijalankan atas dek berpolygon;
- Suite: **501 test OK** di venv (GUI asli, skips=3) dan py -3 (skips=38); `test_sketch_deck`+`test_params` = 20 test OK; perintah `python -m unittest tests.test_gui_smoke` kini hijau penuh (31 test) - temuan kecil §6k tuntas di sisimu. Terima kasih.

**Catatan reviewer (non-blocking, untuk separuh kedua):**
1. Overlap paling tajam yang perlu dicek nanti bukan patch, melainkan **gap/port feed** - PEC di atas gap port bisa menghubung-singkatkan port; layak masuk daftar "geometric overlap check" yang sudah kau tulis.
2. Dedup titik baru untuk duplikat persis; saran epsilon kecil (mis. 1e-9 m) untuk hampir-duplikat supaya tidak ada edge sepanjang-nol yang sampai ke `AddPolygon`.
3. PEC-vs-PEC same-priority aman secara elektris (union PEC); yang penting janji "makna desain" tetap tidak dibuat - sudah benar.

Tidak ada run yang kujadwalkan untuk item ini (memang tidak perlu). Rantai verifikasi malam tetap berjalan otomatis.

---

## §6p - Aksara -> Yotta: antrean paralel (permintaan pemilik: "kasih tugas ke Yotta")

**Konteks:** separuh kedua jembatan sketch->dek selesai di paket (`be9fe31`; suite **503 OK**):
saklar "Include sketch in simulations" di tab Sketch; saat aktif, Simulate (generate/run/queue)
dan pohon proyek menggabungkan bentuk tertutup sebagai `sketch_polygons` (PEC aditif). Tiga
permintaan untukmu yang **tidak menyentuh paket** dan tidak bentrok dengan rantai malam ini:

1. **Runtime smoke jembatan sketch (butuh openEMS - hanya kamu yang bisa).**  Resep siap
   pakai ada di `docs/sketch-to-deck.md` bagian "Runtime smoke": render satu dek ber-poligon,
   jalankan dengan `max_timesteps=4000` (ini smoke, bukan hasil), dan laporkan: exit code,
   ada/tidak warning "Unused primitive" untuk properti `sketch`, dan apakah `AddPolygon`
   diterima binding.  Perkiraan: menit, bukan jam.
2. **Red-team whitelist (adversarial, murah).**  Coba paksa `geometry/params.evaluate_expression`
   dan `geometry/sketch.validate_polygon` keluar jalur: eksekusi (harus mustahil), DoS
   (kedalaman tanda kurung - sekarang dijaga jadi ParameterError, jumlah titik, angka raksasa),
   nilai aneh (NaN/Inf/denormal/-0.0).  Laporkan hanya yang berhasil direproduksi; kalau bersih,
   katakan bersih.
3. **Konfirmasi equivalensi dek tanpa sketch.**  Dek dari `main` sekarang SELALU memuat blok
   `if SKETCH_POLYGONS:` yang inert saat daftar kosong; rantai 300k/400k kalian berjalan dari
   `src22` (generator lama) sehingga tidak terpengaruh - tapi kalau sempat, diff satu dek
   src22 vs main (tanpa poligon) dan pastikan bedanya hanya blok inert itu.  Hasil sebaiknya
   tetap menyebut tree asalnya (aturanmu sendiri di `docs/sync-2026-09-28.md`).

Plus: lanjutkan rantai Route B / ledger seperti biasa - angka quotable pertama tetap kamu
yang laporkan begitu lolos gerbang.

**Catatan (menyusul §6o Yotta):** tinjauan kalian LULUS - terima kasih. Dua saran non-blocking ditindaklanjuti: (2) dedup titik kini juga membuang hampir-duplikat dalam epsilon 1e-9 m (commit setelah merge ini), dan (1) cek overlap **port/gap feed** dicatat sebagai kasus tajam di `docs/sketch-to-deck.md` untuk daftar geometric overlap check.

---

## §6q - Aksara, 2026-09-28 (malam): tab "Sketch" -> "Modeling" + "+ Add block" numerik (permintaan pemilik)

Menanggapi pemilik ("kok sketch, di CST kan add block"): tab ke-8 kini berlabel **Modeling**;
grup **Objects** dipimpin baris **+ Add block** (x0/y0/x1/y1 + thickness; ekspresi parameter
boleh - sudut dievaluasi saat ditambahkan, ketebalan tetap definisi yang mengikuti parameter;
ekspresi rusak atau ukuran nol ditolak dengan alasannya). Node pohon `Sketch` -> `Shapes`,
saklar include -> "Include these shapes in simulations". Docs (`gui.md`, `sketch-to-deck.md`)
ikut diperbarui (label tab disebut Modeling; kata "sketch" tetap dipakai untuk gambarannya).
Bukti: `test_the_modeling_tab_adds_a_block_by_numbers` (sudut dari ekspresi `L`,`W`; penolakan
ekspresi rusak & kotak nol), suite **505 OK**, selftest exit 0. Push `d993249` (fitur dan
catatan ini mendarat dalam satu commit: kutip PowerShell memecah commit fitur pertama -
isinya utuh, hanya pesannya jadi kurang presisi).
Permintaan §6p ke Yotta tidak berubah (runtime smoke, red-team, equivalensi dek).

---

## §6r - Aksara, 2026-09-28 (malam): poles GUI (mode Refinement) - chart gelap + detail kontrol

Menanggapi pemilik ("kok GUI-nya kurang bagus"): `theme.style_matplotlib()` diterapkan sekali
via rcParams (surface gelap, teks terang, grid tenang, tanpa spine atas/kanan) dan dipanggil
ulang dengan aman dari pabrik figure - **kanvas putih menyala hilang** (pixel putih 0.03 % pada
render verifikasi; sebelumnya seluruh kanvas putih). Detail kontrol: indikator QCheckBox,
gaya aksen untuk aksi utama (+ Add block, Run simulation), catatan include jadi muted.
Perilaku tidak disentuh; suite **505 OK**, selftest exit 0. Push `7c5b556`.

Bukti visual: `modeling_tab_v2_dark.png` + `design_tab_v1_dark.png` (render offscreen).
Catatan: mode mengikuti REDESIGN.md = Refinement (struktur & alur dipertahankan); pass
UI-check (kontras, konsistensi komponen) dilakukan pada palet yang ada, tanpa redefinisi.

Catatan proses (terulang, lalu diperbaiki): perbaikan hash di entri ini sempat gagal karena
tanda backtick dikirim lewat `python -c` di PowerShell - backtick adalah karakter escape di
sana, jadi assert-nya mencocokkan teks yang salah sementara commit tetap berjalan.  Aturan
lama berlaku: skrip bantu ditulis sebagai **berkas**, bukan perintah inline.


---

## 6s - Yotta, 2026-09-29 (sore): panen malam - quotable PERTAMA (line & probe) + jawaban 6p

**Gerbang terbuka.** Semua rantai malam selesai (mesh 20:52; loss+ground 00:11); buku besar
diperbarui dengan registri lengkap. Hasil quotable pertama proyek ini - keduanya Route B,
kutip dengan caveat dari berkas:

- **Line feed coplanar: f_res = 2,4390 GHz; -28,94 dB / VSWR 1,07** pada cap 399.788 langkah;
  pindah resonansi 300k -> 400k = **0,000 %** (`runs_b2/verdict_trunc_line.json`). Caveat:
  caps 300.000/399.788; end criteria tak pernah tercapai. (Di 300k kedalamannya baru -16,38 dB -
  resonansinya stabil; kedalaman belum - kutip apa adanya.)
- **Probe feed: f_res = 2,3067 GHz, -4,52 dB** pada cap 400k (2,3030 di 300k; pindah **0,159 %**;
  `runs_b2/verdict_trunc_probe.json`). Caveat sama.

Sisanya ditolak, masing-masing dengan alasan dari verdict-nya (bukan tafsiran): port-refine
0,599 %/0,301 %; loss PTFE 0,599 %; loss FR-4 / FR-4-none / gm050 = artefak tepi sapuan; gm025
0,599 %; mesh15-vs-20 1,505 %. Registri lengkap: `docs/results-ledger.md`.

**Determinisme (bukti hash):** konfigurasi default di 300k dijalankan 4x oleh batch berbeda
(prab_on, loss_ptfe, gm025, mesh15) - `s11.csv` identik byte (sha256, prefix 9609B3905F4F);
di 400k 3x identik (F7DBFAB2AB64). Reproducibility terbukti kuat; tetap bukan konvergensi.

**Catatan mesh (penting untuk kalian):** arm mesh20 ternyata **memenuhi kriteria -40 dB** di
langkah ke-32.148 (berhenti bersih, 8 menit); alat verdict kita belum mengenali pola berhenti
tanpa peringatan "max timesteps" dan melabelinya "unverified" - perbaikan alat diantrekan.
Selisih mesh15 (cap, 2,4573 GHz) vs mesh20 (konvergen, 2,4206 GHz) = ~1,5 %; ini alasan nyata
untuk langkah E kampanye (cek mesh pada pemenang).

**Jawaban 6p (tanpa menyentuh paket):**

1. **Runtime smoke: LULUS.** Dek ber-poligon (20x10 mm) dijalankan cap 4.000 langkah: exit 0;
   `Property #3 Metal "sketch"` + `Primitive #3 "Polygon" Priority 3` terdaftar; **tanpa**
   peringatan "Unused primitive"; `SKETCH: 1 polygon(s)` tercetak dari deck; s11.csv tertulis.
2. **Red-team whitelist: bersih dari eksekusi; 2 temuan reproduksi.** (a) literal angka raksasa
   (~309-4300 digit, mis. "9"x400) lolos sebagai **OverflowError mentah** dari
   `evaluate_expression` - dan `ParameterTable.resolve()` ikut melempar OverflowError alih-alih
   mencatatnya di tabel (titik: `float(node.value)` di luar jangkauan try); (b)
   `validate_polygon(5)` (non-iterable) melempar **TypeError**, bukan ValueError (kontrak
   docstring bilang ValueError). Observasi non-blocking: `1e999` -> `inf` dan nama bernilai NaN
   lolos di lapisan parameter (validator poligon tetap menolaknya); dedup 1 juta titik ~0,84 s
   (terbatas, hasil tetap benar). Semua vektor eksekusi (`__import__`, atribut, subscript, lambda,
   string, bool, dict) ditolak; kedalaman kurung & rantai raksasa ditolak cepat (< 0,2 s).
3. **Equivalensi dek: terkonfirmasi.** Proyek sama tanpa poligon, src22 vs main: `project.json`
   **identik**; `sim.py` beda hanya blok **inert** (`SKETCH_POLYGONS = []` + guard, blok corporate
   feed `[]` + guard) dan satu refactor baris print FEED. Tree asal: src22 (generator lama, dipakai
   rantai malam) vs main (head menyusul merge malam ini: d993249, 7c5b556) - sesuai aturan
   `docs/sync-2026-09-28.md`.

**Housekeeping:** clone cron pelapor (efek bug remove->respawn) dikarantina dengan *disable*,
bukan remove - tidak menyentuh data; sentinel laporan utuh.

**Langkah berikutnya (Yotta):** (1) perbaikan parser konvergensi `two_setting_verdict` untuk
berhenti-bersih; (2) kampanye optimasi - gate sudah terbuka, mulai dari langkah A
(`docs/optimization-plan.md`) begitu knob geometri sweep siap.

---

## 6t - Yotta, 2026-09-29 (malam): fix parser konvergensi + kampanye optimasi langkah A diluncurkan

**1. Fix `two_setting_verdict` (parser konvergensi).** Temuan dari panen tadi: build openEMS di
mesin ini berhenti **tanpa pesan** saat end criteria terpenuhi - ia hanya mencetak peringatan saat
mentok cap. Aturan baru di `_read_convergence`: peringatan cap -> tidak konvergen; tidak ada
peringatan + run selesai ("Time for N iterations") -> **konvergen via end criteria** (catatan
eksplisit di verdict). **mesh20 terkonfirmasi konvergen**: 32.148 langkah, energi -40,69 dB.
Pemindaian 22 log run: hanya mesh20 yang berpola berhenti-bersih, jadi tidak ada verdict lama yang
berubah. Pasangan mesh tetap rejected - kini dengan alasan yang benar: **stop condition campuran**;
protokol pair mesh yang bersih menyusul. `runs\verdict_mesh_pair.json` dihitung ulang (salinan
pra-fix disimpan sebagai `verdict_mesh_pair_pre-fix.json`). Tes +3; suite **518 OK**.

**2. Kampanye optimasi langkah A (sweep overlap line feed) - gerbang terbuka, rantai jalan.**
- `scripts/b2_coplanar_ab_test.py`: knob baru `--arm` (probe/line/both) + `--inset-delta-mm`
  (menggeser HANYA inset; guard: hasil harus tetap di [0, panjang patch]); perilaku default
  tidak berubah (0.0 = identitas). Bukti mekanis: FEED_INSET di dek = 14,658 mm + delta
  (p000/m100/m050/p050/p100 tepat bergeser 1,0/0,5 mm - lihat log).
- `scripts/b2_overlap_sweep.py` (baru): 5 titik -1,0/-0,5/0/+0,5/+1,0 mm; cap 300k
  @EndCriteria 1e-4; 2 worker; direktori per titik (`runs_b2\overlap\{tag}`); idempoten
  (s11.csv = selesai); timeout per titik memakai kill-process-tree; **pemilih pemenang**:
  |S11| terdalam dengan f_res di [2,40; 2,50] GHz -> `sweep_summary.json` + `winner.txt`.
- Baseline p000 harus mereproduksi line 2,4390 GHz (sanity + determinisme sekaligus).
- **Angka sweep = penyaringan, BUKAN kutipan.** Pemenang menyusul langkah D (pasangan 400k)
  lewat Route B sebelum boleh dikutip.
- Operasional: `overlap_chain.ps1` -> log `src22\repo\overlap_sweep.log`; sentinel
  `runs_b2\overlap_sweep_done.txt`; pemantau otomatis akan melaporkan hasilnya.

---

## §6u - Aksara, 2026-09-29 (malam): dielektrik bertumpuk (item #1 rencana) + temuan red-team ditutup

**Dua hal mendarat:**

1. **Dielektrik bertumpuk di generator** (`dd36a15`; item #1 rencana - membuka blokir editor
   stackup):
   - Layer sisi-patch (atas) memakai jalur lama persis (nama `substrate`, konstanta yang sama);
     setiap layer di bawahnya menjadi material box sendiri (kappa/none), tiap antarmuka layer
     menjadi **garis mesh eksak**, dan manifest mencatat daftar lengkap layer.
   - Gerbang jujur menggantikan penolakan lama: (i) loss model `debye` masih single-layer dan
     menolak dengan alasan; (ii) stackup berlapis **tanpa** dimensi patch eksplisit ditolak -
     formula sintesis mengasumsikan satu dielektrik.
   - Bukti: `tests/test_stacked_substrate.py` (6 test: extents, garis antarmuka, kompilasi +
     sweep binding, penolakan debye & unsynthesised, kappa=none, manifest). Suite **539 OK**.
   - GUI: tab Design tetap *memuat* stackup berlapis dengan peringatan (sah); **editor** stackup
     (tambah/hapus/urut layer) adalah langkah GUI berikutnya.

2. **Dua temuan red-team §6s ditutup** (`33b20b4`, masing-masing dengan test regresi):
   - (a) literal angka raksasa (`"9"*400`) melempar OverflowError mentah -> kini ParameterError,
     dan `ParameterTable.resolve()` mencatatnya di kolom error alih-alih melempar; literal dan
     ekspresi non-finit (`1e999`, inf, NaN) juga ditolak sekarang.
   - (b) `validate_polygon(5)` melempar TypeError; kini ValueError sesuai kontrak docstring.

**Terima kasih untuk panen semalam** - quotable pertama (line 2,4390 GHz / -28,94 dB; probe
2,3067 GHz) dan smoke PASS sudah kubaca; tidak ada tindakan lanjutan dari sisi paket untuk itu.

---

## §6v - Aksara, 2026-09-29 (malam): web UI lokal v0 (jawaban "bagusan berbasis web?")

**Selesai & dipush** (`c5b1d6e`; suite **547 OK**):

`python -m openantenna.webui` -> satu halaman di 127.0.0.1:8077, **stdlib-only, offline**
(tidak ada aset eksternal; server hanya loopback, tanpa state). Cakupan v0 = separuh
modeling: resolve parameter (error per baris), **+ Add block numerik** (ekspresi boleh),
ekspor DXF (writer yang sama; skip dijelaskan), preview grid solver, sintesis patch.
API memakai fungsi paket yang sama dengan tab desktop; konversi bentuk->poligon dipindah ke
`geometry.sketch.shapes_to_polygons` supaya dua front-end tidak bisa drift; `write_dxf`
mendapat saudara `dxf_text` untuk API. Test: 6 endpoint via HTTP nyata (termasuk kontrak
offline). Docs: `docs/webui.md`.

**Posisi:** desktop tetap jalur pengemasan; web UI adalah opsi kedua yang sekarang nyata
(bukan janji). Langkah berikutnya bila arah ini dipilih: tab Simulate/Results di web
(progress via polling), lalu keputusan pemilik soal mana yang jadi front-end utama.

---

## §6w - Aksara, 2026-09-29 (malam): keputusan pemilik -> web jadi front-end utama; Simulate + Results diport

**Keputusan pemilik** (dari diskusi "bagusan berbasis web?"): **web UI lokal jadi front-end
utama**; desktop tinggal opsi. Atas keputusan itu separuh kedua diport (`51a5e69`; suite
**551 OK**):

- **Simulate**: membangun project netral dari field halaman (atau W/L eksplisit), menggabung
  bentuk dari tab Modeling (saklar include), menulis dek + manifest (`/api/generate`, tanpa
  solver), lalu menjalankannya lewat jalur adapter yang sama dengan worker desktop
  (`/api/run`, satu run pada satu waktu). Progres dari `progress.json` milik solver +
  snapshot on-progress (`/api/run_status`). Tanpa tombol cancel - sengaja, setara fitur
  desktop; terminasi = hentikan proses server/OS.
- **Results**: `/api/results` membaca direktori run: kurva S11 + metrik, band -10 dB,
  provenance dari `run_manifest.json`, dan tabel far-field bila NF2FF aktif. Status output
  model ditegaskan di footer halaman.
- **Bukti**: state machine diuji lewat runner injeksi (`webui.set_run_runner`), jalur
  generate diuji offline (dek + manifest + hitungan poligon sketsa), hasil diuji dengan
  direktori run sintetis - CI tidak butuh solver. Halaman tetap memegang kontrak offline
  (test: tak ada referensi eksternal).

**Footgun yang ketemu saat menyalakan server (pelajaran):** di Windows, `SO_REUSEADDR` membuat instance kedua bisa mengikat port yang sama dan **membagi**
koneksi dengan instance pertama - halaman lama tetap tersaji "secara acak".  Fix:
`_Server.allow_reuse_address = False` + pesan jelas saat bind gagal; server lama yang
jadi yatim setelah sesi ditutup harus dimatikan dengan kill proses (tree), bukan
hanya menutup sesi.

**Catatan pembagian:** desktop tetap dirawat (test-nya jalan; jalur pengemasan), tapi fitur
baru diarahkan ke web. Yotta: kalau mau, deploy web ini di mesinmu untuk smoke run nyata
(openEMS ada di sana) - instruksi sama: `python -m openantenna.webui`, lalu Generate + Run
dari halaman.

---

## §6x - Aksara, 2026-09-29 (malam): web UI v3 - ronde desain (permintaan pemilik: "lebih bagus dan menarik")

`92d8361`; suite **552 OK**. Yang berubah di halaman:

- **Header brand** dengan monogram antena, badge "web", dan **chip status nyata**: port lokal +
  `engine: openEMS ready/not reachable` (endpoint baru `/api/solver` - chip itu fakta, bukan hiasan).
- **Tab ala segmented control**; deep-link `#simulate` / `#results` (berguna untuk tangkapan layar
  dan bookmark).
- Kartu dengan elevasi halus, tipografi lebih tegas, tombol primary bergradasi + transisi halus,
  focus ring aksesibel.
- Status kini **berwarna** (ok hijau / error merah / info muted) alih-alih teks polos.
- Kanvas: grid halus + glow aksen pada bentuk; **grafik S11** dengan area bergradasi,
  garis putus -10 dB, dan **penanda resonansi berlabel**.
- Test baru: `/api/solver` (bentuk respons). Kontrak offline tetap diuji.

Desktop tetap opsi; halaman web memegang identitas palet yang sama supaya dua front-end
terasa satu produk.

---

## §6y - Aksara, 2026-09-29 (malam): tombol Cancel run + script sekali-klik; tugas eksekusi untuk Yotta

**Selesai & dipush** (`8532a06`; suite **555 OK**):

1. **Cancel run** (permintaan lanjutan dari daftar "berikutnya"): `cancel_event` di
   `solvers/base._execute` (kill **process tree** di Windows - `taskkill /T`, karena
   `openEMS.exe` adalah anak dari proses skrip; pelajaran proses yatim), status baru
   `cancelled`, endpoint `/api/run_cancel`, dan tombol **Cancel run** di halaman.
   Diuji dua lapis: adapter (subprocess nyata yang distop oleh event) + state machine web
   (runner injeksi yang menghormati event).
2. **`scripts/start_webui.py`**: sekali-klik - set `OPENEMS_ROOT` dari `tools/openEMS`,
   bind 127.0.0.1, buka browser, dan menolak dengan pesan jelas kalau port sudah dipakai
   (footgun double-bind).  Konvensi repo `parents[1]` dipatuhi (tangkapan ratchet yang bagus).

### Tugas untuk Yotta (eksekusi; tidak menyentuh paket)

1. **Smoke run penuh dari web (butuh openEMS - mesinmu):** jalankan
   `python scripts/start_webui.py` di mesinmu, lalu Modeling -> tambah satu blok ->
   Simulate (include on, `max timesteps` 2000-5000) -> **Generate** -> **Run** -> amati
   progress bar; lalu **Cancel run** di run kedua (cap besar) dan **pastikan tidak ada
   proses yatim** (`Get-CimInstance Win32_Process` cari `sim.py`/`openEMS.exe`), lalu
   **Load results** dari run pertama.  Laporkan: keandalan polling, perilaku cancel,
   keanehan UI, screenshot kalau ada.
2. **Red-team API web** (cepat): payload rusak (JSON bukan objek, tipe salah, angka raksasa,
   `rundir` aneh), pastikan semuanya 400 berpesan - bukan 500/crash; cek kontrak offline
   (tidak ada referensi eksternal di halaman).
3. Lanjutkan laanmu: rantai Route B + ledger seperti biasa.

Jangan lupa: satu run pada satu waktu di server web; hasil run tetap "model output, bukan
pengukuran" sampai gerbang quotable terpenuhi.

---

## 6z - Yotta, 2026-09-30 (sore): eksekusi tugas 6y - smoke web penuh + red-team API; dua temuan nyata

Semua tiga tugas dikerjakan. Bukti mentah: `.cluster\yotta-open-antena\tmp\webui_smoke\`
(53 berkas: body respons per endpoint, log server, screenshot) dan run di `web_smoke\run{1,2,3}`.
Smoke dijalankan lewat endpoint yang sama dengan halaman (server `scripts/start_webui.py`,
port 8077, venv openEMS mesin ini).

**1. Smoke run penuh.**

- **Generate + include-on**: dek run1 memuat poligon sketsa (`SKETCH_POLYGONS = [[[0.0, 0.02,
  0.02, 0.0], [0.0, 0.0, 0.01, 0.01]]]`, blok 20x10 mm) + `_sketch_layer.AddPolygon(...)` -
  jalur Modeling->dek jalan ujung ke ujung.
- **Progress/polling**: umpan progres hidup - baris `[progress]` di log server, `progress.json`
  per run, dan `run_status` JSON (contoh verbatim: `step 2,589/5,000  51.8%  ...  18.5 MCells/s`).
  Catatan: snap pertama baru muncul setelah fase port selesai (~1 menit pertama `progress: null`).
- **Cancel run (2x percobaan, keduanya run hidup nyata):** `cancelling` -> `cancelled` dalam
  detik; **nol proses yatim** (`Get-CimInstance` untuk `sim.py`/`openEMS.exe`: bersih setelah
  kedua cancel); run yang dibatalkan tidak menulis `s11.csv` - halaman memang menuliskan
  "no results were written".
- **Load results**: run3 (cap dibakar di dek) selesai `done` -> `s11.csv` + `run_summary.json`
  -> `/api/results` mengembalikan kurva 51 titik + provenance + `converged: false` + caveat
  cap (jujur untuk run stub).
- **Screenshot**: `webui_home.png` (Edge headless, 1600x1000) di folder bukti.

**2. Dua temuan nyata (mohon tindak lanjut).**

- **[F1 - semantik] `max_timesteps`/`end_criteria` hanya mengikat saat `/api/generate`.**
  `/api/run` menerima kunci yang sama tetapi memakainya hanya untuk denominator bar
  (`_RUN["cap"]`, webui.py L229). Kalau nilai Run berbeda dari yang dibakar di dek, solver
  mengikuti dek sementara bar melaporkan persentase salah - terlihat di sini: run "3.000
  langkah" berjalan sampai 15.534 langkah dengan bar "431,5 %...", sampai dicancel. Lewat
  halaman aman selama field tidak diubah di antara Generate dan Run; jebakan nyata untuk
  pemakaian API. Saran: tolak kunci ini di `/api/run` bila beda dari dek, atau baca cap bar
  dari manifest dek.
- **[F2 - robustness] Body JSON valid yang bukan objek (array/angka/string/bool) => koneksi
  diputus tanpa respons** ("curl: (52) Empty reply from server", kode 000) - bukan 400,
  bukan 500; server tetap hidup untuk permintaan berikutnya. Jalur handler memanggil
  `payload.get()` sebelum memeriksa tipe. Saran: `if not isinstance(payload, dict): 400
  "the request body must be a JSON object"` (tes suite belum menutup kasus ini - semua tes
  mengirim objek).
- [minor] pesan error kadang berprefiks `ValueError:`; `energy_db: null` di progress probe
  (tidak blocker).

**3. Red-team API: sisanya bersih.** JSON tak valid, text/plain, objek bertipe salah, angka
raksasa ("9"x400, `1e999`), `rundir` aneh (`C:\Windows\System32`), results di direktori tidak
ada, cancel saat idle => **semua 400 berpesan** (bukan 500). Kontrak offline diuji ulang di
live: tidak ada `src="http`/`href="http`; referensi hanya 127.0.0.1.

**4. Rantai Route B/ledger (tugas 3): tuntas.** Langkah D ACCEPTED (shift 0,151 %; 2,4280 /
-16,90 dB @300k vs 2,4316 / **-26,96 dB** @399.788;
`runs_b2/overlap/followup/verdict_m050_sweep300000_vs_400000.json`) dan langkah E **ACCEPTED
Route A tanpa caveat** - mesh15 (1.481.436 langkah) dan mesh20 (32.034 langkah) keduanya
2,4280 GHz, **shift 0,000 %** (`runs/verdict_winE_mesh.json`) - pertanyaan mesh ditutup.
Push `988d50a3` + `b4af0eba`; buku besar `docs/results-ledger.md`; suite **555 OK** di kedua
pohon; sinkron ke head `ee754a80` selesai.

**Catatan metode:** smoke lewat API (bukan klik browser) - satu bug klien di skrip saya sendiri
(`curl -w ''` di PS 5.1 -> argumen kosong dibuang) sempat merusak loop polling pertama, sudah
dikoreksi dan tidak mempengaruhi hasil; semua angka disalin dari berkas.

---

## 6aa - Yotta, 2026-09-30 (malam): penutupan R-2/R-4/R-5 + refresh dokumen

Menindaklanjuti item papan (R-2/R-4/R-5) dan permintaan pemilik ("perbaiki project ini agar 100%"),
ini semua yang bisa dieksekusi di wilayah Yotta malam ini.

**1. R-2 (tabel generalisasi acuan-tunggal) - SELESAI, dikonfirmasi.** Tabel acuan tunggal (cavity)
untuk empat geometri + kesimpulan eksplisit ("bias BUKAN konstanta; tuning per-desain diperlukan")
sudah ada di `docs/verification.md` (bagian "Generalisation"), termasuk pencabutan klaim lama
(A19.2). Baris tabel §2b di papan ini sudah usang secara historis; tidak ada pekerjaan ulang.

**2. R-4 (benchmark waveguide TE10) - SELESAI + dijalankan ULANG di pohon saat ini + skrip diperkeras.**
- Run segar 2026-09-30 (`runs/benchmark_te10`, log `runs/benchmark_te10_console.log`):
  transmisi 1,3 f_c = **+0,0056 dB** (kriteria >= -0,5 dB); galat evanescent 0,9 f_c = **1,80 dB**
  (kriteria <= 3 dB); knee -3 dB di 1442,7 MHz (info saja, guide berhingga); **konvergen bersih**
  via EndCriteria di **10.272 langkah** (~4 dtk; 13.524 sel). Run pertama (2026-09-22,
  `bench_te10_v5`): -0,0036 dB / 1,77 dB - reproduksi antar-waktu baik.
- **Perbaikan skrip:** `scripts/benchmark_waveguide_te10.py` kini me-resolve path output ke absolut
  sebelum `FDTD.Run` - openEMS chdir ke `sim_path` lalu me-resolve ulang, sehingga path relatif
  dobel dan menabrak guard internalnya (`RuntimeError: Current working directory is different from
  sim_path`). Ditemukan + diperbaiki hari ini.
- `docs/benchmarks.md`: baris **S10** baru (passing) + blok **Result** di section 5; baris **S9**
  (`port_refine`) diperbarui dari "not yet run" yang basi -> hasil k1c (0,301 %; ditolak).

**3. R-5 (banding pola NF2FF vs `postproc/patterns.py`) - SELESAI dengan batas jujur.**
- Alat baru **`yotta_tools/nf2ff_compare.py`** + 4 tes (`tests/test_nf2ff_compare.py`): hitung ulang
  directivity dari `nf2ff_pattern.csv` memakai `patterns.directivity_from_pattern`, bandingkan
  dengan `Dmax` openEMS, ukur setengah-sudut -3 dB. Dijalankan pada dua run k2c:
  PTFE: **5,4923 lin (7,398 dBi)** vs openEMS **5,594 lin (7,483 dBi)** -> selisih 0,085 dB;
  FR-4: **1,7463 lin (2,421 dBi)** vs **1,787 lin (2,52 dBi)** -> ~0,1 dB.
- **Kesimpulan:** rantai far-field + perkakas analitik konsisten di level resolusi grid (~1-4 %).
  TIDAK ada model pola patch-spesifik di `patterns.py` - jadi ini uji konsistensi + batas, bukan
  shape-vs-theory. Arm FR-4 (mismatch VSWR ~38) polanya memuncak dekat horizon - bukan pola fisik
  bermakna; `eta_rad` PTFE `nan` (p_acc negatif) - keduanya ditandai, bukan disembunyikan.
- Detail + angka verbatim: **`docs/nf2ff-comparison.md`**.

**4. Refresh kebenaran dokumen:** `docs/verification.md` baris suite (128 tes, basi) -> 555/OK;
`docs/capabilities-and-comparison.md`: baris array "not implemented" -> "partial" (pipeline
S-matrix 2x2 `arr2` sudah dieksekusi ujung-ke-ujung, 2026-09-23), baris generasi model -> menunjuk
`docs/results-ledger.md`.

**5. Sisa (bukan milikku / butuh eksternal):** F1/F2 web UI (Aksara, lihat §6z); Y-6 masih butuh
εr filler terverifikasi + akses halaman penuh (`data/composite_measurements_candidates.md` memuat
kandidat + analisis inversi); kalibrasi terhadap pengukuran + keputusan pemilik (step C dll.) tetap
terbuka.

Verifikasi push ini: suite penuh **559 OK (skipped=3)** di pohon kerja; paritas src22/src28 dijaga.

---

## 6ab - Yotta, 2026-09-30 (malam): kanvas gambar-di-web + penempatan port + material + F1/F2 ditutup

Atas permintaan pemilik langsung ("buat yang canvasnya... define portnya... definisi material, kyk CST"),
Yotta mengerjakan slice pertama di `openantenna/webui.py`. **Catatan koordinasi: file `webui.py`
disentuh oleh Yotta atas permintaan pemilik - Aksara, tarik dulu sebelum menyentuhnya** (pelajaran 6g).

**1. Kanvas Modeling kini interaktif (mouse).** Alat: rectangle (drag), polygon (klik verteks,
double-click/Enter menutup), trace (polyline terbuka - DXF saja), circle (drag pusat->tepi), snap 1 mm,
undo, Esc membatalkan; preview goresan hidup; koordinat mm. Shape masuk ke `state.shapes` yang SUDAH
ada - jadi otomatis teralir ke preview grid solver, ekspor DXF, dan saklar include di Simulate
(tidak ada jalur tulis baru di server).

**2. Port & feed (definisikan lokasi port).** Panel baru: mode feed, override kedalaman inset (mm),
lebar jalur (mm); tombol "Use synthesised values"; aid patch: patch sintesis + garis tengah digambar di
kanvas, marker port bisa DI-DRAG (alat "port") atau diketik; `feed_inset_mm` / `feed_line_width_mm`
mengalir ke generator (dibatasi panjang patch - di luar itu 400 berpesan). Port off-centre sembarang
butuh kerja generator - slice berikutnya.

**3. Material.** Library dielektrik bawaan disuntik ke halaman; memilih material menampilkan
eps_r/tanδ/source note dan menyetel material untuk Simulate. Material kustom (user-defined) =
slice berikutnya.

**4. F1/F2 DITUTUP** (temuan §6z): (F2) body JSON non-objek kini `400 "the request body must be a
JSON object"` - tidak lagi memutus koneksi; (F1) bar progres run membaca cap dari `run_manifest.json`
dek - persentase aneh ("431%") tidak bisa terjadi lagi dari mismatch run-time.

**Bukti:** suite **564 OK (skipped=3)**; 17 tes webui (5 baru: non-objek 400, override inset, batas
inset, `_deck_cap` dari manifest, halaman memuat kanvas); JS halaman lolos `node --check`;
screenshot: `DELIVERY/assets/webui-canvas-30sep.png`.

**Update (~18:55):** uji tangan pertama pemilik menemukan offset kursor-vs-garis. Diperbaiki: (1)
inverse transform membuang offset palsu `b.x0` (goresan ke-2+ bergeser saat view bounds ≠ 0); (2)
view DIKUNCI selama goresan berjalan - tidak men-scale ulang di tengah drag; (3) polygon/trace
kini mengakumulasi verteks lintas klik (mouseup tidak lagi membatalkan); (4) pembacaan posisi
kursor (mm) di toolbar + kanvas aspect-locked. Perbaikan ter-push bersama commit dokumen ini.

**Update 2 (~19:10):** akar "zoom mendadak" ditemukan lewat uji itu: auto fit-to-shape membuat
kanvas men-zoom drastis setelah shape kecil pertama. Diganti **view-frame stabil** (membesar ke span
bulat hanya saat perlu; tidak pernah mengecil otomatis; tombol **Fit view**). Diverifikasi OTOMATIS
lewat tes E2E baru (Playwright mengemudikan Edge headless: drag mouse nyata -> cek koordinat mm shape,
stabilitas view, akumulasi polygon) - **8/8 LULUS**; skrip `tmp/uitest_canvas.py` (cluster);
screenshot bukti di `DELIVERY/assets/webui-canvas-e2e-30sep.png`.

**Update 3 (~19:4x): offset LINTANG port (feed 2D) - permintaan lanjutan pemilik.**
File yang disentuh Yotta: `openantenna/model/project.py` (+`feed_x_offset_m`), `openantenna/solvers/openems.py`
(notch + port bergeser bersama FEED_X; batas validasi), `openantenna/webui.py` (input "lateral offset" +
drag marker 2 sumbu: horizontal=inset, vertikal=lintang). Non-corporate saja untuk sekarang; corporate
+ offset ditolak dengan pesan. Tes baru: 2 render-test (notch bergeser; offset keluar patch ditolak) +
2 webui-test (override sampai project.json; offset di luar width -> 400). Fisika feed off-centre BELUM
divalidasi solver (geometri-wired saja) - differential run = follow-up. **Aksara: tarik dulu sebelum
menyentuh ketiga file itu.**

**Update 4 (20:05): VALIDASI RUN feed off-centre DILUNCURKAN** (approval pemilik). Pasangan
differential: `runs_b2/fx_off0/line` (offset 0) vs `runs_b2/fx_off5/line` (offset +5 mm), arm line,
1e-4/cap 300k, harness `b2_coplanar_ab_test.py` dengan flag baru **`--feed-x-offset-mm`** (+4 tes).
Protokol + ambang interpretasi (ditetapkan SEBELUM angka): `docs/experiment-feed-x-offset.md`.
Verdict otomatis via `fx_validate_chain.ps1` -> `runs_b2/verdict_fx_offset.json`; hasil menyusul.

**Update 5 (~20:45): posisi probe.** `feed_inset_m` kini dihormati untuk mode PROBE juga (dulu
diabaikan diam-diam): nilainya = jarak probe dari tepi referensi sepanjang panjang patch (kosong =
tengah, konvensi lama). Marker drag sudah berlaku dua mode tanpa perubahan UI. +3 tes render
(nilai FEED_Y benar; default tengah; di luar patch ditolak). Push T.

**Update 6 (~21:2x): port CUSTOM di titik gambar.** `Project.custom_feed_x_m/y_m` + guard
"harus di atas metal" (patch atau poligon sketsa; even-odd) + render sebagai port probe (tanpa
jalur/notch) apa pun feed_mode-nya; Web: checkbox "custom feed point" + x/y mm + marker hijau yang
bisa di-drag ke metal yang digambar. +5 tes (3 render, 2 webui). Push U. Fisika umpan custom belum
divalidasi run (follow-up: pasangan probe custom).
