# Audit Implementasi Session Report EduAI (Phase 1, hanya baca)

Tanggal: 20 November 2026 · Cabang: `istilah-prodi` (dengan perubahan Tahap 0–G-P1 yang belum di-commit)
Acuan: spesifikasi *Implementation Specification — EduAI Session Report* dan [DESIGN_SESSION_SUMMARY_INTERVAL.md](DESIGN_SESSION_SUMMARY_INTERVAL.md).

Tidak ada kode, database, model, konfigurasi, atau environment yang diubah. Semua klaim di bawah berasal dari kode yang dibaca langsung. Rujukan ditulis sebagai `file:fungsi` atau `file:baris`.

---

## 1. Arsitektur aktual

```
Browser mahasiswa ─ JPEG + waktu ambil ─▶ api.upload_frame ─▶ AIManager.submit_jpeg ─┐
Worker OpenVidu ─ frame LiveKit ─▶ livekit_worker._consume ─▶ StudentAnalyzer ─┐       │
                                                                 │             ▼       ▼
                                          (worker, prosesnya sendiri)   StudentAnalyzer.process (pipeline.py)
                                                                          ├ MediaPipePerception.process (perception.py)
                                                                          ├ EventEngine.update (temporal.py)
                                                                          ├ EvidenceBuffer (evidence.py)
                                                                          └ PerfStats.record (perf.py, MEMORI)
   worker ─ /api/ai/events, /api/ai/evidence, /api/ai/status (ts per mahasiswa) ─▶ store.upsert_event / save_evidence / upsert_status
   backend in-process ─ AIManager.persist ─▶ store.upsert_event / save_evidence / upsert_status
                                                        │
              SQLite: events · evidence · ai_status (1 baris terakhir) · presence · connection_log · reviews
                                                        │
   cases.episodes_of / summarize · summary.build (exam_summaries, sekali) · report.by_indicator · report_export.build_pdf
```

**Konsep "sesi":** tidak ada tabel sesi. Sesi = satu ujian (`exams.id`). `session_id` dari AI = `str(exam_id)` (`api._ingest_ids`). Peserta = `exam_students`.

## 2. File dan fungsi terkait

