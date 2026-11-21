# Session Report: Rencana Phase 5 (Kalibrasi)

Tanggal: 21 November 2026 (revisi 1) · Status: **Rencana disetujui pemilik proyek (21 November 2026): K1–K6 disetujui, K7 tetap terbuka.** Pelaksanaan: Tahap 1 (audit D4), Tahap 2 (pencatatan D4), dan Tahap 3 (mekanisme kalibrasi) selesai dan diterima. Tahap 4 (kebutuhan dataset, L5) ditutup pada 21 November 2026 sebagai tahap perancangan (`EDUAI_SESSION_REPORT_PHASE5_TAHAP4_RESULTS.md`; D1 `SESSION_CALIBRATION_DATASET.md`). Langkah 5–7 rencana (§9: regresi penuh, laporan hasil Phase 5, evaluasi penerimaan) belum dilakukan. *Status awal: "rencana, belum diimplementasikan. Semua keputusan K1–K7 masih menunggu persetujuan pemilik proyek."*

Dokumen ini hanya rencana. Tidak ada kode, config, database, model, atau data yang diubah, dan tidak ada commit. Phase 4 telah **diterima** pemilik proyek (21 November 2026). Status itu tidak diubah oleh dokumen ini.

Lingkup tetap sama dengan Phase 4: Session Summary berbasis skor durasi. Phase 5 tidak menambah:
- session-level prediction dari fitur baru;
- temporal probability aggregation;
- video-level classification.

**Isi revisi 1:**
- D4 tidak mengubah rumus Phase 4;
- definisi target kalibrasi;
- jumlah data minimum training dan test dipisah;
- konsistensi dengan keputusan Session Summary;
- rancangan Session Report Phase 6;
- status keputusan K1–K7;
- urutan kerja.

---

## 1. Tujuan dan ruang lingkup

### 1.1 Tujuan

Phase 5 menyiapkan jalur yang aman dan dapat diuji untuk memetakan P_total ke **probabilitas terkalibrasi**. Jalur ini hanya dipakai bila semua syarat berikut terpenuhi:
1. ada kalibrator yang dilatih dari ground truth tingkat sesi;
2. dataset memenuhi kriteria yang disepakati (bagian 3);
3. hasil evaluasinya disetujui pemilik proyek.

Selama syarat itu belum terpenuhi, hasil tetap:
- `calibration.status = "not_calibrated"`;
- `probability = null`;
- catatan "Belum tersedia".

### 1.2 Fakta awal (dari audit Phase 1, bagian 8; tidak berubah)

Ground truth tingkat sesi **belum tersedia**:
- `labels.csv` hanya berisi 2 baris label dan satu baris rusak;
- `dataset_raw.zip` berisi label per frame, bukan per sesi;
- tinjauan pengawas hanya ada untuk kejadian yang ditandai sistem, sehingga mengandung bias seleksi;
- data produksi tidak punya label.

Karena itu Phase 5 **tidak dapat** menghasilkan kalibrator produksi. Yang dibangun hanyalah mekanisme, alat ukur, dan spesifikasi data.

### 1.3 Termasuk dalam lingkup

| No | Hasil | Lokasi rencana |
|---|---|---|
| L1 | Audit D4 dan pencatatan ketersediaan model per peserta. Tidak mengubah rumus Phase 4 (bagian 5). | Ditentukan setelah audit; perkiraan `ai_service.py` dan penyimpanan status per peserta |
| L2 | Antarmuka kalibrator: memuat dan memvalidasi berkas kalibrator, lalu menerapkannya pada P_total bila valid, cocok, dan syarat ketersediaan data terpenuhi. Selain itu `not_calibrated`. | `backend/app/calibration.py` (baru) |
| L3 | Skrip pelatihan dan evaluasi kalibrator (Platt) dengan pemisahan per peserta dan laporan ketidakpastian | `ai/eduai-ai/scripts/calibrate_session.py` (baru), memakai `scripts/eval_stats.py` |
| L4 | Generator data buatan dengan probabilitas sebenarnya yang diketahui, khusus untuk tes | Di dalam tes |
| L5 | Dokumen kebutuhan dataset dan protokol pelabelan tingkat sesi | `docs/SESSION_CALIBRATION_DATASET.md` (baru) |
| L6 | Tes penerimaan dan laporan hasil Phase 5 | `backend/tests/test_calibration.py`, `ai/eduai-ai/tests/test_calibrate_session.py`, `docs/EDUAI_SESSION_REPORT_PHASE5_RESULTS.md` |

