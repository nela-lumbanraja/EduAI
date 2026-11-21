# Kebutuhan Dataset dan Protokol Pelabelan Kalibrasi Sesi EduAI (Rancangan)

Versi rancangan: 0.1 (21 November 2026) · Status: **DITERIMA sebagai dasar desain (H3-9, 21 November 2026); Phase 5 Tahap 4 ditutup sebagai tahap perancangan.** Belum tervalidasi secara empiris. **Bukan** izin pengumpulan data, perekaman, pemakaian instans pilot, atau pemakaian data produksi. Parameter yang bergantung pada uji coba ditandai "ditetapkan setelah uji coba" (§12).

Dokumen ini adalah keluaran L5 rencana Phase 5 (D1). Isinya mencakup:
- pedoman pelabelan (D2), di §3;
- spesifikasi skema dataset (D4), di §8.

**Batas:**
- Dokumentasi saja. Tidak ada perubahan kode, konfigurasi runtime, `.env`, database, skema, data, atau dataset.
- Tidak ada nilai T_k.
- Live Rule Alert tidak diubah.
- Phase 6 belum dimulai.
- DC-4 dan field `target_population` hanya dianalisis, belum disetujui untuk implementasi.

---

## 1. Tujuan dan keputusan yang berlaku

**Tujuan:** menetapkan data dan label yang diperlukan untuk dua penggunaan:
- **kalibrasi sesi** (Tahap 3): label sesi Y dan R = P_total, satu kalibrator per `indicator_set`;
- **validasi T_k** (AL-3 = C): label per indikasi untuk menilai ambang kebijakan Program Studi.

| Keputusan | Isi |
|---|---|
| K1 | Y = 1 bila sesi memuat ≥ 1 perilaku teramati dari daftar indikasi; dua pelabel independen; rekaman penuh; κ ≥ 0,60 |
| H2-3 (TK-10) | "Teramati" mengikuti **definisi operasional per indikasi** yang membedakan perilaku relevan dari aktivitas wajar ujian. Satu kejadian umum bukan bukti kecurangan. |
| H2-1 | Tiga lapisan label: K1 (sesi), G-a (keberadaan + kebermaknaan per indikasi), G-b (rentang, subsampel). K1 boleh diturunkan dari keberadaan G-a dengan aturan eksplisit (§3.3). |
| H2-2 | κ: K1 0,60; G-a 0,60 per indikasi; G-b 0,70 per segmen |
| H2-4 (DC-2) | Sesi skenario untuk evaluasi deteksi dan G-b; **sesi wajar untuk kalibrasi**. Uji coba kecil sebelum ukuran dataset dikunci. |
| H2-5 | Populasi target dinyatakan. Probabilitas hanya berlaku pada populasi kalibrasi yang dinyatakan. |
| H2-6, H2-7 (P1-4c) | Satu protokol untuk V5 dan V5+A3; label V5+A3 delapan indikasi; audio riset terpisah dari EduAI; dua angka persetujuan terpisah |
| K3, K5, C1, C2, P1 §9 | Kalibrator per himpunan; minimum awal 50/50 (kalibrasi) dan 100/100 (test); pemisahan per peserta **dan** per sesi ujian, lintas himpunan; test split sekali pakai |
| AL-3c (G-c bertahap) | G-a untuk semua sesi berlabel; G-b subsampel untuk membedakan masalah P_k dari masalah T_k |

## 2. Jenis sesi dan populasi

| Jenis sesi | Dipakai untuk | Tidak dipakai untuk |
|---|---|---|
| **Sesi skenario** (protokol evaluasi §2.1) | Evaluasi deteksi (`evaluate.py`), label rentang G-b, diagnosis mutu P_k | **Kalibrasi sesi** dan uji kalibrasi |
| **Sesi wajar** (relawan mengerjakan soal latihan tanpa instruksi perilaku) | Kalibrasi sesi (calibration dan test split), validasi T_k (G-a), uji coba kecil | — |

**Populasi target yang dinyatakan (H2-5),** usulan rumusan:
> *Sesi wajar relawan mahasiswa Program Studi Informatika pada pilot EduAI, di perangkat dan ruangan yang mirip ujian, dengan konfigurasi dan model yang dibekukan pada versi X.*

