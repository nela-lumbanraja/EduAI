# Session Report Phase 5, Tahap 3: Rancangan Mekanisme Kalibrasi dan Acuan Arsitektur Akhir

Tanggal: 21 November 2026 (revisi 4) · Status: **RANCANGAN DISETUJUI (T3-1 sampai T3-6, C1–C7). Implementasi kemudian disetujui, selesai, dan diterima pemilik proyek** (lihat `EDUAI_SESSION_REPORT_PHASE5_TAHAP3_RESULTS.md`; penyesuaian P1 dievaluasi di `EDUAI_SESSION_REPORT_PHASE5_P1_EVALUATION.md`). Teks "menunggu persetujuan implementasi" di dalam dokumen ini adalah catatan historis tahap rancangan. *Status awal: "IMPLEMENTASI MENUNGGU PERSETUJUAN EKSPLISIT. Belum ada implementasi."*

**Penyelarasan akhir revisi 4:**
- daftar kode alasan di ruang lingkup §3.2 disamakan dengan §5.1 (10 kode), dan dokumen ini dinyatakan sebagai acuan;
- sidik model kosong tidak pernah lolos (§2.10.4), dan `lineage.models_fingerprint` wajib terisi (§2.2);
- D-R12 dinyatakan tegas: sidik backend tidak menjamin kesesuaian model worker OpenVidu.

**Isi revisi 4** (keputusan C6 dan C7):
- C6 dan C7 disetujui sebagai keputusan tambahan (bagian 5). T3-1 sampai T3-6 dan C1–C5 tetap.
- **Revisi desain terhadap T3-5:** kode alasan `models_mismatch` ditambahkan. Daftar final kode alasan ada di §5.1.
- §2.10.3 (pengikatan SHA-256) disesuaikan dengan ketentuan C6. §2.10.4 baru menjelaskan pemeriksaan model AI (C7).
- §2.3, §2.4, §4, dan §6 diselaraskan. Risiko D-R9 sampai D-R12 tetap tercatat beserta mitigasinya.
- Acuan arsitektur akhir EduAI Session Report (bagian 1) **tidak berubah** akibat keputusan kalibrasi ini.

**Isi revisi 3** (catatan yang diminta sebelum implementasi):
- risiko D-R9 dan D-R10 tetap tercatat dan diperjelas (§6);
- mekanisme pencatatan test split yang sudah dipakai: registri append-only, berikut batasannya (§2.10.1);
- keterkaitan artefak kalibrator dengan model, split, dataset, kode, dan versi kriteria evaluasi (§2.10.2);
- validasi putusan tidak hanya bergantung pada metadata yang dapat disunting: kalibrator hanya aktif bila sidik berkasnya cocok dengan sidik yang ditetapkan saat persetujuan (§2.10.3, usulan C6, disetujui di revisi 4);
- usulan C7: pemeriksaan kecocokan model AI saat penerapan (disetujui di revisi 4).

**Isi revisi 2** (jawaban atas lima permintaan klarifikasi):
- **C1:** overlap sesi ujian antar-split dikembalikan menjadi kondisi **berhenti**. Alasannya di §2.6.1: target generalisasi adalah sesi ujian baru, dan perubahan menjadi peringatan di revisi 1 tidak sesuai dengan target itu.
- **C2:** test split dipakai sekali, dengan aturan konsumsi test split, sidik data dan kriteria di laporan, serta kriteria berupa konstanta kode (§2.6 langkah 6).
- **C3:** §2.9 baru menegaskan bahwa kegagalan kelayakan tidak mengaktifkan, tidak menghasilkan probabilitas, dan tidak mengubah hasil sesi.
- **C4:** definisi intercept dipertegas (calibration-in-the-large) dan aturan bootstrap dibuat konsisten untuk keempat kriteria (§2.7, §2.8).
- **C5:** definisi cakupan yang dibandingkan ambang dipertegas, dan `calibration.load` menghitung ulang putusan dari metrik di berkas (§2.2).

**Isi revisi 1:**
- status T3-1 sampai T3-6 diperbarui;
- klarifikasi pemilik proyek dicatat di §2.6 (pemisahan calibration/test, target Platt dari calibration split saja, bootstrap dan pelaporan);
- §2.8 baru: keberhasilan teknis fitting dipisahkan dari kelayakan hasil evaluasi;
- validasi berkas di §2.2 ditambah syarat hasil evaluasi.

Dokumen ini hanya rancangan. Tidak ada kode, database, konfigurasi, atau data yang diubah, dan tidak ada commit.

Dokumen ini melengkapi `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_SCOPE.md`: ruang lingkup ada di sana, cara kerja mekanismenya ada di sini.

**Batas yang tetap berlaku:**
- Rumus Phase 4, nilai skor, penyebut, aturan data kosong, dan mekanisme finalisasi yang sudah diterima tidak berubah.
- K7 tetap terbuka. Status D4 tidak mengubah nilai numerik apa pun.
- Migrasi produksi belum disetujui, dan backend dengan kode baru tidak dijalankan terhadap database produksi.
- Phase 6 belum dimulai.

---

## 1. Acuan arsitektur akhir EduAI Session Report

Rancangan ini dipertahankan sebagai **target arsitektur akhir**. Ia bukan persetujuan untuk mengimplementasikan Phase 6.

### 1.1 Komponen

| # | Komponen | Isi target |
|---|---|---|
| A1 | Indication Summary | Skor sesi (Indication Score, P_i) dan status ALERT setiap indikasi |
| A2 | Overall Session Summary | P_total, durasi sesi, jumlah indikasi berstatus ALERT |
| A3 | Data Coverage | Cakupan per indikasi, terpisah dari skor |
| A4 | Model Availability (D4) | Status model, indikasi terdampak, catatan interpretasi |
| A5 | Session Finalization | Snapshot final berisi skor, cakupan, bobot, threshold, versi rumus, dan metadata yang diperlukan |
| A6 | PDF Generation | PDF dibuat dari snapshot final, tidak menghitung ulang prediksi AI |

### 1.2 Target struktur PDF (Phase 6)

1. **Session Overview**
2. **Indication Analysis**
3. **Session Timeline**: interval 5 menit; interval parsial memakai durasi aktual (w_k = d_k / 300)
4. **Data Coverage & Calculation Details**

Struktur empat bagian ini **menggantikan** usulan enam bagian di rencana Phase 5 bagian 7.1:

| Usulan lama (rencana §7.1) | Target baru |
|---|---|
| Session Overview | Session Overview |
| Indication Summary, Indication Analysis | Indication Analysis |
| Session Timeline | Session Timeline |
| Data Coverage, Calculation Details | Data Coverage & Calculation Details |

Aturan penyajian di rencana §7.2 tetap berlaku:
- ALERT per indikasi; Overall Session Score hanya ringkasan;
- PDF dari snapshot;
- sesi tanpa data tampil "tidak tersedia" dengan cakupan 0 %;
- istilah **Indication Score (%)** sebelum kalibrator disetujui;
- pembulatan hanya saat penyajian.

### 1.3 Keadaan sekarang dibandingkan target (hanya pemetaan; tidak dikerjakan di Tahap 3)

