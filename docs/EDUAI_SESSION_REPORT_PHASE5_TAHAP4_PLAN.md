# Session Report Phase 5, Tahap 4: Rencana Kerja Evaluasi dan Perancangan Kebutuhan Dataset

Tanggal: 21 November 2026 · Status: **Tahap 4 DITUTUP sebagai tahap perancangan (21 November 2026, opsi a; H1, H2, H3 disetujui).** Parameter yang bergantung pada uji coba tetap "ditetapkan setelah uji coba". Lihat `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_RESULTS.md`. *Status awal: "Tahap 4 disetujui dimulai untuk evaluasi dan perancangan saja."*

**Batas pekerjaan:**
- Tidak ada perubahan kode, konfigurasi runtime, `.env`, database, data, atau dataset, dan tidak ada commit.
- Tidak ada perekaman, pengumpulan, atau pelabelan data.
- Tidak ada nilai T_k yang ditetapkan.
- Keputusan Phase 4 dan Live Rule Alert tidak diubah.
- Phase 6 tidak dimulai.

---

## 1. Tujuan Tahap 4

Menyusun **dokumen kebutuhan dataset dan protokol pelabelan** (keluaran L5 rencana Phase 5: `docs/SESSION_CALIBRATION_DATASET.md`). Dokumen ini harus cukup rinci agar pengumpulan data kelak, yang memerlukan persetujuan terpisah, dapat menghasilkan:
- data kalibrasi sesi (Tahap 3: label Y tingkat sesi, R = P_total);
- data validasi T_k (AL-3 = C, AL-3c = G-c bertahap);

dengan mematuhi semua keputusan yang berlaku.

## 2. Keputusan yang berlaku (masukan Tahap 4)

| Keputusan | Isi singkat |
|---|---|
| K1 | Y = 1 bila sesi memuat ≥ 1 perilaku teramati dari daftar indikasi; dua pelabel independen meninjau rekaman penuh; κ ≥ 0,6 sebagai ambang awal |
| K3 | Kalibrator per `indicator_set` (V5, V5+A3) |
| K5 | Minimum awal, bukan jaminan: kalibrasi ≥ 50/50, test ≥ 100/100 per kalibrator; test split dikunci |
| C1 | Split terpisah per peserta **dan** per sesi ujian |
| C2 | Test split sekali pakai; kriteria sebagai konstanta kode; registri test split |
| P1 (§9) | Pemisahan peserta dan sesi ujian **lintas `indicator_set`**; satu penempatan split untuk seluruh dataset |
| AL-3 = C | T_k awal dari kebijakan Program Studi, lalu divalidasi dengan data berlabel per indikasi |
| AL-3c = G-c bertahap | G-a untuk semua sesi berlabel; G-b pada subsampel terencana untuk membedakan masalah pengukuran P_k dari masalah ambang T_k |
| OS-1 = O1, K-b = KB-1 | Tidak berdampak langsung pada dataset. KB-1: dataset evaluasi T_k mencatat sidik T_k yang dievaluasi di field terpisah. |
| Protokol evaluasi yang ada | `docs/EVALUATION_PROTOCOL.md` (versi 0.1, usulan): pilot relawan, pelabelan rentang, etika |

## 3. Konflik dan prasyarat yang belum terpenuhi

Semua konflik ini ditemukan dengan membandingkan `EVALUATION_PROTOCOL.md` terhadap keputusan Phase 5. Tidak ada yang diselesaikan sepihak.

