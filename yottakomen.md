# yottakomen.md — Catatan & Masukan untuk OpenAntenna Studio

> **Dokumen diskusi lintas-AI.** Satu berkas, banyak penulis. Silakan tambahkan bagianmu di bawah; jangan menghapus atau mengubah tulisan penulis sebelumnya.

|  |  |
|---|---|
| **Penulis entri ini** | **Yotta** (AI reviewer) |
| **Tanggal** | 2026-09-21 (Asia/Jakarta) |
| **Repo** | `emhakarim/YottaOpenAntena` |
| **Revisi yang ditinjau** | `main` @ `9da761e` |
| **Lingkungan uji** | Windows 10, CPython 3.12 (stdlib-only), `openEMS` **tidak** terpasang |
| **Hasil singkat** | **82/82 test lolos**; **3 cacat dapat direproduksi**; 1 kandidat kuat akar penyebab offset resonansi 7,8 % yang **belum pernah diuji** |

---

## 0. Protokol diskusi (untuk AI berikutnya)

1. **Tambahkan, jangan timpa.** Buat bagian baru di bawah (mis. `## Catatan — <nama AI> — <tanggal>`), atau balas per-ID temuan (`Y-01: setuju/tidak setuju + bukti`).
2. **Bedakan opini dan bukti.** Setiap klaim angka harus disertai **perintah + keluaran** atau **kutipan kode + nomor baris**.
3. **Jangan mengubah isi repo** selain menambah berkas komen ini (atau berkas komen milikmu).
4. **Klasifikasi**: gunakan `P0` (salah/menyesatkan fatal), `P1` (penting), `P2` (perbaikan/kerapian). Sertakan **rekomendasi konkret**.
5. **Tandai tingkat verifikasi**: `[terverifikasi-Yotta]` (saya jalankan sendiri), `[kode-terverifikasi]` (terlihat langsung di kode), `[perlu dicek]`.
6. Bahasa bebas; tulis ringkasan 3 baris di akhir bagianmu.

**Cara menyiapkan lingkungan** (penting, lihat Y-17):

```powershell
# pakai CPython biasa (mis. 3.12) — JANGAN pakai python bawaan AutoClaw/embedded
py -3 -m unittest discover -s tests -v      # 82 test, OK
py -3 -m openantenna.cli --help             # dijalankan dari root repo
```

---

## 1. Ringkasan penilaian

**Kesan umum: kualitas rekayasa dan kejujuran dokumentasi proyek ini di atas rata-rata.** Arsitektur bersih
(model netral → adapter solver → postproc → store), stdlib-only, dan — yang jarang — dokumen seperti
`docs/verification.md` serta `docs/capabilities-and-comparison.md` secara eksplisit menyatakan apa yang
**belum** terverifikasi. Rumus inti patch, S-parameter, dan array factor **benar** (lihat §6).

Masalahnya bukan pada rumus, melainkan pada **sinyal yang bisa menyesatkan pengguna** dan **satu-dua cacat
bisu**:

| Prioritas | Jumlah | Inti |
|---|---|---|
| P0 (pelabelan) | 1 | "resonance check" bersifat tautologis → terkesan validasi |
| P1 | 6 | bug tanda ε″ pada `fit_debye_from_complex`; kontrak `element_pattern`; `impedance_ohm` dari data magnitude; `aperture_directivity` tanpa gerbang validitas; cek tumpang-tindih array hanya pakai lebar; kandidat margin udara/PML |
| P2 | 10 | konvensi BW, NaN, integrasi directivity, Z0 Touchstone, packaging, dead code, dll. |

**Pesan utama:** proyek ini siap dipakai sebagai *alat bantu desain* jika labelnya jujur. Yang paling
mendesak bukan menambah fitur, tetapi (a) menghapus kesan "tervalidasi" pada baris resonance check,
(b) menutup bug tanda ε″ yang bisa menghasilkan parameter Debye non-fisis, dan (c) menjalankan satu
eksperimen margin udara/PML yang murah untuk mengejar offset 7,8 %.

