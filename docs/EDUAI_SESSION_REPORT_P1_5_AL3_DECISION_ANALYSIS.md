# Session Report: Analisis Keputusan P1-5 (Pemisahan ALERT) dan AL-3 (Sumber Threshold T_k)

Tanggal: 21 November 2026 · Status: **P1-5 dan AL-3 DIPUTUSKAN pemilik proyek (21 November 2026): P1-5 = S1, AL-3 = C.** Persetujuan hanya untuk kedua keputusan ini; tidak ada nilai numerik T_k yang ditetapkan dan tidak ada persetujuan implementasi. Keputusan turunan AL-3 (lokasi, validasi, kriteria evaluasi), AL-2 (termasuk usulan tiga status, belum disetujui), AL-1, AL-4, AL-5, AL-6, P1-4, dan K7 tetap terbuka. *Status awal: "Analisis keputusan untuk evaluasi. P1-5 dan AL-3 BELUM DIPUTUSKAN."*

Langkah 2 dari `EDUAI_SESSION_REPORT_READINESS_CHECK.md` §5.

**Batas pekerjaan:**
- Tidak ada perubahan kode, konfigurasi, database, data, dataset, atau perilaku sistem, dan tidak ada commit.
- Rumus Phase 4 dan keputusan yang sudah diterima tidak berubah.
- Usulan tiga status ALERT (AL-2) **tidak** disetujui di sini.
- Phase 5 Tahap 4 dan Phase 6 belum dimulai.
- **Tidak ada nilai T_k yang ditetapkan.** Yang dibahas hanya sumber dan mekanisme penentuannya.

**Acuan:**
- `EDUAI_SESSION_REPORT_ARCHITECTURE_ALIGNMENT.md` §4–§7;
- `EDUAI_SESSION_REPORT_P1_4_P1_5_EVALUATION.md` Bagian B (dengan catatan B.7);
- rancangan final Session Report.

---

## 0. Batasan dari rancangan final yang dipakai sebagai syarat

| # | Syarat | Dipakai untuk menilai pilihan |
|---|---|---|
| R1 | Indication Summary menampilkan skor dan ALERT **setiap indikasi** | ALERT harus per indikasi |
| R2 | Overall Session Summary menampilkan skor agregasi, durasi, dan cakupan | P_total tetap ringkasan |
| R3 | P_total **tidak** menggantikan ALERT per indikasi | Tidak ada ALERT berdasarkan P_total |
| R4 | Rumus Phase 4 dan snapshot finalisasi dipertahankan | P_k dipakai apa adanya; snapshot hanya bertambah isi |
| R5 | PDF Phase 6 memakai finalization snapshot | ALERT laporan harus dapat dibekukan di snapshot |
| R6 | Arsitektur target: Session Indication Alert = 1 jika P_k ≥ T_k | Sumber ALERT laporan |

---

# Bagian 1: P1-5, arah pemisahan Live Rule Alert dan Session Indication Alert

## 1.1 Dua mekanisme (ringkasan Alignment §4)

| | Live Rule Alert | Session Indication Alert |
|---|---|---|
| Dasar | Jumlah episode ≥ `min_count` dalam `window_s` | P_k ≥ T_k |
| Waktu | Langsung, selama sesi | Pada laporan sesi (final) |
| Dipakai sekarang | Pop-up pengawas, prioritas tinjauan, status aturan, `rules_met`, daftar kasus | Belum ada |

## 1.2 Pilihan

| Kode | Arah | Ringkasnya |
|---|---|---|
| **S1** | **Dua mekanisme terpisah, keduanya dipertahankan** | Live Rule Alert tetap untuk pemantauan langsung, tanpa perubahan. Session Indication Alert menjadi ALERT di Session Report (Indication Summary). Keduanya punya nama berbeda. Status Live Rule Alert tetap dicatat di laporan sebagai keterangan, bukan sebagai ALERT. |
| S2 | Session Indication Alert menggantikan Live Rule Alert, juga untuk pemantauan langsung | Pop-up dan prioritas dihitung dari P_k sementara terhadap T_k |
| S3 | Session Report memakai Live Rule Alert sebagai ALERT (P1-5a lama) | **Tidak selaras** dengan R6; hanya dicantumkan untuk kelengkapan |
| S4 | Dua mekanisme terpisah, tetapi Live Rule Alert tidak ditampilkan di Session Report | Laporan hanya memuat Session Indication Alert |

## 1.3 Konsekuensi arsitektur

