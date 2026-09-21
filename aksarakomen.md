# aksarakomen — catatan kerja Aksara

File ini adalah catatan lengkap dari **Aksara**, agen yang bertugas
**mendevelop dan menyelesaikan** proyek ini. File pasangannya adalah
**`yottakomen.md`**, ditulis oleh agen lain (**Yotta**) yang bertugas
**mengevaluasi, menganalisis, dan mengetest** hasil kerja ini dengan fokus pada
detail saintifik dan engineering.

**Aturan kerja yang disepakati (dari pemilik proyek):**
1. Setiap kali Aksara membuat/mengubah file → langsung commit → **push ke GitHub**.
2. Repo harus tetap tersinkron dengan GitHub (pull sebelum bekerja bila perlu).
3. Semua keterangan Aksara ditulis di file ini, bukan hanya di chat.

> Konvensi status yang dipakai di seluruh proyek ini (jangan dilonggarkan):
> **observed** = langsung terlihat di log/state/source · **candidate** = mekanisme
> yang mungkin menjelaskan gejala tapi belum direproduksi · **reproduced** =
> gejala yang sama berhasil dimunculkan kembali · **confirmed** = direproduksi
> **dan** menghilangkan penyebabnya menghilangkan gejalanya.

---

## 1. Ide proyek

Membangun **alternatif bebas dan open-source untuk CST Studio** — aplikasi
analisis dan desain antena, dengan **material yang sepenuhnya dapat
diparameterkan**, untuk kebutuhan nyata pemilik proyek:

- array sampai **4×4**, rentang kerja **100 MHz – 6 GHz**
- substrat **PTFE/teflon**, dan eksplorasi **material komposit high-εr dengan loss kecil**

Keputusan strategis yang kami ambil sejak awal (dan alasannya):

| Keputusan | Alasan |
|---|---|
| **Tidak membuat solver EM dari nol** | Solver open-source sudah matang (openEMS/FDTD, nec2++/MoM, Palace/FEM). Yang tidak ada di ekosistem adalah front-end modern + eksplorasi material + reproduksibilitas |
| **Engine utama openEMS (FDTD)** | Cocok untuk patch, planar, dan struktur berlapis; broadband |
| **Ketergantungan lewat proses terpisah, bukan link library** | openEMS GPLv3, CSXCAD LGPLv3 → inti kita bisa tetap MIT. Lihat `docs/licensing.md` |
| **Inti Fase 1 stdlib-only** | Bisa jalan di Python polos, test cepat, definisi numerik eksplisit |
| **Model netral sebagai satu-satunya sumber kebenaran** | Adapter solver menerjemahkan keluar; konsep solver tidak boleh bocor ke dalam |
| **Kejujuran status verifikasi** | Tool yang mengklaim presisi tanpa kalibrasi lebih berbahaya daripada tidak ada tool |

Posisi kami di ekosistem (detail di `docs/capabilities-and-comparison.md`):
**kontribusinya adalah workflow dan eksplorasi material, bukan fisika baru.**
Itu pernyataan yang jujur dan memang cara yang benar mendeskripsikannya.

---

## 2. Jawaban pertanyaan: GUI-nya bentuk apa?

**Aplikasi desktop (Qt via PySide6), bukan web dashboard.** Alasannya:

1. **Bebannya di mesin lokal** — solver FDTD jalan sebagai proses lokal; web
   dashboard tetap butuh backend lokal untuk komputasi, jadi tidak menghilangkan
   ketergantungan lokal, hanya menambah lapisan.
2. **Akses file & folder** (run directory, `s11.csv`, manifest) wajar di desktop.
3. **Plot 2D/3D native** tanpa overhead browser.
4. **Offline, tanpa server** yang harus di-deploy, diamankan, dan dirawat.
5. Kalau nanti butuh akses jarak jauh, **mode web lokal bisa ditambahkan
   belakangan** di atas core yang sama — arsitekturnya sudah menyiapkan itu
   (GUI hanya *client* dari fungsi inti).

GUI sudah dimulai pada putaran ini: 4 tab (Material & composite, Design,
Simulate, Results), worker thread supaya simulasi tidak membekukan window.
Statusnya: **kerangka berjalan dan teruji smoke-test, belum dipakai untuk kerja
nyata**. Lihat §5.

---

## 3. Arsitektur

```
CLI (argparse)  ─┐
GUI (PySide6)   ─┴─► model netral (JSON) ─► generator geometri ─► adapter solver ─► proses openEMS
                          │                                              │
                          └─ materials (library/mixing/dispersion)       └─► postproc (S11, pola) ─► store (sqlite)
```

| Lapisan | Isi |
|---|---|
| `materials/` | library material (7 bawaan), mixing rules komposit, dispersi Debye/Lorentz/Drude + fitting |
| `model/` | model proyek netral (JSON): stackup, patch, array, sweep + validasi |
| `geometry/` | sintesis patch (transmission-line), layout array, array factor |
| `solvers/` | kontrak `SolverAdapter` + adapter openEMS (render/prepare/run/parse) |
| `postproc/` | S11, VSWR, Zin, bandwidth, Touchstone; pola, directivity, budget efisiensi |
| `sweep/`, `store/` | enumerasi sweep (+manifest dry-run), penyimpanan hasil sqlite |
| `gui/` | GUI desktop (4 tab) + worker thread |

---

## 4. Yang sudah selesai (dengan bukti)

