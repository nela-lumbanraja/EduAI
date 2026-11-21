# Session Report Phase 5: Evaluasi P1, Satu atau Beberapa Kalibrator per `indicator_set`

Tanggal: 21 November 2026 (diperbarui) · Status: **Arah desain disetujui secara prinsip (P1-1, P1-2, P1-3, P1-6). P1-5 diputuskan = S1 pada 21 November 2026 (dokumen analisis keputusan P1-5/AL-3); P1-4 masih terbuka. Bukan persetujuan implementasi; B2 belum diimplementasikan.**

Dokumen ini hanya evaluasi dokumentasi dan arsitektur. Tidak ada kode, database, konfigurasi, atau data yang diubah, dan tidak ada commit. Tahap 4 belum dimulai.

**Dasar:**
- hasil Tahap 3 `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_RESULTS.md` (penyesuaian P1);
- rancangan `docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md` revisi 4 (K3, C6, C7, §5.1);
- keputusan Phase 4.

---

## 1. Ringkasan masalah P1

- K3 menetapkan **satu kalibrator per himpunan indikasi** (`indicator_set`).
- C6 menetapkan **satu** setting sidik SHA-256 untuk artefak yang disetujui.
- Karena itu implementasi Tahap 3 hanya menerima **satu berkas kalibrator**, yang berlaku untuk satu himpunan.
- Peserta yang himpunan indikasinya berbeda selalu mendapat `not_calibrated` dengan alasan `indicator_set_mismatch`.

Saat ini belum ada kalibrator sama sekali, jadi P1 belum berdampak di produksi. P1 menjadi relevan begitu kalibrator pertama disetujui.

### 1.1 Himpunan indikasi yang benar-benar muncul

Himpunan indikasi peserta adalah `weights_used`: indikasi yang dinilai dengan bobot > 0. Menurut aturan Phase 4, himpunan itu ditentukan oleh:

| Sumber | Akibat pada himpunan | Skala |
|---|---|---|
| Persetujuan audio (consent) | Tanpa persetujuan: tanpa OTHER_VOICE, WHISPER, BOOK_SOUND | Per peserta |
| `no_audio_data` (T1) | Persetujuan ada tetapi tanpa satu pun sampel audio: tanpa ketiga indikasi suara | Per peserta |
| Config aktif (T4) | Indikasi nonaktif, berkategori info, atau modelnya mati dikeluarkan | Per config: sama untuk semua peserta |
| Bobot 0 (Phase 4) | Indikasi dengan bobot 0 keluar dari himpunan | Per config |
| D4 (`model_unavailable`) | **Tidak** mengubah himpunan; hanya menandai (K7 terbuka) | — |

Dengan config proyek sekarang (semua aktif, bobot 1), dalam satu sesi praktis hanya ada **dua** himpunan:
- **V5**: lima indikasi video, untuk peserta tanpa persetujuan audio atau dengan `no_audio_data`;
- **V5+A3**: delapan indikasi, untuk peserta dengan persetujuan audio dan ada sampel audio.

## 2. Apakah `indicator_set` bagian dari identitas kalibrator?

**Ya, harus.**
- P_total = Σ v_i P_i / Σ v_i dihitung atas `weights_used`. Rata-rata atas lima indikasi dan atas delapan indikasi adalah besaran yang berbeda: indikasi suara menambah penyebut dan menggeser sebaran R.
- Satu pemetaan R → probabilitas tidak sah untuk keduanya. Hal ini sudah menjadi dasar K3 dan kunci kompatibilitas di Tahap 3.

Identitas kalibrator saat diterapkan terdiri dari:

| Kunci | Fungsi |
|---|---|
| `indicator_set` | Memilih kalibrator (§4) |
| `algo_version`, `weights_fingerprint` | Rumus dan bobot yang menghasilkan R |
| `lineage.models_fingerprint` | Model AI penghasil data (C7) |
| `lineage.criteria_version` dan `criteria_sha256` | Kriteria evaluasi |
| SHA-256 artefak | Persetujuan (C6) |

