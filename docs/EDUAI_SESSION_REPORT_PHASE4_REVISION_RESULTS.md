# Session Report: Hasil Revisi Phase 4 (Temuan T1–T6)

Tanggal: 21 November 2026 · Status: **Phase 4 diterima pemilik proyek (21 November 2026). Phase 5 belum dimulai dan menunggu persetujuan terpisah.** Risiko D4 (model gagal dimuat saat runtime padahal `enabled: true`) dicatat untuk evaluasi tahap berikutnya.

Lingkup: temporal aggregation, event/alert aggregation, dan session summary report. Revisi ini **tidak** mengimplementasikan session-level prediction, temporal probability aggregation, atau video-level classification.

Tidak diubah: rumus P_total, pemisahan bobot interval dan bobot indikasi, snapshot idempoten dan beku, `probability = null`, skema database, data historis, PDF, alert, model, inference, dan frontend. Tidak ada commit. Cadangan file sebelum revisi ada di `..\EduAI_cadangan_20261121\sesi_phase4_revisi\`.

---

## 1. Perubahan file

| File | Perubahan |
|---|---|
| `backend/app/session_summary.py` | `config_exclusions` (T4), `config_version` (T3), `COVERAGE_ZERO_NOTE` (T2), cakupan audio dan `no_audio_data` (T1), pembulatan antara dihapus (T5). `compute_exam(..., cfg=)`. Snapshot menyimpan field baru di JSON baris `*`, tanpa kolom baru. |
| `backend/app/api.py` | `_session_summary_live`: meneruskan config aktif ke perhitungan dan memakai `config_version` bersidik bobot |
| `ai/eduai-ai/config.yaml` | Komentar saja (T6 dan T4). Nilai tidak berubah. |
| `docs/API.md` | Keterangan field baru pada endpoint Session Summary |
| `backend/tests/test_session_summary_revision.py` | **Baru**, 8 tes |
| `backend/tests/test_session_summary_engine.py` | Helper `hear()` (sampel audio). Tes persetujuan audio kini memberi sampel audio, karena tanpa sampel indikasi suara sengaja dikecualikan (T1). |
| `backend/tests/test_session_summary_aggregation.py` | Harapan `config_version` disesuaikan ke format bersidik |

## 2. Penyelesaian per temuan

| ID | Keputusan | Implementasi |
|---|---|---|
| T1 | Audio tanpa sampel dikecualikan; cakupan audio terpisah | Persetujuan audio ada, tetapi tidak satu pun sampel audio selama sesi → OTHER_VOICE, WHISPER, BOOK_SOUND masuk `excluded` dengan alasan `no_audio_data` dan tidak masuk penyebut P_total. Bila ada sebagian data audio, interval tanpa sampel audio bernilai 0 dengan `no_data_reason = "no_audio_data"` per indikasi (ikut tersimpan di baris interval snapshot). Cakupan audio per interval (`audio_s`, `audio_coverage`) dan per sesi (`audio_coverage`, `audio_samples`) dilaporkan terpisah dari `coverage` video; `null` tanpa persetujuan audio. Resolusi cakupan audio: satu menit, karena sampel audio disimpan per menit. |
| T2 | Opsi (a): skor tetap 0 | Cakupan sesi 0 → `coverage_note`: "Cakupan pengamatan 0%: skor tidak didukung observasi yang memadai. Skor 0 bukan bukti bahwa tidak ada indikasi." Tersedia di hasil live dan snapshot final, siap dipakai PDF (Phase 6). |
| T3 | Sidik bobot | `config_version = "<version>;w=<8 hex SHA-256 bobot>"`, contoh `0.2-provisional;w=…`. Bobot berbeda → sidik berbeda walau `version` tidak dinaikkan. Bobot lengkap dan bobot yang dipakai tetap tersimpan di baris `*`. |
| T4 | Ikut status dan kategori config aktif | Dikecualikan dengan alasan: `enabled: false`; WHISPER/BOOK_SOUND berkategori `info`; model yang dibutuhkan nonaktif (object detector → PHONE_VISIBLE, dan BOOK_VISIBLE bila CLIP juga nonaktif; face landmarker → HEAD_TURN; model audio → indikasi suara). Bawaan sama dengan `eduai_ai.temporal` (BOOK_VISIBLE nonaktif bila tidak disebut). Daftar ini juga tersimpan sebagai `config_excluded`. Config proyek saat ini: **tidak ada** yang dikecualikan. |
| T5 | Presisi penuh | Pembulatan dihapus dari duration score interval, cakupan, P_i, Σw, rata-rata confidence, dan P_total. Disimpan sebagai REAL presisi penuh; pembulatan hanya saat penyajian. Satu-satunya pembulatan yang tersisa adalah `conf_n` (kolom INTEGER) di baris confidence snapshot. |
| T6 | Dokumentasi | Komentar `config.yaml`, docstring `_session_summary_live`, dan `docs/API.md`: perubahan config berlaku setelah backend dimuat ulang. Snapshot mencatat versi dan bobot yang benar-benar dipakai saat finalisasi. |

## 3. Tes baru (8, semua lulus)

| Tes | Perhitungan dan hasil |
|---|---|
| Audio disetujui tanpa sampel | FACE_ABSENT 30/300 = 0,1. P_total = 0,1/5 = **0,02** (bukan 0,1/8 = 0,0125). Tiga indikasi suara `no_audio_data`, `audio_coverage` 0, `coverage` video 1,0. |
| Audio sebagian | 10 menit, audio hanya di interval 0. OTHER_VOICE: interval 0 = 30/300 = 0,1; interval 1 = 0 dengan alasan `no_audio_data`; P = **0,05**. `audio_coverage` 0,5, `coverage` video 1,0. Alasan tersimpan di baris snapshot. |
| Tanpa persetujuan audio | `audio_coverage`, `audio_samples`, `audio_s` = `null` |
| Cakupan 0% | Episode tidak-dapat-dianalisis sepanjang sesi: cakupan 0, P_total 0 dengan `coverage_note`; catatan ikut di snapshot; sesi normal tanpa catatan |
| Sidik bobot | Berubah bila satu bobot berubah; tidak bergantung urutan |
| Pengecualian config | Config proyek → tidak ada. Contoh config → BOOK_VISIBLE, WHISPER (info), BOOK_SOUND, HEAD_TURN dengan alasan masing-masing; object detector nonaktif → PHONE_VISIBLE |
| Dikecualikan, bukan 0 | BOOK_VISIBLE nonaktif: FACE_ABSENT 0,1 → P_total = 0,1/4 = **0,025** |
| Agregasi berbobot ≠ perkalian cakupan | Video 0–150 dtk dari 10 menit, cakupan 0,25. FACE_ABSENT P = 0,1; PHONE_VISIBLE P = 1/30. P_total = (0,1 + 1/30)/5 = 4/150 = **0,026666…** (presisi 1e-12, tidak sama dengan nilai bulat 4 desimal). Perkalian dengan cakupan memberi 0,0333 atau 0,0067, jadi berbeda. |

Catatan untuk contoh lama (siswa1: 0,125 / 0,2 / 0,025): 0,125 × 0,2 = 0,025 kebetulan sama dengan 0,125/5 karena cakupan 0,2 = 1/5 indikasi. Tes T5 di atas memakai cakupan 0,25 sehingga kedua tafsiran terpisah.

## 4. Regresi

| Paket | Hasil |
|---|---|
| Backend | **328 lulus**, 0 gagal, 2 dilewati (320 + 8 baru) |
| Modul AI | **122 lulus**, 2 dilewati (diperiksa karena komentar `config.yaml` berubah) |
| Frontend | Tidak diubah |
| Data produksi | Hash 1.837 file `backend/data` (1.829 di `evidence/`) sama dengan manifest akhir Phase 2: 0 hilang, 0 baru, 0 berubah |

## 5. Dampak dan batasan

| ID | Hal | Catatan |
|---|---|---|
| D1 | Nilai di respons tidak lagi dibulatkan 4 desimal | Tampilan (Phase 6, PDF) wajib membulatkan sendiri |
| D2 | Format `config_version` berubah | Snapshot sebelum revisi tidak ada di produksi (finalisasi dengan snapshot belum pernah dijalankan pada data produksi), jadi tidak ada data lama yang perlu disesuaikan |
| D3 | Resolusi cakupan audio satu menit | Sampel audio disimpan per menit; menit dengan minimal satu sampel dihitung tercakup penuh |
| D4 | Model gagal dimuat padahal `enabled: true` | Tidak dideteksi dari config; indikasi tetap dihitung. Di luar lingkup T4. |
| D5 | Config dibaca saat start | Perubahan bobot/status berlaku setelah backend dimuat ulang (T6) |

## 6. Langkah berikutnya

Phase 4 diterima (21 November 2026). Phase 5 (kalibrasi) belum dimulai dan memerlukan persetujuan terpisah; rencananya ada di `docs/EDUAI_SESSION_REPORT_PHASE5_PLAN.md`.
