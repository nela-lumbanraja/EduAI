# Session Report Phase 5, Tahap 4: Paket Keputusan H2 (Label, Komposisi Dataset, TK-1, P1-4)

Tanggal: 21 November 2026 · Status: **H2-1 sampai H2-7 DISETUJUI pemilik proyek (21 November 2026) sebagai dasar melanjutkan Tahap 4, dengan batasan yang tercatat di §7.** Hanya analisis, desain, dan dokumentasi. Belum disetujui: perubahan kode atau konfigurasi runtime, database atau skema, implementasi DC-4 atau field `target_population`, nilai T_k, perubahan Live Rule Alert, perekaman, pemakaian data tanpa kejelasan izin, Phase 6. *Status awal: "Titik henti H2. Semua pilihan di dokumen ini BELUM DISETUJUI."*

**Batas pekerjaan:**
- Tidak ada perubahan kode, konfigurasi runtime, `.env`, database, data, atau dataset, dan tidak ada commit.
- Tidak ada perekaman. Data lama yang asal persetujuannya belum jelas tidak dipakai.
- Tidak ada nilai T_k yang ditetapkan, dan Live Rule Alert tidak diubah.
- Phase 6 belum dimulai.
- Komposisi dataset final **tidak** ditetapkan. Probabilitas kalibrasi **tidak** dinyatakan mewakili prevalensi ujian nyata.

**Cakupan H2** (rencana Tahap 4 §6):
- WP1: acuan;
- WP2: rancangan label;
- WP4: TK-1 dan komposisi dataset;
- WP7: P1-4.

WP3, WP5, WP6, WP8, WP9, dan WP10 dikerjakan setelah H2 disetujui, karena bergantung pada keputusan di sini.

---

## 1. WP1: acuan yang dipakai

| Acuan | Isi yang relevan |
|---|---|
| Keputusan berlaku | K1, K3, K5, C1, C2, P1 §9 (pemisahan lintas himpunan), AL-3 = C, AL-3c = G-c bertahap, OS-1 = O1, K-b = KB-1 |
| Masukan skrip kalibrasi (Tahap 3, ruang lingkup §2.2) | `exam_id, student_id, label, label_agreed, R, coverage, audio_coverage, indicator_set, weights_fingerprint, algo_version, d4_status, split, models_fingerprint, config_version`. **Tanpa bobot sampel**: setiap baris berbobot sama. |
| Kriteria kalibrasi | E1–E6; bootstrap peserta B = 2.000; K5 per kalibrator |
| `EVALUATION_PROTOCOL.md` (v0.1, usulan) | Pilot relawan: sesi wajar 30–45 menit dan sesi skenario sekitar 20 menit; pelabelan rentang dua pelabel, κ ≥ 0,70 per segmen; pemisahan per orang; etika (§6) |
| Alat yang ada | `label_agreement.py` (κ segmen, adjudikasi), `evaluate.py` (deteksi), `eval_stats.py` (Wilson, Poisson, κ, AUROC, AP) |
| Data yang ada | Tidak ada data berlabel yang layak (`labels.csv` 2 baris). Data lama (`dataset_raw/`, `pilot/p01.mp4`) tidak dipakai: asal persetujuannya belum jelas. |

---

## 2. Konflik metodologis tambahan: prevalensi Y menurut definisi K1 (TK-10)

**Ditemukan saat WP4. Tidak diselesaikan sepihak.**

K1 (disetujui): *Y = 1 bila sesi memuat sedikitnya satu perilaku teramati yang termasuk daftar indikasi Session Summary.*

- Daftar indikasi memuat perilaku yang **juga terjadi pada ujian wajar**. Protokol evaluasi sendiri mencatat perilaku wajar yang mirip:
  - HEAD_TURN: melihat kertas atau meregangkan leher;
  - FACE_ABSENT: menunduk menulis, bersandar;
  - OTHER_VOICE: suara di sekitar.
- Bila "teramati" berarti "terjadi sekali saja", Y = 1 dapat muncul pada **hampir semua sesi wajar**, sehingga:
  - prevalensi Y mendekati 1, dan E5 (≥ 100 negatif di test) sulit dipenuhi;
  - probabilitas terkalibrasi menjadi hampir selalu tinggi dan **tidak informatif**;
  - makna "probabilitas sesi memenuhi definisi perilaku teramati" menjadi lemah.
- Arah sebaliknya: bila "teramati" diartikan sesuai pedoman operasional per indikasi (mis. HEAD_TURN hanya bila ≥ 30° selama ≥ 3 detik, seperti definisi deteksi), prevalensinya bergantung pada pedoman itu.