### 1.4 Di luar lingkup

- Kalibrator produksi. Tidak ada data berlabel, jadi tidak ada probabilitas di produksi.
- Perubahan rumus P_total, bobot indikasi, bobot interval, penyebut, normalisasi, atau snapshot Phase 4. Setiap perubahan seperti ini memerlukan persetujuan terpisah, termasuk bila diusulkan untuk menangani D4.
- Model prediksi dengan banyak fitur, misalnya regresi logistik per indikasi atau confidence sebagai fitur. Ini termasuk session-level prediction.
- **PDF dan frontend.** Keduanya direncanakan untuk Phase 6 (bagian 7).
- Model, inference, alert, data historis, dan migrasi skema. Kolom `calibration_status`, `calibration_version`, `calibrated_probability` beserta CHECK-nya sudah ada sejak Phase 2.

## 2. Konsistensi dengan Session Summary (keputusan Phase 4 yang dipertahankan)

Phase 5 memakai hasil Phase 4 apa adanya:

| Keputusan | Isi yang dipertahankan |
|---|---|
| Unit pengamatan | Pengamatan disimpan **per menit**: satu baris per menit per sumber, dengan mask 60 bit untuk detik yang teramati. Sampel confidence dan audio juga dijumlahkan per menit; cakupan audio beresolusi satu menit. |
| Interval dan bobot | Interval 300 detik, setengah terbuka. Bobot interval w_k = d_k / 300 dari **durasi aktual**, sehingga interval parsial berkontribusi sebanding dengan durasinya. |
| Skor durasi | p = waktu aktif / waktu yang dapat dianalisis. P_i = Σ w_k p_k / Σ w_k. P_total = Σ v_i P_i / Σ v_i. Bobot interval dan bobot indikasi terpisah. Presisi penuh; pembulatan hanya saat penyajian. |
| Indikasi tanpa data | Interval tanpa data bernilai 0 dan tetap di penyebut, dengan alasan tercatat. Audio disetujui tetapi tanpa sampel sama sekali: dikecualikan (`no_audio_data`). Audio sebagian: interval tanpa audio bernilai 0 dengan alasan `no_audio_data`. Indikasi tanpa persetujuan audio, nonaktif, atau berkategori info: dikecualikan dengan alasan, tidak dihitung 0. |
| Cakupan dan ketersediaan | `coverage` (video), `audio_coverage`, `excluded`, dan `config_excluded` dicatat **terpisah** dari skor |
| Cakupan 0% | Skor tetap 0 (opsi a) dengan `coverage_note`. Cakupan 0% **bukan** bukti bahwa perilaku tidak terjadi. |
| Snapshot | Ditulis sekali saat finalisasi dalam transaksi yang sama dengan `report_finals`; idempoten; beku; menyimpan `config_version` bersidik bobot dan bobot yang benar-benar dipakai |

## 3. Data, skor, dan target kalibrasi

### 3.1 Skor masukan

Hanya satu skor: **R = P_total** per peserta per sesi (`session_participant_summary`, baris `*`), dengan presisi penuh.

Alasannya, kalibrasi hanya memetakan skor yang sudah ada tanpa mengubah urutan peringkat. Memakai lebih dari satu fitur berarti membangun model prediksi baru, dan itu di luar lingkup.

Average confidence, P_i per indikasi, dan jumlah kejadian tetap dicatat dalam dataset, tetapi tidak dipakai sebagai masukan.

### 3.2 Definisi target dan makna probabilitas

**Definisi target yang diusulkan (K1, menunggu persetujuan):**

