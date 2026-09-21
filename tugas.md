# tugas.md â€” papan tugas bersama (Yotta â†” Aksara)

> **Berkas bersama.** Ini papan kerja, bukan catatan pribadi: siapa pun boleh menandai
> status di sini. Riwayat penilaian tetap di `yottakomen.md` / `aksarakomen.md`;
> masukan strategis pihak ketiga di `geminikomen.md`.
> Snapshot saat papan ini dibuat: `main` @ `5cea9159` (2026-09-21).

## 0. Aturan main

1. **Satu item = satu pemilik.** Kalau butuh bantuan pihak lain, tulis di kolom "butuh".
2. **Status yang dipakai (jangan dilonggarkan):** `belum` Â· `jalan` Â· `terverifikasi` Â· `gugur`.
   "terverifikasi" hanya setelah ada **bukti yang bisa direproduksi** (perintah + keluaran,
   atau test yang gagal bila perilakunya dirusak).
3. **Definition of done** untuk item kode: (a) ada test yang menangkap bila perilakunya
   diubah, (b) `python -m unittest discover -s tests` hijau, (c) `docs/` yang relevan
   diperbarui, (d) push, (e) status di papan ini diperbarui.
4. **Pembagian tetap:** Aksara menerapkan di paket `openantenna/` **dan** semua yang butuh
   solver (openEMS hanya terpasang di mesinnya). Yotta mengerjakan verifikasi independen,
   analisis, dan alat di `yotta_tools/` (dan ikut build di paket bila diminta pemilik).
5. **Kredensial:** token GitHub sudah muncul di transkrip chat â€” rotate setelah pekerjaan ini.

---

## 1. Antrean Yotta (dikerjakan mulai sekarang, tanpa solver)

| ID | Item | Prio | Kenapa | Kriteria selesai | Status |
|---|---|---|---|---|---|
| **Y-1** | `yotta_tools/reference_table.py` â€” baca setiap run (`project.json`) + `s11.csv`, hitung prediksi **cavity** & **TL** dari geometri **run itu sendiri**, tulis satu tabel acuan tunggal (JSON + Markdown) | P1 | Menghapus sumber error Â§19.2: tabel generalisasi sekarang mencampur acuan (cavity untuk 3 geometri, hasil ukur tutorial untuk 1) | alat jalan tanpa solver pada run dir mana pun; angka cocok dengan Â§19.2; ada test | belum |
| **Y-2** | Verifikasi klaim S-2/S-3/S-4 (`analyze_resonance.py` ditulis ulang: geometri dari `project.json`, arah persilangan dilabeli, tulis `resonance_analysis.json`) | P1 | Klaim itu belum pernah saya periksa; analisis resonansi dipakai untuk keputusan | bukti keluaran per klaim; status per-ID (`terverifikasi`/`gugur`) | belum |
| **Y-3** | Protokol A/B `port_refine` yang ketat (perintah siap pakai + kriteria interpretasi) | P1 | A4 adalah kandidat sisa bias; A/B harus bersih supaya hasilnya dipakai | perintah + kontrol variabel + ambang keputusan tertulis | belum |
| **Y-4** | Nilai emas benchmark kedua: **microstrip line** (Îµ_eff Hammerstad, Z0 Wheeler/Hammerstad) di `docs/benchmarks.md` + verifikasi implementasi | P2 | Menjawab kelemahan "hanya satu jenis geometri" (masukan Gemini) | rumus + angka + toleransi + sumber; bila paket perlu model saluran, ajukan ke Aksara | belum |
| **Y-5** | Checklist gate fabrikasi: kapan angka solver boleh disebut otoritas desain | P2 | Semua pihak butuh definisi "cukup baik" yang sama | daftar kondisi terukur + sifatnya mengikat | belum |
| **Y-6** | Y-T3: jalankan `yotta_tools/mixing_validation.py` | P1 | Validasi mixing rules terhadap data terukur | tabel terukur vs model + cek batas Wiener | belum (butuh `data/composite_measurements.csv`) |

## 2. Antrean Aksara (butuh openEMS / perubahan paket)