**Konsekuensi:** pedoman operasional "perilaku teramati" untuk K1 **menentukan** prevalensi Y. Ini harus diputuskan bersama bentuk label (§3). Keputusan K1 tidak diubah di sini. Yang diajukan adalah **penafsiran operasionalnya**.

---

## 3. WP2: rancangan label (usulan, belum disetujui)

### 3.1 Tiga lapisan label

| Lapisan | Satuan | Isi | Siapa dan bagaimana | Dipakai untuk |
|---|---|---|---|---|
| **K1**: label sesi | Sesi | Y ∈ {0, 1} | Dua pelabel independen, rekaman penuh, buta terhadap keluaran sistem | Kalibrasi (Tahap 3) |
| **G-a**: label per indikasi | Sesi × indikasi | (i) **kehadiran** perilaku k menurut definisi operasional (ada/tidak); (ii) **bermakna** (ya/tidak) menurut pedoman "bermakna" | Pelabel yang sama dalam satu kali tonton; buta terhadap P_k, T_k, dan keluaran sistem | (ii) validasi T_k (AL-3 = C); (i) menurunkan K1 |
| **G-b**: label rentang | Kemunculan × indikasi | `start_s`, `end_s` (format `labels.csv` yang ada) | Prosedur protokol §3 (dua pelabel, adjudikasi, alat `label_agreement.py`) | Subsampel: mutu pengukuran P_k, pembeda masalah P_k vs T_k, evaluasi deteksi |

**Usulan TK-6:** K1 **diturunkan** dari G-a (i): Y = 1 bila ada sedikitnya satu indikasi berstatus "ada". Dengan begitu tidak ada pelabelan sesi terpisah, dan definisi Y selalu selaras dengan definisi operasional per indikasi (yang juga menjawab TK-10). Ini **bukan perubahan K1**, melainkan cara memenuhinya. Perlu persetujuan.

### 3.2 Pedoman (struktur; isi final disusun bersama Program Studi)

| Bagian pedoman | Isi |
|---|---|
| Definisi operasional "ada" per indikasi | Diselaraskan dengan pedoman rentang protokol §3 (mis. HEAD_TURN: hidung melewati tepi bahu, durasi minimum). Satu sumber definisi untuk G-a (i) dan G-b. |
| Definisi "bermakna" per indikasi | Kriteria **kualitatif** dari Program Studi (mis. lama, berulang, disertai objek), **tidak** berupa ambang proporsi waktu. Bila berupa proporsi waktu, pelabel akan meniru T_k dan validasi menjadi sirkular. |
| Larangan | Pelabel tidak melihat keluaran EduAI, P_k, T_k, atau status ALERT apa pun. Pedoman dibekukan sebelum pelabelan; uji coba pada beberapa sesi seperti protokol. |
| Indikasi suara (V5+A3) | Memerlukan rekaman audio penelitian (§5) |

### 3.3 Kesepakatan antarpelabel (TK-5)

| Label | Satuan | Ambang usulan | Dasar |
|---|---|---|---|
| K1 | Sesi | κ ≥ 0,6 | **Sudah diputuskan** (K1). Bila K1 diturunkan dari G-a (i), κ dihitung atas Y turunan. |
| G-a (i) kehadiran | Sesi × indikasi | κ ≥ 0,6 per indikasi | Satuan sama dengan K1 (sesi) |
| G-a (ii) bermakna | Sesi × indikasi | κ ≥ 0,6 per indikasi | Sama; penilaian lebih subjektif, sehingga pedoman perlu diuji coba |
| G-b rentang | Segmen 1 detik | κ ≥ 0,70 | Protokol yang ada; satuan berbeda |

Ambang yang berbeda **dibenarkan oleh satuan yang berbeda**: keputusan sesi vs segmen detik. Bila κ di bawah ambang, pedoman diperbaiki dan dilabeli ulang (seperti protokol). Ketidaksepakatan diselesaikan pelabel ketiga, juga buta terhadap keluaran sistem.

### 3.4 Subsampel G-b (AL-3c)

- **Usulan bentuk:** semua sesi yang G-a (ii) "bermakna" pada sedikitnya satu indikasi, ditambah sampel acak sesi lainnya dengan peluang terpilih **f** yang dicatat.
- Proporsi f diputuskan di WP6 setelah beban pelabelan diukur pada uji coba.
- Peluang terpilih setiap sesi **wajib dicatat**, agar estimasi mutu P_k dari subsampel dapat dibobot dan tidak bias.

