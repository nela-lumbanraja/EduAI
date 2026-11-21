# Verifikasi PDF Session Report terhadap commit `e17d456`

**Tanggal:** 21 November 2026
**Commit yang diverifikasi:** `e17d456` (Commit B: Session Report, D4, mekanisme kalibrasi), cabang `istilah-prodi`
**Sifat:** verifikasi implementasi yang sudah di-commit. Ini bukan Phase 6 dan bukan implementasi fitur baru.

## Ringkasan

| Pertanyaan | Jawaban |
|---|---|
| Apakah PDF sesuai rancangan final (empat bagian)? | **Belum.** PDF masih berformat surat "Laporan Hasil Pengawasan Ujian" (bagian I–V dan Lampiran). Keempat bagian rancangan tidak ada. |
| Apakah snapshot Session Summary benar? | **Ya.** Skor per indikasi, skor agregasi, durasi, cakupan, dan interval 5 menit (termasuk interval terakhir yang lebih pendek) cocok dengan hitungan manual. Snapshot beku setelah finalisasi. |
| Apakah PDF dibuat dari snapshot? | **Tidak.** PDF disusun ulang dari tabel kejadian dan akun setiap kali diminta. PDF tidak memanggil analisis AI. |
| Apakah ALERT dapat diuji? | **Tidak.** Session Indication Alert dan jumlah ALERT belum diimplementasikan (G1/G2). |

Ini sejalan dengan [rancangan Tahap 3](EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md) §1.3, yang mencatat bahwa Session Summary belum masuk PDF dan menjadwalkan PDF empat bagian di Phase 6.

## 1. Metode dan batasannya

- **Kode yang diuji:** isi `e17d456`, diekstrak dengan `git archive` ke folder kerja sementara di luar repositori. Perubahan yang belum di-commit (fitur liveFrame yang ditahan) tidak ikut teruji. Repositori tidak diubah selama verifikasi.
- **Data:** setiap tes memakai database SQLite sementara yang dibuat baru dan akun demo hasil seed (`siswa1`–`siswa6`, `pengawas1`, `admin1`). Tidak ada data mahasiswa nyata, database produksi, atau dataset.
- **AI:** pengganti berskrip (`FakePerception` dari `backend/tests/test_api.py`), yang ditentukan oleh kecerahan frame. Model AI nyata, audio, pilot, dan perekaman sengaja tidak dipakai.
- **Pemeriksaan PDF:** teks diekstrak dari stream halaman PDF (ASCII85 + Flate). Perender PDF tidak terpasang, jadi tampilan visual tidak diperiksa.
- **Kalibrasi:** tidak ada kalibrator dan tidak ada T_k. Status tetap `not_calibrated`.

## 2. Skenario yang diuji

| # | Skenario | Isi |
|---|---|---|
| S1 | Alur utama | Ujian 1, 12 menit (720 detik), sehingga ada interval 300, 300, dan 120 detik. Satu mahasiswa mengirim 1 frame/detik: interval pertama memuat 60 detik tanpa wajah dan 30 detik gelap; interval kedua tanpa frame; interval ketiga memuat 60 detik tanpa wajah. Lima mahasiswa lain terdaftar tanpa data. Pemantauan dihentikan, semua kejadian ditinjau, laporan difinalisasi, lalu PDF dibuat sebelum dan sesudah finalisasi. |
| S2 | Data lama | Ujian 2 berisi kejadian tanpa data observasi (seperti data sebelum Phase 2), lalu difinalisasi dengan cara lama (baris `report_finals` tanpa snapshot, seperti sebelum Phase 4). |
| S3 | Sesi tanpa data sama sekali | Ujian 2: pemantauan dimulai dan dihentikan tanpa satu frame pun, lalu difinalisasi. |
| S4 | Perubahan sesudah finalisasi | Setelah S1 difinalisasi: (a) satu kejadian disisipkan langsung ke database uji; (b) admin mengganti nama akun mahasiswa lewat API resmi `PATCH /users/{id}`. |

