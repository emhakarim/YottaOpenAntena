# yotta_tools

Alat milik **Yotta** (peran: reviewer/analis). Berkas di sini **di luar paket `openantenna`**
sesuai pembagian kerja: Aksara menerapkan perubahan paket, Yotta menyediakan alat bantu,
pengukuran, dan verifikasi.

## `mixing_validation.py` — Y-T3

Membandingkan **data komposit terukur** dengan empat mixing rule di
`openantenna/materials/mixing.py` (Wiener bounds, Lichtenecker, Maxwell-Garnett, Bruggeman),
lalu memeriksa apakah nilai terukur masuk di dalam batas Wiener.

### Cara pakai

```powershell
# dari root repo
python yotta_tools/mixing_validation.py                              # baca data/composite_measurements.csv
python yotta_tools/mixing_validation.py path/ke/tabel.csv            # berkas lain
python yotta_tools/mixing_validation.py tabel.csv --out laporan.md   # laporan
```

Keluaran: tabel nilai terukur vs tiap model, tabel galat relatif per model, ringkasan model mana
yang paling dekat secara rata-rata, dan daftar baris yang **di luar batas Wiener** (itu sinyal —
fase terbalik, rongga udara, atau perkolasi — bukan bug). Laporan Markdown ditulis ke
`yotta_tools/mixing_validation_report.md`.

### Skema CSV yang diharapkan

```csv
matrix_material,eps_matrix,filler_material,eps_filler,vf,freq_hz,eps_eff_measured,tand_measured,source_doi
PTFE,2.1,BaTiO3,2000,0.15,2.45e9,4.2,0.002,10.xxxx/xxxxx
```

Hanya `eps_matrix`, `eps_filler`, `vf`, `eps_eff_measured` yang **wajib**; kolom lain boleh kosong.
Baris dengan nilai tidak valid dilewati **dan dilaporkan** — tidak pernah "diperbaiki" diam-diam.

### Prinsip

* Alat ini **tidak mengarang data**. Kalau CSV belum ada, ia mencetak skema yang dibutuhkan dan
  keluar dengan kode non-nol.
* Angka terukur harus berasal dari sumber yang bisa dikutip (`source_doi`), bukan dari ingatan
  model bahasa.
* Kesepakatan atau ketidaksesuaian di sini menguji **implementasi** rule, bukan fisika sampel
  tertentu — itu catatan yang selalu ikut di laporan.
