# Session Report: Hasil Phase 2 (Database dan Observation Tracking)

Tanggal: 20 November 2026 · Persetujuan: Phase 2 dengan keputusan A1–A8 (A2 dan A4 dengan revisi).
Status: **selesai, menunggu evaluasi pemilik proyek. Phase 3 belum dimulai.**

Di luar ruang lingkup dan **tidak** diubah: inference, model ONNX/TFLite, aturan alert, PDF, frontend, worker OpenVidu, dan data historis. Tidak ada commit.

---

## 1. Ringkasan

| Kebutuhan Phase 2 | Hasil |
|---|---|
| Backup database sebelum migrasi | Selesai: salinan byte-per-byte, hash identik, integritas ok (bagian 3) |
| Tiga tabel baru, migrasi aditif | Selesai: `observation_seconds`, `session_interval_summary`, `session_participant_summary` |
| Observation tracking persisten | Selesai: detik teramati per peserta per menit per sumber, plus sampel confidence valid |
| Tanpa hitung ganda worker + browser | Selesai: mask detik digabung dengan OR (diuji) |
| Tidak dihitung ulang setelah restart | Selesai: OR idempoten; flush hanya mengirim selisih yang belum tersimpan (diuji) |
| Uji migrasi pada salinan, integritas, rollback | Lulus (bagian 4) |
| Uji restart normal dan crash mendadak | Lulus; batas kehilangan terdokumentasi (bagian 5) |
| Migrasi database produksi | **Belum dijalankan** (lihat risiko R1) |

## 2. Perubahan file

