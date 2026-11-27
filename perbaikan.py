"""Operator perbaikan (repair) untuk gen bentrok.

Ide: sesi yang melanggar kendala keras dipindahkan ke pasangan (slot, ruang) di domainnya yang
menimbulkan pelanggaran paling sedikit terhadap sesi lain (best-fit relocation). Sisa seri dipilih acak
agar tidak menghilangkan keragaman populasi.

Dipakai oleh:
  * ga.py          -> repair operator pada sebagian anak tiap generasi
  * pembanding.py  -> konstruksi jadwal Greedy (menempatkan sesi satu per satu)
"""
import numpy as np


def biaya_penempatan(p, i, slots, rooms, aktif):
    """Matriks biaya (D, n_ruang) menempatkan sesi i di tiap (slot domain[i], ruang).

    biaya = #bentrok dosen/kelas (slot beririsan) + #bentrok ruang (slot beririsan, ruang sama)
            + 1 bila kapasitas ruang < jumlah mahasiswa.
    `aktif` = mask sesi lain yang sudah ditempatkan (sesi i sendiri diabaikan).
    """
    dom = p.domain[i]
    mask = aktif.copy()
    mask[i] = False
    j = np.where(mask)[0]
    ov = p.OV[np.ix_(dom, slots[j])]                                     # (D, J) slot beririsan?
    c_slot = (ov & (p.same_dosen[i, j] | p.class_conflict[i, j])[None, :]).sum(1)
    onehot = np.zeros((len(j), p.n_ruang), dtype=np.int64)
    onehot[np.arange(len(j)), rooms[j]] = 1
    c_ruang = ov.astype(np.int64) @ onehot                              # (D, n_ruang)
    c_kap = (p.size[i] > p.cap).astype(np.int64)                        # (n_ruang,)
    return c_slot[:, None] + c_ruang + c_kap[None, :]


def pilih_acak_minimum(biaya, rng):
    """Indeks (baris, kolom) dari salah satu sel bernilai minimum (seri dipilih acak)."""
    kandidat = np.argwhere(biaya == biaya.min())
    return kandidat[rng.integers(len(kandidat))]


def sesi_bermasalah(p, slots, rooms):
    """Indeks sesi yang terlibat pelanggaran keras (dosen / kelas / ruang / kapasitas)."""
    ov = p.OV[np.ix_(slots, slots)]
    np.fill_diagonal(ov, False)
    bentrok = ov & (p.same_dosen | p.class_conflict | (rooms[:, None] == rooms[None, :]))
    return np.where(bentrok.any(1) | (p.size > p.cap[rooms]))[0]


def perbaiki_individu(p, slots, rooms, rng, maks_pindah=4):
    """Perbaiki SATU individu di tempat (in-place). Return jumlah sesi yang dipindahkan."""
    aktif = np.ones(p.n_sesi, dtype=bool)
    bad = sesi_bermasalah(p, slots, rooms)
    if len(bad) == 0:
        return 0
    rng.shuffle(bad)
    pindah = 0
    for i in bad[:maks_pindah]:
        biaya = biaya_penempatan(p, i, slots, rooms, aktif)
        dom = p.domain[i]
        sekarang = biaya[np.searchsorted(dom, slots[i]), rooms[i]]
        a, b = pilih_acak_minimum(biaya, rng)
        if biaya[a, b] < sekarang:                       # hanya pindah bila benar-benar membaik
            slots[i], rooms[i] = dom[a], b
            pindah += 1
    return pindah


def perbaiki_populasi(p, slots, rooms, indeks, rng, maks_pindah=4):
    """Terapkan repair pada baris-baris `indeks` dari populasi (in-place)."""
    return sum(perbaiki_individu(p, slots[k], rooms[k], rng, maks_pindah) for k in indeks)
