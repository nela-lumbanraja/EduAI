# Session Report: Analisis Lanjutan AL-3c (Bentuk Label), OS-1 (Status Keseluruhan), K-b (Sidik T_k), dan Kesiapan Tahap 4

Tanggal: 21 November 2026 · Status: **AL-3c, OS-1, dan K-b DIPUTUSKAN pemilik proyek (21 November 2026): AL-3c = G-c bertahap, OS-1 = O1, K-b = KB-1. Phase 5 Tahap 4 disetujui dimulai untuk evaluasi dan perancangan saja.** Tidak ada nilai T_k yang ditetapkan; tidak ada persetujuan Phase 6 atau implementasi. Rincian AL-3c (pedoman pelabelan, proporsi subsampel, kriteria kesepakatan antarpelabel) tetap harus dirancang dan dievaluasi sebelum Tahap 4 ditutup. *Status awal: "Analisis untuk keputusan pemilik proyek. AL-3c, OS-1, dan pilihan K-b BELUM DISETUJUI."*

**Batas pekerjaan:**
- Tidak ada perubahan kode, konfigurasi runtime, `.env`, database, data, dataset, atau perilaku sistem, dan tidak ada commit.
- Tahap 4 dan Phase 6 belum dimulai.
- Tidak ada nilai T_k yang ditetapkan.
- Keputusan Phase 4 dan Live Rule Alert tidak diubah.
- Tidak ada aturan NORMAL/ALERT baru.
- Rekomendasi di bawah **bukan** keputusan.

**Keputusan berlaku yang menjadi dasar:**
- P1-5 = S1 (Live Rule Alert dan Session Indication Alert terpisah);
- AL-3 = C (T_k awal dari kebijakan Program Studi, lalu divalidasi dengan data berlabel per indikasi);
- K1 (target sesi, κ ≥ 0,6), K3, K5, C1–C7;
- rumus dan snapshot Phase 4.

**Dokumen dan alat yang dirujuk (dibaca saja):**
- `EDUAI_SESSION_REPORT_CHECKPOINT_AL3_DERIVED.md` §4.3;
- `EDUAI_SESSION_REPORT_PHASE5_PLAN.md` §3;
- `EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md`;
- `EVALUATION_PROTOCOL.md` (protokol evaluasi deteksi yang sudah ada);
- `ai/eduai-ai/scripts/label_agreement.py`, `evaluate.py`;
- `ai/eduai-ai/labels.csv` (format label rentang).

---

## 1. AL-3c: bentuk label per indikasi

### 1.1 Tiga bentuk secara konkret

| | **G-a: label biner per indikasi per sesi** | **G-b: label rentang waktu per indikasi** | **G-c: keduanya** |
|---|---|---|---|
| Satu label berisi | Sesi, indikasi k, nilai 0/1: "perilaku k terjadi **secara bermakna** dan perlu ditindaklanjuti" menurut pedoman tertulis | Sesi/video, indikasi k, `start_s`, `end_s`, catatan: setiap kemunculan perilaku k. Format ini **sudah dipakai** di `labels.csv` (`video,indicator,start_s,end_s,…`) dan oleh `label_agreement.py`/`evaluate.py`. | Keduanya untuk sesi yang sama |
| Per sesi menghasilkan | 5 (V5) atau 8 (V5+A3) nilai biner | Daftar rentang per indikasi. Dari situ dapat diturunkan: durasi perilaku k, **proporsi referensi** P*_k (durasi dibagi waktu yang dapat dianalisis), kehadiran perilaku (ada/tidak), dan label sesi K1. | Semua di kiri |
| Kesepakatan pelabel | κ per indikasi atas keputusan biner per sesi (satuan: sesi) | κ per indikasi atas segmen 1 detik (protokol yang ada: target κ ≥ 0,70), ditambah penyelesaian batas waktu dan adjudikasi | Keduanya |
| Yang dapat divalidasi | **Validitas ambang**: apakah Session Indication Alert (P_k ≥ T_k) sejalan dengan penilaian manusia bahwa perilaku itu bermakna | **Validitas pengukuran**: seberapa dekat P_k sistem dengan P*_k referensi (selisih, bias, korelasi), dan apakah P_k ≥ T_k sama dengan P*_k ≥ T_k. Tidak menjawab apakah T_k itu sendiri bermakna. | Keduanya |

