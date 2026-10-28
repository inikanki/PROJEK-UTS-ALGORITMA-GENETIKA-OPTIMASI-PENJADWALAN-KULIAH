import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest
from data_loader import load_problem, parse_slot
from fitness import Evaluator, validasi_independen, NAMA_KENDALA
from ga import GeneticAlgorithm


@pytest.fixture(scope="module")
def p():
    return load_problem()


def test_ukuran_data(p):
    assert p.n_sesi == 43 and p.n_ruang == 11 and p.n_slot == 21


def test_dosen_dinormalisasi(p):
    assert sum("Christian Novan" in d for d in set(p.dosen)) == 1


def test_parse_slot():
    assert parse_slot("07.00–09.30") == (420, 570)


def test_overlap_slot(p):
    idx = lambda h, l: next(i for i in range(p.n_slot) if p.slot_hari[i] == h and p.slot_label[i] == l)
    assert p.OV[idx("Selasa", "07.00–09.30"), idx("Selasa", "08.40–11.10")]       # beririsan
    assert not p.OV[idx("Senin", "07.00–09.30"), idx("Senin", "09.30–12.00")]      # bersinggungan saja
    assert not p.OV[idx("Senin", "07.00–09.30"), idx("Selasa", "07.00–09.30")]     # beda hari


def test_jadwal_asli_punya_bentrok_dosen(p):
    r = Evaluator(p).rincian(p.slot_asli, p.ruang_asli)[0]
    assert r[0] > 0


def test_agama_tidak_bentrok_kelas_satu_sama_lain(p):
    ag = [i for i in range(p.n_sesi) if p.is_agama[i]]
    assert not any(p.class_conflict[i, j] for i in ag for j in ag)


def test_vectorized_sama_dengan_validator_independen(p):
    rng = np.random.default_rng(0)
    ev = Evaluator(p)
    ga = GeneticAlgorithm(p, pop_size=30, seed=0)
    s, r = ga._init_pop()
    r = rng.integers(0, p.n_ruang, size=r.shape)
    rin = ev.rincian(s, r)
    for k in range(len(s)):
        ref = validasi_independen(p, s[k], r[k])
        assert [ref[n] for n in NAMA_KENDALA] == list(rin[k])


def test_konflik_buatan_terdeteksi(p):
    ev = Evaluator(p)
    s, r = p.slot_asli.copy(), p.ruang_asli.copy()
    i, j = 0, 1                      # Aljabar Linear A & B (beda dosen, beda kelas)
    s[j] = s[i]; r[j] = r[i]         # paksa satu ruang + satu slot
    assert ev.rincian(s, r)[0][2] >= 1


def test_ga_menemukan_jadwal_valid(p):
    h = GeneticAlgorithm(p, seed=1).run()
    assert h["best_violations"] == 0 and h["best_fitness"] == 1.0
    assert h["gen_valid_pertama"] is not None


def test_reprodusibel_dengan_seed(p):
    a = GeneticAlgorithm(p, seed=7, generations=30).run()
    b = GeneticAlgorithm(p, seed=7, generations=30).run()
    assert a["hist_best"] == b["hist_best"]


def test_domain_durasi_terjaga(p):
    h = GeneticAlgorithm(p, seed=3, generations=50).run()
    assert h["rincian"][NAMA_KENDALA.index("durasi")] == 0
