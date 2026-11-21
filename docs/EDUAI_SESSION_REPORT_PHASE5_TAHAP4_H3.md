# Session Report Phase 5, Tahap 4: Titik Henti H3 (Rancangan Lengkap)

Tanggal: 21 November 2026 · Status: **H3-1 sampai H3-9 DISETUJUI pemilik proyek (21 November 2026). Tahap 4 DITUTUP sebagai tahap perancangan (opsi a).** Parameter yang bergantung pada uji coba tetap "ditetapkan setelah uji coba". Lihat `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_RESULTS.md`. *Status awal: "Titik henti H3. Semua keputusan di dokumen ini BELUM DISETUJUI."*

**Keluaran yang dievaluasi:**
- **D1 + D2 + D4:** `docs/SESSION_CALIBRATION_DATASET.md` (rancangan 0.1);
- **D3:** P1-4 di `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP4_H2.md` §5 (disetujui di H2).

Paket kerja yang tercakup: WP3 urutan versi beku (D1 §4), WP5 pemisahan dan registri (§5), WP6 kelayakan (§6, §7.1), WP8 etika (§9), WP9 skema (§8), WP10 kriteria T_k (§7.2).

---

## 1. Keputusan yang diminta di H3

| ID | Keputusan | Status dan batasan |
|---|---|---|
| **H3-1** | Penanganan label tidak lengkap | **Disetujui (21 November 2026)**: aturan ketat. K1 = 0 hanya bila semua indikasi berlabel presence "tidak". Sesi dengan label tidak lengkap atau "tidak dapat dinilai" dikeluarkan dari analisis yang mensyaratkan label lengkap. **Jumlah dan karakteristik sesi yang dikeluarkan wajib dilaporkan** (D1 §3.3). |
| **H3-2** | Definisi operasional dan kebermaknaan | **Disetujui (21 November 2026)**: kerangka per indikasi. Definisi final dan kriteria kebermaknaan disusun bersama Program Studi; kriteria kebermaknaan kualitatif, tanpa ambang proporsi waktu (mencegah sirkularitas validasi T_k). |
| **H3-3** | Desain kohort dan split | **Disetujui (21 November 2026)**: kohort tetap; pemisahan per komponen peserta–sesi ujian; tidak ada peserta atau sesi ujian yang sama di kalibrasi dan test. Proporsi sekitar 1/3 kalibrasi dan 2/3 test **sementara**, bukan final. |
| **H3-4** | Lokasi registri | **Disetujui (21 November 2026)**: penyimpanan penelitian dengan akses terkendali; sidik kepala registri dicatat di laporan evaluasi. Registri dan data penelitian **tidak** di penyimpanan produksi atau repositori publik. |
| **H3-5** | Urutan versi beku | **Disetujui (21 November 2026)**: izin etik dan persetujuan → penyetelan deteksi → pembekuan konfigurasi dan model → uji coba → pembekuan pedoman dan split → pengumpulan data → evaluasi sekali. **Tidak ada penyetelan ulang berdasarkan hasil test.** |
| **H3-6** | Uji coba kecil | **Disetujui (21 November 2026)**: rancangan untuk memperkirakan prevalensi, waktu pelabelan, κ aktual, fraksi sesi lolos penyaringan. Jumlah peserta **belum ditetapkan**; ditentukan dalam rencana uji coba (tujuan estimasi, kelayakan, persetujuan etik). Data uji coba **tidak boleh** masuk test split atau menjadi data kalibrasi final. |
| **H3-7** | Kriteria evaluasi T_k | **Disetujui (21 November 2026)**: M-a dahulu; batas bawah selang sensitivitas dan spesifisitas. Nilai minimum sensitivitas, spesifisitas, dan jumlah minimum per indikasi **belum ditetapkan** (PS-8, PS-9). Tidak ada nilai T_k. |
| **H3-8** | Revisi protokol evaluasi | **Disetujui (21 November 2026)** sebagai rancangan dokumentasi dengan pengendalian versi: `EVALUATION_PROTOCOL_REVISI_0.2_RANCANGAN.md` (belum berlaku). Bukan izin pengumpulan data atau perubahan kode. Persetujuan formal PS-7 diperlukan sebelum berlaku. |
| **H3-9** | Status D1 | **Disetujui (21 November 2026)**: D1 diterima sebagai dasar desain. **Bukan** izin pengumpulan data, perekaman, instans pilot, atau pemakaian data produksi. |