> Y = 1 bila sesi peserta memuat sedikitnya satu perilaku teramati yang termasuk daftar indikasi Session Summary, ditetapkan oleh **dua pelabel independen** yang meninjau **rekaman sesi penuh**, bukan hanya kejadian yang ditandai sistem. Ketidaksepakatan diselesaikan oleh pelabel ketiga.

**Makna probabilitas terkalibrasi:** perkiraan kemungkinan bahwa sesi tersebut **memenuhi definisi perilaku teramati di atas**, menurut ground truth tingkat sesi yang dipakai melatih kalibrator.

Probabilitas ini **bukan**:
- probabilitas bahwa peserta berbuat curang atau melanggar aturan;
- penilaian niat;
- keputusan akademik.

Perilaku yang teramati, misalnya ponsel terlihat atau wajah tidak tampak, bisa punya penjelasan yang sah. Penilaian pelanggaran tetap menjadi wewenang manusia.

Kalibrator **tidak boleh diaktifkan** sebelum ketiga syarat ini terpenuhi:
- dataset ground truth memenuhi kriteria yang disepakati (bagian 3.4);
- evaluasi pada set test memenuhi kriteria aktivasi (bagian 4.4);
- pemilik proyek menyetujuinya.

### 3.3 Syarat kompatibilitas dan ketersediaan data

Probabilitas hanya diberikan bila semua syarat berikut terpenuhi. Bila satu saja gagal, hasilnya `not_calibrated` dengan alasan yang menyebut syarat mana yang gagal.

| Syarat | Sumber | Bila tidak terpenuhi |
|---|---|---|
| `algo_version` sama | `session-summary-1` | "versi algoritme berbeda" |
| Sidik bobot sama | bagian `w=` dari `config_version` (T3) | "bobot berbeda" |
| Himpunan indikasi yang dipakai sama | `weights_used` peserta (dengan/tanpa audio) | "himpunan indikasi berbeda". Opsi lain: satu kalibrator per himpunan (K3). |
| Cakupan di atas ambang | `coverage`, dan `audio_coverage` bila audio dipakai | "cakupan di bawah ambang" (K2). Cakupan 0% tidak pernah diberi probabilitas. |
| **Tidak ada `model_unavailable`** | Pencatatan D4 per peserta (bagian 5) | "model tidak tersedia". **Sesi dengan model_unavailable tidak boleh mendapatkan probabilitas kalibrasi.** |
| Status pencatatan D4 diketahui | Sesi sebelum pencatatan D4 tidak punya catatan ketersediaan model | "ketersediaan model tidak tercatat" |

### 3.4 Kebutuhan dataset

**Sumber data.** Sesi uji coba atau simulasi dengan persetujuan peserta. Sebagian peserta mengikuti skenario perilaku terencana, sebagian ujian normal. Rekaman penuh diperlukan agar pelabelan tidak bergantung pada sistem.

Tinjauan pengawas (`reviews`) **tidak** dipakai sebagai label karena bias seleksi. Data ini boleh dilaporkan terpisah sebagai pembanding.

**Kesepakatan pelabel.** Diukur dengan Cohen's κ (`eval_stats.cohen_kappa`, `label_agreement.py`), dan κ dilaporkan beserta selang kepercayaannya. Ambang diusulkan κ ≥ 0,6 (K1).

**Pemisahan dan pencegahan kebocoran:**
- Pemisahan dilakukan per **peserta**. Semua sesi seorang peserta masuk ke satu set saja, kalibrasi atau test.
- Sesi ujian yang sama sebaiknya tidak terbagi antara kedua set, karena kondisi ruang, jadwal, dan perangkat yang sama bisa bocor.
- Set test dikunci sebelum pelatihan dan hanya dipakai sekali untuk evaluasi akhir.
- Skrip memeriksa irisan `student_id` dan `exam_id` antara kedua set. Bila ada irisan, skrip berhenti dengan galat (fail-fast).
- Ambang cakupan (K2), aturan pengecualian D4, dan definisi target ditetapkan **sebelum** melihat hasil test.
- Sesi dengan `model_unavailable`, cakupan di bawah ambang, atau label yang tidak disepakati dikeluarkan dari **kedua** set. Jumlah dan alasannya dilaporkan.