Populasi ini **bukan** populasi ujian nyata. Probabilitas terkalibrasi tidak boleh diklaim sebagai prevalensi ujian nyata atau probabilitas kecurangan. Sampai artefak dapat menyimpan populasi target (field `target_population`, **belum disetujui**), populasi target dicatat di laporan evaluasi dan dokumen persetujuan aktivasi.

## 3. Pedoman pelabelan (D2)

### 3.1 Prinsip umum

1. **Buta terhadap sistem.** Pelabel tidak melihat keluaran EduAI, kejadian, P_k, P_total, T_k, Live Rule Alert, Session Indication Alert, atau probabilitas.
2. **Rekaman penuh.** Pelabel meninjau rekaman penelitian penuh sesi: video, dan audio untuk V5+A3.
3. **Dua pelabel independen** per sesi; tanpa diskusi selama pelabelan.
4. **Pedoman dibekukan** sebelum pelabelan dataset. Uji coba pedoman pada beberapa sesi uji coba (bukan test split), lalu dibekukan dengan versi dan sidik.
5. **Adjudikasi** oleh pelabel ketiga, juga buta terhadap sistem.
6. **Kode samaran** di semua berkas label.

### 3.2 Label per indikasi (G-a), untuk setiap sesi berlabel

Untuk setiap indikasi k dalam `indicator_set` sesi (V5: 5; V5+A3: 8), pelabel mengisi:

| Kolom | Nilai | Definisi |
|---|---|---|
| `presence` | `ada` / `tidak` / `tidak_dapat_dinilai` | **Ada** bila perilaku k muncul menurut **definisi operasional** (tabel 3.4). `tidak_dapat_dinilai` bila rekaman tidak memungkinkan penilaian (mis. kamera mati, audio hilang untuk indikasi suara). |
| `meaningful` | `ya` / `tidak` / `tidak_dapat_dinilai` | **Ya** bila perilaku k, menurut **pedoman kebermaknaan kualitatif** Program Studi, cukup bermakna untuk ditindaklanjuti. Hanya diisi bila `presence = ada`; bila `presence = tidak`, maka `meaningful = tidak`. |
| `notes` | teks | Kondisi khusus |

**Larangan sirkularitas:** pedoman kebermaknaan bersifat kualitatif (lama, berulang, disertai objek atau orang, konteks) dan **tidak** dirumuskan sebagai ambang proporsi waktu. Bila dirumuskan sebagai proporsi waktu, label akan meniru T_k dan validasi T_k menjadi sirkular.

### 3.3 Penurunan K1 dari G-a (syarat H2-1)

Aturan agregasi, per pelabel dan setelah adjudikasi, atas indikasi dalam `indicator_set` sesi:

| Keadaan label `presence` untuk semua indikasi sesi | Y |
|---|---|
| Sedikitnya satu indikasi `ada` | **1** |
| Semua indikasi `tidak` | **0** |
| Tidak ada yang `ada`, tetapi ada indikasi `tidak_dapat_dinilai` atau belum dilabeli | **Tidak ditetapkan**: sesi **dikeluarkan** dari dataset kalibrasi (`label_agreed = false`) dengan alasan `label_tidak_lengkap` |

**Penanganan label tidak lengkap (usulan ketat):**
- Untuk mencegah bias, sesi hanya masuk dataset kalibrasi bila **semua** indikasi dalam himpunannya berlabel lengkap (`ada`/`tidak`) dan disepakati.
- Alasannya: perilaku positif lebih mudah dipastikan daripada ketiadaannya. Menerima sesi positif yang tidak lengkap tetapi menolak sesi negatif yang tidak lengkap akan menaikkan prevalensi secara semu.
- **Pilihan lebih longgar** (Y = 1 bila ada satu `ada`, walau indikasi lain tidak lengkap) **tidak** dipakai karena alasan bias tersebut. Aturan ketat **disetujui (H3-1)**.

**Pelaporan sesi yang dikeluarkan (H3-1, wajib):** setiap laporan uji coba, kalibrasi, dan evaluasi T_k memuat jumlah sesi yang dikeluarkan per alasan (`label_tidak_lengkap`, `tidak_dapat_dinilai` per indikasi, audio tidak tersedia, cakupan, D4), per `indicator_set` dan per split. Laporan juga membandingkan karakteristik sesi yang dikeluarkan dengan yang dipakai: kondisi (protokol §5.3), cakupan, durasi, dan sebaran R. Tujuannya agar bias akibat penyaringan dapat dievaluasi.

