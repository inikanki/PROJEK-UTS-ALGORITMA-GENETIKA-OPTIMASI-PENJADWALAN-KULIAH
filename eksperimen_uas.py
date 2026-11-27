"""Eksperimen UAS (dapat direproduksi): penyetelan parameter, 30 run konfigurasi terbaik, perbandingan metode.

    python eksperimen_uas.py tuning     [--runs 5]     # grid 54 konfigurasi -> hasil/tuning_parameter.csv
    python eksperimen_uas.py best       [--runs 30]    # 30 run konfigurasi terbaik -> hasil/best_config_30run.csv
    python eksperimen_uas.py bandingkan [--runs 30]    # AG UAS vs AG UTS vs HC vs SA vs Greedy
    python eksperimen_uas.py semua                     # ketiganya berurutan

Desain (semua angka seed tetap -> hasil sama bila diulang):
  * Tuning memakai seed 1..R (R=5 per konfigurasi), konfigurasi terbaik dipilih dari rata-rata penalti terkecil,
    lalu waktu konvergensi tercepat.
  * Konfigurasi terbaik diuji ulang dengan seed BARU (101..130) agar tidak bias terhadap seed tuning.
  * Semua metode dinilai ulang dengan Evaluator UAS yang sama (penalti berbobot) -> sebanding.
  * Hill Climbing dan Simulated Annealing diberi anggaran evaluasi sama dengan AG terbaik (pop x (gen+1)).
  * Uji statistik: Mann-Whitney U (Wilcoxon rank-sum, run independen) dan uji-t Welch, AG terbaik vs metode lain.
"""
import argparse
import itertools
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import config
import pembanding
from data_loader import load_problem
from fitness import Evaluator
from ga import GeneticAlgorithm

SEED_TUNING = lambda n: list(range(1, n + 1))
SEED_UJI = lambda n: list(range(101, 101 + n))
GRID = dict(pop_size=[50, 100, 200], pc=[0.6, 0.8, 0.9], pm=[0.01, 0.05, 0.1],
            selection=["tournament", "roulette"])


# ------------------------------------------------------------------ utilitas
def skor(ev, h):
    """Nilai ulang solusi akhir dengan Evaluator UAS -> metrik yang sebanding antar metode."""
    s, r = h["best_slots"][None, :], h["best_rooms"][None, :]
    keras, lunak_w, pen = ev.evaluasi(s, r)
    L = ev.lunak(s)[0]
    return dict(keras=int(keras[0]), lunak_berbobot=float(lunak_w[0]), penalti=float(pen[0]),
                jeda_panjang=int(L[0]), beban_dosen=int(L[1]), sesi_sore=int(L[2]),
                valid=int(keras[0] == 0), waktu_detik=round(h["waktu"], 3))


def gen_konvergen(hist_pen):
    h = np.asarray(hist_pen)
    return int(np.argmax(h <= h.min() + 1e-9))


def run_ga(p, ev, params, seed):
    h = GeneticAlgorithm(p, seed=seed, **params).run()
    d = skor(ev, h)
    d.update(gen_valid_pertama=h["gen_valid_pertama"], gen_konvergen=gen_konvergen(h["hist_pen"]),
             evaluasi=params["pop_size"] * (params["generations"] + 1))
    return d, h


def ringkas(df, kolom="penalti"):
    return {"n": len(df), "valid_%": round(100 * df["valid"].mean(), 1),
            f"{kolom}_mean": round(df[kolom].mean(), 3), f"{kolom}_std": round(df[kolom].std(ddof=1), 3),
            f"{kolom}_min": df[kolom].min(), f"{kolom}_median": df[kolom].median(), f"{kolom}_max": df[kolom].max()}


