# Session Report Phase 5: Laporan Hasil dan Evaluasi Penutupan

Tanggal: 21 November 2026 · Status: **Diserahkan untuk keputusan penutupan Phase 5 oleh pemilik proyek. Belum ditutup.** Tidak ada commit.

**Batas pekerjaan penutupan:**
- Tidak ada perubahan kode, konfigurasi runtime, `.env`, database, skema, data, atau dataset.
- Tidak ada migrasi, aktivasi kalibrator, nilai T_k, instans pilot, perekaman, pembacaan data produksi, DC-4, `target_population`, perubahan Live Rule Alert, atau Phase 6.

---

## 1. Ruang lingkup Phase 5 dan hasilnya

| Tahap | Isi | Status | Dokumen |
|---|---|---|---|
| Rencana | Rencana revisi 1; K1–K6 disetujui, K7 terbuka | Disetujui | `EDUAI_SESSION_REPORT_PHASE5_PLAN.md` |
| Tahap 1 | Audit D4 (ketersediaan model) | Diterima; S1 dipilih | `EDUAI_SESSION_REPORT_PHASE5_D4_AUDIT.md` |
| Tahap 2 | Pencatatan D4 per peserta: tabel aditif `model_availability`, pesan worker per peserta, penanda `model_unavailable` tanpa mengubah rumus | Diterima | `EDUAI_SESSION_REPORT_PHASE5_TAHAP2_RESULTS.md` |
| Tahap 3 | Mekanisme kalibrasi: modul bersama, `calibration.py`, skrip luring, C1–C7, 10 kode alasan | Diterima | `…_TAHAP3_SCOPE.md`, `…_DESIGN.md` (revisi 4), `…_RESULTS.md` |
| Evaluasi lanjutan | P1 (B2 arah desain), Architecture Alignment, readiness check, P1-5 = S1, AL-3 = C, AL-3c = G-c bertahap, OS-1 = O1, K-b = KB-1 | Diputuskan atau diterima sebagai acuan | `…_P1_EVALUATION.md`, `…_ARCHITECTURE_ALIGNMENT.md`, `…_READINESS_CHECK.md`, `…_P1_5_AL3_DECISION_ANALYSIS.md`, `…_AL3C_OS1_KB_ANALYSIS.md` |
| Tahap 4 | Kebutuhan dataset dan protokol pelabelan (L5) | **Ditutup sebagai perancangan** (opsi a) | `…_TAHAP4_RESULTS.md`, `SESSION_CALIBRATION_DATASET.md` |

## 2. Audit kesiapan regresi

| Pemeriksaan | Hasil |
|---|---|
| Isolasi database tes | Setiap tes membuat database, folder bukti, dan folder laporan **sementara** sendiri (`make_settings`); tidak ada tes yang membuka `backend/data` |
| Isolasi `.env` | `backend/tests/conftest.py` menghapus semua variabel yang masuk dari `.env`; tiga tes `test_env_isolation.py` memeriksanya |
| Migrasi | Hanya terjadi pada database sementara tes; database produksi tidak dibuka |
| Model | Tes AI membaca berkas model (hanya baca); tidak ada perubahan model |
| Kalibrator | `.env` tidak memuat setting `EDUAI_SESSION_CALIBRATOR*` (hanya nama kunci yang diperiksa, tanpa nilai) |
| Frontend | `node_modules` tersedia; `npm test` menjalankan tes Node lokal tanpa server |
| Data produksi | Larangan membaca data produksi dipatuhi. Perbandingan **hash isi** `backend/data` yang biasa dilakukan **tidak** dijalankan. Sebagai gantinya dibandingkan **metadata** (jalur, ukuran, waktu ubah) sebelum dan sesudah regresi, tanpa membuka isi berkas. |
| Kesimpulan | Aman dan terisolasi; tidak memerlukan perubahan atau dependensi yang belum disetujui. Regresi dijalankan. |