**Ketentuan tambahan:**
- **Indikasi suara (V5+A3):** bila audio penelitian tidak tersedia atau tidak dapat dinilai, label suara tidak lengkap dan sesi dikeluarkan dari dataset V5+A3. Sesi itu **tidak** dipindah ke V5, karena R sesi V5+A3 dihitung atas delapan indikasi (K3).
- **κ K1** dihitung atas Y turunan per pelabel (ambang 0,60).
- **κ G-a** dihitung per indikasi atas `presence` dan atas `meaningful` (ambang 0,60), dengan satuan sesi × indikasi.

### 3.4 Definisi operasional per indikasi (struktur; isi final bersama Program Studi)

Definisi operasional memakai sumber yang **sama** dengan pedoman rentang (protokol evaluasi §3) agar G-a dan G-b konsisten. Contoh struktur, bukan nilai final:

| Indikasi | Dihitung "ada" bila (contoh struktur) | Aktivitas wajar yang **tidak** dihitung (dari protokol §2.2) |
|---|---|---|
| FACE_ABSENT | Wajah tidak tampak pada kamera selama sedikitnya *d* detik | Menunduk menulis dengan wajah sebagian tampak; bersandar sebentar |
| HEAD_TURN | Kepala menoleh jelas menjauhi layar selama sedikitnya *d* detik | Melihat keyboard atau kertas; melirik jam; meregangkan leher |
| PHONE_VISIBLE | Ponsel tampak dipegang atau dipakai | Kalkulator, dompet, power bank; ponsel tertutup dan tidak dipakai (bila Program Studi menetapkan demikian) |
| MULTIPLE_PERSONS | Orang lain tampak di bingkai | Poster atau foto, pantulan |
| BOOK_VISIBLE | Buku atau catatan terbuka atau dipakai | Kertas coretan yang diizinkan (bila Program Studi menetapkan demikian) |
| OTHER_VOICE (V5+A3) | Suara orang lain berbicara saat peserta diam | Suara lingkungan jauh, TV atau radio tetangga |
| WHISPER (V5+A3) | Bisikan yang dapat dikenali | Peserta membaca pelan |
| BOOK_SOUND (V5+A3) | Suara halaman atau kertas yang menunjukkan pemakaian bahan | Kertas coretan yang diizinkan |

Parameter seperti *d* ditetapkan Program Studi dan dibekukan bersama pedoman. Parameter ini **bukan** T_k: ia adalah definisi perilaku, bukan ambang skor.

### 3.5 Label rentang (G-b), subsampel

- **Prosedur:** sama dengan protokol evaluasi §3 (dua pelabel, κ ≥ 0,70 per segmen 1 detik, penyelesaian batas ≤ 1 detik, adjudikasi), dengan alat `label_agreement.py` dan format `labels.csv`.
- **Subsampel (usulan bentuk):** semua sesi yang G-a `meaningful = ya` pada sedikitnya satu indikasi, ditambah sampel acak sesi lainnya dengan peluang terpilih **f**. Nilai f diputuskan setelah uji coba (§6).
- **Wajib dicatat:** peluang terpilih setiap sesi (`gb_inclusion_prob`), untuk pembobotan estimasi mutu P_k.
- **Kegunaan:** membandingkan P_k sistem dengan proporsi referensi P*_k (dari rentang), sehingga kegagalan validasi T_k dapat dibedakan antara masalah **pengukuran P_k** dan masalah **ambang T_k**.

## 4. Urutan kerja dan versi beku (WP3, TK-4)