## 2. Konflik dan hal yang tersisa

| # | Hal | Status |
|---|---|---|
| **TK-2** (kelayakan ukuran) | Tidak dapat diselesaikan tanpa uji coba: π dan q belum diketahui | **Terbuka, menunggu uji coba**, yang memerlukan PS-4 dan PS-5 |
| **Penutupan Tahap 4 vs uji coba** — **diputuskan: opsi (a)** | Beberapa kriteria penutupan (rencana §7) bergantung pada hasil uji coba: nilai f subsampel G-b, proporsi split final, ukuran dataset. Uji coba memerlukan izin etika dan instans pilot di luar Tahap 4. | **Konflik urutan.** Pilihan: (a) Tahap 4 ditutup sebagai rancangan, dengan parameter yang secara eksplisit "ditetapkan setelah uji coba"; (b) Tahap 4 tetap terbuka sampai uji coba selesai. Keputusan pemilik proyek. |
| TK-7, TK-8 | Instans pilot dan izin etika | Prasyarat di luar Tahap 4 (PS-4, PS-5) |
| AL-2 | Aturan final inklusi sesi bercakupan rendah | Sementara K2; terbuka |
| T_k | Nilai kebijakan | Belum ditetapkan (PS-8) |
| DC-4 | Pembobotan | Hanya dianalisis; implementasi belum disetujui (PS-2) |
| `target_population` | Field artefak | Belum disetujui (PS-3); sementara dicatat di laporan |

## 3. Status kriteria penutupan Tahap 4 (rencana §7)

| # | Kriteria | Status |
|---|---|---|
| 1 | P1-4 dan turunannya | **Selesai** (H2-6, H2-7) |
| 2 | Rincian AL-3c: pedoman, subsampel, kesepakatan | κ **selesai** (H2-2). Pedoman: kerangka siap, isi menunggu Program Studi dan uji coba (H3-2). Nilai f menunggu uji coba. |
| 3 | Kriteria evaluasi T_k | Bentuk diajukan (H3-7); nilai menunggu (PS-9) |
| 4 | Lokasi registri | Diajukan (H3-4) |
| 5 | Inklusi sesi bercakupan rendah | Sementara K2 (§7.2 D1); final mengikuti AL-2 |
| 6 | TK-1 sampai TK-4 | TK-1 **selesai** (DC-2). TK-2 menunggu uji coba. TK-3 dan TK-4 diajukan (H3-3, H3-5). |
| 7 | Konsistensi dokumen | Diperiksa (§4) |

## 4. Perubahan dokumen dalam paket ini

| Dokumen | Perubahan |
|---|---|
| `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_H2.md` | Status dan tabel §7: H2-1 sampai H2-7 disetujui beserta batasannya |
| `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_PLAN.md` | TK-10 ditambahkan ke daftar risiko dan konflik (§3) |
| `EVALUATION_PROTOCOL.md` | Bagian baru §7a: TK-10, DC-2, satuan κ, pemisahan untuk kalibrasi sesi. Bagian lain tidak diubah. |
| `SESSION_CALIBRATION_DATASET.md` | **Baru** (D1, D2, D4) |
| `EDUAI_SESSION_REPORT_PHASE5_TAHAP4_H3.md` | **Baru** (dokumen ini) |

## 5. Konfirmasi

- Tidak ada perubahan kode, konfigurasi runtime, `.env`, database, skema, data, atau dataset, dan tidak ada commit.
- Tidak ada perekaman, dan data lama tidak dipakai.
- Tidak ada nilai T_k yang ditetapkan, dan Live Rule Alert tidak diubah.
- DC-4 dan `target_population` tidak diimplementasikan.
- Phase 6 belum dimulai.
- Pekerjaan berhenti di **H3**.
