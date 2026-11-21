# Session Report: Hasil Phase 3 (Mesin Interval dan Metrik)

Tanggal: 20 November 2026 · Status: **selesai, menunggu evaluasi pemilik proyek. Phase 4 belum dimulai.**

Ruang lingkup: fungsi perhitungan **hanya-baca**. Tidak ada penulisan ke tabel hasil (itu Phase 4), tidak ada endpoint, dan tidak ada perubahan pada PDF, alert, model, inference, atau frontend. Tidak ada commit.

---

## 1. Perubahan file

| File | Perubahan |
|---|---|
| `backend/app/session_summary.py` | **Baru.** Mesin interval dan metrik (fungsi murni, hanya membaca `events`, `observation_seconds`, `presence`, `connection_log`, `consents`, `exams`) |
| `backend/tests/test_session_summary_engine.py` | **Baru**, 22 tes dengan hasil yang dihitung tangan |

Tidak ada file lama yang diubah di Phase 3, sehingga tidak diperlukan cadangan kode.

## 2. Fungsi utama

| Fungsi | Isi |
|---|---|
| `intervals(start, end)` | Interval `[a, b)` 300 dtk; tanpa celah, tumpang tindih, atau panjang 0; `w = d/300` |
| `session_window(db, exam, tz, now)` | **A1**: S = yang lebih awal antara jadwal dan observasi pertama ujian. E = yang lebih akhir antara `report.session_end` dan observasi terakhir; sesi berjalan berakhir "sekarang" (`sementara`). Menyimpan durasi terjadwal dan rentang observasi aktual terpisah. |
| `compute_student(db, exam, student, window)` | Per interval: `observed_s`, `analysable_s` (teramati dikurangi `CANNOT_ANALYZE`), `coverage`, `no_data_reason`; per indikasi: `active_s`, `duration_score`, confidence per sumber. Per sesi: P(i), C(i), Σw, interval valid/tanpa data, cakupan berbobot. |
| `compute_exam(db, exam, tz, now)` | Semua peserta terdaftar. Ujian tanpa data cakupan → `tidak_tersedia` (**A7**, tanpa hitung ulang) |

## 3. Aturan yang diterapkan

| Aturan | Implementasi |
|---|---|
| Timestamp aktual, resolusi 1 dtk | Detik teramati dari mask Phase 2; episode dari `start_ts`/`end_ts` kejadian |
| Episode bertumpuk (worker + browser) | `cases.episodes_of` menggabungkan dulu, lalu ditandai per detik, sehingga satu detik dihitung sekali |
| Episode melewati batas interval | Dipotong per detik ke interval masing-masing |
| Kejadian "open" sisa crash | Waktu aktif = episode ∩ detik **dapat dianalisis**, sehingga tidak menambah waktu yang tidak teramati |
| Duration score | `p = active / analysable` bila analysable > 0; selain itu `p = 0` + alasan |
| Interval tanpa data | Tetap di penyebut P(i). Alasan, dari yang paling spesifik: `tidak_hadir`, `belum_bergabung`, `sudah_keluar`, `tidak_dapat_dianalisis` (teramati tetapi semuanya `CANNOT_ANALYZE`), `terputus` (≥ separuh interval terputus menurut `connection_log`), `tidak_ada_frame` |
| P(i) | `Σ w_k p_k / Σ w_k` |
| Average confidence (**A2**) | Ponsel: deteksi positif. Buku: COCO dan CLIP **terpisah**. Suara: speech/whisper/paper per sampel. Tanpa sampel → `None` (N/A, bukan 0). FACE_ABSENT, MULTIPLE_PERSONS, HEAD_TURN: tidak ada confidence (hanya duration score). C(i) sesi = Σ sampel / banyak sampel. |
| Sampel per menit yang melewati batas interval | Dibagi menurut **detik teramati** baris itu di dalam irisan. Bila menit itu tanpa detik teramati (sampel audio saja), dibagi menurut waktu. Rata-rata menit tetap. |
| Indikasi yang dihitung | Video: FACE_ABSENT, MULTIPLE_PERSONS, HEAD_TURN, PHONE_VISIBLE, BOOK_VISIBLE. Suara: OTHER_VOICE, WHISPER, BOOK_SOUND **hanya dengan persetujuan audio**; tanpa itu dikecualikan dengan alasan, bukan 0 |
| Dikecualikan dengan alasan | HEAD_TURN_REPEATED (turunan episode HEAD_TURN), CAMERA_OFF/MIC_OFF/LOCKDOWN_LOST (indikasi sistem, **A3**) |

## 4. Temuan saat pengujian

Tes "menit melewati batas interval" mula-mula **gagal**. Rancangan awal membagi sampel confidence menurut lamanya irisan waktu. Pada data uji, menit terakhir hanya punya sampel di detik ke-540–569, tetapi 15 sampel "dipindahkan" ke interval [570, 600) yang sama sekali tidak teramati.

Perbaikannya membagi menurut detik teramati baris itu (data mask sudah tersedia), dan kini tepat: 300 / 300 / 0 sampel. Perubahan ini menyimpang dari usulan K7 ("pemotongan proporsional waktu") ke versi yang lebih teliti; aturan untuk sampel audio-saja tetap menurut waktu.

## 5. Hasil pengujian (22 tes baru, semua lulus)

