/* Kuliahify — perilaku antarmuka. Tidak menyentuh algoritma; hanya membaca hasil yang dirender server. */
(function () {
  'use strict';

  /* Upload: nama file + drag and drop */
  const fileInput = document.getElementById('data_file');
  const fileName = document.getElementById('file-name');
  const dropzone = document.getElementById('dropzone');
  function showFile() {
    if (fileInput.files.length) kirimFile(fileInput.files[0]);
    const has = fileInput.files && fileInput.files.length;
    fileName.textContent = has ? 'File dipilih: ' + fileInput.files[0].name : 'Memakai data bawaan';
    dropzone.classList.toggle('has-file', !!has);
  }
  if (fileInput && fileName && dropzone) {
    fileInput.addEventListener('change', showFile);
    ['dragenter', 'dragover'].forEach(function (ev) {
      dropzone.addEventListener(ev, function () { dropzone.classList.add('is-over'); });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      dropzone.addEventListener(ev, function () { dropzone.classList.remove('is-over'); });
    });
  }

  /* Menu samping: tandai bagian yang sedang dilihat */
  const navLinks = Array.from(document.querySelectorAll('.nav-item[data-spy]'));
  if (navLinks.length && 'IntersectionObserver' in window) {
    const targets = navLinks.map(function (a) { return document.getElementById(a.dataset.spy); }).filter(Boolean);
    const setCurrent = function (id) {
      navLinks.forEach(function (a) {
        const on = a.dataset.spy === id;
        a.classList.toggle('is-current', on);
        if (on) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current');
      });
    };
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) setCurrent(e.target.id); });
    }, { rootMargin: '-25% 0px -60% 0px' });
    targets.forEach(function (t) { io.observe(t); });
    setCurrent('beranda');
  }

  /* ===== Alur AG: info, upload, run + polling, hasil ===== */
  const $ = function (q) { return document.querySelector(q); };
  const DAYS = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat'];
  const jam = function (m) { return String(Math.floor(m / 60)).padStart(2, '0') + '.' + String(m % 60).padStart(2, '0'); };
  const jget = function (u) { return fetch(u).then(function (r) { return r.json(); }); };
  let info = null, hasil = null, jobId = null, snapIdx = null, chart = null;

  function notif(msg) { const a = $('#alert'); a.hidden = !msg; a.innerHTML = msg ? '<b>Gagal</b><span></span>' : ''; if (msg) a.lastChild.textContent = msg; }
  function tampilInfo(d) {
    info = d;
    $('#info-data').textContent = d.jumlah.sesi + ' sesi · ' + d.jumlah.dosen + ' dosen · ' + d.jumlah.ruang + ' ruang · ' + d.jumlah.slot + ' slot';
    if (d.nama_file) { fileName.textContent = 'File dipakai: ' + d.nama_file; dropzone.classList.add('has-file'); }
  }
  function kirimFile(f) {
    const fd = new FormData(); fd.append('file', f); notif('');
    fetch('/api/upload', { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (r) {
      if (r.error) { notif(r.error); fileName.textContent = 'Memakai data bawaan'; dropzone.classList.remove('has-file'); fileInput.value = ''; return; }
      tampilInfo(r); fileName.textContent = 'File dipakai: ' + f.name; dropzone.classList.add('has-file');
    });
  }
  function ambilParam() {
    const p = {};
    document.querySelectorAll('#optimasi-form [name]').forEach(function (e) {
      if (e.name === 'seed') return;
      p[e.name] = e.type === 'checkbox' ? e.checked : e.type === 'number' ? Number(e.value) : e.value;
    });
    return p;
  }
  const runButton = $('#run-button');
  runButton.addEventListener('click', function () {
    if (!$('#optimasi-form').reportValidity()) return;
    notif(''); runButton.disabled = true; runButton.classList.add('is-loading');
    runButton.querySelector('.btn-label').textContent = 'Menjalankan optimasi';
    $('#progress').hidden = false;
    fetch('/api/run', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ params: ambilParam(), seed: Number($('[name=seed]').value), snapshot_every: 10 }) })
      .then(function (r) { return r.json(); }).then(function (r) { if (r.error) throw new Error(r.error); jobId = r.job_id; poll(); })
      .catch(function (e) { selesaiRun(); notif(e.message); });
  });
  function selesaiRun() {
    runButton.disabled = false; runButton.classList.remove('is-loading');
    runButton.querySelector('.btn-label').textContent = 'Jalankan optimasi'; $('#progress').hidden = true;
  }
  function poll() {
    jget('/api/job/' + jobId).then(function (j) {
      $('#bar').max = j.total || 1; $('#bar').value = j.gen;
      $('#ptext').textContent = ' generasi ' + j.gen + '/' + j.total;
      gambarChart(j.riwayat_live);
      if (j.status === 'berjalan') return setTimeout(poll, 300);
      selesaiRun();
      if (j.status === 'gagal') return notif('Optimasi gagal: ' + j.error);
      hasil = j.hasil; snapIdx = null; tampilHasil(j.nama_file);
      $('#hasil').scrollIntoView({ behavior: 'smooth' });
    });
  }

  /* ===== Hasil ===== */
  function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function tampilHasil(namaFile) {
    $('#hasil').hidden = false;
    const ok = hasil.pelanggaran === 0, v = $('#verdict');
    v.className = 'verdict ' + (ok ? 'verdict-ok' : 'verdict-warn'); v.textContent = '';
    const ic = el('span', 'verdict-ic', ok ? '\u2713' : '!'); ic.setAttribute('aria-hidden', 'true'); v.appendChild(ic);
    const vt = el('div'); const h2 = el('h2'); if (ok) { h2.appendChild(el('mark', null, 'Jadwal valid.')); h2.appendChild(document.createTextNode(' Tidak ada pelanggaran kendala keras.')); }
    else h2.textContent = 'Masih ada ' + hasil.pelanggaran + ' pelanggaran kendala keras.';
    vt.appendChild(h2);
    vt.appendChild(el('p', null, (namaFile ? 'Data dari ' + namaFile : 'Data bawaan') + ', seed ' + hasil.seed + ', populasi ' + hasil.parameter.pop_size + ', ' + hasil.parameter.generations + ' generasi.' + (ok ? '' : ' Coba tambah generasi atau ukuran populasi.'))); v.appendChild(vt);
    const M = [['Fitness terbaik', hasil.fitness_terbaik.toFixed(4), 'Mendekati 1 lebih baik'], ['Pelanggaran keras', hasil.pelanggaran, 'Pada solusi terbaik'],
      ['Jeda panjang', hasil.jeda_panjang_soft, 'Info saja, belum dioptimalkan'], ['Valid pertama', hasil.generasi_valid_pertama == null ? 'Belum ada' : 'gen. ' + hasil.generasi_valid_pertama, 'Generasi pertama tanpa pelanggaran'],
      ['Waktu eksekusi', hasil.waktu_detik.toFixed(2) + ' detik', 'Satu kali jalan']];
    $('#metrics').textContent = '';
    M.forEach(function (m) { const d = el('div'); d.appendChild(el('dt', null, m[0])); d.appendChild(el('dd', null, m[1])); d.appendChild(el('dd', 'm-note', m[2])); $('#metrics').appendChild(d); });
    const sl = $('#gen-slider'); $('#evo').hidden = !hasil.snapshots.length; sl.max = hasil.snapshots.length - 1; sl.value = sl.max; $('#gen-label').textContent = '';
    $('#dl-csv').href = '/api/export/' + jobId + '.csv'; $('#dl-xlsx').href = '/api/export/' + jobId + '.xlsx';
    const r = $('#rincian'); r.textContent = '';
    Object.keys(hasil.rincian_pelanggaran).forEach(function (k) { const li = el('li', hasil.rincian_pelanggaran[k] ? 'is-bad' : 'is-ok'); li.appendChild(el('span', null, k)); li.appendChild(el('b', null, hasil.rincian_pelanggaran[k])); r.appendChild(li); });
    $('#mode').value = 'semua'; $('#nilai').hidden = true;
    render(); gambarChart(hasil.riwayat);
    if ($('#t-ag')) tampilBanding();
  }
  function jadwalAktif() { return snapIdx !== null && hasil.snapshots[snapIdx] ? hasil.snapshots[snapIdx].jadwal : hasil.jadwal; }
  function detail(r) {
    const d = $('#detail'); d.hidden = false; d.textContent = '';
    d.appendChild(el('b', null, r['Mata Kuliah']));
    d.appendChild(el('p', null, 'Semester ' + r.Semester + ' · kelas ' + (r.Kelas === '-' ? '- (gabungan satu angkatan)' : r.Kelas) + ' · ' + r.Hari + ', ' + r['Slot Waktu'] + ' · ruang ' + r.Ruang + ' · ' + r.Dosen));
  }
  function render() {
    const rows = jadwalAktif(), m = $('#mode').value, n = $('#nilai').value;
    const tampil = rows.filter(function (r) { return m === 'semua' || String(r[m]) === n; });
    $('#row-count').textContent = tampil.length;
    gambarGrid(rows, $('#grid'), m === 'semua' ? null : function (r) { return String(r[m]) === n; }, snapIdx === null ? idBermasalah(hasil.detail_pelanggaran) : null);
    const tb = $('#list-body'); tb.textContent = '';
    tampil.slice().sort(function (a, b) { return DAYS.indexOf(a.Hari) - DAYS.indexOf(b.Hari) || a.mulai_menit - b.mulai_menit; }).forEach(function (r) {
      const tr = el('tr'), td = el('td'); td.appendChild(el('span', 'day day-' + r.Hari.toLowerCase(), r.Hari)); tr.appendChild(td);
      [r['Slot Waktu'], r['Mata Kuliah'], r.Semester, r.Kelas, r.Ruang, r.Dosen].forEach(function (x, i) { tr.appendChild(el('td', i === 1 ? 'course' : i === 0 || i === 2 ? 'num' : null, x)); });
      tb.appendChild(tr);
    });
  }
  /* Grid hari x waktu dengan sumbu proporsional.
     Lebar kolom hari menyesuaikan jumlah blok yang paralel supaya blok tidak berdempetan.
     `bermasalah` = Set id sesi yang melanggar kendala (diberi tanda merah). */
  const PX = 1.3, LANE_W = 176, GAP = 6;
  function gambarGrid(rows, target, cocok, bermasalah) {
    const slots = info.slot;
    const t0 = Math.min.apply(null, slots.map(function (s) { return s.mulai_menit; })) - 20;
    const t1 = Math.max.apply(null, slots.map(function (s) { return s.selesai_menit; })) + 20, H = (t1 - t0) * PX;
    const perHari = DAYS.map(function (hari) {
      const rs = rows.filter(function (r) { return r.Hari === hari; }).sort(function (a, b) { return a.mulai_menit - b.mulai_menit || a.Semester - b.Semester; });
      const lane = []; rs.forEach(function (r) { let i = 0; while (lane[i] !== undefined && lane[i] > r.mulai_menit) i++; lane[i] = r.selesai_menit; r._l = i; });
      return { hari: hari, rs: rs, n: Math.max(1, lane.length) };
    });
    target.textContent = '';
    target.style.gridTemplateColumns = '56px ' + perHari.map(function (d) { return 'minmax(' + (d.n * LANE_W) + 'px,' + d.n + 'fr)'; }).join(' ');
    target.style.minWidth = (56 + perHari.reduce(function (a, d) { return a + d.n * LANE_W; }, 0)) + 'px';
    target.appendChild(el('div', 'tg-head tg-corner'));
    perHari.forEach(function (d) { target.appendChild(el('div', 'tg-head tg-head-' + d.hari.toLowerCase(), d.hari)); });
    const jk = el('div', 'tg-col tg-time'); jk.style.height = H + 'px';
    for (let t = Math.ceil(t0 / 60) * 60; t < t1; t += 60) { const j = el('div', 'tg-jam', jam(t)); j.style.top = (t - t0) * PX + 'px'; jk.appendChild(j); }
    target.appendChild(jk);
    perHari.forEach(function (d, k) {
      const kol = el('div', 'tg-col' + (k % 2 ? ' tg-alt' : '')); kol.style.height = H + 'px';
      for (let t = Math.ceil(t0 / 60) * 60; t < t1; t += 60) { const g = el('div', 'tg-garis'); g.style.top = (t - t0) * PX + 'px'; kol.appendChild(g); }
      d.rs.forEach(function (r) {
        const bad = bermasalah && bermasalah.has(r.id);
        const b = el('div', 'tg-blok sem' + r.Semester + (bad ? ' bentrok' : '') + (cocok && !cocok(r) ? ' redup' : ''));
        b.style.cssText = 'top:' + ((r.mulai_menit - t0) * PX + 1) + 'px;height:' + (r.durasi_menit * PX - 3) + 'px;left:calc(' + (r._l / d.n * 100) + '% + ' + (GAP / 2) + 'px);width:calc(' + (100 / d.n) + '% - ' + GAP + 'px)';
        b.appendChild(el('b', null, r['Mata Kuliah']));
        b.appendChild(el('span', 'tg-meta', 'Smt ' + r.Semester + ' · ' + (r.Kelas === '-' ? 'gabungan' : 'kelas ' + r.Kelas) + ' · ' + r.Ruang));
        b.appendChild(el('span', 'tg-jamrow', jam(r.mulai_menit) + '–' + jam(r.selesai_menit)));
        if (r.durasi_menit * PX > 120) b.appendChild(el('span', 'tg-dosen', r.Dosen));
        if (bad) b.appendChild(el('i', 'tg-flag', '!'));
        b.title = r['Mata Kuliah'] + '\n' + r.Dosen + (bad ? '\nMelanggar kendala keras' : '');
        b.tabIndex = 0; b.addEventListener('click', function () { detail(r); });
        kol.appendChild(b);
      });
      target.appendChild(kol);
    });
  }
  /* Rincian pelanggaran: satu kartu per pelanggaran, dengan sesi yang terlibat */
  const JENIS = { dosen: 'Bentrok dosen', kelas: 'Bentrok kelas', ruang: 'Bentrok ruang', kapasitas: 'Kapasitas ruang', durasi: 'Durasi tidak sesuai' };
  function idBermasalah(list) { const s = new Set(); (list || []).forEach(function (v) { v.sesi.forEach(function (x) { s.add(x.id); }); }); return s; }
  function gambarPelanggaran(target, list, rinci) {
    target.textContent = '';
    const ring = el('div', 'pl-ringkas');
    Object.keys(rinci || {}).forEach(function (k) { const c = el('span', 'pl-chip' + (rinci[k] ? ' is-bad' : ' is-ok')); c.appendChild(document.createTextNode((JENIS[k] || k) + ' ')); c.appendChild(el('b', null, rinci[k])); ring.appendChild(c); });
    target.appendChild(ring);
    if (!list || !list.length) { target.appendChild(el('p', 'pl-kosong', 'Tidak ada pelanggaran kendala keras.')); return; }
    const ul = el('ol', 'pl-list');
    list.forEach(function (v, i) {
      const li = el('li', 'pl-item pl-' + v.jenis), top = el('div', 'pl-top');
      top.appendChild(el('span', 'pl-no', i + 1)); top.appendChild(el('span', 'pl-badge', JENIS[v.jenis] || v.jenis));
      li.appendChild(top); li.appendChild(el('p', 'pl-alasan', v.alasan));
      const sw = el('div', 'pl-sesi');
      v.sesi.forEach(function (x) {
        const c = el('div', 'pl-s');
        c.appendChild(el('b', null, x.mk));
        c.appendChild(el('span', null, 'Smt ' + x.semester + ' · ' + (x.kelas === '-' ? 'gabungan' : 'kelas ' + x.kelas) + ' · ' + x.mhs + ' mhs'));
        c.appendChild(el('span', null, x.hari + ', ' + x.slot + ' · ruang ' + x.ruang));
        c.appendChild(el('span', null, x.dosen));
        sw.appendChild(c);
      });
      li.appendChild(sw); ul.appendChild(li);
    });
    target.appendChild(ul);
  }
  $('#mode').addEventListener('change', function () {
    const m = this.value, n = $('#nilai');
    if (m === 'semua') n.hidden = true;
    else { n.textContent = ''; Array.from(new Set(jadwalAktif().map(function (r) { return String(r[m]); }))).sort().forEach(function (x) { const o = el('option', null, m === 'Kelas' && x === '-' ? '- (gabungan satu angkatan)' : x); o.value = x; n.appendChild(o); }); n.hidden = false; }
    render();
  });
  $('#nilai').addEventListener('change', render);
  $('#gen-slider').addEventListener('input', function () {
    snapIdx = Number(this.value); const sn = hasil.snapshots[snapIdx];
    $('#gen-label').textContent = '· generasi ' + sn.generasi + ', ' + sn.pelanggaran + ' pelanggaran'; render();
  });
  document.querySelectorAll('[data-view]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('[data-view]').forEach(function (b) { b.classList.toggle('is-active', b === btn); b.setAttribute('aria-selected', b === btn ? 'true' : 'false'); });
      $('#view-grid').hidden = btn.dataset.view !== 'grid'; $('#view-list').hidden = btn.dataset.view !== 'list';
    });
  });
  function tampilBanding() {
    jget('/api/asli').then(function (a) {
      $('#t-asli').textContent = 'Jadwal asli (Excel): ' + a.pelanggaran + ' pelanggaran';
      gambarGrid(a.jadwal, $('#g-asli'), null, idBermasalah(a.detail_pelanggaran));
      gambarPelanggaran($('#pl-asli'), a.detail_pelanggaran, a.rincian_pelanggaran);
      if (hasil) {
        $('#t-ag').textContent = 'Hasil AG: ' + hasil.pelanggaran + ' pelanggaran';
        gambarGrid(hasil.jadwal, $('#g-ag'), null, idBermasalah(hasil.detail_pelanggaran));
        gambarPelanggaran($('#pl-ag'), hasil.detail_pelanggaran, hasil.rincian_pelanggaran);
      }
    });
  }

  /* Grafik konvergensi (Chart.js, diperbarui langsung saat proses berjalan) */
  function gambarChart(rw) {
    const canvas = $('#convergenceChart');
    if (!canvas || typeof Chart === 'undefined' || !rw || !rw.fitness_terbaik.length) return;
    const css = getComputedStyle(document.documentElement);
    const cobalt = css.getPropertyValue('--cobalt').trim(), muted = css.getPropertyValue('--ink-3').trim(), grid = css.getPropertyValue('--line-soft').trim();
    const labels = rw.fitness_terbaik.map(function (_, i) { return i + 1; });
    if (!chart) {
      chart = new Chart(canvas, { type: 'line',
        data: { labels: labels, datasets: [
          { label: 'Fitness terbaik', data: [], borderColor: cobalt, backgroundColor: 'rgba(217,70,143,.10)', fill: true, tension: 0.2, pointRadius: 0, borderWidth: 2.5 },
          { label: 'Fitness rata-rata', data: [], borderColor: muted, borderDash: [5, 4], tension: 0.2, pointRadius: 0, borderWidth: 1.75 }] },
        options: { responsive: true, maintainAspectRatio: false, animation: false, interaction: { intersect: false, mode: 'index' },
          plugins: { legend: { display: false }, tooltip: { callbacks: { title: function (i) { return 'Generasi ' + i[0].label; } } } },
          scales: { x: { title: { display: true, text: 'Generasi', color: muted }, grid: { display: false }, ticks: { color: muted, maxTicksLimit: 8 } },
            y: { min: 0, max: 1, title: { display: true, text: 'Fitness', color: muted }, grid: { color: grid }, ticks: { color: muted, maxTicksLimit: 6 } } } } });
    }
    chart.data.labels = labels; chart.data.datasets[0].data = rw.fitness_terbaik; chart.data.datasets[1].data = rw.fitness_rata2; chart.update();
  }

  jget('/api/info').then(tampilInfo);
  tampilBanding0();
  function tampilBanding0() { const t = setInterval(function () { if (info) { clearInterval(t); tampilBanding(); } }, 100); }
})();
