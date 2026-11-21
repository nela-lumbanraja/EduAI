# Session Report: Laporan Lanjutan Checkpoint 21 November 2026 dan Analisis Keputusan Turunan AL-3

Tanggal: 21 November 2026 · Status: **Laporan pemeriksaan dan analisis. Pembaruan 21 November 2026: AL-3c = G-c bertahap dan OS-1 = O1 diputuskan (lihat `EDUAI_SESSION_REPORT_AL3C_OS1_KB_ANALYSIS.md`), juga K-b = KB-1. AL-3a dan AL-3b tetap BELUM DISETUJUI. Belum ada implementasi.**

**Batas pekerjaan:**
- Tidak ada perubahan kode, konfigurasi runtime, `.env`, database, data, dataset, atau perilaku sistem, dan tidak ada commit.
- Phase 5 Tahap 4 dan Phase 6 belum dimulai.
- **Tidak ada nilai T_k yang ditetapkan.**
- Keputusan yang berlaku (P1-5 = S1, AL-3 = C, dan keputusan sebelumnya) tidak dievaluasi ulang.

---

## 1. Status checkpoint terbaru

| Hal | Status |
|---|---|
| Tahap terakhir selesai dan diterima | Phase 5 Tahap 3 (mekanisme kalibrasi), beserta evaluasi dokumentasi P1, Architecture Alignment, readiness check, dan langkah 1 |
| Keputusan terbaru | **P1-5 = S1**: Live Rule Alert dan Session Indication Alert dua mekanisme terpisah; Live Rule Alert tidak diubah. **AL-3 = C**: T_k awal dari kebijakan Program Studi yang terdokumentasi, lalu divalidasi dengan data berlabel per indikasi. |
| Nilai T_k | Belum ditetapkan |
| Terbuka | P1-4; AL-1; AL-2 (usulan tiga status belum disetujui); keputusan turunan AL-3; AL-4; AL-5; AL-6; K7 |
| Belum dimulai | Phase 5 Tahap 4, Phase 6 |
| Lain-lain | Migrasi database produksi belum disetujui. Commit terakhir `af628da`; pekerjaan sejak itu belum di-commit. |

## 2. Konsistensi keputusan dan dokumen

### 2.1 Dokumen yang diperiksa

- `EDUAI_SESSION_REPORT_P1_5_AL3_DECISION_ANALYSIS.md`
- `EDUAI_SESSION_REPORT_P1_4_P1_5_EVALUATION.md`
- `EDUAI_SESSION_REPORT_ARCHITECTURE_ALIGNMENT.md`
- `EDUAI_SESSION_REPORT_PHASE5_P1_EVALUATION.md`
- `EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md`
- `EDUAI_SESSION_REPORT_READINESS_CHECK.md`

Juga dibaca, tanpa diubah: `backend/app/calibration.py` (fungsi `weights_fingerprint`), untuk memeriksa dampak teknis pada AL-3a.

### 2.2 Ketidakkonsistenan yang ditemukan dan diperbaiki

Semuanya teks yang **bertentangan** dengan keputusan yang berlaku, bukan sekadar status yang usang:

| Dokumen | Bagian | Masalah | Perbaikan |
|---|---|---|---|
| TAHAP3_DESIGN | §1.3, baris A1, A2, A5 | G1, G2, dan G4 masih dalam arti lama (ALERT = aturan `cases`), bertentangan dengan §5 yang sudah disesuaikan dengan S1 | Disamakan dengan §5: G1 = Session Indication Alert ditambah field keterangan Live Rule Alert; G2 = jumlah Session Indication Alert; G4 = T_k dan threshold Live Rule Alert dibekukan |
| TAHAP3_DESIGN | §2.5 | "Status ALERT (aturan episode) tidak membaca…" menyamakan ALERT dengan Live Rule Alert | Menyebut kedua mekanisme |
| TAHAP3_DESIGN | §6, D-R6 | "ALERT tetap dari aturan episode" | Kalibrasi tidak menyentuh kedua mekanisme |
| TAHAP3_DESIGN | §2.8 | "E6 … menunggu konfirmasi", padahal C4 (termasuk E6) sudah disetujui | Dicatat sebagai bagian C4 yang disetujui |
| PHASE5_P1_EVALUATION | §13, butir 3 | "perbedaan definisi yang perlu diselaraskan" | Definisi diputuskan S1; implementasi terbuka |
| READINESS_CHECK | §4 | Arah AL-3 masih disebut penghalang Tahap 4; P1-5 dan AL-3 masih penghalang utuh Phase 6 | Arah AL-3 ditandai selesai. Penghalang Phase 6 kini hanya nilai dan turunan AL-3 beserta keputusan terbuka lain. |