Hanya `indicator_set` yang dipakai untuk **memilih**. Kunci lain hanya untuk **memvalidasi** kalibrator yang sudah terpilih.

## 3. Alternatif desain

| Kode | Desain | Ringkasnya |
|---|---|---|
| **A** | Satu kalibrator (keadaan Tahap 3) | Satu berkas, satu sidik. Himpunan lain → `indicator_set_mismatch`. |
| **B1** | Beberapa kalibrator, satu pasang setting per himpunan | Mis. `EDUAI_SESSION_CALIBRATOR_V5`/`_SHA256`, `…_V5A3`/`_SHA256`. Jumlah dan nama setting bergantung pada himpunan. |
| **B2** | Beberapa kalibrator lewat **manifes yang disetujui** | Setting C6 yang sudah ada menunjuk satu **manifes** dan menyimpan SHA-256-nya. Manifes mencantumkan, per himpunan, satu berkas kalibrator beserta SHA-256-nya. Rantai persetujuan: setting → manifes → berkas. |
| C | Satu kalibrator gabungan untuk semua himpunan | `indicator_set` bukan bagian identitas, atau dijadikan fitur tambahan |
| D | Fallback | Bila tidak ada kalibrator untuk himpunan peserta, pakai kalibrator himpunan lain (mis. V5 untuk peserta V5+A3) |

**C dan D ditolak:**
- C mencampur R dengan skala berbeda dan melanggar K3. Bila `indicator_set` dijadikan fitur, hasilnya model prediksi multi-fitur, yang berada di luar lingkup.
- D melanggar ketentuan "tidak boleh ada fallback kalibrator" (C3/C7) dan menerapkan pemetaan yang tidak sah.

Menghitung "P_total versi video" khusus untuk peserta V5+A3 supaya bisa memakai kalibrator V5 juga ditolak, karena itu menambah skor baru dan mengubah agregasi Phase 4.

## 4. Pemilihan kalibrator yang deterministik (B1/B2)

1. **Kunci himpunan:** nama indikasi di `weights_used` peserta, diurutkan, digabung dengan `;`. Contoh: `BOOK_VISIBLE;FACE_ABSENT;HEAD_TURN;MULTIPLE_PERSONS;PHONE_VISIBLE`. Kunci ini dihitung dari hasil Phase 4 yang sudah ada, tanpa perhitungan baru.
2. **Cocok persis.** Hanya kalibrator dengan `indicator_set` yang **identik** yang dipilih. Tidak ada kecocokan subset, superset, atau "terdekat".
3. **Paling banyak satu per kunci.** Manifes atau setting dengan dua kalibrator untuk kunci yang sama ditolak seluruhnya.
4. **Tanpa pencarian lanjutan.** Bila kalibrator terpilih gagal validasi kompatibilitas (versi, bobot, model, cakupan, D4), hasilnya `not_calibrated` dengan alasan itu. Kalibrator lain tidak dicoba.
5. **Tidak ada kalibrator untuk kunci itu** → `indicator_set_mismatch`, dengan rincian "tidak ada kalibrator yang disetujui untuk himpunan …".

Dengan aturan ini, untuk data dan konfigurasi yang sama hasilnya selalu sama, tidak bergantung pada urutan berkas atau waktu muat.

## 5. Mencegah kalibrator yang tidak sesuai, tidak disetujui, atau ber-lineage lain

