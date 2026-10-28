# Kuliahify — Penjadwal Kuliah Tanpa Bentrok

UI ini menggunakan HTML, CSS, dan JavaScript dengan Flask sebagai penghubung ke algoritma Python yang sudah ada. Algoritma inti tidak ditulis ulang.

## Menjalankan di komputer

1. Buka terminal di folder proyek.
2. Instal dependensi:
   ```bash
   pip install -r requirements.txt
   ```
3. Jalankan aplikasi web:
   ```bash
   python flask_app.py
   ```
4. Buka `http://127.0.0.1:5000` di browser.

## Menjalankan di Google Colab

Unggah dan ekstrak folder proyek terlebih dahulu, lalu jalankan di cell:

```python
%cd /content/penjadwalan_ag_uts
!pip install -r requirements.txt
!python flask_app.py
```

Agar bisa dibuka dari browser di luar Colab, server perlu diteruskan menggunakan layanan tunnel seperti Cloudflare Tunnel atau localtunnel. Jangan membagikan URL tunnel yang sedang aktif kepada orang yang tidak dipercaya.

## Catatan integrasi

- File Excel unggahan harus memiliki sheet dan kolom sesuai `data_loader.py` (`Data Jadwal`, `Slot Waktu`, `Ruang`, `Dosen`).
- Data bawaan diambil dari `data/Data_Jadwal_TI_UPR_Semester_1_3_5.xlsx`.
- Kapasitas ruang dan jumlah mahasiswa di `config.py` masih diberi label placeholder di proyek asal. Periksa dan ganti dengan data sebenarnya sebelum menganggap hasil optimasi sebagai jadwal final.
- Backend (ga.py, ga_api.py, config.py, data_loader.py, data Excel) disamakan dengan proyek penjadwalan AG. Server memakai API yang sama: proses GA berjalan di thread dan UI memantau progres lewat `/api/job/<id>`.
- UI mengikuti alur AG: progres langsung, grafik konvergensi live, grid hari × waktu proporsional, filter per semester/kelas/dosen/ruang, slider evolusi generasi, dan bagian Asli vs AG.
- Satu permintaan menjalankan satu seed/run. Batch banyak run dan perbandingan operator masih ada di `app.py` (Streamlit).
- Satu tes di `tests/test_fitness.py` (`test_jadwal_asli_punya_bentrok_dosen`) gagal juga di proyek AG asli dengan data Excel terbaru.
- Font dan Chart.js disimpan lokal di `static/` (tanpa CDN), jadi demo bisa berjalan tanpa internet.
- v6: judul diganti menjadi "Susun jadwal kuliah tanpa bentrok", font disesuaikan dengan berkas di `static/fonts`, bagian bernomor 01-04, kartu status hasil, dan legenda warna semester.
