"""Algoritma Genetika (operator ditulis sendiri, tanpa library GA).

Gen ke-i  = (slot_i, ruang_i) untuk sesi kuliah ke-i  (encoding integer, 2 baris array).
Kromosom  = n_sesi gen.  Populasi = array (N, n_sesi) untuk slots dan rooms.
"""
import time
import numpy as np
from fitness import Evaluator

SELEKSI = ("tournament", "roulette")
CROSSOVER = ("uniform", "one_point")


class GeneticAlgorithm:
    def __init__(self, problem, pop_size=100, generations=300, pc=0.8, pm=0.03,
                 selection="tournament", crossover="uniform", tournament_k=3,
                 elitism=2, seed=None, stop_on_valid=False, evaluator=None):
        if selection not in SELEKSI or crossover not in CROSSOVER:
            raise ValueError(f"selection harus {SELEKSI}, crossover harus {CROSSOVER}")
        self.p = problem
        self.ev = evaluator or Evaluator(problem)
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
    def _mutate(self, s, r):
        rng, p = self.rng, self.p
        mut = rng.random(s.shape) < self.pm
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
        best_f, mean_f, best_v = [], [], []
        first_valid = None
        for gen in range(self.G + 1):
            viol = self.ev.total(s, r)
            fit = Evaluator.fitness_dari_pelanggaran(viol)
            ib = int(np.argmin(viol))
            best_f.append(float(fit[ib]))
            mean_f.append(float(fit.mean()))
            best_v.append(int(viol[ib]))
            if first_valid is None and viol[ib] == 0:
                first_valid = gen
            berhenti = gen == self.G or (self.stop_on_valid and viol[ib] == 0)
            if callback:
                callback(gen, dict(total=self.G, best_fitness=best_f[-1], mean_fitness=mean_f[-1],
                                   violations=best_v[-1], valid_pertama=first_valid))
            if snapshot_every and (gen % snapshot_every == 0 or berhenti):
                snaps.append(dict(gen=gen, slots=s[ib].copy(), rooms=r[ib].copy(),
                                  violations=int(viol[ib])))
            if berhenti:
                break
            # elitisme
            elite = np.argsort(viol, kind="stable")[: self.E]
            n_child = self.N - self.E
            n_pair = (n_child + 1) // 2
            parents = self._select(fit, 2 * n_pair)
            cs, cr = self._crossover(s, r, parents[:n_pair], parents[n_pair:])
            cs, cr = self._mutate(cs[:n_child].copy(), cr[:n_child].copy())
            s = np.vstack([s[elite], cs])
            r = np.vstack([r[elite], cr])
        viol = self.ev.total(s, r)
        ib = int(np.argmin(viol))
        return dict(
            best_slots=s[ib].copy(), best_rooms=r[ib].copy(),
            best_violations=int(viol[ib]),
            best_fitness=float(1.0 / (1.0 + viol[ib])),
            rincian=self.ev.rincian(s[ib], r[ib])[0],
            mean_fitness_final=float(Evaluator.fitness_dari_pelanggaran(viol).mean()),
            gen_valid_pertama=first_valid,
            hist_best=best_f, hist_mean=mean_f, hist_viol=best_v,
            waktu=time.perf_counter() - t0,
            generasi_dijalankan=len(best_f) - 1,
            snapshots=snaps,
        )