| Area | File : fungsi | Temuan |
|---|---|---|
| Model / ONNX | `perception.py:MediaPipePerception.__init__/process`, `book_clip.py:ClipBookClassifier.score` | Satu-satunya ONNX adalah CLIP (buku). Detektor objek, wajah, dan landmark berupa TFLite (MediaPipe). Tidak diubah. |
| Output confidence | `perception.py:process` | `phone_score`/`book_score` = skor maksimum kelas COCO **di antara deteksi ≥ `detector_threshold` (0,35)**, atau **0,0 bila tidak ada deteksi** (bukan confidence model 0). `book_clip_score` = pangsa softmax, **selalu ada** setiap CLIP berjalan. Skor deteksi wajah/orang **tidak diekstrak** (hanya jumlah). Yaw/pitch adalah geometri, tanpa confidence. |
| Skor suara | `api.submit_audio` → `AIManager.submit_audio` → `EventEngine.update_audio` | YAMNet di browser: speech/whisper/media/paper 0–1, ±4 sampel/dtk, hanya bila persetujuan audio (`consents.audio_accepted`). |
| Temporal / episode | `temporal.py:SustainedIndicator`, `EventEngine.update/flush`, `cases.py:merge_episodes/episodes_of` | Episode = event open→closed. Event yang bertumpuk ≤ 2 dtk digabung (`EPISODE_JOIN_S`). |
| HEAD_TURN_REPEATED | `temporal.py:RepeatCounter`; `EventEngine.update` bagian "3b" | **Terbukti turunan:** `self.repeat.update(s.ts, head_active)` memakai sinyal `head_active` yang sama dengan `HEAD_TURN`. Event instan (`closed` langsung), tanpa bukti. |
| Statistik episode | `temporal.py:_with_stats` (`details.stats_version 1`) | Per **episode**: `n_frames` aktif; confidence ponsel (mean/peak) **hanya dari frame aktif (≥ 0,5)**; buku COCO/CLIP terpisah. Belum ada statistik per interval atau per frame di luar episode. |
| Pencatatan waktu analisis | `perf.py:PerfStats`, `ai_service.py:_Entry`, `performance()` | **Hanya di memori**, jendela 60 dtk, hilang saat restart. `ai_status` menyimpan satu baris terakhir per peserta. |
| Worker → status | `api.ingest_status`, `schemas.StatusItem` (`ts: Optional[float]`) | Worker mengirim status **setiap frame** dengan `ts` (jam worker). Bisa dipakai untuk cakupan jalur worker tanpa mengubah worker. |
| Jendela sesi | `exams.monitoring_started_at` (`api.py:1032`), `report.session_end`, `summary.exam_window` | `monitoring_started_at` **ditimpa** setiap kali pemantauan dimulai ulang, jadi periode pertama hilang. `session_end` = yang lebih awal antara "Selesai" dan akhir jadwal. |
| Kehadiran | `presence` (nilai terakhir), `connection_log` (riwayat connected/disconnected) | `connection_log` bisa menjadi dasar alasan "tidak terhubung". |
| Restart | `main.py:lifespan` | Mengatur `monitoring_active=0` dan menutup event **worker** yang masih open. Event jalur **browser** yang open saat proses mati **tetap open**, dan `cases._end` menganggapnya berakhir "sekarang". |
| Alert | `cases.py:rule_status`, `config.yaml:summary_rules`, `summary.check_all` | Terpisah dari hitungan; tidak disentuh. |
| Ringkasan sesi | `summary.py:build/generate`, tabel `exam_summaries` (PK exam_id, `INSERT OR IGNORE`) | Satu kali (pre_end/final); berisi jumlah, bukan persentase. |
| Laporan | `api.py:_report_data/finalize_report`, `report.py:by_indicator/copy_frames`, `report_export.py:build_pdf/build_xlsx` | Finalisasi = `report_finals` + salinan gambar, dalam satu `db.run_all`. PDF per ujian (templat 3 halaman). Tabel G-R1 "Ringkasan per indikasi" untuk seluruh sesi. |
| Skema / migrasi | `db.py:SCHEMA` (`CREATE TABLE IF NOT EXISTS`), `Database.__init__` (`ALTER TABLE … ADD COLUMN` bila kolom belum ada) | Pola migrasi aditif sudah dipakai. `PRAGMA foreign_keys = ON`, WAL. Tabel yang ditulis AI (`events`, `ai_status`, `presence`) **tanpa FK**. |
| Tes | `backend/tests` (266 fungsi), `ai/eduai-ai/tests` (122) | Isolasi DB (`tmp_path`) dan `.env` (`tests/conftest.py`). |

## 3. Alur data yang relevan untuk Session Report

1. Setiap frame dianalisis dengan `ts` = jam server (browser/Jitsi) atau jam worker (OpenVidu).
2. Hasilnya berupa event (episode) yang tersimpan dengan `start_ts`/`end_ts`. Confidence hanya per episode, di `details`.
3. **Tidak ada** catatan persisten tentang *kapan peserta benar-benar teramati*. Itu penyebut yang dibutuhkan p(i,k) dan cakupan.
4. Laporan dan PDF membaca event saat diminta. Yang dibekukan saat finalisasi hanya gambar kunci.

## 4. Kekurangan terhadap spesifikasi

| Kebutuhan | Status | Kekurangan |
|---|---|---|
| Interval 300 dtk, `[a,b)`, bobot parsial | Belum ada | Modul baru |
| Average confidence C(i,k) dari pengamatan valid | Sebagian | Hanya per episode dan hanya frame aktif. Butuh akumulator per waktu (termasuk di luar episode) dan definisi "valid" per sumber (bagian 6.2). |
| Duration score p(i,k) | Belum ada | Butuh waktu teramati persisten (penyebut) |
| Cakupan + alasan tanpa data | Belum ada | Butuh waktu teramati + `connection_log` + `CANNOT_ANALYZE` |
| P(i), P_total berbobot dari konfigurasi | Belum ada | Bobot belum ada di `config.yaml` |
| Penyimpanan per peserta (finalisasi, idempoten) | Belum ada | Tabel baru; ikut transaksi `finalize_report` |
| Kalibrasi Platt tingkat sesi | Belum ada | **Ground truth tingkat sesi tidak tersedia** (bagian 8) |
| PDF Session Summary / per indikasi / informasi sesi | Belum ada | PDF sekarang per ujian, bukan per peserta |