**Jumlah minimum (usulan, K5, menunggu persetujuan):**

| Set | Positif (Y = 1) | Negatif (Y = 0) | Catatan |
|---|---|---|---|
| Kalibrasi (training) | ≥ 50 | ≥ 50 | Platt hanya memperkirakan 2 parameter. Set yang lebih kecil membuat a dan b tidak stabil. |
| Test (evaluasi) | ≥ 100 | ≥ 100 | Pedoman umum validasi model probabilitas: sekitar 100 kejadian dan 100 non-kejadian agar slope kalibrasi dan Brier cukup sempit selang kepercayaannya |

Jumlah dihitung **setelah** pengecualian di atas, per himpunan indikasi bila K3 memilih kalibrator per himpunan.

**Jumlah minimum adalah syarat perlu, bukan syarat cukup.** Memenuhi jumlah ini tidak otomatis membuat kalibrator layak dipakai. Kelayakan ditentukan oleh hasil evaluasi beserta ketidakpastiannya (bagian 4.4) dan persetujuan pemilik proyek. Bila selang kepercayaan terlalu lebar, data harus ditambah walaupun jumlah minimum sudah terpenuhi.

## 4. Metode kalibrasi dan evaluasi

### 4.1 Metode: Platt scaling (regresi logistik satu variabel)

P_session = 1 / (1 + exp(−(a·R + b))), dengan a dan b diestimasi dengan maximum likelihood pada set kalibrasi.

| Pilihan | Alasan |
|---|---|
| **Platt (usulan)** | Dua parameter, cocok untuk data sedikit. Monoton naik (urutan peringkat dipertahankan) bila a > 0. Dapat diimplementasikan dengan pustaka standar (Newton–Raphson). |
| Isotonic regression | Butuh data jauh lebih banyak; kurva bertangga tidak stabil pada set kecil. Bisa dibandingkan nanti bila data mencapai ribuan sesi. |
| Beta calibration / temperature | Tidak memberi keuntungan berarti untuk satu skor di [0, 1] dengan data kecil |

**Pengaman yang direncanakan:**
- a ≤ 0 → kalibrator ditolak;
- separasi sempurna, satu kelas saja, atau gagal konvergensi → pelatihan berhenti tanpa menulis berkas;
- nilai NaN atau tak hingga → ditolak.

### 4.2 Berkas kalibrator (rancangan)

Berkas JSON berisi:
- `version`, `method: "platt"`, `a`, `b`;
- `target_definition`;
- `algo_version`, `weights_fingerprint`, `indicator_set`, `min_coverage`;
- `trained_on`: rentang tanggal, jumlah sesi, peserta, positif, dan negatif per set, plus jumlah sesi yang dikeluarkan beserta alasannya;
- metrik test beserta selang kepercayaan;
- `created_at`, `approved_by`.

Antarmuka hanya menerima berkas yang lengkap dan bernilai wajar. Bawaannya tidak ada berkas.

**Berkas rusak saat finalisasi (K6, menunggu persetujuan).** Usulan saya, finalisasi tidak gagal. Hasilnya `not_calibrated` dengan alasan tercatat dan peringatan di log.

Bila kalibrator valid dan syarat 3.3 terpenuhi, probabilitas dihitung saat finalisasi dan dibekukan di snapshot bersama `calibration_version`. Snapshot lama tidak dihitung ulang.

### 4.3 Evaluasi dan pelaporan ketidakpastian

Evaluasi dilakukan pada set test yang terpisah per peserta. Setiap metrik dilaporkan sebagai **nilai titik dan selang kepercayaan 95 %** dari bootstrap berkelompok per peserta (resampling peserta, bukan sesi). Jumlah sampel efektif dilaporkan bersamanya.