| Komponen | Sudah ada (Phase 4 + Tahap 2) | Celah terhadap target |
|---|---|---|
| A1 | P_i per indikasi (live dan snapshot). Live Rule Alert per indikasi sudah ada di sistem kasus (`cases.rule_status`: min_count episode dalam window_s, dari `config.yaml` `summary_rules`). | **G1.** Session Indication Alert (P_k ≥ T_k, P1-5 = S1) belum ada; status Live Rule Alert belum dicatat di Session Summary maupun snapshot sebagai field keterangan |
| A2 | P_total; jendela sesi (`duration_s`), durasi terjadwal (`scheduled_s`), detik teramati (`observed_s`) | **G2.** Jumlah Session Indication Alert belum ada di Session Summary |
| A3 | Cakupan video per interval dan per sesi; cakupan audio per interval dan per sesi; keduanya terpisah dari skor | **G3.** Belum ada daftar cakupan **per indikasi**. Indikasi video memakai cakupan video dan indikasi suara memakai cakupan audio, jadi daftar ini dapat diturunkan tanpa mengubah perhitungan; yang belum ada hanya penyajiannya. |
| A4 | Lengkap (Tahap 2): live dan snapshot | — |
| A5 | Snapshot menyimpan skor, cakupan, bobot (lengkap dan yang dipakai), `config_version` bersidik bobot, `algo_version`, pengecualian, D4, dan kolom kalibrasi | **G4.** T_k (nilai, versi, asal) dan Session Indication Alert, serta threshold dan status Live Rule Alert (`min_count`, `window_s`), belum dibekukan di snapshot |
| A6 | PDF laporan sekarang dibuat dari data laporan; Session Summary belum masuk PDF | Phase 6 |
| Timeline | Baris interval snapshot sudah menyimpan `start_ts`, `end_ts`, `d_s`, dan `w` per interval 300 detik | Cukup untuk timeline 5 menit dengan interval parsial; penyajian di Phase 6 |

G1–G4 menambah isi snapshot (A5), sehingga termasuk keputusan **tersendiri sebelum Phase 6**, bukan bagian Tahap 3.

**Prinsip yang perlu dijaga:**
- ALERT berasal dari aturan jumlah episode, bukan dari Indication Score maupun probabilitas kalibrasi.
  > **Catatan penyelarasan (21 November 2026):** kalimat di atas menggambarkan **Live Rule Alert** yang berjalan sekarang. Arsitektur target menetapkan **Session Indication Alert** berbasis skor (P_k ≥ T_k), mekanisme yang berbeda. Konflik ini terbuka (P1-5, AL-2, AL-3; `docs/EDUAI_SESSION_REPORT_ARCHITECTURE_ALIGNMENT.md` §4). **Pembaruan 21 November 2026:** P1-5 diputuskan = S1 (dua mekanisme terpisah) dan sumber T_k AL-3 = C; AL-2 dan nilai T_k masih terbuka. Prinsip bahwa kalibrasi tidak membaca, mengubah, atau menggantikan ALERT berlaku untuk kedua mekanisme.
- Kalibrasi tidak boleh mengubah atau menggantikan status ALERT.

## 2. Rancangan mekanisme kalibrasi

### 2.1 Posisi dalam alur data

```
compute_exam(...)                                   (Phase 4, tidak berubah)
  └─ per peserta: compute_student → aggregate → R = P_total, coverage, D4, weights_used
                                         │
                                         ▼
                       calibration.evaluate(peserta, kalibrator, konteks)      (baru, Tahap 3)
                                         │  hanya MEMBACA nilai di atas
                                         ▼
               blok "calibration": status, version, probability, reasons, note
                                         │
finalize_report → snapshot_statements    ▼   (mekanisme finalisasi sama; hanya kolom kalibrasi yang sudah
                                              ada dan metadata JSON baris '*' yang terisi)
```

Kalibrator dimuat sekali per perhitungan `compute_exam`, dari lokasi yang ditetapkan T3-1. Bawaannya tidak ada berkas, sehingga hasil = `no_calibrator`.

### 2.2 Format berkas kalibrator (rancangan)

Nilai di contoh ini **khusus tes**, bukan hasil pelatihan:

```json
{
  "format": "eduai-session-calibrator-1",
  "version": "uji-2026-11-21",
  "method": "platt",
  "a": 4.0,
  "b": -3.0,
  "target_definition": "K1: >=1 perilaku teramati dari daftar indikasi Session Summary, dua pelabel independen, rekaman penuh",
  "algo_version": "session-summary-1",
  "weights_fingerprint": "w=xxxxxxxx",
  "indicator_set": ["BOOK_VISIBLE", "FACE_ABSENT", "HEAD_TURN", "MULTIPLE_PERSONS", "PHONE_VISIBLE"],
  "min_coverage": 0.5,
  "min_audio_coverage": 0.5,
  "trained_on": {"from": "...", "to": "...", "calibration": {"sessions": 0, "students": 0, "pos": 0, "neg": 0},
                 "test": {"sessions": 0, "students": 0, "pos": 0, "neg": 0}, "excluded": {"model_unavailable": 0}},
  "metrics_test": {"brier": {"value": 0, "ci95": [0, 0], "ci_width": 0}, "...": "..."},
  "evaluation_verdict": "memadai",
  "lineage": {
    "criteria_version": "session-calibration-criteria-1", "criteria_sha256": "...",
    "script_sha256": "...", "dataset_sha256": "...",
    "calibration_split_sha256": "...", "test_split_sha256": "...",
    "config_version": "0.2-provisional;w=xxxxxxxx", "models_fingerprint": "...",
    "bootstrap": {"B": 2000, "seed": 20261121},
    "report_sha256": "...", "registry_entry": "..."
  },
  "created_at": "...",
  "approved_by": null
}
```

Satu berkas berlaku untuk **satu** himpunan indikasi (K3). Beberapa himpunan memerlukan beberapa berkas, misalnya satu folder berisi satu berkas per himpunan.

**Validasi** (gagal → `invalid_calibrator` beserta rinciannya):
- `format` dikenal;
- `method == "platt"`;
- `a`, `b`, `min_coverage`, `min_audio_coverage` berupa angka berhingga, dengan a > 0 dan ambang di [0, 1];
- `version`, `target_definition`, `algo_version`, `weights_fingerprint` berupa teks tidak kosong;
- `indicator_set` berisi daftar indikasi yang dikenal (`SCORED`) tanpa duplikat;
- `evaluation_verdict == "memadai"` (§2.8). Ini pengaman tambahan: berkas dengan hasil evaluasi belum memadai tidak pernah diterima, walaupun ditempatkan di lokasi aktif.
- **Putusan dihitung ulang (C5):** `calibration.load` menerapkan lagi kriteria §2.8 pada `metrics_test` di berkas (nilai titik dan selang 95 % slope, intercept, Brier skill score, AUROC, serta jumlah efektif). Bila hasilnya bukan `memadai`, atau tidak sama dengan `evaluation_verdict` yang tertulis, berkas ditolak (`invalid_calibrator`). Dengan begitu putusan tidak dapat diubah dengan menyunting berkas.

Kriteria §2.8 dan ambang K2/K5 didefinisikan **satu kali** di modul bersama (`eduai_ai`), yang dipakai oleh skrip pelatihan dan oleh `calibration.load`. Keduanya tidak mungkin memakai kriteria yang berbeda.

Tambahan revisi 3 (§2.10):
- `lineage.criteria_version` harus sama dengan versi kriteria yang berlaku di kode; bila berbeda, berkas ditolak.
- Sidik SHA-256 seluruh berkas harus sama dengan sidik yang ditetapkan saat persetujuan aktivasi (C6, §2.10.3). Pemeriksaan ini dilakukan **sebelum** isi berkas dibaca.
- `lineage.models_fingerprint` wajib berupa teks sidik yang tidak kosong. Bila kosong atau tidak ada, berkas tidak sah (`invalid_calibrator`).
- Saat penerapan, `lineage.models_fingerprint` harus sama dengan sidik model yang sedang dimuat backend (C7, §2.10.4). Bila tidak sama, kodenya `models_mismatch`.