---

## 4. WP4: analisis TK-1 dan komposisi dataset

### 4.1 Prevalensi pada tiga jenis data

| Jenis data | Prevalensi Y | Distribusi R di antara positif | Catatan |
|---|---|---|---|
| **Sesi skenario** (protokol §2.1: relawan diminta melakukan perilaku) | Ditentukan **rancangan kartu instruksi**, tinggi menurut konstruksinya | Perilaku cenderung jelas, panjang, berulang, sehingga R positif cenderung lebih tinggi daripada perilaku alami | Bagus untuk evaluasi deteksi dan G-b; **tidak mewakili** ujian |
| **Sesi wajar pilot** (relawan tanpa instruksi) | Tidak diketahui; bergantung definisi operasional (TK-10) | Lebih alami, tetapi relawan tidak berada dalam ujian bertaruhan nyata | Lebih dekat ke ujian, tetap bukan ujian nyata |
| **Sesi ujian nyata** | **Tidak diketahui.** Tidak ada label. EduAI tidak menyimpan rekaman penuh, hanya potongan bukti, jadi K1 dengan rekaman penuh tidak dapat dipenuhi dari data produksi. | Tidak diketahui | Populasi penggunaan sebenarnya |

Tidak ada data yang memungkinkan memperkirakan prevalensi ujian nyata saat ini. Dokumen ini **tidak** mengasumsikan angkanya.

### 4.2 Dampak perbedaan prevalensi pada Platt

Platt: P(Y=1 | R) = σ(aR + b). Bila populasi penggunaan berbeda dari populasi kalibrasi:

| Jenis pergeseran | Akibat | Dapat dikoreksi? |
|---|---|---|
| **Hanya prevalensi berubah** (*label shift*: sebaran R di antara positif dan di antara negatif tetap sama) | Hanya b yang bergeser: logit p_guna = logit p_kalibrasi + ln[π_guna/(1−π_guna)] − ln[π_kal/(1−π_kal)]. Bila π_kal > π_guna, probabilitas **terlalu tinggi** di semua R. | Ya, **bila π_guna diketahui** (koreksi prior). π_guna **tidak diketahui**. Estimasi dari R ujian nyata tanpa label (mis. EM, Saerens dkk. 2002) bergantung pada asumsi label shift murni dan memerlukan pemakaian data produksi. |
| **Sebaran R berubah** (perilaku skenario lebih jelas daripada alami; *covariate/concept shift*) | a dan b sama-sama tidak berlaku; bentuk hubungan R → Y bisa berbeda | Tidak dengan koreksi prior. Perlu data yang mirip populasi penggunaan. |
| **Keduanya** (paling mungkin bila memakai sesi skenario) | Probabilitas tidak dapat ditafsirkan untuk ujian nyata | Tidak |

**Akibat pada evaluasi E1–E6:** bila test split berasal dari populasi yang sama dengan calibration split (mis. sama-sama campuran skenario), E1–E6 bisa **lolos**. Kalibrator yang lolos itu tetap **salah terkalibrasi** untuk ujian nyata. Lolos E1–E6 hanya membuktikan kalibrasi **pada populasi data**, bukan pada populasi penggunaan.

### 4.3 Batas interpretasi skor kalibrasi

1. Probabilitas terkalibrasi bermakna: *P(Y = 1 | R) **pada populasi data kalibrasi***, dengan definisi Y operasional yang dipakai (K1, TK-10). Ia **bukan** prevalensi perilaku pada ujian nyata dan bukan probabilitas kecurangan (D-R1).
2. Bila populasi kalibrasi berbeda dari ujian nyata, tidak ada jaminan kalibrasi pada ujian nyata, walaupun E1–E6 lolos.
3. Karena itu, sebelum aktivasi (keputusan terpisah), dokumen dan laporan wajib menyatakan **populasi target** kalibrator. Usulan: tambahkan field `target_population` pada artefak kalibrator. Ini perubahan format yang memerlukan persetujuan terpisah; tidak dikerjakan sekarang.
4. Sampai ada bukti dari populasi penggunaan, istilah di laporan tetap **Indication Score (%)** (rencana Phase 5 §7.2). Probabilitas, bila kelak diaktifkan, disertai keterangan populasinya.

### 4.4 Pilihan rancangan dataset untuk mengurangi risiko pergeseran