| ID | Item | Prio | Kenapa | Kriteria selesai | Status |
|---|---|---|---|---|---|
| **A-1** | A/B `port_refine` **on/off** pada geometri tutorial **dan** patch PTFE 2,45 GHz (geometri, mesh, margin lain identik) | P1 | A4 menyasar sisa bias; tanpa A/B kita tidak tahu apakah bergerak | 4 angka: resonansi/\\|S11\\|/VSWR + status konvergen, untuk kedua geometri | **jalan** (dijalankan 2026-09-21) |
| **A-2** | **NF2FF**: kotak near-to-far-field di generator + dump far-field + pembacaannya di `postproc/` | P1 | Celah nyata (masukan Gemini #3): tanpa ini pola/gain dari solver tidak bisa diverifikasi | differential run: S11 **tidak berubah**; pola bisa dibaca & dibandingkan dengan `patterns.py` | belum |
| **A-3** | Tabel generalisasi **ulang** memakai alat Y-1 (acuan tunggal = cavity), bukan campur acuan | **P0 (keputusan)** | Menentukan: kalibrasi sekali vs tuning per-geometri | tabel ber-acuan tunggal + pernyataan eksplisit kesimpulannya | **selesai 2026-09-21** (spread 2,7 poin: -2,31 % s/d -4,99 %) |
| **A-4** | Perbaiki `docs/verification.md` Â§generalisation bila hasil A-3 bertentangan dengan klaim "bias konstan âˆ’4,1â€¦âˆ’5,0 %" | P1 | Klaim yang salah lebih berbahaya daripada tidak ada klaim | dokumen sesuai hasil A-3 | **selesai** — klaim "konstan" ditarik |
| **A-5** | Selesaikan uji ground plane bebas perancu (titik 1,00 Î» yang tadi masih berjalan) + ulangi dengan `port_refine` default baru | P2 | Baseline bergeser setelah snapping; tren ground plane harus diukur ulang pada baseline baru | 3 titik, domain tetap, dilaporkan di `docs/verification.md` | belum |
| **A-6** | Pakai `tugas.md` sebagai papan status (jangan hanya di `aksarakomen.md`) | P2 | Supaya pembagian kerja terlihat satu tempat | status di tabel ini diperbarui tiap push | belum |
| **A-7** | Ekspos `port_refine` (dan `metal_edge_snapping`) ke CLI/GUI sehingga A/B bisa satu perintah | P2 | Mengurangi kesalahan manual saat A/B | flag CLI + kontrol GUI + test | belum |

## 3. Ditunda â€” dengan alasan (bukan dilupakan)

| Item | Asal | Alasan menunda |
|---|---|---|
| Parser Gerber/KiCad | Gemini #2 | Pekerjaan besar (format, layer, via, netâ†’geometri). Bukan blocker: model parametrik sudah menutup kebutuhan proyek sendiri. Butuh keputusan scope dulu |
| GUI web (WebGL/Plotly) | Gemini | Proyek memilih desktop PySide6 dengan alasan tertulis (offline, solver lokal, tanpa server). Tinjau ulang **setelah** kalibrasi |
| Inset coplanar sungguhan (microstrip + notch) | Y-19 | Phase 2, tetapi **prioritasnya lebih tinggi daripada parser Gerber** â€” ini yang membuat model bisa memvalidasi rumus inset |
| Loss konduktor (sekarang metal = PEC) | Y-03 | Perlu keputusan; memengaruhi efisiensi/gain. `conductivity` sudah tersedia di CSXCAD, tinggal dinyalakan + diuji |
| Unit-cell/periodic + array 4Ã—4 penuh | roadmap | Setelah akurasi elemen tunggal tuntas |
| Deteksi konvergensi sebagai syarat lapor | roadmap | Sebagian sudah (manifest mencatat `converged`) â€” sisa: **tolak** melaporkan resonansi dari run yang menyentuh cap langkah |

## 4. Aturan pelaporan hasil (supaya bisa dipercaya)

* Setiap angka solver ditulis dengan **acuan yang sejenis** (cavity untuk analitik, hasil ukur
  untuk pengukuran) â€” jangan campur dalam satu tabel tanpa kolom acuan.
* Sertakan **jumlah langkah + status konvergen** pada setiap run yang dilaporkan.
* Kalau sebuah hipotesis gugur, tulis "gugur" â€” jangan dihapus (lihat Y-18 sebagai contoh).
* Perubahan perilaku numerik apa pun harus datang dengan **differential run** (satu variabel).

---

*Dibuat oleh **Yotta** â€” 2026-09-21. Silakan Aksara menambahkan/mengubah barisnya; kalau ada
item yang menurutmu salah pemilik, pindahkan dan tulis alasannya di baris itu.*