| Ancaman | A (sekarang) | B1 | B2 (manifes) |
|---|---|---|---|
| Berkas tidak disetujui | C6: sidik berkas | C6 per himpunan | C6 pada manifes, ditambah sidik setiap berkas di manifes; satu byte berubah di mana pun → ditolak |
| Berkas disunting | Ditolak (sidik) | Ditolak | Ditolak (sidik berkas ≠ manifes, atau sidik manifes ≠ setting) |
| Kalibrator salah himpunan | `indicator_set_mismatch` | Bisa salah pasang setting ↔ berkas; perlu cek `indicator_set` di isi berkas sama dengan nama setting | Kunci manifes harus sama dengan `indicator_set` di isi berkas; berbeda → manifes ditolak |
| Lineage berbeda (kriteria, model) | Ditolak / `models_mismatch` | Sama, per berkas | Sama, per berkas. Usulan: manifes juga mencatat `criteria_version` dan memvalidasi semua berkas sebelum ada yang dipakai. |
| Sebagian berkas rusak | — | Per setting | **Usulan gagal tertutup:** satu entri rusak → seluruh manifes `invalid_calibrator` untuk semua peserta (keputusan P1-3) |
| Penyalahgunaan administrator (D-R11) | Terbuka | Terbuka | Terbuka; tidak lebih buruk, karena satu titik persetujuan tetap di setting |

## 6. Perubahan skema database?

**Tidak diperlukan untuk A, B1, maupun B2.**
- Probabilitas tetap satu per peserta di kolom `calibrated_probability` baris `*` (sudah ada).
- `calibration_version` (kolom yang sudah ada) menyimpan versi kalibrator yang terpilih.
- Identitas tambahan masuk metadata JSON baris `*`, seperti di Tahap 3: kunci himpunan, SHA-256 berkas terpilih, dan untuk B2 juga SHA-256 manifes.
- Tidak ada tabel atau kolom baru, dan tidak ada migrasi.

**Konfigurasi:**

| Desain | Setting |
|---|---|
| A | Dua setting Tahap 3 |
| B1 | Setting bertambah per himpunan, dan nama setting bergantung pada daftar himpunan |
| B2 | **Dua setting Tahap 3 yang sama.** Lokasi menunjuk manifes, sidik menunjuk SHA-256 manifes. Loader mengenali format manifes (`eduai-session-calibrator-manifest-1`) selain format berkas tunggal yang sudah ada. |

## 7. Dampak terhadap C6, C7, snapshot, `not_calibrated`, dan kode alasan

| Hal | A | B2 (rekomendasi) |
|---|---|---|
| C6 | Tetap | Diperluas menjadi **rantai**: setting menyimpan SHA-256 manifes; manifes menyimpan SHA-256 tiap berkas. Setting kosong = tidak disetujui (sama). Ketentuan "setting terpisah dari artefak" tetap terpenuhi. |
| C7 | Tetap | Tetap, per kalibrator terpilih. Rincian `tidak_tersedia` dan `berbeda` tetap dibedakan. |
| Snapshot final | Tetap | Tambahan di metadata JSON baris `*`: kunci himpunan, SHA-256 berkas terpilih, SHA-256 manifes. Tetap beku; tidak dihitung ulang. |
| `not_calibrated`, `probability = null` | Peserta di luar himpunan berkas | Hanya peserta yang himpunannya tidak punya kalibrator yang disetujui, atau yang gagal syarat lain |
| Kode alasan (§5.1, 10 kode) | Tetap | **Tetap 10 kode, tanpa kode baru.** "Tidak ada kalibrator untuk himpunan ini" memakai `indicator_set_mismatch` dengan rincian. Manifes rusak memakai `invalid_calibrator` dengan rincian. |

## 8. Dampak terhadap peserta dan Session Report

### 8.1 Peserta dengan himpunan berbeda (termasuk indikasi suara)

**A** (dan B tanpa kalibrator V5+A3):
- Dalam satu sesi, peserta V5 bisa mendapat probabilitas, sedangkan peserta V5+A3 tidak.
- Perbedaan itu muncul karena peserta **memberi persetujuan audio**. Ada risiko persepsi bahwa memberi persetujuan audio "mengubah perlakuan". Ini harus dijelaskan di laporan.
- Bila kalibrator yang dipilih justru V5+A3, peserta tanpa persetujuan audio yang tidak mendapat probabilitas.