**Perbedaan pokok:**
- **G-a** menilai **apakah ambangnya tepat**. Dalam AL-3 = C, inilah inti "validasi T_k kebijakan".
- **G-b** menilai **apakah P_k mengukur dengan benar**. Ini prasyarat agar ALERT dari P_k bermakna, tetapi tidak menilai kebijakan T_k.

### 1.2 Kebutuhan pelabelan dan beban anotasi

| Aspek | G-a | G-b | G-c |
|---|---|---|---|
| Pekerjaan pelabel per sesi | Menonton rekaman penuh (memang sudah diperlukan untuk K1), lalu memberi 5–8 penilaian | Menandai awal dan akhir **setiap** kemunculan setiap indikasi. Untuk perilaku sering seperti menoleh, bisa puluhan rentang per sesi. Biasanya perlu lebih dari satu kali tonton. | Penjumlahan keduanya |
| Beban relatif (perkiraan kualitatif) | Rendah di atas K1 | **Tinggi**: beberapa kali durasi sesi per pelabel. Angka pastinya belum diukur; perlu uji coba. | Tertinggi |
| Indikasi suara (V5+A3) | Perlu rekaman audio penelitian | Perlu rekaman audio dan anotasi rentang suara (bisikan, suara kertas), yang lebih sulit dari video | Sama |
| Pedoman | Definisi operasional "bermakna" per indikasi. **Subjektif dan rawan bias:** pelabel tidak boleh melihat P_k, T_k, maupun keluaran sistem. | Definisi awal/akhir perilaku. Contoh sudah ada di protokol: `HEAD_TURN` dimulai saat hidung melewati tepi bahu. | Keduanya |
| Alat | Formulir sederhana; κ dengan `eval_stats.cohen_kappa` | **Sudah ada**: `label_agreement.py` (κ per segmen, pemasangan, adjudikasi) dan `evaluate.py` | Sebagian sudah ada |
| Risiko kesepakatan | κ dapat rendah karena "bermakna" bergantung penilaian | Batas waktu berbeda antarpelabel; sudah ditangani protokol (≤ 1 detik dirata-rata, selebihnya adjudikasi) | Keduanya |

### 1.3 Validitas evaluasi

| | G-a | G-b | G-c |
|---|---|---|---|
| Menilai T_k kebijakan (inti AL-3 = C) | **Ya, langsung** | Tidak langsung. Hanya menilai kecocokan P_k dengan referensi pada T_k yang sama. | Ya |
| Menilai mutu P_k | Tidak | **Ya** | Ya |
| Bila G-a gagal, membedakan penyebabnya | Tidak dapat: P_k salah ukur, atau T_k salah tempat? | — | **Dapat**: G-b menunjukkan apakah P_k akurat, G-a menunjukkan apakah ambangnya tepat |
| Hubungan dengan target sesi K1 | K1 tetap dilabeli terpisah. "Bermakna" (G-a) tidak sama dengan "terjadi" (K1), sehingga Y sesi tidak dapat diturunkan dari G-a. | **K1 dapat diturunkan secara deterministik**: Y = 1 bila ada rentang perilaku teramati di daftar indikasi. Ini mengurangi pelabelan terpisah dan menjamin definisi Y konsisten. | K1 dari G-b |
| Perilaku jarang (ponsel, buku) | Sedikit sesi positif per indikasi, sehingga sulit mencapai jumlah minimum | Jumlah **kejadian** lebih banyak dari jumlah sesi. Protokol yang ada menetapkan ≥ 30 kejadian positif per indikasi di set uji untuk evaluasi deteksi. | — |

### 1.4 Konsekuensi terhadap rancangan kalibrasi (Tahap 3)

Mekanisme kalibrasi **tidak berubah** dalam ketiga pilihan:
- masukan tetap R = P_total dengan label sesi Y;
- K1, K5, C1–C7 tetap;
- kalibrasi tidak membaca T_k maupun ALERT (P1-5 = S1).

Yang berbeda hanya **asal Y**:

