# Session Report Phase 5, Tahap 3: Evaluasi Ruang Lingkup Mekanisme Kalibrasi

Tanggal: 21 November 2026 (diselaraskan dengan rancangan revisi 4) · Status: **Ruang lingkup dan rancangan disetujui (T3-1 sampai T3-6, C1–C7). Implementasi kemudian disetujui, selesai, dan diterima pemilik proyek** (lihat `EDUAI_SESSION_REPORT_PHASE5_TAHAP3_RESULTS.md`). Dokumen ini tetap menjadi acuan ruang lingkup. *Status awal: "implementasi menunggu persetujuan eksplisit. Belum ada implementasi."*

> **Acuan:** rincian mekanisme ada di `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md` (revisi 4). Bila ada perbedaan, dokumen rancangan revisi 4 yang berlaku. Daftar kode alasan di §3.2 sudah disamakan dengan §5.1 dokumen rancangan.

Dokumen ini hanya evaluasi ruang lingkup. Tidak ada kode, database, konfigurasi, atau data yang diubah, dan tidak ada commit.

**Dasar:**
- rencana Phase 5 `docs/EDUAI_SESSION_REPORT_PHASE5_PLAN.md`, dengan keputusan K1–K6 disetujui dan K7 terbuka;
- hasil Tahap 2 yang sudah diterima: `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP2_RESULTS.md`.

**Batas yang tetap berlaku:**
- Migrasi database produksi belum disetujui. Backend dengan kode baru **tidak** dijalankan terhadap database produksi, karena migrasi berjalan otomatis saat start. Semua pengujian Tahap 3 memakai basis data sementara.
- Phase 6 (PDF dan frontend) belum dimulai.
- Tidak ada commit.

---

## 1. Tujuan dan batas mekanisme kalibrasi

### 1.1 Tujuan

Tahap 3 membangun dan menguji **mekanisme** yang memetakan R = P_total ke probabilitas terkalibrasi dengan Platt scaling. Mekanisme ini hanya bekerja bila ada berkas kalibrator yang sah **dan** semua syarat kelayakan per peserta terpenuhi (bagian 3). Di produksi tidak ada berkas kalibrator, sehingga semua hasil tetap `not_calibrated` dan probabilitas tetap `null`.

### 1.2 Hasil yang diusulkan

| No | Hasil | Lokasi |
|---|---|---|
| H1 | Modul antarmuka kalibrator: memuat dan memvalidasi berkas, memeriksa syarat kelayakan per peserta, dan menghitung probabilitas hanya bila semuanya terpenuhi | `backend/app/calibration.py` (baru) |
| H2 | Integrasi ke perhitungan sesi: hasil kalibrasi menggantikan `NOT_CALIBRATED` yang sekarang tetap; alasan ketidaklayakan disimpan di metadata JSON baris `*` | `backend/app/session_summary.py` (`aggregate`/`compute_exam`, `snapshot_statements`, `read_snapshot`) |
| H3 | Skrip pelatihan dan evaluasi (luring, tidak dipanggil backend): fit Platt, metrik, bootstrap per peserta, pemeriksaan kebocoran, penulisan berkas kalibrator hanya bila syarat terpenuhi | `ai/eduai-ai/scripts/calibrate_session.py` (baru); memakai `scripts/eval_stats.py` |
| H4 | Tes dengan data buatan yang probabilitas sebenarnya diketahui | `backend/tests/test_calibration.py`, `ai/eduai-ai/tests/test_calibrate_session.py` |
| H5 | Laporan hasil Tahap 3 | `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_RESULTS.md` |

Dokumen kebutuhan dataset (L5 di rencana) adalah tahap berikutnya (Tahap 4), bukan bagian Tahap 3.

### 1.3 Di luar lingkup Tahap 3

- Berkas kalibrator untuk produksi, pelatihan dengan data nyata, dan pengaktifan kalibrasi di produksi. Semuanya butuh dataset berlabel dan persetujuan terpisah (rencana bagian 4.4).
- Perubahan rumus, skor, penyebut, bobot, atau cakupan Phase 4, termasuk perubahan nilai berdasarkan status D4 (K7).
- Perubahan skema database, migrasi, dan menjalankan backend terhadap database produksi.
- Perubahan `.env` atau `config.yaml`. Lokasi berkas kalibrator lewat setting baru adalah butir keputusan (bagian 8, T3-1).
- Model, inference, alert, PDF, frontend, dan data historis.
- Model prediksi dengan banyak fitur (session-level prediction).

## 2. Input dan ground truth

### 2.1 Input saat penerapan (backend)

