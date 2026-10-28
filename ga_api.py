"""Antarmuka backend untuk tim desain / UI. Semua fungsi mengembalikan dict/list yang bisa di-JSON-kan.

    from ga_api import info_data, jalankan_ga, validasi_jadwal, jadwal_asli

    info_data()                                   # halaman A: ringkasan data, daftar ruang/slot/dosen
    jalankan_ga(params, seed, on_progress=fn,     # halaman B: fn(gen, total, best_fitness, mean_fitness, violations)
                snapshot_every=10)                # halaman D/animasi: jadwal terbaik tiap 10 generasi
    validasi_jadwal(sesi_list)                    # drag & drop: cek bentrok setelah pengguna memindah blok
    jadwal_asli()                                 # banding "Jadwal Asli vs Hasil AG"
"""
import numpy as np

import config
from data_loader import load_problem
from export import jadwal_df
from fitness import NAMA_KENDALA, Evaluator, jeda_panjang
from ga import GeneticAlgorithm

_cache = {}


def _problem(path):
    path = str(path)
    if path not in _cache:
        _cache[path] = load_problem(path)
    return _cache[path]


def _jam(menit):
    return f"{menit // 60:02d}.{menit % 60:02d}"


def _baris(p, slots, rooms):
    """Satu dict per sesi. `id` = indeks sesi (gen), stabil antar run -> dipakai UI untuk drag & drop.
    mulai_menit/selesai_menit = menit sejak 00:00 (untuk grid dengan sumbu waktu proporsional)."""
    rows = []
    for i in range(p.n_sesi):
        s = int(slots[i])
        rows.append({
            "id": i, "Hari": p.slot_hari[s], "Slot Waktu": p.slot_label[s], "slot_id": p.slot_id[s],
            "mulai_menit": int(p.slot_mulai[s]), "selesai_menit": int(p.slot_selesai[s]),
            "durasi_menit": int(p.slot_durasi[s]),
            "Mata Kuliah": p.mk[i], "Semester": p.semester[i], "Kelas": p.kelas[i],
            "Ruang": p.ruang[int(rooms[i])], "Dosen": p.dosen[i],
        })
    urut = {h: k for k, h in enumerate(config.HARI_URUT)}
    rows.sort(key=lambda r: (urut[r["Hari"]], r["mulai_menit"], r["Semester"], r["Kelas"]))
    return rows


def _rincian(p, slots, rooms):
    r = Evaluator(p).rincian(np.asarray(slots), np.asarray(rooms))[0]
    d = dict(zip(NAMA_KENDALA, map(int, r)))
    return d, int(sum(d.values()))


def rincian_detail(p, slots, rooms):
    """Daftar pelanggaran kendala keras satu per satu (bukan hanya jumlahnya), supaya UI bisa menjelaskan
    sesi mana yang bermasalah dan kenapa. Aturan sama persis dengan Evaluator.rincian."""
    slots, rooms = np.asarray(slots), np.asarray(rooms)

    def sesi(i):
        s = int(slots[i])
        return {"id": int(i), "mk": p.mk[i], "semester": int(p.semester[i]), "kelas": p.kelas[i],
                "dosen": p.dosen[i], "ruang": p.ruang[int(rooms[i])], "hari": p.slot_hari[s],
                "slot": p.slot_label[s], "mhs": int(p.size[i])}

    out = []
    n = p.n_sesi
    for i in range(n):
        for j in range(i + 1, n):
            if not p.OV[slots[i], slots[j]]:
                continue
            a, b = sesi(i), sesi(j)
            for jenis, cocok, alasan in (
                    ("dosen", p.same_dosen[i, j], "Dosen {d} mengajar dua kelas pada waktu yang beririsan"),
                    ("kelas", p.class_conflict[i, j], "Mahasiswa semester {s} kelas yang sama harus hadir di dua kuliah bersamaan"),
                    ("ruang", rooms[i] == rooms[j], "Ruang {r} dipakai dua kuliah pada waktu yang beririsan")):
                if cocok:
                    out.append({"jenis": jenis, "sesi": [a, b],
                                "alasan": alasan.format(d=a["dosen"], s=a["semester"], r=a["ruang"])})
    for i in range(n):
        if p.size[i] > p.cap[rooms[i]]:
            out.append({"jenis": "kapasitas", "sesi": [sesi(i)],
                        "alasan": f"{p.size[i]} mahasiswa, tetapi kapasitas ruang {p.ruang[int(rooms[i])]} hanya {int(p.cap[rooms[i]])}"})
        if p.slot_durasi[slots[i]] != p.durasi[i]:
            out.append({"jenis": "durasi", "sesi": [sesi(i)],
                        "alasan": f"Durasi slot {int(p.slot_durasi[slots[i]])} menit, seharusnya {int(p.durasi[i])} menit"})
    return out