| | Asal Y (K1) | Konsekuensi |
|---|---|---|
| G-a | Dilabeli terpisah (penilaian tingkat sesi) | Dua pedoman (Y sesi dan G-a). Risiko keduanya tidak selaras. |
| G-b | **Diturunkan** dari rentang | Satu sumber kebenaran. κ K1 (0,6, tingkat sesi) dan κ segmen (0,70, protokol) perlu diselaraskan, karena keduanya ambang kesepakatan pada satuan yang berbeda. |
| G-c | Dari G-b; G-a untuk validasi T_k | Sama dengan G-b, ditambah G-a |

Pemisahan data (C1, lintas `indicator_set`), registri test split, dan aturan konsumsi test split berlaku sama untuk evaluasi T_k dan kalibrasi. Penempatan split dipakai satu untuk seluruh dataset.

### 1.5 Kelayakan dan ketersediaan data saat ini

- **Data berlabel nyata hampir tidak ada.** `labels.csv` berisi 2 baris rentang dan 1 baris rusak (audit Phase 1). Data produksi adalah data uji coba pengembang.
- Infrastruktur G-b **sudah ada** (format, alat kesepakatan, alat evaluasi, protokol). Infrastruktur G-a belum ada, tetapi sederhana.
- Beban G-b tinggi dan belum diukur. Indikasi suara menambah kebutuhan rekaman audio penelitian (terkait P1-4).

### 1.6 Pilihan untuk diputuskan

| Pilihan | Isi | Konsekuensi utama |
|---|---|---|
| **G-a** | Hanya label biner per indikasi per sesi | Murah; langsung menilai T_k. Tidak dapat membedakan kesalahan P_k dari kesalahan T_k. K1 dilabeli terpisah. |
| **G-b** | Hanya label rentang | Memakai protokol dan alat yang ada; K1 dapat diturunkan; menilai mutu P_k. **Tidak** menilai apakah T_k kebijakan bermakna, sehingga tujuan validasi AL-3 = C hanya sebagian tercapai. Beban tinggi. |
| **G-c penuh** | Keduanya untuk semua sesi berlabel | Paling lengkap; beban tertinggi |
| **G-c bertahap** | G-a untuk **semua** sesi berlabel; G-b untuk **subsampel** terencana, mis. semua sesi yang G-a-nya positif ditambah sampel acak sesi negatif, dengan proporsi ditetapkan di Tahap 4 | Menilai T_k (G-a) dan mutu P_k (G-b subsampel) dengan beban terkendali. **Kekurangan:** K1 tidak dapat diturunkan dari G-b untuk semua sesi, sehingga K1 tetap perlu dilabeli untuk sesi di luar subsampel, dan desain subsampel harus dicatat agar estimasi tidak bias. |

### 1.7 Rekomendasi AL-3c (belum disetujui)

**G-c bertahap.** Alasannya:
1. AL-3 = C menuntut validasi **T_k kebijakan**, dan itu memerlukan G-a. Tanpa G-a, validasi hanya menilai pengukuran, bukan ambang.
2. G-b diperlukan untuk menafsirkan kegagalan G-a dan menilai mutu P_k. G-b dapat memakai protokol dan alat yang sudah ada, tetapi bebannya tinggi, sehingga subsampel lebih layak dengan data yang masih nol.
3. Kalibrasi Tahap 3 tidak terpengaruh.

**Alternatif konsisten:** bila beban pelabelan bukan kendala, **G-c penuh** lebih baik, karena K1 dapat diturunkan dari G-b untuk semua sesi. Bila anggaran sangat terbatas, **G-a** adalah minimum yang masih melayani AL-3 = C.

Proporsi subsampel, pedoman "bermakna" per indikasi, dan penyelarasan ambang κ (0,6 vs 0,70) dirinci di Tahap 4.

---

## 2. OS-1: status Overall Session Summary

### 2.1 Lima hal yang berbeda