Hitung ulang putusan dari `metrics_test` hanya pemeriksaan **konsistensi**: metrik itu sendiri juga tertulis di berkas dan dapat disunting. Jaminan bahwa berkas tidak diubah sesudah dievaluasi dan disetujui datang dari pengikatan sidik (§2.10.3), bukan dari isi berkas.

**Definisi cakupan yang dibandingkan dengan ambang (C5, kontrak Phase 4 apa adanya):**

| Ambang | Nilai yang dibandingkan | Definisi Phase 4 |
|---|---|---|
| `min_coverage` (50 %, K2) | `coverage` peserta, presisi penuh | Σ w_k · (detik teranalisis_k / d_k) / Σ w_k. Detik teranalisis = detik teramati dikurangi detik tidak-dapat-dianalisis. |
| `min_audio_coverage` (50 %, T3-3) | `audio_coverage` peserta, presisi penuh | Σ w_k · (detik dalam menit yang punya ≥ 1 sampel audio_k / d_k) / Σ w_k, resolusi satu menit; `null` tanpa persetujuan audio |

Aturan perbandingan:
- Lolos bila nilai ≥ ambang. Cakupan 0 % selalu gagal.
- Nilai tidak dibulatkan sebelum dibandingkan.
- Nilai tidak dihitung ulang: yang dibaca adalah nilai yang sama dengan yang disimpan di snapshot.

Ambang cakupan audio (T3-3):
- hanya syarat **kelayakan kalibrasi**;
- hanya diperiksa bila `weights_used` peserta memuat indikasi suara (OTHER_VOICE, WHISPER, BOOK_SOUND);
- bila indikasi suara sudah dikecualikan Phase 4 (tanpa persetujuan audio, `no_audio_data`, atau config), himpunan peserta adalah himpunan video, ambang audio tidak diperiksa, dan yang dipakai adalah kalibrator himpunan video (K3);
- bila indikasi suara ada di `weights_used` tetapi `audio_coverage` kosong, hasilnya gagal (`coverage_below_threshold`), tidak dianggap lolos.

Ambang ini tidak mengubah skor, cakupan, pengecualian, atau aturan Phase 4.

### 2.3 Antarmuka modul `calibration.py` (rancangan)

```text
load(path, approved_sha256) -> {"ok": bool, "calibrators": [...], "errors": [...]}
    path kosong/tidak ada  -> ok=True, calibrators=[]            (no_calibrator)
    sidik persetujuan kosong, atau SHA-256 berkas != sidik persetujuan
                            -> ok=False, errors=[rincian]         (invalid_calibrator; berkas tidak dianggap disetujui, C6)
    berkas tidak sah        -> ok=False, errors=[rincian]         (invalid_calibrator; log peringatan; tidak melempar galat)

reasons(student, total, config_version, calibrators, models_fingerprint_now) -> [kode alasan]
                                                                     kumpulkan SEMUA yang berlaku:
    no_calibrator / invalid_calibrator
    no_score                         bila total.duration_score is None
    models_mismatch                  bila models_fingerprint_now kosong (model backend tidak siap) atau
                                     != c.lineage.models_fingerprint   (C7)
    algo_version_mismatch            bila student.algo_version != c.algo_version
    weights_mismatch                 bila sidik bobot di config_version != c.weights_fingerprint
    indicator_set_mismatch           bila sorted(total.weights_used) tidak cocok dengan berkas mana pun
    coverage_below_threshold         bila coverage < min_coverage, atau ada indikasi suara dan
                                     audio_coverage < min_audio_coverage (cakupan 0 % selalu gagal)
    model_unavailable                bila model_availability.status == "model_unavailable"
    model_availability_not_recorded  bila model_availability.status == "tidak_tercatat"

evaluate(...) -> {"status", "version", "probability", "reasons", "note"}
    reasons kosong  -> status "calibrated", probability = 1/(1+exp(-(a*R+b))), version = c.version
    reasons ada     -> status "not_calibrated", probability None (tidak dihitung), version None,
                       note "Belum tersedia" bila no_calibrator
```

Pemeriksaan hanya membaca nilai yang sudah dihitung. Tidak ada fungsi yang menulis ke `indicators`, `total.duration_score`, `coverage`, interval, atau blok D4.

### 2.4 Penyimpanan

| Data | Tempat | Perubahan struktur |
|---|---|---|
| status, versi, probabilitas | kolom `calibration_status`, `calibration_version`, `calibrated_probability` baris `*` (sudah ada sejak Phase 2) | Tidak ada |
| kode alasan | metadata JSON baris `*`, kunci `calibration_reasons` | Tidak ada kolom baru |
| sidik berkas yang disetujui (C6) | metadata JSON baris `*`, kunci `calibration_approved_sha256`. Dicatat setiap kali setting sidik terisi, termasuk bila hasilnya `not_calibrated`, supaya terlihat berkas mana yang disetujui saat finalisasi. | Tidak ada kolom baru |
| sidik model backend saat finalisasi (C7) | metadata JSON baris `*`, kunci `models_fingerprint` | Tidak ada kolom baru |
| baris per indikasi | tetap `not_calibrated`, probabilitas `NULL`; probabilitas tidak pernah per indikasi | Tidak ada |

CHECK `calibration_status = 'calibrated' OR calibrated_probability IS NULL` tetap menjadi pengaman kedua. Hasil kalibrasi dibekukan bersama snapshot dan tidak dihitung ulang.

**Hasil live (T3-2):** status dan alasan saja, tanpa angka probabilitas.

### 2.5 Hubungan dengan skor, ALERT, dan istilah

- R, P_i, cakupan, interval, `excluded`, dan blok D4 identik dengan atau tanpa kalibrator.
- Live Rule Alert (aturan episode) dan Session Indication Alert (P_k ≥ T_k, P1-5 = S1) tidak membaca dan tidak dibaca oleh kalibrasi.
- Sebelum kalibrator disetujui dan diaktifkan, penyajian memakai **Indication Score (%)**. Probabilitas, bila kelak aktif, bermakna "kemungkinan sesi memenuhi definisi perilaku teramati (K1)", bukan probabilitas kecurangan.

### 2.6 Skrip pelatihan dan evaluasi (luring)

`calibrate_session.py --data <csv> --out <berkas> --report <laporan>`. Skrip tidak dipanggil backend, tidak membaca database produksi, dan tidak mengaktifkan apa pun.

1. **Baca dan validasi kolom** (format di ruang lingkup §2.2). Kolom kurang atau nilai tidak sah → berhenti.
2. **Saring** dan hitung jumlah per alasan:
   - D4 bukan `lengkap`;
   - cakupan di bawah ambang;
   - `label_agreed` salah;
   - versi algoritme, sidik bobot, atau himpunan indikasi berbeda dari target berkas.
3. **Periksa pemisahan** (klarifikasi pemilik proyek):
   - Pemisahan dilakukan **berdasarkan peserta**. Semua sesi seorang peserta berada di satu split saja. Irisan `student_id` antara calibration split dan test split → berhenti (kebocoran).
   - Kolom `split` ditetapkan **sebelum** skrip dijalankan. Skrip tidak membuat ulang, menukar, atau memilih split.
   - **Sesi ujian (`exam_id`) yang muncul di kedua split → berhenti (C1).** Split harus terpisah sekaligus per peserta **dan** per sesi ujian. Alasannya ada di §2.6.1.