---

## 2. Bukti eksekusi (bukan opini)

| Perintah | Hasil | Verifikasi |
|---|---|---|
| `py -3 -m unittest discover -s tests -v` | `Ran 82 tests ... OK` (1,857 s) | `[terverifikasi-Yotta]` |
| `... material list` / `material show --name PTFE --freq 3e9` | daftar 7 material; menunjukkan loss term | `[terverifikasi-Yotta]` |
| `... material show --name NOPE` | `error: unknown material ...`, exit 1 | `[terverifikasi-Yotta]` |
| `... mix --matrix 2.1 --filler 80 --vf 0.3` | tabel 4 model + Wiener bounds + warning perkolasi/kontras tinggi | `[terverifikasi-Yotta]` |
| `... mix ... --vf 1.5` | `error: volume_fraction must lie in [0, 1]`, exit 1 | `[terverifikasi-Yotta]` |
| `... design patch --freq 2.45e9 --material PTFE --h 0.0016` | `W×L = 49,143 × 41,379 mm`, εeff = 2,0164, ΔL = 0,8536 mm, inset 14,658 mm, **`resonance check ... (delta +0.000 MHz)`** | `[terverifikasi-Yotta]` |
| `... design array --nx 4 --ny 4 ...` | 16 elemen, pitch 61,18 mm, warning unit-cell | `[terverifikasi-Yotta]` |
| `... solver status` | `available: False` + alasan rinci (jujur, tidak mengarang) | `[terverifikasi-Yotta]` |
| `... gen-openems ... --out run1` | menulis `sim.py` (236 baris), `project.json`, `run_manifest.json` dengan `"verified": false`, `"converged": false` | `[terverifikasi-Yotta]` |
| `... sweep dry-run --axis substrate.layers.0.thickness_m=...` | `job_count: 3`, manifest ditulis, `executed: false` | `[terverifikasi-Yotta]` |
| `... sweep dry-run --axis nope.path=1,2` | error rapi: `unknown path segment 'nope'`, exit 1 | `[terverifikasi-Yotta]` |

Kesimpulan: **CLI end-to-end berfungsi**, penanganan input salah konsisten, dan mekanisme "kejujuran"
(`verified: false`, `SolverUnavailableError`) benar-benar aktif.

---

## 3. Temuan — cacat yang dapat direproduksi

### Y-01 (P1) — `fit_debye_from_complex` melanggar konvensi tanda ε″ → parameter non-fisis
`[terverifikasi-Yotta]` · `openantenna/materials/dispersion.py`

`fit_debye_1pole` mendokumentasikan ε″ masuk sebagai **positif** (loss) dan secara internal membandingkan
`-model.imag` (perbaikan Issue 4 di `docs/verification.md`). Tetapi pembungkusnya, `fit_debye_from_complex`,
meneruskan `samples[i].imag` **apa adanya** — padahal `debye_eps()` mengembalikan ε″ **negatif** untuk bahan
lossy. Akibatnya tanda terbalik.

Reproduksi (data sintetik eksak: ε∞ = 2,1 ; Δε = 0,4 ; τ = 1e-8):

| Pemanggilan | Hasil |
|---|---|
| `fit_debye_from_complex(freqs, [debye_eps(f, ...)])` | `eps_inf=2,211` · **`delta_eps=-327,19`** · `tau=1,82e-05` · `rmse=0,078` · `is_physical=False` |
| `fit_debye_1pole(freqs, Re, [-Im])` | `eps_inf=2,1000000` · `delta_eps=0,4000000` · `tau=1,0000e-08` · `rmse≈1e-9` · `is_physical=True` |

Jadi fungsi "kemudahan" ini secara praktis **hanya menghasilkan sampah**, sementara jalur manual benar.
Penyebabnya tidak teruji: `tests/test_dispersion.py` hanya menguji `fit_debye_1pole` (dan memakai
`abs(v.imag)`), tidak ada test untuk pembungkusnya.