## 5. Risiko kompatibilitas

1. **`monitoring_started_at` ditimpa saat pemantauan dimulai ulang.** Bila S diambil dari kolom ini, periode pemantauan pertama hilang. Usulan: S = awal jadwal ujian (`summary.exam_window`) atau observasi pertama, mana yang lebih awal; E = `report.session_end`.
2. **Event browser yang tertinggal open setelah crash** akan memanjang sampai "sekarang". Mesin interval harus memotong episode pada E **dan** pada waktu teramati terakhir peserta.
3. **Dua sumber sekaligus** (fallback browser + worker untuk mahasiswa yang sama): waktu teramati tidak boleh dijumlah dua kali. Penyimpanan cakupan harus berbentuk *gabungan detik*, bukan jumlah (lihat 7.1).
4. **Jam worker berbeda dari jam backend.** Event worker memakai jam worker. Cakupan jalur worker juga memakai `ts` worker, supaya konsisten dengan event-nya. Bila worker di mesin lain, jamnya harus disinkronkan (NTP). Risiko ini didokumentasikan.
5. **Beban tulis SQLite:** 2–5 fps × N peserta. Menulis per frame bisa membebani WAL. Usulan: akumulasi di memori dan *flush* tiap 10 dtk, saat berganti ember, dan saat analyzer berhenti. Kehilangan maksimum saat crash: ≤ 10 dtk cakupan.
6. **Foreign key:** tabel AI yang ada sengaja tanpa FK. Tes `AIManager` memakai id fiktif (`test_api.test_busy_frames_are_dropped`, `test_ai_performance.test_busy_frames_are_counted_per_student`). Tabel cakupan mengikuti konvensi itu (tanpa FK). Tabel hasil finalisasi boleh ber-FK ke `exams(id)` dan `users(id)`, karena ditulis setelah data valid.
7. **PDF templat 3 halaman** (`test_report.test_pdf_follows_template…`, `test_report_by_indicator.test_template_stays_three_pages…`). Ringkasan per peserta akan menambah halaman, sehingga tes templat perlu dibedakan antara sesi tanpa dan dengan lampiran.
8. **Laporan yang sudah final** tidak boleh berubah. Session Summary untuk sesi yang final sebelum fitur ini ditandai "tidak tersedia (sesi sebelum fitur)", tanpa menghitung ulang data historis.

## 6. Rancangan perubahan

### 6.1 Duration score dan cakupan, per peserta *s*, indikasi *i*, interval *k*

- Interval: `[S + 300k, min(S + 300(k+1), E))`, hanya bila d_k > 0; `w_k = d_k / 300`.
- `u_k` (detik dapat dianalisis) = |detik teramati ∩ interval| − |CANNOT_ANALYZE ∩ interval|, memakai gabungan himpunan detik.
- `a_i,k` = |episode gabungan (`episodes_of`) ∩ interval ∩ detik teramati|. Ditambah irisan dengan detik teramati supaya event "open" sisa crash tidak menambah waktu.
- `p_i,k = a_i,k / u_k` bila u_k > 0; bila u_k = 0: `p = 0` dengan alasan dari `connection_log`, cakupan, atau `CANNOT_ANALYZE`.
- `P_i = Σ w_k p_i,k / Σ w_k`. Interval tanpa data **tetap** di penyebut (sesuai spesifikasi).
- Cakupan: `c_k = u_k / d_k`, `C = Σ w_k c_k / Σ w_k`.

### 6.2 Average confidence C(i,k): definisi pengamatan valid per sumber (perlu disetujui)

