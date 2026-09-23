# Status & plan — 2026-09-23 (Aksara)

Ringkasan capaian, bukti, batasan jujur, dan rencana lanjutan. Ditulis dari keadaan repo
yang sudah diperiksa pada tanggal ini, bukan dari ingatan.

- HEAD saat ditulis: `172ec96` (== `origin/main`)
- Suite: **464 test OK** (`python -m unittest discover -s tests`)
- CI: **6/6 job success** — `suite` (ubuntu/windows × py3.11/3.13), `GUI (qt, offscreen)`,
  `frozen GUI (windows)`
- Permukaan: **20 subperintah CLI**, **7 tab GUI**, 42 modul paket, 50 berkas test, 33 dokumen

---

## 1. Capaian yang terverifikasi

### Fase 1 — inti + GUI (selesai untuk ruang lingkupnya)

| Bidang | Isi |
|---|---|
| Material | pustaka material, aturan pencampuran dua-fasa, dispersi; editor sensitivitas + Wiener |
| Model | model proyek netral-solver (`kind: openantenna.project`), simpan/muat JSON |
| Geometri | sintesis patch, tata letak array, feed korporat 1-D, pohon-H 2-D dua-lapis, CAD (STL biner/ASCII, OBJ, DXF) |
| Solver | batas proses untuk openEMS/CSXCAD (tidak pernah di-vendor), generator dek, streaming progres |
| Pasca-proses | S-parameter, pola, far-field/NF2FF, matriks port, jaringan feed, kalibrasi, pembanding referensi |
| Sweep | mesin sweep, runner paralel, tabel gaya-CST (factorial & one-at-a-time, cap 4096, `to_csv`) |
| Optimasi | differential evolution stdlib-only, deterministik per seed, kegagalan dihitung bukan disembunyikan |
| GPU | FDTD 2-D TMz OpenCL (`openantenna/gpu/`), validasi rongga **0.031 %** |
| CLI | 20 subperintah, termasuk `feed-plan`, `optimise`, `cad-inspect`, `dxf-inspect` |
| GUI | 7 tab: Material & composite · Design · Simulate · Results · Sweep · Import · Optimise |

### Fase 2 — pemodelan lanjutan

NF2FF, sel unit, kenop `numthreads` (no-op di build resmi openEMS — dicatat), sweep paralel,
streaming progres atomik (`progress.json`) dengan bar di GUI.

### Fase 3 — GUI & pengemasan

Tema gelap, pratinjau 2-D + faktor array + pratinjau 3-D dengan **preset kamera**, simpan/muat
proyek, provenance hasil + far-field + overlay A/B, dock pohon proyek, antrean batch,
notifikasi non-modal, `--selftest`, dan paket PyInstaller (`scripts/build_gui.py`,
`packaging/openantenna-gui.spec`).

### Fase 4 — optimasi

Pencarian lintas-generasi + CLI (`optimise`) + **tab Optimise di GUI**.

---

## 2. Disiplin bukti yang dipakai

- Inti dan test **stdlib-only**; dependensi opsional (PySide6, matplotlib, pyopencl, scikit-rf)
  dimuat malas dan test-nya di-skip bila tidak ada.
- Status epistemik dipakai ketat: **teramati / kandidat / tereproduksi / terkonfirmasi**.
  Tidak ada klaim "terverifikasi" tanpa menjalankan sesuatu.
- Setiap deviasi menyebut referensinya; satu tabel tidak mencampur referensi.
- Penyangkalan eksplisit (bukan fallback diam): non-pangkat-dua, `element_ports` + pohon feed,
  header STL yang berbohong, grid > 2000 sel/sumbu, |S| ≥ 1, run tidak konvergen.
- Tiga penyapu statis sebagai **ratchet**, bukan surat sehat: binding dek tergenerate (AST),
  binding kondisional generator (baseline heuristik 40), eksekusi dek nyata dengan stub numerik.

---

## 3. Bukti numerik yang tercatat