| Urutan | Langkah | Prasyarat |
|---|---|---|
| 0 | Izin komite etik, persetujuan pimpinan Program Studi, persetujuan operasional instans pilot (TK-7, TK-8) | **Wajib sebelum perekaman apa pun** |
| 1 | Sesi skenario: evaluasi deteksi dan penyetelan ambang deteksi (protokol §4, set kalibrasi deteksi) | 0 |
| 2 | **Pembekuan:** `config.yaml` (versi baru), bobot indikasi, model. Catat `config_version`, sidik bobot, `models_fingerprint`, `algo_version`. | 1 selesai |
| 3 | Uji coba kecil sesi wajar (§6) dengan versi beku | 2 |
| 4 | Pembekuan pedoman pelabelan (setelah uji coba), penempatan split (§5), kriteria evaluasi T_k dan nilai minimumnya (§7) | 3 |
| 5 | Pengumpulan dan pelabelan sesi wajar dengan versi beku | 4 |
| 6 | Kalibrasi (skrip Tahap 3) dan evaluasi T_k pada test split, **sekali** | 5 |

**Tidak ada penyetelan ulang berdasarkan hasil test (H3-5):** ambang deteksi, bobot, pedoman, split, kriteria, dan T_k tidak diubah sesudah melihat hasil test. Perubahan sesudahnya berarti dataset dan test split baru.

**Aturan versi:**
- Sesi dengan `config_version`, sidik bobot, atau `models_fingerprint` berbeda dari versi beku **tidak dicampur**. Skrip kalibrasi mengeluarkannya otomatis (`config_version_berbeda`, `models_fingerprint_berbeda`).
- Perubahan ambang deteksi setelah langkah 2 berarti dataset baru.
- Perubahan T_k **tidak** memengaruhi dataset kalibrasi (KB-1): T_k tidak masuk R maupun identitas kalibrator.

## 5. Pemisahan data dan registri (WP5, TK-3, TK-9)

### 5.1 Struktur sesi ujian pilot

- Setiap **sesi duduk pilot** (sekelompok relawan pada satu jadwal) adalah satu `exam_id` di instans pilot.
- **Desain kohort (usulan):** relawan dikelompokkan dalam **kohort tetap** yang selalu duduk bersama di `exam_id` yang sama. Relawan tidak berpindah kohort.

### 5.2 Penempatan split

- Penempatan split dilakukan pada **komponen terhubung** graf peserta–sesi ujian. Peserta dan sesi ujian yang terhubung (karena peserta mengikuti sesi itu) harus berada di split yang sama.
- Dengan desain kohort, setiap kohort adalah satu komponen, sehingga penempatan per kohort menjamin pemisahan **per peserta dan per sesi ujian sekaligus** (C1).
- Bila relawan berpindah-pindah kohort, komponen dapat menyatu menjadi satu dan pemisahan menjadi mustahil. Itulah alasan desain kohort.
- Penempatan dilakukan **sekali untuk seluruh dataset, lintas `indicator_set`** (P1 §9). Sesi V5 dan V5+A3 seorang peserta berada di split yang sama.
- **Acak berstrata:** kohort ditempatkan acak dengan seed tercatat, menjaga keseimbangan kasar kondisi (kacamata, jenis kamera, pencahayaan; protokol §5.3).
- **Proporsi:** K5 meminta lebih banyak positif di test (100) daripada di kalibrasi (50). Usulan: sekitar sepertiga kohort untuk calibration split dan dua pertiga untuk test split. Proporsi final dikunci setelah uji coba (§6).
- **Pembekuan:** tabel penempatan (kohort → split, seed, waktu) dibekukan dan disidik **sebelum** pelabelan dataset selesai. Skrip kalibrasi tetap memeriksa irisan peserta dan sesi ujian (C1).

### 5.3 Registri test split dan artefak (TK-9)

| Pilihan | Isi | Penilaian |
|---|---|---|
| R1 | Registri di penyimpanan penelitian dengan akses terkendali, bersama artefak dataset; sidik kepala registri dicatat di setiap laporan evaluasi | **Disetujui (H3-4).** Registri dan data penelitian **tidak** ditempatkan di penyimpanan produksi atau repositori publik. |
| R2 | Registri di repositori | **Tidak dipilih** (H3-4) |

Isi registri hanya sidik dan putusan; tidak ada data pribadi.

## 6. Uji coba kecil (H2-4)