| Indikasi | Sumber skor | Pengamatan valid | Catatan |
|---|---|---|---|
| PHONE_VISIBLE | EfficientDet-Lite0 `cell phone` | Lintasan detektor yang **mengembalikan deteksi ponsel** (skor ≥ 0,35, ambang detektor) | 0,0 = "tidak ada deteksi", **tidak** dihitung sebagai confidence 0 |
| BOOK_VISIBLE | COCO `book` | Sama, deteksi buku ≥ 0,35 | Dilaporkan **terpisah** dari CLIP |
| BOOK_VISIBLE | CLIP P(buku) | Setiap kali CLIP berjalan | Pangsa softmax; skalanya berbeda dari COCO |
| OTHER_VOICE / WHISPER / BOOK_SOUND | YAMNet speech/whisper/paper | Setiap sampel audio yang diterima (bila persetujuan audio) | Per **sampel audio**, bukan per frame video, sehingga tidak bias oleh pengulangan |
| FACE_ABSENT, HEAD_TURN, MULTIPLE_PERSONS | — | **Tidak berlaku** | Tidak ada confidence model yang bermakna (ketiadaan wajah, sudut geometri). Skor deteksi wajah/orang tidak diekstrak. Mengekstraknya berarti mengubah perception (di luar lingkup, perlu persetujuan). |

### 6.3 Agregasi

- `P_total = Σ v_i P_i / Σ v_i` hanya atas indikasi yang **berlaku** bagi peserta:
  - `HEAD_TURN_REPEATED` dikeluarkan (terbukti turunan);
  - indikasi suara dikeluarkan bila tidak ada persetujuan audio;
  - kategori info dan `CANNOT_ANALYZE` tidak termasuk;
  - indikasi backend (`CAMERA_OFF`, `MIC_OFF`, `LOCKDOWN_LOST`) diusulkan dikeluarkan di versi pertama.
- `v_i` dari `config.yaml` → `session_summary.indicator_weights`, bawaan semua 1. Bobot dan versi config disimpan bersama hasil.
- Average confidence **tidak** diagregasi menjadi satu angka sesi, karena skalanya berbeda antarsumber. Nilainya disimpan dan ditampilkan per indikasi/sumber.

### 6.4 Kalibrasi (Phase 5)

- Modul antarmuka `calibration.py`: muat kalibrator (berkas JSON: `a`, `b`, `version`, `target_definition`, `trained_on`, `brier`, `n`) bila ada dan valid. Selain itu status `not_calibrated`, dan probabilitas **tidak** dihitung.
- `P_session = 1 / (1 + exp(−(a · R + b)))` dengan R = P_total, **hanya** bila kalibrator valid.
- Skrip pelatihan (`scripts/calibrate_session.py`) dibuat bersama tes kebocoran, Brier, dan kurva kalibrasi memakai data buatan. Skrip ini tidak dipakai di produksi sampai ada ground truth.

## 7. Rencana migrasi database (aditif; belum dijalankan)

Konvensi yang diikuti: nama `snake_case`, waktu ISO UTC `TEXT` (`now_iso`), `CREATE TABLE IF NOT EXISTS` di `db.SCHEMA`.

### 7.1 `observation_seconds`: pelacakan waktu teramati

| Kolom | Tipe | Keterangan |
|---|---|---|
| exam_id, student_id | INTEGER NOT NULL | tanpa FK (konvensi tabel AI, risiko 6) |
| minute_start | TEXT NOT NULL | awal menit UTC |
| source | TEXT NOT NULL | browser / jitsi / livekit |
| observed_mask | INTEGER NOT NULL | 60 bit, bit *n* = detik ke-*n* teramati (frame dianalisis dan Δ ke frame sebelumnya ≤ G = 2,0 dtk) |
| frames | INTEGER NOT NULL | informasi |
| conf_json | TEXT | akumulator confidence per sumber `{phone:{sum,n}, book_coco:…, book_clip:…, speech:…, whisper:…, paper:…}` |
| updated_at | TEXT NOT NULL | |

PK `(exam_id, student_id, minute_start, source)`. Upsert memakai `observed_mask = observed_mask | ?`, sehingga restart dan pengiriman ulang **tidak** menghitung ganda. Gabungan antarsumber = OR mask, juga tanpa hitungan ganda (risiko 3). Resolusinya 1 detik, berbasis timestamp, bukan jumlah frame.

### 7.2 `session_interval_summary`: hasil per peserta, indikasi, interval (ditulis saat finalisasi)

`exam_id, student_id, indicator, k, start_ts, end_ts, d_s, w, active_s, analysable_s, coverage, duration_score, conf_mean, conf_n, conf_source, no_data_reason, algo_version, config_version, computed_at`; PK `(exam_id, student_id, indicator, k, conf_source)`.