### 2.3 Yang konsisten dan tidak diubah

- `P1_5_AL3_DECISION_ANALYSIS`, `P1_4_P1_5_EVALUATION`, dan `ARCHITECTURE_ALIGNMENT` sudah konsisten dengan S1 dan C.
- Rekomendasi lama P1-5a di `P1_4_P1_5_EVALUATION` §B.6 sudah ditandai **bukan rekomendasi aktif** (§B.7). Teksnya dibiarkan sebagai catatan evaluasi.

### 2.4 Konflik antara rancangan, Phase 4, dan Tahap 3 yang masih ada

| # | Konflik | Status |
|---|---|---|
| K-a | Aturan data kosong Phase 4 (interval tanpa data = 0; cakupan 0 % → skor 0 dengan catatan) vs syarat target bahwa status harus "Tidak tersedia" bila seluruh data indikasi tidak ada | Tercatat sebagai **AL-2** (terbuka). Rumus Phase 4 tidak diubah. |
| K-b | **Baru ditemukan, teknis.** `config_version` Phase 4 berbentuk `"<version>;w=<sidik bobot>"`, dan kode Tahap 3 (`calibration.weights_fingerprint`) mengambil **seluruh teks setelah `;` pertama** sebagai sidik bobot. Bila sidik T_k kelak ditambahkan ke `config_version` (mis. `;t=…`), pemeriksaan `weights_mismatch` akan selalu gagal untuk kalibrator yang sah. | Tidak berbahaya sekarang. Menjadi **batasan desain AL-3a** (§4.1): sidik T_k harus disimpan di field terpisah, atau parser diubah lewat perubahan kode yang disetujui. |
| K-c | **Klarifikasi (OS-1).** Instruksi terbaru menyebut Overall Session Summary menampilkan skor agregasi "dan statusnya berdasarkan mekanisme yang telah disepakati". Dokumen yang ada **tidak** mendefinisikan status keseluruhan sesi selain: jumlah Session Indication Alert (G2), status kalibrasi (`not_calibrated`/`calibrated`), dan `coverage_note`. R3 juga melarang P_total menggantikan ALERT per indikasi. | Perlu klarifikasi pemilik proyek (§3, OS-1). Tidak ada mekanisme status keseluruhan baru yang diasumsikan. |
| K-d | PDF sekarang dibangun dari data laporan, bukan snapshot | Target Phase 6 (AL-6); tercatat |

## 3. Keputusan yang masih terbuka

| ID | Isi | Status |
|---|---|---|
| P1-4 | Prioritas dataset V5 / V5+A3 dan turunannya (definisi Y untuk V5+A3, persetujuan audio penelitian, pengumpulan, penyimpanan, akses, penghapusan audio, pengukuran tingkat persetujuan) | Belum diputuskan |
| AL-1 | Skor per menit | Terbuka |
| AL-2 | Status Session Indication Alert saat data kosong atau sebagian; usulan tiga status belum disetujui | Terbuka |
| **AL-3a** | Lokasi dan sumber penyimpanan T_k | **Dianalisis di §4.1; belum disetujui** |
| **AL-3b** | Aturan validasi T_k | **Dianalisis di §4.2; belum disetujui** |
| **AL-3c** | Bentuk label dan kriteria evaluasi validasi T_k (jalur data) | **Diputuskan (21 November 2026)** untuk bentuk label: **G-c bertahap**. Kriteria evaluasi, pedoman, proporsi subsampel, dan kesepakatan antarpelabel dirancang di Tahap 4. |
| AL-4 | Status ketersediaan data per indikasi | Terbuka |
| AL-5 | Isi snapshot tambahan (G1–G4) | Terbuka |
| AL-6 | PDF dari snapshot | Terbuka (Phase 6) |
| K7 | Perlakuan nilai indikasi terdampak D4 | Terbuka |
| **OS-1** | Makna "status" Overall Session Summary (K-c) | **Diputuskan (21 November 2026)**: **O1**, tanpa status gabungan |