| Input | Sumber | Catatan |
|---|---|---|
| R = P_total | `aggregate(...)["duration_score"]`, presisi penuh | Satu-satunya fitur. Tidak ada confidence, P_i, atau jumlah kejadian. |
| `algo_version` | `session-summary-1` | Kunci kompatibilitas |
| Sidik bobot | bagian `w=` dari `config_version` | Kunci kompatibilitas (T3 Phase 4) |
| Himpunan indikasi yang dipakai | `weights_used` peserta | Kalibrator per himpunan (K3) |
| Cakupan video, dan cakupan audio bila indikasi suara dipakai | `coverage`, `audio_coverage` | Ambang K2 |
| Status D4 | blok `model_availability` (Tahap 2) | Bagian 4 |
| Berkas kalibrator | lokasi dari setting (T3-1); bawaan: tidak ada | Tanpa berkas → `not_calibrated` |
| Sidik berkas yang disetujui | setting terpisah (C6); bawaan: kosong | Kosong atau tidak cocok → berkas ditolak |
| Sidik model AI backend | dihitung backend saat model dimuat (C7) | Kosong (AI belum `READY`) atau tidak cocok → `models_mismatch` |

### 2.2 Ground truth

- **Data nyata:** belum tersedia (fakta awal rencana bagian 1.2). Tahap 3 **tidak** memakai data nyata apa pun, termasuk data produksi dan tinjauan pengawas.
- **Data buatan untuk tes:** R diambil acak di [0, 1], lalu label Y ~ Bernoulli(1/(1+exp(−(a·R+b)))) dengan a dan b diketahui (mis. a = 4, b = −3), plus `student_id`/`exam_id` buatan untuk tes kebocoran. Dengan begitu kebenaran fit dan metrik dapat dibuktikan.
- **Format masukan skrip** (disiapkan untuk data nyata kelak, tanpa diisi):
  - per baris sesi peserta: `exam_id`, `student_id`, `label`, `label_agreed`, `R`, `coverage`, `audio_coverage`, `indicator_set`, `weights_fingerprint`, `algo_version`, `d4_status`, `split` (`calibration`/`test`), serta `models_fingerprint` dan `config_version` (rancangan revisi 3, §2.10.2);
  - definisi label mengikuti K1.

## 3. Kondisi `calibrated` dan `not_calibrated`

### 3.1 `calibrated`

Status `calibrated` diberikan bila **semua** syarat berikut terpenuhi:
1. Berkas kalibrator ada, terbaca, lengkap, dan sah: metode `platt`, a > 0, a dan b berhingga, versi dan definisi target terisi. Putusan `memadai` cocok dengan hitungan ulang, dan versi kriteria sama (C5, rancangan §2.2). SHA-256 berkas sama dengan setting sidik persetujuan, dan setting itu tidak kosong (C6).
2. `algo_version` sama.
3. Sidik bobot sama.
4. Himpunan indikasi peserta sama dengan himpunan berkas (K3).
5. Cakupan video ≥ ambang berkas (K2: 50 %). Bila himpunan memuat indikasi suara, cakupan audio memenuhi ambang berkas.
6. Status D4 = `lengkap` (bagian 4).
7. R ada (bukan `null`).
8. Sidik model AI backend tersedia dan sama dengan `lineage.models_fingerprint` berkas (C7).

Hasilnya: `calibration = {status: "calibrated", version: <versi berkas>, probability: 1/(1+exp(−(a·R+b)))}`. Probabilitas berpresisi penuh, dibulatkan hanya saat penyajian.

### 3.2 `not_calibrated`

Bila satu saja syarat di atas gagal, statusnya `not_calibrated` dengan `probability = null` dan daftar **semua** alasan yang berlaku, bukan hanya yang pertama.

| Kode alasan | Syarat yang gagal |
|---|---|
| `no_calibrator` | Tidak ada berkas (keadaan produksi) |
| `invalid_calibrator` | Berkas rusak atau tidak sah; putusan bukan `memadai` atau tidak cocok dengan hitungan ulang; versi kriteria berbeda; setting sidik kosong; sidik berkas tidak cocok (C5, C6). K6: finalisasi tetap berjalan, peringatan di log. |
| `algo_version_mismatch` | Versi algoritme berbeda |
| `weights_mismatch` | Sidik bobot berbeda |
| `indicator_set_mismatch` | Himpunan indikasi berbeda |
| `coverage_below_threshold` | Cakupan video atau audio di bawah ambang; termasuk cakupan 0 % |
| `model_unavailable` | Status D4 `model_unavailable` |
| `model_availability_not_recorded` | Status D4 `tidak_tercatat` |
| `no_score` | R `null` |
| `models_mismatch` | Sidik model AI backend tidak tersedia (AI belum `READY`) atau berbeda dari `lineage.models_fingerprint` (C7; revisi desain terhadap T3-5) |