Nilai harapan S1, dihitung manual:
- Interval k0 (300 detik, w = 1): analysable 270 detik, aktif 60 detik, sehingga p = 60/270 = 0,2222 dan cakupan 0,9.
- Interval k1 (300 detik, w = 1): tanpa data, sehingga p = 0 dan cakupan 0. Interval ini tetap dihitung di penyebut.
- Interval k2 (120 detik, w = 0,4): p = 60/120 = 0,5 dan cakupan 1.
- P(FACE_ABSENT) = (0,2222 + 0 + 0,4 × 0,5) / 2,4 = **0,175926**.
- Cakupan sesi = (0,9 + 0 + 0,4) / 2,4 = **0,541667**.
- P_total = 0,175926 / 5 indikasi video = **0,035185**.

## 3. Hasil per butir

| # | Butir | Hasil | Bukti |
|---|---|---|---|
| 1 | Alur dari sesi selesai sampai PDF | ✅ Finalisasi berhasil (HTTP 200) dan PDF terbentuk. PDF sebelum finalisasi bertanda **DRAF**; sesudahnya tidak. | S1 |
| 2 | Data uji yang sah | ✅ Akun demo dan database sementara. Tanpa data nyata. | — |
| 3 | PDF terhadap empat bagian rancangan | ❌ Session Overview, Indication Analysis, Session Timeline, dan Data Coverage & Calculation Details tidak ada. Yang ada: I Identitas Ujian, II Kehadiran Peserta, III Jalannya Ujian, IV Catatan Pemantauan, V Tindak Lanjut, Lampiran. | S1 |
| 4a | Skor per indikasi dan skor agregasi | ✅ di snapshot: FACE_ABSENT 0,175926; P_total 0,035185; probabilitas kosong. ❌ di PDF: tidak ada angka skor. | S1 |
| 4b | Durasi dan cakupan | ✅ di snapshot: terjadwal 720 detik, teramati 420 detik, cakupan 0,541667. Indikasi audio dikecualikan dengan alasan tercatat; status model (D4) lengkap. ❌ di PDF: tidak ada cakupan. | S1 |
| 4c | Status ALERT per indikasi dan jumlah ALERT | ⛔ Tidak dapat diuji, karena belum diimplementasikan (lihat bagian 5). | — |
| 5 | Interval 5 menit dan interval terakhir lebih pendek | ✅ di snapshot: durasi 300 / 300 / 120 detik, w = 1 / 1 / 0,4; interval tanpa data beralasan `tidak_ada_frame` dan tetap di penyebut. ❌ di PDF: tidak ada timeline. | S1 |
| 6 | PDF dari snapshot, tanpa menghitung ulang AI | Sebagian. ✅ Membuat PDF tidak memanggil analisis AI (0 panggilan). ✅ Snapshot tidak berubah pada S4. ❌ PDF tidak memakai snapshot dan berubah pada S4 (temuan T2). | S1, S4 |
| 7a | Tanpa data per peserta | ✅ di snapshot: cakupan 0, ketiga interval tanpa data, P_total 0, dengan catatan "Skor 0 bukan bukti bahwa tidak ada indikasi". ❌ di PDF tidak ada keterangan. | S1 |
| 7b | Sesi tanpa data sama sekali | ⚠ Finalisasi dan PDF berhasil ("mencatat 0 indikasi"). Snapshot tidak disimpan, sesuai aturan A7, tetapi alasan yang dilaporkan keliru (temuan T3). | S3 |
| 7c | Data lama tanpa cakupan | ✅ Status `tidak_tersedia` tanpa menghitung ulang, dengan alasan "tidak ada data cakupan pengamatan" (sebelum final) dan "sesi sebelum fitur ini" (sesudah finalisasi lama). PDF tetap terbentuk tanpa keterangan cakupan. | S2 |

## 4. Temuan

