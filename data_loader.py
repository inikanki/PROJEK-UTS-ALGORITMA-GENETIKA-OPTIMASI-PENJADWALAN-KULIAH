"""Membaca Excel -> objek Problem (entitas, slot, matriks overlap, domain gen)."""
import re
import numpy as np
import pandas as pd
import config


def _menit(txt):
    h, m = txt.strip().split(".")
    return int(h) * 60 + int(m)


def parse_slot(label):
    a, b = re.split(r"[–-]", label.strip())
    return _menit(a), _menit(b)


class Problem:
    """Semua data masalah dalam bentuk array siap pakai untuk GA."""
    pass


def load_problem(path=config.DATA_PATH):
    xl = pd.ExcelFile(path)
    jad = xl.parse("Data Jadwal")
    slot_df = xl.parse("Slot Waktu")
    ruang_df = xl.parse("Ruang")
    dosen_df = xl.parse("Dosen")
    kol_dosen = "Dosen Mata Kuliah/Pendamping"

    # --- normalisasi nama dosen (mis. 2 penulisan "Christian Novan") ---
    kunci = lambda n: n.split(",")[0].strip().lower()
    canon = {}
    for n in list(dosen_df["Nama Dosen"].dropna()) + list(jad[kol_dosen].dropna()):
        n = n.strip()
        k = kunci(n)
        if k not in canon or len(n) > len(canon[k]):
            canon[k] = n
    dosen_list = sorted(set(canon.values()))
    dosen_idx = {d: i for i, d in enumerate(dosen_list)}

    p = Problem()
    # --- slot waktu ---
    p.slot_id = slot_df["ID Slot"].tolist()
    p.slot_hari = slot_df["Hari"].tolist()
    p.slot_label = slot_df["Slot Waktu"].tolist()
    mm = [parse_slot(l) for l in p.slot_label]
    p.slot_mulai = np.array([a for a, _ in mm])
    p.slot_selesai = np.array([b for _, b in mm])
    p.slot_durasi = p.slot_selesai - p.slot_mulai
    p.n_slot = len(p.slot_id)
    hari = np.array(p.slot_hari)
    p.OV = ((hari[:, None] == hari[None, :])
            & (p.slot_mulai[:, None] < p.slot_selesai[None, :])
            & (p.slot_mulai[None, :] < p.slot_selesai[:, None]))
    slot_idx = {(h, l): i for i, (h, l) in enumerate(zip(p.slot_hari, p.slot_label))}

    # --- ruang ---
    p.ruang = ruang_df["Ruang"].tolist()
    p.n_ruang = len(p.ruang)
    ruang_idx = {r: i for i, r in enumerate(p.ruang)}
    p.cap = np.array([config.KAPASITAS_RUANG.get(r, config.KAPASITAS_DEFAULT) for r in p.ruang])

    # --- sesi kuliah (= gen) ---
    p.mk, p.semester, p.kelas, p.dosen = [], [], [], []
    p.koordinator, p.hari_asli, p.slot_asli, p.ruang_asli = [], [], [], []
    size = []
    for _, r in jad.iterrows():
        p.mk.append(r["Mata Kuliah"])
        p.semester.append(int(r["Semester"]))
        p.kelas.append(str(r["Kelas"]))
        d = canon[kunci(r[kol_dosen])]
        p.dosen.append(d)
        p.koordinator.append(r["Koordinator Mata Kuliah"] if pd.notna(r["Koordinator Mata Kuliah"]) else "")
        p.slot_asli.append(slot_idx[(r["Hari"], r["Slot Waktu"])])
        p.ruang_asli.append(ruang_idx[r["Ruang"]])
        # jumlah mahasiswa: pakai kolom "Jmlh mhs" di Excel bila ada & terisi,
        # selain itu jatuh ke asumsi di config.py (JUMLAH_MHS_*)
        if "Jmlh mhs" in jad.columns and pd.notna(r["Jmlh mhs"]):
            size.append(int(r["Jmlh mhs"]))
        else:
            size.append(config.JUMLAH_MHS_OVERRIDE.get(r["Mata Kuliah"],
                                                        config.JUMLAH_MHS_KELAS[str(r["Kelas"])]))
    p.n_sesi = len(p.mk)
    p.size = np.array(size)
    p.slot_asli = np.array(p.slot_asli)
    p.ruang_asli = np.array(p.ruang_asli)
    p.durasi = p.slot_durasi[p.slot_asli]          # durasi wajib per sesi (dari jadwal asli)
    p.dosen_id = np.array([dosen_idx[d] for d in p.dosen])
    p.n_dosen = len(dosen_list)

    # domain slot tiap gen: hanya slot dengan durasi sama (kendala keras durasi/SKS)
    p.domain = [np.where(p.slot_durasi == p.durasi[i])[0] for i in range(p.n_sesi)]

    # --- matriks pasangan sesi yang berpotensi bentrok ---
    S = p.n_sesi
    is_agama = np.array([m.startswith("Agama") for m in p.mk])
    p.same_dosen = p.dosen_id[:, None] == p.dosen_id[None, :]
    sem = np.array(p.semester)
    kel = np.array(p.kelas)
    same_sem = sem[:, None] == sem[None, :]
    kelas_irisan = (kel[:, None] == kel[None, :]) | (kel[:, None] == "-") | (kel[None, :] == "-")
    # mata kuliah agama saling paralel (mhs hanya ambil satu) -> tidak dianggap bentrok kelas
    p.class_conflict = same_sem & kelas_irisan & ~(is_agama[:, None] & is_agama[None, :])
    np.fill_diagonal(p.same_dosen, False)
    np.fill_diagonal(p.class_conflict, False)
    p.is_agama = is_agama
    return p