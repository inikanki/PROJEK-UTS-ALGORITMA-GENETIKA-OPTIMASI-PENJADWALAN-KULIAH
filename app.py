"""Aplikasi sederhana AG Penjadwalan Kuliah (UTS).  Jalankan:  streamlit run app.py"""
import copy
import io
import numpy as np
import pandas as pd
import streamlit as st

import config
from data_loader import load_problem
from eksperimen import bandingkan_operator, jalankan_batch, pilih_terbaik, ringkas, tabel_runs
from export import grid_df, jadwal_df
from fitness import NAMA_KENDALA, Evaluator, jeda_panjang

st.set_page_config(page_title="AG Penjadwalan Kuliah", page_icon="🧬", layout="wide")
st.title("🧬 Penjadwalan Kuliah dengan Algoritma Genetika")
st.caption("UTS – AG dasar: kromosom (slot, ruang) per sesi, fitness = 1 / (1 + pelanggaran kendala keras)")


@st.cache_data(show_spinner=False)
def muat(file_bytes):
    src = io.BytesIO(file_bytes) if file_bytes else config.DATA_PATH
    return load_problem(src)


def excel_bytes(df, grid, tab_runs=None):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Jadwal Detail", index=False)
        grid.to_excel(w, sheet_name="Grid Hari x Slot")
        if tab_runs is not None:
            tab_runs.to_excel(w, sheet_name="Hasil Run", index=False)
    return buf.getvalue()


def grid_html(grid):
    g = grid.copy().astype(str).replace("\n", "<br><hr style='margin:3px 0'>", regex=True)
    css = ("<style>.g td,.g th{border:1px solid #8884;padding:6px;vertical-align:top;font-size:12px}"
           ".g{border-collapse:collapse;width:100%}.g th{background:#8882}</style>")
    return css + g.to_html(escape=False, classes="g", border=0)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("⚙️ Pengaturan")
    up = st.file_uploader("Data jadwal (.xlsx)", type="xlsx",
                          help="Kosongkan untuk memakai data bawaan (TI UPR Semester 1/3/5).")
    try:
        p0 = muat(up.getvalue() if up else None)
    except Exception as e:
        st.error(f"Gagal membaca Excel: {e}")
        st.stop()

    d = config.PARAM_DEFAULT
    pop = st.slider("Ukuran populasi", 20, 300, d["pop_size"], 10)
    gen = st.slider("Jumlah generasi", 10, 1000, d["generations"], 10)
    pc = st.slider("Probabilitas crossover (pc)", 0.0, 1.0, d["pc"], 0.05)
    pm = st.slider("Probabilitas mutasi per gen (pm)", 0.0, 0.3, d["pm"], 0.005)
    sel = st.selectbox("Seleksi", ["tournament", "roulette"],
                       format_func=lambda x: {"tournament": "Turnamen", "roulette": "Roulette wheel"}[x])
    k = st.slider("Ukuran turnamen (k)", 2, 10, d["tournament_k"], disabled=(sel != "tournament"))
    cx = st.selectbox("Crossover", ["uniform", "one_point"],
                      format_func=lambda x: {"uniform": "Uniform", "one_point": "Satu titik"}[x])
    elit = st.slider("Elitisme (jumlah individu)", 0, 10, d["elitism"])
    stop = st.checkbox("Berhenti saat solusi valid pertama", value=False)
    st.divider()
    n_run = st.number_input("Jumlah run (seed berbeda)", 1, 50, 10,
                            help="UTS meminta minimal 10 run. Isi 1 untuk satu run saja.")
    seed0 = st.number_input("Seed awal", 0, 10_000, 1)
    tombol = st.button("▶️ Jalankan GA", type="primary")

params = dict(pop_size=pop, generations=gen, pc=pc, pm=pm, selection=sel, crossover=cx,
              tournament_k=k, elitism=elit, stop_on_valid=stop)

# ------------------------------------------------------------------ kapasitas ruang (asumsi)
p = copy.copy(p0)
with st.expander("🏫 Kapasitas ruang & asumsi (bisa diedit sebelum run)"):
    st.warning("Excel tidak memuat kapasitas ruang. Angka di bawah hanya placeholder dari `config.py` "
               "– ganti dengan data sebenarnya.")
    kap = st.data_editor(pd.DataFrame({"Ruang": p0.ruang, "Kapasitas": p0.cap}),
                         hide_index=True, disabled=["Ruang"], key="kap")
    p.cap = kap["Kapasitas"].to_numpy(dtype=int)

# ------------------------------------------------------------------ run
if tombol:
    seeds = list(range(int(seed0), int(seed0) + int(n_run)))
    ev = Evaluator(p)
    bar = st.progress(0.0, text="Menjalankan GA…")
    hasil = []
    for i, sd in enumerate(seeds):
        hasil += jalankan_batch(p, params, [sd], evaluator=ev)
        bar.progress((i + 1) / len(seeds), text=f"Run {i + 1}/{len(seeds)} selesai")
    bar.empty()
    st.session_state["hasil"] = hasil
    st.session_state["p"] = p
    st.session_state["params"] = params
    st.session_state.pop("banding", None)

tab_info, tab_grid, tab_detail, tab_konv, tab_run, tab_data = st.tabs(
    ["📊 Ringkasan", "🗓️ Grid Hari × Slot", "📋 Jadwal Detail", "📈 Konvergensi", "🔁 Hasil Run", "🗂️ Data"])