### 7.3 `session_participant_summary`: hasil sesi per peserta (ditulis saat finalisasi)

`exam_id, student_id, indicator` (`'*'` = baris total), `duration_score` (P_i atau P_total), `coverage`, `sum_w, n_intervals, n_no_data, observed_s, exam_s`, `conf_json`, `weights_json, config_version, algo_version`, `calibration_status, calibration_version, calibrated_probability` (NULL bila `not_calibrated`), `computed_at`. PK `(exam_id, student_id, indicator)`; FK ke `exams(id)` dan `users(id)`.

### 7.4 Finalisasi dan idempotensi

- Ditulis di dalam `finalize_report`, dalam `db.run_all` yang sama dengan `report_finals`.
- `INSERT OR IGNORE` + PK, plus pemeriksaan "sudah final". Finalisasi ulang ditolak seperti sekarang (`_not_final`).

### 7.5 Backup dan rollback

- **Backup:** salin `backend/data/eduai.sqlite3` (beserta `-wal`/`-shm`, atau `VACUUM INTO`) ke `backend/data/backup/eduai-sebelum-session-summary-<tanggal>.sqlite3` sebelum backend versi baru pertama kali dijalankan.
- **Rollback:** kode lama tidak membaca tabel baru, jadi cukup kembali ke kode lama. Bila perlu, `DROP TABLE` ketiga tabel baru **hanya setelah persetujuan**. Tabel lama tidak disentuh.
- **Uji migrasi:** di salinan database (tmp), bukan produksi. Pola ini sudah dipakai `test_sound_labels.test_old_database_is_migrated_without_losing_rows`.

## 8. Ground truth untuk kalibrasi

| Kandidat | Isi | Layak untuk Platt tingkat sesi? |
|---|---|---|
| `ai/eduai-ai/labels.csv` | 2 baris label interval, satu video; baris terakhir rusak (sisa teks PowerShell) | Tidak |
| `ai/eduai-ai/dataset_raw.zip` | 4.425 gambar (tingkat frame, mis. kelas `kosong`) | Tidak; ini data frame, bukan label sesi |
| Tinjauan pengawas (`reviews`) | Valid/Tidak Valid per kejadian yang **ditandai sistem** | Tidak sebagai ground truth. Hanya sesi yang ditandai yang punya label, sehingga bias seleksi, dan targetnya "pengawas mengonfirmasi indikasi", bukan perilaku sebenarnya. |
| Database produksi (148 paket bukti) | Data uji coba, tanpa label sesi | Tidak |

**Kesimpulan:** ground truth tingkat sesi **belum tersedia**. Phase 5 hanya menyiapkan antarmuka dan status `not_calibrated`, ditambah dokumen kebutuhan data:

- definisi target, misalnya "sesi peserta memuat ≥ 1 perilaku yang ditetapkan dua pelabel independen";
- jumlah sesi berlabel dengan pemisahan per peserta (protokol §4);
- set kalibrasi dan set evaluasi terpisah.

## 9. Rencana uji

**Mesin interval dan metrik (unit, data buatan):**

| # | Kasus | Hasil yang diharapkan |
|---|---|---|
| 1 | Sesi 3 menit | 1 interval, w = 0,6, P_i = p_i,0 |
| 2 | Sesi 50 menit | 10 interval, Σw = 10, tanpa interval d = 0 |
| 3 | Sesi 52 menit | 10 × w = 1,0 + 1 × w = 0,4; Σw = 10,4 |
| 4 | Interval tanpa data | p = 0, alasan tersimpan, tetap di penyebut, cakupan 0 |
| 5 | Episode 290–310 dtk | 10 dtk di k = 0, 10 dtk di k = 1 |
| 6 | Worker + browser bertumpuk | Waktu aktif dan waktu teramati masing-masing dihitung sekali (OR mask, `episodes_of`) |
| 8 | Pengamatan parsial | u_k < d_k → p = a/u; cakupan c_k = u/d |
| 9 | Audio tanpa persetujuan | Indikasi suara tidak ada di P_total, bukan 0 |
| 10 | HEAD_TURN_REPEATED | Tidak ada di P_total; tetap tercatat sebagai kejadian |
| 11 | Dua metrik | C dari pengamatan valid (0,0 tanpa deteksi tidak dihitung); p dari durasi; disimpan di kolom berbeda |
| 12 | Agregasi berbobot | 0,5 / 0,6 / 0,8 / 0,5, v = 1 → 0,60; v = (2, 1, 1, 1) → 0,58 |