**Tujuan:** memperkirakan, **sebelum** ukuran dataset dikunci:
1. prevalensi Y sesi wajar (π) per `indicator_set`;
2. prevalensi `presence` dan `meaningful` per indikasi;
3. waktu pelabelan per sesi (G-a; G-b untuk subsampel);
4. κ nyata dengan pedoman draf;
5. fraksi sesi yang lolos penyaringan (q): cakupan, D4, label lengkap;
6. proporsi persetujuan audio riset di pilot (angka pertama H2-7).

**Rancangan:**

| Unsur | Usulan |
|---|---|
| Jumlah | **Belum ditetapkan** (H3-6). Ditentukan dalam rencana uji coba berdasarkan tujuan estimasi (mis. lebar selang Wilson π yang dapat diterima), kelayakan, dan persetujuan etik. |
| Pemakaian data | **Tidak boleh** masuk test split dan **tidak boleh** menjadi data kalibrasi final (H3-6). Hanya untuk estimasi parameter perancangan. |
| Keluaran | Laporan uji coba: π dengan selang Wilson 95 %, waktu pelabelan, κ, q. Dipakai untuk menghitung ukuran dataset (§7.1) dan nilai f (§3.5). |
| Prasyarat | §4 langkah 0–2: izin etika, versi beku, instans pilot |

## 7. Ukuran sampel, kelayakan, dan kriteria evaluasi T_k (WP6, WP10)

### 7.1 Kalibrasi (per `indicator_set`)

- **Kebutuhan minimum (K5)**, setelah penyaringan: calibration split ≥ 50 positif dan ≥ 50 negatif; test split ≥ 100 positif dan ≥ 100 negatif.
- **Perkiraan jumlah sesi berlabel** dari hasil uji coba, memakai batas **konservatif** selang π:
  - calibration split ≈ max(50/π, 50/(1−π)) / q;
  - test split ≈ max(100/π, 100/(1−π)) / q.
- **Tidak ada angka final** yang ditetapkan sebelum uji coba. Ilustrasi di dokumen H2 bukan perkiraan.
- **Konsekuensi yang diterima:** bila kebutuhan tidak terjangkau, kalibrator tidak dibuat dan laporan tetap `not_calibrated`. Itu hasil sah (K5 bukan jaminan).
- **DC-4** (pemilihan berstrata dengan bobot) dapat **dianalisis** sebagai cara menghemat pelabelan bila π ekstrem. Implementasinya (fit dan metrik berbobot di skrip) **belum disetujui**.

### 7.2 Validasi T_k (AL-3 = C, M-a dahulu)

| Unsur | Rancangan |
|---|---|
| Referensi | G-a `meaningful` per indikasi (sesi wajar) |
| Prediksi | Session Indication Alert_k = 1 bila P_k ≥ T_k, dengan T_k **kebijakan** versi tertentu. Sidik T_k dicatat di field terpisah (KB-1). |
| Data | Test split yang sama penempatannya (§5); calibration split untuk M-b bila diperlukan |
| Metrik per indikasi | Sensitivitas, spesifisitas, PPV, NPV, dengan selang 95 % bootstrap **peserta** (B = 2.000, seperti C4) dan jumlah efektif |
| Bentuk kriteria lolos | Batas bawah selang sensitivitas ≥ s_min **dan** batas bawah selang spesifisitas ≥ p_min. **Nilai s_min dan p_min = keputusan pemilik proyek**, ditetapkan **sebelum** test split dilihat. |
| Jumlah minimum per indikasi | Ditetapkan dari lebar selang yang dapat diterima: n_pos ≈ z²·s(1−s)/h², dengan h = setengah lebar selang yang diinginkan. Nilainya keputusan pemilik proyek. Indikasi yang tidak mencapai minimum tetap **"kebijakan, belum divalidasi"**. |
| Bila M-a gagal | M-b: T_k baru dipilih di calibration split dengan aturan yang dikunci lebih dahulu (usulan: sensitivitas minimum lalu spesifisitas maksimum), dievaluasi **sekali** pada test split **yang belum dipakai** untuk T_k. Versi T_k baru tetap memerlukan persetujuan Program Studi dan pemilik proyek. |
| Diagnosis dengan G-b | Pada subsampel, bandingkan P_k dengan P*_k (berbobot 1/f) untuk melihat apakah kegagalan berasal dari pengukuran |
| Inklusi sesi | Sementara: cakupan video ≥ 0,5 (K2), D4 `lengkap`, label lengkap. Aturan final mengikuti AL-2 (terbuka). |
| Larangan klaim | Laporan validasi tidak menyatakan T_k "akurat" tanpa dukungan batas bawah selang |
| Alat | **Belum ada** skrip evaluasi T_k. Membuatnya adalah perubahan kode yang **memerlukan persetujuan terpisah**. |

