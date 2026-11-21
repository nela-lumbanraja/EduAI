# Session Report Phase 5, Tahap 3: Hasil Implementasi Mekanisme Kalibrasi

Tanggal: 21 November 2026 · Status: **Diterima pemilik proyek (21 November 2026).** Penyesuaian P1 dievaluasi terpisah (`EDUAI_SESSION_REPORT_PHASE5_P1_EVALUATION.md`); P1-4 dan P1-5 masih terbuka. Tidak ada commit. *Status awal: "selesai, menunggu evaluasi pemilik proyek."*

**Dasar:**
- `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md` (revisi 4);
- `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_SCOPE.md`;
- persetujuan implementasi T3-1 sampai T3-6 dan C1–C7.

**Tidak dikerjakan:** G1–G4, Phase 6, dan K7 (tetap terbuka). Cadangan file sebelum perubahan ada di `..\EduAI_cadangan_20261121\phase5_tahap3\`.

**Tidak berubah:**
- skema database (tidak ada migrasi);
- `.env` dan `config.yaml`;
- model, inference, dan alert;
- PDF dan frontend;
- data historis dan database produksi.

Backend tidak dijalankan terhadap database produksi; semua pengujian memakai basis data sementara dan data buatan.

---

## 1. Perubahan file

| File | Perubahan |
|---|---|
| `ai/eduai-ai/src/eduai_ai/session_calibration.py` | **Baru.** Modul bersama untuk skrip dan backend (C4, C5). Isinya: kriteria K2/K5/E1–E6 dan bootstrap sebagai konstanta kode dengan `CRITERIA_VERSION` dan `criteria_sha256()` (C2); fit Platt (Newton–Raphson, target dihaluskan dari calibration split, T3-6); metrik §2.7; `verdict()` E1–E6; `models_fingerprint()` (C7); `split_sha256()`. Hanya pustaka standar (T3-4). |
| `ai/eduai-ai/scripts/calibrate_session.py` | **Baru.** Skrip luring §2.6: validasi, penyaringan, pemisahan per peserta dan per sesi ujian (C1), K5, registri test split berantai (§2.10.1), fit, evaluasi sekali dengan bootstrap peserta, laporan, dan berkas kalibrator hanya bila `memadai` (dengan `lineage`, `approved_by: null`). Tidak ada opsi untuk mengubah kriteria. |
| `backend/app/calibration.py` | **Baru.** `load()` menjalankan C6 terlebih dahulu (setting sidik kosong = tidak disetujui; sidik tidak cocok = ditolak sebelum isi dibaca), lalu memvalidasi isi berkas, menghitung ulang putusan, dan memeriksa versi kriteria. `evaluate()` mengumpulkan semua alasan dari 10 kode yang disetujui. `probability()` adalah satu-satunya tempat probabilitas dihitung. |
| `backend/app/settings.py` | Dua setting baru: `EDUAI_SESSION_CALIBRATOR` (T3-1) dan `EDUAI_SESSION_CALIBRATOR_SHA256` (C6), keduanya kosong secara bawaan. `.env` tidak diubah. |
| `backend/app/ai_service.py` | `models_fingerprint()` (C7): sidik model yang aktif, termasuk berkas prompt CLIP. Nilainya kosong bila AI bukan `READY` atau ada berkas yang tidak terbaca. Kegagalan tidak di-cache. |
| `backend/app/session_summary.py` | `compute_exam(..., calibrator, config_version, models_fp, final)`: blok kalibrasi berasal dari `calibration.evaluate`, yang hanya membaca nilai. Metadata JSON baris `*` ditambah `calibration_reasons`, `calibration_details`, `calibration_approved_sha256`, dan `models_fingerprint`. `read_snapshot` mengembalikannya. Tanpa argumen `calibrator`, blok Phase 4 tetap seperti semula. |
| `backend/app/api.py` | `_session_summary_live(..., final)` memuat kalibrator dan sidik model. Finalisasi memakai `final=True`; hasil live tidak pernah memuat angka probabilitas (T3-2). |
| `docs/API.md` | Field kalibrasi pada endpoint Session Summary |
| Tes baru | `backend/tests/test_calibration.py` (12 tes), `ai/eduai-ai/tests/test_calibrate_session.py` (12 tes) |

## 2. Perilaku yang diterapkan

| Hal | Perilaku |
|---|---|
| Tanpa kalibrator (keadaan produksi) | `not_calibrated`, probabilitas `null`, alasan `no_calibrator`, catatan "Belum tersedia". Semua angka Phase 4 identik (diuji). |
| C6 | Setting sidik kosong → `invalid_calibrator` ("belum ada sidik persetujuan"). Sidik berbeda, termasuk berkas yang disunting satu nilai → `invalid_calibrator` ("tidak cocok"), dan isi berkas tidak dibaca. Sidik yang disetujui dicatat di snapshot, juga bila hasilnya `not_calibrated`. |
| C7 | Sidik model backend kosong → `models_mismatch` dengan rincian `tidak_tersedia: ...`. Sidik berbeda → `models_mismatch` dengan rincian `berbeda: ...`. Kedua penyebab dapat dibedakan di `details`, tanpa kode baru. Sidik kosong tidak pernah cocok. `lineage.models_fingerprint` kosong → `invalid_calibrator`. |
| Tanpa fallback | Tidak ada kalibrator lain dan tidak ada a/b bawaan. Bila ada alasan apa pun, `probability()` tidak dipanggil (diuji dengan penghitung panggilan). |
| Probabilitas | Hanya saat finalisasi, hanya bila daftar alasan kosong: P = 1/(1+exp(−(aR+b))), presisi penuh. Disimpan di kolom `calibrated_probability` baris `*` yang sudah ada; baris per indikasi tidak pernah memuat probabilitas. |
| Snapshot final | Dibekukan. Mengganti atau menghapus kalibrator setelah finalisasi tidak mengubah hasil, dan finalisasi ulang tetap 409. |
| K6 | Berkas rusak tidak menggagalkan finalisasi. Alasan tercatat dan ada peringatan di log. |

## 3. Penyesuaian terhadap rancangan (perlu diketahui)

| # | Hal | Keterangan |
|---|---|---|
| P1 | **Satu berkas kalibrator aktif pada satu waktu** | Rancangan §2.2 menyebut kemungkinan beberapa berkas, satu per himpunan indikasi, "misalnya satu folder". C6 menetapkan **satu** setting sidik, jadi implementasi hanya menerima **satu berkas** (satu himpunan indikasi). Peserta dengan himpunan lain, misalnya dengan indikasi suara, mendapat `indicator_set_mismatch`. Mendukung beberapa himpunan memerlukan beberapa sidik persetujuan, dan itu butuh keputusan tersendiri. Pilihan ini lebih ketat, bukan lebih longgar. |
| P2 | Bentuk hasil live | Live selalu `status: not_calibrated` dan `probability: null` (T3-2), ditambah `reasons`, `details`, dan `eligible_at_finalization` (true bila tidak ada alasan). Tidak ada nilai status baru. |
| P3 | Alasan saat tidak ada kalibrator | Alasan yang tidak membutuhkan berkas tetap dikumpulkan: `no_score`, `coverage_below_threshold` dengan ambang bawaan K2/T3-3, dan D4. Alasan kompatibilitas memerlukan berkas, jadi tidak muncul. |
| P4 | Sidik model mencakup berkas prompt CLIP | Prompt memengaruhi skor CLIP, jadi berkasnya ikut dalam `models_fingerprint` sebagai `book_classifier_prompts` |
| P5 | `lineage.report_sha256` | SHA-256 dari bagian `evaluation` laporan (JSON kanonis). Berkas laporan sendiri juga memuat `calibrator_sha256` (nilai yang disetujui pemilik proyek), sehingga hash keduanya tidak bisa saling memuat. |
| P6 | Registri | Baris registri ditulis setiap kali evaluasi test split benar-benar berjalan. Kegagalan sebelum evaluasi, seperti input tidak sah, kebocoran, K5, atau fit gagal, tidak menghabiskan test split. |
| P7 | Kode keluar skrip | 0 `memadai` (berkas ditulis), 2 input tidak sah, 3 kebocoran, 4 di bawah K5, 5 fit gagal, 6 `belum_memadai`, 7 rantai registri rusak. Tanpa `--registry` → argparse menolak (kode 2). |
| P8 | Biaya sidik model | Sekitar 97 MB berkas model di-hash sekali per proses backend (sekitar 0,2 detik), lalu disimpan sementara |

## 4. Hasil pengujian

### 4.1 Tes baru: 24, semua lulus pada akhir pekerjaan

**Modul AI** (`test_calibrate_session.py`, 12):

| Tes | Hasil |
|---|---|
| Pemulihan parameter (a = 4, b = −3, n = 5.000) | Estimasi a dan b dalam ±10 %; Brier terkalibrasi < Brier R mentah; ECE < 0,03; target dihaluskan sesuai rumus |
| Metrik terhadap hitungan tangan | Brier 0,2; Brier skill score 0,2; log loss; ECE 0; AUROC 0,75. Slope ≈ 1 dan intercept ≈ 0 pada data terkalibrasi; intercept = 1 pada prediksi yang bergeser −1 logit; slope `None` bila hanya satu kelas. |
| Kegagalan fit | `satu_kelas`, `separasi_sempurna`, `a_tidak_positif` |
| Batas E1–E6 | Slope 0,8 dan 1,2 lolos, 0,79 dan 1,21 gagal; selang yang menyentuh 1 atau 0 lolos; batas bawah BSS 0 gagal; AUROC 0,5 gagal dan 0,5001 lolos; 99 positif gagal; ulangan tanpa nilai 5 % lolos dan 5,01 % gagal; nilai kosong tidak pernah lolos |
| Sidik | Tidak bergantung urutan; berubah bila isi berubah; berkas hilang → kosong; sidik split tidak bergantung urutan baris |
| Kriteria tidak dapat diubah lewat argumen | `--min-coverage` ditolak; `--registry` wajib |
| Kebocoran | Satu peserta di kedua split → kode 3; satu sesi ujian di kedua split → kode 3; tidak ada berkas |
| Penyaringan dan K5 | Lima alasan pengecualian terhitung; data di bawah K5 → kode 4 |
| Fit hanya dari calibration split | Label test split dibalik → a, b, N₊, N₋ tetap sama; baseline BSS = prevalensi calibration split |
| Skor lemah (a = 0,6) | Fit berhasil (a > 0), tetapi putusannya `belum_memadai` (E3, E4) → kode 6, tanpa berkas; kesimpulan "belum memadai; kalibrator tidak boleh diaktifkan", tanpa kata "meningkatkan", dan disebut "DATA BUATAN" |
| Skor tanpa hubungan | a ≤ 0 → kode 5, tanpa evaluasi dan tanpa berkas |
| End-to-end, B = 2.000 | `memadai`; setiap metrik memuat nilai titik, selang 95 %, lebar selang, dan bagian ulangan tanpa nilai; jumlah peserta, sesi, dan sesi ujian efektif; berkas dan `lineage` lengkap dengan sidik yang benar; `calibrator_sha256` = sidik berkas. Test split yang sama (urutan diacak) → kode 6 `test_split_sudah_dipakai`, tanpa berkas. Baris registri yang disunting → kode 7. |

**Backend** (`test_calibration.py`, 12):

| Tes | Hasil |
|---|---|
| Tanpa kalibrator | Angka identik dengan perhitungan Phase 4; `no_calibrator`; snapshot tanpa probabilitas; sidik model tercatat |
| Kalibrator sah | Live tanpa angka, `eligible_at_finalization` true. Final `calibrated`, probabilitas = 1/(1+e^−(4R−3)) pada presisi 1e-12, versi dan sidik persetujuan tercatat, R tidak berubah, baris per indikasi tanpa probabilitas. |
| Beku | Kalibrator diganti atau dihapus → snapshot sama; finalisasi ulang 409 |
| C6 | Setting kosong, sidik salah, dan satu nilai disunting → ditolak; sidik persetujuan tercatat walaupun `not_calibrated` |
| Isi tidak sah (10 varian) | JSON rusak, a < 0, NaN, metode asing, versi kosong, putusan disunting tanpa metrik pendukung, putusan `belum_memadai`, versi kriteria lama, sidik model kosong, indikasi duplikat → semua `invalid_calibrator` dengan rincian; finalisasi tetap 200 |
| C7 | Sidik tidak tersedia (`tidak_tersedia…`) dan berbeda (`berbeda…`) dapat dibedakan; probabilitas tidak dipanggil saat finalisasi |
| Sidik model | 64 heksa, stabil; status bukan `READY` → kosong |
| Kompatibilitas | Tiga alasan tercatat sekaligus; semua kode termasuk daftar yang disetujui |
| Cakupan dan D4 | Cakupan 0,2 → `coverage_below_threshold`; model tidak termuat → `model_unavailable`; tanpa catatan D4 → `model_availability_not_recorded` |
| Tidak ada probabilitas untuk kegagalan | Penghitung panggilan = 0; tidak ada probabilitas di database |
| Skor dan ALERT tidak berubah | Angka sama antara tanpa kalibrator, kalibrator sah, dan berkas rusak. Laporan sesi (kasus, aturan ALERT, `by_indicator`, kejadian) sama, kecuali tautan bukti bertanda tangan yang bergantung waktu. |
| Artefak dari skrip | Ditolak tanpa sidik persetujuan; diterima dengan sidik yang benar; ditolak setelah kriteria kembali ke versi resmi (tes ini memakai B = 300, sehingga sidik kriterianya berbeda) |

### 4.2 Kegagalan yang terjadi selama pengerjaan (semuanya kesalahan tes, sudah diperbaiki)

| Tes | Penyebab | Perbaikan |
|---|---|---|
| Metrik hitungan tangan (AI) | Nilai log loss yang saya hitung tangan salah (ln 0,6 seharusnya ln 0,4) | Nilai harapan diperbaiki; kode tidak diubah |
| Skor tidak informatif (AI) | Pada data tanpa hubungan, fit menghasilkan a < 0, sehingga skrip benar berhenti dengan kode 5, bukan 6 | Dipisah menjadi dua tes: skor lemah (kode 6) dan skor tanpa hubungan (kode 5) |
| 6 tes backend | Helper `full_session` tidak meninjau kejadian, sehingga finalisasi ditolak (409) | Helper meninjau kejadian seperti `prepare()` milik tes Phase 4 |
| 1 tes backend (ALERT) | Laporan berbeda hanya pada tautan bukti bertanda tangan yang bergantung waktu | Perbandingan tanpa field `evidence` |

### 4.3 Regresi

| Paket | Hasil |
|---|---|
| Backend | **350 lulus**, 0 gagal, 2 dilewati (338 + 12 baru) |
| Modul AI | **139 lulus**, 0 gagal, 2 dilewati (127 + 12 baru) |
| Frontend | Tidak diubah |
| Data produksi | Hash 1.837 file `backend/data` sama dengan manifest Phase 2: 0 hilang, 0 baru, 0 berubah |
| `.env` | Tidak diubah (waktu ubah terakhir 20 November 2026, perubahan retensi yang sudah disetujui) |

### 4.4 Catatan statistik (data buatan)

Dengan data dari a = 4 dan b = −3, 1.500 baris kalibrasi, 600 baris test, dan B = 300, tiga dari lima seed berputusan `memadai`. Dua seed gagal E1 atau E2 karena variasi sampel. Ini sesuai sifat kriteria berbasis selang kepercayaan: model yang benar pun tidak selalu lolos pada sampel terbatas. Tes end-to-end memakai seed tetap dengan B = 2.000.

## 5. Perubahan database dan konfigurasi

- **Database:** tidak ada perubahan skema dan tidak ada migrasi. Yang diisi hanya kolom kalibrasi yang sudah ada sejak Phase 2 dan metadata JSON baris `*`.
- **Konfigurasi:** dua nama setting baru di kode (`EDUAI_SESSION_CALIBRATOR`, `EDUAI_SESSION_CALIBRATOR_SHA256`), keduanya kosong secara bawaan. `.env` dan `config.yaml` tidak diubah, sehingga produksi tetap tanpa kalibrator dan tanpa probabilitas.

## 6. Risiko terbuka

| ID | Risiko | Status |
|---|---|---|
| D-R9 | Pemisahan ganda per peserta dan per sesi ujian membuat data cepat habis | Disengaja (C1) |
| D-R10 | Test split dipakai berulang | Ada registri berantai. Tetap terbuka, karena registri bisa diganti utuh oleh orang yang punya akses tulis. |
| D-R11 | Isi artefak disunting | Ditangani C6. Tetap terbuka terhadap administrator yang dapat mengubah setting dan berkas sekaligus. |
| D-R12 | Model berbeda | C7 hanya membandingkan model **backend**. Sidik ini **tidak menjamin** kesesuaian model worker OpenVidu. Diterima sebagai keterbatasan Tahap 3. |
| P1 | Satu kalibrator aktif | Himpunan indikasi lain (misalnya dengan suara) tidak pernah dikalibrasi sampai ada keputusan untuk beberapa sidik |
| R-M | Migrasi produksi Phase 2 dan Tahap 2 | Belum disetujui; backend kode baru belum dijalankan terhadap database produksi |
| K7 | Perlakuan nilai indikasi terdampak D4 | Tetap terbuka |

## 7. Langkah berikutnya

Menunggu evaluasi hasil Tahap 3. Sesuai rencana, langkah berikutnya adalah Tahap 4 (dokumen kebutuhan dataset), yang memerlukan persetujuan terpisah. G1–G4 dan Phase 6 belum dimulai.
