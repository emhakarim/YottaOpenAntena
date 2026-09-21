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

## 7. Rencana berikutnya (urutan prioritas)

1. **Loop sintesis→tuning otomatis** (`scripts/auto_tune.py`): sintesis
   analitik, ukur pergeseran di FDTD, koreksi dimensi, ulangi sampai toleransi.
   Ini jawaban engineering untuk bias sintesis yang sudah terlokalisasi.
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

_Terakhir diperbarui oleh Aksara pada 2026-09-21._