## 8. Spesifikasi skema dataset (D4)

Semua berkas memakai kode samaran dan disimpan di penyimpanan penelitian (§9). Tidak ada perubahan skema database EduAI.

| Berkas | Kolom | Catatan |
|---|---|---|
| `sessions.csv` (masukan skrip kalibrasi, satu baris per sesi peserta) | Kolom wajib Tahap 3: `exam_id, student_id, label, label_agreed, R, coverage, audio_coverage, indicator_set, weights_fingerprint, algo_version, d4_status, split, models_fingerprint, config_version`. Tambahan informatif: `session_type` (`wajar`; sesi skenario tidak masuk berkas ini), `cohort_id`, `labeling_guideline_version`, `snapshot_computed_at`, `exclusion_reason` | `label` = Y turunan (§3.3); `label_agreed` = false bila tidak lengkap atau tidak disepakati. Skrip kalibrasi mengabaikan kolom tambahan, jadi tidak perlu perubahan kode. Nilai R, cakupan, D4, dan sidik diambil dari **snapshot final** Session Summary instans pilot. |
| `labels_ga.csv` (G-a) | `session_ref, labeler, indicator, presence, meaningful, notes, guideline_version, labeled_at` | Dua pelabel ditambah hasil adjudikasi (`labeler = adjudicated`) |
| `labels_gb.csv` (G-b) | Format `labels.csv` yang ada: `video, indicator, start_s, end_s, intent, visibility, annotator, notes`, ditambah `session_ref` | Hanya subsampel |
| `gb_sample.csv` | `session_ref, gb_selected, gb_inclusion_prob, stratum` | Peluang terpilih wajib dicatat |
| `split_assignment.csv` | `cohort_id, split, seed, assigned_at` | Dibekukan dan disidik |
| `tk_evaluation.csv` (validasi T_k) | `session_ref, indicator, p_k, thresholds_version, thresholds_fingerprint, alert, meaningful_ref, split` | `thresholds_*` di field terpisah (KB-1) |
| `consent_research.csv` | `participant_ref, video, audio, sensitive_data, publication, consent_version` | Untuk angka persetujuan riset (H2-7 angka pertama) |
| `manifest.json` | Sidik setiap berkas, versi pedoman, versi beku (`config_version`, `models_fingerprint`, `algo_version`), seed, populasi target | Dirujuk di laporan dan `lineage` kalibrator (`dataset_sha256`) |

**Angka persetujuan kedua (H2-7):** tingkat persetujuan audio **pemantauan** pada ujian nyata dihitung secara **agregat** dari tabel `consents` produksi. Membaca data produksi, walaupun agregat, **memerlukan persetujuan terpisah**.

## 9. Etika, pelindungan data, dan tata kelola (WP8, TK-8)

Mengikuti `EVALUATION_PROTOCOL.md` §6 tanpa pengurangan. Tambahan untuk kalibrasi sesi:

| Hal | Ketentuan |
|---|---|
| Izin | Komite etik, persetujuan pimpinan Program Studi, persetujuan operasional instans pilot. **Sebelum perekaman apa pun.** |
| Persetujuan peserta | Bertingkat (video, audio, data sensitif, publikasi). Audio riset hanya dengan centang audio. Kesukarelaan; tidak memengaruhi nilai; rekaman tidak dipakai untuk penilaian atau disiplin. |
| Pemisahan sistem | Rekaman penelitian dibuat **terpisah dari EduAI** (EduAI tidak menyimpan audio maupun video penuh). Instans EduAI pilot terpisah dari produksi; tidak ada data pilot di database produksi. |
| Minimisasi | Berkas dataset hanya berisi kode samaran, label, dan nilai snapshot. Tanpa nama atau NIM. |
| Retensi | Rekaman mentah paling lama 12 bulan atau sesuai komite etik, dengan berita acara penghapusan. Label dan nilai dengan kode samaran selama diperlukan untuk replikasi. Peserta mundur → dihapus dalam 14 hari, termasuk dari dataset; bila sudah dipakai dalam kalibrator, dicatat di laporan. |
| Akses | Hanya tim yang disebut dalam izin etik; terenkripsi; akses dicatat |
| Data lama | `dataset_raw/` dan `pilot/p01.mp4` **tidak dipakai** sampai asal persetujuannya jelas |
| Data produksi | Tidak dipakai untuk pelabelan. Angka persetujuan audio pemantauan (agregat) memerlukan persetujuan terpisah. |

