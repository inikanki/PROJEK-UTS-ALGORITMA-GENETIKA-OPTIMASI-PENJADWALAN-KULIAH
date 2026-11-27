"""Membuat dataset skala UAS: 60 sesi kuliah, 20 dosen, 10 ruang, 21 slot waktu.

DATA INI SINTETIS (dibangkitkan dengan seed tetap), mengikuti skala yang diminta dosen untuk UAS
(~60 mata kuliah, 20 dosen, 10 ruang) dan format Excel yang sama dengan data asli UTS
(sheet: Data Jadwal, Slot Waktu, Ruang, Dosen, Mata Kuliah). Daftar slot waktu dan nama ruang
diambil dari data asli prodi; nama mata kuliah mengikuti kurikulum Teknik Informatika secara umum,
nama dosen dianonimkan. Ganti file ini dengan data prodi sebenarnya bila sudah tersedia
(cukup unggah lewat aplikasi atau pakai --data).

    python buat_data_uas.py            # -> data/Data_Jadwal_UAS_Sintetis.xlsx
"""
import numpy as np
import pandas as pd

import config

SEED = 2026
OUT = config.BASE / "data" / "Data_Jadwal_UAS_Sintetis.xlsx"

# (nama MK, SKS-panjang?)  True = 3 SKS (slot 150 menit), False = 2 SKS (slot 100 menit)
MK = {
    1: [("Aljabar Linear Matriks", True), ("Kalkulus", True), ("Algoritma dan Pemrograman", True),
        ("Pengantar Teknologi Informasi", False), ("Logika Informatika", True),
        ("Bahasa Inggris", False), ("Fisika Dasar", True)],
    3: [("Struktur Data", True), ("Basis Data", True), ("Arsitektur Komputer", True),
        ("Statistika", True), ("Sistem Operasi", True), ("Matematika Diskrit", False),
        ("Pemrograman Berorientasi Objek", True)],
    5: [("Metodologi Penelitian", False), ("Analisis dan Desain Perangkat Lunak", True),
        ("Kecerdasan Buatan", True), ("Jaringan Komputer", True), ("Pemrograman Web", True),
        ("Algoritma Genetika", True), ("Pengolahan Citra Digital", True)],
    7: [("Keamanan Informasi", True), ("Data Mining", True), ("Manajemen Proyek TI", False),
        ("Komputasi Awan", True), ("Sistem Pakar", True), ("Interaksi Manusia dan Komputer", True),
        ("Etika Profesi", False)],
}
AGAMA = [("Agama Islam", 32), ("Agama Kristen", 50), ("Agama Katolik", 6), ("Agama Hindu/Kaharingan", 1)]


def main():
    rng = np.random.default_rng(SEED)
    asli = pd.ExcelFile(config.DATA_PATH)
    slot = asli.parse("Slot Waktu")
    ruang = asli.parse("Ruang")
    ruang = ruang[ruang["Ruang"] != "PRIVAT"].reset_index(drop=True)      # 10 ruang
    assert len(ruang) == 10

    dosen = [f"Dosen {i:02d}, M.Kom." for i in range(1, 21)]            # 20 dosen (anonim)
    # satu sesi = (semester, kelas, MK, panjang, jumlah mhs)
    sesi = []
    for sem, daftar in MK.items():
        for nama, panjang in daftar:
            for kls in ("A", "B"):
                sesi.append((sem, kls, nama, panjang, int(rng.integers(38, 53))))
    for nama, n in AGAMA:
        sesi.append((1, "-", nama, True, n))
    assert len(sesi) == 60

    # tiap dosen mengampu tepat 3 sesi (beban seimbang), diacak
    pemilik = rng.permutation(np.repeat(np.arange(20), 3))
    koordinator = {}
    slot["durasi"] = [(lambda a, b: (int(b[:2]) * 60 + int(b[3:])) - (int(a[:2]) * 60 + int(a[3:])))(
        *s.replace("–", "-").split("-")) for s in slot["Slot Waktu"]]

    baris = []
    for k, (sem, kls, nama, panjang, n) in enumerate(sesi):
        durasi = 150 if panjang else 100
        pilih = slot[slot["durasi"] == durasi].sample(1, random_state=int(rng.integers(1_000_000))).iloc[0]
        d = dosen[pemilik[k]]
        koordinator.setdefault(nama, d)
        baris.append({"Hari": pilih["Hari"], "Slot Waktu": pilih["Slot Waktu"], "Mata Kuliah": nama,
                      "Semester": sem, "Kelas": kls, "Ruang": ruang["Ruang"].iloc[int(rng.integers(10))],
                      "Dosen Mata Kuliah/Pendamping": d, "Koordinator Mata Kuliah": koordinator[nama],
                      "Jmlh mhs": n})
    jad = pd.DataFrame(baris)

    mk_df = pd.DataFrame([{"Angkatan/Semester": f"Semester {s}", "Semester": s, "Mata Kuliah": n}
                          for s, ds in MK.items() for n, _ in ds])
    OUT.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as w:
        jad.to_excel(w, sheet_name="Data Jadwal", index=False)
        mk_df.to_excel(w, sheet_name="Mata Kuliah", index=False)
        pd.DataFrame({"Nama Dosen": dosen}).to_excel(w, sheet_name="Dosen", index=False)
        ruang.to_excel(w, sheet_name="Ruang", index=False)
        slot.drop(columns="durasi").to_excel(w, sheet_name="Slot Waktu", index=False)
    print(f"Tersimpan: {OUT}  ({len(jad)} sesi, {len(dosen)} dosen, {len(ruang)} ruang, {len(slot)} slot)")


if __name__ == "__main__":
    main()
