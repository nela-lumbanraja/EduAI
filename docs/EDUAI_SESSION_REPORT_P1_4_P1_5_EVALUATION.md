# Session Report: Evaluasi P1-4 (Prioritas Dataset) dan P1-5 (Definisi ALERT)

Tanggal: 21 November 2026 · Status: **P1-5 DIPUTUSKAN = S1 (21 November 2026; lihat `EDUAI_SESSION_REPORT_P1_5_AL3_DECISION_ANALYSIS.md`). P1-4 BELUM DIPUTUSKAN. Belum ada implementasi.** *Status awal: "P1-4 dan P1-5 BELUM DIPUTUSKAN."*

Dokumen ini hanya evaluasi. Tidak ada kode, database, konfigurasi, atau data yang diubah, dan tidak ada commit. Tahap 4 belum dimulai, B2 tidak diimplementasikan, dan definisi ALERT di kode maupun konfigurasi tidak diubah.

Tidak ada definisi atau pilihan di dokumen ini yang dianggap sudah disetujui.

> **Penyelarasan dengan arsitektur target (21 November 2026):** pemilik proyek menetapkan arsitektur target Session Report, termasuk **Session Indication Alert** (Alert_k = 1 jika P_k ≥ T_k). Keselarasan dan konflik dicatat di `docs/EDUAI_SESSION_REPORT_ARCHITECTURE_ALIGNMENT.md`. Catatan di bawah (A.7, B.7) menyesuaikan evaluasi ini dengan arsitektur itu. **Status P1-4 dan P1-5 tidak berubah: belum diputuskan.**

**Dasar:**
- `docs/EDUAI_SESSION_REPORT_PHASE5_P1_EVALUATION.md` (P1-1/2/3/6 disetujui secara prinsip);
- rancangan Tahap 3 revisi 4 (K1, K2, K3, K5, C1–C7);
- kode yang berjalan (dibaca saja);
- statistik dari **salinan sementara** database produksi, dibaca saja. Database produksi tidak dibuka dan salinannya dihapus setelah dibaca.

---

# Bagian A: P1-4, prioritas pengumpulan dataset `V5` atau `V5+A3`

## A.1 Kedua himpunan

| | V5 | V5+A3 |
|---|---|---|
| Indikasi | FACE_ABSENT, MULTIPLE_PERSONS, HEAD_TURN, PHONE_VISIBLE, BOOK_VISIBLE | V5 + OTHER_VOICE, WHISPER, BOOK_SOUND |
| Peserta yang masuk | Tanpa persetujuan audio, **atau** dengan persetujuan tetapi tanpa satu pun sampel audio (`no_audio_data`) | Dengan persetujuan audio **dan** ada sampel audio |
| Penentu | Pilihan peserta (sukarela) dan keadaan teknis (mikrofon atau YAMNet gagal) | Sama |

Peserta tidak dapat ditempatkan ke himpunan oleh peneliti. Himpunan **mengikuti** persetujuan dan keadaan teknis.

## A.2 Fakta dari data uji coba (tidak representatif)

Data diambil dari salinan sementara database produksi, yang berisi data uji coba pengembangan:

| Hal | Nilai |
|---|---|
| Persetujuan tercatat | 20, di 17 ujian |
| Dengan persetujuan audio | 19 dari 20 (95 %) |
| Kejadian indikasi suara | OTHER_VOICE 73; WHISPER dan BOOK_SOUND 0 |
| Kejadian indikasi video | FACE_ABSENT 55, MULTIPLE_PERSONS 42, HEAD_TURN 39, PHONE_VISIBLE 31, BOOK_VISIBLE 17 |

Data ini dibuat saat pengujian oleh pengembang, jadi **tidak** mewakili tingkat persetujuan mahasiswa sesungguhnya. Angka-angka di atas hanya menunjukkan bahwa sistem mampu menghasilkan kedua himpunan, bukan proporsi yang akan terjadi.

## A.3 Perbandingan