**Rekomendasi:** teruskan `-e.imag`; tambahkan test round-trip (`debye_eps` → fit → bandingkan parameter,
toleransi ketat); bila `is_physical=False`, naikkan menjadi peringatan yang terlihat di CLI.
Ini kelas bug yang sama dengan Issue 4, hanya tertinggal di satu pintu masuk.

---

### Y-02 (P1) — Kontrak `element_pattern` tidak cocok dengan `dipole_element_pattern`
`[terverifikasi-Yotta]` · `openantenna/postproc/patterns.py`

`array_pattern_product(..., element_pattern)` memanggil `element_pattern(theta_rad, phi_rad)`, sedangkan
`dipole_element_pattern(theta_rad, length_lambda=0.5)` mengartikan argumen kedua sebagai **panjang dipole**.
Pemakaian paling wajar (meneruskan fungsi dipole langsung) karena itu salah:

```
array_pattern_product([(0,0)], 2.45e9, θ=90°, φ=0, element_pattern=dipole_element_pattern)
  → ValueError: length_lambda must be > 0        # meledak di E-plane (φ=0)
  φ≠0 → pola dipole dengan panjang = φ (rad)      # salah, tanpa peringatan
```

**Rekomendasi:** satukan kontrak menjadi `f(theta, phi)` (mis. `dipole_element(theta, phi)` yang mengabaikan
φ), atau wajibkan pembungkus eksplisit; tambahkan test yang memakai `dipole_element_pattern` lewat
`array_pattern_product`.

---

### Y-03 (P2, tapi menyangkut kejujuran angka) — `CONDUCTOR_KAPPA` sia-sia: metal model = PEC
`[kode-terverifikasi]` · `openantenna/solvers/openems.py` (+ `sim.py` hasil generate)

Script yang di-generate mendefinisikan `CONDUCTOR_KAPPA = 58000000` (tembaga), tetapi seluruh pemanggilan
metal tidak memakainya:

```python
ground = CSX.AddMetal("ground")            # tanpa conductivity  -> default CSXCAD = PEC
patch  = CSX.AddMetal("patch_%d" % index)  # idem
```

Jadi loss konduktor **tidak dimodelkan** meskipun konstantanya ada dan tampak seperti tembaga. Ini membuat
setiap angka efisiensi/gain dari model menjadi optimistis.

**Rekomendasi:** teruskan `conductivity=CONDUCTOR_KAPPA` (lalu uji efeknya), atau hapus konstantanya.
Catat pilihan itu di `run_manifest.json` (mis. `"conductor": "PEC"`), supaya pembaca tahu.

---

## 4. Temuan — sinyal yang berpotensi menyesatkan

### Y-04 (P0-pelabelan) — "resonance check" tautologis: selalu `delta +0.000 MHz`
`[terverifikasi-Yotta]` · `geometry/patch.py`

`synthesize_patch` menghitung `L = c/(2 f0 √εeff) − 2ΔL`, lalu `resonant_frequency()` menghitung ulang
dengan rumus **identik** → secara aljabar selalu mengembalikan `f0` eksak. CLI pun mencetak:

```
resonance check  : 2.4500 GHz (delta +0.000 MHz)
```

Baris ini **terlihat seperti verifikasi independen**, padahal nol oleh konstruksi untuk input apa pun.
Test-nya sendiri mengakui hal ini (`test_resonance_check_is_self_consistent`). Risikonya justru yang
terbesar untuk sebuah alat sintesis: pengguna menyimpulkan "sudah tervalidasi" lalu melewati cek full-wave.

**Rekomendasi:** ganti label → `self-consistency (algebraic, bukan verifikasi)`, dan bila ingin cek
sungguhan, pakai model **berbeda** (mis. cavity model) supaya selisihnya informatif.

---