| # | Temuan | Dampak | Tindak lanjut |
|---|---|---|---|
| T1 | PDF belum memuat Session Summary: tidak ada skor, cakupan, interval, ataupun empat bagian rancangan. | PDF belum dapat dipakai sebagai Session Report sesuai rancangan. | Ditunda ke Phase 6, bersama G1–G4. |
| T2 | PDF disusun ulang dari tabel kejadian dan akun, bukan dari snapshot. Semua jalur tulis kejadian dan tinjauan memang diblokir sesudah finalisasi, tetapi (a) nama akun yang diubah lewat `PATCH /users` ikut berubah di PDF final, dan (b) kejadian yang disisipkan langsung ke database mengubah jumlah indikasi di PDF (2 menjadi 3). | PDF final belum memenuhi prinsip "PDF dari snapshot". | Ditunda ke Phase 6 (PDF dari snapshot). |
| T3 | Sesi baru yang difinalisasi tanpa data Session Summary dilaporkan dengan alasan "laporan difinalisasi tanpa data Session Summary (sesi sebelum fitur ini)". Alasan aslinya ("tidak ada data cakupan pengamatan untuk sesi ini") hilang. | Menyesatkan: sesi baru tampak seperti sesi lama. | **Diperbaiki** (bagian 6). |
| T4 | 30 detik video yang tidak dapat dianalisis ditulis "total sekitar 0 menit", karena `round(0.5)` di Python menghasilkan 0. | Durasi pendek tampak nol. | **Diperbaiki** (bagian 6). |

Catatan di luar lingkup T4: tampilan laporan di frontend (`frontend/src/charts.tsx`, "Periode tidak terbaca") membulatkan dengan `Math.round(detik / 60)`. Durasi 30 detik tampil "± 1 menit", tetapi durasi di bawah 30 detik tampil "± 0 menit". Tidak diubah; perlu keputusan terpisah.

## 5. Belum dapat diuji

| Item | Alasan |
|---|---|
| G1: Session Indication Alert per indikasi (P_k ≥ T_k) | Belum diimplementasikan; T_k belum ditetapkan. Tidak ada field ALERT di hasil langsung maupun snapshot. |
| G2: jumlah indikasi berstatus ALERT | Belum diimplementasikan. |
| Live Rule Alert di laporan | Aturan episode (`min_count`, `window_s`) ada di sistem kasus, tetapi tidak masuk laporan, snapshot, maupun PDF (bagian dari G1/G4). |
| Empat bagian PDF | Belum ada (Phase 6). |
| Indikasi audio dan model AI nyata | Sengaja tidak dipakai: perekaman, pilot, dan model nyata di luar batas verifikasi ini. |
| Tampilan visual PDF | Perender PDF tidak tersedia; isi diperiksa lewat teks yang diekstrak. |

## 6. Perbaikan terbatas T3 dan T4 (disetujui pemilik proyek, 21 November 2026)

Patch terpisah, di-commit sebagai **`411a887`** (`fix: alasan Session Summary untuk sesi baru tanpa data (T3) dan durasi pendek di PDF (T4)`). Rumus skor, cakupan, isi snapshot, skema database, dan `backend/app/api.py` tidak diubah.

**T3 (`backend/app/session_summary.py`)**
- Bila laporan final tidak punya baris snapshot, `read_snapshot` kini membedakan dua keadaan:
  - **Sesi yang difinalisasi oleh kode sekarang** saat Session Summary tidak tersedia. Penandanya adalah catatan audit finalisasi "…; Session Summary tidak tersedia)", yang ditulis `finalize_report` sejak Phase 4. Hasilnya: `status: tidak_tersedia`, alasan asli, `unavailable_kind: tidak_tersedia_saat_finalisasi`, dan bila tidak ada observasi sama sekali, `coverage: 0` beserta catatan "Skor 0 bukan bukti bahwa tidak ada indikasi".
  - **Laporan yang difinalisasi sebelum Phase 4** (tanpa penanda itu). Tetap dilaporkan sebagai "sesi sebelum fitur ini", tanpa field baru.
- Alasan asli diturunkan lagi dari data observasi yang tersimpan. Data itu tidak dapat berubah setelah laporan final, dan tidak ada skor yang dihitung ulang.
- Kalimat alasan "tidak ada data cakupan pengamatan untuk sesi ini" kini berupa satu konstanta (`NO_OBSERVATION_REASON`), dipakai bersama oleh hasil langsung dan hasil final.
- Penanda dicocokkan per ujian: `target` audit harus persis `exam:<id>` (jadi `exam:1` tidak cocok dengan `exam:12`), dan pola teks dimulai dari awal ("Memfinalisasi laporan (…"). ID ujian memakai `AUTOINCREMENT`, tidak ada penghapusan ujian, audit, atau data observasi, dan tidak ada pembatalan finalisasi.
- **Keterbatasan (risiko ketergantungan pada teks audit):**
  1. Bila kalimat audit di `finalize_report` diubah kelak, penanda ini harus ikut disesuaikan; tanpa itu sesi baru tanpa data kembali disebut "sesi sebelum fitur ini". Tes T3 menjalankan finalisasi sungguhan, sehingga perubahan kalimat itu akan membuat tesnya gagal.
  2. Audit ditulis sesudah transaksi finalisasi. Bila proses terhenti di antaranya, penanda tidak ada dan jawabannya jatuh ke pesan lama (konservatif; tidak ada data yang hilang).
  3. Bila tabel audit kelak dipangkas, penanda bisa hilang. Saat ini tidak ada pemangkasan.

  Pilihan yang lebih kuat, misalnya menyimpan alasan saat finalisasi, memerlukan perubahan `api.py` atau skema dan karena itu tidak diambil.

