# AG Penjadwalan Kuliah — UTS

Algoritma Genetika (operator ditulis sendiri, tanpa DEAP/PyGAD) untuk menyusun jadwal kuliah
TI UPR Semester 1/3/5 dari `data/Data_Jadwal_TI_UPR_Semester_1_3_5.xlsx`.

## Cara menjalankan
```bash
pip install -r requirements.txt
python flask_app.py            # APLIKASI (tampilan web): upload data, atur parameter, run, unduh jadwal
python main.py                  # 1 run (seed 42) -> hasil/jadwal_terbaik.csv|xlsx, hasil/konvergensi.png
python main.py --eksperimen     # 10 run seed 1..10 -> hasil/hasil_run.csv, ringkasan_run.csv
python main.py --bandingkan     # 10 run x 4 kombinasi (seleksi x crossover) -> perbandingan_operator.csv
python main.py --evaluasi-asli  # cek pelanggaran pada jadwal asli di Excel
python -m pytest -q             # unit test
```
Parameter bisa diubah lewat opsi CLI: `--pop --gen --pc --pm --seleksi --crossover --elitisme --seed --runs`.

## Struktur kode
| File | Isi |
|---|---|
| `config.py` | parameter default + **asumsi kapasitas ruang & jumlah mahasiswa (placeholder, mohon diganti)** |
| `data_loader.py` | baca Excel, normalisasi nama dosen, matriks overlap slot, domain slot per gen |
| `fitness.py` | fitness `1/(1+pelanggaran)`, validator independen (untuk test), kendala lunak (jeda panjang) |
| `ga.py` | inisialisasi, seleksi roulette & turnamen, crossover satu titik & uniform, mutasi, elitisme |
| `export.py` | tabel jadwal, grid hari x slot, ekspor CSV/Excel, grafik konvergensi |
| `eksperimen.py` | batch run, ringkasan, perbandingan operator |
| `flask_app.py` | server Flask: API JSON + menyajikan halaman web |
| `ga_api.py` | `jalankan_ga(params, seed)` -> dict JSON-able, untuk tim desain/UI |
| `templates/` | tampilan HTML |
| `static/` | CSS, JS, font, library (Chart.js, disimpan lokal untuk offline) |
| `main.py` | perintah command line |