| Pilihan | Isi | Kelebihan | Kekurangan / risiko |
|---|---|---|---|
| **DC-1** | Kalibrasi dan uji **hanya dari sesi wajar** (tanpa instruksi perilaku) | Prevalensi dan sebaran R lebih alami; tidak ada prevalensi buatan | Butuh banyak sesi untuk mencapai K5 (lihat §4.5); tetap bukan ujian nyata |
| **DC-2** | **Pemisahan tujuan:** sesi skenario **hanya** untuk evaluasi deteksi, G-b, dan validasi pengukuran P_k; kalibrasi dan uji kalibrasi **hanya** dari sesi wajar (DC-1). Validasi T_k (G-a) dari sesi wajar, dengan sesi skenario sebagai pelengkap yang dilaporkan terpisah. | Memanfaatkan sesi skenario tanpa mencemari kalibrasi; sejalan dengan protokol yang ada | Seperti DC-1 untuk jumlah sesi wajar |
| **DC-3** | Campuran, lalu **koreksi prior** dengan perkiraan π ujian nyata | Data lebih sedikit | π ujian nyata tidak diketahui; koreksi hanya sah untuk label shift murni, yang tidak berlaku bila ada sesi skenario; memerlukan data produksi |
| **DC-4** | Sesi wajar, tetapi **pemilihan sesi untuk dilabeli secara berstrata** (mis. menurut R atau G-a) dengan peluang pemilihan tercatat, lalu fit dan evaluasi **berbobot** (bobot = 1/peluang) | Lebih hemat pelabelan untuk mencapai jumlah positif; prevalensi populasi dipulihkan lewat bobot | Skrip Tahap 3 **belum** mendukung bobot, sehingga perlu perubahan kode dan kriteria (persetujuan terpisah); varians lebih besar; rancangan strata harus dikunci sebelum test split dilihat |
| DC-5 | Sesi ujian nyata dengan persetujuan riset | Paling dekat ke penggunaan | Memerlukan **rekaman penuh** untuk K1, yang tidak disimpan EduAI; perlu persetujuan riset dan etika khusus pada ujian bertaruhan; tidak layak saat ini |

### 4.5 Kelayakan jumlah sesi (rumus; bukan perkiraan)

Untuk satu kalibrator, K5 memerlukan ≥ 150 positif dan ≥ 150 negatif (50 + 100 per kelas), **setelah** penyaringan (cakupan, D4, kesepakatan label). Dengan prevalensi sesi wajar π (belum diketahui) dan fraksi sesi yang lolos penyaringan q:

- sesi berlabel yang diperlukan ≈ max(150/π, 150/(1−π)) / q.
- **Ilustrasi saja, bukan perkiraan:** π = 0,2 dan q = 0,8 → sekitar 940 sesi; π = 0,5 dan q = 0,8 → sekitar 375 sesi.
- Untuk V5 dan V5+A3 kebutuhannya **per himpunan**.
- C1 menambah syarat jumlah peserta dan sesi ujian yang cukup di kedua split.
- Sebagai pembanding, protokol pilot merancang ≥ 24 relawan. Kesenjangannya besar; WP6 menilainya setelah π dapat diperkirakan dari uji coba kecil.

### 4.6 Rekomendasi WP4 (belum disetujui; TK-1 tetap keputusan pemilik proyek)

1. **DC-2** sebagai arah rancangan: sesi skenario tidak dipakai untuk kalibrasi.
2. **DC-4** dipertimbangkan sebagai perluasan bila jumlah sesi wajar tidak terjangkau. Perubahan skrip (bobot) memerlukan persetujuan terpisah.
3. **DC-3 dan DC-5 tidak direkomendasikan** sekarang.
4. **Batas interpretasi (§4.3) dicatat** sebagai syarat aktivasi kelak: populasi target dinyatakan, dan tidak ada klaim prevalensi ujian nyata.
5. **Uji coba kecil sesi wajar** (setelah izin etika dan operasional) dipakai untuk memperkirakan π dan beban pelabelan sebelum ukuran dataset dikunci. Perkiraan dari uji coba tidak dipakai sebagai test split.
6. **Konsekuensi yang harus diterima:** dengan DC-2, kalibrator kemungkinan **lama** tersedia, atau tidak tersedia sama sekali bila K5 tidak terjangkau. Itu hasil yang sah: laporan tetap `not_calibrated`.

---

## 5. WP7: P1-4 dan turunannya

### 5.1 Pilihan (dari evaluasi P1-4, dengan dampak DC-2)

