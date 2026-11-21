# EduAI Session Report: Penyelarasan dengan Arsitektur Target

Tanggal: 21 November 2026 · Status: **Diterima pemilik proyek sebagai acuan pemetaan keselarasan, konflik, dan keputusan terbuka (21 November 2026). Ini penerimaan hasil evaluasi dokumentasi, bukan persetujuan implementasi atau pengesahan usulan di dalamnya.** **Pembaruan 21 November 2026: P1-5 diputuskan = S1 dan AL-3 diputuskan = C (sumber T_k; tanpa nilai).** P1-4, AL-1, AL-2, AL-4, AL-5, AL-6, K7, dan keputusan turunan AL-3 tetap terbuka. Usulan tiga status ALERT (§5.2) belum disetujui. Rekomendasi P1-5a tidak dipakai sebagai rekomendasi aktif. Tidak ada perubahan perilaku ALERT, rumus Phase 4, atau mekanisme finalisasi. PDF dari snapshot tetap target Phase 6.

Dokumen ini hanya dokumentasi dan evaluasi. Tidak ada kode, konfigurasi, database, data, atau dataset yang diubah atau dibuat. Tidak ada migrasi, kalibrasi produksi, perubahan perilaku ALERT, atau commit. Phase 5 Tahap 4 belum dimulai.

**Dokumen yang diperiksa:**
- rancangan interval: `DESIGN_SESSION_SUMMARY_INTERVAL.md`;
- hasil Phase 3: `EDUAI_SESSION_REPORT_PHASE3_RESULTS.md`;
- hasil Phase 4: `EDUAI_SESSION_REPORT_PHASE4_RESULTS.md`;
- revisi Phase 4: `EDUAI_SESSION_REPORT_PHASE4_REVISION_RESULTS.md`;
- rencana Phase 5: `EDUAI_SESSION_REPORT_PHASE5_PLAN.md`;
- hasil Tahap 2: `EDUAI_SESSION_REPORT_PHASE5_TAHAP2_RESULTS.md`;
- Tahap 3: `EDUAI_SESSION_REPORT_PHASE5_TAHAP3_SCOPE.md`, `_DESIGN.md`, `_RESULTS.md`;
- evaluasi P1: `EDUAI_SESSION_REPORT_PHASE5_P1_EVALUATION.md`;
- evaluasi P1-4/P1-5: `EDUAI_SESSION_REPORT_P1_4_P1_5_EVALUATION.md`;
- kode yang terkait, dibaca saja (`session_summary.py`, `cases.py`, `summary.py`, `api.py`).

---

## 1. Arsitektur target (ditetapkan pemilik proyek)

Session Report memiliki **dua hasil utama yang terpisah**:
1. **Indication Summary**: skor sesi dan status **Session Indication Alert** per indikasi.
2. **Overall Session Summary**: skor berbobot, durasi sesi, cakupan, dan jumlah indikasi yang mencapai ALERT.

**Alur:**

Session Start → AI Observation → Per-minute Score dan Data Availability → 5-minute Interval Aggregation → Indication Summary dan Session Indication Alert → Overall Session Summary → Coverage Calculation → Session Finalization → PDF Generation dari finalization snapshot.

PDF tidak menjalankan ulang prediksi AI dan tidak menghitung ulang hasil sesi yang sudah difinalisasi.

## 2. Lima besaran yang harus dibedakan

