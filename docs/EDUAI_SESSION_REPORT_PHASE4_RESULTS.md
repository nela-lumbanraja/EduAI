# Session Report: Hasil Phase 4 (Agregasi Sesi dan Snapshot Finalisasi)

Tanggal: 20 November 2026 · Status: **Diterima pemilik proyek pada 21 November 2026, setelah revisi T1–T6** (lihat `EDUAI_SESSION_REPORT_PHASE4_REVISION_RESULTS.md`). *Status awal dokumen ini: "selesai, menunggu evaluasi pemilik proyek. Phase 5 belum dimulai."* Isi di bawah adalah hasil sebelum revisi.

Tidak diubah: PDF, alert, model, inference, frontend, dan data historis. Kalibrasi tetap `not_calibrated`. Tidak ada commit. Cadangan file sebelum perubahan ada di `..\EduAI_cadangan_20261120\sesi_phase4\`.

---

## 1. Perubahan file

| File | Perubahan |
|---|---|
| `ai/eduai-ai/config.yaml` | Bagian baru `session_summary.indicator_weights` dengan delapan indikasi, semuanya **1** (rata-rata biasa, K5), plus dokumentasi. Hanya dibaca backend; analisis AI tidak memakainya. `version` config tidak diubah. |
| `backend/app/session_summary.py` | `load_weights` (validasi ketat), `aggregate` (P_total), `compute_exam(..., weights)`, `snapshot_statements`, `read_snapshot`, `MAX_WINDOW_S`; rentang observasi per peserta (`observation_start`/`observation_end`) |
| `backend/app/api.py` | `finalize_report`: hitung Session Summary sebelum transaksi, tulis snapshot **dalam transaksi yang sama** dengan `report_finals`, flush observasi ujian dulu, bobot tidak valid → finalisasi ditolak, salinan gambar dihapus lagi bila transaksi gagal. `_session_summary_live`; endpoint baru `GET /api/sessions/{id}/session-summary`. |
| `docs/API.md` | Baris endpoint baru |
| `backend/tests/test_session_summary_aggregation.py` | **Baru**, 12 tes |

## 2. Aturan yang diterapkan

| Aturan | Implementasi |
|---|---|
| Bobot jenis hanya di tahap akhir | `P_total = Σ v_i P_i / Σ v_i`. Bobot interval sudah ada di dalam P_i (Phase 3) dan tidak dicampur. |
| Bobot dari konfigurasi | `load_weights`: indikasi tak dikenal (termasuk HEAD_TURN_REPEATED), nilai negatif, teks, boolean, atau NaN → `ValueError`, finalisasi ditolak dengan pesan jelas. Indikasi yang tidak disebut → 1, dan sumbernya menyebut "bawaan 1". |
| Bisa ditelusuri | Setiap baris `*` menyimpan `weights_json`: bobot lengkap, bobot yang dipakai peserta itu, sumber bobot, indikasi yang dikecualikan beserta alasannya, persetujuan audio, dan status. Ditambah `config_version` dan `algo_version` (`session-summary-1`). |
| Indikasi yang tidak berlaku | Tidak masuk penjumlahan (contoh: audio tanpa persetujuan); bobot 0 mengeluarkan indikasi; semua bobot 0 → `null`, bukan pembagian nol |
| Kalibrasi | `calibration = {status: not_calibrated, version: null, probability: null}` dengan catatan "Belum tersedia"; CHECK di database menolak probabilitas tanpa status `calibrated` |
| Snapshot | Semua baris interval (duration score per indikasi + confidence per sumber) dan baris peserta (per indikasi + `*`) untuk **semua peserta terdaftar**, ditulis di `db.run_all` bersama `report_finals` |
| Idempoten | Finalisasi kedua → 409 seperti sebelumnya; `INSERT OR IGNORE` + PK, sehingga penulisan ulang tidak menambah baris |
| Beku | Setelah final, endpoint membaca snapshot; data yang datang belakangan tidak mengubahnya |
| Sesi lama (A7) | Laporan final tanpa snapshot → `tidak_tersedia`, tidak dihitung ulang |
| Pengaman baru | Jendela sesi > 24 jam (jam pengamatan atau jadwal tidak wajar) → `tidak_tersedia` dengan alasan, tanpa membuat larik per detik berbulan-bulan |

**Perbaikan sampingan yang terkait:** sebelumnya, bila transaksi finalisasi gagal, gambar yang sudah disalin untuk laporan tertinggal di folder `report-frames` tanpa baris database. Sekarang gambar itu dihapus lagi (diuji).

## 3. Hasil pengujian (12 tes baru, semua lulus)

| Tes | Hasil yang diharapkan dan teramati |
|---|---|
| Bobot dari config dan validasi | `PHONE_VISIBLE: 2` terbaca; config tanpa bagian → semua 1 dan sumbernya "bawaan 1"; HEAD_TURN_REPEATED, nama asing, −1, "2", True, NaN ditolak |
| Config proyek | Delapan bobot eksplisit = 1, tanpa "bawaan" |
| Contoh pemilik proyek | 0,50 / 0,60 / 0,80 / 0,50 → **0,60** |
| Rata-rata berbobot | v = (2, 1, 1, 1) → **0,58**; indikasi tidak berlaku tidak dihitung; bobot 0 mengeluarkan; semua 0 → `null` |
| Tanpa kalibrator | `not_calibrated`, probabilitas `null`, catatan "Belum tersedia" |
| Finalisasi membekukan nilai live | Lewat API (frame nyata, kejadian ditinjau, finalisasi). Siswa1: FACE_ABSENT **0,125** = (30/120 + 0)/2; cakupan **0,2**; P_total **0,025** = 0,125/5. Live tidak disimpan; final = live; versi config `0,2-provisional`; durasi terjadwal 600 dtk, teramati 120 dtk, 2 interval, 1 tanpa data. Semua peserta terdaftar tersimpan; baris interval = peserta × 2 interval × (5 duration + 3 confidence). |
| Idempoten dan beku | Finalisasi kedua 409, jumlah baris tetap; data baru setelah final tidak mengubah hasil; penulisan ulang snapshot tidak menambah baris |
| Transaksi gagal | Baris yang melanggar CHECK → seluruh transaksi batal: 0 baris ringkasan, `report_finals` kosong, `report_frames` kosong, folder gambar laporan kosong |
| Bobot tidak valid | Finalisasi 500 dengan pesan "tidak valid"; laporan tidak menjadi final |
| Laporan final sebelum fitur | `tidak_tersedia`, tanpa hitung ulang |
| Jendela tidak wajar | Jam 6 tahun meleset → `tidak_tersedia`, alasan "melebihi" |
| Akses | Tanpa login 401; mahasiswa 403 |

**Regresi:**

| Paket | Hasil |
|---|---|
| Backend | **320 lulus**, 0 gagal, 2 dilewati (308 + 12) |
| Modul AI | 122 lulus (diperiksa karena `config.yaml` berubah) |
| Frontend | Tidak diubah |
| Data produksi | Hash `backend/data` tidak berubah sejak akhir Phase 2 |

## 4. Risiko dan batasan

| ID | Hal | Catatan |
|---|---|---|
| R1 | Waktu finalisasi bertambah | Perhitungan semua peserta terjadi saat tombol finalisasi ditekan. Ujian 120 menit × 40 peserta belum diukur; masuk regresi Phase 7. |
| R2 | P_total adalah gabungan duration score | Bukan probabilitas. PDF di Phase 6 harus menuliskannya demikian; probabilitas hanya dari kalibrator (Phase 5). |
| R3 | Bobot 1 adalah keputusan K5 | Nilai lain harus ditetapkan Program Studi; setiap perubahan tercatat di snapshot. |
| R4 | Laporan draf | PDF draf (Phase 6) akan memakai nilai live yang bisa berubah sampai final |
| R5 | Migrasi produksi | Belum dijalankan (Phase 2, R1) |

## 5. Langkah berikutnya (menunggu persetujuan)

Phase 5, kalibrasi: ground truth tingkat sesi **belum tersedia** (audit Phase 1 bagian 8). Rencananya:

- antarmuka kalibrator (memuat berkas kalibrator bila ada dan valid, selain itu `not_calibrated`);
- skrip pelatihan Platt dan evaluasi (Brier, kurva kalibrasi, cek kebocoran per peserta/sesi) yang diuji dengan data buatan;
- dokumen kebutuhan dataset;
- **tidak** menghasilkan probabilitas apa pun di produksi.