| # | Konflik | Rincian | Mengapa penting | Kapan perlu diputuskan |
|---|---|---|---|---|
| **TK-1** | **Prevalensi sesi skenario** | Protokol memakai **sesi skenario**: relawan diminta melakukan perilaku tertentu. Platt scaling (Tahap 3) mempelajari pemetaan R → probabilitas dengan **prevalensi Y di data latih**. | Bila data kalibrasi didominasi sesi skenario, prevalensi Y jauh lebih tinggi daripada di ujian sungguhan, sehingga probabilitas terkalibrasi akan **terlalu tinggi** saat diterapkan (dataset shift, terkait D-R2). Ini masalah metodologis inti, bukan sekadar teknis. | **Sebelum perancangan komposisi dataset** (WP4) |
| **TK-2** | **Ukuran sampel** | Protokol: ≥ 24 relawan, ≥ 30 **kejadian** positif per indikasi (evaluasi deteksi). K5: ≥ 150 **sesi** positif dan ≥ 150 sesi negatif **per kalibrator** (50 + 100 per kelas), dengan peserta dan sesi ujian terpisah. Dua kalibrator (V5, V5+A3) menggandakannya. | Ukuran pilot di protokol jauh di bawah K5. Kelayakan pengumpulan harus dinilai jujur. Bisa jadi kalibrator tidak dapat dibuat dalam waktu dekat, dan hal itu sah (K5 bukan jaminan, D-R3). | Sebelum Tahap 4 ditutup (WP6) |
| **TK-3** | **Aturan pemisahan berbeda** | Protokol §4: pemisahan per orang, sekitar 50/50. Phase 5 C1: per orang **dan** per sesi ujian (`exam_id`), lintas `indicator_set`. | Bila beberapa relawan berbagi satu `exam_id`, aturan protokol saja tidak cukup. Struktur `exam_id` untuk pilot harus dirancang agar C1 terpenuhi. | Sebelum Tahap 4 ditutup (WP5) |
| **TK-4** | **Urutan penyetelan ambang deteksi** | Protokol §4 mengizinkan penyetelan ambang `config.yaml` pada set kalibrasi, lalu pembekuan versi baru. Kalibrator sesi terikat pada `config_version`, sidik bobot, dan `models_fingerprint` (C7). | Bila ambang deteksi diubah setelah data sesi terkumpul, R berubah dan data sesi lama tidak lagi cocok dengan target kalibrator (`config_version_berbeda`). Urutannya harus ditetapkan: penyetelan deteksi dibekukan dulu, atau data sesi dikumpulkan dengan versi beku. | Sebelum Tahap 4 ditutup (WP3) |
| **TK-5** | **Ambang κ berbeda** | K1: κ ≥ 0,6 (label tingkat sesi). Protokol: κ ≥ 0,70 (segmen 1 detik, label rentang = G-b). G-a belum punya ambang. | Satuan berbeda, ambang berbeda. Rincian kesepakatan AL-3c wajib diselesaikan sebelum Tahap 4 ditutup (keputusan pemilik proyek). | Sebelum Tahap 4 ditutup (WP2) |
| **TK-6** | **Label K1 di luar subsampel G-b** | Dengan G-c bertahap, G-b hanya untuk subsampel, sehingga K1 **tidak dapat diturunkan** dari G-b untuk semua sesi. G-a ("bermakna") berbeda arti dengan K1 ("teramati"). | Setiap sesi berlabel butuh K1 dan G-a terpisah. Ada opsi menambahkan kolom "ada/tidak" per indikasi pada formulir G-a sehingga K1 = gabungan kehadiran. Opsi ini belum diputuskan. | Sebelum Tahap 4 ditutup (WP2) |
| **TK-7** | **Jalur pembuatan R untuk data pilot** | Untuk memperoleh R, P_k, cakupan, D4, dan `models_fingerprint`, sesi pilot harus berjalan di EduAI versi baru sampai finalisasi Session Summary. Ini butuh instans backend dengan tabel Phase 2 dan Tahap 2. | Tidak perlu migrasi database **produksi**: dapat memakai instans dan database pilot terpisah. Namun menjalankan instans itu adalah kegiatan operasional yang memerlukan persetujuan tersendiri, dan tidak termasuk Tahap 4. | Dicatat; persetujuan diperlukan sebelum pengumpulan data |
| **TK-8** | **Prasyarat etika dan pelindungan data** | Protokol §6: izin komite etik **wajib sebelum perekaman pertama**; persetujuan bertingkat (video, audio, data sensitif); persetujuan wali untuk peserta < 18 tahun; persetujuan pimpinan program studi; DPIA disarankan. Data lama (`dataset_raw/`, `pilot/p01.mp4`) asal persetujuannya tidak tercatat. | Tahap 4 boleh merancang. **Pengumpulan data tidak boleh dimulai** sebelum izin ini ada. Data lama tidak boleh dipakai sampai asal persetujuannya jelas. | Prasyarat pengumpulan data (di luar Tahap 4); dirinci di WP8 |
| **TK-9** | **Lokasi registri dan artefak** | Tahap 3 §2.10.1 menyerahkan lokasi tetap registri test split ke Tahap 4. Protokol melarang rekaman pilot masuk repositori. | Registri hanya berisi sidik, sehingga boleh di repositori atau di penyimpanan penelitian. Keputusan diperlukan. | Sebelum Tahap 4 ditutup (WP5) |
| **TK-10** | **Prevalensi Y menurut definisi K1** (ditemukan di WP4; dokumen H2 §2) | Daftar indikasi memuat perilaku yang juga terjadi pada ujian wajar. Bila "teramati" berarti "terjadi sekali", hampir semua sesi wajar menjadi Y = 1. | Probabilitas tidak informatif; E5 sulit dipenuhi; risiko satu kejadian umum dibaca sebagai bukti. **Mitigasi disetujui (H2-3):** "teramati" mengikuti definisi operasional per indikasi yang membedakan perilaku relevan dari aktivitas wajar; K1 tidak diubah. **Risiko sisa:** prevalensi tetap bergantung pada kualitas definisi operasional; diukur di uji coba kecil. | Mitigasi disetujui; definisi operasional final disusun di D2 |