| Besaran | Definisi yang berlaku sekarang | Sumber | Catatan |
|---|---|---|---|
| **Indication score** P_k | p = detik aktif / detik yang dapat dianalisis per interval; P_k = Σ w_j p_j / Σ w_j, dengan w_j = d_j/300 (Phase 4) | Snapshot `session_participant_summary` per indikasi, `session_interval_summary` per interval | Proporsi waktu, bukan probabilitas |
| **Overall weighted score** P_total | Σ v_k P_k / Σ v_k atas `weights_used` (Phase 4) | Baris `*` | Ringkasan, bukan pengganti ALERT |
| **Calibrated session probability** | P = 1/(1+exp(−(aR+b))) dengan R = P_total, hanya dengan kalibrator yang disetujui (Tahap 3) | Kolom `calibrated_probability` baris `*` | Saat ini `null` + `not_calibrated` (belum ada kalibrator). Hanya per sesi, tidak per indikasi. |
| **Status ALERT** | Lihat §4: ada dua mekanisme yang **berbeda** | — | P1-5 diputuskan S1: dua mekanisme terpisah. Implementasi Session Indication Alert menunggu AL-2, AL-4, AL-5, nilai T_k. |
| **Data availability** | Per interval: `no_data_reason`. Per indikasi: `excluded` (tanpa persetujuan audio, `no_audio_data`, config), D4 `model_availability`. Per sesi: `coverage_note`, status `tidak_tersedia`. | Snapshot (kolom dan metadata JSON) | Belum ada status ketersediaan **per indikasi** yang ringkas (§5) |
| **Coverage** | Video: Σ w_j (detik teranalisis_j/d_j)/Σ w_j. Audio: idem, resolusi menit, `null` tanpa persetujuan. | Kolom `coverage`; metadata `audio_coverage` | **Tidak dikalikan ke skor** (diuji di revisi Phase 4, T5) |

## 3. Matriks keselarasan

| # | Unsur arsitektur target | Keadaan sekarang | Penilaian |
|---|---|---|---|
| 1 | Dua hasil terpisah (Indication Summary dan Overall Session Summary) | Per peserta tersedia P_k per indikasi dan baris `*` untuk P_total | **Sesuai** untuk skor. ALERT belum ada di Session Summary (G1). |
| 2 | AI Observation | Pelacakan detik teramati per menit per sumber (`observation_seconds`, Phase 2) | **Sesuai** |
| 3 | Per-minute Score dan Data Availability | Ketersediaan data disimpan **per menit** (mask 60 bit per detik, sampel confidence/audio per menit). Skor **tidak** dihitung per menit; skor interval dihitung langsung dari detik aktif dan detik yang dapat dianalisis di dalam interval. | **Sebagian.** Lihat AL-1. |
| 4 | Agregasi interval 5 menit dengan durasi aktual | Interval 300 detik, w_j = d_j/300, interval parsial proporsional (Phase 4) | **Sesuai** |
| 5 | Indication Summary + Session Indication Alert | P_k ada. Session Indication Alert berbasis skor (Alert_k = 1 jika P_k ≥ T_k) **belum ada**. Yang berjalan adalah Live Rule Alert berbasis episode. | **Bertentangan / belum diputuskan.** Lihat §4, P1-5, AL-3. |
| 6 | Overall Session Summary: skor berbobot, durasi, cakupan, jumlah ALERT | P_total, `scheduled_s`, `observed_s`, jendela sesi, dan cakupan ada. Jumlah indikasi ALERT belum ada. | **Sebagian** (G2, bergantung P1-5) |
| 7 | Coverage Calculation, terpisah, tidak dikalikan | Cakupan video dan audio terpisah dari skor; tidak dikalikan | **Sesuai.** Cakupan per indikasi belum disajikan (G3). |
| 8 | Session Finalization | Snapshot beku dan idempoten (Phase 4), plus D4 (Tahap 2) dan kalibrasi (Tahap 3) di metadata | **Sesuai** untuk unsur yang ada; ALERT dan threshold belum dibekukan (G4) |
| 9 | PDF dari snapshot final | PDF laporan sekarang (`/api/sessions/{id}/report.pdf`) dibangun dari data laporan (`_report_data`), bukan dari snapshot Session Summary. Session Summary belum masuk PDF. | **Belum sesuai.** Direncanakan untuk Phase 6 (AL-6). |
| 10 | PDF tidak menghitung ulang | Snapshot Session Summary dibaca apa adanya (`read_snapshot`) | **Sesuai** untuk API; PDF menunggu Phase 6 |
| 11 | Kalibrasi hanya untuk sesi; `null` + `not_calibrated` tanpa kalibrator sah | Tahap 3 | **Sesuai** |
| 12 | Coverage tidak dikalikan ke skor | Diuji (revisi Phase 4, T5) | **Sesuai** |

## 4. ALERT: dua mekanisme yang tidak sama