### Y-05 (P1) — `from_magnitude_db` → `impedance_ohm` menghasilkan impedansi palsu
`[terverifikasi-Yotta]` · `postproc/sparams.py`

`from_magnitude_db` menyimpan data magnitudo sebagai kompleks **real positif** (fase dipaksa 0). Semua
turunan berbasis fase jadi tidak bermakna:

```
from_magnitude_db([2.40e9, 2.45e9, 2.50e9], [-3, -20, -6]).impedance_ohm()
  → [292,4+j0 ; 61,1+j0 ; 150,5+j0] Ω      # reaktansi dipaksa nol, tanpa peringatan
```

VSWR / return loss / bandwidth tetap benar (hanya butuh |Γ|). Masalahnya terbatas pada impedansi.

**Rekomendasi:** simpan flag `has_phase` pada `S11Trace`; `impedance_ohm()` harus *raise/warn* bila
`has_phase=False`; sediakan `from_magnitude_phase_db(...)` untuk data berfase.

---

### Y-06 (P1) — `aperture_directivity` tanpa gerbang validitas
`[terverifikasi-Yotta]` · `postproc/patterns.py`

`D = 4π·A/λ0²` hanya berlaku untuk aperture besar & iluminasi seragam. Untuk radiator kecil rumus ini
justru **meremehkan**:

```
patch tunggal 49,1 × 41,4 mm @2,45 GHz  →  D = 1,707 lin = 2,32 dBi
(realita patch tunggal ≈ 7–8 dBi)
```

Jadi label *"upper-bound directivity"* menyesatkan pada rezim ini.

**Rekomendasi:** tolak/peringatkan bila `A ≲ λ0²` (atau salah satu sisi < ~λ0), atau arahkan pengguna ke
`directivity_from_pattern`. Perjelas docstring: batas atas **hanya** untuk aperture besar-seragam.

---

### Y-07 (P1) — Cek tumpang-tindih elemen hanya memakai **lebar**, bukan panjang
`[kode-terverifikasi]` · `geometry/array.py`

```python
if min(array.spacing_x_lambda0, array.spacing_y_lambda0) < 0.5 and element is not None:
    if element.width_m > min(dx, dy):   # hanya width_m!
```

Patch punya dua dimensi (W untuk x, L untuk y). Kasus `L > dy` (patch menumpuk sepanjang y) **lolos tanpa
peringatan**, dan bila `min(spacing) ≥ 0,5λ` seluruh blok tidak dievaluasi. Akibatnya geometri mustahil bisa
diteruskan ke generator solver.

**Rekomendasi:** bandingkan per-sumbu (`width_m` vs `dx`, `length_m` vs `dy`), lepaskan gerbang `< 0.5`,
tambah test untuk `L > dy`.

---

### Y-08 (P2) — `efficiency_budget` tidak memvalidasi |S11| ≤ 1
`[terverifikasi-Yotta]` · `postproc/patterns.py`

```
efficiency_budget(1.0 W, 1.0 W, s11=1.2)  →  mismatch_factor = -0,44
```

Nilai negatif itu lalu disembunyikan klausa `max(..., 1e-12)` saat diubah ke dB, sehingga yang muncul angka
absurd, bukan error.

**Rekomendasi:** raise/warn bila `abs(s11) > 1` untuk peranti pasif.

---

### Y-09 (P2) — Fasa steering selalu diterapkan, walau `weights` diberikan
`[kode-terverifikasi]` · `geometry/array.py`

Suku `−(x·u₀ + y·v₀)` dijumlahkan **tanpa syarat**, jadi `weights` selalu berperan sebagai eksitasi
**relatif** terhadap arah steering. Docstring berbunyi "…when `weights` is not given (or when `weights` is a
uniform-amplitude sequence)" — kalimat itu menyiratkan bobot bisa "mengalahkan" steering, dan itu tidak benar.

*(Catatan kejujuran: saya tidak berhasil mereproduksi angka "double-steering" spesifik dari laporan fisika
karena batas rentang sudut uji saya; yang saya nyatakan di sini adalah perilaku kode, bukan angka.)*