| Kriteria | Prioritas V5 | Prioritas V5+A3 |
|---|---|---|
| **Ground truth (K1)** | Pelabel cukup meninjau **video** sesi penuh. Perilaku yang dinilai: lima indikasi video. | Pelabel memerlukan **video dan audio** sesi penuh, karena perilaku suara (bicara dengan orang lain, bisikan, suara kertas) hanya dapat dilabeli dari audio. EduAI sendiri tidak menyimpan audio; bukti hanya berupa gambar. Jadi diperlukan perekaman terpisah dengan persetujuan khusus. |
| **Definisi target Y** | Y dibatasi pada perilaku lima indikasi video | Y mencakup delapan indikasi. Ada keputusan turunan: apakah Y untuk V5+A3 memakai daftar delapan indikasi atau tetap lima (lihat A.5). |
| **Privasi dan persetujuan** | Persetujuan video (sudah wajib dalam pemantauan) dan persetujuan penelitian untuk perekaman penuh | Tambahan persetujuan perekaman **audio** untuk penelitian, prosedur penyimpanan dan pemusnahan audio, serta risiko suara orang lain di ruangan |
| **Kelayakan pengumpulan** | Semua peserta yang memiliki video dapat ikut, asalkan tidak memberi persetujuan audio atau sampel audionya kosong. **Konsekuensinya:** bila tingkat persetujuan audio tinggi, peserta V5 justru sedikit. | Hanya peserta yang memberi persetujuan audio dan mikrofonnya berfungsi. Bila tingkat persetujuan tinggi, mayoritas peserta masuk di sini. |
| **Persyaratan K5 dan C1** | Calibration ≥ 50 positif/50 negatif, test ≥ 100/100, setelah penyaringan. Pemisahan per peserta dan per sesi ujian, **lintas himpunan** (§9 dokumen P1). | Sama. Penyaringan cakupan audio (T3-3, 50 %) membuang sesi dengan audio terputus, sehingga data yang dibutuhkan lebih banyak. |
| **Kejadian positif** | Indikasi video lebih beragam di data uji coba | Indikasi suara di data uji coba hampir seluruhnya OTHER_VOICE. Positif yang didorong WHISPER atau BOOK_SOUND belum pernah teramati. |
| **Penggunaan kalibrator** | Berlaku untuk peserta tanpa persetujuan audio atau tanpa sampel audio. Bila hampir semua peserta memberi persetujuan audio, kalibrator V5 jarang terpakai. | Berlaku untuk peserta dengan persetujuan dan sampel audio. Bila tingkat persetujuan tinggi, kalibrator ini mencakup mayoritas. |
| **Risiko persepsi (§8.1 dokumen P1)** | Peserta yang memberi persetujuan audio tidak mendapat probabilitas | Peserta yang tidak memberi persetujuan audio tidak mendapat probabilitas |

## A.4 Pilihan dan konsekuensinya

| Pilihan | Isi | Konsekuensi |
|---|---|---|
| **P1-4a: V5 dahulu** | Kumpulkan dan labeli hanya untuk V5 | Ground truth dan privasi paling sederhana. Bila tingkat persetujuan audio tinggi, data V5 terkumpul lambat (peserta V5 sedikit) dan kalibratornya jarang terpakai. |
| **P1-4b: V5+A3 dahulu** | Kumpulkan dan labeli hanya untuk V5+A3 | Bila persetujuan audio tinggi, mencakup mayoritas peserta. Namun memerlukan perekaman audio penelitian, persetujuan tambahan, dan pelabelan audio. Positif untuk indikasi suara selain OTHER_VOICE belum pernah teramati. |
| **P1-4c: Satu protokol untuk keduanya, prioritas aktivasi ditentukan data** | Semua sesi penelitian direkam penuh (video, dan audio bila ada persetujuan). Setiap sesi otomatis masuk V5 atau V5+A3 menurut aturan Phase 4. Penempatan split ditetapkan sekali per peserta dan per sesi ujian untuk seluruh dataset. Himpunan yang **lebih dulu** memenuhi K5 dan lolos E1–E6 diusulkan untuk diaktifkan pertama. | Tidak ada data yang terbuang hanya karena pilihan himpunan. Biaya pelabelan audio tetap ada untuk sesi V5+A3. Urutan aktivasi tidak dapat dipastikan di awal. |

