"""CLI proyek AG Penjadwalan Kuliah (UTS).

  python main.py                      # 1 run (seed 42) -> jadwal + grafik
  python main.py --eksperimen         # 10 run, seed berbeda -> tabel hasil + grafik
  python main.py --bandingkan         # 10 run x 4 kombinasi seleksi/crossover
  python main.py --evaluasi-asli      # hitung pelanggaran pada jadwal asli di Excel
"""
import argparse
import pandas as pd
import config
from data_loader import load_problem
from export import jadwal_df, plot_konvergensi, simpan_jadwal
from fitness import NAMA_KENDALA, Evaluator, jeda_panjang
from eksperimen import bandingkan_operator, jalankan_batch, pilih_terbaik, ringkas, tabel_runs


def evaluasi_asli(p):
    ev = Evaluator(p)
    r = ev.rincian(p.slot_asli, p.ruang_asli)[0]
    print("Pelanggaran jadwal ASLI (Excel):", dict(zip(NAMA_KENDALA, map(int, r))))
    for i in range(p.n_sesi):
        for j in range(i + 1, p.n_sesi):
            if p.same_dosen[i, j] and p.OV[p.slot_asli[i], p.slot_asli[j]]:
                print(f"  bentrok dosen: {p.dosen[i]} -> {p.mk[i]} {p.kelas[i]} "
                      f"({p.slot_hari[p.slot_asli[i]]} {p.slot_label[p.slot_asli[i]]}) "
                      f"vs {p.mk[j]} {p.kelas[j]} "
                      f"({p.slot_hari[p.slot_asli[j]]} {p.slot_label[p.slot_asli[j]]})")


def main():
    ap = argparse.ArgumentParser()
    d = config.PARAM_DEFAULT
    ap.add_argument("--data", default=str(config.DATA_PATH))
    ap.add_argument("--out", default=str(config.OUT_DIR))
    ap.add_argument("--pop", type=int, default=d["pop_size"])
    ap.add_argument("--gen", type=int, default=d["generations"])
    ap.add_argument("--pc", type=float, default=d["pc"])
    ap.add_argument("--pm", type=float, default=d["pm"])
    ap.add_argument("--seleksi", choices=["tournament", "roulette"], default=d["selection"])
    ap.add_argument("--crossover", choices=["uniform", "one_point"], default=d["crossover"])
    ap.add_argument("--elitisme", type=int, default=d["elitism"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--eksperimen", action="store_true")
    ap.add_argument("--bandingkan", action="store_true")
    ap.add_argument("--evaluasi-asli", action="store_true")
    a = ap.parse_args()

    from pathlib import Path
    out = Path(a.out)
    p = load_problem(a.data)
    params = {**d, "pop_size": a.pop, "generations": a.gen, "pc": a.pc, "pm": a.pm,
              "selection": a.seleksi, "crossover": a.crossover, "elitism": a.elitisme}
    print(f"Data: {p.n_sesi} sesi, {p.n_dosen} dosen, {p.n_ruang} ruang, {p.n_slot} slot")

    if a.evaluasi_asli:
        evaluasi_asli(p)
        return

    if a.bandingkan:
        seeds = list(range(1, a.runs + 1))
        tab = bandingkan_operator(p, params, seeds)
        out.mkdir(parents=True, exist_ok=True)
        tab.to_csv(out / "perbandingan_operator.csv", index=False)
        print(tab.round(4).to_string(index=False))
        return

    seeds = list(range(1, a.runs + 1)) if a.eksperimen else [a.seed]
    hasil = jalankan_batch(p, params, seeds)
    tab = tabel_runs(p, hasil)
    ring = ringkas(tab)
    best = pilih_terbaik(hasil)
    df, grid = simpan_jadwal(p, best["best_slots"], best["best_rooms"], out, ringkasan=ring)
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "hasil_run.csv", index=False)
    ring.to_csv(out / "ringkasan_run.csv", index=False)
    plot_konvergensi(hasil, out / "konvergensi.png")
    print(tab.round(4).to_string(index=False))
    print("\nRingkasan:\n", ring.round(4).T.to_string(header=False))
    print(f"\nJadwal terbaik: seed {best['seed']}, fitness {best['best_fitness']:.4f}, "
          f"pelanggaran {best['best_violations']}")
    print(f"\nFile tersimpan di: {out}")


if __name__ == "__main__":
    main()