4. **Periksa jumlah minimum K5:** calibration split ≥ 50 positif dan ≥ 50 negatif; test split ≥ 100 positif dan ≥ 100 negatif. Kurang → berhenti. Jumlah ini kriteria minimum awal, bukan jaminan kelayakan (§2.8).
5. **Fit Platt hanya pada calibration split:**
   - Newton–Raphson untuk log-likelihood logistik; batas iterasi dan toleransi.
   - Target Platt yang dihaluskan (T3-6): positif (N₊ + 1)/(N₊ + 2), negatif 1/(N₋ + 2).
   - **N₊ dan N₋ dihitung hanya dari calibration split.** Tidak ada nilai dari test split yang dipakai untuk menentukan target, a, b, atau parameter lain.
   - Separasi sempurna, tidak konvergen, atau a ≤ 0 → berhenti.
6. **Evaluasi pada test split, sekali, setelah a dan b dibekukan (C2):**
   - Test split **tidak** dipakai untuk fitting, tuning, pemilihan parameter, pemilihan model atau metode (metode tetap Platt; tidak ada pembandingan metode pada test split), perubahan ambang cakupan atau threshold, maupun perubahan kriteria kelayakan, **baik sebelum maupun sesudah hasil evaluasi diketahui**.
   - Ambang dan kriteria (K2, K5, §2.8) adalah **konstanta kode** di modul bersama, bukan argumen baris perintah. Mengubahnya memerlukan perubahan kode, dan itu butuh persetujuan pemilik proyek.
   - Laporan mencatat sidik (SHA-256) baris test split dan sidik kriteria yang dipakai.
   - **Aturan konsumsi test split:** sekali dievaluasi, test split itu dianggap terpakai. Bila putusannya `belum_memadai`, percobaan berikutnya, misalnya dengan data kalibrasi tambahan, harus dievaluasi pada **test split baru** yang belum pernah dilihat. Evaluasi ulang pada test split yang sama ditandai di laporan sebagai bukan evaluasi independen dan tidak boleh menghasilkan putusan `memadai`. Pendeteksiannya memakai registri test split (§2.10.1). Aturan ini juga dicatat di dokumen kebutuhan dataset (Tahap 4).
   - Baseline Brier skill score memakai prevalensi **calibration split**.
   - Metrik dihitung seperti §2.7, dengan pelaporan seperti §2.8.
7. **Laporan selalu ditulis.** Isinya parameter hasil fit, metrik, ketidakpastian, jumlah yang dikeluarkan per alasan, peringatan, dan putusan evaluasi (§2.8).
8. **Berkas kalibrator ditulis hanya bila** langkah 1–6 lolos secara teknis **dan** putusan evaluasi = `memadai`. Berkas itu tetap tidak aktif (`approved_by: null`) sampai ditempatkan sesuai T3-1 atas persetujuan pemilik proyek.

Kode keluar dibedakan per jenis kegagalan, untuk tes dan otomasi. "Fit berhasil tetapi evaluasi belum memadai" punya kode sendiri yang bukan sukses.

#### 2.6.1 Alasan metodologis: pemisahan per peserta dan per sesi ujian (C1)

**Target generalisasi.** Di produksi, kalibrator diterapkan saat finalisasi sesi ujian **baru**. Sesi itu belum pernah ada saat pelatihan, dan pesertanya bisa baru, bisa juga peserta lama. Evaluasi harus memperkirakan kinerja pada kondisi itu.

**Mengapa revisi 1 keliru.** Di revisi 1, overlap `exam_id` saya turunkan menjadi peringatan karena membaca "pemisahan berdasarkan peserta" sebagai satu-satunya aturan wajib. Pembacaan itu tidak sesuai dengan target generalisasi:
- Sesi yang sama berbagi kondisi yang memengaruhi R dan label: pencahayaan dan kamera ruangan, jadwal, pengawas, versi config, dan pada data uji coba terencana juga **skenario perilaku** yang sama.
- Bila sesi yang sama ada di kedua split, metrik test mengukur kinerja pada sesi yang **sudah dilihat** saat fitting. Hasilnya cenderung terlalu optimistis untuk sesi baru.

**Mengapa tetap per peserta juga.** Kebiasaan, perangkat, dan wajah seorang peserta berulang lintas sesi. Peserta yang sama di kedua split membocorkan pola individu.

**Aturan revisi 2:**
- Calibration split dan test split harus terpisah **per peserta dan per sesi ujian sekaligus**. Pelanggaran salah satu → berhenti.
- Peserta yang mengikuti sesi di kedua sisi harus ditempatkan seluruhnya di satu split oleh penyusun data. Konsekuensinya, sebagian sesi peserta itu tidak dapat dipakai. Skrip tidak memindahkan atau membuang baris sendiri; skrip hanya menolak data yang melanggar.

**Konsekuensi praktis.**
- Diperlukan cukup banyak sesi ujian yang berbeda agar kedua split memenuhi K5. Jumlah sesi ujian per split dilaporkan.
- Pelonggaran aturan ini, misalnya bila data terlalu sedikit, **bukan** opsi skrip. Pelonggaran memerlukan keputusan pemilik proyek dan perubahan kode yang disetujui.

### 2.7 Definisi metrik

| Metrik | Definisi |
|---|---|
| Brier | (1/n) Σ (p − y)² |
| Brier skill score | 1 − Brier / Brier_baseline, dengan baseline p = prevalensi set kalibrasi |
| Log loss | −(1/n) Σ [y ln p + (1−y) ln(1−p)], p dibatasi ke [1e-15, 1−1e-15] |
| ECE | Σ_bin (n_bin/n) · \|rata-rata p − rata-rata y\|, dengan bin kuantil berjumlah sama; jumlah bin = min(10, n/20) |
| Slope kalibrasi | β₁ dari regresi logistik y ~ β₀ + β₁ · logit(p) (ideal 1) |
| Intercept kalibrasi (calibration-in-the-large) | α dari regresi logistik y ~ α + offset(logit(p)), dengan slope dikunci 1 (ideal 0). Didefinisikan begini agar intercept tidak bergantung pada slope dan mudah ditafsirkan. |
| AUROC, average precision | `eval_stats.roc_auc`, `eval_stats.average_precision`, dihitung pada p. Karena a > 0, urutannya sama dengan R. |

logit(p) dihitung dari p yang dibatasi ke [1e-15, 1−1e-15].

**Bootstrap (C4), sama untuk semua metrik:**
- B = 2.000 ulangan;
- seed tetap, dicatat di laporan;
- persentil 2,5 % dan 97,5 %;
- yang diambil ulang adalah **peserta** dengan pengembalian, dan semua sesi peserta terpilih ikut;
- setiap metrik dan setiap kriteria dihitung ulang pada setiap ulangan.

### 2.8 Keberhasilan teknis berbeda dari kelayakan hasil evaluasi

**Keberhasilan teknis** berarti langkah 1–6 di §2.6 lolos: data sah, tanpa kebocoran, jumlah minimum terpenuhi, fit konvergen dengan a > 0. Ini **tidak** berarti kalibrator layak dipakai.

**Pelaporan setiap metrik test** (Brier, Brier skill score, log loss, ECE, slope, intercept, AUROC, average precision):

