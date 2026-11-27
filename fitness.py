"""Fungsi fitness berbasis penalti: kendala keras (bobot besar) + kendala lunak (bobot kecil) + validator independen.

UAS: penalti = w_hard*keras + w_jeda*jeda_panjang + w_beban*beban_dosen + w_sore*sesi_sore ; fitness = 1/(1+penalti).
Dengan BOBOT_UTS (w_hard=1, lunak=0) rumusnya identik dengan fitness UTS: 1/(1+pelanggaran).
"""
import numpy as np

import config

NAMA_KENDALA = ["dosen", "kelas", "ruang", "kapasitas", "durasi"]
NAMA_LUNAK = ["jeda_panjang", "beban_dosen", "sesi_sore"]


class Evaluator:
    """Hitung pelanggaran kendala keras untuk populasi sekaligus (vectorized).

    Kromosom = dua array int (slots, rooms) berukuran (N, n_sesi).
    fitness = 1 / (1 + total_pelanggaran)   -> 1.0 berarti jadwal valid.
    """

    def __init__(self, p, bobot=None, batas=None):
        self.p = p
        self.I, self.J = np.triu_indices(p.n_sesi, 1)
        self.m_dosen = p.same_dosen[self.I, self.J]
        self.m_kelas = p.class_conflict[self.I, self.J]
        # ---- bobot & parameter kendala lunak ----
        b = {**config.BOBOT_DEFAULT, **(bobot or {})}
        self.w_hard, self.w_jeda = float(b["w_hard"]), float(b["w_jeda"])
        self.w_beban, self.w_sore = float(b["w_beban"]), float(b["w_sore"])
        bt = {**config.SOFT_BATAS, **(batas or {})}
        self.batas_jeda, self.maks_hari, self.sore = bt["batas_jeda"], bt["maks_sesi_hari"], bt["sore_selesai"]
        # ---- prakomputasi lunak ----
        urut = {h: k for k, h in enumerate(config.HARI_URUT)}
        self.hari_slot = np.array([urut[h] for h in p.slot_hari])
        self.mulai, self.selesai = np.asarray(p.slot_mulai), np.asarray(p.slot_selesai)
        self.sore_slot = (self.selesai > self.sore).astype(np.int64)
        sem, kls = np.array(p.semester), np.array(p.kelas)
        self.grup_jeda = []                          # tiap (semester, kelas A/B): indeks sesi non-agama
        for s in sorted(set(p.semester)):
            for k in ("A", "B"):
                idx = np.where((sem == s) & ((kls == k) | (kls == "-")) & ~np.asarray(p.is_agama))[0]
                if len(idx) >= 2:
                    self.grup_jeda.append(idx)
        self.M_dosen = np.zeros((p.n_sesi, p.n_dosen))
        self.M_dosen[np.arange(p.n_sesi), p.dosen_id] = 1.0

    def rincian(self, slots, rooms):
        """Return array (N, 5): pelanggaran per jenis kendala keras."""
        p = self.p
        slots = np.atleast_2d(slots)
        rooms = np.atleast_2d(rooms)
        ov = p.OV[slots[:, self.I], slots[:, self.J]]
        same_room = rooms[:, self.I] == rooms[:, self.J]
        v_dosen = (ov & self.m_dosen).sum(1)
        v_kelas = (ov & self.m_kelas).sum(1)
        v_ruang = (ov & same_room).sum(1)
        v_kap = (p.size[None, :] > p.cap[rooms]).sum(1)
        v_dur = (p.slot_durasi[slots] != p.durasi[None, :]).sum(1)
        return np.stack([v_dosen, v_kelas, v_ruang, v_kap, v_dur], axis=1)

    def total(self, slots, rooms):
        """Jumlah pelanggaran KERAS per individu (N,)."""
        return self.rincian(slots, rooms).sum(1)

    def lunak(self, slots):
        """Return (N, 3): [jeda_panjang, beban_dosen, sesi_sore] untuk tiap individu (tervektorisasi)."""
        slots = np.atleast_2d(slots)
        N = len(slots)
        # (1) jeda panjang: urutkan sesi tiap kelas per (hari, mulai, selesai); hitung jeda berurutan > batas
        jeda = np.zeros(N)
        for g in self.grup_jeda:
            sl = slots[:, g]
            h, a, b = self.hari_slot[sl], self.mulai[sl], self.selesai[sl]
            o = np.argsort(h * 10_000_000 + a * 2000 + b, axis=1, kind="stable")
            h, a, b = (np.take_along_axis(x, o, axis=1) for x in (h, a, b))
            jeda += ((h[:, 1:] == h[:, :-1]) & (a[:, 1:] - b[:, :-1] > self.batas_jeda)).sum(1)
        # (2) beban dosen: kelebihan sesi per hari di atas maks_sesi_hari
        hs = self.hari_slot[slots]
        beban = np.zeros(N)
        for d in range(len(config.HARI_URUT)):
            cnt = (hs == d).astype(float) @ self.M_dosen                    # (N, n_dosen)
            beban += np.maximum(0, cnt - self.maks_hari).sum(1)
        # (3) sesi sore
        sore = self.sore_slot[slots].sum(1)
        return np.stack([jeda, beban, sore], axis=1)

    def evaluasi(self, slots, rooms):
        """Return (keras, lunak_berbobot, penalti) masing-masing (N,). penalti = w_hard*keras + lunak_berbobot."""
        keras = self.total(slots, rooms)
        L = self.lunak(slots)
        lunak_w = L @ np.array([self.w_jeda, self.w_beban, self.w_sore])
        return keras, lunak_w, self.w_hard * keras + lunak_w

    @staticmethod
    def fitness_dari_pelanggaran(v):
        return 1.0 / (1.0 + v)


