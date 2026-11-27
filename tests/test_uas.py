"""Unit test pengembangan UAS: kendala lunak, fitness berbobot, repair, mutasi adaptif, immigrants, pembanding."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

import config
import pembanding
from data_loader import load_problem
from fitness import NAMA_LUNAK, Evaluator, lunak_independen
from ga import GeneticAlgorithm
from perbaikan import perbaiki_individu, sesi_bermasalah


@pytest.fixture(scope="module")
def p():
    return load_problem(config.DATA_UAS_PATH)


@pytest.fixture(scope="module")
def ev(p):
    return Evaluator(p)


def acak(p, n, seed=0):
    rng = np.random.default_rng(seed)
    s = np.stack([[rng.choice(d) for d in p.domain] for _ in range(n)])
    return s, rng.integers(0, p.n_ruang, size=s.shape)


def test_skala_data_uas(p):
    assert (p.n_sesi, p.n_dosen, p.n_ruang) == (60, 20, 10)


def test_lunak_vektor_sama_dengan_loop(p, ev):
    s, _ = acak(p, 60, seed=1)
    L = ev.lunak(s)
    for k in range(len(s)):
        assert list(L[k].astype(int)) == [lunak_independen(p, s[k])[n] for n in NAMA_LUNAK]


def test_bobot_uts_sama_dengan_fitness_uts(p):
    e = Evaluator(p, bobot=config.BOBOT_UTS)
    s, r = acak(p, 20, seed=2)
    keras, _, pen = e.evaluasi(s, r)
    assert np.allclose(pen, keras)


def test_bobot_keras_jauh_lebih_besar_dari_lunak(p, ev):
    s, _ = acak(p, 500, seed=3)
    assert ev.w_hard >= 10 * (ev.lunak(s) @ np.array([ev.w_jeda, ev.w_beban, ev.w_sore])).max()


def test_repair_tidak_menambah_pelanggaran_dan_menjaga_domain(p, ev):
    s, r = acak(p, 30, seed=4)
    rng = np.random.default_rng(0)
    for k in range(len(s)):
        sebelum = ev.total(s[k:k+1], r[k:k+1])[0]
        perbaiki_individu(p, s[k], r[k], rng, maks_pindah=10)
        sesudah = ev.total(s[k:k+1], r[k:k+1])[0]
        assert sesudah <= sebelum
        assert ev.rincian(s[k:k+1], r[k:k+1])[0][4] == 0          # durasi tetap benar (slot dalam domain)


def test_repair_memperbaiki_konflik_buatan(p, ev):
    s, r = acak(p, 1, seed=5)
    s, r = s[0].copy(), r[0].copy()
    s[1], r[1] = s[0], r[0]                                        # paksa dua sesi satu slot + satu ruang
    assert 0 in sesi_bermasalah(p, s, r) or 1 in sesi_bermasalah(p, s, r)
    rng = np.random.default_rng(1)
    for _ in range(5):
        perbaiki_individu(p, s, r, rng, maks_pindah=10)
    assert ev.rincian(s[None, :], r[None, :])[0][2] == 0           # bentrok ruang hilang


def test_ga_uas_valid_dan_reprodusibel(p):
    a = GeneticAlgorithm(p, seed=11, generations=60, **{k: v for k, v in config.PARAM_DEFAULT.items()
                                                          if k not in ("generations",)}).run()
    b = GeneticAlgorithm(p, seed=11, generations=60, **{k: v for k, v in config.PARAM_DEFAULT.items()
                                                          if k not in ("generations",)}).run()
    assert a["best_violations"] == 0 and a["hist_pen"] == b["hist_pen"]


def test_mutasi_adaptif_naik_saat_stagnan_dan_kembali_saat_membaik(p):
    prm = {**config.PARAM_DEFAULT, "pop_size": 30, "generations": 80, "pm": 0.02, "stagnasi": 5}
    h = GeneticAlgorithm(p, seed=3, **prm).run()
    assert max(h["hist_pm"]) > 0.02 and max(h["hist_pm"]) <= prm["pm_maks"] + 1e-12
    mati = GeneticAlgorithm(p, seed=3, **{**prm, "adaptif": False}).run()
    assert set(mati["hist_pm"]) == {0.02}


def test_random_immigrants_berjalan(p):
    prm = {**config.PARAM_DEFAULT, "pop_size": 30, "generations": 60, "stagnasi": 4, "imigran": True}
    h = GeneticAlgorithm(p, seed=2, **prm).run()
    assert np.isfinite(h["best_penalti"]) and len(h["hist_pen"]) == 61


def test_ag_uts_tidak_mengoptimalkan_lunak(p):
    h = GeneticAlgorithm(p, seed=1, **config.PARAM_UTS).run()
    assert h["best_violations"] == 0 and h["best_penalti"] == 0.0     # fitness UTS: hanya kendala keras


@pytest.mark.parametrize("nama", list(pembanding.METODE))
def test_pembanding_menghasilkan_solusi_dalam_domain(p, ev, nama):
    kw = {} if nama == "Greedy" else {"anggaran": 1500}
    h = pembanding.METODE[nama](p, ev, seed=1, **kw)
    assert len(h["best_slots"]) == p.n_sesi
    assert all(h["best_slots"][i] in p.domain[i] for i in range(p.n_sesi))
    assert ev.rincian(h["best_slots"][None, :], h["best_rooms"][None, :])[0][4] == 0