| Metrik | Gunanya |
|---|---|
| Brier score dan Brier skill score terhadap baseline prevalensi | Akurasi probabilitas keseluruhan |
| Log loss | Hukuman untuk probabilitas yang terlalu yakin |
| Kurva reliabilitas (bin kuantil) dan ECE | Kecocokan probabilitas prediksi dengan frekuensi teramati. Jumlah sesi per bin ikut ditampilkan. |
| Calibration slope dan intercept | Idealnya slope ≈ 1 dan intercept ≈ 0 |
| AUROC dan average precision (`eval_stats`) | Daya pembeda P_total. Kalibrasi tidak mengubahnya; dilaporkan agar probabilitas yang terkalibrasi tetapi tidak membedakan kelas tidak dianggap berguna. |
| Analisis per kelompok cakupan dan himpunan indikasi | Memeriksa apakah kalibrasi bertahan di subkelompok. Subkelompok kecil dilaporkan sebagai indikatif saja. |

### 4.4 Kriteria aktivasi kalibrator (di luar Phase 5, keputusan terpisah)

Kalibrator baru boleh diusulkan untuk diaktifkan bila:
- dataset memenuhi bagian 3.4;
- pada set test, selang kepercayaan slope berada di sekitar 1 (usulan 0,8–1,2 untuk nilai titik), intercept mendekati 0, dan Brier skill score > 0 dengan batas bawah selang > 0;
- batas bawah selang AUROC > 0,5;
- pemilik proyek menyetujui.

Ambang-ambang ini adalah usulan dan menjadi bagian K5.

## 5. Risiko D4: model gagal dimuat atau gagal saat inference

### 5.1 Prinsip

Model yang gagal dimuat atau gagal saat inference **tidak boleh** dianggap sebagai indikasi yang tidak terjadi. Nol karena model tidak berjalan berbeda maknanya dari nol karena perilaku tidak ada. D4 harus **terdeteksi dan tercatat per peserta**, dan sesi dengan `model_unavailable` tidak mendapat probabilitas kalibrasi.

Penanganan D4 di Phase 5 **tidak mengubah** rumus P_total, bobot, penyebut, normalisasi, atau snapshot Phase 4. Perlakuan skor untuk indikasi yang modelnya tidak tersedia ditetapkan lewat keputusan terpisah (K7).

### 5.2 Hasil pemeriksaan kode (hanya-baca; tidak berubah dari rencana awal)

| Situasi | Perilaku sekarang | Dampak pada skor |
|---|---|---|
| Model yang diaktifkan gagal dimuat **saat backend start** | Setiap model yang aktif di config diperlakukan wajib (`model_check.inventory`). Jika satu saja gagal, status AI menjadi `FAILED` dan tidak ada analisis sama sekali. | Tidak ada observasi, sehingga cakupan 0, muncul `coverage_note`, dan skor tidak dihitung sebagai bukti. **Gagal tertutup.** |
| Analisis audio dimatikan lewat `EDUAI_AUDIO_ANALYSIS=false` padahal config `enabled: true` | Model audio tidak dimuat dan tidak ada sampel audio | Tertangani T1: `no_audio_data` |
| Set model **per peserta** dibuat belakangan (`_perception`, cadangan `_make_spare`) dan satu model opsional gagal dimuat | `MediaPipePerception._load` menangkap galat, mencatat peringatan di log, dan model itu menjadi `None`. Analisis peserta tetap berjalan. | **Tidak terdeteksi oleh Session Summary.** Contoh: tanpa object detector, PHONE_VISIBLE tidak pernah muncul dan P_i = 0 dengan cakupan penuh. |
| Galat inference model buku (CLIP) per frame | Ditangkap supaya analisis tidak berhenti (`perception.py` sekitar baris 225) | BOOK_VISIBLE bisa menjadi 0 tanpa jejak |
| Model di luar proses backend (mis. sumber worker/LiveKit) | Belum diperiksa | Masuk audit D4 (langkah 1) |

### 5.3 Dampak

- **Validitas skor.**
  - P_i indikasi yang terdampak menjadi 0, sehingga P_total turun (bias ke bawah) sementara cakupan tetap tampak penuh.
  - Sampai D4 tercatat, skor peserta seperti itu tidak dapat dibedakan dari skor yang sah.
- **Kalibrasi.**
  - Sesi D4 di dataset latih membuat hubungan R dan Y berisik, dan probabilitas untuk R tinggi diremehkan.
  - Perbedaan frekuensi D4 antara data latih dan produksi membuat kalibrator tidak berlaku (dataset shift).
  - Oleh karena itu sesi D4 dikeluarkan dari dataset dan tidak pernah diberi probabilitas.