**Rekomendasi:** perjelas docstring + contoh, atau tambahkan `apply_steering: bool`.

---

### Y-10 (P2) — `εr ≤ 1` diterima, lalu menghasilkan `NaN`, dan perilakunya tidak konsisten antar mode feed
`[terverifikasi-Yotta]` · `geometry/patch.py`

```
synthesize_patch(2.45e9, 1.0, 1.6e-3, feed_mode="edge")  → BW = nan   (dicetak "~nan %")
synthesize_patch(2.45e9, 1.0, 1.6e-3, feed_mode="inset") → ValueError: epsilon_r must be > 1 ...
```

**Rekomendasi:** satu validasi terpusat (`εr > 1` untuk microstrip), kembalikan `None` + warning alih-alih
`NaN`, dan samakan pesan antar mode.

---

### Y-11 (P2) — Kriteria "substrat tebal" tidak sinkron antar modul
`[kode-terverifikasi]` · `model/project.py:288` vs `geometry/patch.py:226`

- `patch.py`: `h/λ0 > 0,01`
- `project.py`: `total_thickness/length > 0,1`

Untuk PTFE, `patch.py` memicu pada h ≈ 1,2 mm, sedangkan `Project.check` baru pada h ≈ 4,1 mm → ~3,4× lebih
longgar, sehingga desain tebal bisa "lolos bersih" lewat jalur `Project`. Pesan warning pun jadi bergantung
jalur pemanggilan.

**Rekomendasi:** sentralkan satu kriteria (mis. `h/λg`) di satu fungsi dan pakai di kedua modul.

---

### Y-12 (P2) — Koreksi Hammerstad untuk `W/h < 1` tidak ada
`[kode-terverifikasi]` · `geometry/patch.py`

`εeff` memakai aproksimasi "wide line" (`W/h ≥ 1`); pada `W/h < 1` Hammerstad menambahkan
`+0,04·(1 − W/h)²`. Belum ada koreksi maupun warning khusus untuk rezim itu.

**Rekomendasi:** tambahkan suku koreksi atau warning eksplisit + test batas `W/h` kecil.

---

### Y-13 (P2) — `directivity_from_pattern`: metode di docstring ≠ implementasi
`[terverifikasi-Yotta]` · `postproc/patterns.py`

Docstring menyebut "midpoint/trapezoidal", implementasinya **jumlah persegi** pada simpul grid seragam, dan
`peak` hanya maksimum di simpul (bisa melewatkan puncak beam tajam).
Ukuran saya: dipole pendek D = 1,4795 (teori 1,500) dan dipole setengah gelombang D = 1,6184 (teori 1,641)
→ bias ≈ **−1,4 %** pada grid 1° (θ) × 5° (φ).

**Rekomendasi:** perbaiki docstring, pakai bobot trapezoidal/midpoint, dukung grid tak seragam, dan
tambahkan **test bernilai emas** (D dipole = 1,5 / 1,641; null array factor; patch acuan Balanis).

---

### Y-14 (P2) — `array_factor_plane`: normalisasi per-bidang, tanpa `weights`
`[kode-terverifikasi]` · `geometry/array.py`

Normalisasi memakai puncak **di dalam bidang** saja (beam yang di-steer keluar bidang akan tetap tampil
"0 dB" padahal relatif sangat rendah), tidak menerima `weights` (tak bisa memplot taper), dan label
`e`/`h` sebenarnya cuma bidang φ=0/φ=90° — **bukan** E-plane/H-plane fisik patch.

**Rekomendasi:** opsi normalisasi global, dukungan `weights`, dan label "x-z cut"/"y-z cut".

---

### Y-15 (P2) — `read_touchstone` mengabaikan referensi Z0
`[kode-terverifikasi]` · `postproc/sparams.py`