**B2** dengan kalibrator untuk kedua himpunan:
- Kedua kelompok bisa mendapat probabilitas, masing-masing dari kalibrator yang dilatih untuk himpunannya.
- Kebutuhan data menjadi kira-kira dua kali lipat (§9).

Dalam semua desain, probabilitas kedua kelompok **tidak** boleh dibandingkan seolah satu skala tanpa catatan, karena berasal dari kalibrator berbeda. Penyajiannya menyebut versi kalibrator.

### 8.2 Komponen Session Report tetap terpisah

| Komponen | Dipengaruhi P1? | Catatan |
|---|---|---|
| Skor indikasi P_i (interval 5 menit, durasi aktual) | Tidak | Rumus Phase 4 tetap |
| Status ALERT per indikasi | Tidak | Kalibrasi tidak membaca dan tidak mengubah ALERT. Lihat catatan definisi ALERT di §8.3. |
| Skor keseluruhan berbobot (P_total) | Tidak | Tetap Σ v_i P_i / Σ v_i atas indikasi yang sah; cakupan **tidak** dikalikan |
| Cakupan | Tidak | Dihitung dan ditampilkan terpisah; dipakai hanya sebagai syarat kelayakan kalibrasi (K2/T3-3) |
| Probabilitas sesi terkalibrasi | **Ya, hanya ini** | Satu per peserta, hanya untuk keseluruhan sesi, tidak pernah per indikasi. `null` + `not_calibrated` bila tidak tersedia atau tidak sah. |
| Snapshot dan PDF | Hanya isi metadata | PDF membaca snapshot final; tidak menghitung ulang prediksi AI, agregasi, atau kalibrasi. Pada A, PDF harus mampu menampilkan "Belum tersedia" untuk sebagian peserta dalam sesi yang sama, beserta alasannya. |

### 8.3 Catatan yang perlu diselaraskan: definisi ALERT

Butir 3 acuan arsitektur menyatakan: **"Status ALERT ditentukan berdasarkan skor agregasi sesi setiap indikasi dan threshold indikasi tersebut."**

Implementasi yang berjalan dan yang dicatat di rancangan Tahap 3 §1.3 dan §2.5 berbeda:
- ALERT (aturan kasus dan pop-up pengawas) ditentukan oleh **jumlah episode** dalam jendela waktu (`cases.rule_status`: `min_count`, `window_s` dari `config.yaml` `summary_rules`);
- ALERT **tidak** ditentukan oleh skor durasi P_i dan threshold skor.

P1 tidak bergantung pada definisi ini, dan kalibrasi tidak menyentuh ALERT dalam definisi mana pun. Namun perbedaan ini harus diputuskan **sebelum G1/G4 dan Phase 6**:
- **Opsi pertama:** ALERT tetap dari aturan episode, dan dokumen acuan disesuaikan.
- **Opsi kedua:** ALERT dari P_i dibandingkan threshold per indikasi. Ini perubahan perilaku yang memerlukan threshold baru, persetujuan, dan evaluasi tersendiri.

Saya tidak mengubah apa pun terkait ALERT (keputusan P1-5).

## 9. Hubungan dengan Tahap 4 (dokumen kebutuhan dataset)

| Hal | A | B2 |
|---|---|---|
| Kebutuhan K5 | Untuk satu himpunan saja | **Per himpunan**: calibration ≥ 50/50 dan test ≥ 100/100 untuk setiap kalibrator |
| Pemisahan (C1) | Satu pasang split | Satu pasang split per himpunan, masing-masing terpisah per peserta dan per sesi ujian. Peserta yang muncul sebagai V5 di satu sesi dan V5+A3 di sesi lain memerlukan aturan penempatan. |
| Registri test split | Satu alur | Per himpunan: sidik test split dan registri dicatat per kunci himpunan |
| Pengumpulan data | Data peserta di himpunan lain tidak terpakai untuk kalibrator itu | Perlu cukup peserta **dengan** dan **tanpa** persetujuan audio yang punya sampel audio. Proporsinya tidak dapat dikendalikan karena persetujuan bersifat sukarela. |
| Ground truth | Definisi target K1 sama | Sama, tetapi pelabelan perilaku suara memerlukan rekaman audio, sehingga butuh persetujuan audio dan prosedur privasi tambahan |