### 5.4 Usulan penanganan dalam Phase 5 (K4, menunggu persetujuan)

**Termasuk dalam usulan K4 (tanpa perubahan rumus):**
1. **Deteksi.** Catat ketersediaan setiap model per peserta:
   - saat set model peserta dibuat, dari `perception.status`;
   - selama sesi, lewat penghitung galat inference per model.
2. **Pencatatan.** Simpan status ini per peserta, termasuk indikasi yang terdampak, model, waktu, dan jumlah galat. Status juga disertakan dalam hasil live dan dalam metadata snapshot (JSON baris `*`) **tanpa** mengubah nilai skor, bobot, atau penyebut, dan tanpa kolom baru bila memungkinkan.
3. **Penanda.** Peserta dengan `model_unavailable` diberi penanda ketersediaan data yang terlihat, terpisah dari cakupan, dengan teks bahwa skor indikasi terdampak tidak dapat dibaca sebagai "tidak terjadi".
4. **Kalibrasi.** `model_unavailable` → `not_calibrated` (syarat 3.3), dan sesi itu dikeluarkan dari dataset kalibrasi.

**Tidak termasuk dalam K4 (keputusan terpisah K7):** apakah indikasi yang modelnya tidak tersedia nantinya dikecualikan dari P_total, ditandai tidak valid, atau perlakuan lain. Sampai K7 disetujui, P_total dihitung persis seperti Phase 4.

Alternatif K4 untuk perbandingan:
- **B:** hanya menyaring dataset dari log, tanpa pencatatan runtime. Laporan produksi tetap tanpa penanda, dan log bisa hilang.
- **C:** gagal tertutup per peserta. Ini mengubah perilaku analisis dan alert, sehingga di luar lingkup.

## 6. Tes penerimaan dan kriteria keberhasilan

### 6.1 Tes (semua dengan basis data sementara dan data buatan)

| # | Tes | Kriteria lulus |
|---|---|---|
| 1 | Tanpa berkas kalibrator | `not_calibrated`, `probability = null`, catatan "Belum tersedia". Skor dan snapshot sama persis dengan Phase 4. |
| 2 | Berkas rusak: JSON tidak valid, field hilang, a ≤ 0, NaN, metode asing | `not_calibrated` dengan alasan spesifik. Perilaku finalisasi sesuai K6. |
| 3 | Ketidakcocokan versi algoritme, sidik bobot, atau himpunan indikasi | `not_calibrated` dengan alasan yang menyebut kunci yang berbeda |
| 4 | Cakupan di bawah ambang atau 0% | Tidak ada probabilitas; alasan dan `coverage_note` tercatat |
| 5 | Kalibrator valid (berkas uji) dan semua syarat 3.3 terpenuhi | p = 1/(1+exp(−(aR+b))) cocok dengan hitungan tangan (presisi 1e-12). Status `calibrated`, versi tercatat, probabilitas dibekukan di snapshot. |
| 6 | Snapshot beku | Mengganti atau menghapus berkas kalibrator setelah finalisasi tidak mengubah hasil final. Finalisasi ulang 409. |
| 7 | CHECK database | Probabilitas tanpa status `calibrated` tetap ditolak |
| 8 | Pemulihan parameter | Data buatan dari a = 4, b = −3 dengan n = 5.000: estimasi a dan b dalam ±10 %. Brier terkalibrasi < Brier P_total mentah. ECE < 0,03. |
| 9 | Kebocoran | Peserta atau sesi yang sama di set kalibrasi dan test → skrip berhenti dengan kode galat |
| 10 | Kasus degeneratif dan jumlah kurang | Satu kelas saja, separasi sempurna, atau jumlah di bawah minimum K5 → berhenti tanpa menulis berkas |
| 11 | Metrik dan ketidakpastian | Brier, log loss, ECE, slope/intercept, AUROC pada contoh kecil dengan nilai hitungan tangan. Bootstrap me-resample peserta dan menghasilkan selang yang memuat nilai titik. |
| 12 | **D4: deteksi dan pencatatan** | Perception palsu tanpa object detector, atau dengan galat inference buatan, menghasilkan `model_unavailable` tercatat untuk peserta itu (model, indikasi terdampak, alasan) di hasil live dan metadata snapshot. **P_total, P_i, bobot, dan penyebut identik dengan perhitungan Phase 4 untuk data yang sama.** Status kalibrasi `not_calibrated` dengan alasan "model tidak tersedia", walaupun ada kalibrator valid. Peserta lain dalam sesi yang sama tidak terpengaruh. |
| 13 | D4 di dataset | Sesi dengan `model_unavailable` dikeluarkan dari set kalibrasi dan test; jumlahnya dilaporkan |
| 14 | Regresi | Semua tes backend dan modul AI lulus. Hash `backend/data` sama dengan manifest Phase 2. |