## A.5 Keputusan turunan yang perlu dicatat (belum diputuskan)

1. **Definisi Y per himpunan.**
   - Untuk V5+A3: apakah Y mencakup perilaku suara (delapan indikasi), atau tetap lima perilaku video seperti V5?
   - Mencakup suara lebih konsisten dengan R, karena R memuat indikasi suara.
   - Tetap lima perilaku video membuat kedua himpunan memakai target yang sama, tetapi membuat indikasi suara dalam R menjadi "fitur" yang tidak dilabeli.
2. **Data tingkat persetujuan audio sesungguhnya.** Sebelum prioritas dikunci, sebaiknya tingkat persetujuan diukur pada populasi target, misalnya satu periode uji coba pertama. Data pengembangan (95 %) tidak dapat dipakai.

## A.6 Rekomendasi P1-4

- **P1-4c** sebagai protokol pengumpulan. Alasannya: proporsi himpunan ditentukan oleh persetujuan sukarela yang belum diketahui, dan C1 lintas himpunan mewajibkan satu penempatan split untuk seluruh dataset.
- Bila sumber daya hanya cukup untuk **satu** himpunan, pilihan bergantung pada tingkat persetujuan audio populasi target:
  - tinggi → **V5+A3** mencakup lebih banyak peserta, dengan biaya perekaman dan pelabelan audio;
  - rendah atau belum diketahui → **V5** lebih sederhana dan lebih rendah risiko privasinya.
  
  Keputusan ini sebaiknya diambil setelah tingkat persetujuan terukur (A.5 butir 2).

## A.7 Catatan penyelarasan (arsitektur target)

- Dua kemungkinan `indicator_set` dipertahankan: **V5** (lima indikasi video) dan **V5+A3** (lima video dan tiga audio).
- **Dataset, ground truth, evaluasi, dan kalibrasi harus sesuai dengan `indicator_set` yang dipakai.** Data, label, split, registri, dan kalibrator satu himpunan tidak dipakai untuk himpunan lain (K3; dokumen P1 §4 dan §9).
- **P1-4c masih usulan**, bukan keputusan final.
- **Belum ada kalibrator** untuk V5 maupun V5+A3, dan tidak satu pun dianggap tersedia atau layak. Aktivasi tetap menunggu K5 dan evaluasi E1–E6, serta persetujuan C6 untuk artefak tertentu.
- **Masih harus diselesaikan** sebelum Tahap 4 dapat ditutup (status: belum diputuskan):
  1. definisi target/ground truth Y untuk V5+A3 (lima atau delapan perilaku);
  2. persetujuan audio untuk penelitian, terpisah dari persetujuan pemantauan;
  3. cara pengumpulan audio penelitian, karena EduAI tidak menyimpan audio;
  4. penyimpanan, hak akses, dan penghapusan rekaman audio dan video penelitian;
  5. pengukuran tingkat persetujuan audio populasi target.

**Status P1-4: BELUM DIPUTUSKAN.**

---

# Bagian B: P1-5, definisi ALERT pada Session Report

## B.1 Definisi yang saat ini diterapkan (dibaca dari kode)