# ------------------------------------------------------------------ 1. tuning
def tuning(p, ev, runs, out, dasar):
    out.mkdir(parents=True, exist_ok=True)
    f = out / "tuning_parameter.csv"
    sudah = pd.read_csv(f) if f.exists() else pd.DataFrame()
    kunci = lambda r: (int(r["pop_size"]), float(r["pc"]), float(r["pm"]), r["selection"])
    selesai = {kunci(r) for _, r in sudah.iterrows()} if len(sudah) else set()
    konfig = list(itertools.product(*GRID.values()))
    print(f"Tuning: {len(konfig)} konfigurasi x {runs} run (sudah selesai: {len(selesai)})", flush=True)
    for n, (pop, pc, pm, sel) in enumerate(konfig, 1):
        if (pop, pc, pm, sel) in selesai:
            continue
        params = {**dasar, "pop_size": pop, "pc": pc, "pm": pm, "selection": sel}
        t0 = time.perf_counter()
        df = pd.DataFrame([run_ga(p, ev, params, sd)[0] for sd in SEED_TUNING(runs)])
        baris = dict(pop_size=pop, pc=pc, pm=pm, selection=sel, runs=runs,
                     valid_pct=round(100 * df["valid"].mean(), 1),
                     penalti_mean=round(df["penalti"].mean(), 3), penalti_std=round(df["penalti"].std(ddof=1), 3),
                     keras_mean=round(df["keras"].mean(), 3),
                     gen_valid_mean=round(df["gen_valid_pertama"].mean(), 2),
                     gen_konvergen_mean=round(df["gen_konvergen"].mean(), 1),
                     waktu_mean=round(df["waktu_detik"].mean(), 2))
        pd.DataFrame([baris]).to_csv(f, mode="a", header=not f.exists(), index=False)
        print(f"[{n}/{len(konfig)}] pop={pop} pc={pc} pm={pm} {sel:10s} -> penalti {baris['penalti_mean']:.2f} "
              f"valid {baris['valid_pct']}% gen_konv {baris['gen_konvergen_mean']} ({time.perf_counter()-t0:.0f}s)",
              flush=True)
    t = pd.read_csv(f).sort_values(["penalti_mean", "gen_konvergen_mean", "waktu_mean"]).reset_index(drop=True)
    t.to_csv(f, index=False)
    marg = []
    for k in GRID:
        g = t.groupby(k)[["penalti_mean", "gen_valid_mean", "gen_konvergen_mean", "waktu_mean"]].mean().round(3)
        g.insert(0, "nilai", g.index); g.insert(0, "parameter", k)
        marg.append(g.reset_index(drop=True))
    pd.concat(marg).to_csv(out / "tuning_marginal.csv", index=False)
    b = t.iloc[0]
    terbaik = dict(pop_size=int(b["pop_size"]), pc=float(b["pc"]), pm=float(b["pm"]), selection=b["selection"])
    (out / "best_config.json").write_text(json.dumps(terbaik, indent=2))
    print("\n10 konfigurasi teratas:\n", t.head(10).to_string(index=False))
    print("\nKonfigurasi terbaik:", terbaik, flush=True)
    return terbaik


def muat_terbaik(out):
    f = out / "best_config.json"
    if not f.exists():
        raise SystemExit("Jalankan dulu: python eksperimen_uas.py tuning")
    return json.loads(f.read_text())


# ------------------------------------------------------------------ 2. 30 run konfigurasi terbaik
def best30(p, ev, runs, out, dasar):
    terbaik = muat_terbaik(out)
    params = {**dasar, **terbaik}
    rows, hists = [], []
    for sd in SEED_UJI(runs):
        d, h = run_ga(p, ev, params, sd)
        rows.append({"seed": sd, **d}); hists.append(h)
    df = pd.DataFrame(rows)
    df.to_csv(out / "best_config_30run.csv", index=False)
    r = {**terbaik, **ringkas(df), "gen_valid_mean": round(df["gen_valid_pertama"].mean(), 2),
         "gen_konvergen_mean": round(df["gen_konvergen"].mean(), 1), "waktu_mean": round(df["waktu_detik"].mean(), 2)}
    pd.DataFrame([r]).to_csv(out / "best_config_30run_ringkasan.csv", index=False)
    print(df.round(3).to_string(index=False)); print("\nRingkasan:", r, flush=True)
    plot_konvergensi(hists, out / "konvergensi_ag_terbaik.png")
    return df


