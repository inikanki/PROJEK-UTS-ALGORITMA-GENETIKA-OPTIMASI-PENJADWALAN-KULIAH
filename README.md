# AG Penjadwalan Kuliah — UTS

Algoritma Genetika (operator ditulis sendiri, tanpa DEAP/PyGAD) untuk menyusun jadwal kuliah
TI UPR Semester 1/3/5 dari `data/Data_Jadwal_TI_UPR_Semester_1_3_5.xlsx`.

## Cara menjalankan
```bash
pip install -r requirements.txt
streamlit run app.py           # APLIKASI (tampilan web): upload data, atur parameter, run, unduh jadwal
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
| `app.py` | aplikasi Streamlit (UI) |
| `ga_api.py` | `jalankan_ga(params, seed)` -> dict JSON-able, untuk tim desain/UI |

## Rancangan singkat (bahan laporan)
- **Gen** = satu sesi kuliah (43 sesi dari data) berisi pasangan `(slot_waktu, ruang)` bertipe integer.
  **Kromosom** = 43 gen. Encoding integer dipilih karena entitas (slot, ruang) berhingga dan operator
  crossover/mutasi sederhana tetap menghasilkan kromosom yang sah.
- **Kendala keras** (tiap pelanggaran = penalti 1): (1) dosen mengajar dua sesi pada slot beririsan,
  (2) ruang dipakai dua sesi pada slot beririsan, (3) kelas yang sama (semester + kelas, "-" = satu angkatan)
  punya dua sesi beririsan, (4) kapasitas ruang < jumlah mahasiswa, (5) durasi slot tidak sesuai durasi mata kuliah.
- **Irisan slot**: slot di data tidak seragam (mis. 07.00–09.30 dan 08.40–11.10 di hari yang sama saling
  menimpa), jadi bentrok dihitung dari irisan waktu, bukan dari kesamaan ID slot.
- **Durasi (kendala 5)** diturunkan dari jadwal asli: mata kuliah 100 menit (Pancasila, B. Inggris,
  Kalkulus I, Agama) hanya boleh di slot 100 menit, sisanya 150 menit. Ini diterapkan sebagai *domain gen*,
  jadi inisialisasi, crossover, dan mutasi tidak pernah melanggarnya.
- **Mata kuliah agama** paralel (mahasiswa memilih satu), jadi tidak dihitung bentrok kelas satu sama lain.
- **Kendala lunak** (hanya dilaporkan, belum dioptimalkan): jumlah jeda > 90 menit antar kuliah satu kelas
  di hari yang sama (`jeda_panjang`). Preferensi waktu dosen belum ada datanya.
- **Parameter default**: populasi 100, 300 generasi, pc 0.8, pm 0.03 per gen, turnamen k=3, uniform, elitisme 2.
