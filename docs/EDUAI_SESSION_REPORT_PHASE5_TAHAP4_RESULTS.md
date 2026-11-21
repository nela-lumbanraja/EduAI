# Session Report Phase 5, Tahap 4: Laporan Penutupan (Perancangan Kebutuhan Dataset)

Tanggal: 21 November 2026 · Status: **Tahap 4 DITUTUP sebagai tahap perancangan (keputusan pemilik proyek, opsi a). Diserahkan untuk evaluasi.** Tidak ada commit.

**Penutupan ini tidak berarti:**
- rancangan telah tervalidasi secara empiris;
- kalibrator layak;
- sistem siap dipakai pada ujian nyata.

Tahap 4 hanya menghasilkan dokumentasi. Tidak ada perubahan kode, skrip, konfigurasi runtime, `.env`, database, skema, data, atau dataset. Tidak ada perekaman, instans pilot, pembacaan data produksi, nilai T_k, perubahan Live Rule Alert, atau Phase 6.

---

## 1. Ringkasan keputusan Tahap 4

| Titik | Keputusan (semua 21 November 2026) | Dokumen |
|---|---|---|
| Masuk Tahap 4 | AL-3c = G-c bertahap; OS-1 = O1; K-b = KB-1; Tahap 4 dimulai (evaluasi dan perancangan) | `EDUAI_SESSION_REPORT_AL3C_OS1_KB_ANALYSIS.md` |
| H1 | Rencana WP1–WP11; TK-1 dianalisis di WP4 | `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_PLAN.md` |
| H2 | H2-1 label tiga lapisan; H2-2 κ 0,60 / 0,60 / 0,70; H2-3 "teramati" menurut definisi operasional (TK-10); H2-4 DC-2; H2-5 populasi target wajib; H2-6 P1-4c (V5+A3 delapan indikasi); H2-7 audio riset terpisah dan dua angka persetujuan | `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_H2.md` |
| H3 | H3-1 label tidak lengkap ketat dan pelaporan sesi yang dikeluarkan; H3-2 kerangka definisi dan kebermaknaan kualitatif; H3-3 kohort dan split per komponen (1/3 : 2/3 sementara); H3-4 registri di penyimpanan penelitian; H3-5 urutan versi beku tanpa penyetelan ulang dari test; H3-6 uji coba kecil (jumlah belum ditetapkan; data tidak untuk test atau kalibrasi final); H3-7 M-a dengan batas bawah selang sensitivitas dan spesifisitas (nilai belum); H3-8 revisi protokol sebagai rancangan berversi; H3-9 D1 dasar desain | `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_H3.md` |
| Penutupan | Opsi (a): ditutup sebagai perancangan; parameter yang bergantung pada uji coba "ditetapkan setelah uji coba" | Dokumen ini |

## 2. Keluaran

| ID | Keluaran | Status |
|---|---|---|
| D1 | `docs/SESSION_CALIBRATION_DATASET.md`: kebutuhan dataset dan protokol pelabelan, rancangan 0.1 | Diterima sebagai dasar desain (H3-9) |
| D2 | Pedoman pelabelan K1, G-a, dan G-b (D1 §3) | Kerangka disetujui; isi final bersama Program Studi |
| D3 | Keputusan P1-4 dan turunannya (H2 §5) | Disetujui (H2-6, H2-7) |
| D4 | Skema dataset (D1 §8) | Bagian D1; tidak mengubah skema database EduAI |
| D5 | Laporan ini | — |
| Tambahan | `docs/EVALUATION_PROTOCOL_REVISI_0.2_RANCANGAN.md` | Rancangan berversi, **belum berlaku** (PS-7) |
| Tambahan | `EVALUATION_PROTOCOL.md` §7a, dan baris versi yang merujuk ke rancangan 0.2 | Ditambahkan atas permintaan pemilik proyek (TK-10, DC-2, satuan κ, pemisahan) |

## 3. Status kriteria penutupan (rencana Tahap 4 §7)