| Aspek | S1 | S2 | S4 |
|---|---|---|---|
| Kesesuaian R1–R6 | Sesuai | Sesuai untuk laporan, tetapi mengubah pemantauan | Sesuai |
| Perilaku pemantauan langsung | **Tidak berubah** | Berubah total. P_k sementara di awal sesi tidak stabil, karena jendela sesi masih pendek dan interval tanpa data bernilai 0, sehingga pop-up bisa muncul atau hilang. | Tidak berubah |
| Ketertelusuran ("mengapa pengawas mendapat pop-up?") | Terjaga: laporan menyimpan keduanya | Tidak relevan (hanya satu) | **Hilang**: laporan tidak menjelaskan pop-up yang dilihat pengawas |
| Isi snapshot (AL-5) | Session Indication Alert, T_k, versi T_k; status dan ambang Live Rule Alert (`min_count`, `window_s`) | Session Indication Alert dan T_k | Session Indication Alert dan T_k |
| G1 di rancangan Tahap 3 §5 ("dibaca dari aturan `cases`") | Arti G1 berubah: G1 = Session Indication Alert; status Live Rule Alert menjadi field terpisah | Sama | Sama |
| Jumlah ALERT di Overall Session Summary | Jumlah Session Indication Alert. Berbeda dari `rules_met` di ringkasan ujian, yang menghitung Live Rule Alert, sehingga perlu label berbeda. | Satu definisi | Jumlah Session Indication Alert |
| Kalibrasi | Tidak terpengaruh: kalibrasi tidak membaca ALERT mana pun | Tidak terpengaruh | Tidak terpengaruh |
| Rumus Phase 4 | Tetap | Tetap | Tetap |
| Ketergantungan sebelum implementasi | AL-2 (data kosong), AL-3 (T_k), AL-4, AL-5 | Sama, ditambah perubahan antarmuka pemantauan | Sama |

## 1.4 Risiko

| Risiko | S1 | Mitigasi (S1) |
|---|---|---|
| Dua status bertentangan untuk indikasi yang sama. Contoh: ponsel terlihat 5 detik memenuhi Live Rule Alert (`min_count: 1`), sedangkan P_k ≈ 0,0014 kemungkinan di bawah T_k. | Ada | Nama berbeda. Laporan menjelaskan bahwa Live Rule Alert = "kejadian muncul selama ujian" dan Session Indication Alert = "proporsi waktu sesi melewati ambang". Status Live Rule Alert ditampilkan sebagai keterangan, bukan ALERT. |
| Pengawas menganggap pop-up sama dengan ALERT laporan | Ada | Istilah antarmuka langsung ("memenuhi ambang") tidak diganti menjadi "ALERT" |
| Session Indication Alert tidak mendeteksi kejadian singkat tetapi penting | Ada (sifat P_k sebagai proporsi waktu) | Live Rule Alert tetap mendeteksinya selama ujian dan statusnya tercatat di laporan. Apakah ini cukup adalah bagian penilaian T_k (AL-3). |
| Status saat data kosong atau sebagian | Ada di semua pilihan | Menunggu AL-2. Usulan tiga status **belum disetujui**. |

Pada S2: risiko pop-up tidak stabil, perubahan alur kerja pengawas, dan hilangnya deteksi kejadian singkat selama ujian. Pada S4: hilangnya ketertelusuran.

## 1.5 Rekomendasi P1-5

**S1: dua mekanisme terpisah, keduanya dipertahankan, dengan nama berbeda.** Alasannya:
- memenuhi R1–R6 tanpa mengubah perilaku pemantauan langsung;
- menjaga ketertelusuran antara yang dilihat pengawas dan isi laporan;
- tidak menyentuh rumus Phase 4.

Implementasi Session Indication Alert tetap menunggu AL-2, AL-3, AL-4, dan AL-5.

Bila S1 disetujui, perlu penyesuaian dokumentasi: arti G1 di rancangan Tahap 3 §5, dan nama kedua mekanisme di Alignment §4. Penyesuaian ini dilakukan setelah keputusan.

**Status P1-5: DIPUTUSKAN = S1** (21 November 2026). Live Rule Alert dan Session Indication Alert dipertahankan sebagai dua mekanisme berbeda; Live Rule Alert tidak diubah. Implementasi Session Indication Alert tetap menunggu AL-2, AL-4, AL-5, nilai T_k, dan persetujuan Phase 6.

---

# Bagian 2: AL-3, sumber dan mekanisme threshold T_k

## 2.1 Hal yang menentukan makna T_k

1. **Skala.** P_k adalah proporsi waktu (0–1): detik aktif dibagi detik yang dapat dianalisis, dirata-rata berbobot atas interval 5 menit. T_k berada pada skala yang sama.
2. **Tidak bergantung pada `indicator_set`.** P_k satu indikasi dihitung dari indikasi itu saja, sehingga nilainya sama di V5 dan V5+A3. Karena itu **satu T_k per indikasi cukup**. Berbeda dengan kalibrator, yang bergantung pada himpunan karena memakai P_total.
3. **Dipengaruhi aturan data kosong Phase 4.** Interval tanpa data bernilai 0 dan tetap di penyebut, sehingga P_k pada sesi bercakupan rendah terdilusi. Bila T_k ditentukan tanpa memperhitungkan ini, maknanya bergeser antarsesi. Perlakuannya bagian AL-2; rumus Phase 4 tidak diubah.
4. **Tidak berlaku untuk indikasi yang dikecualikan** (tanpa persetujuan audio, `no_audio_data`, config). Untuk indikasi terdampak D4, perlakuannya menunggu K7 dan AL-4.