| Isi | Keterangan |
|---|---|
| Nilai titik | Dihitung pada seluruh test split |
| Selang kepercayaan 95 % | Bootstrap persentil dengan **resampling peserta** (semua sesi seorang peserta ikut terambil bersama), bukan resampling sesi secara independen; jumlah ulangan dan seed dicatat |
| Lebar selang | Batas atas − batas bawah |
| Jumlah efektif | Jumlah peserta dan sesi di test split, serta positif/negatif, setelah penyaringan |

Ulangan bootstrap yang tidak menghasilkan nilai untuk suatu metrik (misalnya hanya satu kelas, atau regresi slope tidak konvergen) dihitung dan dilaporkan per metrik, bukan dibuang diam-diam.

**Putusan evaluasi (C4):**

`memadai` hanya bila **semua** syarat berikut terpenuhi. Ini kriteria aktivasi rencana §4.4, diterima sebagai kriteria minimum awal (K5). Semua syarat memakai nilai titik dari seluruh test split dan selang 95 % dari bootstrap peserta yang sama:

| # | Syarat | Rumus |
|---|---|---|
| E1 | Slope kalibrasi | 0,8 ≤ nilai titik ≤ 1,2 **dan** batas bawah selang ≤ 1 ≤ batas atas |
| E2 | Intercept kalibrasi | batas bawah selang ≤ 0 ≤ batas atas |
| E3 | Brier skill score | batas bawah selang > 0 |
| E4 | AUROC | batas bawah selang > 0,5 |
| E5 | Jumlah efektif test split | ≥ 100 positif dan ≥ 100 negatif (K5), dilaporkan bersama jumlah peserta dan jumlah sesi ujian |
| E6 | Ketidakpastian dapat diperkirakan | Untuk metrik E1–E4, ulangan bootstrap tanpa nilai ≤ 5 % dari B. Bila lebih, selang dianggap tidak dapat diandalkan dan syaratnya gagal. |

E6 berasal dari klarifikasi C4, yang disetujui pemilik proyek (revisi 2).

Laporan menampilkan setiap syarat dengan nilainya, hasilnya (lolos atau gagal), lebar selang, dan jumlah peserta efektif.

Bila satu saja tidak terpenuhi, putusannya `belum_memadai`. Laporan lalu:
- menyatakan **"hasil belum memadai; kalibrator tidak boleh diaktifkan"**;
- menyebut syarat yang gagal;
- tidak menulis berkas kalibrator.

Selang yang sangat lebar biasanya membuat syarat di atas gagal dengan sendirinya. Lebar selang tetap dilaporkan agar pemilik proyek dapat menilai apakah data perlu ditambah.

**Larangan klaim:**
- Laporan tidak boleh menyatakan bahwa kalibrator "meningkatkan" kualitas probabilitas, kecuali didukung hasil test: batas bawah selang Brier skill score > 0.
- Kalimat kesimpulan dibangkitkan dari putusan dan angka, bukan teks tetap.
- Pada data buatan (tes), laporan menyebut dengan jelas bahwa datanya buatan.

**Aktivasi** tetap keputusan terpisah pemilik proyek, walaupun putusannya `memadai`.

### 2.9 Jaminan bila kelayakan gagal (C3)

Kegagalan kelayakan ada dua jenis: berkas atau putusan evaluasi tidak sah, atau syarat per peserta di §2.3 tidak terpenuhi. Dalam kedua kasus:

| Jaminan | Cara |
|---|---|
| Kalibrator tidak aktif | `calibration.load` menolak berkas yang tidak sah, berputusan bukan `memadai`, atau putusannya tidak cocok dengan hitungan ulang. Tidak ada jalur lain untuk mengaktifkan kalibrator; tidak ada fallback ke "kalibrator terakhir" atau nilai bawaan a/b. |
| Tidak ada probabilitas | Untuk peserta yang gagal syarat, fungsi probabilitas **tidak dipanggil**. `calibrated_probability` = `NULL` dan status `not_calibrated`, dijaga juga oleh CHECK database. Probabilitas tidak muncul di live (T3-2), log, API, atau snapshot. |
| Hasil sesi tidak berubah | R, P_i, cakupan, interval, `excluded`, D4, dan baris/kolom snapshot sama persis dengan keadaan tanpa kalibrator. Satu-satunya tambahan adalah `calibration_reasons` di metadata JSON baris `*`. |
| Snapshot yang sudah final tidak disentuh | Snapshot final tidak pernah dihitung ulang (Phase 4). Kalibrator yang muncul, berubah, atau hilang kemudian tidak mengubah sesi yang sudah difinalisasi, termasuk statusnya. |
| Finalisasi tetap berjalan | Berkas rusak tidak menggagalkan finalisasi (K6); yang dicatat hanya alasan dan peringatan |
| Skrip | Kegagalan teknis atau `belum_memadai` → tidak ada berkas kalibrator yang ditulis; kode keluar bukan sukses |

### 2.10 Ketertelusuran artefak dan perlindungan putusan (revisi 3)

#### 2.10.1 Pencatatan test split yang sudah dipakai

| Unsur | Rancangan |
|---|---|
| Sidik test split | SHA-256 atas baris test split yang dinormalisasi: kolom tetap, urutan `exam_id`, `student_id`, angka dalam presisi penuh. Sidik yang sama berarti data yang sama, terlepas dari urutan baris di berkas CSV. |
| Registri | Berkas JSON Lines **append-only**, wajib diberikan ke skrip (`--registry <berkas>`); tanpa registri, skrip menolak berjalan. Satu baris per evaluasi: waktu, `test_split_sha256`, `calibration_split_sha256`, `dataset_sha256`, `criteria_version`/`criteria_sha256`, `script_sha256`, putusan, syarat yang gagal, dan sidik baris sebelumnya. Sidik berantai ini membuat penghapusan atau penyuntingan baris lama terdeteksi. |
| Pemeriksaan | Sebelum evaluasi, skrip membaca registri dan memeriksa rantai sidiknya. Rantai rusak → skrip berhenti. `test_split_sha256` sudah ada di registri → evaluasi tetap boleh dijalankan untuk informasi, tetapi putusan dipaksa `belum_memadai` dengan alasan "test split sudah pernah dipakai", dan berkas kalibrator tidak ditulis. |
| Penyimpanan | Registri disimpan bersama artefak kalibrasi, di luar database aplikasi. Tidak ada tabel baru dan tidak ada migrasi. Lokasi tetapnya ditetapkan di dokumen kebutuhan dataset (Tahap 4). |
| Keterkaitan | Baris registri yang menghasilkan sebuah berkas kalibrator dirujuk di `lineage.registry_entry`, dan sidik registri pada saat itu tercatat di laporan. |
| Batasan (D-R10) | Registri berupa berkas. Orang dengan akses tulis dapat mengganti seluruh registri atau memakai registri baru. Rantai sidik hanya mendeteksi perubahan pada registri yang sama. Karena itu, persetujuan aktivasi (§2.10.3) wajib memeriksa registri dan laporan, bukan hanya berkas kalibrator. |

#### 2.10.2 Keterkaitan artefak kalibrator

Setiap berkas kalibrator, dan laporan pasangannya, memuat bagian `lineage`:

