"""Algoritma Genetika (operator ditulis sendiri, tanpa library GA).

Gen ke-i  = (slot_i, ruang_i) untuk sesi kuliah ke-i  (encoding integer, 2 baris array).
Kromosom  = n_sesi gen.  Populasi = array (N, n_sesi) untuk slots dan rooms.

Pengembangan UAS (semua bisa dimatikan lewat parameter -> dengan semuanya mati + bobot UTS = AG versi UTS):
  * fitness berbobot  : penalti = w_hard*keras + kendala lunak berbobot            (fitness.py)
  * repair operator   : sesi yang bentrok dipindah ke (slot, ruang) terbaik          (perbaikan.py)
  * mutasi adaptif    : pm dinaikkan bertahap saat populasi stagnan, reset saat membaik
  * random immigrants : individu acak baru menggantikan sebagian anak saat stagnan (menjaga diversitas)
"""
import math
import time
import numpy as np
import config
from fitness import NAMA_LUNAK, Evaluator
from perbaikan import perbaiki_populasi

SELEKSI = ("tournament", "roulette")
CROSSOVER = ("uniform", "one_point")


class GeneticAlgorithm:
    def __init__(self, problem, pop_size=100, generations=300, pc=0.8, pm=0.03,
                 selection="tournament", crossover="uniform", tournament_k=3,
                 elitism=2, seed=None, stop_on_valid=False, evaluator=None,
                 repair=False, repair_rate=0.3, repair_maks_pindah=4,
                 adaptif=False, pm_maks=0.15, stagnasi=8,
                 imigran=False, imigran_rate=0.05,
                 w_hard=config.BOBOT_DEFAULT["w_hard"], w_jeda=config.BOBOT_DEFAULT["w_jeda"],
                 w_beban=config.BOBOT_DEFAULT["w_beban"], w_sore=config.BOBOT_DEFAULT["w_sore"]):
        if selection not in SELEKSI or crossover not in CROSSOVER:
            raise ValueError(f"selection harus {SELEKSI}, crossover harus {CROSSOVER}")
        self.p = problem
        self.ev = evaluator or Evaluator(problem, bobot=dict(w_hard=w_hard, w_jeda=w_jeda,
                                                              w_beban=w_beban, w_sore=w_sore))
        self.repair, self.repair_rate, self.repair_maks = repair, repair_rate, repair_maks_pindah
        self.adaptif, self.pm_maks, self.stagnasi = adaptif, pm_maks, stagnasi
        self.imigran, self.imigran_rate = imigran, imigran_rate
        self.N, self.G = pop_size, generations
        self.pc, self.pm = pc, pm
        self.selection, self.crossover = selection, crossover
        self.k, self.E = tournament_k, elitism
        self.stop_on_valid = stop_on_valid
        self.rng = np.random.default_rng(seed)

    # ---- inisialisasi populasi acak (selalu dalam domain slot yang valid) ----
    def _init_pop(self):
        p, rng = self.p, self.rng
        slots = np.empty((self.N, p.n_sesi), dtype=np.int64)
        for j in range(p.n_sesi):
            slots[:, j] = rng.choice(p.domain[j], size=self.N)
        rooms = rng.integers(0, p.n_ruang, size=(self.N, p.n_sesi))
        return slots, rooms

    # ---- seleksi ----
    def _select(self, fit, n):
        rng = self.rng
        if self.selection == "roulette":
            return rng.choice(len(fit), size=n, p=fit / fit.sum())
        cand = rng.integers(0, len(fit), size=(n, self.k))
        return cand[np.arange(n), np.argmax(fit[cand], axis=1)]

    # ---- crossover (gen = pasangan slot+ruang, jadi keduanya ikut tertukar) ----
    def _crossover(self, s, r, ia, ib):
        rng, S = self.rng, self.p.n_sesi
        m = len(ia)
        do = rng.random(m) < self.pc
        if self.crossover == "one_point":
            cut = rng.integers(1, S, size=m)
            mask = np.arange(S)[None, :] < cut[:, None]
        else:
            mask = rng.random((m, S)) < 0.5
        mask[~do] = True                       # tanpa crossover -> anak = salinan orang tua
        sa, sb, ra, rb = s[ia], s[ib], r[ia], r[ib]
        c1s, c2s = np.where(mask, sa, sb), np.where(mask, sb, sa)
        c1r, c2r = np.where(mask, ra, rb), np.where(mask, rb, ra)
        return np.vstack([c1s, c2s]), np.vstack([c1r, c2r])

    # ---- mutasi acak per gen: ganti slot, ruang, atau keduanya ----
    def _mutate(self, s, r, pm=None):
        rng, p = self.rng, self.p
        mut = rng.random(s.shape) < (self.pm if pm is None else pm)
        jenis = rng.random(s.shape)
        ubah_slot = mut & (jenis < 0.7)
        ubah_ruang = mut & ((jenis >= 0.4))
        for j in range(p.n_sesi):
            idx = np.where(ubah_slot[:, j])[0]
            if len(idx):
                s[idx, j] = rng.choice(p.domain[j], size=len(idx))
        r[ubah_ruang] = rng.integers(0, p.n_ruang, size=int(ubah_ruang.sum()))
        return s, r

    def run(self, callback=None, snapshot_every=0):
        """callback(gen, info) dipanggil tiap generasi (untuk progress live di UI).
        snapshot_every=N -> simpan jadwal terbaik tiap N generasi (untuk animasi evolusi)."""
        t0 = time.perf_counter()
        snaps = []
        s, r = self._init_pop()
        best_f, mean_f, best_v, best_pen, hist_pm = [], [], [], [], []
        first_valid = None
        pm_cur, stag, terbaik = self.pm, 0, math.inf
        for gen in range(self.G + 1):
            keras, lunak_w, pen = self.ev.evaluasi(s, r)
            fit = Evaluator.fitness_dari_pelanggaran(pen)
            ib = int(np.argmin(pen))
            best_f.append(float(fit[ib]))
            mean_f.append(float(fit.mean()))
            best_v.append(int(keras[ib]))
            best_pen.append(float(pen[ib]))
            hist_pm.append(float(pm_cur))
            if first_valid is None and keras[ib] == 0:
                first_valid = gen
            # ---- pantau stagnasi (dasar mutasi adaptif & random immigrants) ----
            if pen[ib] < terbaik - 1e-9:
                terbaik, stag, pm_cur = float(pen[ib]), 0, self.pm
            else:
                stag += 1
                if self.adaptif and stag >= self.stagnasi:
                    pm_cur = min(self.pm_maks, pm_cur * 1.2)
            berhenti = gen == self.G or (self.stop_on_valid and keras[ib] == 0)
            if callback:
                callback(gen, dict(total=self.G, best_fitness=best_f[-1], mean_fitness=mean_f[-1],
                                   violations=best_v[-1], valid_pertama=first_valid,
                                   penalti=best_pen[-1], pm=pm_cur))
            if snapshot_every and (gen % snapshot_every == 0 or berhenti):
                snaps.append(dict(gen=gen, slots=s[ib].copy(), rooms=r[ib].copy(),
                                  violations=int(keras[ib])))
            if berhenti:
                break
            # elitisme
            elite = np.argsort(pen, kind="stable")[: self.E]
            n_child = self.N - self.E
            n_pair = (n_child + 1) // 2
            parents = self._select(fit, 2 * n_pair)
            cs, cr = self._crossover(s, r, parents[:n_pair], parents[n_pair:])
            cs, cr = self._mutate(cs[:n_child].copy(), cr[:n_child].copy(), pm_cur)
            if self.repair:                                   # repair operator pada sebagian anak
                pilih = np.where(self.rng.random(n_child) < self.repair_rate)[0]
                perbaiki_populasi(self.p, cs, cr, pilih, self.rng, self.repair_maks)
            if self.imigran and stag > 0 and stag % self.stagnasi == 0:   # random immigrants
                m = max(1, math.ceil(self.imigran_rate * self.N))
                ms, mr = self._init_pop()
                cs[-m:], cr[-m:] = ms[:m], mr[:m]
            s = np.vstack([s[elite], cs])
            r = np.vstack([r[elite], cr])
        keras, lunak_w, pen = self.ev.evaluasi(s, r)
        ib = int(np.argmin(pen))
        return dict(
            best_slots=s[ib].copy(), best_rooms=r[ib].copy(),
            best_violations=int(keras[ib]),
            best_fitness=float(1.0 / (1.0 + pen[ib])),
            best_penalti=float(pen[ib]), best_lunak=float(lunak_w[ib]),
            rincian_lunak=dict(zip(NAMA_LUNAK, map(int, self.ev.lunak(s[ib])[0]))),
            rincian=self.ev.rincian(s[ib], r[ib])[0],
            mean_fitness_final=float(Evaluator.fitness_dari_pelanggaran(pen).mean()),
            gen_valid_pertama=first_valid,
            hist_best=best_f, hist_mean=mean_f, hist_viol=best_v, hist_pen=best_pen, hist_pm=hist_pm,
            waktu=time.perf_counter() - t0,
            generasi_dijalankan=len(best_f) - 1,
            snapshots=snaps,
        )
