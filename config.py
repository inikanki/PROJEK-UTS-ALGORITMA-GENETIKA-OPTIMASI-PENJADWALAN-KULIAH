"""Konfigurasi proyek AG Penjadwalan Kuliah (UTS)."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_PATH = BASE / "data" / "Data_Jadwal_TI_UPR_Semester_1_3_5.xlsx"
OUT_DIR = BASE / "hasil"
HARI_URUT = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"]

# Parameter default GA
PARAM_DEFAULT = dict(
    pop_size=100,
    generations=300,
    pc=0.8,              # probabilitas crossover
    pm=0.03,             # probabilitas mutasi PER GEN
    selection="tournament",   # "tournament" | "roulette"
    crossover="uniform",      # "uniform" | "one_point"
    tournament_k=3,
    elitism=2,
    stop_on_valid=False,
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