## 2.2 Pilihan sumber T_k

| Kode | Sumber | Cara penentuan |
|---|---|---|
| **A** | **Kebijakan Program Studi** | Program Studi menetapkan T_k per indikasi sebagai kebijakan ("perilaku X lebih dari θ waktu sesi perlu perhatian"). Dicatat dengan alasan, versi, dan tanggal. |
| **B** | **Data berlabel per indikasi** | T_k dipilih dari data berlabel: label per indikasi per sesi ("perilaku k benar terjadi secara bermakna"). Dipilih pada split penentuan, dievaluasi sekali pada split uji (sensitivitas, spesifisitas, PPV, dengan selang 95 % bootstrap peserta), dengan kriteria kelayakan yang disetujui lebih dahulu. Polanya mengikuti pola kalibrasi Tahap 3. |
| **C** | **Bertahap: A sebagai ambang sementara, B sebagai jalur validasi** | T_k awal dari kebijakan, diberi label jelas "ambang kebijakan, belum divalidasi data". Bila data berlabel per indikasi tersedia dan lolos evaluasi, T_k dapat direvisi lewat versi baru yang disetujui. |
| D | Distribusi populasi | T_k = persentil P_k di antara sesi (mis. 5 % teratas) |
| E | Diturunkan dari Live Rule Alert | T_k dibuat setara dengan `min_count` episode |

**D dan E tidak direkomendasikan:**
- **D** membuat ALERT seorang peserta bergantung pada peserta lain. Ambangnya bergeser setiap populasi berubah, dan persentase peserta yang ALERT ditentukan lebih dahulu, bukan oleh perilakunya. Ini bermasalah untuk keadilan dan untuk interpretasi.
- **E** mencampur dua besaran yang berbeda (jumlah episode dan proporsi waktu) sehingga menghapus alasan memisahkan kedua mekanisme di P1-5.

## 2.3 Konsekuensi arsitektur dan risiko

| Aspek | A: kebijakan | B: data berlabel | C: bertahap |
|---|---|---|---|
| Ketersediaan | Segera setelah Program Studi menetapkan | Setelah data berlabel per indikasi terkumpul dan dievaluasi (lama) | Segera (A); lalu revisi bila B tersedia |
| Dasar ilmiah | Penilaian ahli; **tidak tervalidasi** | Tervalidasi pada data, dengan ketidakpastian dilaporkan | Awalnya penilaian ahli, kemudian tervalidasi |
| Label di laporan | Wajib: "ambang kebijakan, belum divalidasi" | "ambang tervalidasi versi …" | Mengikuti asal versi T_k yang dipakai |
| Kebutuhan Tahap 4 | Tidak ada | **Label per indikasi wajib dikumpulkan.** Ini berbeda dari label tingkat sesi K1, sehingga beban pelabelan bertambah. | Sebaiknya label per indikasi dikumpulkan sejak Tahap 4, agar jalur B terbuka |
| Pemisahan data | — | Split penentuan dan split uji terpisah per peserta dan per sesi ujian (seperti C1), dan tidak boleh tumpang tindih dengan split kalibrasi bila dipakai bersama | Sama dengan B untuk jalur validasi |
| Risiko | Ambang arbitrer; sengketa; dapat dianggap "angka model" padahal kebijakan | Data kurang; perilaku jarang (mis. ponsel) sulit mencapai jumlah positif minimum per indikasi; tergantung definisi label | Dua jenis T_k sepanjang waktu; perlu versi yang tegas |
| Perubahan rumus Phase 4 | Tidak | Tidak | Tidak |

## 2.4 Mekanisme penetapan, berlaku untuk A, B, dan C