Daftar 10 kode ini identik dengan rancangan revisi 4 §5.1, yang menjadi acuan. Catatan "Belum tersedia" yang sudah ada tetap dipakai untuk `no_calibrator`.

## 4. Hubungan status D4 dengan kelayakan kalibrasi

| Status D4 (Tahap 2) | Kalibrasi | Dataset kalibrasi (skrip) |
|---|---|---|
| `lengkap` | Boleh, bila syarat lain terpenuhi | Boleh dipakai |
| `model_unavailable` | **Tidak pernah**: `not_calibrated`, alasan `model_unavailable` | Dikeluarkan; jumlahnya dilaporkan |
| `tidak_tercatat` (sesi sebelum pencatatan D4, atau tanpa analisis AI) | Tidak pernah: `not_calibrated`, alasan `model_availability_not_recorded` | Dikeluarkan; jumlahnya dilaporkan |

- Aturan ini berlaku untuk sesi **secara keseluruhan**, bukan per indikasi. Satu indikasi terdampak saja sudah membuat P_total sesi itu tidak layak dikalibrasi.
- Status D4 tidak mengubah R. Kalibrasi tidak dijalankan bila status D4 tidak `lengkap`, dan R tetap tersimpan apa adanya (K7 terbuka).

## 5. Perlakuan probabilitas yang tidak memenuhi syarat

1. **Tidak dihitung sama sekali.** Probabilitas tidak dihitung lalu disembunyikan; perhitungan dilewati, sehingga tidak ada nilai yang bisa bocor ke log, API, atau snapshot.
2. **Disimpan sebagai `null`.** Kolom `calibrated_probability` tetap `NULL`. CHECK database yang sudah ada (`calibration_status = 'calibrated' OR calibrated_probability IS NULL`) menjadi pengaman kedua.
3. **Alasan tercatat.** Daftar kode alasan disimpan di metadata JSON baris `*` (tanpa kolom baru) dan dikembalikan oleh API live dan final.
4. **Beku.** Status, versi, probabilitas, dan alasan dibekukan saat finalisasi. Berkas kalibrator yang diganti atau dihapus setelahnya tidak mengubah hasil final.
5. **Skrip luring.** Skrip pelatihan **tidak menulis berkas kalibrator** bila:
   - jumlah minimum per set (K5) tidak terpenuhi;
   - hanya ada satu kelas;
   - terjadi separasi sempurna atau fit tidak konvergen;
   - a ≤ 0;
   - ditemukan kebocoran.
   
   Skrip berhenti dengan kode galat dan laporan alasannya. Berkas yang ditulis pun tidak otomatis aktif; aktivasi adalah keputusan terpisah.
6. **Live dan draf (keputusan T3-2).** Usulan saya: probabilitas hanya dihitung untuk snapshot final. Hasil live menampilkan status dan alasan saja, supaya angka probabilitas sementara tidak beredar sebelum laporan final.

## 6. Rumus dan data Phase 4 yang tidak boleh berubah

| Hal | Jaminan |
|---|---|
| Rumus | p = aktif/teranalisis; P_i = Σ w_k p_k / Σ w_k; P_total = Σ v_i P_i / Σ v_i; w_k = d_k/300; aturan data kosong, `no_audio_data`, pengecualian config, presisi penuh |
| Nilai | R, P_i, cakupan, Σw, interval, alasan tanpa data, dan `excluded` identik dengan dan tanpa kalibrator. Kalibrasi hanya **menambah** status/probabilitas di sampingnya. |
| Snapshot | Baris dan kolom sama dengan Phase 4. Hanya kolom kalibrasi yang sudah ada dan metadata JSON baris `*` yang terisi. Tetap idempoten dan beku. |
| D4 | Tabel `model_availability` dan blok D4 tidak diubah; hanya dibaca |
| `algo_version` | Tetap `session-summary-1`, karena perhitungan skor tidak berubah. Versi kalibrator dicatat di `calibration_version`. |
| Skema dan data | Tidak ada tabel atau kolom baru, tidak ada migrasi, tidak ada perubahan data historis, tidak ada backfill |
| Bobot dan config | `config.yaml` dan `.env` tidak berubah |

## 7. Rencana pengujian dan kriteria penerimaan

### 7.1 Tes (basis data sementara dan data buatan saja)