**Integrasi:**

| # | Kasus | Hasil yang diharapkan |
|---|---|---|
| 7 | Restart saat sesi | Mask sebelum restart tetap ada; tambahan sesudah restart di-OR; kehilangan ≤ interval flush |
| 13 | Finalisasi | Hasil tertulis sekali; finalisasi ulang ditolak; PDF membaca tabel hasil (bukan menghitung ulang) |
| 14 | Regresi | Seluruh tes lama lulus; tes templat PDF disesuaikan dengan lampiran per peserta |

**Kalibrasi:**

- kebocoran (peserta sama di latih dan uji → berhenti);
- Brier pada data buatan dengan nilai diketahui;
- kurva kalibrasi (bin);
- kalibrator tidak ada → `not_calibrated` dan PDF menulis "Belum tersedia";
- versi kalibrator berubah → versi tercatat di hasil.

**Migrasi:** database lama (salinan) → tabel baru dibuat, baris lama utuh. Rollback = kode lama tetap berjalan dengan tabel baru ada.

## 10. Urutan implementasi dan file

| Phase | File baru | File diubah |
|---|---|---|
| 2: tabel dan pelacakan waktu | — | `backend/app/db.py` (SCHEMA + migrasi aditif); `backend/app/ai_service.py` (akumulator mask per peserta, flush); `backend/app/api.py` (`ingest_status` → cakupan worker; `submit_audio` → akumulator confidence suara); `ai/eduai-ai/src/eduai_ai/pipeline.py` (mengembalikan skor valid per frame bila perlu) |
| 3: mesin interval dan metrik | `backend/app/session_summary.py` (fungsi murni) | `ai/eduai-ai/config.yaml` (`session_summary`: interval 300, G = 2,0, `indicator_weights`) |
| 4: agregasi dan finalisasi | — | `backend/app/api.py` (`finalize_report`, endpoint `GET /api/sessions/{id}/session-summary`); `backend/app/session_summary.py` |
| 5: kalibrasi | `backend/app/calibration.py`; `ai/eduai-ai/scripts/calibrate_session.py`; `docs/` kebutuhan dataset | — |
| 6: PDF | — | `backend/app/report_export.py` (lampiran per peserta: Session Summary, Ringkasan per indikasi, Informasi sesi); `backend/app/api.py` (`_report_data`); XLSX sheet |
| Uji | `backend/tests/test_session_summary_*.py`, `backend/tests/test_observation_tracking.py`, `backend/tests/test_calibration.py` | Tes templat PDF (bila lampiran menambah halaman) |
| 7: laporan hasil | `docs/EDUAI_SESSION_REPORT_IMPLEMENTATION_RESULTS.md` | `docs/API.md` |

## 11. Keputusan yang perlu disetujui sebelum Phase 2

| ID | Keputusan | Usulan |
|---|---|---|
| A1 | Jendela sesi S | Awal jadwal ujian atau observasi pertama, mana yang lebih awal (bukan `monitoring_started_at`, yang ditimpa saat restart) |
| A2 | Pengamatan valid untuk C(i,k) | Tabel 6.2; FACE_ABSENT/HEAD_TURN/MULTIPLE_PERSONS "tidak berlaku" |
| A3 | Indikasi backend di P_total | Tidak di versi pertama |
| A4 | Resolusi dan flush pelacakan | Mask 1 dtk per menit; G = 2,0 dtk; flush tiap 10 dtk |
| A5 | Tabel tanpa FK untuk pelacakan; dengan FK untuk hasil | Sesuai risiko 6 |
| A6 | PDF | Lampiran "Session Summary per peserta" di PDF yang sama; templat 3 halaman tetap untuk bagian I–V |
| A7 | Sesi final sebelum fitur | "Tidak tersedia", tanpa menghitung ulang |
| A8 | Kalibrasi | `not_calibrated` sampai ada ground truth tingkat sesi |