def validasi_independen(p, slots, rooms):
    """Pengecekan versi loop biasa (lambat tapi mudah dibaca) -> dipakai untuk unit test."""
    c = dict.fromkeys(NAMA_KENDALA, 0)
    for i in range(p.n_sesi):
        if p.size[i] > p.cap[rooms[i]]:
            c["kapasitas"] += 1
        if p.slot_durasi[slots[i]] != p.durasi[i]:
            c["durasi"] += 1
        for j in range(i + 1, p.n_sesi):
            if not p.OV[slots[i], slots[j]]:
                continue
            if p.same_dosen[i, j]:
                c["dosen"] += 1
            if p.class_conflict[i, j]:
                c["kelas"] += 1
            if rooms[i] == rooms[j]:
                c["ruang"] += 1
    return c


def jeda_panjang(p, slots, batas_menit=90):
    """KENDALA LUNAK #1 (UAS: ikut dioptimalkan lewat Evaluator.lunak):
    jumlah jeda > batas_menit di antara dua kuliah pada hari yang sama untuk tiap kelas.
    Mata kuliah agama dilewati (mahasiswa hanya mengambil satu)."""
    total = 0
    for sem in sorted(set(p.semester)):
        for kls in ("A", "B"):
            idx = [i for i in range(p.n_sesi)
                   if p.semester[i] == sem and p.kelas[i] in (kls, "-") and not p.is_agama[i]]
            per_hari = {}
            for i in idx:
                s = slots[i]
                per_hari.setdefault(p.slot_hari[s], []).append((p.slot_mulai[s], p.slot_selesai[s]))
            for lst in per_hari.values():
                lst.sort()
                for (a1, b1), (a2, b2) in zip(lst, lst[1:]):
                    if a2 - b1 > batas_menit:
                        total += 1
    return total


def lunak_independen(p, slots, batas=None):
    """Versi loop biasa dari kendala lunak (untuk unit test). Return dict {jeda_panjang, beban_dosen, sesi_sore}."""
    bt = {**config.SOFT_BATAS, **(batas or {})}
    jeda = jeda_panjang(p, slots, bt["batas_jeda"])
    beban = 0
    for d in range(p.n_dosen):
        per_hari = {}
        for i in range(p.n_sesi):
            if p.dosen_id[i] == d:
                per_hari[p.slot_hari[slots[i]]] = per_hari.get(p.slot_hari[slots[i]], 0) + 1
        beban += sum(max(0, c - bt["maks_sesi_hari"]) for c in per_hari.values())
    sore = sum(1 for i in range(p.n_sesi) if p.slot_selesai[slots[i]] > bt["sore_selesai"])
    return {"jeda_panjang": int(jeda), "beban_dosen": int(beban), "sesi_sore": int(sore)}