| # | Kriteria | Status |
|---|---|---|
| 1 | P1-4 dan turunannya | **Selesai** |
| 2 | Rincian AL-3c | κ **selesai**. Kerangka pedoman **selesai**; isi final bersama Program Studi. f ditetapkan setelah uji coba. |
| 3 | Kriteria evaluasi T_k | Bentuk **selesai** (H3-7); nilai ditunda (PS-9) |
| 4 | Lokasi registri | **Selesai** (H3-4) |
| 5 | Inklusi sesi bercakupan rendah | Sementara K2; final mengikuti AL-2 (terbuka) |
| 6 | TK-1 sampai TK-4 | TK-1, TK-3, TK-4 **selesai**; TK-2 terbuka sampai uji coba |
| 7 | Konsistensi dokumen | Diperiksa (§7) |

Kriteria yang tidak selesai ditunda secara eksplisit sesuai opsi (a).

## 4. Parameter yang belum ditetapkan

| Parameter | Ditetapkan oleh atau kapan |
|---|---|
| Jumlah peserta uji coba | Rencana uji coba (tujuan estimasi, kelayakan, persetujuan etik) |
| f, peluang terpilih subsampel G-b | Setelah uji coba |
| Proporsi split final | Setelah uji coba (sementara sekitar 1/3 : 2/3) |
| Ukuran dataset per `indicator_set` | Setelah uji coba (D1 §7.1, batas konservatif π) |
| Isi final definisi operasional dan kriteria kebermaknaan | Bersama Program Studi, setelah uji coba pedoman |
| Nilai T_k kebijakan | Program Studi (PS-8) |
| s_min, p_min, jumlah minimum per indikasi | Pemilik proyek (PS-9), sebelum test split dilihat |
| Aturan final inklusi sesi bercakupan rendah | AL-2 |
| Kelayakan K5 (TK-2) | Setelah uji coba |

## 5. Risiko terbuka

| ID | Risiko | Mitigasi yang dirancang | Sisa |
|---|---|---|---|
| TK-2 | Ukuran pilot jauh di bawah kebutuhan K5 | Uji coba memperkirakan π dan q; DC-4 dapat dianalisis (belum disetujui) | Kalibrator mungkin tidak dapat dibuat dalam waktu dekat. Itu hasil sah (`not_calibrated`). |
| TK-10 | Definisi "teramati" terlalu longgar membuat Y hampir selalu 1 | Definisi operasional per indikasi (H2-3), uji coba pedoman | Prevalensi bergantung pada kualitas definisi final |
| TK-1 / D-R2 | Populasi pilot berbeda dari ujian nyata | DC-2; populasi target dinyatakan (H2-5) | Probabilitas hanya berlaku pada populasi pilot; tidak ada jaminan pada ujian nyata walaupun E1–E6 lolos |
| Bias penyaringan | Aturan ketat mengeluarkan sesi tidak lengkap | Pelaporan jumlah dan karakteristik sesi yang dikeluarkan (H3-1) | Bias tetap mungkin; dievaluasi dari laporan |
| Subjektivitas kebermaknaan | κ G-a mungkin rendah | Pedoman kualitatif, uji coba, κ ≥ 0,60, adjudikasi | Pedoman mungkin perlu beberapa iterasi |
| Perilaku jarang | Indikasi seperti ponsel atau buku tidak mencapai minimum | Tetap "kebijakan, belum divalidasi" | T_k indikasi jarang mungkin tidak pernah tervalidasi |
| Etika dan privasi | Rekaman wajah dan audio (data pribadi spesifik) | Protokol §6, persetujuan bertingkat, penyimpanan penelitian terpisah | Bergantung pada izin etik (PS-5) |
| D-R9 sampai D-R12 (Tahap 3) | Data cepat habis; test split dipakai berulang; penyuntingan artefak; model worker | Seperti Tahap 3 | Tetap terbuka |
| AL-2 | Status data kosong untuk Session Indication Alert | Sementara K2 untuk inklusi | Terbuka |

## 6. Dependensi menuju tahap berikutnya

### 6.1 Untuk memulai uji coba kecil (di luar Phase 5 Tahap 4)

Berurutan, semuanya memerlukan persetujuan terpisah:
1. **PS-5:** izin komite etik, persetujuan pimpinan Program Studi, persetujuan bertingkat peserta.
2. **PS-4:** instans EduAI pilot terpisah dari produksi (memerlukan backend kode baru dengan tabel Phase 2 dan Tahap 2 pada database pilot, bukan produksi).
3. Penyetelan dan **pembekuan** deteksi, konfigurasi, dan model (H3-5).
4. Rencana uji coba dengan jumlah peserta (H3-6) dan pedoman draf bersama Program Studi.
5. **PS-7:** revisi protokol 0.2 diberlakukan, bila pilot memakai protokol revisi.