| Pilihan | Isi | Dampak dengan DC-2 |
|---|---|---|
| P1-4a | V5 dahulu | Sesi wajar tanpa persetujuan audio (atau tanpa audio) untuk kalibrasi V5. Peserta V5 di pilot bergantung pada siapa yang tidak memberi persetujuan audio. |
| P1-4b | V5+A3 dahulu | Sesi wajar dengan persetujuan audio dan rekaman audio penelitian. Pelabelan suara memerlukan audio. |
| **P1-4c** | Satu protokol untuk keduanya; aktivasi ditentukan data | Setiap sesi wajar masuk V5 atau V5+A3 menurut aturan Phase 4. Penempatan split sekali untuk seluruh dataset (lintas himpunan). Himpunan yang lebih dulu memenuhi K5 dan E1–E6 diusulkan pertama. |

**Catatan penting:** pada pilot, persetujuan audio **riset** dan pengaktifan audio **pemantauan** adalah dua hal berbeda. Sesi pilot dapat diatur agar peserta yang memberi persetujuan audio riset juga mengaktifkan audio pemantauan, sehingga masuk V5+A3. Proporsi persetujuan di pilot **tidak** sama dengan tingkat persetujuan mahasiswa pada ujian nyata, sehingga tidak boleh dipakai untuk memperkirakannya.

### 5.2 Turunan P1-4

| Turunan | Usulan (belum disetujui) | Dasar |
|---|---|---|
| Definisi Y untuk V5+A3 | **Delapan indikasi** (termasuk perilaku suara), dengan definisi operasional dan G-a untuk ketiga indikasi suara | R V5+A3 memuat indikasi suara (K3). Y hanya lima perilaku video akan membuat indikasi suara di R menjadi fitur tanpa label. |
| Persetujuan audio penelitian | Kotak centang terpisah, sesuai protokol §6.1 (persetujuan bertingkat) | Sudah ada di protokol |
| Cara pengumpulan audio | Perekaman penelitian terpisah dari EduAI (EduAI tidak menyimpan audio). Hanya pada sesi pilot dengan persetujuan audio. | EduAI hanya menyimpan skor audio |
| Penyimpanan, akses, penghapusan | Ikut protokol §6.2–§6.4: kode samaran; terenkripsi; hanya tim yang disebut; mentah paling lama 12 bulan atau sesuai komite etik; berita acara penghapusan; mundur → dihapus dalam 14 hari; tidak pernah masuk repositori | Sudah ada di protokol |
| Pengukuran tingkat persetujuan | Dua angka **terpisah**: (a) proporsi persetujuan audio riset di pilot (untuk perencanaan pilot); (b) tingkat persetujuan audio pemantauan pada ujian nyata, dari tabel `consents` produksi bila disetujui (agregat saja). Hanya (b) yang relevan untuk memilih prioritas penggunaan kalibrator. | Data uji coba pengembang (95 %) tidak representatif |

### 5.3 Rekomendasi P1-4 (belum disetujui)

- **P1-4c**, dengan Y V5+A3 mencakup delapan indikasi.
- Prioritas aktivasi ditentukan oleh himpunan yang lebih dulu memenuhi K5 dan E1–E6.
- Bila sumber daya hanya cukup untuk satu himpunan, keputusan diambil setelah angka (b) tersedia.

---

## 6. Konsekuensi terhadap protokol evaluasi dan kalibrasi

| Bila disetujui | Konsekuensi pada `EVALUATION_PROTOCOL.md` | Konsekuensi pada kalibrasi (Tahap 3) |
|---|---|---|
| DC-2 | Protokol perlu menambah **sesi wajar dalam jumlah jauh lebih besar** dan memisahkan tujuan: skenario untuk deteksi dan G-b; wajar untuk kalibrasi. Versi protokol perlu dinaikkan (perubahan dokumen di H3). | Mekanisme tidak berubah. Data kalibrasi dibatasi ke sesi wajar. |
| DC-4 (bila diambil) | Rancangan strata dan peluang pemilihan dicatat | **Perlu perubahan kode** (fit dan metrik berbobot) dan penyesuaian kriteria. Persetujuan terpisah. |
| TK-6 (K1 dari G-a kehadiran) | Formulir pelabelan per sesi memuat kehadiran dan "bermakna" per indikasi | Y diturunkan; kolom `label` tetap |
| TK-5 (ambang κ per satuan) | Ambang κ G-a ditambahkan; κ segmen 0,70 untuk G-b tetap | — |
| TK-3 (C1) | Pemisahan per orang **dan** per sesi ujian, lintas himpunan; struktur `exam_id` pilot dirancang (WP5) | Skrip sudah memeriksa keduanya |
| TK-4 | Penyetelan ambang deteksi dibekukan **sebelum** pengumpulan sesi kalibrasi (WP3) | `config_version`, sidik bobot, dan `models_fingerprint` data harus sama dengan target kalibrator |
| Batas interpretasi (§4.3) | Laporan pilot menyebut populasi | Usulan field `target_population` pada artefak (perubahan format, persetujuan terpisah) |
| P1-4c, Y delapan indikasi | Pelabelan suara dengan audio penelitian | Satu penempatan split lintas himpunan |