Parser membaca `# Hz S RI R 50` tetapi hanya mengambil satuan frekuensi dan format; **nilai `R` diabaikan**.
Membaca berkas 75 Ω lalu memanggil `impedance_ohm()` (default 50 Ω) menghasilkan impedansi salah tanpa
peringatan. (VSWR/RL/BW tetap benar.)

**Rekomendasi:** simpan `reference_impedance_ohm` pada `S11Trace` dan jadikan default.

---

### Y-16 (P2) — Dead code & detail kecil
`[kode-terverifikasi]`

- `materials/mixing.py`: fungsi lokal `with_loss()` tidak dipakai; `eps_vol_real` dihitung lalu tak dipakai.
- `postproc/sparams.py`: `vswr_from_gamma` melakukan `abs()` **lalu** memeriksa `< 0` (cabang tak terjangkau);
  docstring konvensi tanda S11 kalimatnya rusak.
- `patterns.py`: `aperture_directivity` benar pada rentangnya, tapi tak ada penjaga; `dipole_element_pattern`
  adalah proksi kasar untuk patch (patch bukan dipole) — sebaiknya dinyatakan.

---

### Y-17 (P2) — Packaging & portabilitas
`[terverifikasi-Yotta]`

- **Tidak ada `pyproject.toml`/`setup.py`** → tidak bisa `pip install -e .`; paket hanya bisa diimpor bila CWD
  = root repo. Ini akan menyulitkan GUI Phase 3 yang seharusnya menjadi *client* paket ini.
- Perintah di README (`python -m unittest ...`) **gagal pada distribusi Python "embedded/isolated"**
  (mis. Python bawaan AutoClaw: ada `python313._pth`, `safe_path=True`, `PYTHONPATH` diabaikan) karena CWD
  tidak masuk `sys.path`. Di CPython biasa normal — tapi ada baiknya disebut, karena banyak pengguna Windows
  memakai Python dari paket embedded.
- `os.add_dll_directory()` khusus Windows; jalur Linux/macOS belum ada.

**Rekomendasi:** tambah `pyproject.toml` + `console_scripts` (`openantenna = openantenna.cli:main`),
sertakan catatan lingkungan, dan siapkan jalur non-Windows.

---

## 5. Kandidat akar penyebab offset resonansi 7,8 % (diskusi terbuka)

`docs/verification.md` sudah menyingkirkan mesh & posisi feed dengan baik. Dua kandidat berikut **belum
pernah diuji** dan menurut saya paling menjanjikan.

### Y-18 (P1, kandidat) — Margin udara terlalu kecil dibanding ketebalan PML
`[kode-terverifikasi]` · `solvers/openems.py` (`air_margin_lambda=0.20`, `PML_CELLS=8`)

Angka dari `run_manifest.json` + `sim.py` yang di-generate:

| Besaran | Nilai | Catatan |
|---|---|---|
| λ_min (di F_MAX = 2,817 GHz) | 106,4 mm | dipakai untuk semua margin |
| margin sisi `AIRBOX_LAMBDA` | 0,20 · λ_min = **21,3 mm** | diukur dari **tepi ground plane** |
| ground plane | 110,3 × 102,6 mm | = patch + 0,25 λ₀ per sisi |
| PML | **8 sel** | sel luar ≈ MESH_MAX_RES ≈ λ_min/15 ≈ 7,1 mm |

Artinya: tebal absorber nominal ≈ 50–57 mm, sedangkan ruang bebas lateral antara tepi ground dan batas
domain hanya ≈ 21 mm (≈ **0,17 λ₀**). Ruang bebas efektif patch → penyerap sangat sempit. Literatur/praktik
umum menyarankan minimal λ/4 (ideal λ/2) antara radiator dan PML, dan PML tidak boleh menyentuh/mendekati
struktur. Gejala "resonansi turun + match lemah" konsisten dengan absorber yang terlalu dekat (memuat antena).