| Kunci | Menghubungkan ke |
|---|---|
| `criteria_version`, `criteria_sha256` | Versi dan isi kriteria evaluasi (E1–E6, K2, K5) yang dipakai. `calibration.load` menolak versi kriteria yang berbeda dari kode yang berjalan. |
| `script_sha256` | Kode skrip pelatihan yang menghasilkan berkas |
| `dataset_sha256`, `calibration_split_sha256`, `test_split_sha256` | Data masukan dan kedua split |
| `algo_version`, `weights_fingerprint`, `config_version` | Rumus Session Summary dan bobot yang menghasilkan R (sudah diperiksa saat penerapan) |
| `models_fingerprint` | Model AI yang menghasilkan data: SHA-256 atas nama dan isi berkas model (face detector, landmarker, object detector, CLIP, YAMNet). Selalu dicatat, dan diperiksa saat penerapan (C7, §2.10.4). |
| `bootstrap` | B dan seed, supaya selang dapat direproduksi |
| `report_sha256`, `registry_entry` | Laporan evaluasi dan baris registri |

Dataset masukan (format ruang lingkup §2.2) ditambah kolom `models_fingerprint` dan `config_version` per baris. Baris dengan nilai yang berbeda dari target berkas dikeluarkan dan dihitung (langkah 2 §2.6).

#### 2.10.3 Pengikatan SHA-256 artefak kalibrator (C6, disetujui)

**Masalahnya:** `evaluation_verdict`, `metrics_test`, dan `lineage` semuanya tertulis di berkas JSON. Hitung ulang putusan (§2.2) mendeteksi berkas yang tidak konsisten, tetapi tidak mendeteksi berkas yang metrik **dan** putusannya disunting bersamaan.

**Rancangan, sesuai ketentuan C6:**
1. **Sidik dari artefak final yang disetujui.** SHA-256 dihitung atas byte persis berkas kalibrator final yang dievaluasi dan disetujui pemilik proyek. Skrip mencetak sidik ini di laporan untuk keperluan persetujuan.
2. **Setting sidik terpisah dari artefak.** Sidik disimpan di setting server tersendiri (mis. `EDUAI_SESSION_CALIBRATOR_SHA256`), tidak di dalam berkas kalibrator dan tidak di folder yang sama sebagai berkas pendamping. Lokasi berkas ada di setting T3-1. Kedua setting kosong secara bawaan; `.env` tidak diubah dalam Tahap 3.
3. **Setting sidik kosong → tidak disetujui.** Bila lokasi berkas terisi tetapi setting sidik kosong, berkas **tidak dianggap disetujui** dan ditolak (`invalid_calibrator`, rincian "belum ada sidik persetujuan").
4. **Sidik tidak cocok → ditolak.** `calibration.load` menghitung SHA-256 berkas yang ada di lokasi dan membandingkannya dengan setting, **sebelum** isi berkas dibaca. Bila berbeda, berkas ditolak (`invalid_calibrator`, rincian "sidik berkas tidak cocok dengan persetujuan"). Penyuntingan satu byte saja mengubah sidik.
5. Sesudah sidik cocok, baru pemeriksaan isi berjalan: validasi §2.2, hitung ulang putusan, dan versi kriteria. Semuanya pemeriksaan konsistensi tambahan.
6. **Dicatat di finalization snapshot.** Sidik yang disetujui disimpan di metadata JSON baris `*` (`calibration_approved_sha256`) bersama `calibration_version`. Ini dilakukan setiap kali setting sidik terisi, termasuk bila hasilnya `not_calibrated`. Setiap probabilitas dapat ditelusuri ke berkas yang persis disetujui.

Bila ditolak, perilakunya sama dengan §2.9: `not_calibrated`, tanpa probabilitas, hasil sesi tidak berubah, finalisasi tetap berjalan (K6).

**Batasan (dicatat sebagai risiko D-R11):** orang yang dapat mengubah setting server **dan** berkas sekaligus dapat melewati perlindungan ini. Melindungi dari administrator server memerlukan tanda tangan kriptografis dan pengelolaan kunci, yang di luar lingkup ini.

**Kode alasan:** tidak ada kode baru untuk C6. Penolakan memakai `invalid_calibrator` dengan rinciannya.

#### 2.10.4 Pemeriksaan model AI saat penerapan (C7, disetujui)

**Sidik model saat ini.**
- Saat backend memuat model, backend menghitung `models_fingerprint` dengan algoritme yang **sama** dengan yang dipakai di `lineage`: SHA-256 atas kunci model, nama berkas, dan isi berkas setiap model yang aktif (face detector, landmarker, object detector, CLIP, YAMNet). Algoritmenya didefinisikan sekali di modul bersama.
- Bila status AI bukan `READY`, sidik dianggap kosong.

**Penerapan.**
- Saat kalibrasi dievaluasi untuk seorang peserta, `models_fingerprint` saat ini dibandingkan dengan `lineage.models_fingerprint` di berkas kalibrator.
- Bila berbeda, atau sidik saat ini kosong, kode alasannya `models_mismatch`.

**Sidik kosong tidak pernah lolos.** Sidik model yang tidak tersedia tidak dianggap cocok dengan apa pun, termasuk dengan sidik kosong lain. Ini berlaku pada kondisi berikut:

| Kondisi | Hasil |
|---|---|
| AI belum `READY` (sedang memuat, gagal, dinonaktifkan) | `models_mismatch` |
| Berkas model tidak dapat dibaca saat menghitung sidik | sidik kosong → `models_mismatch` |
| `lineage.models_fingerprint` kosong atau tidak ada di berkas | berkas ditolak (`invalid_calibrator`, §2.2) |

Perbandingannya: kedua sidik **harus tidak kosong dan identik**. Tidak ada jalur yang mengaktifkan kalibrator tanpa verifikasi model.

**Bila tidak cocok (ketentuan C7):**
- kalibrator **tidak diaktifkan** untuk penerapan itu, tanpa fallback ke kalibrator lain;
- backend berperilaku **seperti tanpa kalibrator** menurut kontrak Phase 4: `not_calibrated`, probabilitas `null`, dan semua skor, cakupan, serta snapshot sama persis;
- hasil sesi yang **sudah difinalisasi tidak diubah**, karena snapshot final tidak pernah dihitung ulang.

**Pencatatan.** Sidik model backend saat finalisasi disimpan di metadata JSON baris `*` (`models_fingerprint`), sehingga dataset kalibrasi kelak dapat dibangun dari snapshot dengan sidik yang tepat. Tidak ada kolom baru.

**Batasan (D-R12, diterima sebagai keterbatasan rancangan Tahap 3).**
- Yang dibandingkan hanya model yang dimuat **backend**.
- Sidik backend **tidak menjamin** bahwa model worker OpenVidu sama. Sesi yang dianalisis worker memakai berkas model worker, dan sidiknya tidak dilaporkan ke backend.
- Lolosnya pemeriksaan C7 hanya berarti model backend cocok dengan artefak. Untuk sesi sumber `livekit`, pemeriksaan ini tidak membuktikan apa pun tentang model worker.
- Melaporkan sidik model worker memerlukan perubahan pesan worker, yang **tidak termasuk** lingkup implementasi yang disetujui saat ini.

## 3. Yang tidak berubah

Rincian lengkap ada di ruang lingkup §6:
- rumus dan nilai Phase 4;
- struktur dan mekanisme snapshot (hanya kolom kalibrasi yang sudah ada dan metadata JSON terisi);
- data D4;
- `algo_version`;
- skema database, migrasi, `.env`, dan `config.yaml`;
- data historis.

K7 tidak disentuh: status D4 hanya menentukan **kelayakan** kalibrasi, tidak pernah nilai.

## 4. Pemetaan tes

Tes 1–17 di ruang lingkup §7 memeriksa rancangan ini sebagai berikut:

| Bagian rancangan | Tes |
|---|---|
| §2.2 validasi berkas | 1, 2 |
| §2.3 alasan dan kelayakan | 3, 4, 5, 6 |
| §2.4 penyimpanan dan beku | 6, 7, 9, 10 |
| §2.5 skor dan ALERT tidak berubah | 8, ditambah pemeriksaan bahwa status ALERT (`cases`) sama dengan dan tanpa kalibrator |
| §2.6 skrip | 11, 13, 14, 15, 16. Ditambah: N₊/N₋ hanya dari calibration split (mengubah label test split tidak mengubah a dan b); test split tidak memengaruhi fit. |
| §2.7 metrik | 12 |
| §2.8 putusan evaluasi | Fit berhasil tetapi syarat §2.8 gagal → `belum_memadai`, kode keluar bukan sukses, tanpa berkas, laporan menyebut syarat yang gagal tanpa klaim "meningkatkan". Laporan memuat nilai titik, selang 95 %, lebar selang, serta jumlah peserta dan sesi. Bootstrap me-resample peserta. Berkas dengan `evaluation_verdict` selain `memadai` ditolak `calibration.load`. |
| §2.6.1 pemisahan (C1) | Overlap `student_id` → berhenti; overlap `exam_id` → berhenti; data yang terpisah pada keduanya → lanjut. Jumlah sesi ujian per split dilaporkan. |
| §2.6 langkah 6 (C2) | Kriteria tidak dapat diubah lewat argumen. Sidik test split dan kriteria tercatat. Evaluasi ulang pada test split yang sama tidak menghasilkan `memadai`. |
| §2.8 E1–E6 (C4) | Setiap syarat diuji pada batasnya: slope 0,8 dan 1,2, selang yang tepat menyentuh 1 atau 0, batas bawah Brier skill score dan AUROC tepat di ambang. Intercept memakai offset logit(p). Ulangan tanpa nilai > 5 % → gagal (E6). |
| §2.9 jaminan (C3) | Untuk setiap jenis kegagalan, fungsi probabilitas tidak dipanggil (dipastikan dengan penghitung panggilan di tes). Snapshot sama baris per baris dengan keadaan tanpa kalibrator, kecuali `calibration_reasons`. Snapshot yang sudah final tidak berubah setelah berkas kalibrator ditambah, diganti, atau dihapus. |
| §2.10.1 registri (revisi 3) | Tanpa `--registry` → skrip menolak berjalan. Rantai sidik rusak (baris dihapus atau disunting) → berhenti. Test split yang sama (urutan baris berbeda) → terdeteksi; putusan dipaksa `belum_memadai`; tanpa berkas. |
| §2.10.2 lineage | Berkas berisi semua kunci `lineage`. `criteria_version` berbeda dari kode → ditolak. Sidik di `lineage` sama dengan sidik data, skrip, dan laporan yang sebenarnya. |
| §2.10.3 pengikatan sidik (C6) | Lokasi terisi tetapi setting sidik kosong → ditolak ("belum ada sidik persetujuan"). Sidik cocok → diterima. Satu byte disunting (termasuk metrik dan putusan yang diubah bersamaan) → ditolak sebelum isi dibaca. Sidik di dalam berkas atau berkas pendamping diabaikan. Sidik yang disetujui terbekukan di snapshot, juga bila hasilnya `not_calibrated`. |
| §2.10.4 pemeriksaan model (C7) | Sidik model sama → lolos syarat ini. Sidik berbeda → `models_mismatch`, `not_calibrated`, fungsi probabilitas tidak dipanggil, snapshot identik dengan keadaan tanpa kalibrator. Status AI bukan `READY` → `models_mismatch`. Sidik backend kosong dan `lineage` kosong tidak dianggap cocok (`lineage` kosong → `invalid_calibrator`). Berkas model tidak terbaca → `models_mismatch`. Snapshot yang sudah final tidak berubah setelah model diganti. Skrip dan backend menghasilkan sidik yang sama untuk berkas model yang sama. |
| §2.2 putusan dan cakupan (C5) | Berkas dengan `evaluation_verdict: "memadai"` yang disunting tetapi metriknya tidak memenuhi kriteria → ditolak. Cakupan tepat 0,5 lolos, 0,4999… gagal. Ambang audio hanya diperiksa bila `weights_used` memuat indikasi suara. Indikasi suara di `weights_used` dengan `audio_coverage` kosong → gagal. |
| Regresi dan data produksi | 17 |

## 5. Keputusan yang diperlukan

**Untuk Tahap 3** (dari ruang lingkup, ditambah satu):

| ID | Keputusan | Usulan | Status |
|---|---|---|---|
| T3-1 | Lokasi berkas kalibrator | Setting baru, bawaan kosong; `.env` tidak diubah | **Disetujui** |
| T3-2 | Probabilitas di hasil live | Tidak; hanya di snapshot final | **Disetujui** |
| T3-3 | Ambang cakupan audio | `min_audio_coverage` di berkas, 50 % | **Disetujui dengan ketentuan:** hanya syarat kelayakan kalibrasi, memakai definisi cakupan Phase 4, hanya bila indikasi suara termasuk dalam sesi (§2.2) |
| T3-4 | Implementasi fit dan metrik | Pustaka standar Python, tanpa dependensi baru | **Disetujui** |
| T3-5 | Kode alasan | Ruang lingkup §3.2 | **Disetujui**; **direvisi oleh C7**: ditambah `models_mismatch`. Daftar final ada di §5.1. |
| T3-6 | Target Platt dihaluskan | Positif (N₊ + 1)/(N₊ + 2), negatif 1/(N₋ + 2) | **Disetujui dengan ketentuan:** N₊ dan N₋ hanya dari calibration split (§2.6 langkah 5) |

Persetujuan di atas adalah persetujuan **rancangan**. Implementasi Tahap 3 menunggu evaluasi dokumen final dan persetujuan terpisah.

**Klarifikasi revisi 2:**

| ID | Klarifikasi | Isi | Status |
|---|---|---|---|
| C1 | Overlap sesi ujian antar-split | **Berhenti** (bukan peringatan); split terpisah per peserta dan per sesi ujian (§2.6.1) | **Disetujui** (rancangan) |
| C2 | Isolasi test split | Kriteria sebagai konstanta kode; sidik test split dan kriteria di laporan; test split hanya untuk evaluasi final dan tidak dipakai ulang untuk putusan baru (§2.6 langkah 6, §2.10.1) | **Disetujui** (rancangan) |
| C3 | Jaminan bila kelayakan gagal | Tidak mengaktifkan kalibrator, tidak menghasilkan probabilitas, tidak mengubah hasil sesi (§2.9) | **Disetujui** (rancangan) |
| C4 | Konsistensi kriteria | Intercept = calibration-in-the-large; bootstrap peserta B = 2.000 dengan seed tetap; syarat E1–E6 (§2.7, §2.8) | **Disetujui** (rancangan) |
| C5 | Putusan dan ambang audio | Putusan dihitung ulang oleh `calibration.load`; kriteria di satu modul bersama; definisi cakupan Phase 4 apa adanya (§2.2) | **Disetujui** (rancangan) |

**Keputusan tambahan revisi 4:**