## 7. Keputusan H2

**Disetujui pemilik proyek pada 21 November 2026**, dengan status dan batasan di kolom kanan. Rekomendasi di §3–§5 kini berlaku sebagai keputusan sejauh tercantum di tabel ini.

| ID | Keputusan | Status dan batasan |
|---|---|---|
| **H2-1: bentuk label** | Tiga lapisan: K1 (sesi), G-a (keberadaan + kebermaknaan per indikasi), G-b (rentang, subsampel) | **Disetujui (21 November 2026)**. K1 boleh diturunkan dari kolom keberadaan G-a, **dengan syarat** aturan agregasi dan penanganan label tidak lengkap dijelaskan eksplisit di protokol (`SESSION_CALIBRATION_DATASET.md` §3.3). |
| **H2-2: ambang κ (TK-5)** | K1 κ = 0,60 (sesi); G-a κ = 0,60 per indikasi (sesi × indikasi); G-b κ = 0,70 per segmen 1 detik | **Disetujui (21 November 2026)**. Satuan penilaian berbeda: tingkat sesi, indikasi, dan segmen waktu. |
| **H2-3: penafsiran operasional K1 (TK-10)** | "Teramati" mengikuti definisi operasional per indikasi | **Disetujui (21 November 2026)**. K1 tidak diubah. Definisi operasional wajib membedakan perilaku relevan dari aktivitas wajar ujian dan tidak menjadikan satu kejadian umum bukti kecurangan. TK-10 masuk daftar risiko dan protokol evaluasi. |
| **H2-4: TK-1, komposisi dataset** | DC-2 | **Disetujui (21 November 2026)** sebagai arah desain: sesi skenario untuk evaluasi deteksi dan G-b; sesi wajar untuk kalibrasi. DC-4 boleh dianalisis sebagai perluasan bersyarat, **belum disetujui** untuk implementasi. Uji coba kecil memperkirakan prevalensi dan kelayakan **sebelum** ukuran dataset dikunci; jumlah sampel final tidak ditetapkan dari ilustrasi. |
| **H2-5: batas interpretasi** | Populasi target wajib dinyatakan | **Disetujui (21 November 2026)**. Populasi target dinyatakan di dokumentasi dan artefak kalibrator. Probabilitas hanya berlaku pada populasi kalibrasi yang dinyatakan; bukan prevalensi ujian nyata dan bukan probabilitas kecurangan. Field `target_population` pada artefak **belum disetujui** untuk implementasi. |
| **H2-6: P1-4** | P1-4c | **Disetujui (21 November 2026)** sebagai arah protokol: satu protokol untuk V5 dan V5+A3; label V5+A3 mencakup delapan indikasi. |
| **H2-7: turunan P1-4** | Audio riset terpisah dari EduAI; tata kelola protokol §6; dua angka persetujuan terpisah | **Disetujui (21 November 2026)**. **Tidak** berarti audio boleh direkam sebelum izin etik dan persetujuan yang sesuai. |

## 8. Prasyarat yang tetap tercatat (di luar Tahap 4)

- **TK-7:** instans EduAI pilot terpisah dari produksi memerlukan persetujuan operasional.
- **TK-8:** izin komite etik, persetujuan bertingkat, dan persetujuan pimpinan program studi **sebelum** perekaman apa pun.
- Data lama tidak dipakai sampai asal persetujuannya jelas.

## 9. Konfirmasi

- Dokumen ini baru. Tidak ada dokumen lain, kode, konfigurasi runtime, `.env`, database, data, atau dataset yang diubah, dan tidak ada commit.
- Tidak ada perekaman.
- Tidak ada nilai T_k yang ditetapkan, Live Rule Alert tidak diubah, dan Phase 6 belum dimulai.
- Pekerjaan berhenti di **H2**.