**Usulan:** dokumen Tahap 4 menuliskan kebutuhan **per himpunan** apa pun keputusan P1. Kebutuhan A menjadi kasus khusus (satu himpunan), dan beralih ke B2 kemudian tidak memerlukan dokumen baru.

**Permintaan pemilik proyek untuk Tahap 4:** aturan pemisahan peserta dan sesi ujian harus berlaku **lintas `indicator_set`**. Peserta yang sama tidak boleh menimbulkan kebocoran antara calibration split dan test split lewat himpunan indikasi yang berbeda.

Arah yang akan dirinci di Tahap 4 (belum disetujui):
- Penempatan split ditetapkan **sekali per peserta dan per sesi ujian untuk seluruh dataset**, bukan per himpunan. Seorang peserta yang muncul sebagai V5 di satu sesi dan V5+A3 di sesi lain berada di split yang sama untuk kedua kalibrator.
- Pemeriksaan kebocoran dijalankan atas gabungan semua himpunan, selain atas masing-masing himpunan.
- Registri mencatat sidik test split per himpunan beserta daftar peserta dan sesi ujiannya, agar tumpang tindih lintas himpunan dapat diperiksa.

## 10. Perbandingan konsekuensi teknis

| Aspek | A | B1 | B2 |
|---|---|---|---|
| Cakupan peserta terkalibrasi | Satu himpunan | Semua himpunan yang punya kalibrator | Semua himpunan yang punya kalibrator |
| Perubahan kode | Tidak ada | Loader, setting dinamis | Loader (format manifes, rantai sidik, pemilihan per kunci); tidak ada setting baru |
| Skema database | Tidak | Tidak | Tidak |
| Setting | 2 | 2 per himpunan | 2 (sama dengan sekarang) |
| Titik persetujuan | 1 berkas | N berkas | 1 manifes, yang mengunci N berkas |
| Risiko salah pasang | Rendah | Sedang (nama setting ↔ isi berkas) | Rendah (kunci manifes harus sama dengan isi berkas) |
| Kebutuhan data | 1 × K5 | N × K5 | N × K5 |
| Penyajian dalam satu sesi | Campuran tersedia/tidak, menurut persetujuan audio | Seragam bila semua kalibrator ada | Seragam bila semua kalibrator ada |
| Kode alasan | 10 | 10 | 10 |

## 11. Rekomendasi

1. **Target desain: B2** (manifes yang disetujui, dikunci lewat dua setting C6 yang sudah ada). Alasannya:
   - paling konsisten dengan K3 (satu kalibrator per himpunan);
   - satu titik persetujuan C6;
   - tanpa setting baru, tanpa kode alasan baru, tanpa perubahan skema;
   - pemilihannya deterministik;
   - komponen Session Report tetap terpisah.
2. **Waktu implementasi: ditunda.** B2 dikerjakan saat **ada kalibrator kedua yang lolos evaluasi**, setelah data Tahap 4 terkumpul.
   - Sampai saat itu A (Tahap 3) tetap berlaku, karena saat ini belum ada satu pun kalibrator.
   - A sudah aman dan gagal tertutup: peserta di luar himpunan berkas mendapat `not_calibrated`.
3. **Tahap 4 ditulis per himpunan**, termasuk aturan untuk peserta yang himpunannya berbeda antarsesi dan kebutuhan peserta dengan persetujuan audio.
4. **Bila hanya satu himpunan yang bisa didanai datanya,** urutan prioritas diputuskan pemilik proyek (P1-4). Sebagai pertimbangan: V5 berlaku untuk semua peserta yang punya video, sedangkan V5+A3 hanya untuk peserta yang memberi persetujuan audio dan punya sampel audio.
5. **Definisi ALERT** (§8.3) diselaraskan sebelum G1/G4 dan Phase 6.