## 4. Analisis keputusan turunan AL-3 (belum disetujui)

Dasar yang berlaku:
- AL-3 = C;
- satu T_k per indikasi, karena P_k tidak bergantung pada `indicator_set`;
- skala T_k sama dengan P_k (0–1);
- **tidak ada nilai T_k yang diusulkan.**

### 4.1 AL-3a: lokasi dan sumber penyimpanan T_k

| Pilihan | Isi | Kelebihan | Kekurangan dan risiko |
|---|---|---|---|
| **L1: bagian baru `config.yaml`** (mis. `session_summary.indicator_thresholds`), dengan blok asal: `version`, `source` (`kebijakan`/`tervalidasi`), `approved_by`, `approved_at`, `reference` | Sama dengan pola bobot indikasi Phase 4. Dibaca saat backend start (T6). | Konsisten dengan bobot; mudah ditinjau; tanpa skema baru; tanpa setting baru | Siapa pun yang dapat menyunting config dapat mengubah T_k. Persetujuan hanya tercatat sebagai teks. Sidik **harus terpisah** dari `config_version` (K-b). |
| **L2: berkas threshold yang disetujui, dikunci SHA-256** lewat dua setting baru (lokasi dan sidik), seperti C6 | Persetujuan Program Studi terikat pada isi berkas yang persis | Perlindungan penyuntingan setara kalibrator; persetujuan eksplisit per versi | Dua setting baru dan prosedur aktivasi; risiko administrator tetap ada (seperti D-R11) |
| L3: tabel database dengan antarmuka admin | Disetel dari aplikasi | Jejak audit di aplikasi | Perubahan skema dan migrasi, antarmuka baru; di luar lingkup sekarang |
| L4: konstanta kode | Seperti kriteria kalibrasi (C2) | Perubahan hanya lewat rilis kode | Kebijakan Program Studi bergantung pada rilis kode; tidak cocok untuk ambang kebijakan yang direvisi berkala |

**Untuk semua pilihan:**
- sidik T_k (SHA-256 isi yang dinormalisasi) disimpan di **field snapshot terpisah**, mis. `thresholds_fingerprint` dan `thresholds_version`, bukan digabung ke `config_version` (K-b);
- T_k beserta asal, versi, dan sidiknya dibekukan di snapshot (AL-5);
- tanpa backfill.

**Rekomendasi AL-3a (belum disetujui):** **L1**, dengan blok asal wajib dan sidik terpisah. Alasannya:
- T_k awal adalah kebijakan Program Studi, seperti bobot indikasi yang juga sudah berada di `config.yaml`;
- satu pola untuk dua kebijakan memudahkan peninjauan.

Bila pemilik proyek menginginkan persetujuan yang terikat secara kriptografis seperti kalibrator, pilihan konsisten berikutnya adalah **L2**.

### 4.2 AL-3b: aturan validasi T_k