| Hal | Fakta |
|---|---|
| Nama di sistem | Kode tidak memakai kata "ALERT". Yang dipakai adalah aturan ringkasan (`summary_rules`) yang **terpenuhi** (`rule.met`). Antarmuka menampilkannya sebagai "memenuhi ambang" atau "di bawah ambang". |
| Sumber data | Kejadian indikasi (`events`) yang digabung menjadi **episode** (`cases.episodes_of`; kejadian yang tumpang tindih atau berjarak ≤ 2 detik dihitung satu) |
| Aturan pemicu | Terpenuhi bila sedikitnya `min_count` episode dimulai dalam `window_s` detik, atau di sepanjang ujian bila `window_s` tidak ada (`cases.rule_status`) |
| Nilai sekarang (`config.yaml` `summary_rules`) | `min_count: 1` untuk PHONE_VISIBLE, MULTIPLE_PERSONS, OTHER_VOICE, WHISPER, FACE_ABSENT, HEAD_TURN, BOOK_VISIBLE, BOOK_SOUND. HEAD_TURN_REPEATED: 4 episode per 3.600 detik. Indikasi yang tidak disebut: 1 episode. |
| Waktu | **Langsung, selama ujian berjalan**: dievaluasi setiap kali kasus dibaca |
| Dipakai untuk | Pop-up notifikasi pengawas (`notify.ts`); urutan prioritas tinjauan (`cases.priority_key`); keterangan "aturan ringkasan terpenuhi"; ringkasan ujian (`rules_met`: "N perilaku memenuhi ambang"); daftar kasus ("Di bawah ambang (x/y)") |
| Hubungan dengan skor durasi P_i | Tidak ada. Episode 5 detik dan episode 30 menit sama-sama satu episode. |
| Hubungan dengan cakupan dan D4 | Tidak langsung. Waktu tanpa data tidak menghasilkan episode; model yang tidak tersedia tidak menghasilkan episode. |
| Snapshot | Status aturan dan ambangnya **belum** dibekukan di snapshot Session Summary (G1, G4) |

## B.2 Rancangan alternatif: ALERT berbasis skor indikasi sesi

Rumusan acuan arsitektur: **"Status ALERT ditentukan berdasarkan skor agregasi sesi setiap indikasi dan threshold indikasi tersebut."**

| Hal | Rancangan |
|---|---|
| Sumber data | P_i: skor durasi sesi per indikasi (Phase 4, interval 5 menit dengan durasi aktual), dari snapshot final |
| Aturan pemicu | ALERT_i bila P_i ≥ θ_i, dengan θ_i threshold per indikasi |
| Waktu | Pada **akhir sesi** (snapshot final). Selama sesi hanya nilai sementara yang masih bisa berubah. |
| Threshold θ_i | **Belum ada.** Tidak ada nilai yang tervalidasi; menetapkannya secara bermakna memerlukan data berlabel per indikasi. |

## B.3 Perbandingan

| Aspek | Definisi berjalan (episode) | Rancangan skor (P_i ≥ θ_i) |
|---|---|---|
| **Makna** | "Perilaku ini muncul sedikitnya N kali (dalam jendela waktu)": frekuensi kejadian | "Perilaku ini aktif selama sedikitnya θ dari waktu yang dapat dianalisis": proporsi durasi |
| **Sumber data** | Kejadian dan episode | Skor durasi P_i dari detik teramati, interval berbobot |
| **Kepekaan** | Kejadian singkat tetapi penting (ponsel terlihat 5 detik) langsung memicu bila `min_count = 1` | Kejadian singkat hampir tidak menggerakkan P_i (5 detik dari 60 menit ≈ 0,0014), sehingga tidak memicu kecuali θ sangat kecil |
| **Kejadian panjang dan wajar** | Wajah tidak terlihat 20 menit karena posisi duduk tetap dihitung satu episode | Menaikkan P_i tinggi, sehingga mudah memicu |
| **Waktu tersedia** | Selama ujian: mendukung pop-up dan tinjauan langsung | Setelah sesi (final). Sebelum itu hanya sementara, jadi tidak cocok untuk notifikasi langsung. |
| **Cakupan dan data kosong** | Tidak terpengaruh penyebut | Interval tanpa data bernilai 0 di penyebut (aturan Phase 4), sehingga cakupan rendah menurunkan P_i dan ALERT bisa tidak muncul. Perlu aturan tambahan; cakupan tidak boleh dikalikan. |
| **D4 (`model_unavailable`)** | Model mati tidak menghasilkan episode | P_i = 0 dengan cakupan penuh (K7 terbuka): ALERT tidak pernah muncul untuk indikasi terdampak, sehingga penandaan D4 menjadi wajib di sampingnya |
| **Threshold** | `min_count`/`window_s` sudah ada di config (nilai produk awal, bukan hasil validasi model) | θ_i belum ada; perlu ditetapkan, sebaiknya dari data berlabel |
| **Konsistensi dengan sistem lain** | Sama dengan pop-up, prioritas tinjauan, ringkasan ujian, dan daftar kasus yang sudah dipakai pengawas | Berbeda dengan semua tampilan di atas. Bila menggantikan, semua tampilan itu harus ikut diubah; bila tidak, dua "ALERT" bisa saling bertentangan untuk indikasi yang sama. |
| **Kebutuhan implementasi** | Hanya G1/G4: membekukan status aturan dan ambangnya di snapshot | Threshold baru di config, kode penentuan, pembekuan di snapshot, perubahan tampilan, dan evaluasi threshold |