| Hal | Definisi yang berlaku | Status keputusan | Sifat |
|---|---|---|---|
| **Skor agregasi** P_total | Σ v_k P_k / Σ v_k atas `weights_used` (Phase 4) | Diterima | Angka proporsi waktu berbobot; bukan probabilitas; **tidak menggantikan ALERT per indikasi** (R3) |
| **Jumlah Session Indication Alert** (G2) | Banyaknya indikasi dengan Session Indication Alert | Arti diterima (S1); implementasi menunggu T_k, AL-2, AL-5 | Ringkasan hitungan dari Indication Summary |
| **Status kalibrasi** | `not_calibrated`/`calibrated`, probabilitas, alasan (Tahap 3) | Diterima | Status ketersediaan probabilitas, bukan status perilaku |
| **Catatan cakupan** | `coverage`, `audio_coverage`, `coverage_note` saat cakupan 0 % | Diterima | Status ketersediaan data, bukan status perilaku |
| **Status keseluruhan sesi** | **Tidak didefinisikan** di rancangan mana pun | **OS-1, belum diputuskan** | — |

### 2.2 Pilihan mekanisme status keseluruhan

Tidak satu pun dianggap harus ada.

| Pilihan | Isi | Konsekuensi | Risiko |
|---|---|---|---|
| **O1: tidak ada status keseluruhan** | Overall Session Summary menampilkan P_total, durasi, cakupan, jumlah Session Indication Alert, dan status kalibrasi, masing-masing dengan labelnya sendiri, tanpa satu status gabungan | Tidak perlu aturan atau ambang baru; sepenuhnya sesuai R3; tidak bergantung AL-2 | Pembaca harus membaca beberapa angka; tidak ada "kesimpulan satu kata" |
| **O2: status ketersediaan data sesi** | Satu status yang hanya menyatakan **kelengkapan data**, mis. data lengkap / sebagian / tidak tersedia, dari cakupan, D4, dan status kalibrasi. Bukan penilaian perilaku. | Membantu menafsirkan angka lain; tidak memerlukan T_k | Memerlukan aturan batas "lengkap" atau "sebagian" (keputusan baru, terkait AL-2 dan AL-4). Bisa disalahbaca sebagai penilaian perilaku bila namanya tidak jelas. |
| **O3: status turunan dari Session Indication Alert** | Mis. "terdapat ≥ 1 indikasi ALERT" / "tidak terdapat indikasi ALERT" / "tidak tersedia" | Tidak memerlukan ambang baru selain T_k; konsisten dengan ALERT per indikasi | Bergantung AL-2 dan T_k. "Tidak terdapat indikasi ALERT" **tidak boleh** dinamai NORMAL atau dibaca "bersih", karena cakupan bisa rendah atau indikasi dikecualikan. Aturan "≥ 1" tetap aturan baru. |
| O4: ambang pada P_total (T_total) | ALERT keseluruhan bila P_total ≥ T_total | Memerlukan ambang baru | **Bertentangan dengan semangat R3**: satu indikasi tinggi terdilusi oleh indikasi lain dalam rata-rata, sehingga status keseluruhan bisa "rendah" padahal ada ALERT per indikasi. Tidak direkomendasikan. |
| O5: pita probabilitas terkalibrasi | Mis. probabilitas tinggi/rendah | Hanya bila ada kalibrator; memerlukan ambang pita baru | Saat ini tidak ada kalibrator; pita adalah ambang baru; risiko dibaca sebagai probabilitas kecurangan (D-R1). Tidak direkomendasikan sekarang. |

### 2.3 Rekomendasi OS-1 (belum disetujui)

**O1 sekarang.** Overall Session Summary menampilkan komponennya secara terpisah, tanpa status gabungan. Tidak ada aturan baru dan tidak ada risiko status yang menutupi ALERT per indikasi.

Bila kelak dibutuhkan satu status ringkas, **O2** (ketersediaan data) atau **O3** (turunan ALERT, tanpa kata NORMAL) dapat dievaluasi setelah AL-2 dan T_k diputuskan. **O4 dan O5 tidak direkomendasikan.**

---

## 3. K-b: sidik T_k di field terpisah

### 3.1 Masalah (dari laporan checkpoint)

`config_version` berbentuk `"<version>;w=<sidik bobot>"`, dan `calibration.weights_fingerprint` mengambil **seluruh teks setelah `;` pertama**. Menambahkan `;t=<sidik T_k>` akan membuat `weights_mismatch` selalu terpicu untuk kalibrator yang sah.

