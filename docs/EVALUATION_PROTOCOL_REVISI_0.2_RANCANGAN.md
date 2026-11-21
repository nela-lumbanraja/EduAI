# Protokol Evaluasi Indikasi EduAI: Rancangan Revisi 0.2

| | |
|---|---|
| Versi | **0.2 (RANCANGAN, BELUM BERLAKU)**, 21 November 2026 |
| Berlaku sekarang | `docs/EVALUATION_PROTOCOL.md` versi 0.1 (usulan), dengan tambahan §7a |
| Dasar | Keputusan pemilik proyek H3-8 (Phase 5 Tahap 4): revisi disetujui **sebagai rancangan dokumentasi** dengan pengendalian versi |
| Syarat berlaku | Persetujuan formal pemilik proyek atas **PS-7**. Untuk pilot, juga persetujuan pimpinan Program Studi dan komite etik (protokol §6.1). |
| Bukan | Izin pengumpulan data, perekaman, pemakaian instans pilot, pemakaian data produksi, atau perubahan kode |

Dokumen ini hanya memuat **perubahan** terhadap versi 0.1. Bagian yang tidak disebut tetap seperti versi 0.1. Bila PS-7 disetujui, perubahan ini digabungkan ke `EVALUATION_PROTOCOL.md` dengan versi 0.2. Versi 0.1 dipertahankan sebagai riwayat, tidak dihapus.

Rincian teknis ada di `docs/SESSION_CALIBRATION_DATASET.md` (D1), yang diterima sebagai dasar desain (H3-9).

---

## R1. Tujuan (tambahan pada §1)

Selain evaluasi deteksi per indikasi, pilot menyediakan data untuk:
- (a) kalibrasi probabilitas tingkat sesi (Session Report Phase 5);
- (b) validasi ambang T_k Session Indication Alert (AL-3 = C).

Probabilitas terkalibrasi hanya berlaku pada **populasi pilot yang dinyatakan**. Probabilitas ini bukan prevalensi ujian nyata dan bukan probabilitas kecurangan.

## R2. Bentuk sesi (perubahan §2.1, DC-2)

| Sesi | Tujuan | Tidak dipakai untuk |
|---|---|---|
| Sesi skenario | Evaluasi deteksi; label rentang (G-b); diagnosis pengukuran | Kalibrasi sesi |
| **Sesi wajar** | Evaluasi deteksi (FP/jam); **kalibrasi sesi; validasi T_k**; uji coba kecil | — |

- Jumlah sesi wajar untuk kalibrasi dihitung dari uji coba kecil (D1 §6, §7.1), **per himpunan indikasi** (V5, V5+A3).
- Relawan dikelompokkan dalam **kohort tetap** yang selalu duduk bersama pada sesi ujian pilot yang sama (D1 §5.1).

## R3. Pelabelan (tambahan pada §3)

- **Tiga lapisan label:**
  - K1, tingkat sesi;
  - G-a, per indikasi per sesi: keberadaan dan kebermaknaan;
  - G-b, rentang waktu (prosedur §3 yang ada), pada subsampel.
- **"Teramati"** mengikuti definisi operasional per indikasi yang membedakan perilaku relevan dari aktivitas wajar ujian (TK-10). Satu kejadian umum bukan bukti kecurangan.
- **Kebermaknaan** bersifat kualitatif, ditetapkan bersama Program Studi, dan **tidak** berupa ambang proporsi waktu.
- **K1 diturunkan dari keberadaan G-a** dengan aturan ketat:
  - Y = 0 hanya bila semua indikasi berlabel "tidak";
  - sesi dengan label tidak lengkap atau "tidak dapat dinilai" dikeluarkan;
  - jumlah dan karakteristik sesi yang dikeluarkan dilaporkan.
- **Kesepakatan antarpelabel:**

  | Label | Satuan | Ambang |
  |---|---|---|
  | K1 | Sesi | κ ≥ 0,60 |
  | G-a | Sesi × indikasi | κ ≥ 0,60 |
  | G-b | Segmen 1 detik | κ ≥ 0,70 (tetap) |

- Pelabel buta terhadap keluaran sistem, skor, ambang, dan status alert apa pun.

## R4. Pemisahan data (perubahan §4, untuk kalibrasi sesi dan validasi T_k)

- Pemisahan **per peserta dan per sesi ujian**, dengan penempatan per komponen peserta–sesi ujian (kohort). Penempatan dilakukan **sekali untuk seluruh dataset**, lintas himpunan indikasi.
- Proporsi sementara sekitar 1/3 kalibrasi dan 2/3 test; proporsi final ditetapkan setelah uji coba.
- **Test split dipakai sekali.** Registri test split disimpan di penyimpanan penelitian dengan akses terkendali, tidak di penyimpanan produksi atau repositori publik. Sidik kepala registri dicatat di laporan evaluasi.
- Pemisahan per orang di §4 versi 0.1 tetap berlaku untuk evaluasi deteksi.

## R5. Urutan dan versi beku (tambahan pada §4)

Urutan langkahnya:
1. izin etik dan persetujuan;
2. penyetelan deteksi;
3. pembekuan konfigurasi dan model;
4. uji coba kecil;
5. pembekuan pedoman dan split;
6. pengumpulan data;
7. evaluasi sekali.

**Tidak ada penyetelan ulang berdasarkan hasil test.** Data uji coba tidak masuk test split dan tidak menjadi data kalibrasi final.

## R6. Audio (tambahan pada §6)

- Audio penelitian direkam **terpisah dari EduAI**, hanya dengan centang audio pada persetujuan bertingkat.
- Tata kelolanya mengikuti §6.2–§6.4.
- Persetujuan audio **riset** pada pilot dan persetujuan audio **pemantauan** pada ujian nyata dicatat sebagai **dua angka terpisah**.

## R7. Batas interpretasi (tambahan pada §8)

- Populasi target kalibrasi wajib dinyatakan.
- Lolosnya kriteria kalibrasi (E1–E6) hanya membuktikan kalibrasi pada populasi data pilot.
- Penutupan perancangan tidak berarti rancangan tervalidasi secara empiris, kalibrator layak, atau sistem siap untuk ujian nyata.