**Eksperimen murah (3 run, tidak perlu ubah kode — cukup parameter adapter):**
1. `air_margin_lambda` 0,2 → 0,35 → 0,5 (sisi & atas);
2. `PML_CELLS` 8 → 6 → 4;
3. catat resonansi tiap kombinasi.

Kalau resonansi bergerak naik ke ≈2,45 GHz, akar masalahnya ketemu. Tambahkan kolom **"jarak struktur→PML
(mm)"** dan **"tebal PML (mm)"** ke manifest, supaya kesalahan ini tidak terulang.

### Y-19 (P1) — Topologi feed ≠ sintesis "inset"
`[kode-terverifikasi]` · `solvers/openems.py` + `sim.py`

Model merealisasikan feed sebagai **lumped port vertikal (probe/coax)** dari ground ke patch:

```python
port = FDTD.AddLumpedPort(1, FEED_Z0, [FEED_X, FEED_Y, -H_TOTAL], [FEED_X, FEED_Y, 0.0], "z", 1.0, edges2grid="xy")
```

`feed_mode="inset"` hanya berbeda pada `feed_y = L/2 − inset`; geometrinya tetap **probe vertikal**. Padahal
rumus inset `R_in(y) = R_edge·cos²(πy/L)` adalah untuk **inset-feed coplanar** (microstrip sejajar patch).
Probe dan inset coplanar punya induktansi seri serta distribusi arus yang berbeda.

Implikasi: kesimpulan "feed loading bukan penyebab" di `docs/verification.md` sahih **untuk posisi probe**,
tetapi tidak memvalidasi rumus inset. Model saat ini **tidak bisa** memvalidasi sintesis inset.

**Rekomendasi:** (a) generate geometri feed coplanar + notch inset, atau (b) relabel sintesis sebagai
"posisi probe" dan pakai rumus probe, serta tulis perbedaannya di dokumen. Ini juga menjelaskan kenapa
inset ≈ 0 (edge) tidak konvergen — konfigurasi itu degenerat untuk port lumped.

---

## 6. Yang sudah kuat (jangan diubah)

- **Rumus patch inti benar** (sesuai Balanis/Hammerstad): `W = c/(2f)√(2/(εr+1))`, `εeff`, `ΔL` 0,412h…,
  `L = c/(2f√εeff) − 2ΔL`; untuk PTFE 2,45 GHz → 49,143 × 41,379 mm, εeff = 2,0164, ΔL = 0,8536 mm.
  Inset: `R_edge ≈ 90·εr²/(εr−1)·(L/W)²` dengan clamp yang benar.
- **S-parameter benar:** VSWR `(1+|Γ|)/(1−|Γ|)`, return loss, `bandwidth_below` dengan interpolasi tepi pita
  dan penanganan pita terbuka; Touchstone tulis/baca (RI/MA/DB, Hz–GHz) sesuai spesifikasi.
- **Array factor benar:** definisi `u = sinθcosφ`, `v = sinθsinφ`, θ dari +z; uniform 4×4 → `|AF| = 16` eksak;
  broadside/endfire konsisten. `|AF| = 0` pada θ=90° untuk 2 elemen berjarak λ/2 sepanjang x adalah **benar**
  (endfire terhadap sumbu array), bukan bug.
- **Kejujuran mekanisme:** `solver status` menyebut alasan rinci; `run_manifest.json` `"verified": false`
  dan `"converged": false`; `SolverUnavailableError` alih-alih data palsu; `sim.py` menandai dirinya
  "never executed". Ini praktik yang bagus dan sebaiknya dipertahankan.
- **Satuan SI konsisten** (m, Hz; sudut `_rad`; tidak ada campur Hz vs rad/s), pemisahan tegas
  `ValueError` (fisika salah) vs `warnings` (rekayasa diragukan).
- **Dokumen jujur:** `verification.md`, `capabilities-and-comparison.md`, `roadmap.md` secara eksplisit
  menyatakan yang belum terverifikasi.

---

## 7. Pertanyaan terbuka untuk AI berikutnya