## 3. Hasil regresi penuh (aktual, 21 November 2026)

| Paket | Perintah | Hasil |
|---|---|---|
| Backend | `pytest tests` | **350 lulus**, 0 gagal, 2 dilewati |
| Modul AI | `pytest tests` | **139 lulus**, 0 gagal, 2 dilewati |
| Frontend | `npm test` | **133 lulus**, 0 gagal |
| Data produksi | Metadata `backend/data`, sebelum vs sesudah | **Identik**: 1.837 berkas; jalur, ukuran, dan waktu ubah sama |

**Tes yang dilewati (sama dengan sebelumnya, tidak terkait Phase 5):**

| Tes | Alasan |
|---|---|
| `backend/tests/test_api.py:375` | Paket `skimage` tidak terpasang |
| `backend/tests/test_worker_mgmt.py:184` | Khusus POSIX |
| `ai/eduai-ai/tests/test_models_smoke.py:11` | Paket `skimage` tidak terpasang |
| `ai/eduai-ai/tests/test_worker.py:143` | Cabang POSIX |

**Perkembangan jumlah tes selama Phase 5:**
- backend: 328 → 338 (Tahap 2, +10) → 350 (Tahap 3, +12);
- AI: 122 → 127 (Tahap 2, +5) → 139 (Tahap 3, +12).

Satu peringatan pustaka (`httpx`/`starlette`, deprecation) muncul sejak sebelum Phase 5.

## 4. Evaluasi kriteria penerimaan Phase 5 (rencana Phase 5 §6.2)

| # | Kriteria | Bukti | Status |
|---|---|---|---|
| 1 | Semua tes 1–14 rencana lulus dan tidak ada tes lama yang gagal | §4.1; regresi §3: 0 gagal di tiga paket | **Terpenuhi** |
| 2 | Di produksi tidak ada satu pun probabilitas: tidak ada berkas kalibrator, semua `not_calibrated` | Setting kalibrator tidak ada di `.env`, sehingga bawaan kosong = `no_calibrator`. Database produksi belum dimigrasi, jadi belum ada snapshot Session Summary sama sekali. Tes "tanpa kalibrator" lulus. | **Terpenuhi** |
| 3 | Mekanisme kalibrasi benar pada data buatan dan menolak masukan atau kondisi tidak sah | Pemulihan a = 4, b = −3 dalam ±10 %; metrik sesuai hitungan tangan; E1–E6 di batas; 10 varian berkas tidak sah ditolak; C6, C7, kebocoran, K5, dan registri diuji (Tahap 3) | **Terpenuhi** |
| 4 | D4 terdeteksi dan tercatat per peserta tanpa mengubah rumus Phase 4 | Tahap 2: angka identik dengan dan tanpa catatan D4; bertahan hingga snapshot dan setelah restart | **Terpenuhi** |
| 5 | Dokumen kebutuhan dataset lengkap: definisi target dan maknanya, protokol pelabelan, ambang κ, jumlah minimum per set, aturan pemisahan dan kebocoran, pelaporan ketidakpastian | `SESSION_CALIBRATION_DATASET.md`: definisi target dan populasi (§1–§2), pelabelan (§3), κ (§3.3), K5 per set dan rumus ukuran (§7.1), pemisahan kohort, registri, dan test split sekali (§5), bootstrap peserta dan selang 95 % (§7.2). **Ukuran dataset final dan nilai numerik kriteria T_k ditunda** ke "setelah uji coba" atau PS-9, sesuai keputusan opsi (a). | **Terpenuhi sebagai perancangan**, dengan parameter tertunda yang dinyatakan |
| 6 | Tidak ada perubahan pada rumus P_total, snapshot Phase 4, data historis, model, inference, alert, PDF, atau frontend di luar yang tertulis | Waktu ubah berkas: frontend, `report.py`/`report_export.py` (PDF), `cases.py` (Live Rule Alert), `temporal.py`/`events.py` terakhir diubah 20 November 2026, **sebelum** Phase 5. `config.yaml` terakhir pada revisi Phase 4 (komentar). Perubahan Phase 5 hanya yang disetujui: `perception.py` (penghitung galat Tahap 2), `ai_service.py`, `api.py`, `schemas.py`, `db.py` (tabel aditif), `session_summary.py`, `calibration.py`, `settings.py`, dan berkas worker. Tes kunci membuktikan angka Phase 4 identik. | **Terpenuhi** |