def plot_konvergensi(hists, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pen = np.array([h["hist_pen"] for h in hists]); viol = np.array([h["hist_viol"] for h in hists])
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    x = np.arange(pen.shape[1])
    for a, M, ttl, yl in ((ax[0], pen, "Penalti berbobot (terbaik per generasi)", "penalti"),
                          (ax[1], viol, "Pelanggaran kendala keras (terbaik per generasi)", "pelanggaran keras")):
        m, sd = M.mean(0), M.std(0)
        a.plot(x, m, color="k"); a.fill_between(x, np.maximum(m - sd, 0), m + sd, color="0.8")
        a.set_yscale("symlog"); a.set_xlabel("generasi"); a.set_ylabel(yl); a.set_title(ttl, fontsize=10)
        a.grid(alpha=.3)
    fig.suptitle(f"Konvergensi AG UAS (rata-rata ± simpangan baku, {len(hists)} run)")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


# ------------------------------------------------------------------ 3. perbandingan metode
def bandingkan(p, ev, runs, out, dasar):
    terbaik = muat_terbaik(out)
    params_uas = {**dasar, **terbaik}
    anggaran = params_uas["pop_size"] * (params_uas["generations"] + 1)
    print(f"Anggaran evaluasi HC/SA = {anggaran} (= AG terbaik)", flush=True)
    seeds = SEED_UJI(runs)
    baris = []

    def catat(nama, d):
        baris.append({"metode": nama, **d})

    for sd in seeds:
        catat("AG UAS (konfigurasi terbaik)", {"seed": sd, **run_ga(p, ev, params_uas, sd)[0]})
    for sd in seeds:
        catat("AG UTS", {"seed": sd, **run_ga(p, ev, config.PARAM_UTS, sd)[0]})
    for nama, fn in pembanding.METODE.items():
        for sd in seeds:
            kw = {"anggaran": anggaran} if nama != "Greedy" else {}
            h = fn(p, ev, seed=sd, **kw)
            catat(nama, {"seed": sd, **skor(ev, h), "evaluasi": h["evaluasi"]})
        print(f"  {nama} selesai", flush=True)
    df = pd.DataFrame(baris)
    df.to_csv(out / "perbandingan_metode_run.csv", index=False)

    ring = []
    for nama, g in df.groupby("metode", sort=False):
        ring.append({"metode": nama, "run": len(g), "valid_%": round(100 * g["valid"].mean(), 1),
                     "penalti_mean": round(g["penalti"].mean(), 3), "penalti_std": round(g["penalti"].std(ddof=1), 3),
                     "keras_mean": round(g["keras"].mean(), 3),
                     "jeda_mean": round(g["jeda_panjang"].mean(), 2), "beban_mean": round(g["beban_dosen"].mean(), 2),
                     "sore_mean": round(g["sesi_sore"].mean(), 2),
                     "waktu_mean_dtk": round(g["waktu_detik"].mean(), 3), "waktu_std_dtk": round(g["waktu_detik"].std(ddof=1), 3),
                     "evaluasi_mean": int(g["evaluasi"].mean())})
    ring = pd.DataFrame(ring)
    ring.to_csv(out / "perbandingan_metode.csv", index=False)

    uji = []
    ref = df[df["metode"] == "AG UAS (konfigurasi terbaik)"]["penalti"].to_numpy()
    try:
        from scipy import stats
    except ImportError:
        stats = None
    for nama in df["metode"].unique()[1:]:
        x = df[df["metode"] == nama]["penalti"].to_numpy()
        row = {"pembanding": nama, "mean_AG_UAS": round(ref.mean(), 3), "mean_pembanding": round(x.mean(), 3)}
        if stats:
            try: row["p_mann_whitney"] = float(stats.mannwhitneyu(ref, x, alternative="two-sided").pvalue)
            except ValueError: row["p_mann_whitney"] = float("nan")
            try: row["p_welch_t"] = float(stats.ttest_ind(ref, x, equal_var=False).pvalue)
            except Exception: row["p_welch_t"] = float("nan")
        uji.append(row)
    uji = pd.DataFrame(uji)
    uji.to_csv(out / "uji_statistik.csv", index=False)
    print("\n", ring.to_string(index=False), "\n\n", uji.to_string(index=False), flush=True)

    plot_perbandingan(df, out, runs)
    return df


def plot_perbandingan(df, out, runs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    nama = list(df["metode"].unique())
    lab = [n.replace(" (", "\n(") for n in nama]

    def kotak(a, data):
        try:
            a.boxplot(data, tick_labels=lab)          # matplotlib >= 3.9
        except TypeError:
            a.boxplot(data, labels=lab)               # matplotlib lama

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    kotak(ax[0], [df[df["metode"] == n]["penalti"] for n in nama])
    ax[0].set_ylabel("penalti berbobot (lebih kecil lebih baik)"); ax[0].set_yscale("symlog"); ax[0].grid(alpha=.3)
    ax[0].set_title("Kualitas solusi akhir", fontsize=10)
    kotak(ax[1], [df[df["metode"] == n]["waktu_detik"] for n in nama])
    ax[1].set_ylabel("waktu komputasi (detik)"); ax[1].set_yscale("log"); ax[1].grid(alpha=.3)
    ax[1].set_title("Waktu komputasi", fontsize=10)
    for a in ax: a.tick_params(axis="x", labelsize=7)
    fig.suptitle(f"Perbandingan metode ({runs} run per metode)"); fig.tight_layout()
    fig.savefig(out / "perbandingan_metode.png", dpi=150); plt.close(fig)


# ------------------------------------------------------------------ CLI
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tahap", choices=["tuning", "best", "bandingkan", "semua"])
    ap.add_argument("--data", default=str(config.DATA_UAS_PATH))
    ap.add_argument("--out", default=str(config.OUT_DIR / "uas"))
    ap.add_argument("--runs", type=int, default=None)
    a = ap.parse_args()
    p = load_problem(a.data)
    ev = Evaluator(p, bobot=config.BOBOT_DEFAULT)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dasar = dict(config.PARAM_DEFAULT)
    print(f"Data: {p.n_sesi} sesi, {p.n_dosen} dosen, {p.n_ruang} ruang, {p.n_slot} slot | keluaran: {out}", flush=True)
    if a.tahap in ("tuning", "semua"):
        tuning(p, ev, a.runs or 5, out, dasar)
    if a.tahap in ("best", "semua"):
        best30(p, ev, a.runs or 30, out, dasar)
    if a.tahap in ("bandingkan", "semua"):
        bandingkan(p, ev, a.runs or 30, out, dasar)


if __name__ == "__main__":
    main()
