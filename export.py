"""Tabel jadwal (detail + grid hari x slot), ekspor CSV/Excel, grafik konvergensi."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import config


def jadwal_df(p, slots, rooms):
    rows = []
    for i in range(p.n_sesi):
        s = slots[i]
        rows.append({
            "Hari": p.slot_hari[s], "Slot Waktu": p.slot_label[s], "Mata Kuliah": p.mk[i],
            "Semester": p.semester[i], "Kelas": p.kelas[i], "Ruang": p.ruang[rooms[i]],
            "Dosen": p.dosen[i], "_mulai": int(p.slot_mulai[s]),
        })
    df = pd.DataFrame(rows)
    df["_h"] = df["Hari"].map({h: i for i, h in enumerate(config.HARI_URUT)})
    df = df.sort_values(["_h", "_mulai", "Semester", "Kelas"]).drop(columns=["_h", "_mulai"])
    return df.reset_index(drop=True)


def grid_df(df):
    """Tabel hari (baris) x slot waktu (kolom); sel berisi semua sesi pada slot tsb."""
    def kunci(lbl):
        a, b = lbl.replace("–", "-").split("-")
        return (a, b)
    kolom = sorted(df["Slot Waktu"].unique(), key=kunci)
    grid = pd.DataFrame("", index=config.HARI_URUT, columns=kolom)
    for _, r in df.iterrows():
        teks = f"{r['Mata Kuliah']} ({r['Kelas']}) [{r['Ruang']}] - {r['Dosen']}"
        cur = grid.at[r["Hari"], r["Slot Waktu"]]
        grid.at[r["Hari"], r["Slot Waktu"]] = (cur + "\n" if cur else "") + teks
    grid.index.name = "Hari"
    return grid


def simpan_jadwal(p, slots, rooms, folder=config.OUT_DIR, nama="jadwal_terbaik", ringkasan=None):
    folder.mkdir(parents=True, exist_ok=True)
    df = jadwal_df(p, slots, rooms)
    grid = grid_df(df)
    df.to_csv(folder / f"{nama}.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(folder / f"{nama}.xlsx", engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Jadwal Detail", index=False)
        grid.to_excel(w, sheet_name="Grid Hari x Slot")
        if ringkasan is not None:
            ringkasan.to_excel(w, sheet_name="Ringkasan", index=False)
        from openpyxl.styles import Alignment
        ws = w.sheets["Grid Hari x Slot"]
        ws.column_dimensions["A"].width = 10
        for col in ws.iter_cols(min_col=2, max_col=ws.max_column):
            ws.column_dimensions[col[0].column_letter].width = 42
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ws2 = w.sheets["Jadwal Detail"]
        for col, wd in zip("ABCDEFG", (9, 14, 38, 9, 7, 11, 40)):
            ws2.column_dimensions[col].width = wd
    return df, grid


def plot_konvergensi(hasil_runs, path, judul="Konvergensi Fitness per Generasi"):
    """hasil_runs: list hasil GA.run(). Garis tipis = best tiap run, tebal = rata-rata semua run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    panjang = max(len(h["hist_best"]) for h in hasil_runs)
    mat = np.array([h["hist_best"] + [h["hist_best"][-1]] * (panjang - len(h["hist_best"]))
                    for h in hasil_runs])
    mat_mean = np.array([h["hist_mean"] + [h["hist_mean"][-1]] * (panjang - len(h["hist_mean"]))
                         for h in hasil_runs])
    for row in mat:
        ax.plot(row, color="tab:blue", alpha=0.2, lw=0.8)
    ax.plot(mat.mean(0), color="tab:blue", lw=2, label="Fitness terbaik (rata-rata run)")
    ax.plot(mat_mean.mean(0), color="tab:orange", lw=2, label="Fitness rata-rata populasi")
    ax.set_xlabel("Generasi")
    ax.set_ylabel("Fitness = 1 / (1 + pelanggaran)")
    ax.set_title(judul)
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
