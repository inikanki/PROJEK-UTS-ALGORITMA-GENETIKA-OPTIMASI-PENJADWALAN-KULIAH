"""Server Flask Kuliahify. Jalankan:  python flask_app.py  lalu buka http://127.0.0.1:5000

Backend mengikuti kontrak penjadwalan AG (server.py): proses GA berjalan di thread, UI memantau progres.
API (JSON):
  GET  /api/info | POST /api/upload | POST /api/run | GET /api/job/<id>
  GET  /api/asli | POST /api/validasi | GET /api/export/<id>.csv|.xlsx
"""
import io
import threading
import uuid

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

import config
import ga_api

app = Flask(__name__)
UPLOAD = config.BASE / "uploads" / "data_upload.xlsx"
state = {"data_path": str(config.DATA_PATH), "nama_file": None}
jobs = {}


@app.get("/")
def index():
    return render_template("index.html", defaults=config.PARAM_DEFAULT)


@app.get("/api/info")
def info():
    return jsonify({**ga_api.info_data(state["data_path"]), "nama_file": state["nama_file"]})


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith(".xlsx"):
        return jsonify(error="Unggah file .xlsx"), 400
    UPLOAD.parent.mkdir(exist_ok=True)
    f.save(UPLOAD)
    try:
        ga_api._cache.pop(str(UPLOAD), None)
        data = ga_api.info_data(str(UPLOAD))
    except Exception as e:
        return jsonify(error=f"Format data tidak sesuai: {e}"), 400
    state.update(data_path=str(UPLOAD), nama_file=f.filename)
    return jsonify({**data, "nama_file": f.filename})


def _worker(job_id, params, seed, snap):
    j = jobs[job_id]

    def progress(gen, total, best, mean, viol):
        j.update(gen=gen, total=total)
        j["best"].append(best); j["mean"].append(mean); j["viol"].append(viol)

    try:
        j["hasil"] = ga_api.jalankan_ga(params, seed, data_path=j["data_path"],
                                        on_progress=progress, snapshot_every=snap)
        j["status"] = "selesai"
    except Exception as e:
        j["status"], j["error"] = "gagal", str(e)


def _cek_param(p):
    if not 20 <= p["pop_size"] <= 300:
        raise ValueError("Ukuran populasi harus antara 20–300.")
    if not 10 <= p["generations"] <= 1000:
        raise ValueError("Jumlah generasi harus antara 10–1000.")
    if not 0 <= p["pc"] <= 1 or not 0 <= p["pm"] <= 0.3:
        raise ValueError("Nilai pc harus 0–1 dan pm harus 0–0,3.")
    if not 0 <= p["elitism"] <= 10:
        raise ValueError("Elitisme harus antara 0–10.")


@app.post("/api/run")
def run():
    b = request.get_json(silent=True) or {}
    params = {**config.PARAM_DEFAULT, **(b.get("params") or {})}
    try:
        _cek_param(params)
    except (ValueError, KeyError, TypeError) as e:
        return jsonify(error=str(e)), 400
    job_id = uuid.uuid4().hex[:10]
    jobs[job_id] = dict(status="berjalan", gen=0, total=0, best=[], mean=[], viol=[],
                        data_path=state["data_path"], nama_file=state["nama_file"])
    threading.Thread(target=_worker, daemon=True, args=(
        job_id, params, b.get("seed"), int(b.get("snapshot_every", 10)))).start()
    return jsonify(job_id=job_id)


@app.get("/api/job/<job_id>")
def job(job_id):
    j = jobs.get(job_id)
    if not j:
        return jsonify(error="job tidak ditemukan"), 404
    out = {k: j.get(k) for k in ("status", "gen", "total", "error", "nama_file")}
    out["riwayat_live"] = {"fitness_terbaik": j["best"], "fitness_rata2": j["mean"], "pelanggaran": j["viol"]}
    if j["status"] == "selesai":
        out["hasil"] = j["hasil"]
    return jsonify(out)


@app.get("/api/asli")
def asli():
    return jsonify(ga_api.jadwal_asli(state["data_path"]))


@app.post("/api/validasi")
def validasi():
    try:
        return jsonify(ga_api.validasi_jadwal((request.get_json() or {}).get("sesi", []), state["data_path"]))
    except (ValueError, KeyError) as e:
        return jsonify(error=str(e)), 400


@app.get("/api/export/<job_id>.<fmt>")
def export(job_id, fmt):
    j = jobs.get(job_id)
    if not j or j["status"] != "selesai" or fmt not in ("csv", "xlsx"):
        return jsonify(error="hasil belum tersedia"), 404
    kolom = ["Hari", "Slot Waktu", "Mata Kuliah", "Semester", "Kelas", "Ruang", "Dosen"]
    df = pd.DataFrame(j["hasil"]["jadwal"])[kolom]
    buf = io.BytesIO()
    if fmt == "csv":
        buf.write(df.to_csv(index=False).encode("utf-8-sig")); mime = "text/csv"
    else:
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Jadwal Detail", index=False)
            rows = [{"Hari": h, "Slot Waktu": s, "Sesi": "\n".join(v)}
                    for h, sl in j["hasil"]["grid"].items() for s, v in sl.items()]
            pd.DataFrame(rows).to_excel(w, sheet_name="Grid Hari x Slot", index=False)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    buf.seek(0)
    return send_file(buf, mimetype=mime, as_attachment=True, download_name=f"jadwal_terbaik.{fmt}")


if __name__ == "__main__":
    app.run(debug=False, threaded=True, host="127.0.0.1", port=5000)