| | **Live Rule Alert** (berjalan sekarang) | **Session Indication Alert** (arsitektur target) |
|---|---|---|
| Rumus | Aturan terpenuhi bila ≥ `min_count` episode dalam `window_s` (`cases.rule_status`) | Alert_k = 1 jika P_k ≥ T_k; Alert_k = 0 jika P_k < T_k |
| Sumber | Kejadian dan episode (`events`, `cases.episodes_of`) | Indication score P_k dari snapshot |
| Waktu | Selama sesi, langsung | Pada Session Report (final); selama sesi hanya nilai sementara |
| Threshold | `min_count`/`window_s` di `config.yaml` `summary_rules` (nilai produk awal, bukan hasil validasi model) | T_k **belum ada**; belum tervalidasi dan belum siap dipakai |
| Dipakai untuk | Pop-up notifikasi pengawas, urutan prioritas tinjauan, status aturan, `rules_met` di ringkasan ujian, daftar kasus | Indication Summary dan jumlah ALERT di Overall Session Summary |

**Kedua mekanisme tidak sama dan tidak boleh disamakan.** Arsitektur target mensyaratkan Session Indication Alert. Live Rule Alert tetap berjalan seperti sekarang dan **tidak** diganti tanpa persetujuan pemilik proyek.

Pemisahan **diputuskan (P1-5 = S1, 21 November 2026)**:
- **Live Rule Alert** tetap mekanisme pemantauan langsung, tidak diubah.
- **Session Indication Alert** menjadi status di Session Report, ditentukan dari P_k dan T_k.
- Laporan memakai **nama berbeda** untuk keduanya, sehingga pengawas tidak menganggap "memenuhi ambang" selama ujian sama dengan ALERT di laporan.

**Prasyarat sebelum Session Indication Alert dapat diimplementasikan** (semuanya belum ada):
1. **Definisi T_k** per indikasi: skala sama dengan P_k (proporsi waktu, 0–1), satu nilai per indikasi, dan apakah berbeda per `indicator_set`.
2. **Sumber T_k**, **diputuskan (AL-3 = C, 21 November 2026):** ambang awal dari kebijakan Program Studi yang terdokumentasi (berlabel "belum divalidasi data"), kemudian divalidasi dengan data berlabel per indikasi (ground truth per indikasi, berbeda dari ground truth tingkat sesi K1). Nilai T_k belum ditetapkan.
3. **Persetujuan T_k** dan lokasinya (config atau berkas yang disetujui), termasuk versi dan pembekuan di snapshot.
4. **Aturan data kosong** untuk status ALERT (§5, AL-2).

## 5. Skor, data kosong, dan status "Tidak tersedia"

### 5.1 Keputusan yang sudah disetujui (Phase 4)

| Keputusan | Isi | Sumber |
|---|---|---|
| Interval tanpa data | p = 0, tetap di penyebut P_k, alasan tercatat (`no_data_reason`) | Keputusan pemilik proyek, rancangan interval §2.4 dan Phase 3 |
| Cakupan 0 % | Skor tetap 0 dengan `coverage_note` ("skor 0 bukan bukti tidak ada indikasi") | Revisi Phase 4 T2, opsi (a) |
| Audio tanpa satu pun sampel | Indikasi suara **dikecualikan** (`no_audio_data`), bukan 0 | Revisi Phase 4 T1 |
| Audio sebagian | Interval tanpa audio = 0 dengan alasan `no_audio_data` | Revisi Phase 4 T1 |
| Indikasi nonaktif atau info di config | Dikecualikan dengan alasan, bukan 0 | Revisi Phase 4 T4 |
| Model tidak tersedia (D4) | Skor tetap rumus Phase 4; indikasi ditandai `model_unavailable`; nilai numerik menunggu K7 | Tahap 2 |
| Sesi sebelum fitur | `tidak_tersedia`, tidak dihitung ulang (A7) | Phase 3/4 |

Jadi "data tidak tersedia = skor 0" **sudah merupakan keputusan eksplisit untuk skor** (interval tanpa data dan cakupan 0 %), disertai alasan dan catatan. Keputusan itu tidak diubah di sini.

### 5.2 Konflik dengan arsitektur target

Arsitektur target meminta: **"Jika seluruh data indikasi tidak tersedia, status harus menunjukkan No data/Tidak tersedia, bukan otomatis NORMAL atau ALERT."**