# ------------------------------------------------------------------ tab data (selalu tampil)
with tab_data:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sesi kuliah (gen)", p0.n_sesi)
    c2.metric("Dosen", p0.n_dosen)
    c3.metric("Ruang", p0.n_ruang)
    c4.metric("Slot waktu", p0.n_slot)
    st.subheader("Jadwal asli (dari Excel)")
    ev0 = Evaluator(p0)
    r0 = ev0.rincian(p0.slot_asli, p0.ruang_asli)[0]
    st.write("Pelanggaran kendala keras pada jadwal asli: "
             + ", ".join(f"**{n}** = {int(v)}" for n, v in zip(NAMA_KENDALA, r0)))
    st.dataframe(jadwal_df(p0, p0.slot_asli, p0.ruang_asli), hide_index=True)
    st.subheader("Kendala yang dipakai")
    st.markdown(
        "- **Dosen**: tidak mengajar dua sesi pada slot yang beririsan\n"
        "- **Ruang**: tidak dipakai dua sesi pada slot yang beririsan\n"
        "- **Kelas**: satu kelas (semester + kelas; `-` = satu angkatan) tidak punya dua sesi beririsan\n"
        "- **Kapasitas**: kapasitas ruang ≥ jumlah mahasiswa\n"
        "- **Durasi**: sesi 100/150 menit hanya boleh di slot berdurasi sama\n"
        "- *Lunak (dilaporkan saja)*: jeda > 90 menit antar kuliah satu kelas dalam sehari")

if "hasil" not in st.session_state:
    for t in (tab_info, tab_grid, tab_detail, tab_konv, tab_run):
        with t:
            st.info("Atur parameter di sidebar lalu klik **Jalankan GA**.")
    st.stop()

hasil, pp, prm = st.session_state["hasil"], st.session_state["p"], st.session_state["params"]
best = pilih_terbaik(hasil)
tab = tabel_runs(pp, hasil)
ring = ringkas(tab)
df = jadwal_df(pp, best["best_slots"], best["best_rooms"])
grid = grid_df(df)

# ------------------------------------------------------------------ ringkasan
with tab_info:
    ok = int((tab["pelanggaran_terbaik"] == 0).sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Run berhasil (valid)", f"{ok}/{len(hasil)}")
    c2.metric("Fitness terbaik", f"{best['best_fitness']:.4f}")
    gv = tab["generasi_valid_pertama"].dropna()
    c3.metric("Generasi valid pertama (rata-rata)", f"{gv.mean():.1f}" if len(gv) else "–")
    c4.metric("Waktu rata-rata / run", f"{tab['waktu_detik'].mean():.2f} dtk")
    st.write(f"Jadwal ditampilkan berasal dari **seed {best['seed']}** (run terbaik). "
             "Pelanggaran per kendala: "
             + ", ".join(f"**{n}** = {int(v)}" for n, v in zip(NAMA_KENDALA, best["rincian"])))
    st.write(f"Kendala lunak – jeda panjang (>90 menit): **{jeda_panjang(pp, best['best_slots'])}**")
    st.dataframe(ring.round(4).T.rename(columns={0: "nilai"}))

    st.divider()
    st.subheader("Bandingkan seleksi × crossover")
    st.caption("Menjalankan 4 kombinasi dengan parameter lain sesuai sidebar. Butuh sekitar 30 detik untuk 10 run.")
    if st.button("Jalankan perbandingan operator"):
        with st.spinner("Membandingkan…"):
            st.session_state["banding"] = bandingkan_operator(
                pp, prm, list(range(int(seed0), int(seed0) + int(n_run))))
    if "banding" in st.session_state:
        b = st.session_state["banding"]
        st.dataframe(b.round(4), hide_index=True)
        st.download_button("⬇️ Unduh perbandingan (CSV)", b.to_csv(index=False).encode("utf-8-sig"),
                           "perbandingan_operator.csv", "text/csv")

# ------------------------------------------------------------------ grid
with tab_grid:
    st.markdown(grid_html(grid), unsafe_allow_html=True)

# ------------------------------------------------------------------ detail + filter
with tab_detail:
    f1, f2, f3 = st.columns(3)
    fs = f1.multiselect("Semester", sorted(df["Semester"].unique()))
    fk = f2.multiselect("Kelas", sorted(df["Kelas"].unique()))
    fd = f3.multiselect("Dosen", sorted(df["Dosen"].unique()))
    v = df
    if fs: v = v[v["Semester"].isin(fs)]
    if fk: v = v[v["Kelas"].isin(fk)]
    if fd: v = v[v["Dosen"].isin(fd)]
    st.dataframe(v, hide_index=True)
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Unduh jadwal (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       "jadwal_terbaik.csv", "text/csv")
    d2.download_button("⬇️ Unduh jadwal (Excel)", excel_bytes(df, grid, tab),
                       "jadwal_terbaik.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# ------------------------------------------------------------------ konvergensi
with tab_konv:
    L = max(len(h["hist_best"]) for h in hasil)
    pad = lambda a: a + [a[-1]] * (L - len(a))
    kurva = pd.DataFrame({
        "Fitness terbaik (rata-rata run)": np.mean([pad(h["hist_best"]) for h in hasil], axis=0),
        "Fitness rata-rata populasi": np.mean([pad(h["hist_mean"]) for h in hasil], axis=0),
    })
    kurva.index.name = "Generasi"
    st.line_chart(kurva)
    pel = pd.DataFrame({"Pelanggaran terbaik (rata-rata run)":
                        np.mean([pad(h["hist_viol"]) for h in hasil], axis=0)})
    pel.index.name = "Generasi"
    st.line_chart(pel)
    st.caption("Fitness = 1 / (1 + pelanggaran). Nilai 1,0 berarti jadwal tanpa bentrok.")

# ------------------------------------------------------------------ tabel run
with tab_run:
    st.dataframe(tab.round(4), hide_index=True)
    st.download_button("⬇️ Unduh hasil run (CSV)", tab.to_csv(index=False).encode("utf-8-sig"),
                       "hasil_run.csv", "text/csv")
