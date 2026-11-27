"""Konfigurasi proyek AG Penjadwalan Kuliah (UTS)."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_PATH = BASE / "data" / "Data_Jadwal_TI_UPR_Semester_1_3_5.xlsx"          # data UTS (43 sesi)
DATA_UAS_PATH = BASE / "data" / "Data_Jadwal_UAS_Sintetis.xlsx"              # data UAS (60 sesi, 20 dosen, 10 ruang)
OUT_DIR = BASE / "hasil"
HARI_URUT = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"]

# ---- Bobot fungsi fitness UAS ----------------------------------------------------------
# penalti = w_hard * (#pelanggaran kendala keras) + w_jeda * jeda_panjang + w_beban * beban_dosen + w_sore * sesi_sore
# fitness = 1 / (1 + penalti).  w_hard dibuat jauh lebih besar daripada total kendala lunak yang realistis
# (lihat README: pada jadwal acak total lunak <= 22), sehingga satu pelanggaran keras tidak pernah
# "dibayar" dengan perbaikan kendala lunak.
BOBOT_DEFAULT = dict(w_hard=1000.0, w_jeda=1.0, w_beban=2.0, w_sore=1.0)
BOBOT_UTS = dict(w_hard=1.0, w_jeda=0.0, w_beban=0.0, w_sore=0.0)      # = fitness 1/(1+pelanggaran) milik UTS
SOFT_BATAS = dict(batas_jeda=90,        # menit; jeda antar kuliah satu kelas > ini dihitung 1 pelanggaran
                  maks_sesi_hari=2,     # dosen mengajar > ini dalam sehari -> kelebihannya dihitung
                  sore_selesai=16 * 60) # sesi yang selesai setelah jam ini dianggap kurang disukai

# Parameter GA versi UTS (dipakai sebagai pembanding "AG UTS")
PARAM_UTS = dict(
    pop_size=100, generations=300, pc=0.8, pm=0.03, selection="tournament", crossover="uniform",
    tournament_k=3, elitism=2, stop_on_valid=False,
    repair=False, adaptif=False, imigran=False, **BOBOT_UTS,
)

# Parameter default GA UAS (konfigurasi terbaik hasil tuning: lihat hasil/tuning_parameter.csv)
PARAM_DEFAULT = dict(
    pop_size=100,
    generations=300,
    pc=0.8,              # probabilitas crossover
    pm=0.03,             # probabilitas mutasi PER GEN (dasar; mutasi adaptif menaikkannya saat stagnan)
    selection="tournament",   # "tournament" | "roulette"
    crossover="uniform",      # "uniform" | "one_point"
    tournament_k=3,
    elitism=2,
    stop_on_valid=False,
    # --- perbaikan operator UAS (bisa dimatikan satu per satu) ---
    repair=True, repair_rate=0.3, repair_maks_pindah=4,
    adaptif=True, pm_maks=0.15, stagnasi=8,
    imigran=True, imigran_rate=0.05,
    **BOBOT_DEFAULT,
)

KAPASITAS_DEFAULT = 100          # FT3 sampai FT9
KAPASITAS_RUANG = {
    "AUDIT": 120,
    "PRIVAT": 10,
    "GKTA-LT4": 50,
    "GKTA-LT5": 50,
}
JUMLAH_MHS_KELAS = {"A": 45, "B": 45, "-": 90}   # jumlah TERBANYAK per jenis kelas (data cadangan)
JUMLAH_MHS_OVERRIDE = {
    "Agama Islam": 32,
    "Agama Kristen": 50,
    "Agama Katolik": 6,
    "Agama Hindu/Kaharingan": 1,
}