| Situasi | Skor menurut Phase 4 | Status yang diminta target | Konflik |
|---|---|---|---|
| Cakupan video 0 % (tidak ada detik teranalisis) | P_k = 0 untuk semua indikasi video, `coverage_note` | "Tidak tersedia" untuk indikasi video | Bila Session Indication Alert dihitung langsung dari P_k = 0, hasilnya NORMAL. Itu **tidak boleh**. Perlu aturan status terpisah dari skor (AL-2). |
| Indikasi suara tanpa sampel audio | Dikecualikan (`no_audio_data`) | "Tidak tersedia" | Selaras: tidak ada skor, status dapat "Tidak tersedia" |
| Indikasi dinonaktifkan config | Dikecualikan | Bukan NORMAL/ALERT | Selaras bila status "Tidak dinilai/Tidak tersedia" |
| Model indikasi tidak tersedia (D4) | P_k = 0, ditandai `model_unavailable` | "Tidak tersedia"? | **Terbuka**, terkait K7 |
| Cakupan sebagian (mis. 20 %) | P_k memuat interval tanpa data sebagai 0, sehingga P_k terdilusi | NORMAL/ALERT dari P_k ≥ T_k | P_k yang terdilusi bisa berada di bawah T_k hanya karena data kurang. Perlu keputusan: ambang cakupan minimum untuk status ALERT, status "data tidak cukup", atau P_k tetap dipakai apa adanya (AL-2). |

**Usulan arah (belum diputuskan):** status Session Indication Alert punya **tiga nilai**, `ALERT`, `NORMAL`, dan `TIDAK_TERSEDIA`.
- Status ditentukan dari P_k, T_k, **dan** ketersediaan data indikasi itu.
- Rumus P_k dan aturan data kosong Phase 4 **tidak diubah**. Ketersediaan data hanya menentukan apakah status boleh dihitung.

## 6. Finalization snapshot: yang sudah dan belum disimpan

| Isi yang diminta target | Tersedia sekarang | Tempat | Catatan |
|---|---|---|---|
| Session ID dan waktu sesi | Ya | `exam_id`; `start_ts`/`end_ts` per interval; `observation_start`/`end`; `scheduled_s` | Jendela sesi tersirat dari interval pertama dan terakhir |
| `indicator_set` | Ya | `weights_used` di metadata `*` | Kunci himpunan eksplisit belum ada (B2/P1) |
| Indication scores | Ya | Baris per indikasi dan per interval | |
| Session Indication Alert + threshold | **Tidak** | — | G1/G4, bergantung P1-5 dan AL-3 |
| Overall weighted score | Ya | Baris `*` | |
| Durasi dan cakupan | Ya | `scheduled_s`, `observed_s`, `sum_w`, `coverage`; `audio_coverage` di metadata | Cakupan **per indikasi** belum ada (G3) |
| Bobot dan konfigurasi | Ya | `weights`, `weights_used`, `source`, `config_excluded`, `config_version` (bersidik bobot) | Threshold Live Rule Alert (`summary_rules`) belum dibekukan |
| Versi perhitungan | Ya | `algo_version` | |
| Status dan metadata kalibrasi | Ya | Kolom kalibrasi + `calibration_reasons`, `calibration_details`, `calibration_approved_sha256`, `models_fingerprint` | |
| Alasan data atau probabilitas tidak tersedia | Ya, sebagian | `no_data_reason` per interval, `excluded`, `coverage_note`, `model_availability`, `calibration_reasons` | Status ketersediaan per indikasi yang ringkas belum ada (AL-4) |

### 6.1 Sesi lama dan field baru

- Laporan yang difinalisasi **sebelum** Session Summary ada → `tidak_tersedia` (A7, K8). Tidak dihitung ulang dan tidak di-backfill.
- Snapshot dari versi lebih awal yang belum punya field Tahap 2/3 (`model_availability`, `calibration_*`, `models_fingerprint`) → `read_snapshot` mengembalikan `null` untuk field itu. Penyajian (Phase 6) wajib menampilkan **"Tidak tersedia"**, bukan 0, NORMAL, atau kosong.
- Catatan: database produksi belum dimigrasi, sehingga saat ini di produksi belum ada snapshot Session Summary sama sekali.
- Tidak ada backfill dan tidak ada hitung ulang sesi lama tanpa persetujuan terpisah.