**T4 (`backend/app/report_export.py`)**
- Fungsi baru `duration_text(detik)`: durasi dibulatkan setengah ke atas ke detik penuh. Di bawah 60 detik ditulis dalam detik ("30 detik"). Mulai 59,5 detik ditulis "sekitar N menit" dengan pembulatan setengah ke atas, jadi 59,5–59,9 detik menjadi "sekitar 1 menit", bukan "60 detik".
- Batas yang diperiksa: 29 → "29 detik"; 29,5 dan 30 → "30 detik"; 59 dan 59,4 → "59 detik"; 59,5, 60, dan 89,9 → "sekitar 1 menit"; 90 → "sekitar 2 menit"; 150 → "sekitar 3 menit".
- Hanya dipakai untuk kalimat "Waktu video tidak dapat dianalisis …" di PDF. XLSX, frontend, dan teks durasi suara tidak berubah. Nilai detik yang tersimpan dan semua penjumlahan tidak berubah.

**Tes regresi (`backend/tests/test_session_report_t3_t4.py`, 6 tes)**
- T3: sesi baru tanpa data menyimpan alasan aslinya; laporan sebelum fitur tetap sesi lama; penanda satu ujian tidak bocor ke ujian lain; snapshot normal tetap terbaca seperti sebelumnya.
- T4: tabel nilai `duration_text`, termasuk detik pecahan dan batas 59,5 detik; PDF menulis 30 detik gelap dalam detik dan tidak lagi "sekitar 0 menit".

**Hasil**
- Backend penuh: **356 lulus**, 2 dilewati, 0 gagal (350 sebelumnya + 6 tes baru).
- Pada `e17d456` + patch saja (tanpa liveFrame, model ONNX opsional tersedia di salinan uji): semua lulus.
- Pada kode tanpa patch, tes T3 (sesi baru dan penanda) serta tes T4 gagal, seperti yang diharapkan.
- **Uji mutasi** (kode patch sengaja dirusak di salinan uji, lalu keenam tes dijalankan): 8 dari 8 mutasi tertangkap.
  - T4: kembali ke `round()` lama; detik pecahan dipotong (`int(s)`); 59,5–59,9 detik kembali menjadi "60 detik".
  - T3: perilaku lama; penanda tanpa filter ujian; penanda cocok untuk semua finalisasi; catatan "skor 0" hilang; target dicocokkan sebagai prefiks.

## 7. Keputusan tindak lanjut

| Item | Keputusan (21 November 2026) |
|---|---|
| Dokumen ini | Dibuat dan di-commit terpisah dari perbaikan kode. |
| T3, T4 | Perbaikan terbatas disetujui, ditinjau (termasuk uji mutasi), dan di-commit sebagai `411a887`. |
| Format durasi di frontend (`charts.tsx`) | Di luar lingkup T4; belum diputuskan. |
| T1, T2 | Tidak dikerjakan. Diputuskan bersama G1–G4 sebelum Phase 6. |
| G1–G4, T_k, kalibrator, PDF empat bagian, PDF dari snapshot | Tidak dikerjakan. |
| Pilot, perekaman, migrasi produksi, perubahan database/skema, Phase 6 | Tidak dikerjakan. |

Bukti verifikasi (PDF, JSON, dan teks hasil ekstraksi untuk S1–S4) disimpan di folder kerja sementara sesi pengerjaan, di luar repositori, dan tidak permanen. Skrip tes verifikasi dapat dijalankan ulang terhadap `e17d456` untuk membuat bukti yang sama.