### 6.2 Kriteria keberhasilan Phase 5

1. Semua tes 1–14 lulus dan tidak ada tes lama yang gagal.
2. Di produksi **tidak ada satu pun probabilitas**. Tidak ada berkas kalibrator; semua hasil `not_calibrated`.
3. Mekanisme kalibrasi terbukti benar pada data buatan (tes 5, 8, 11) dan menolak semua masukan atau kondisi yang tidak sah (tes 2–4, 9, 10, 12).
4. D4 terdeteksi dan tercatat per peserta tanpa mengubah rumus Phase 4, bila K4 disetujui.
5. Dokumen kebutuhan dataset (L5) lengkap: definisi target dan maknanya, protokol pelabelan, ambang κ, jumlah minimum per set, aturan pemisahan dan kebocoran, serta pelaporan ketidakpastian.
6. Tidak ada perubahan pada rumus P_total, snapshot Phase 4, data historis, model, inference, alert, PDF, atau frontend di luar yang tertulis di sini.

## 7. Rancangan final EduAI Session Report (Phase 6, di luar lingkup Phase 5)

Bagian ini hanya menyelaraskan rencana. **PDF dan frontend tidak dikerjakan di Phase 5.** Implementasinya direncanakan untuk Phase 6 dan memerlukan persetujuan terpisah.

> **Diperbarui 21 November 2026:** target arsitektur akhir dan struktur PDF empat bagian (Session Overview; Indication Analysis; Session Timeline; Data Coverage & Calculation Details) ditetapkan pemilik proyek dan dicatat di `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md` bagian 1. Struktur itu menggantikan tabel 7.1 di bawah; aturan penyajian 7.2 tetap berlaku.

### 7.1 Struktur laporan

| Bagian | Isi yang direncanakan |
|---|---|
| Session Overview | Identitas sesi dan peserta, jadwal, jendela sesi, status (lengkap/sementara/tidak tersedia), versi algoritme dan konfigurasi |
| Indication Summary | Per indikasi: status ALERT, Indication Score (%), jumlah kejadian, dan alasan bila dikecualikan |
| Indication Analysis | Rincian per indikasi: skor per interval, average confidence per sumber (N/A bila tanpa sampel), dan bukti terkait |
| Session Timeline | Garis waktu interval dan episode indikasi, interval tanpa data beserta alasannya |
| Data Coverage | Cakupan video dan audio terpisah, interval tanpa data, `no_audio_data`, `model_unavailable` (bila K4 disetujui), dan catatan cakupan 0% |
| Calculation Details | Rumus, bobot indikasi dan interval, indikasi yang dikecualikan beserta alasannya, `config_version`, `algo_version`, status kalibrasi |

### 7.2 Aturan penyajian