Cadangan kode sebelum perubahan ada di `..\EduAI_cadangan_20261120\sesi_phase2\`.

| File | Perubahan |
|---|---|
| `backend/app/db.py` | Tiga tabel di `SCHEMA` (`CREATE TABLE IF NOT EXISTS`); `SESSION_REPORT_TABLES`; ketiganya didaftarkan di `_pending_migrations()`, sehingga database lama **otomatis dicadangkan** (SQLite backup API, folder `backup/`) sebelum tabel dibuat. Tabel dan kolom lama tidak diubah. |
| `backend/app/observation.py` | **Baru**: `ObservationTracker` (`frame`, `audio`, `flush`, `flush_if_due`, `forget`), `confidence_samples`, `is_observed`, dan fungsi baca `observed_masks`, `observed_seconds`, `observation_span` (dipakai Phase 3) |
| `backend/app/ai_service.py` | `AIManager.observations`; `observe()` dipanggil setelah setiap frame browser/Jitsi dianalisis; sampel audio dicatat di `submit_audio`; `flush_observations()`; flush saat `stop_student` (termasuk lewat `reap_idle`/`stop_exam`) dan saat `shutdown` |
| `backend/app/api.py` | `ingest_status` (worker OpenVidu): detik teramati dari `ts` status per mahasiswa (jam worker, sama dengan jam kejadiannya); flush bila sudah waktunya |
| `backend/app/main.py` | Tugas `_observation_flush`: flush tiap 10 dtk, juga saat tidak ada frame baru; dibatalkan saat shutdown, lalu `ai.shutdown()` melakukan flush terakhir |
| `backend/tests/test_session_tables.py` | **Baru**, 5 tes |
| `backend/tests/test_observation_tracking.py` | **Baru**, 12 tes |

## 3. Kondisi backup

| Backup | Isi | Verifikasi |
|---|---|---|
| `backend/data/backup/eduai-sebelum-session-summary-20261120/` | `eduai.sqlite3` (675.840 B), `-wal` (4.132.392 B), `-shm` (32.768 B); disalin byte-per-byte saat backend mati | SHA-256 identik dengan aslinya. Pada salinan: `integrity_check` = ok, `foreign_key_check` kosong, 23 tabel; users 12, exams 25, events 440, reviews 83, evidence 148, presence 19, connection_log 1, report_finals 2 |
| Backup otomatis kode baru | Dibuat `Database()` saat pertama kali membuka database lama: `backup/eduai-sebelum-migrasi-<waktu>.sqlite3` | Diuji pada salinan: berisi data lama (440 kejadian), tanpa tabel baru |

Database produksi tidak dibuka oleh SQLite selama Phase 2; integritasnya diperiksa pada salinan. Hash seluruh `backend/data` sebelum dan sesudah semua tes identik, kecuali tiga file backup baru di atas.

## 4. Hasil migrasi (pada salinan database produksi)

Skrip uji dijalankan pada salinan backup di folder sementara:

| Langkah | Hasil |
|---|---|
| Sebelum | 22 tabel, integrity ok, FK ok |
| Migrasi (kode baru) | Backup otomatis `eduai-sebelum-migrasi-20261120-220028.sqlite3` dibuat; **3 tabel baru (0 baris)**; **jumlah baris 22 tabel lama tidak berubah**; integrity ok; FK ok |
| Kode lama membuka DB termigrasi | Berjalan; events = 440; tabel lama utuh |
| Rollback (`DROP TABLE` tiga tabel baru) | Database **sama persis** dengan sebelum migrasi (jumlah baris semua tabel); integrity ok; FK ok |
| Migrasi ulang setelah rollback | Tabel baru ada lagi; tabel lama utuh; integrity ok |

**Strategi rollback:** kembalikan kode lama, yang tetap bisa berjalan dengan tabel baru ada. Bila perlu, `DROP TABLE observation_seconds, session_interval_summary, session_participant_summary` dijalankan **hanya dengan persetujuan**. Alternatif: pulihkan dari salah satu backup di bagian 3.

## 5. Observation tracking: perilaku dan batas kehilangan

| Aturan | Implementasi |
|---|---|
| Resolusi | 1 detik, dari **timestamp aktual** (jam server untuk browser/Jitsi; jam worker untuk OpenVidu, sama dengan jam kejadiannya) |
| Jeda | Detik di antara dua frame ditandai hanya bila jeda ≤ 2,0 dtk; jeda lebih panjang bukan waktu teramati |
| Frame yang dihitung | Status `analyzed` atau `cannot_analyze` dengan gambar nyata. Frame tanpa gambar / model tidak siap memutus jembatan dan tidak dihitung. Periode `CANNOT_ANALYZE` dikurangkan di Phase 3. |
| Tanpa hitung ganda | `observed_mask = observed_mask \| baru` di SQL; dua sumber digabung dengan OR saat dibaca |
| Penyimpanan | Satu transaksi (`Database.run_all`) per flush; memori baru dihapus **setelah** commit. Bila gagal, data disimpan untuk percobaan berikutnya dan tidak tertulis ganda. |
| Flush | Tiap 10 dtk (tugas latar belakang + saat frame/status masuk), saat analyzer berhenti, dan saat shutdown normal |
| Confidence (A2) | Ponsel/COCO buku: hanya deteksi positif (skor > 0; 0,0 = tidak terdeteksi, **tidak** dihitung). CLIP: setiap inference berhasil. Suara: setiap sampel audio (API hanya menerimanya dengan persetujuan audio). Disimpan sebagai jumlah dan banyaknya sampel per menit; rata-rata dihitung di Phase 3; tanpa sampel → N/A. |

**Batas kehilangan data:**

| Kejadian | Kehilangan |
|---|---|
| Restart / shutdown normal | **Tidak ada** (flush saat `stop_student` dan `shutdown`; diuji: 4 dtk tersimpan utuh setelah restart) |
| Crash mendadak (proses mati, listrik padam) | Paling banyak bagian yang belum di-flush: **≤ 10 dtk pengamatan per peserta**, ditambah ≤ 2 dtk di awal setelah restart karena jembatan ke frame sebelum crash tidak disimpan (diuji: 30 dtk frame → 21 dtk tersimpan, flush terakhir di detik ke-20) |
| Gagal tulis SQLite (disk penuh, terkunci) | Tidak hilang selama proses hidup: data tetap di memori dan ditulis pada flush berikutnya |

## 6. Hasil pengujian

**Tes baru (17, semua lulus):**

| Tes | Hasil yang diharapkan dan teramati |
|---|---|
| `test_new_database_has_the_three_tables_with_keys` | 3 tabel; PK sesuai desain; FK hanya pada tabel hasil (`exams`, `users`); database baru tanpa backup |
| `test_constraints_reject_bad_rows` | Ditolak: mask ≥ 2^60, mask negatif, sumber tak dikenal, PK ganda, exam tak dikenal (FK), interval 0 dtk dan > 300 dtk, cakupan > 1, skor > 1, probabilitas tanpa status `calibrated` |
| `test_existing_database_is_backed_up_then_migrated_additively` | Backup otomatis berisi data lama; jumlah baris lama tetap; integrity/FK ok; dibuka ulang tanpa backup kedua (idempoten) |
| `test_rollback_drops_only_the_new_tables` | Setelah DROP: tabel lama utuh, integrity/FK ok; dibuka ulang → tabel dibuat lagi |
| `test_gaps_up_to_two_seconds_are_bridged_longer_gaps_are_not` | Jeda 0,5/0,8/1,9 dtk → 4 detik; jeda 3,0 dan 6,6 dtk → hanya 2 detik sendiri. Total 6 |
| `test_runs_cross_minute_boundaries_into_two_rows` | 59,5 → 60,5 dtk: dua baris menit, mask bit 59 dan bit 0 |
| `test_a_frame_that_is_not_observed_breaks_the_bridge` | 2 detik (bukan 3) |
| `test_frame_counts_are_not_the_basis` | 2 fps dan 5 fps selama 10 dtk → masing-masing 10 dtk |
| `test_browser_and_worker_overlap_count_once` | 0–9 + 5–14 → 15 dtk (bukan 20) |
| `test_restart_resending_the_same_seconds_does_not_double` | 0–9 lalu 5–11 → 12 dtk; flush berulang tidak menambah |
| `test_flush_failure_keeps_the_data_and_writes_it_once_later` | Gagal → 0 tersimpan, data tetap di memori; berhasil → 3 dtk, sekali saja |
| `test_sudden_crash_loses_at_most_the_unflushed_window` | 30 dtk frame, tanpa flush akhir → tepat 21 dtk tersimpan (kehilangan ≤ 10 dtk) |
| `test_normal_restart_of_the_backend_keeps_every_second` | Aplikasi ditutup normal lalu dibuka lagi → 4 dtk tersimpan |
| `test_confidence_samples_follow_each_model` | 0,0 tidak dihitung; deteksi positif dan CLIP dihitung; frame buruk tanpa sampel; aturan "teramati" |
| `test_confidence_sums_and_audio_samples_are_stored` | Ponsel jumlah 1,4 / n 2; CLIP n 1; COCO n 0; suara speech 1, whisper 1, paper 2 (nilai > 1 dan NaN dibuang); audio tidak menambah detik teramati |
| `test_browser_frames_are_tracked_with_the_server_clock` | 10 frame lewat API → 5 dtk, sumber browser, rentang = (BASE_T, BASE_T + 5) |
| `test_worker_status_is_tracked_and_merged_with_the_browser_fallback` | Browser 0–5 + worker 3–9 → 10 dtk; status akhir worker (`no_frame`) tidak menambah detik |

**Regresi:**

| Paket | Hasil |
|---|---|
| Backend | **286 lulus**, 0 gagal, 2 dilewati (269 lama + 17 baru) |
| Modul AI | 122 lulus, 2 dilewati (tidak diubah) |
| Frontend | tidak diubah |
| Data produksi | Hash `backend/data` identik, kecuali 3 file backup baru |

## 7. Risiko yang tersisa

| ID | Risiko | Penanganan |
|---|---|---|
| **R1** | **Migrasi produksi terjadi otomatis** saat backend versi baru pertama kali dijalankan pada `backend/data/eduai.sqlite3` (pola yang sudah ada di proyek). | Aditif dan didahului backup otomatis, ditambah backup manual bagian 3. Bila migrasi produksi ingin ditunda, jangan jalankan backend versi ini sampai disetujui. |
| R2 | Jalur worker tidak mengirim skor detektor, sehingga **confidence dari jalur OpenVidu belum tersedia** (detik teramati tersedia). | Butuh perubahan worker (di luar Phase 2, perlu persetujuan). Sampai itu, confidence untuk sesi worker = N/A. |
| R3 | Jam worker di mesin lain bisa berbeda dari jam backend. | Event dan cakupan worker memakai jam yang sama (jam worker), jadi tetap konsisten. Sinkronkan NTP bila worker di mesin terpisah. |
| R4 | Event browser yang tertinggal "open" setelah crash masih memanjang sampai "sekarang" di `cases`. | Ditangani di Phase 3: waktu aktif = episode ∩ detik teramati ∩ [S, E). |
| R5 | Crash mendadak kehilangan ≤ 10 dtk (+ ≤ 2 dtk) per peserta. | Terdokumentasi; dapat diperkecil dengan flush lebih sering, dengan biaya tulis lebih banyak. |
| R6 | Beban tulis. | Satu UPSERT per (peserta, menit, sumber) per flush 10 dtk. Belum diukur dengan banyak peserta; dapat ditambahkan ke `soak_test.py` di Phase 7. |
| R7 | Sesi sebelum fitur ini tidak punya data cakupan. | Sesuai A7: "Tidak tersedia", tanpa hitung ulang (Phase 3/6). |

## 8. Langkah berikutnya (menunggu persetujuan)

Phase 3, mesin interval dan metrik:

- interval 300 dtk dengan bobot parsial;
- penggabungan dan pemotongan episode;
- average confidence dari jumlah/banyak sampel (N/A tanpa sampel);
- duration score dan cakupan;
- alasan tanpa data dari `connection_log`, `CANNOT_ANALYZE`, dan cakupan.

Phase 3 hanya membaca tabel Phase 2 dan `events`; belum menulis tabel hasil (Phase 4).