## 10. Konsekuensi terhadap protokol evaluasi

Usulan revisi `EVALUATION_PROTOCOL.md` ke versi berikutnya. Saat ini hanya §7a yang ditambahkan; revisi lainnya menunggu persetujuan H3.

1. Menambahkan **sesi wajar** dalam jumlah yang dihitung dari uji coba, terpisah tujuannya dari sesi skenario (DC-2).
2. Menambahkan **desain kohort** dan pemisahan per peserta **dan** per sesi ujian untuk kalibrasi sesi.
3. Menambahkan pelabelan **G-a** (keberadaan, kebermaknaan) dan penurunan K1, dengan κ ≥ 0,60.
4. Menyatakan urutan **pembekuan versi** sebelum pengumpulan sesi kalibrasi.
5. Menyatakan **populasi target** dan batas interpretasi probabilitas.

Rancangan teks revisi ada di `docs/EVALUATION_PROTOCOL_REVISI_0.2_RANCANGAN.md` (H3-8). Rancangan ini **belum berlaku** sampai PS-7 disetujui.

## 11. Perubahan yang memerlukan persetujuan terpisah

| # | Perubahan | Jenis |
|---|---|---|
| PS-1 | Skrip evaluasi T_k | Kode |
| PS-2 | DC-4: fit dan metrik kalibrasi berbobot | Kode dan kriteria |
| PS-3 | Field `target_population` pada artefak kalibrator | Kode (format artefak) |
| PS-4 | Instans EduAI pilot (TK-7) | Operasional |
| PS-5 | Izin etika, persetujuan pimpinan, perekaman (TK-8) | Etika dan operasional |
| PS-6 | Pembacaan agregat tabel `consents` produksi | Akses data produksi |
| PS-7 | Revisi versi `EVALUATION_PROTOCOL.md` (§10) | Dokumen protokol |
| PS-8 | Nilai T_k kebijakan oleh Program Studi | Kebijakan |
| PS-9 | Nilai s_min, p_min, dan jumlah minimum per indikasi | Kriteria |

## 12. Parameter yang ditetapkan setelah uji coba (penutupan Tahap 4, opsi a)

Parameter berikut **sengaja belum ditetapkan**. Penetapannya memerlukan hasil uji coba (yang sendiri memerlukan PS-4 dan PS-5) atau keputusan pemilik proyek. Tidak satu pun boleh diisi dari ilustrasi.

| Parameter | Dasar penetapan | Keputusan |
|---|---|---|
| Jumlah peserta uji coba | Tujuan estimasi, kelayakan, persetujuan etik (H3-6) | Rencana uji coba |
| f, peluang terpilih subsampel G-b | Waktu pelabelan G-b dan jumlah sesi `meaningful = ya` di uji coba | Setelah uji coba |
| Proporsi split final (sementara sekitar 1/3 : 2/3) | π dan q dari uji coba; K5 | Setelah uji coba |
| Ukuran dataset per `indicator_set` | §7.1 dengan batas konservatif π dari uji coba | Setelah uji coba |
| Isi final definisi operasional (parameter *d*) dan kriteria kebermaknaan | Program Studi; uji coba pedoman (H3-2) | Bersama Program Studi |
| Nilai T_k kebijakan | Program Studi (AL-3 = C) | PS-8 |
| s_min, p_min, jumlah minimum per indikasi | Lebar selang yang dapat diterima (§7.2) | PS-9, sebelum test split dilihat |
| Inklusi sesi bercakupan rendah (final) | Sementara K2 | AL-2 (terbuka) |
| Kelayakan K5 (TK-2) | π, q, sumber daya | Terbuka sampai uji coba |
