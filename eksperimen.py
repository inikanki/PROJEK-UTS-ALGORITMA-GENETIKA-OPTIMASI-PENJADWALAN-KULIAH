"""Eksperimen UTS: >=10 run dengan seed berbeda + perbandingan kombinasi operator."""
import numpy as np
import pandas as pd
from ga import GeneticAlgorithm
from fitness import NAMA_KENDALA, Evaluator, jeda_panjang


def jalankan_batch(p, params, seeds, evaluator=None):
    ev = evaluator or Evaluator(p)
    hasil = []
    for sd in seeds:
        h = GeneticAlgorithm(p, seed=sd, evaluator=ev, **params).run()
        h["seed"] = sd
        hasil.append(h)
    return hasil


def tabel_runs(p, hasil):
    rows = []
    for h in hasil:
        rows.append({
            "seed": h["seed"],
            "fitness_terbaik": h["best_fitness"],
            "pelanggaran_terbaik": h["best_violations"],
            "fitness_rata2_populasi_akhir": h["mean_fitness_final"],
            "generasi_valid_pertama": h["gen_valid_pertama"],
            "waktu_detik": round(h["waktu"], 3),
            "jeda_panjang_(soft)": jeda_panjang(p, h["best_slots"]),
        })
    return pd.DataFrame(rows)


def ringkas(tabel):
    valid = tabel["generasi_valid_pertama"].dropna()
    return pd.DataFrame([{
        "jumlah_run": len(tabel),
        "run_berhasil_valid": int((tabel["pelanggaran_terbaik"] == 0).sum()),
        "fitness_terbaik_max": tabel["fitness_terbaik"].max(),
        "fitness_terbaik_rata2": tabel["fitness_terbaik"].mean(),
        "fitness_terbaik_std": tabel["fitness_terbaik"].std(ddof=1) if len(tabel) > 1 else 0.0,
        "gen_valid_pertama_rata2": valid.mean() if len(valid) else np.nan,
        "gen_valid_pertama_min": valid.min() if len(valid) else np.nan,
        "gen_valid_pertama_max": valid.max() if len(valid) else np.nan,
        "waktu_rata2_detik": tabel["waktu_detik"].mean(),
    }])


def pilih_terbaik(hasil):
    """Run terbaik: pelanggaran paling sedikit, lalu generasi valid paling awal."""
    return min(hasil, key=lambda h: (h["best_violations"],
                                     h["gen_valid_pertama"] if h["gen_valid_pertama"] is not None else 1e9))


def bandingkan_operator(p, params, seeds):
    rows = []
    for sel in ("tournament", "roulette"):
        for cx in ("uniform", "one_point"):
            hasil = jalankan_batch(p, {**params, "selection": sel, "crossover": cx}, seeds)
            t = tabel_runs(p, hasil)
            r = ringkas(t).iloc[0].to_dict()
            rows.append({"seleksi": sel, "crossover": cx, **r})
    return pd.DataFrame(rows)