### 3.2 Pilihan

| Pilihan | Isi | Konsekuensi |
|---|---|---|
| **KB-1: field terpisah** | Snapshot (metadata JSON baris `*`, tanpa kolom baru) menyimpan `thresholds_version`, `thresholds_fingerprint`, dan `thresholds_source` (`kebijakan`/`tervalidasi`), serta per indikasi T_k yang dipakai. `config_version` tidak berubah. | Lihat §3.3 |
| KB-2: digabung ke `config_version`, parser diubah | `config_version = "<version>;w=…;t=…"`, dan `weights_fingerprint` diubah agar mengambil bagian `w=` saja | Perubahan kode Tahap 3 yang sudah diterima. Setiap perubahan T_k mengubah `config_version`, sehingga data kalibrasi lama dan baru dianggap berbeda konfigurasi di skrip (`config_version_berbeda`). |

### 3.3 Konsekuensi KB-1 bila dipilih

| Aspek | Konsekuensi |
|---|---|
| Kalibrasi (Tahap 3) | **Tidak terpengaruh.** Parser dan `config_version` tetap. Kalibrator yang sah tetap sah saat T_k berubah. Ini **benar secara desain**: kalibrasi memakai P_total dan tidak membaca ALERT (P1-5 = S1), sehingga T_k memang bukan bagian identitas kalibrator. |
| AL-3 = C | Konsisten. Revisi T_k (kebijakan → tervalidasi) hanya mengubah `thresholds_version`/`thresholds_fingerprint`, tanpa menyentuh bobot, skor, atau kalibrator. |
| Ketertelusuran laporan | Identitas konfigurasi laporan menjadi gabungan: `algo_version` + `config_version` (bobot) + `thresholds_fingerprint` (T_k) + `live_rules_fingerprint` (threshold Live Rule Alert, bila G4 disetujui) + field kalibrasi. Dokumentasi harus menyatakan bahwa `config_version` saja **tidak lagi** menggambarkan seluruh konfigurasi laporan. |
| Dataset kalibrasi | Tidak perlu kolom T_k (T_k tidak memengaruhi R). Dataset evaluasi T_k (AL-3c) **perlu** mencatat `thresholds_fingerprint` yang dievaluasi. |
| Snapshot | Hanya metadata JSON bertambah, tanpa kolom baru dan migrasi; bagian dari AL-5 yang belum disetujui |
| Kode | Nanti: kode baru untuk menghitung dan menyimpan sidik T_k. **Parser tidak diubah.** Tidak ada perubahan sekarang. |
| Live Rule Alert | Tidak berubah. Sidik threshold-nya, bila disimpan (G4), juga field terpisah. |

### 3.4 Rekomendasi K-b (belum disetujui)

**KB-1.** Tidak mengubah kode yang sudah diterima, tidak mengikat kalibrator pada T_k, dan konsisten dengan S1 dan C. Pelaksanaannya bagian AL-5 (isi snapshot), yang masih terbuka.

---

## 4. Kesiapan Tahap 4

Tahap 4 adalah dokumen kebutuhan dataset (rencana Phase 5 L5).

### 4.1 Wajib sebelum Tahap 4 **dimulai**

| # | Keputusan | Status | Alasan wajib |
|---|---|---|---|
| W1 | Persetujuan eksplisit memulai Tahap 4 | Belum | Ketentuan proyek |
| W2 | **AL-3c: bentuk label per indikasi** (G-a / G-b / G-c penuh / G-c bertahap) | Belum | Menentukan isi protokol pelabelan, beban anotasi, dan apakah K1 diturunkan atau dilabeli terpisah. **Alternatif:** pemilik proyek mengizinkan Tahap 4 dimulai dengan AL-3c diajukan di dalamnya sebagai keputusan; dengan begitu W2 berpindah ke daftar "sebelum ditutup". |

Sudah terpenuhi: AL-3 = C, K1, K3, K5, C1 (termasuk pemisahan lintas `indicator_set` yang diminta), dan aturan registri test split (Tahap 3).

### 4.2 Wajib sebelum Tahap 4 **ditutup**