| # | Tes | Kriteria lulus |
|---|---|---|
| 1 | Tanpa berkas kalibrator | `not_calibrated`, `no_calibrator`, probabilitas `null`, catatan "Belum tersedia". Semua angka dan baris snapshot identik dengan Phase 4. |
| 2 | Berkas rusak: JSON tidak valid, field hilang, a ≤ 0, NaN/tak hingga, metode asing | `invalid_calibrator` dengan rincian; finalisasi tetap 200 (K6) |
| 3 | Ketidakcocokan versi, sidik bobot, himpunan indikasi | Kode alasan yang tepat; beberapa alasan sekaligus tercatat semua |
| 4 | Cakupan di bawah ambang, cakupan 0 %, cakupan audio kurang | `coverage_below_threshold`; probabilitas `null` |
| 5 | Status D4 `model_unavailable` dan `tidak_tercatat` | `model_unavailable` / `model_availability_not_recorded`, walaupun berkas sah dan syarat lain terpenuhi |
| 6 | Semua syarat terpenuhi (berkas uji) | Probabilitas = 1/(1+exp(−(aR+b))) dengan presisi 1e-12; status `calibrated`; versi tercatat |
| 7 | Snapshot beku | Mengganti atau menghapus berkas setelah finalisasi tidak mengubah hasil; finalisasi ulang 409; penulisan ulang tidak menambah baris |
| 8 | Skor tidak berubah | R, P_i, cakupan, interval identik antara tanpa berkas, berkas sah, dan berkas rusak |
| 9 | CHECK database | Probabilitas tanpa status `calibrated` tetap ditolak |
| 10 | Live (sesuai T3-2) | Live tidak memuat angka probabilitas; status dan alasan ada |
| 11 | Pemulihan parameter | Data buatan a = 4, b = −3, n = 5.000: estimasi a dan b dalam ±10 %; Brier terkalibrasi < Brier R mentah; ECE < 0,03 |
| 12 | Metrik | Brier, log loss, ECE, slope/intercept kalibrasi, AUROC pada contoh kecil sama dengan hitungan tangan |
| 13 | Ketidakpastian | Bootstrap me-resample **peserta**; selang 95 % memuat nilai titik; jumlah sampel efektif dilaporkan |
| 14 | Kebocoran | Peserta atau sesi yang sama di set kalibrasi dan test → skrip berhenti dengan kode galat, tanpa berkas |
| 15 | Kasus degeneratif | Satu kelas, separasi sempurna, jumlah di bawah K5, a ≤ 0 → berhenti tanpa berkas |
| 16 | Penyaringan dataset | Baris dengan D4 bukan `lengkap`, cakupan di bawah ambang, atau label tidak disepakati dikeluarkan dari kedua set; jumlah per alasan dilaporkan |
| 17 | Regresi | Semua tes backend dan modul AI lulus; hash `backend/data` sama dengan manifest Phase 2; database produksi tidak disentuh |

### 7.2 Kriteria penerimaan Tahap 3

1. Tes 1–17 lulus dan tidak ada tes lama yang gagal.
2. Tanpa berkas kalibrator (keadaan produksi), hasil Session Summary identik dengan Tahap 2, selain daftar alasan `no_calibrator` di metadata.
3. Tidak ada probabilitas yang dihitung untuk sesi yang tidak memenuhi bagian 3.1, termasuk semua sesi dengan status D4 bukan `lengkap`.
4. Rumus, nilai, snapshot, dan data Phase 4 tidak berubah (bagian 6), dan K7 tetap tidak tersentuh.
5. Tidak ada perubahan skema, migrasi, `.env`, `config.yaml`, model, alert, PDF, atau frontend. Backend baru tidak dijalankan terhadap database produksi.
6. Laporan Tahap 3 memuat file yang berubah, hasil tes, dan risiko terbuka. Pekerjaan berhenti untuk evaluasi.

## 8. Keputusan yang diperlukan sebelum implementasi

| ID | Keputusan | Usulan | Status |
|---|---|---|---|
| T3-1 | Cara menentukan lokasi berkas kalibrator | Setting baru di `settings.py` (mis. `EDUAI_SESSION_CALIBRATOR`, bawaan kosong = tidak ada kalibrator). `.env` **tidak** diubah, sehingga produksi tetap tanpa kalibrator. | Disetujui (rancangan) |
| T3-2 | Probabilitas di hasil live | Tidak: hanya di snapshot final; live menampilkan status dan alasan | Disetujui (rancangan) |
| T3-3 | Ambang cakupan audio untuk himpunan dengan indikasi suara | Ditetapkan di berkas kalibrator (`min_audio_coverage`), 50 % | Disetujui dengan ketentuan (rancangan §2.2) |
| T3-4 | Implementasi fit dan metrik | Pustaka standar Python (Newton–Raphson), tanpa dependensi baru | Disetujui (rancangan) |
| T3-5 | Kode alasan | Daftar di bagian 3.2 | Disetujui; direvisi oleh C7 (`models_mismatch`) |

Keputusan tambahan (T3-6, C1–C7) dan statusnya tercatat di dokumen rancangan revisi 4, bagian 5. Semua persetujuan di atas adalah persetujuan rancangan; implementasi menunggu persetujuan eksplisit.

K7 tetap terbuka dan tidak disentuh oleh Tahap 3.