## B.4 Dampak terhadap Session Report

| Bagian laporan | Definisi episode | Definisi skor |
|---|---|---|
| Indication Analysis | ALERT per indikasi = aturan episode terpenuhi; jumlah episode, ambang (`min_count`/`window_s`), dan P_i ditampilkan berdampingan sebagai dua ukuran berbeda | ALERT per indikasi = P_i ≥ θ_i; θ_i ditampilkan |
| Overall Session Summary | Jumlah indikasi ALERT = jumlah aturan terpenuhi (sama dengan `rules_met` di ringkasan ujian) | Jumlah indikasi dengan P_i ≥ θ_i; bisa berbeda dari `rules_met` yang dilihat pengawas selama ujian |
| Data Coverage | Cakupan tetap terpisah | Cakupan tetap terpisah, tetapi perlu catatan bahwa cakupan rendah dapat menyembunyikan ALERT |
| Snapshot (G4) | Bekukan `min_count`, `window_s`, status terpenuhi, dan jumlah episode | Bekukan θ_i dan status ALERT |
| P_total dan kalibrasi | Tidak terpengaruh | Tidak terpengaruh |

Dalam kedua definisi:
- ALERT tetap **per indikasi**;
- P_total tetap ringkasan dan tidak menggantikan ALERT;
- kalibrasi tidak membaca ALERT;
- PDF tidak menghitung ulang.

## B.5 Pilihan dan konsekuensinya

| Pilihan | Isi | Konsekuensi |
|---|---|---|
| **P1-5a: ALERT = aturan episode** | Definisi berjalan menjadi definisi ALERT Session Report. Rumusan acuan arsitektur butir 3 disesuaikan. P_i ditampilkan di samping ALERT sebagai ukuran durasi, bukan pemicu. | Tanpa perubahan perilaku. Konsisten dengan pop-up dan tinjauan. G1/G4 cukup membekukan status dan ambang. Acuan arsitektur perlu diubah. |
| **P1-5b: ALERT = P_i ≥ θ_i (menggantikan)** | Sesuai rumusan acuan arsitektur | Perubahan perilaku besar: pop-up, prioritas, ringkasan ujian, dan daftar kasus harus diselaraskan atau dibiarkan berbeda. θ_i harus ditetapkan tanpa data validasi. Tidak tersedia selama ujian. Peka terhadap cakupan dan D4. |
| **P1-5c: Dua konsep terpisah** | ALERT tetap aturan episode (5a). Ditambah penanda tingkat sesi dengan **nama lain**, misalnya "Indication Score di atas ambang", untuk P_i ≥ θ_i. | Tidak ada konflik makna. Butuh θ_i dan penamaan yang jelas. Dua penanda bisa membingungkan bila tidak dijelaskan di laporan. |

## B.6 Rekomendasi P1-5

1. **Sekarang: P1-5a.**
   - Aturan episode sudah menjadi dasar pop-up, prioritas tinjauan, dan ringkasan ujian yang dipakai pengawas.
   - Aturan ini tersedia selama ujian dan tidak terpengaruh penyebut cakupan maupun K7.
   - Yang perlu dilakukan: acuan arsitektur butir 3 disesuaikan, dan G1/G4 membekukan status aturan serta `min_count`/`window_s` di snapshot.