| # | Keputusan | Status |
|---|---|---|
| T1 | P1-4: prioritas V5 / V5+A3 | Belum diputuskan |
| T2 | Turunan P1-4: definisi Y untuk V5+A3; persetujuan audio penelitian; cara pengumpulan audio; penyimpanan, akses, dan penghapusan rekaman; pengukuran tingkat persetujuan | Belum diputuskan |
| T3 | Rincian AL-3c: pedoman "bermakna" per indikasi (bila G-a); proporsi subsampel (bila G-c bertahap); penyelarasan ambang κ (0,6 tingkat sesi vs 0,70 segmen) | Belum diputuskan |
| T4 | Bentuk kriteria evaluasi T_k dan jumlah minimum per indikasi (AL-3c). Nilai minimum s_min/p_min boleh tetap terbuka sampai evaluasi, tetapi harus ditetapkan **sebelum** melihat test split. | Belum diputuskan |
| T5 | Lokasi tetap registri test split dan artefak dataset (Tahap 3 §2.10.1 menyerahkannya ke Tahap 4) | Belum diputuskan |
| T6 | Aturan inklusi sesi bercakupan rendah untuk evaluasi T_k (sementara ikut K2; final mengikuti AL-2) | Belum diputuskan |

### 4.3 Wajib sebelum **Phase 6**

| # | Keputusan | Status |
|---|---|---|
| P1 | Nilai T_k kebijakan oleh Program Studi (AL-3 = C) | Belum ditetapkan |
| P2 | AL-3a (lokasi T_k), AL-3b (aturan validasi T_k) | Belum disetujui |
| P3 | K-b (KB-1 atau KB-2) | Belum disetujui |
| P4 | AL-2, termasuk usulan tiga status | Belum disetujui |
| P5 | AL-1, AL-4, AL-5 (G1–G4), AL-6, K7 | Terbuka |
| P6 | OS-1 | Belum diputuskan |
| P7 | Persetujuan Phase 6 | Belum |

**Jalur terpisah,** tidak menghalangi Tahap 4 maupun rancangan Phase 6: persetujuan migrasi database produksi dan keputusan commit.

---

## 5. Ringkasan keputusan yang diminta

Semua **belum disetujui**.

| ID | Pilihan | Rekomendasi | Kapan diperlukan |
|---|---|---|---|
| **AL-3c** | G-a / G-b / G-c penuh / G-c bertahap | **G-c bertahap**: G-a untuk semua sesi berlabel; G-b pada subsampel terencana untuk membedakan masalah pengukuran P_k dari masalah penetapan ambang T_k | Sebelum Tahap 4 dimulai | **Diputuskan (21 November 2026)**: **G-c bertahap**; rincian dirancang di Tahap 4 |
| **OS-1** | O1 / O2 / O3 / O4 / O5 | **O1**: tanpa status NORMAL/ALERT gabungan; P_total, jumlah Session Indication Alert, status kalibrasi, dan catatan cakupan ditampilkan terpisah | Sebelum Phase 6 | **Diputuskan (21 November 2026)**: **O1**. Tidak ada aturan status keseluruhan baru tanpa keputusan pemilik proyek. |
| **K-b** | KB-1 / KB-2 | **KB-1**: sidik T_k di field terpisah; parser dan `config_version` tidak diubah | Sebelum Phase 6 (bagian AL-5) | **Diputuskan (21 November 2026)**: **KB-1**; konsekuensi bahwa `config_version` tidak mewakili seluruh konfigurasi laporan didokumentasikan (Alignment §6.2) |
| Mulai Tahap 4 | Ya / belum | — | — | **Disetujui (21 November 2026)** untuk evaluasi dan perancangan saja; P1-4 dan turunannya diajukan di dalam Tahap 4; bukan persetujuan Phase 6 |

## 6. Konfirmasi

- Dokumen ini baru. Tidak ada dokumen lain, kode, konfigurasi runtime, `.env`, database, data, atau dataset yang diubah.
- Tidak ada commit.
- Tidak ada nilai T_k, tidak ada aturan NORMAL/ALERT baru, dan Live Rule Alert tidak diubah.
- Tahap 4 belum dimulai.