def info_data(data_path=config.DATA_PATH):
    """Untuk halaman Data & Pengaturan."""
    p = _problem(data_path)
    return {
        "jumlah": {"sesi": p.n_sesi, "dosen": p.n_dosen, "ruang": p.n_ruang, "slot": p.n_slot},
        "ruang": [{"nama": r, "kapasitas": int(c)} for r, c in zip(p.ruang, p.cap)],
        "slot": [{"id": p.slot_id[i], "hari": p.slot_hari[i], "label": p.slot_label[i],
                  "mulai_menit": int(p.slot_mulai[i]), "selesai_menit": int(p.slot_selesai[i])}
                 for i in range(p.n_slot)],
        "dosen": sorted(set(p.dosen)),
        "parameter_default": dict(config.PARAM_DEFAULT),
        "kendala": list(NAMA_KENDALA),
    }


def jadwal_asli(data_path=config.DATA_PATH):
    """Jadwal dari Excel + jumlah pelanggarannya (pembanding di UI)."""
    p = _problem(data_path)
    rinc, total = _rincian(p, p.slot_asli, p.ruang_asli)
    return {"jadwal": _baris(p, p.slot_asli, p.ruang_asli), "rincian_pelanggaran": rinc,
            "pelanggaran": total, "jeda_panjang_soft": int(jeda_panjang(p, p.slot_asli)),
            "detail_pelanggaran": rincian_detail(p, p.slot_asli, p.ruang_asli)}


def validasi_jadwal(sesi, data_path=config.DATA_PATH):
    """Cek jadwal hasil edit manual. `sesi` = list {id, slot_id, ruang} (lengkap, semua sesi).
    Mengembalikan pelanggaran per kendala dan daftar id sesi yang ikut bentrok."""
    p = _problem(data_path)
    if len(sesi) != p.n_sesi:
        raise ValueError(f"harus berisi {p.n_sesi} sesi, diterima {len(sesi)}")
    slots, rooms = np.zeros(p.n_sesi, int), np.zeros(p.n_sesi, int)
    for x in sesi:
        slots[x["id"]] = p.slot_id.index(x["slot_id"])
        rooms[x["id"]] = p.ruang.index(x["ruang"])
    rinc, total = _rincian(p, slots, rooms)
    # sesi bermasalah: pasangan yang beririsan waktu dan berbagi dosen / ruang / kelas
    ov = p.OV[slots][:, slots]
    np.fill_diagonal(ov, False)
    bentrok = ov & (p.same_dosen | p.class_conflict | (rooms[:, None] == rooms[None, :]))
    bermasalah = set(np.where(bentrok.any(axis=1))[0].tolist())
    bermasalah |= set(np.where(p.size > p.cap[rooms])[0].tolist())
    bermasalah |= set(np.where(p.slot_durasi[slots] != p.durasi)[0].tolist())
    return {"rincian_pelanggaran": rinc, "pelanggaran": total, "valid": total == 0,
            "jeda_panjang_soft": int(jeda_panjang(p, slots)), "sesi_bermasalah": sorted(bermasalah)}


def jalankan_ga(params=None, seed=None, data_path=config.DATA_PATH, on_progress=None, snapshot_every=0):
    p = _problem(data_path)
    prm = {**config.PARAM_DEFAULT, **(params or {})}
    cb = None
    if on_progress:
        cb = lambda g, i: on_progress(g, i["total"], i["best_fitness"], i["mean_fitness"], i["violations"])
    h = GeneticAlgorithm(p, seed=seed, **prm).run(callback=cb, snapshot_every=snapshot_every)
    rows = _baris(p, h["best_slots"], h["best_rooms"])
    df = jadwal_df(p, h["best_slots"], h["best_rooms"])
    grid = {}
    for _, r in df.iterrows():
        grid.setdefault(r["Hari"], {}).setdefault(r["Slot Waktu"], []).append(
            f"{r['Mata Kuliah']} ({r['Kelas']}) [{r['Ruang']}] - {r['Dosen']}")
    return {
        "parameter": prm,
        "seed": seed,
        "fitness_terbaik": h["best_fitness"],
        "pelanggaran": h["best_violations"],
        "rincian_pelanggaran": dict(zip(NAMA_KENDALA, map(int, h["rincian"]))),
        "jeda_panjang_soft": jeda_panjang(p, h["best_slots"]),
        "detail_pelanggaran": rincian_detail(p, h["best_slots"], h["best_rooms"]),
        "generasi_valid_pertama": h["gen_valid_pertama"],
        "waktu_detik": h["waktu"],
        "jadwal": rows,
        "grid": grid,
        "riwayat": {"fitness_terbaik": h["hist_best"], "fitness_rata2": h["hist_mean"],
                    "pelanggaran": h["hist_viol"]},
        "snapshots": [{"generasi": s["gen"], "pelanggaran": s["violations"],
                       "jadwal": _baris(p, s["slots"], s["rooms"])} for s in h["snapshots"]],
    }