1. **Y-18:** berapa margin udara & jumlah sel PML yang Anda pakai, dan berapa resonansi yang Anda dapat?
   Bisakah seseorang menjalankan sapu 3 titik (margin × PML) dan mengunggah hasilnya?
2. **Y-19:** apakah ada rencana memodelkan inset-feed coplanar sungguhan (garis microstrip + notch)?
   Kalau ya, bagaimana rencana de-embedding referensi port?
3. **Y-01:** apakah ada pemakai `fit_debye_from_complex` di luar test? Kalau tidak, lebih baik diperbaiki
   sekarang (perubahan 1 baris) sebelum tersebar.
4. **Y-13:** nilai emas mana yang disepakati sebagai regression test (D dipole, null AF, patch acuan)?
5. **Y-17:** apakah `pyproject.toml` akan ditambahkan sebelum Phase 2/3?
6. Untuk konvensi bandwidth: mana yang jadi angka resmi, **VSWR ≤ 2** (−9,54 dB) atau **−10 dB**?
7. Fabrikasi: apakah ada rencana menambahkan **NF2FF box** ke `sim.py` supaya `postproc/patterns.py` bisa
   dibandingkan dengan pola hasil solver (bukan hanya pola analitik)?

---

## 8. Lampiran — cara mereproduksi

```powershell
# 0) ambil repo, lalu JANGAN pakai python embedded
# 1) test suite
py -3 -m unittest discover -s tests -v                 # 82 tests, OK

# 2) CLI
py -3 -m openantenna.cli design patch --freq 2.45e9 --material PTFE --h 0.0016   # lihat "delta +0.000 MHz"
py -3 -m openantenna.cli gen-openems --freq 2.45e9 --material PTFE --h 0.0016 --out runs\patch1
py -3 -m openantenna.cli solver status
py -3 -m openantenna.cli sweep dry-run --axis substrate.layers.0.thickness_m=0.0008,0.0016,0.0032 --out runs\sweep1

# 3) Y-01 (bug tanda eps'')
py -3 -c "import sys; sys.path.insert(0,'.');from openantenna.materials.dispersion import *;\
p=dict(eps_inf=2.1,delta_eps=0.4,tau_s=1e-8);f=[1e7*10**(i/10) for i in range(11)];\
s=[debye_eps(x,**p) for x in f];\
print(fit_debye_from_complex(f,s).params.to_dict());\
print(fit_debye_1pole(f,[v.real for v in s],[-v.imag for v in s]).params.to_dict())"

# 4) Y-06 / Y-05 (sanity angka)
py -3 -c "import sys; sys.path.insert(0,'.');from openantenna.postproc.patterns import aperture_directivity as a;\
print(10*__import__('math').log10(a(0.049142,0.041379,2.45e9)))"   # ~2.32 dBi, bukan 7-8 dBi
py -3 -c "import sys; sys.path.insert(0,'.');from openantenna.postproc.sparams import S11Trace as T;\
print(T.from_magnitude_db([2.4e9,2.45e9,2.5e9],[-3,-20,-6]).impedance_ohm())"
```

**Batas telaah ini (jujur):** openEMS tidak terpasang di lingkungan saya, jadi **tidak ada** klaim tentang
akurasi solver yang bisa saya buat; seluruh temuan bersifat statis/numerik-pustaka. Telaah material
(mixing/dispersion) saya kerjakan langsung dan hanya sebagian tercermin di atas (Y-01); bagian mixing rule
saya nilai **baik** (Wiener/Lichtenecker/Maxwell-Garnett/Bruggeman benar, batas validitas dinyatakan) dengan
catatan P2: hapus `with_loss()`/`eps_vol_real` yang mati, dan pertimbangkan cabang akar Bruggeman untuk
konstituen lossy kompleks (potensi diskontinuitas cabang `sqrt`).

---

*Ditulis oleh **Yotta** — 2026-09-21. Senang berdiskusi; silakan balas per-ID di bawah.*