## 12. Keputusan yang memerlukan persetujuan pemilik proyek

| ID | Keputusan | Usulan | Status |
|---|---|---|---|
| P1-1 | Desain kalibrator untuk beberapa himpunan | B2 sebagai target; A tetap berlaku sampai ada kalibrator kedua | **Disetujui secara prinsip** (arah desain; implementasi ditunda sampai ada kalibrator kedua yang lolos evaluasi) |
| P1-2 | Cara B2 memakai setting | Dua setting Tahap 3 yang sama; lokasi menunjuk manifes, sidik = SHA-256 manifes (rantai C6) | **Disetujui secara prinsip** |
| P1-3 | Manifes dengan satu entri tidak sah | Gagal tertutup: seluruh manifes `invalid_calibrator` | **Disetujui secara prinsip** |
| P1-4 | Prioritas himpunan untuk pengumpulan data | Diputuskan pemilik proyek; dokumen Tahap 4 tetap ditulis per himpunan, dengan pemisahan lintas himpunan (§9) | **Terbuka** |
| P1-5 | Definisi ALERT (episode vs skor + threshold) | Lihat `EDUAI_SESSION_REPORT_P1_5_AL3_DECISION_ANALYSIS.md` | **Diputuskan (21 November 2026)**: **S1**, dua mekanisme terpisah; Live Rule Alert tidak diubah |
| P1-6 | Penyajian campuran tersedia/tidak dalam satu sesi (Phase 6) | Tampilkan "Belum tersedia" beserta alasan dan versi kalibrator per peserta; tidak ada probabilitas per indikasi | **Disetujui secara prinsip** (diterapkan saat Phase 6 disetujui) |

## 13. Dampak terhadap rangkaian final Session Report

| Butir acuan | Dampak P1 |
|---|---|
| 1. Interval 5 menit dengan durasi aktual | Tidak ada |
| 2. Skor per indikasi | Tidak ada |
| 3. ALERT per indikasi | Tidak ada dari P1. Definisi ALERT diputuskan P1-5 = S1 (Live Rule Alert dan Session Indication Alert terpisah); implementasi masih terbuka. |
| 4. Skor keseluruhan berbobot dari indikasi yang sah | Tidak ada; `weights_used` hanya **dibaca** sebagai kunci pemilihan |
| 5–6. Cakupan terpisah dan tidak dikalikan | Tidak ada; cakupan hanya syarat kelayakan kalibrasi |
| 7. Kalibrasi hanya untuk keseluruhan sesi | Tetap; satu probabilitas per peserta per sesi, tidak per indikasi |
| 8. Tanpa kalibrator sah → `probability = null`, `not_calibrated` | Tetap, untuk A maupun B2 |
| 9. Snapshot final sebagai sumber utama | Tetap; hanya metadata JSON bertambah pada B2 |
| 10. PDF tidak menghitung ulang | Tetap |

## 14. Batas pekerjaan yang belum dilakukan

- Tidak ada perubahan kode, database, konfigurasi, data, atau commit.
- B1/B2 belum diimplementasikan; A dari Tahap 3 tetap berlaku. Persetujuan P1-1/2/3/6 adalah persetujuan arah desain, bukan implementasi.
- Tahap 4 (dokumen kebutuhan dataset) belum dimulai.
- G1–G4 dan Phase 6 belum dimulai; definisi ALERT belum diselaraskan.
- K7 tetap terbuka.
- Migrasi database produksi belum disetujui; backend kode baru belum dijalankan terhadap database produksi.
- Tidak ada probabilitas per indikasi, dan tidak ada perubahan pada rumus agregasi, aturan data kosong, cakupan, atau snapshot final.