### 6.2 Untuk penutupan Phase 5 (rencana Phase 5 §9 langkah 5–7)

- Regresi penuh dan perbandingan hash data produksi.
- Laporan hasil Phase 5.
- Evaluasi penerimaan Phase 5 oleh pemilik proyek.

Langkah ini **tidak** memerlukan uji coba, karena Tahap 4 ditutup sebagai perancangan. Pelaksanaannya memerlukan instruksi pemilik proyek.

### 6.3 Untuk kalibrasi dan validasi T_k sungguhan (setelah uji coba dan pengumpulan data)

- PS-1 (skrip evaluasi T_k);
- PS-8 (nilai T_k);
- PS-9 (nilai kriteria);
- bila perlu, PS-2 (DC-4) dan PS-3 (`target_population`);
- keputusan aktivasi kalibrator (C6) terpisah.

### 6.4 Untuk Phase 6

Prasyarat:
- AL-1, AL-2 (termasuk usulan tiga status, belum disetujui);
- AL-3a, AL-3b;
- AL-4, AL-5 (G1–G4, termasuk field sidik T_k KB-1);
- AL-6, K7;
- nilai T_k (PS-8);
- persetujuan Phase 6.

Yang **sudah** diputuskan: P1-5 = S1, AL-3 = C, OS-1 = O1, K-b = KB-1, P1-6 (prinsip).

### 6.5 Jalur terpisah

- Persetujuan migrasi database produksi.
- Keputusan commit pekerjaan sejak `af628da`.
- PS-6: pembacaan agregat `consents` produksi untuk angka persetujuan audio pemantauan.

## 7. Perubahan dokumen di penutupan ini

| Dokumen | Perubahan |
|---|---|
| `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_H3.md` | Status dan tabel: H3-1 sampai H3-9 disetujui beserta batasannya; konflik penutupan diputuskan opsi (a) |
| `SESSION_CALIBRATION_DATASET.md` | Status diterima sebagai dasar desain. §3.3: pelaporan sesi yang dikeluarkan. §4: tanpa penyetelan ulang dari test. §5.3: R1 disetujui, R2 tidak dipilih, tidak di produksi atau repositori publik. §6: jumlah belum ditetapkan, data uji coba tidak untuk test atau kalibrasi final. §10: rujukan rancangan protokol. §12 baru: parameter yang ditetapkan setelah uji coba. |
| `EVALUATION_PROTOCOL_REVISI_0.2_RANCANGAN.md` | **Baru:** rancangan revisi berversi (R1–R7), belum berlaku |
| `EVALUATION_PROTOCOL.md` | Baris versi merujuk ke rancangan 0.2 (belum berlaku). §7a dari H2 tetap. |
| `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_PLAN.md` | Status: ditutup sebagai perancangan |
| `EDUAI_SESSION_REPORT_PHASE5_PLAN.md` | Status: Tahap 4 ditutup; langkah 5–7 belum |
| `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_RESULTS.md` | **Baru** (dokumen ini) |

**Catatan konsistensi:**
- Kalimat "Tahap 4 belum dimulai" di bagian batas pekerjaan dokumen evaluasi lama tidak diubah. Ketiganya: `…_P1_4_P1_5_EVALUATION.md`, `…_PHASE5_P1_EVALUATION.md`, `…_AL3C_OS1_KB_ANALYSIS.md`.
- Kalimat itu menggambarkan keadaan saat dokumen-dokumen tersebut ditulis, bukan baris status. Status terkini tercatat di rencana Phase 5 dan dokumen ini.

## 8. Konfirmasi

- Hanya dokumen di `docs/` yang berubah atau ditambahkan.
- Tidak ada perubahan kode, skrip, konfigurasi runtime, `.env`, database, skema, data, atau dataset, dan tidak ada commit (commit terakhir `af628da`).
- Tidak ada perekaman, instans pilot, pembacaan data produksi, nilai T_k, s_min, p_min, atau jumlah minimum.
- DC-4 dan `target_population` tidak diimplementasikan. Live Rule Alert tidak diubah. Phase 6 belum dimulai.