### 6.2 Identitas konfigurasi laporan (keputusan K-b = KB-1, 21 November 2026)

Sidik T_k disimpan di field snapshot **terpisah** dari `config_version`; parser `calibration.weights_fingerprint` dan bentuk `config_version` (`"<version>;w=<sidik bobot>"`) tidak diubah. Konsekuensinya, **`config_version` tidak lagi mewakili seluruh konfigurasi laporan**. Identitas konfigurasi sebuah laporan adalah gabungan:

- `algo_version` (rumus Session Summary);
- `config_version` (versi config dan sidik bobot indikasi);
- sidik dan versi T_k di field terpisah (nama field final ditetapkan bersama AL-5);
- sidik threshold Live Rule Alert, bila G4 disetujui;
- field kalibrasi (`calibration_version`, `calibration_approved_sha256`, `models_fingerprint`).

Kalibrator tidak bergantung pada T_k, sesuai P1-5 = S1: kalibrasi tidak membaca ALERT.

## 7. Keputusan terbuka

Hanya dicatat, tidak diputuskan. Status keputusan yang sudah ada tidak diubah.

| ID | Keputusan | Hubungan |
|---|---|---|
| **P1-5** | Definisi ALERT: pemisahan Live Rule Alert dan Session Indication Alert (§4) | **Diputuskan (21 November 2026)**: **S1** |
| **AL-1** | "Per-minute Score": cukup ketersediaan data per menit seperti sekarang (skor interval dari detik), atau skor per menit harus dihitung dan disimpan sebagai tahap tersendiri. Menghitung skor interval sebagai agregasi skor per menit dapat memberi angka berbeda bila bobotnya tidak dari detik, sehingga perlu keputusan agar rumus Phase 4 tidak berubah tanpa sengaja. | Terbuka |
| **AL-2** | Status Session Indication Alert saat data kosong atau sebagian: tiga nilai (`ALERT`/`NORMAL`/`TIDAK_TERSEDIA`), ambang cakupan minimum untuk status, dan perlakuan P_k yang terdilusi. Tidak mengubah rumus P_k. | Terbuka; bergantung P1-5 |
| **AL-3** | Threshold T_k: sumber, definisi, persetujuan, lokasi, versi, dan pembekuan | **Diputuskan (21 November 2026)** untuk **sumber = C** (kebijakan Program Studi, lalu validasi data per indikasi). Nilai T_k, lokasi, aturan validasi, dan kriteria evaluasi validasi **masih terbuka**. |
| **AL-4** | Status ketersediaan data per indikasi dalam Indication Summary: penggabungan cakupan video/audio, `excluded`, dan D4 | Terbuka; terkait G3 dan K7 |
| **AL-5** | Isi snapshot tambahan: Session Indication Alert, T_k, threshold Live Rule Alert, cakupan dan ketersediaan per indikasi | Terbuka; sama dengan G1–G4 |
| **OS-1** | Status Overall Session Summary | **Diputuskan (21 November 2026): O1**, tanpa status NORMAL/ALERT gabungan |
| **K-b** | Penyimpanan sidik T_k | **Diputuskan (21 November 2026): KB-1**, field terpisah (§6.2) |
| **AL-6** | PDF Session Report dibangun dari snapshot final (Phase 6), termasuk penyajian "Tidak tersedia" untuk field yang tidak ada | Terbuka; Phase 6 belum disetujui |
| **P1-4** | Prioritas dataset V5 / V5+A3, termasuk definisi Y untuk V5+A3, persetujuan audio, pengumpulan audio penelitian, penyimpanan, akses, dan penghapusan | **Belum diputuskan** |
| **K7** | Perlakuan nilai indikasi terdampak D4 | Terbuka |

## 8. Batas pekerjaan

- Dokumentasi dan evaluasi saja.
- Tidak ada perubahan kode, konfigurasi, database, data, atau dataset; tidak ada migrasi, kalibrasi produksi, perubahan perilaku ALERT, atau commit.
- Phase 5 Tahap 4, B2, G1–G4, dan Phase 6 belum dimulai.