| Aturan | Pilihan | Rekomendasi (belum disetujui) | Alasan |
|---|---|---|---|
| Nama indikasi | Hanya indikasi yang dinilai (`SCORED`); nama lain ditolak | Ditolak | Sama dengan validasi bobot Phase 4 |
| Rentang nilai | [0, 1], atau (0, 1] | **0 < T_k ≤ 1** | T_k = 0 membuat setiap sesi ALERT (P_k ≥ 0 selalu benar). T_k > 1 tidak pernah tercapai. |
| Tipe | Angka berhingga, bukan boolean atau teks | Wajib | Sama dengan bobot |
| Blok asal | `version`, `source` ∈ {`kebijakan`, `tervalidasi`}, `approved_by`, `approved_at`, `reference` wajib; untuk `tervalidasi` juga sidik laporan evaluasi | Wajib | Ketertelusuran AL-3 = C |
| Indikasi tanpa T_k | V-a: seluruh set tidak sah · V-b: indikasi itu "Tidak tersedia" dengan alasan `threshold_missing` | **V-b** | Dengan C, Program Studi mungkin menetapkan T_k bertahap. Ketiadaan T_k jangan disamarkan sebagai NORMAL. |
| Set rusak (tipe, rentang, nama, atau blok asal salah) | F-a: finalisasi ditolak (seperti bobot tidak sah, Phase 4) · F-b: finalisasi berjalan; seluruh Session Indication Alert "Tidak tersedia" dengan alasan, plus peringatan di log dan status admin | **F-b** | Skor dan snapshot tetap sah tanpa T_k, karena T_k bukan masukan skor. Ini setara dengan K6 untuk kalibrator. Risiko konfigurasi rusak tidak tersadari dimitigasi lewat pemeriksaan saat start dan status admin. |
| Nilai bawaan | Tidak ada | Tidak ada nilai bawaan T_k | Berbeda dengan bobot (bawaan 1): tidak ada ambang netral yang bermakna |
| Hubungan dengan AL-2 | — | Validasi T_k tidak menentukan ketersediaan data; status data kosong tetap keputusan AL-2 | Menghindari mencampur dua keputusan |

Kode alasan baru seperti `threshold_missing` atau `thresholds_invalid` bukan bagian dari daftar alasan kalibrasi (§5.1 rancangan Tahap 3). Kode itu milik Session Indication Alert, dan daftarnya diputuskan bersama AL-2 dan AL-5.

### 4.3 AL-3c: kriteria evaluasi validasi T_k (jalur data dalam C)

| Unsur | Pilihan | Rekomendasi (belum disetujui) |
|---|---|---|
| **Label per indikasi** (memengaruhi Tahap 4) | G-a: biner per sesi per indikasi ("perilaku k terjadi secara bermakna dan perlu ditindaklanjuti") · G-b: durasi perilaku k per sesi (detik), dari anotasi rentang waktu · G-c: keduanya | **G-c bila beban pelabelan disetujui, minimal G-a.** G-a langsung mengevaluasi ALERT; G-b memungkinkan memeriksa P_k itu sendiri. Label dibuat tanpa melihat T_k atau P_k, dua pelabel dengan κ ≥ 0,6 (sama dengan K1). |
| Cara memakai data | M-a: **evaluasi T_k kebijakan apa adanya** pada test split · M-b: pilih T_k baru pada calibration split dengan aturan yang ditetapkan lebih dahulu, lalu evaluasi sekali pada test split | **M-a dahulu.** Bila lolos, status `tervalidasi`. Bila tidak, M-b boleh mengusulkan versi T_k baru, yang tetap memerlukan persetujuan Program Studi dan pemilik proyek. |
| Aturan pemilihan bila M-b | Youden J maksimum · sensitivitas minimum lalu spesifisitas maksimum · PPV minimum | Ditetapkan **sebelum** melihat test split. Usulan: sensitivitas minimum lalu spesifisitas maksimum, karena ALERT berfungsi sebagai penanda tinjauan. Nilai minimumnya keputusan pemilik proyek. |
| Pemisahan data | Ikut C1: per peserta dan per sesi ujian, lintas `indicator_set`. Satu penempatan split untuk seluruh dataset, dipakai bersama kalibrasi. | Satu penempatan split. Test split tidak dipakai untuk memilih T_k maupun kalibrator. Registri test split (§2.10.1 Tahap 3) mencatat evaluasi T_k juga. |
| Metrik | Sensitivitas, spesifisitas, PPV, NPV per indikasi, dengan selang 95 % bootstrap peserta (B = 2.000, seperti C4), jumlah efektif, dan lebar selang | Sama dengan pola Tahap 3 |
| Kriteria lolos | Mis. batas bawah selang sensitivitas ≥ s_min dan batas bawah spesifisitas ≥ p_min | Bentuknya diusulkan; **nilai s_min/p_min adalah keputusan pemilik proyek**, belum ditetapkan |
| Jumlah minimum per indikasi | Seperti K5, per indikasi | Diusulkan per indikasi. Perilaku jarang (mis. ponsel, buku) mungkin tidak mencapai minimum; indikasi itu tetap berstatus `kebijakan, belum divalidasi`, **tidak** dipaksa lolos. |
| Cakupan | Sesi dengan cakupan di bawah ambang dikecualikan dari evaluasi | Ikut K2 untuk sementara; aturan finalnya mengikuti AL-2 |
| Tanpa klaim | Laporan validasi tidak menyatakan T_k "akurat" tanpa dukungan batas bawah selang | Sama dengan larangan klaim §2.8 Tahap 3 |