| Unsur | Usulan mekanisme (belum diputuskan) |
|---|---|
| **Lokasi** | Satu tempat yang dibaca saat finalisasi. Pilihannya: bagian baru `config.yaml` (seperti `session_summary.indicator_weights`), atau berkas threshold yang disetujui dan dikunci SHA-256 seperti C6. Pilihan lokasi adalah keputusan tersendiri. |
| **Validasi** | Nama indikasi dikenal; nilai di [0, 1]; tidak ada indikasi tanpa T_k bila Session Indication Alert diaktifkan. Bila tidak valid: gagal tertutup. Session Indication Alert tidak dihitung dan alasannya dicatat, sama dengan prinsip bobot (Phase 4) dan kalibrator (K6). Aturan pastinya keputusan tersendiri. |
| **Versi dan sidik** | Setiap himpunan T_k punya versi dan sidik (seperti sidik bobot T3). Dicatat di snapshot bersama asalnya: kebijakan atau tervalidasi. |
| **Persetujuan** | A: penetapan Program Studi tercatat (siapa dan kapan). B: hasil evaluasi dengan kriteria yang disetujui sebelumnya, ditambah persetujuan aktivasi. |
| **Pembekuan** | T_k, versi, asal, dan status Session Indication Alert dibekukan di snapshot final (AL-5). PDF membaca nilai beku (R5). Perubahan T_k kemudian tidak mengubah sesi yang sudah final. |
| **Tanpa backfill** | Sesi yang difinalisasi sebelum ada T_k menampilkan Session Indication Alert "Tidak tersedia"; tidak dihitung ulang |
| **Hubungan dengan AL-2** | Status saat data kosong atau sebagian diputuskan terpisah (AL-2). Usulan tiga status **belum disetujui**. T_k tidak menggantikan aturan ketersediaan data. |

## 2.5 Rekomendasi AL-3

**Sumber C (bertahap)**, dengan syarat:
1. T_k awal berasal dari **kebijakan Program Studi** yang tercatat. Laporan memberi label jelas "ambang kebijakan, belum divalidasi data".
2. Tahap 4 dirancang agar **mengumpulkan label per indikasi** selain label tingkat sesi (K1), supaya jalur validasi B terbuka. Beban pelabelan tambahan ini perlu disetujui di Tahap 4.
3. Revisi T_k berbasis data hanya lewat versi baru yang dievaluasi dan disetujui; tidak pernah mengubah sesi final.
4. **Lokasi dan aturan validasi** T_k diputuskan tersendiri sebelum implementasi.

Bila pemilik proyek tidak ingin ambang yang belum divalidasi muncul di laporan, pilihan konsisten berikutnya adalah **B**. Konsekuensinya, Session Indication Alert baru tersedia setelah data berlabel per indikasi terkumpul dan dievaluasi. Sampai saat itu, statusnya "Tidak tersedia" sesuai keputusan AL-2.

**Status AL-3: DIPUTUSKAN = C** (21 November 2026). T_k awal berasal dari kebijakan Program Studi yang terdokumentasi, kemudian divalidasi dengan data berlabel per indikasi. **Tidak ada nilai T_k yang ditetapkan.** Keputusan turunan (lokasi, aturan validasi, kriteria evaluasi validasi) masih terbuka.

---

# Bagian 3: Ringkasan untuk keputusan

| ID | Pilihan | Rekomendasi | Bergantung pada | Status |
|---|---|---|---|---|
| P1-5 | S1 / S2 / S3 / S4 | **S1**: dua mekanisme terpisah, keduanya dipertahankan, nama berbeda; Live Rule Alert tidak diubah | — (arah). Implementasi menunggu AL-2, AL-4, AL-5, nilai T_k. | **Diputuskan (21 November 2026)**: S1 |
| AL-3 | A / B / C / D / E | **C**: kebijakan Program Studi sebagai ambang awal berlabel "belum divalidasi", dengan jalur validasi data (label per indikasi di Tahap 4) | P1-5; AL-2; lokasi dan validasi T_k (keputusan turunan) | **Diputuskan (21 November 2026)**: C (tanpa nilai T_k) |
| Turunan AL-3 | Lokasi T_k (config atau berkas yang dikunci), aturan validasi, kriteria evaluasi bila B | Diputuskan setelah arah AL-3 | — | Belum diputuskan |
| Dampak ke Tahap 4 | Label per indikasi | Diperlukan karena AL-3 = C | AL-3 | Mengikuti AL-3 = C: Tahap 4 perlu memuat label per indikasi (rincian dan beban pelabelan diajukan di Tahap 4) |

**Yang tidak berubah oleh pilihan mana pun:**
- rumus Phase 4 (P_k, P_total, bobot, penyebut, aturan data kosong, cakupan);
- snapshot finalisasi yang sudah ada (hanya bertambah isi bila AL-5 disetujui);
- kalibrasi Tahap 3;
- Live Rule Alert, kecuali dipilih S2;
- keputusan yang sudah diterima.

## Batas pekerjaan

- Analisis keputusan saja.
- Tidak ada perubahan kode, konfigurasi, database, data, dataset, atau perilaku sistem, dan tidak ada commit.
- Usulan tiga status ALERT tidak disetujui.
- Tidak ada nilai T_k yang ditetapkan.
- Phase 5 Tahap 4 dan Phase 6 belum dimulai.