### 4.1 Pemetaan tes 1–14 rencana Phase 5 §6.1

| # | Tes rencana | Tes aktual | Hasil |
|---|---|---|---|
| 1 | Tanpa berkas kalibrator | `test_calibration.py::test_without_a_calibrator_nothing_changes` | Lulus |
| 2 | Berkas rusak | `test_invalid_content_is_refused_and_finalisation_still_runs`, `test_c6_…` | Lulus |
| 3 | Ketidakcocokan versi, bobot, himpunan | `test_compatibility_reasons_are_all_collected` | Lulus |
| 4 | Cakupan di bawah ambang | `test_coverage_and_d4_reasons` | Lulus |
| 5 | Kalibrator sah | `test_valid_calibrator_gives_a_probability_only_in_the_final_snapshot` | Lulus |
| 6 | Snapshot beku | `test_final_snapshot_stays_frozen_when_the_calibrator_changes` | Lulus |
| 7 | CHECK database | `test_session_summary_aggregation.py::test_a_failed_transaction_leaves_nothing_behind` | Lulus |
| 8 | Pemulihan parameter | `test_calibrate_session.py::test_platt_recovers_known_parameters` | Lulus |
| 9 | Kebocoran | `test_leakage_of_participants_or_exam_sessions_stops` | Lulus |
| 10 | Kasus degeneratif, jumlah kurang | `test_fit_failures_are_technical_errors`, `test_filtering_and_minimum_counts`, `test_an_unrelated_score_is_a_technical_failure` | Lulus |
| 11 | Metrik dan ketidakpastian | `test_metrics_against_hand_values`, `test_adequate_calibrator_end_to_end_with_lineage_and_registry` | Lulus |
| 12 | D4: deteksi dan pencatatan | `test_model_availability.py` (10 tes), `test_d4_model_availability.py` (5 tes) | Lulus |
| 13 | D4 di dataset | `test_filtering_and_minimum_counts` (`d4_bukan_lengkap`) | Lulus |
| 14 | Regresi | §3 | Lulus |

## 5. Yang tidak dicakup penutupan Phase 5

| Hal | Status |
|---|---|
| Kalibrator nyata | Tidak ada. Belum ada data berlabel; semua hasil `not_calibrated`. |
| Uji coba kecil, pengumpulan data, pelabelan | Belum. Memerlukan PS-5 (etik) dan PS-4 (instans pilot), serta pembekuan deteksi, konfigurasi, dan model. |
| Validasi empiris rancangan Tahap 4 | Belum |
| Nilai T_k, s_min, p_min, minimum per indikasi | Belum (PS-8, PS-9) |
| Skrip evaluasi T_k | Belum (PS-1) |
| DC-4, `target_population` | Hanya analisis (PS-2, PS-3) |
| B2 (beberapa kalibrator) | Arah desain; implementasi ditunda sampai ada kalibrator kedua |
| Revisi protokol 0.2 | Rancangan berversi, belum berlaku (PS-7) |

## 6. Risiko yang masih terbuka