| Item | Angka | Catatan |
|---|---|---|
| `auto_tune.py` | 2.4496 GHz, **−0.018 %** dari target | penyetelan, bukan validasi solver |
| Validasi GPU (rongga) | **0.031 %** | kernel FDTD kita sendiri |
| Beda dua prediktor @2.45 GHz | **3.3 %** (cavity 31.6431 mm vs TL 32.7110 mm) | angka targeting |
| Bias kalibrasi | PTFE −4.99 % (2.45 GHz), εr 2.2 −4.90 %, εr 4.4 −4.11 % | `docs/calibration.md` |
| Anggaran tata letak feed 1 lapis | 19 pasangan bertabrakan pada 4×4 | karena itu dua lapis |

---

## 4. Batasan jujur (belum, dan alasannya)

1. **Belum ada validasi solver end-to-end yang konvergen.** Gerbang bias (#2) dan loss (#4)
   menunggu run terkonvergensi. Hambatan sebenarnya proyek ada di sini, bukan di fitur.
2. **Editor dielektrik bertumpuk belum ada**: generator masih menerima satu lapisan dielektrik.
   Ini pekerjaan sisi generator, bukan GUI.
3. **Pohon feed**: mesh hanya edge-snapped; padding λ/4 segmen baris belum; `element_ports` + pohon
   masih ditolak; tumpukan lapisan-terkubur menunggu proses via/dielektrik nyata.
4. **nec2 tidak terpasang** (tidak ada kompiler C).
5. **STEP/IGES tidak ada** — butuh kernel CAD (~300 MB); DXF hanya outline, bukan permukaan.
6. **Token GitHub bocor** (`ghp_…` di `.cluster/yotta-open-antena/.gh_token`) — perlu dirotasi
   oleh pemilik.

---

## 5. Pelajaran yang sudah menjadi aturan kerja

1. Kompilasi/verifikasi di staging **sebelum** menyalin ke repo.
2. Sisip kelas baru di **akhir** berkas; ambil indentasi dari baris anchor itu sendiri.
3. Perbarui ekspektasi test (jumlah tab/judul) secara sadar — jangan melemahkan test.
4. Tulis skrip bantu sebagai **berkas**, bukan perintah inline (kutip PowerShell merusak perintah).
5. **Commit hanya jika suite hijau.** Dua kali hari ini saya push merah (lokal) karena melanggar
   ini — CI tetap hijau waktu itu hanya karena test GUI di-skip tanpa PySide6. Job `gui` sekarang
   menutup lubang itu.
6. Verifikasi sinkronisasi: `sync_audit.py` harus melaporkan 0 perbedaan sebelum berhenti.

---

## 6. Plan lanjutan (urut prioritas)

| # | Pekerjaan | Nilai | Risiko | Ukuran |
|---|---|---|---|---|
| 1 | **Dielektrik bertumpuk di generator** (buka blokir editor stackup) | tinggi untuk riset komposit | sedang–tinggi | besar |
| 2 | **Example + dokumentasi DXF** (`examples/05`, `docs/gui.md`) | paritas galeri & dokumen | rendah | kecil |
| 3 | **Panen run terkonvergensi** (4×4, resumable) | menutup gerbang #2/#4 | — | terblokir: mesin Yotta |
| 4 | **`.s1p` CST + εr** → `reference_compare` → tabel bias → `calibrate()` | menutup perbandingan CST | — | terblokir: berkas dari pemilik |
| 5 | `element_ports` + pohon feed | kelengkapan feed | sedang | sedang |
| 6 | STEP/IGES | impor CAD penuh | tinggi (kernel) | besar |
| 7 | Rotasi token GitHub | keamanan | — | pemilik |

Urutan yang saya sarankan: **1 → 2**, lalu 3/4 begitu sumber dayanya tersedia.

---

## 7. Cara menjalankan

```powershell
# suite (tidak butuh solver maupun dependensi opsional)
python -m unittest discover -s tests

# GUI (butuh PySide6) dan uji mandirinya
python -m openantenna.gui --selftest

# dengan solver: OPENEMS_ROOT harus menunjuk instalasi openEMS
$env:OPENEMS_ROOT = "D:\OpenAntenna\tools\openEMS"

# contoh alur kerja
python -m openantenna.cli feed-plan --rows 4 --cols 4 --pitch-mm 60 --frequency-hz 2.45e9 --epsilon-r 2.2 --height-mm 1.6
python -m openantenna.cli optimise --target-hz 2.45e9 --epsilon-r 2.2 --height-mm 1.6 --predictor cavity
python -m openantenna.cli dxf-inspect board.dxf --cell-mm 2
```