**Prasyarat yang sudah terpenuhi untuk memulai perancangan:**
- persetujuan memulai Tahap 4;
- AL-3 = C, AL-3c = G-c bertahap;
- K1, K3, K5, C1, C2;
- pemisahan lintas `indicator_set`.

**Usulan:** TK-1 diputuskan arahnya **sebelum** WP4, karena memengaruhi seluruh rancangan komposisi dataset. Konflik lain diselesaikan di dalam paket kerja masing-masing.

## 4. Paket kerja

Semuanya dokumentasi dan evaluasi.

| WP | Isi | Konflik yang ditangani | Keluaran |
|---|---|---|---|
| **WP1** | Inventarisasi acuan: keputusan berlaku, format masukan skrip kalibrasi (Tahap 3, ruang lingkup §2.2), protokol evaluasi, alat yang ada (`label_agreement.py`, `evaluate.py`, `eval_stats.py`) | — | Bagian "acuan" di D1 |
| **WP2** | **Rancangan label:** K1 (tingkat sesi); G-a (pedoman "bermakna" per indikasi, formulir, opsi kolom kehadiran); G-b (pakai protokol rentang yang ada); penyelarasan ambang κ; adjudikasi; pelabel buta terhadap keluaran sistem, P_k, dan T_k | TK-5, TK-6 | D2 (rancangan pedoman), keputusan κ |
| **WP3** | **Urutan kerja dan versi beku:** penyetelan deteksi (protokol) → pembekuan `config.yaml`/model → pengumpulan data sesi dengan versi beku; kaitan dengan `config_version`, sidik bobot, `models_fingerprint` | TK-4 | Bagian urutan di D1 |
| **WP4** | **Komposisi dataset:** sesi wajar vs sesi skenario; dampak prevalensi pada Platt; pilihan penanganan (mis. kalibrasi hanya dari sesi wajar, penyesuaian prevalensi, atau pemisahan tujuan: sesi skenario untuk G-b/T_k, sesi wajar untuk kalibrasi). **Pilihan diajukan, tidak diputuskan.** | **TK-1** | Analisis keputusan TK-1 di D1 |
| **WP5** | **Pemisahan dan registri:** struktur `exam_id` pilot, penempatan split sekali untuk seluruh dataset (per peserta, per sesi ujian, lintas himpunan), pemeriksaan kebocoran, aturan konsumsi test split, lokasi registri | TK-3, TK-9 | Bagian pemisahan di D1 |
| **WP6** | **Ukuran sampel dan kelayakan:** K5 per kalibrator; minimum per indikasi untuk validasi T_k; cara memperkirakan jumlah sesi dan peserta dari prevalensi yang **belum diketahui**, dalam bentuk rumus dan skenario, tanpa mengarang angka prevalensi; dampak dua kalibrator | TK-2 | Bagian kelayakan di D1 |
| **WP7** | **P1-4 dan turunannya:** prioritas V5/V5+A3; definisi Y untuk V5+A3; persetujuan audio penelitian; cara pengumpulan audio; penyimpanan, akses, penghapusan; pengukuran tingkat persetujuan | P1-4 | Analisis keputusan P1-4 (D3) |
| **WP8** | **Etika, pelindungan data, tata kelola:** selaras dengan protokol §6; data penelitian terpisah dari data produksi; kode samaran; retensi; status data lama | TK-8 | Bagian etika di D1 |
| **WP9** | **Spesifikasi skema dataset:** kolom untuk kalibrasi (sudah ada di Tahap 3), kolom G-a/G-b, sidik T_k yang dievaluasi (KB-1), kaitan ke field snapshot; format berkas; kode samaran | TK-7 (dicatat) | D4 |
| **WP10** | **Kriteria evaluasi T_k:** bentuk metrik dan ambang lolos (sensitivitas/spesifisitas dengan selang 95 % bootstrap peserta; nilai minimum = keputusan pemilik proyek); aturan pemilihan bila M-b; inklusi sesi bercakupan rendah (sementara K2) | AL-3c rinci | Bagian kriteria di D1 |
| **WP11** | **Penutupan:** pemeriksaan konsistensi dengan semua dokumen, daftar keputusan, laporan hasil | — | D5 |

