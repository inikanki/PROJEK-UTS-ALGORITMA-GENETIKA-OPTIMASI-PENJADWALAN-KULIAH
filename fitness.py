"""Fungsi fitness berbasis penalti kendala keras + validator independen + kendala lunak."""
import numpy as np

NAMA_KENDALA = ["dosen", "kelas", "ruang", "kapasitas", "durasi"]


class Evaluator:
    """Hitung pelanggaran kendala keras untuk populasi sekaligus (vectorized).

    Kromosom = dua array int (slots, rooms) berukuran (N, n_sesi).
    fitness = 1 / (1 + total_pelanggaran)   -> 1.0 berarti jadwal valid.
    """

    def __init__(self, p):
        self.p = p
        self.I, self.J = np.triu_indices(p.n_sesi, 1)
        self.m_dosen = p.same_dosen[self.I, self.J]
        self.m_kelas = p.class_conflict[self.I, self.J]

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
        return self.rincian(slots, rooms).sum(1)

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
    """KENDALA LUNAK (hanya dilaporkan, belum dioptimalkan di UTS):
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