2. **Nanti, bila diinginkan: P1-5c**, setelah θ_i dapat ditetapkan dari data berlabel per indikasi.
   - Data itu bisa dikumpulkan bersama Tahap 4 bila protokol pelabelan mencatat perilaku per indikasi.
   - Penanda skor memakai nama yang berbeda dari ALERT.
3. **P1-5b tidak direkomendasikan** saat ini. θ_i belum ada dasarnya, perilaku pengawasan langsung akan berubah, dan kepekaannya terhadap cakupan dan K7 menuntut aturan tambahan.

## B.7 Catatan penyelarasan (arsitektur target)

Arsitektur target menetapkan **Session Indication Alert** berbasis skor sesi: Alert_k = 1 jika P_k ≥ T_k, Alert_k = 0 jika P_k < T_k. Akibatnya:

1. **Rekomendasi B.6 butir 1 (P1-5a) tidak selaras dengan arsitektur target.** P1-5a menjadikan aturan episode sebagai ALERT Session Report. Rekomendasi itu dipertahankan di atas hanya sebagai catatan evaluasi, **bukan lagi rekomendasi**.
2. **Dua mekanisme yang tidak sama dicatat terpisah** (dokumen penyelarasan §4):
   - **Live Rule Alert**: berbasis episode (`min_count`, `window_s`), berjalan selama sesi untuk notifikasi langsung, prioritas tinjauan, dan status aturan. **Tidak diubah** tanpa persetujuan pemilik proyek.
   - **Session Indication Alert**: status di Session Report dari P_k dan T_k. Belum diimplementasikan.
   
   Arah ini paling dekat dengan P1-5c, tetapi dengan Session Indication Alert sebagai ALERT laporan sesuai arsitektur target.
3. **T_k belum tervalidasi dan belum siap dipakai.** Definisi, sumber, persetujuan, dan pembekuannya masih diperlukan (AL-3).
4. **Status saat data kosong** belum diputuskan (AL-2). Bila seluruh data indikasi tidak tersedia, status harus "Tidak tersedia", bukan NORMAL atau ALERT. Rumus P_k dan aturan data kosong Phase 4 tidak diubah.
5. **Kedua mekanisme bisa berbeda untuk indikasi yang sama.** Contoh: ponsel terlihat 5 detik memenuhi Live Rule Alert (`min_count: 1`), tetapi P_k ≈ 0,0014 kemungkinan di bawah T_k. Penamaan dan penjelasan di laporan harus mencegah kesan bertentangan.

**Status P1-5: DIPUTUSKAN = S1** (21 November 2026): Live Rule Alert dan Session Indication Alert dua mekanisme berbeda; Live Rule Alert tidak diubah. Pilihan P1-5a/b/c di B.5 adalah catatan evaluasi sebelumnya; keputusan yang berlaku adalah S1 di dokumen analisis keputusan.

---

# Bagian C: Ringkasan keputusan

| ID | Pilihan | Rekomendasi | Status |
|---|---|---|---|
| P1-4 | a: V5 dahulu · b: V5+A3 dahulu · c: satu protokol, aktivasi ditentukan data | c. Bila hanya satu himpunan: tentukan setelah tingkat persetujuan audio populasi target terukur. | **Belum diputuskan** |
| P1-4 turunan | Definisi Y untuk V5+A3 (lima atau delapan perilaku); pengukuran tingkat persetujuan audio | Dibahas di Tahap 4 | **Belum diputuskan** |
| P1-5 | a: episode · b: skor menggantikan · c: dua konsep terpisah (dirumuskan ulang sebagai S1–S4 di dokumen analisis keputusan) | — | **Diputuskan (21 November 2026)**: **S1** (dua mekanisme terpisah) |

## Batas pekerjaan

- Tidak ada perubahan kode, database, konfigurasi, data, atau commit.
- Statistik uji coba dibaca dari salinan sementara yang langsung dihapus; database produksi tidak dibuka.
- Tahap 4 belum dimulai.
- B2 belum diimplementasikan.
- Definisi ALERT di kode dan `config.yaml` tidak diubah.
- G1–G4 dan Phase 6 belum dimulai.
- K7 tetap terbuka.