## 5. Daftar keluaran yang akan dievaluasi

| ID | Keluaran | Bentuk |
|---|---|---|
| D1 | `docs/SESSION_CALIBRATION_DATASET.md`: dokumen kebutuhan dataset dan protokol pelabelan (L5) | Dokumen utama |
| D2 | Rancangan pedoman pelabelan K1, G-a, dan G-b | Lampiran D1 atau dokumen terpisah |
| D3 | Analisis keputusan P1-4 dan turunannya | Dokumen keputusan |
| D4 | Spesifikasi skema dataset | Bagian D1 |
| D5 | `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP4_RESULTS.md`: laporan hasil Tahap 4 | Laporan |

Tidak ada kode, skrip, atau data yang dibuat. Bila spesifikasi kelak menuntut perubahan skrip kalibrasi (mis. kolom baru), perubahan itu dicatat sebagai usulan untuk persetujuan terpisah.

## 6. Titik henti yang diusulkan

| Titik | Setelah | Isi untuk evaluasi pemilik proyek |
|---|---|---|
| **H1** | Rencana ini | Persetujuan rencana dan **arah TK-1** (atau izin agar TK-1 dianalisis di WP4 sebagai keputusan) |
| H2 | WP2, WP4, WP7 | Keputusan: ambang κ dan formulir label (TK-5, TK-6); komposisi dataset (TK-1); P1-4 dan turunannya |
| H3 | WP3, WP5, WP6, WP8, WP9, WP10 | Rancangan lengkap D1–D4 |
| H4 | WP11 | Penutupan Tahap 4 (D5) |

## 7. Kriteria penutupan Tahap 4

Dari laporan AL3C_OS1_KB §4.2, ditambah konflik di §3:
1. P1-4 dan turunannya diputuskan.
2. Rincian AL-3c diputuskan: pedoman "bermakna", proporsi subsampel G-b, ambang kesepakatan antarpelabel (TK-5, TK-6).
3. Bentuk kriteria evaluasi T_k dan minimum per indikasi ditetapkan. Nilai minimum ditetapkan **sebelum** test split dilihat.
4. Lokasi registri test split dan artefak dataset ditetapkan (TK-9).
5. Aturan inklusi sesi bercakupan rendah ditetapkan (sementara K2; final mengikuti AL-2).
6. TK-1 sampai TK-4 diputuskan dan tercermin di D1; TK-7 dan TK-8 tercatat sebagai prasyarat pengumpulan data.
7. Semua dokumen konsisten dengan keputusan yang berlaku.

**Bukan bagian Tahap 4:**
- pengumpulan data dan izin etika;
- instans pilot;
- nilai T_k;
- AL-3a, AL-3b;
- AL-1, AL-2, AL-4, AL-5, AL-6, K7;
- Phase 6.

## 8. Konfirmasi

- Dokumen ini baru.
- Keputusan AL-3c, OS-1, dan K-b sudah dicatat di dokumen terkait:
  - `AL3C_OS1_KB_ANALYSIS`: status dan tabel §5;
  - `CHECKPOINT_AL3_DERIVED`: status dan tabel §3;
  - `ARCHITECTURE_ALIGNMENT`: §6.2 baru tentang identitas konfigurasi laporan (KB-1) dan baris OS-1/K-b di §7;
  - `PHASE5_PLAN`: status Tahap 4.
- Tidak ada perubahan kode, konfigurasi runtime, `.env`, database, data, atau dataset, dan tidak ada commit.
- Tidak ada nilai T_k yang ditetapkan, dan Live Rule Alert tidak diubah.