## 5. Prasyarat sebelum Phase 5 Tahap 4

| # | Prasyarat | Status | Wajib sebelum mulai? |
|---|---|---|---|
| 1 | Persetujuan eksplisit memulai Tahap 4 | Belum ada | **Ya** |
| 2 | Arah AL-3 (sumber T_k) | **Selesai** (C) | — |
| 3 | Bentuk label per indikasi (AL-3c, G-a/G-b/G-c) | Belum diputuskan | **Disarankan ya**, karena menentukan isi protokol pelabelan Tahap 4. Alternatif: diajukan di dalam Tahap 4 sebagai keputusan. |
| 4 | P1-4 dan turunannya | Belum diputuskan | Tidak untuk mulai; **ya untuk menutup Tahap 4** |
| 5 | Pemisahan lintas `indicator_set` | Sudah diminta pemilik proyek (dokumen P1 §9) | — (menjadi isi Tahap 4) |
| 6 | AL-3a, AL-3b | Belum diputuskan | Tidak; keduanya keputusan runtime, diperlukan sebelum Phase 6 |
| 7 | AL-2 | Belum diputuskan | Tidak untuk mulai. Aturan inklusi data Tahap 4 sementara mengikuti K2. |
| 8 | OS-1 | Klarifikasi | Tidak untuk Tahap 4; diperlukan sebelum Phase 6 |
| 9 | Migrasi produksi, commit | Belum diputuskan | Tidak; jalur terpisah |

## 6. Rekomendasi langkah berikutnya

1. **Keputusan atau klarifikasi pemilik proyek atas:**
   - **AL-3c, bentuk label per indikasi** (G-a/G-b/G-c). Hanya bagian ini yang memengaruhi isi Tahap 4.
   - **OS-1:** apakah "status" Overall Session Summary berarti jumlah Session Indication Alert, status kalibrasi, dan catatan cakupan (yang sudah ada di rancangan), atau mekanisme status keseluruhan yang baru. Yang kedua memerlukan evaluasi tersendiri dan tidak boleh menggantikan ALERT per indikasi (R3).
2. Setelah itu, **persetujuan memulai Phase 5 Tahap 4**, ditulis:
   - per himpunan;
   - dengan pemisahan lintas himpunan;
   - dengan label tingkat sesi (K1) dan label per indikasi (AL-3c);
   - dengan P1-4 diajukan di dalamnya sebagai keputusan.
3. **AL-3a dan AL-3b** dapat diputuskan kapan saja sebelum Phase 6. Rekomendasinya: L1 dengan sidik terpisah, 0 < T_k ≤ 1, V-b, dan F-b. Semuanya belum disetujui.
4. Jalur terpisah: migrasi produksi dan commit, kapan pun pemilik proyek siap.

## 7. Konfirmasi

**Diperiksa:**
- enam dokumen di §2.1;
- `backend/app/calibration.py`, dibaca saja.

**Diubah (dokumentasi saja, karena bertentangan dengan keputusan yang berlaku):**
- `EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md`: 6 tempat (§1.3 A1, A2, A5; §2.5; §2.8; D-R6);
- `EDUAI_SESSION_REPORT_PHASE5_P1_EVALUATION.md`: §13 butir 3;
- `EDUAI_SESSION_REPORT_READINESS_CHECK.md`: §4, dua baris.

**Baru:** dokumen ini.

**Tidak diubah:**
- `P1_5_AL3_DECISION_ANALYSIS`, `P1_4_P1_5_EVALUATION`, `ARCHITECTURE_ALIGNMENT` (sudah konsisten);
- semua kode, konfigurasi runtime, `.env`, database, data, dataset, dan perilaku sistem.

Tidak ada commit, dan tidak ada nilai T_k yang ditetapkan.