- **ALERT ditentukan per indikasi.** Overall Session Score (P_total) hanya ringkasan agregasi sesi dan **tidak menggantikan** ALERT per indikasi.
- **Sumber data:** PDF dibuat dari **finalization snapshot**, bukan dengan menghitung ulang prediksi AI. Laporan draf sebelum finalisasi ditandai sementara.
- **Sesi tanpa data:** tampil sebagai "tidak tersedia" atau "tidak dapat dianalisis secara valid", dengan cakupan 0% dan catatan cakupan. Skor 0% tidak boleh ditampilkan seolah-olah sesi telah diamati lengkap.
- **Istilah:** sebelum kalibrator disetujui dan diaktifkan, nilai skor disebut **Indication Score (%)**, bukan *calibrated probability*. Status kalibrasi ditulis "Belum tersedia". Bila kelak diaktifkan, probabilitas disajikan sesuai makna di bagian 3.2, bukan sebagai probabilitas kecurangan.
- **Pembulatan:** hanya saat penyajian, karena nilai tersimpan berpresisi penuh.

## 8. Keputusan pemilik proyek

Semua butir di bawah adalah **usulan**. Tidak ada yang dianggap final sebelum disetujui pemilik proyek.

| ID | Keputusan | Usulan | Status |
|---|---|---|---|
| K1 | Definisi target Y, makna probabilitas, dan ambang κ pelabel | Bagian 3.2; κ ≥ 0,6 | Disetujui (21 November 2026): κ ≥ 0,6 sebagai ambang awal |
| K2 | Ambang cakupan minimum untuk diberi probabilitas | 50 % cakupan video; cakupan audio sesuai himpunan indikasi | Disetujui (21 November 2026), dengan definisi cakupan yang jelas dan pemeriksaan audio sesuai himpunan |
| K3 | Satu kalibrator untuk semua atau per himpunan indikasi | Per himpunan; yang tidak cocok → `not_calibrated` | Disetujui (21 November 2026) |
| K4 | Penanganan D4 di Phase 5 | Deteksi, pencatatan, penanda, dan pengecualian dari kalibrasi, tanpa mengubah rumus (bagian 5.4) | Disetujui (21 November 2026), tanpa mengubah rumus Phase 4 |
| K5 | Jumlah minimum per set dan kriteria aktivasi | Kalibrasi ≥ 50 positif dan ≥ 50 negatif; test ≥ 100 positif dan ≥ 100 negatif; kriteria bagian 4.4 | Disetujui (21 November 2026) sebagai kriteria minimum awal, bukan jaminan kelayakan; test split dikunci |
| K6 | Berkas kalibrator rusak saat finalisasi | Finalisasi tetap jalan; `not_calibrated` dengan alasan | Disetujui (21 November 2026) |
| K7 | Perlakuan skor indikasi yang modelnya tidak tersedia (perubahan rumus Phase 4) | Belum diusulkan. Dibahas terpisah setelah audit D4. Sampai disetujui, rumus Phase 4 berlaku apa adanya. | **Tetap terbuka** (belum disetujui); di luar Phase 5 kecuali disetujui |

## 9. Urutan kerja (setelah Phase 5 disetujui)

1. **Audit D4 (hanya-baca)** atas jalur pemuatan dan inference semua model, termasuk worker/LiveKit dan audio. Hasilnya dilaporkan. Bila ditemukan kebutuhan mengubah rumus Phase 4, pekerjaan berhenti dan menunggu K7.
2. **Penanganan D4 sesuai K4** dengan cadangan file lebih dulu. Hanya deteksi, pencatatan, dan penanda, tanpa mengubah P_total, bobot, penyebut, normalisasi, atau snapshot Phase 4. Tes 12 dan 13.
3. **Mekanisme kalibrasi**, dikerjakan setelah K1, K2, K3, K5, dan K6 disetujui:
   - `calibration.py` dengan validasi dan syarat 3.3, beserta tes 1–7;
   - `calibrate_session.py` dengan Platt, metrik, bootstrap per peserta, dan pemeriksaan kebocoran, beserta tes 8–11.
4. **Dokumen kebutuhan dataset** (L5) diselesaikan.
5. **Regresi penuh** backend dan modul AI, ditambah perbandingan hash data produksi.
6. **Laporan hasil** `docs/EDUAI_SESSION_REPORT_PHASE5_RESULTS.md`.
7. **Berhenti** dan menunggu evaluasi penerimaan Phase 5. Phase 6 (PDF dan frontend) tidak dimulai tanpa persetujuan terpisah.