| ID | Keputusan | Isi | Status |
|---|---|---|---|
| C6 | Pengikatan SHA-256 artefak kalibrator | Sidik dihitung dari artefak final yang disetujui. Setting sidik terpisah dari artefak. Sidik tidak cocok → ditolak. Setting kosong → tidak dianggap disetujui. Sidik yang disetujui dicatat di finalization snapshot. Risiko administrator tetap dicatat (D-R11). (§2.10.3) | **Disetujui** (rancangan) |
| C7 | Pemeriksaan model AI saat penerapan | Sidik model backend dibandingkan dengan `lineage.models_fingerprint`. Bila tidak cocok: kode `models_mismatch`, kalibrator tidak diaktifkan, perilaku tanpa kalibrator menurut kontrak Phase 4, hasil yang sudah final tidak diubah. Ini revisi desain terhadap T3-5. (§2.10.4) | **Disetujui** (rancangan) |

Persetujuan T3-1 sampai T3-6 dan C1–C7 adalah persetujuan **rancangan**, bukan persetujuan implementasi.

### 5.1 Daftar final kode alasan `not_calibrated` (T3-5, direvisi oleh C7)

| Kode | Syarat yang gagal | Sumber |
|---|---|---|
| `no_calibrator` | Tidak ada berkas kalibrator (lokasi kosong atau tidak ada); keadaan produksi | T3-5 |
| `invalid_calibrator` | Berkas rusak atau tidak sah; putusan bukan `memadai` atau tidak cocok dengan hitungan ulang; versi kriteria berbeda; setting sidik kosong; sidik berkas tidak cocok (C6). Rincian dicatat. | T3-5, C5, C6 |
| `algo_version_mismatch` | Versi algoritme Session Summary berbeda | T3-5 |
| `weights_mismatch` | Sidik bobot berbeda | T3-5 |
| `indicator_set_mismatch` | Himpunan indikasi peserta tidak cocok dengan berkas mana pun | T3-5 |
| `coverage_below_threshold` | Cakupan video, atau cakupan audio bila indikasi suara dipakai, di bawah ambang; termasuk 0 % | T3-5, T3-3 |
| `model_unavailable` | Status D4 `model_unavailable` | T3-5 |
| `model_availability_not_recorded` | Status D4 `tidak_tercatat` | T3-5 |
| `no_score` | R kosong | T3-5 |
| **`models_mismatch`** | Sidik model AI backend saat ini berbeda dari `lineage.models_fingerprint`, atau tidak tersedia | **C7 (baru)** |

Daftar ini adalah **acuan**. Ruang lingkup §3.2 sudah diperbarui agar identik dengan daftar ini, sehingga tidak ada dua daftar yang berbeda. Semua alasan yang berlaku dicatat sekaligus. Tidak ada kode lain yang dipakai tanpa revisi desain yang disetujui.

**Untuk sebelum Phase 6** (bukan Tahap 3; dicatat agar arsitektur akhir tercapai):

| ID | Keputusan | Catatan |
|---|---|---|
| G1 | **Session Indication Alert** per indikasi (P_k ≥ T_k) masuk Session Summary dan snapshot; status Live Rule Alert dicatat sebagai field keterangan terpisah | Arti disesuaikan dengan P1-5 = S1 (21 November 2026). Implementasi masih terbuka: menunggu AL-2, AL-4, AL-5, nilai T_k (sumber AL-3 = C). |
| G2 | Jumlah **Session Indication Alert** di Overall Session Summary | Turunan dari G1; berbeda dari `rules_met` (Live Rule Alert) dan diberi label berbeda |
| G3 | Cakupan per indikasi | Diturunkan dari cakupan video/audio; tanpa mengubah perhitungan |
| G4 | T_k (nilai, versi, asal kebijakan/tervalidasi) dan threshold Live Rule Alert (`min_count`, `window_s`) dibekukan di snapshot | Menambah isi metadata snapshot; masih terbuka (AL-5) |
| K7 | Perlakuan nilai indikasi terdampak D4 | Tetap terbuka |

## 6. Risiko rancangan

| ID | Risiko | Mitigasi |
|---|---|---|
| D-R1 | Probabilitas dibaca sebagai probabilitas kecurangan | Makna dari K1 dicatat di berkas dan laporan; istilah Indication Score (%) sampai aktif |
| D-R2 | Kalibrator dipakai untuk sesi yang berbeda sifatnya (dataset shift) | Kunci kompatibilitas: versi, sidik bobot, himpunan indikasi, ambang cakupan, D4 `lengkap` |
| D-R3 | Data kecil menghasilkan a dan b tidak stabil | Jumlah minimum K5, target dihaluskan (T3-6), selang kepercayaan dilaporkan; jumlah minimum bukan jaminan |
| D-R4 | Sesi lama selalu `not_calibrated` | Disengaja: tanpa catatan D4 (`tidak_tercatat`), tanpa backfill |
| D-R5 | Berkas kalibrator rusak di lokasi aktif | K6: finalisasi tetap berjalan, alasan tercatat, peringatan di log |
| D-R6 | Kalibrasi tertukar dengan ALERT | Kalibrasi tidak membaca, mengubah, atau menggantikan Live Rule Alert maupun Session Indication Alert (P1-5 = S1); tes memeriksa Live Rule Alert tidak berubah |
| D-R7 | Fit yang berhasil dianggap layak | §2.8: putusan evaluasi terpisah, berkas hanya untuk `memadai`, `calibration.load` menolak berkas lain, aktivasi tetap keputusan terpisah |
| D-R8 | Informasi test split bocor ke fitting | Fit, target Platt, dan baseline hanya dari calibration split; split ditetapkan sebelumnya; ambang dikunci sebelum evaluasi |
| D-R9 | Pemisahan ganda (peserta dan sesi ujian) membuat data cepat habis | Konsekuensi yang disengaja dari C1. Jumlah sesi ujian dan peserta per split dilaporkan. Kebutuhan jumlah sesi ujian dibahas di dokumen kebutuhan dataset (Tahap 4). Pelonggaran hanya lewat keputusan pemilik proyek. |
| D-R10 | Test split dipakai berulang sampai "lolos" | Aturan konsumsi test split, registri append-only dengan rantai sidik (§2.10.1), sidik test split di laporan dan `lineage`, kriteria sebagai konstanta kode (C2). Ini mengurangi risiko tetapi tidak dapat mencegah penyalahgunaan sepenuhnya: registri dapat diganti utuh oleh orang yang punya akses tulis. Persetujuan aktivasi wajib memeriksa registri dan laporan. **Risiko tetap terbuka.** |
| D-R11 | Isi berkas kalibrator (metrik dan putusan) disunting bersamaan sehingga lolos hitung ulang | Pengikatan SHA-256 artefak pada persetujuan (C6, disetujui, §2.10.3): sidik di setting terpisah, diperiksa sebelum isi dibaca, setting kosong = tidak disetujui, sidik dibekukan di snapshot. **Sisa risiko tetap terbuka:** administrator yang dapat mengubah setting dan berkas sekaligus tetap dapat melewatinya (tanda tangan kriptografis di luar lingkup). |
| D-R12 | Kalibrator dipakai dengan model AI yang berbeda dari model penghasil data | Pemeriksaan `models_fingerprint` saat penerapan (C7, disetujui, §2.10.4) dengan kode `models_mismatch`. Sidik kosong tidak pernah lolos. Sidik model dibekukan di snapshot. **Risiko tetap terbuka dan diterima sebagai keterbatasan rancangan Tahap 3:** yang dibandingkan hanya model backend. Sidik backend tidak menjamin kesesuaian model worker OpenVidu, sehingga sesi worker dengan berkas model berbeda tidak terdeteksi. Perubahan pesan worker tidak termasuk lingkup implementasi yang disetujui. |
