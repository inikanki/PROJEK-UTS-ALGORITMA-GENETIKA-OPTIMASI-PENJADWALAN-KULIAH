"""Metode pembanding untuk AG: Hill Climbing, Simulated Annealing, dan Greedy (konstruktif acak).

Semua metode memakai representasi yang sama dengan AG (slots, rooms per sesi) dan Evaluator yang sama
(penalti berbobot UAS), sehingga hasilnya langsung sebanding. Hill Climbing dan Simulated Annealing diberi
ANGGARAN EVALUASI FITNESS yang sama dengan AG (pop_size x (generasi+1)) agar perbandingannya adil.
Greedy bersifat konstruktif (sekali jalan) sehingga hanya melihat kendala keras.

Setiap fungsi mengembalikan dict berkunci sama dengan AG:
  best_slots, best_rooms, best_violations (keras), best_penalti, best_lunak, waktu, evaluasi, hist_pen
"""
import math
import time

import numpy as np

from perbaikan import biaya_penempatan, pilih_acak_minimum


def _acak(p, rng):
    s = np.array([rng.choice(p.domain[i]) for i in range(p.n_sesi)], dtype=np.int64)
    r = rng.integers(0, p.n_ruang, size=p.n_sesi)
    return s, r


def _hasil(ev, s, r, t0, evaluasi, hist):
    keras, lunak, pen = ev.evaluasi(s[None, :], r[None, :])
    return dict(best_slots=s.copy(), best_rooms=r.copy(), best_violations=int(keras[0]),
                best_penalti=float(pen[0]), best_lunak=float(lunak[0]),
                waktu=time.perf_counter() - t0, evaluasi=int(evaluasi), hist_pen=hist)


def hill_climbing(p, ev, seed=None, anggaran=30_000):
    """Hill Climbing relokasi (best-improvement dengan langkah menyamping).

    Tiap iterasi: pilih satu sesi acak, evaluasi SEMUA pasangan (slot, ruang) tujuannya sekaligus,
    pindah ke yang terbaik bila tidak lebih buruk dari posisi sekarang (langkah menyamping diizinkan
    agar tidak mudah macet di plateau)."""
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    s, r = _acak(p, rng)
    pen = float(ev.evaluasi(s[None, :], r[None, :])[2][0])
    used, hist = 1, [pen]
    while True:
        i = int(rng.integers(p.n_sesi))
        dom = p.domain[i]
        D, R = len(dom), p.n_ruang
        if used + D * R > anggaran:
            break
        cs = np.tile(s, (D * R, 1)); cr = np.tile(r, (D * R, 1))
        cs[:, i] = np.repeat(dom, R)
        cr[:, i] = np.tile(np.arange(R), D)
        pc = ev.evaluasi(cs, cr)[2]
        used += D * R
        terbaik = np.flatnonzero(pc == pc.min())
        k = int(rng.choice(terbaik))
        if pc[k] <= pen:
            s, r, pen = cs[k].copy(), cr[k].copy(), float(pc[k])
        hist.append(pen)
    return _hasil(ev, s, r, t0, used, hist)


def simulated_annealing(p, ev, seed=None, anggaran=30_000, T0=None, T_akhir=0.3):
    """Simulated Annealing dengan pendinginan geometrik. Satu langkah = ubah satu sesi (slot dan/atau ruang).

    T0 default = 0.5*w_hard (di awal pelanggaran keras masih bisa diterima), T_akhir ~ skala kendala lunak."""
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    T0 = 0.5 * ev.w_hard if T0 is None else T0
    alpha = (T_akhir / T0) ** (1.0 / max(1, anggaran - 1))
    s, r = _acak(p, rng)
    pen = float(ev.evaluasi(s[None, :], r[None, :])[2][0])
    best = (s.copy(), r.copy(), pen)
    T, hist = T0, [pen]
    for k in range(1, anggaran):
        i = int(rng.integers(p.n_sesi))
        s0, r0 = s[i], r[i]
        if rng.random() < 0.7:
            s[i] = rng.choice(p.domain[i])
        if rng.random() < 0.6 or s[i] == s0:
            r[i] = rng.integers(p.n_ruang)
        pn = float(ev.evaluasi(s[None, :], r[None, :])[2][0])
        d = pn - pen
        if d <= 0 or rng.random() < math.exp(-d / T):
            pen = pn
            if pen < best[2]:
                best = (s.copy(), r.copy(), pen)
        else:
            s[i], r[i] = s0, r0
        T *= alpha
        if k % 100 == 0:
            hist.append(best[2])
    return _hasil(ev, best[0], best[1], t0, anggaran, hist)


def greedy(p, ev, seed=None, noise=3.0):
    """Greedy konstruktif acak: urutkan sesi dari yang paling "sulit" (banyak potensi bentrok, domain sempit),
    lalu tempatkan satu per satu di (slot, ruang) yang paling sedikit melanggar kendala keras terhadap sesi
    yang sudah ditempatkan. `noise` memberi variasi urutan antar-run (seed berbeda -> hasil berbeda)."""
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    derajat = p.same_dosen.sum(1) + p.class_conflict.sum(1) + 1.0 / np.array([len(d) for d in p.domain])
    urutan = np.argsort(-(derajat + rng.uniform(0, noise, p.n_sesi)))
    s = np.zeros(p.n_sesi, dtype=np.int64)
    r = np.zeros(p.n_sesi, dtype=np.int64)
    aktif = np.zeros(p.n_sesi, dtype=bool)
    for i in urutan:
        a, b = pilih_acak_minimum(biaya_penempatan(p, i, s, r, aktif), rng)
        s[i], r[i], aktif[i] = p.domain[i][a], b, True
    return _hasil(ev, s, r, t0, p.n_sesi, [])


METODE = {"Hill Climbing": hill_climbing, "Simulated Annealing": simulated_annealing, "Greedy": greedy}