| ID | Risiko | Status |
|---|---|---|
| R-M | **Migrasi database produksi belum disetujui.** Backend kode baru akan menambah tabel Phase 2 dan Tahap 2 secara otomatis saat start (teruji di salinan, dengan cadangan otomatis). | Kode baru belum boleh dijalankan terhadap database produksi |
| R-C | **Pekerjaan belum di-commit.** Seluruh Phase 4–5 dan pekerjaan sebelumnya sejak `af628da` (lebih dari 100 berkas) belum di-commit. Cadangan per tahap ada di `EduAI_cadangan_20261120/` dan `EduAI_cadangan_20261121/`. | Risiko kehilangan dan kesulitan peninjauan; keputusan commit milik pemilik proyek |
| K7 | Perlakuan nilai indikasi terdampak D4 | Terbuka |
| D-R10 | Registri test split dapat diganti utuh oleh pemegang akses tulis | Terbuka (mitigasi sebagian) |
| D-R11 | Administrator yang dapat mengubah setting dan berkas dapat melewati C6 | Terbuka |
| D-R12 | Model worker OpenVidu tidak tercakup pemeriksaan C7 | Terbuka; diterima sebagai keterbatasan |
| R2–R9 (Tahap 2) | Set model per peserta tidak dipanaskan; set cadangan yang gagal pemanasan tetap dipakai; penandaan konservatif; celah waktu laporan worker; sesi lama `tidak_tercatat` | Terbuka, tercatat |
| TK-2 | Kelayakan ukuran dataset (K5) | Terbuka sampai uji coba |
| TK-10 | Prevalensi Y bergantung pada definisi operasional | Mitigasi disetujui; sisa terbuka |
| TK-1 / D-R2 | Populasi pilot ≠ ujian nyata | Batas interpretasi disetujui; sisa terbuka |
| AL-1, AL-2, AL-3a, AL-3b, AL-4, AL-5, AL-6 | Keputusan menuju Phase 6 | Terbuka |
| Verifikasi isi data produksi | Hash isi tidak dibandingkan pada penutupan ini (larangan membaca data produksi); hanya metadata | Catatan metode |

## 7. Rekomendasi

**Phase 5 layak ditutup secara keseluruhan sebagai "mekanisme dan perancangan"**, dengan pernyataan eksplisit:
1. **Keenam kriteria penerimaan terpenuhi.** Kriteria 5 terpenuhi sebagai perancangan, dengan parameter tertunda yang dinyatakan.
2. **Regresi penuh lulus:** backend 350, AI 139, frontend 133; 0 gagal. Metadata data produksi identik.
3. **Penutupan tidak berarti** ada kalibrator, probabilitas tervalidasi, T_k ditetapkan, data dikumpulkan, atau sistem siap untuk ujian nyata. Produksi tetap `not_calibrated`, dan istilah laporan tetap Indication Score (%).

**Sebelum atau bersamaan dengan keputusan penutupan, disarankan agar pemilik proyek memutuskan:**
- **R-C (commit):** pekerjaan yang sudah diterima di banyak tahap belum tersimpan di riwayat git. Ini risiko operasional terbesar saat ini.
- **R-M (migrasi produksi):** menentukan kapan kode baru boleh dijalankan terhadap database produksi.

**Setelah penutupan, jalur yang tersedia** (semuanya perlu persetujuan terpisah):
- (a) uji coba kecil: PS-5 → PS-4 → pembekuan → rencana uji coba;
- (b) perancangan Phase 6: paket keputusan AL-1 sampai AL-6, K7, dan nilai T_k;
- (c) migrasi produksi dan commit.

Keputusan penutupan Phase 5 berada pada pemilik proyek.

## 8. Konfirmasi

- Hanya dokumen ini yang dibuat. Tidak ada perubahan kode, konfigurasi runtime, `.env`, database, skema, data, atau dataset, dan tidak ada commit (commit terakhir `af628da`).
- Data produksi tidak dibuka; yang dibaca hanya metadata berkas.
- Tidak ada migrasi produksi, aktivasi kalibrator, nilai T_k, instans pilot, perekaman, DC-4, `target_population`, perubahan Live Rule Alert, atau Phase 6.
- Tes membuat folder `__pycache__` di dalam repositori. Itu artefak run Python, bukan perubahan kode.