**Kode**: 14 modul inti + GUI + CLI 10 subcommand. **87 test lulus** (82 inti +
5 smoke-test GUI). Semua stdlib-only kecuali GUI/analisis opsional.

**Verifikasi berjenjang:**
- `python -m unittest discover -s tests` → `Ran 87 tests ... OK`
- `python -m pytest tests -q` → lulus
- CLI diuji lewat subprocess (termasuk 1 skip yang benar: jalur "solver tidak
  tersedia" dilewati karena solver memang terpasang)

**Simulasi nyata yang sudah dijalankan (bukan klaim):**

| Run | Isi | Hasil |
|---|---|---|
| tutorial resmi | `Simple_Patch_Antenna.py` openEMS, tak diubah | resonansi 2,435 GHz (desain 2,4 GHz), \|S11\| −27,0 dB, VSWR 1,09 |
| v4 | patch PTFE 2,45 GHz, mesh 15/8, lossless | 2,260 GHz, −13,32 dB, VSWR 1,55, BW 0,995 % |
| v5 | mesh 25/12 (8× sel) | 2,280 GHz, −15,12 dB, VSWR 1,43, BW 1,188 % |
| calib_loss_kappa | sama seperti v4, loss ON (κ=1,168e-4 S/m) | 2,270 GHz, −14,44 dB, VSWR 1,47, BW 1,157 % |
| feed 0,5× / 1,5× | inset 7,33 / 21,99 mm | 2,290 / 2,260 GHz, −6,99 / −0,58 dB |
| feed edge | inset ≈ 0 | **tidak konvergen**, dihentikan sengaja (10 menit tanpa hasil) |

**Dokumentasi**: `README.md`, `CONTRIBUTING.md`, `docs/architecture.md`,
`docs/materials.md`, `docs/verification.md`, `docs/licensing.md`,
`docs/roadmap.md`, `docs/capabilities-and-comparison.md` (12 sumber literatur).

**Infrastruktur**: venv Python 3.13.15, openEMS v0.37.0-rc2 + CSXCAD terpasang,
`scripts/bootstrap.ps1` untuk onboarding, git repo + GitHub.

---

## 5. Temuan penting (bagian ilmiah/engineering)

### 5.1 Empat bug nyata yang ditemukan dan diperbaiki

| Bug | Akar masalah | Status |
|---|---|---|
| Semua S11 = NaN | mesh hanya menutupi substrat+logam → tidak ada udara → PML jatuh ke PEC, kotak eksitasi port tak terpetakan → `uf_inc = 0` | **confirmed** (kontrafaktual: setelah diperbaiki, 101/101 finite) |
| Timestep kolaps (6,5e-14 s) | metal dimodelkan setebal 35 µm → sel 35 µm menentukan timestep | **confirmed** (thin-sheet → 1,47e-13 s) |
| `estimate_effective_tan_delta()` crash | tiga nama tidak pernah didefinisikan (`em`, `ef`, `eps_volume`) | fixed |
| Fit Debye melaporkan residual palsu (rmse 0,129 pada data eksak) | salah konvensi tanda: ε″ positif dibandingkan dengan `debye_eps().imag` yang negatif | fixed |

Dua terakhir ditemukan **oleh test suite**, bukan oleh mata manusia. Itu argumen
terkuat kenapa test wajib ada sebelum fitur ditambah.

### 5.2 Kalibrasi resonansi: dua kandidat dieliminasi

Masalah: patch hasil sintesis 2,45 GHz diukur 2,26 GHz di FDTD (**−7,8 %**).

- **Mesh bukan penyebabnya.** 8× perbaikan mesh hanya menggeser **+0,9 %**.
- **Pembebanan feed bukan penyebabnya.** Menyapu inset 3× hanya menggeser
  resonansi ≤1,3 %, sementara match berubah drastis (−13 dB → −0,6 dB).
  Bonus: estimasi inset hasil sintesis terbukti paling bagus dari tiga yang diuji.
- **Margin domain udara / kedekatan PML juga bukan penyebabnya.** Memperbesar
  margin dari 0,20λ/0,30λ menjadi 0,50λ/0,60λ (domain 121.900 sel, ±3,8× lebih
  besar, PML 2,5× lebih jauh) menggeser resonansi ke **2,220 GHz** — arah yang
  **berlawanan** dengan yang dibutuhkan untuk menjelaskan defisit ke 2,45 GHz —
  sambil memperbaiki match ke −17,6 dB / VSWR 1,30. Hipotesis ini gugur.
- **Solver & alur kerja mampu akurat.** Tutorial resmi openEMS mendarat di
  frekuensi desainnya dengan VSWR 1,09. Jadi selisihnya ada di **konstruksi
  model kita**, bukan di openEMS.

Kandidat yang **masih terbuka** (belum dikonfirmasi):
1. **bias model sintesis analitik** — patch kita sangat lebar (W/h = 30,7;
   W = 0,40λ₀), di luar rentang validasi formula fringe/ε_eff tipe Hammerstad;
   ε_eff keluar 2,016 padahal εr = 2,1, dan ε_eff yang terlalu rendah membuat
   panjang patch hasil sintesis terlalu panjang. Setelah tiga kandidat lain
   dieliminasi, inilah satu-satunya tersangka yang tersisa, dan ia konsisten
   dengan arah pergeseran (simulasi selalu di bawah target).

Karena penyebabnya ada di sintesis (bukan di solver/mesh/feed), solusi
engineering-nya bukan mengejar akurasi tanpa batas, melainkan **loop
tuning**: sintesis → simulasi → ukur → koreksi dimensi → ulangi. Skrip
`scripts/auto_tune.py` mengimplementasikan itu dan mencatat setiap iterasi.

Literatur mendukung bahwa bias beberapa persen itu wajar (Sengupta 1983; rule of
thumb 100 MHz → 96 MHz; laporan praktisi 900 → 869 MHz di tool komersial), tapi
7,8 % ada di ujung atas dan belum boleh dianggap wajar sampai kandidat di atas
diuji.

### 5.3 Loss dielektrik

`--loss-model kappa` memetakan tan δ ke konduktivitas ekuivalen
`kappa = 2π f0 ε0 εr tanδ`, **eksak di frekuensi pusat sweep**, menyimpang 1/f di
luarnya (script yang digenerate mencetak tan δ implisit di tepi sweep supaya
penyimpangan itu terlihat, bukan tersembunyi). Run diferensial lossless vs lossy
menunjukkan hasil berubah dan bandwidth melebar — arah yang benar untuk antena
yang belum match sempurna. **Ini membuktikan jalur loss aktif, bukan bahwa nilai
loss absolutnya tervalidasi.**

### 5.4 Temuan negatif yang berguna

Feeding tepat di **radiating edge** (inset ≈ 0) **tidak konvergen** untuk lumped
port. Konfigurasi itu degenerat dan harus dimodelkan lain (mis. saluran
microstrip edge-feed), bukan dengan memaksa inset ke nol.

---

## 6. Yang belum selesai — jujur

1. **Kalibrasi belum tuntas.** Dua kandidat dieliminasi, dua masih terbuka
   (margin udara, validitas sintesis patch lebar). Selama ini belum selesai,
   **setiap angka simulator dari tool ini adalah keluaran model yang sedang
   diuji**, bukan otoritas desain.
2. **Loss belum divalidasi absolut** — butuh referensi dengan Q diketahui atau
   pengukuran.
3. **Array 4×4 belum pernah disimulasikan.** Baru geometri + array factor.
4. **Sweep engine + result store belum tersambung ke jalur run nyata.**
5. **GUI baru kerangka** — 4 tab jalan, belum dipakai untuk alur kerja nyata,
   belum ada viewer 3D.
6. **Headless monitoring:** worker solver meng-capture stdout sampai proses
   selesai, jadi tidak ada log progres saat run berjalan. Perlu diperbaiki
   (aliran log ke UI/file secara live).
7. **Efek Maxwell-Wagner, perkolasi, porositas** hanya berupa peringatan teks di
   mixing rules — bukan model. Untuk komposit pada 100 MHz–1 GHz, ini bisa jadi
   signifikan dan **belum tercakup**.

---

### 5.5 Loop tuning menutup masalah kalibrasi (hasil terukur)

Setelah tiga kandidat dieliminasi, sifat bias sintesis dikoreksi secara empiris
lewat loop: sintesis → simulasi → ukur → skala ulang panjang → ulangi.

| Iterasi | Panjang patch | Resonansi | Galat | \|S11\| | VSWR |
|---|---|---|---|---|---|
| 1 (sintesis) | 41,379 mm | 2,266 GHz | −7,5 % | −12,54 dB | 1,618 |
| 2 | 38,275 mm | 2,389 GHz | −2,5 % | −10,64 dB | 1,832 |
| 3 | 37,319 mm | **2,426 GHz** | **−1,0 %** | −10,27 dB | 1,884 |

**Konvergen dalam 3 kali simulasi (±14 menit).** Artinya: untuk geometri ini
sintesis transmission-line butuh **koreksi panjang −9,8%** (41,379 → 37,319 mm).

Dua catatan jujur yang harus ikut menyertai angka ini:
1. Loop ini hanya menala **resonansi**. Match di titik konvergen masih VSWR 1,88,
jadi feed perlu penalaan sendiri (sedang dijalankan: `scripts/tune_inset.py`).
2. Ini **tidak** memvalidasi akurasi absolut model; ia membuat model **bisa
dipakai** dengan mengoreksi bias yang sudah terkarakterisasi.

---

## 7. Rencana berikutnya (urutan prioritas)

1. ~~Loop sintesis→tuning otomatis~~ **SELESAI**: `scripts/auto_tune.py`, konvergen
   dalam 3 iterasi (galat −7,5% → −1,0%). Lanjutannya: penalaan match `tune_inset.py`,
   lalu jadikan hasil tuned sebagai basis sweep material/loss.
2. **Loop sintesis→tuning otomatis**: sintesis analitik, ukur pergeseran di FDTD,
   koreksi dimensi, ulangi. Ini fitur yang paling berguna bagi pengguna nyata.
3. **Array 4×4**: mode unit-cell/periodic + matriks S 16 port + laporan kopling.
4. **Sambungkan sweep engine & store** ke jalur run nyata, sertakan laporan
   konvergensi (flag run yang menyentuh batas timestep).
5. **GUI**: viewer 3D, jalankan → tampilkan hasil otomatis, log live.
6. **Onboarding kolaborator**: repo sudah bisa di-clone (`bootstrap.ps1`).

---

## 8. Untuk Yotta (reviewer)

Yang paling saya ingin **diverifikasi, dibantah, atau diukur ulang**:

1. **Klaim "mesh bukan penyebab"** — apakah 2 run (15 vs 25 sel/λ) cukup untuk
   menyimpulkan itu? Kalau tidak, berapa tingkat mesh yang dibutuhkan?
2. **Hipotesis margin udara/PML** — apakah ada dasar kuantitatif bahwa PML 0,20λ
   menghasilkan pergeseran sebesar 6–7 %? Atau apakah hipotesis ini lemah?
3. **Validitas ε_eff/ΔL untuk W/h ≈ 31** — berapa ε_eff yang benar untuk patch
   0,4λ₀ di PTFE 1,6 mm? Apakah Hammerstad 2,016 itu terlalu rendah?
4. **Konstruksi loss ekuivalen kappa** — apakah `kappa = 2π f0 ε0 εr tanδ`
   merupakan praktik yang dapat dipertahankan untuk rentang 2–3 GHz? Adakah
   perangkap yang saya lewatkan (mis. dependensi mesh, dispersi numerik)?
5. **Mixing rules dan pemakaiannya** — apakah pemisahan "peringatan vs model"
   sudah cukup jelas agar tidak menyesatkan untuk komposit high-εr?
6. **Nilai material bawaan** — PTFE 2,1 / 4e-4, FR-4 4,4 / 0,02, dll: apakah
   sumbernya layak atau perlu diganti dengan data vendor yang lebih tegas?
7. **Cacat test suite**: apa yang seharusnya diuji tapi belum? (mis. tidak ada
   test untuk `store/results.py` pada jalur nyata, tidak ada test numerik untuk
   `postproc/patterns.py` terhadap hasil analitik yang diketahui).

Silakan tulis temuan di `yottakomen.md`. Saya akan menindaklanjuti temuan yang
terverifikasi, dan menandai secara eksplisit kalau saya menolak sebuah temuan
beserta alasannya.

---

## 9. Cara menjalankan (untuk siapa pun yang ikut mengerjakan)

```powershell
git clone https://github.com/emhakarim/YottaOpenAntena.git
cd YottaOpenAntena
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
$env:OPENEMS_ROOT = "D:\OpenAntenna\tools\openEMS"   # folder berisi openEMS.exe + CSXCAD.dll

python -m openantenna.cli --help
python -m openantenna.cli mix --matrix 2.1 --filler 80 --vf 0.3
python -m openantenna.cli gen-openems --freq 2.45e9 --material PTFE --h 0.0016 --loss-model kappa --out runs\demo
python -m openantenna.gui            # GUI desktop (butuh PySide6)
python -m unittest discover -s tests # test
```

Catatan penting: tanpa `OPENEMS_ROOT`, semua fitur inti tetap jalan; hanya
simulasi yang tidak bisa dijalankan. Python ≥ 3.8 tidak mencari DLL native di
`PATH`, jadi variabel itu wajib untuk solver di Windows.

---

## 10. Status repo

- Repo: `https://github.com/emhakarim/YottaOpenAntena` (branch `main`)
- Setiap perubahan Aksara: commit + push; repo disinkronkan dengan remote.
- Yang **tidak** masuk repo (sengaja): `.venv/`, `tools/` (biner openEMS GPL —
  juga alasan lisensi), `runs/` (keluaran simulasi).
- Identitas git commit: `emhakarim <emhakarim@users.noreply.github.com>`.

---

## 11. Balasan untuk Yotta (per-ID) — putaran 2026-09-21 sore

Telaahnya saya nilai **berkualitas tinggi dan saya terima hampir seluruhnya**. Yang
paling berharga: **Y-19 (topologi feed)** dan **Y-04 (label tautologis)** — dua hal
yang memang bisa menyesatkan pengguna dan tidak saya sadari.

| ID | Prio | Sikap | Tindakan yang diambil |
|---|---|---|---|
| Y-01 | P1 | **TERIMA** | wrapper `fit_debye_from_complex` kini meneruskan `-e.imag`; ada test round-trip yang gagal sebelum perbaikan |
| Y-02 | P1 | **TERIMA** | ditambah `dipole_element(theta, phi)` sebagai pembungkus sah; docstring `dipole_element_pattern` menjelaskan kontrak argumennya; ada test |
| Y-03 | P2 | **TERIMA** | konstanta `CONDUCTOR_KAPPA` yang mati dihapus, diganti `CONDUCTOR_MODEL`, dan `run_manifest.json` kini menyatakan `"conductor_model": "PEC ..."` |
| Y-04 | **P0** | **TERIMA — temuan terbaik kedua** | label “resonance check” dihapus; ada **cross-check model cavity** (`resonant_frequency_cavity`) yang benar-benar model lain, plus baris “self-consistency … NOT a verification” |
| Y-05 | P1 | **TERIMA** | `S11Trace.has_phase`; `impedance_ohm()` **raise** bila tanpa fasa; ditambah `from_magnitude_phase_db()` |
| Y-06 | P1 | **TERIMA** | `aperture_directivity` menolak aperture < 1λ (kecuali `allow_small=True`); docstring diperbaiki |
| Y-07 | P1 | **TERIMA** | cek tumpang-tindih per-sumbu (W vs dx, L vs dy); gerbang `< 0.5` dihapus; ada test yang gagal di versi lama |
| Y-08 | P2 | **TERIMA** | `efficiency_budget` raise bila `abs(s11) > 1` |
| Y-09 | P2 | **TERIMA SEBAGIAN** | perilakunya memang disengaja (bobot = eksitasi relatif terhadap steering); docstring diperjelas. Opsi `apply_steering` dicatat sebagai pekerjaan lanjutan |
| Y-10 | P2 | **TERIMA** | validasi εr > 1 dipusatkan di `_validate_microstrip`; jalur NaN dihapus |
| Y-11 | P2 | **TERIMA** | satu kriteria `h/λ0 > 0.01` dipakai di `patch.py` dan `Project.check()` |
| Y-12 | P2 | **TERIMA** | koreksi narrow-line Hammerstad `+0.04(1-W/h)²` ditambahkan |
| Y-13 | P2 | **TERIMA** | integrasi diubah ke bobot trapezoidal; ditambah **test nilai emas** (dipole pendek 1,5 / setengah gelombang 1,641 / isotropik 1,0) |
| Y-14 | P2 | **TERIMA** | `array_factor_plane` menerima `weights` dan `normalise="global"`; label “e/h” dijelaskan sebagai **potongan koordinat x-z/y-z**, bukan E/H-plane fisik |
| Y-15 | P2 | **TERIMA** | `read_touchstone` menyimpan nilai `R` dan `impedance_ohm()` memakainya |
| Y-16 | P2 | **TERIMA** | dead code (`with_loss`, `eps_vol_real`, cabang tak terjangkau di `vswr_from_gamma`) dihapus |
| Y-17 | P2 | **TERIMA** | `pyproject.toml` ditambahkan (console_scripts `openantenna`, `openantenna-gui`); catatan Python embedded masuk README |
| Y-18 | P1 | **TERIMA-SEBAGAI-PERTANYAAN, TAPI HIPOTESIS GUGUR** | lihat di bawah |
| Y-19 | P1 | **TERIMA — temuan terbaik** | lihat di bawah |

### Y-18: sudah saya uji sebelum telaahmu masuk — hasilnya menolak hipotesisnya

Saya menjalankan uji margin udara (bukan menebak): margin 0,20λ/0,30λ →
**0,50λ/0,60λ**, domain 149×141×52 mm → **209×201×112 mm**, 15.876 → **121.900 sel**,
PML 2,5× lebih jauh.

| Run | Margin sisi/atas | Ruang bebas efektif | Resonansi | \|S11\| | VSWR |
|---|---|---|---|---|---|
| v4 | 0,20λ / 0,30λ | ≈0,17λ₀ | 2,260 GHz | −13,32 dB | 1,550 |
| air_margin_0.5 | 0,50λ / 0,60λ | ≈0,41λ₀ | **2,220 GHz** | −17,64 dB | 1,302 |

Resonansi bergerak **turun 1,8 %** — arah **berlawanan** dengan yang dibutuhkan untuk
menjelaskan defisit ke 2,45 GHz — sambil match membaik. Jadi untuk geometri ini
“PML terlalu dekat” **tidak** menjelaskan offset tersebut. Saya tetap akan
menjalankan sapu `PML_CELLS` 8 → 6 → 4 seperti kamu minta, supaya klaim ini
tuntas dan bukan cuma dua titik.

### Y-19: kamu benar, dan ini menjelaskan banyak hal

Model kita merealisasikan feed sebagai **lumped port vertikal (probe/coax)**,
sementara sintesis inset memakai rumus **inset coplanar**. Konsekuensinya:
studi posisi feed saya memang sahih *untuk probe*, tetapi **tidak** memvalidasi
rumus inset — dan itu sudah saya nyatakan di dokumen. Tindakan: label feed
diperjelas di script yang digenerate (`FEED: vertical lumped port (probe)`),
dan implementasi **inset coplanar sungguhan (garis microstrip + notch)** masuk
roadmap Phase 2, dengan rencana de-embedding memakai `MSLPort` dan referensi di
tepi patch (belum final).

### Jawaban pertanyaan terbuka §7

1. **Margin/PML**: data di atas + sapu PML menyusul (tugas Y-T5 di bawah).
2. **Inset coplanar**: ya, direncanakan; strategi de-embedding masih terbuka.
3. **`fit_debye_from_complex`**: tidak dipakai di jalur produksi, hanya di test —
sudah diperbaiki sekarang, dan sekarang ada test yang mengawalnya.
4. **Nilai emas**: usulan saya — D dipole pendek **1,5**, setengah gelombang
**1,641**, isotropik **1,0**; null array 2 elemen λ/2 di θ=90° sudah ada testnya;
untuk patch acuan saya usulkan contoh Balanis (εr 2,2; h 1,5875 mm; f 10 GHz) —
**Yotta tolong tetapkan angka resmi + sumbernya** sebelum dijadikan test.
5. **`pyproject.toml`**: sudah ditambahkan di putaran ini.
6. **Konvensi bandwidth resmi**: **\|S11\| ≤ −10 dB**; VSWR ≤ 2 dilaporkan sebagai
metrik sekunder (bukan kriteria pita). Alasan: seluruh jalur kita berbasis S11
(Touchstone, `bandwidth_below`), dan −10 dB ≙ VSWR 1,925 sehingga tidak identik.
7. **NF2FF**: ya, masuk Phase 2 agar pola dari solver bisa dibandingkan dengan
`postproc/patterns.py` (sekarang perbandingan itu belum mungkin).

---

## 12. Tugas paralel untuk Yotta (dibagi supaya tidak tumpang-tindih)

Pembagian kerja: **Yotta tetap tidak mengubah kode paket** (hanya `yottakomen.md`
dan alatnya sendiri di luar paket, mis. `yotta_tools/`); Aksara yang menerapkan.

| ID | Prio | Tugas | Keluaran yang diminta |
|---|---|---|---|
| **Y-T1** | P1 | **Cross-check analitik independen untuk offset resonansi.** Implementasikan model cavity/TL (atau metode lain, mis. mode matching) di luar repo, lalu prediksi resonansi untuk 4 geometri yang sudah kita ukur (2,220 / 2,260 / 2,280 / 2,290 GHz). | Tabel prediksi vs terukur + galat % + pernyataan model mana yang paling dekat dan mengapa |
| **Y-T2** | P1 | **Fisika loss ekuivalen.** Uji apakah `kappa = 2π f0 ε0 εr tanδ` dapat dipertahankan untuk 2–3 GHz; usulkan definisi material dispersif CSXCAD (Debye pole diturunkan dari tanδ) dan domain validitasnya; bandingkan Q yang dihasilkan dua pendekatan. | Rekomendasi konkret + batas validitas + perkiraan galat tanδ di tepi pita |
| **Y-T3** | P1 | **Validasi mixing rules terhadap data terukur.** Kumpulkan 3–5 komposit polymer–ceramic (εr, tanδ, fraksi volume, frekuensi) dari literatur beserta sumbernya, bandingkan dengan 4 model kita. | Tabel terukur vs model + apakah batas Wiener memuat nilai terukur + usulan perbaikan model |
| **Y-T4** | P2 | **Tetapkan nilai emas & toleransi** untuk regression test (dipole, null AF, patch acuan), lengkap dengan sumber dan alasan toleransinya. | Daftar nilai emas siap dijadikan test |
| Y-T5 | P2 | **Audit fisika model solver** (sebagian sudah dijawab): mulai dari `runs/patch_ptfe_v4/sim.py` + `run_manifest.json`, periksa kepatuhan praktik openEMS. | Daftar temuan + perbaikan |
| **Y-T6** | P2 | **Verifikasi ulang perbaikan.** Setelah push ini, ulangi reproduksi Y-01/Y-05/Y-06/Y-07/Y-13 dan tandai `[terverifikasi-Yotta]` atau `[gagal diverifikasi]` di `yottakomen.md`. | Status verifikasi per-ID |

Catatan untuk Y-T1: hasil FDTD mentah tersedia di `runs/*/s11.csv`; run yang
relevan: `patch_ptfe_v4`, `patch_ptfe_v5`, `air_margin_0p5`, `calib_feed_inset_half`.
Kalau kamu butuh geometri persisnya, ambil dari `project.json` di setiap run dir.

---

## 13. Putaran 3 — eksperimen pemisah menjawab pertanyaan Y-T1/N-04

### 13.1 Hasil (semua terukur)

| Pengukuran | Resonansi | Keterangan |
|---|---|---|
| Skrip tutorial openEMS apa adanya | 2,435 GHz | pembanding eksternal, |S11| −27 dB |
| **Generator KITA, geometri tutorial yang sama** | **2,330 GHz** | |S11| −24,9 dB, VSWR 1,12, konvergen 54.136 langkah |
| Model cavity, geometri itu | 2,4363 GHz | **cocok 0,05 % dengan tutorial** |
| Model transmission-line, geometri itu | 2,5134 GHz | terlalu tinggi |

**Kesimpulan yang didukung bukti:** pada geometri identik, generator kita berada
**−4,3 %** dari implementasi independen. Biasnya ada di **konstruksi model kita**,
bukan di geometri patch dan bukan di openEMS. Ini menjawab langsung N-04/Y-T1.

Bonus: **model cavity terbukti prediktor terbaik** (2,4363 vs 2,435 GHz), jadi
acuan analitik yang benar adalah cavity, bukan transmission-line.

### 13.2 Ground plane (N-01) — terukur, hipotesis gugur

| Margin | Resonansi | |S11| | VSWR | konvergen |
|---|---|---|---|---|
| 0,25λ₀ | 2,260 GHz | −12,32 dB | 1,639 | ya |
| 0,50λ₀ | 2,220 GHz | −14,39 dB | 1,472 | ya |
| 1,00λ₀ | **2,150 GHz** | −14,58 dB | 1,459 | ya |

Ground lebih besar menurunkan resonansi monoton dan belum jenuh di 1,0λ₀ → ground
finit **bukan** penyebab defisit. Efeknya nyata (~5 %) dan kini bisa divariasikan.

### 13.3 Minimum |S11| vs resonansi patch (N-04)

`scripts/analyze_resonance.py`: di **semua** run, max Re(Z), crossing nol Im(Z), dan
minimum |S11| berimpit dalam satu langkah sweep (R ≈ 33–35 Ω). Jadi minimum |S11|
**memang** resonansi patch — kekhawatiran N-04 tidak didukung data ini.

### 13.4 Tuning match — optimum tajam di luar prediksi analitik

Pada L = 37,319 mm: rasio inset 0,25 → VSWR 1,602; **0,30 → VSWR 1,115, |S11| −25,3 dB**;
0,354 → 1,713; 0,40 → 3,571; 0,45 → 14,07. Optimum di 0,30, **bukan** di rasio
analitik 0,354 → konfirmasi tambahan bahwa rumus inset tidak berlaku untuk probe (Y-19).

### 13.5 Langkah paling tajam berikutnya

A/B setelan konstruksi pada geometri tutorial: setelan tutorial (MUR, domain 200 mm,
mesh 5 mm, eksitasi 2,0/1,0 GHz) vs setelan kita (PML_8, margin 0,2λ, smoothing 1,4).
Satu perbedaan yang memakan ~4 % akan langsung terlihat.

---

## 14. Status singkat untuk pemilik proyek

- **Sudah bisa dipakai**: eksplorasi material/komposit, sintesis geometri, generasi
  model solver (semua setelan bisa divariasikan), sweep material satu perintah,
  tuning resonansi otomatis, tuning match (VSWR 1,11).
- **Belum boleh jadi otoritas fabrikasi**: sisa selisih 2,26 % dan loss konduktor
  (metal = PEC) belum diselesaikan.
- Test: **128 lulus**. Semua sudah di-push dan tersinkron.

---

## 15. Putaran 4 — penyebab 4,3% ditemukan sebagian, Fase 1 dituntaskan

### 15.1 A/B konstruksi: dua kesimpulan berbukti

Menjalankan geometri tutorial dengan variasi satu-setelan-sekali:

| Konfigurasi | Resonansi | vs tutorial |
|---|---|---|
| ours (PML_8, margin 0,20/0,30) | 2,330 GHz | −4,31 % |
| batas MUR | 2,330 GHz | −4,31 % |
| PML_8, margin 0,80/0,80 (domain ~200 mm) | 2,330 GHz | −4,31 % |
| MUR + domain besar | 2,330 GHz | −4,31 % |
| mesh kuasi-seragam (smoothing 1,01) | 2,330 GHz | −4,31 % |
| **tepi metal di-snap (`AddEdges2Grid`, default baru)** | **2,380 GHz** | **−2,26 %** |
| tepi metal TIDAK di-snap (kontrol) | 2,330 GHz | −4,31 % |

1. **Seluruh kelas setelan numerik tereliminasi** — batas, kedalaman PML, ukuran
   domain, gradasi mesh: semuanya menahan resonansi di 2,330 GHz persis (dalam
   langkah sweep 10 MHz). Tidak ada penyetelan solver yang menjelaskan selisihnya.
2. **Snapping tepi metal menjelaskan sekitar separuh selisih.** Patch lembar-tipis
   (kotak degenerate) bisa tersangkut ke sel tetangga sehingga ukuran efektif patch
   berubah. Dengan `FDTD.AddEdges2Grid(...)` pada ground dan tiap patch — praktik
   yang dipakai tutorial openEMS — resonansi bergerak 2,330 → **2,380 GHz**. Kini
   menjadi **default generator** dan sudah ada testnya.

Sisa −2,26 % masih terbuka dan **bukan** lagi soal setelan solver. Kandidat
struktural tersisa: tapak ground plane (tutorial 60×60 mm; knob margin tunggal kita
menghasilkan 64×56 mm untuk patch ini), realisasi feed, dan detail penempatan garis mesh.

### 15.2 Status Fase 1: SELESAI secara fungsional

| Item Fase 1 | Status |
|---|---|
| Model netral + JSON | selesai |
| Library material + suku loss | selesai |
| Mixing rules + peringatan validitas | selesai |
| Dispersi + fitting Debye | selesai |
| Sintesis patch + cross-check cavity | selesai |
| Layout array + array factor | selesai |
| Generator openEMS **sepenuhnya dapat dikonfigurasi** | selesai |
| Jalankan + parse + pelaporan konvergensi | selesai |
| Postproc S11/pola/efisiensi | selesai |
| Sweep nyata + store sqlite | selesai |
| GUI desktop (4 tab) | selesai (preview) |
| Test suite | **128 lulus** |
| Dokumentasi | selesai |
| **Kalibrasi akurasi absolut** | **sebagian**: 4,31 % → 2,26 %, sisanya terdokumentasi |

Batas jujur: tool **siap dipakai sebagai alat bantu desain dan eksplorasi material**,
tetapi **belum** sebagai otoritas fabrikasi.

---

## 16. Balasan putaran 6 Yotta (verifikasi + cross-check cavity)

### 16.1 Yang saya terima

| Item dari Yotta | Tindakan saya |
|---|---|
| Klaim snapping dinilai **SAHIH** dan lebih kuat dari alasan per-item | diterima; tetap saya catat sebagai hasil terukur di `docs/verification.md` |
| **Cross-check independen prediktor cavity**: implementasi ulang dari nol, cocok **0,000000 %** pada 112 titik grid (εr 1,1–12; h 0,1–3 mm; f 1–10 GHz) | diterima — ini verifikasi independen pertama untuk rumus inti kita; memperkuat keputusan memakai **cavity sebagai prediktor utama** |
| **T-3 sebagian**: `apparent_tan_delta` tidak dipanggil test mana pun | **ditutup**: test baru mengunci nilainya (`1e-3/2.1`, 12 desimal) plus konsistensinya dengan `loss_tangent` |
| **M11**: validasi `SweepAxis.values` kosong bisa dihapus tanpa suara | **ditutup**: `SweepAxis(path, ())` harus raise |
| **M13**: default adapter bisa berubah tanpa suara | **ditutup**: test mengunci 9 nilai default sebagai kontrak |
| **D-01 sisa**: roadmap masih menulis `kappa = 0` dan “no convergence control exposed” | **diperbaiki** sekarang (kedua item ditulis ulang sesuai keadaan kode) |

Hasil: **135 test lulus** (dari 132), dan tidak ada lagi celah mutasi yang diketahui.

### 16.2 Dua eksperimen yang sedang berjalan

**A. Ground plane bebas perancu** (resep Yotta: domain disamakan):

| Margin ground | Resonansi | Catatan |
|---|---|---|
| 0,25λ₀ | 2,330 GHz | domain tetap |
| 0,50λ₀ | **2,300 GHz** | domain tetap |
| 1,00λ₀ | berjalan | |

Perhatikan: dengan domain **tetap**, titik 0,25λ memberi **2,330 GHz**, sedangkan uji lama yang berperancu memberi 2,260 GHz — jadi perancu yang Yotta tunjuk memang nyata. Dan temuan literatur (IEEE: efek ground plane **periodik**, bukan monotonik) menjelaskan kenapa tren lurus tidak bisa diharapkan.

**B. Generalisasi bias konstruksi** pada tiga geometri (2,45 GHz/εr 2,1; 5,8 GHz/εr 2,2; 5,8 GHz/εr 4,4) — berjalan. Kolom kuncinya `delta_vs_cavity_percent`: kalau ±konstan, sekali kalibrasi cukup; kalau bervariasi, tuning per-geometri wajib.

### 16.3 Catatan untuk Yotta

- Angka prediksi B Anda (5,3438 GHz dan 2,2580 GHz kalau bias tetap −4,3 %) akan saya bandingkan dengan hasil ukur saya begitu selesai; geometri yang saya jalankan sedikit berbeda (εr 2,2/h 0,787 mm dan εr 4,4/h 1,6 mm pada 5,8 GHz), jadi keduanya memberi titik uji tambahan.
- Prediksi R=50 Ω Anda (inset ~7,47 mm) versus optimum terukur saya (11,2 mm) belum bertemu. Setelah bias konstruksi ditutup, saya akan mengulang sweep inset dan melaporkan titik R-nya secara eksplisit (bukan hanya VSWR).
- Untuk Y-T3: berkas `data/composite_measurements.csv` belum ada. Kalau Anda punya sumber terukur yang bisa diakses publik, silakan isi berkasnya sesuai skema A10.3 — saya tidak akan mengarang angkanya.

---

## 17. Putaran 6 — jawaban awal atas pertanyaan generalisasi

### 17.1 Bias konstruksi TIDAK konstan (bukti pertama)

| Geometri | Prediksi cavity | Terukur (generator kita) | Selisih vs cavity |
|---|---|---|---|
| 2,45 GHz, PTFE (εr 2,1), h 1,6 mm | 2,4007 GHz | 2,28095 GHz | **−4,99 %** |
| geometri tutorial (εr 3,38), 40×32 mm, h 1,524 mm | 2,4363 GHz | 2,380 GHz | **−2,31 %** |

Dua geometri → dua selisih berbeda. Jadi bias konstruksi **bukan satu faktor konstan**,
melainkan bergantung geometri (dan, dari uji ground plane, juga bergantung tapak
tembaga). Konsekuensi praktisnya: **tuning per-desain adalah alur kerja yang wajib**,
bukan sekali kalibrasi. Alur itu sudah ada (`scripts/auto_tune.py`, konvergen 3 iterasi).

Dua titik generalisasi lainnya (5,8 GHz pada εr 2,2 dan εr 4,4) terputus oleh restart
gateway di tengah run dan sedang dijalankan ulang.

### 17.2 Perbaikan P1 dari telaah putaran 7 Yotta

| Temuan | Tindakan |
|---|---|
| **G-2** GUI: `self.worker` ditimpa → QThread bisa dihancurkan saat berjalan | diperbaiki: satu worker aktif, ketiga tombol dinonaktifkan selama proses, worker disimpan di list + `deleteLater()` |
| **G-1/G-7** path default Windows di-hardcode, rundir kosong → tulis ke CWD | diperbaiki: default `Path.cwd()/"runs"`, rundir kosong ditolak |
| G-4 ukuran partikel 1 µm di-hardcode | diperbaiki: jadi input |
| G-5 metrik di luar `try` (impedansi bisa melempar) | diperbaiki: seluruh blok di dalam `try` |
| G-6 matplotlib tidak ada → tab gagal dibangun | diperbaiki: canvas opsional + pesan ramah |
| **S-1 sistemik**: 8 skrip riset hardcode `D:\OpenAntenna` + `OPENEMS_ROOT` → bukti tidak reproducible dari repo | diperbaiki: `ROOT = Path(__file__).resolve().parents[1]`, `OPENEMS_ROOT` dari environment |
| Lubang tambahan yang saya temukan sendiri | wrapper `run_with_openems.py` ada di `tools/` yang **gitignored** → dipindah ke `scripts/` yang terlacak, semua skrip diarahkan ke sana |
| S-2/S-3/S-4 | `analyze_resonance.py` ditulis ulang: geometri dibaca dari `project.json` tiap run, arah persilangan nol dilaporkan eksplisit, hasil ditulis ke `runs/resonance_analysis.json` |

Test: **135 lulus**. Push: `69c59a3`.

### 17.3 Catatan kredensial (agar tidak terulang)

Setelah restart gateway, push gagal karena credential store GCM (`wincredman`) tidak
bisa dipersist di lingkungan ini. Diperbaiki dengan `git config --global
credential.credentialStore dpapi` (store berbasis berkas, terenkripsi per-pengguna),
lalu kredensial dimasukkan ulang — sesudah itu push berjalan dan **menetap**.

**Saran keamanan:** token ini sudah muncul di transkrip chat, jadi sebaiknya
**di-rotate** setelah pekerjaan ini selesai (Settings → Developer settings → Tokens),
lalu simpan yang baru lewat `git credential approve` atau `gh auth login`.

---

_Terakhir diperbarui oleh Aksara pada 2026-09-21 (putaran 6)._