| Kasus spesifikasi | Tes | Hasil yang diharapkan dan teramati |
|---|---|---|
| 1. Sesi 3 menit | `test_session_lengths…[3]`, `test_three_minute…` | 1 interval, w = 0,6; ponsel 45 dari 180 dtk → P = 0,25 (bobot ternormalisasi) |
| 2. Sesi 50 menit | `test_session_lengths…[50]` | 10 interval, Σw = 10,0; tanpa interval 0 dtk |
| 3. Sesi 52 menit | `test_session_lengths…[52]`, `test_intervals_are_half_open…` | 10 × 300 dtk + 1 × 120 dtk; w terakhir 0,4; Σw = 10,4; batas bersambung, berakhir tepat di 3.120 |
| Agregasi temporal | `test_partial_interval_weight…` | p = 0,2 × 10 dan 0,5 di interval parsial → P = 2,2 / 10,4 = **0,2115** |
| 4. Interval tanpa data | `test_interval_without_data…` | p = 0,1 / 0,1 / 0 (alasan `tidak_ada_frame`) → P = 0,0667; interval valid 2, tanpa data 1, cakupan 0,667 |
| Alasan tanpa data | `test_no_data_reasons…` | `belum_bergabung`, `belum_bergabung`, valid, `tidak_dapat_dianalisis`; peserta tidak bergabung → `tidak_hadir` |
| 5. Episode melewati batas | `test_episode_crossing…` | 290–310 dtk → 10 dtk di k0 dan 10 dtk di k1 |
| 6. Worker + browser bertumpuk | `test_overlapping_worker_and_browser…` | 100–130 + 110–140 → 40 dtk (bukan 60) |
| 8. Pengamatan parsial | `test_partial_observation…` | teramati 150, tak dapat dianalisis 30 → dapat dianalisis 120; ponsel 30 → p = 0,25; cakupan 0,4 |
| Kejadian open setelah crash | `test_event_left_open_by_a_crash…` | Hanya 100 dtk (100–200) yang teramati, tidak sampai akhir |
| Timestamp, bukan jumlah frame | `test_frame_rate_does_not_change_the_score` | 2 fps dan 5 fps → sama-sama 0,2 |
| 9. Audio tanpa persetujuan | `test_audio_indicators_need_consent…` | Dikecualikan dengan alasan; dengan persetujuan 30/300 → 0,1 |
| 10. HEAD_TURN_REPEATED | `test_head_turn_repeated…` | Dikecualikan ("turunan"); HEAD_TURN tetap 0,1; indikasi sistem dikecualikan |
| 11. Dua metrik terpisah | `test_average_confidence_and_duration_score…` | C ponsel = 0,7 (n 200); duration score 0,1; buku tanpa sampel → N/A (`None`); wajah/menoleh tanpa confidence |
| Pembagian menit | `test_confidence_of_a_minute…`, `test_minute_share…` | 300 / 300 / 0 sampel; menit audio-saja dibagi menurut waktu |
| A1 jendela | `test_window_starts…` | Mulai 2 menit sebelum jadwal → S = jadwal − 120; terjadwal 600 dtk; jendela 720 dtk; 3 interval |
| Sesi berjalan | `test_running_session…` | Status `sementara`, E = sekarang |
| A7 sesi lama | `test_session_without_observation_data…` | `tidak_tersedia`, tanpa peserta |
| Hanya-baca | `test_engine_is_read_only` | Jumlah baris tabel tidak berubah; tabel hasil tetap 0 baris |

Kasus 7 (restart) diuji di Phase 2. Kasus 12–13 (P_total berbobot, finalisasi) adalah Phase 4.

**Regresi:**

| Paket | Hasil |
|---|---|
| Backend | **308 lulus**, 0 gagal, 2 dilewati (286 + 22) |
| Modul AI, frontend | Tidak diubah |
| Data produksi | Hash `backend/data` tidak berubah sejak akhir Phase 2 |

## 6. Batasan dan risiko

| ID | Hal | Catatan |
|---|---|---|
| L1 | Alasan tanpa data bersumber dari `presence` (waktu bergabung pertama, waktu keluar terakhir) dan `connection_log` (hanya sambung/putus Jitsi) | Keluar-masuk berulang di jalur browser tidak punya riwayat. Alasannya bisa jatuh ke `tidak_ada_frame`, padahal penyebabnya mahasiswa sempat keluar. |
| L2 | Confidence jalur worker = N/A (Phase 2, R2) | Butuh perubahan worker (persetujuan terpisah) |
| L3 | Jendela memakai observasi seluruh ujian (A1), sama untuk semua peserta | Peserta yang tidak teramati di awal mendapat interval `belum_bergabung` atau `tidak_ada_frame` (bernilai 0, sesuai keputusan) |
| L4 | Kinerja | Array per detik per peserta. Ujian 120 menit ≈ 7.200 elemen × indikasi; belum diukur pada ujian dengan banyak peserta. Ditambahkan ke regresi Phase 7. |
| L5 | Database produksi belum dimigrasi (Phase 2, R1) | Tetap berlaku |

## 7. Langkah berikutnya (menunggu persetujuan)

Phase 4, agregasi sesi:

- `P_total = Σ v_i P(i) / Σ v_i` dengan bobot dari `config.yaml` (bawaan 1, dicatat bersama hasil);
- snapshot ke `session_interval_summary` dan `session_participant_summary` di dalam transaksi `finalize_report`, idempoten;
- versi config dan algoritma tersimpan;
- endpoint baca `GET /api/sessions/{id}/session-summary`.
