# Desain Teknis: Session Summary per Interval (P_i dan P_total)

Status: **draf untuk disetujui. Belum ada kode yang diubah.**
Tanggal: 20 November 2026
Dasar: audit Session Summary (20 Nov 2026) dan *Addendum: Partial Interval Weighting*.

---

## 1. Tujuan dan batas makna

Untuk setiap peserta dalam satu sesi, sistem menghitung:

- **p_i,k**: nilai indikasi *i* pada interval *k*;
- **P_i**: nilai indikasi *i* untuk seluruh sesi, rata-rata berbobot durasi interval;
- **P_total**: gabungan semua P_i, dengan bobot jenis indikasi (opsional).

**Makna yang diusulkan** (lihat keputusan K1): p_i,k = **proporsi waktu pengamatan yang dapat dianalisis, saat indikasi i aktif**, di interval k.

Angka ini **bukan** probabilitas kecurangan, **bukan** akurasi model, dan **bukan** confidence detektor. Karena itu semua tampilan memakai nama "proporsi waktu terindikasi", dan setiap angka disertai cakupan pengamatan. Status alert tetap berasal dari `summary_rules` (`cases.rule_status`), terpisah dari angka ini.

---

## 2. Pembagian interval

### 2.1 Jendela sesi per peserta

```
S = awal sesi, E = akhir sesi   (detik epoch, timestamp aktual)
```

Usulan (keputusan K2):

- **S** = `exams.monitoring_started_at`. Bila kosong, pakai awal jadwal (`summary.exam_window`).
- **E** = `report.session_end(exam)`, yaitu yang lebih awal antara "ditandai Selesai" dan akhir jadwal. Bila sesi masih berjalan, E = sekarang dan hasilnya berstatus *sementara*.

Jendela ini **sama untuk semua peserta satu sesi**, sehingga interval sejajar antarpeserta dan bisa dibandingkan. Peserta yang terlambat bergabung punya interval awal berstatus "tanpa data" (lihat 2.4).

### 2.2 Batas interval

```
T = 300 detik
N_penuh = floor((E - S) / T)
interval k (k = 0, 1, …):  [S + kT, min(S + (k+1)T, E))      setengah terbuka, tidak tumpang tindih
d_k = min(S + (k+1)T, E) - (S + kT)
interval terakhir dibuat hanya bila d_k > 0                 (tidak pernah ada interval berdurasi 0)
w_k = d_k / 300
```

Batas setengah terbuka `[a, b)` menjamin satu detik hanya masuk ke satu interval (persyaratan 3).

### 2.3 Contoh wajib

| Sesi | Interval | Bobot |
|---|---|---|
| 52 menit (3.120 dtk) | 10 × 300 dtk + 1 × 120 dtk | 10 × 1,0 + **0,4**; Σw = 10,4 |
| 50 menit (3.000 dtk, kelipatan tepat) | 10 × 300 dtk | 10 × 1,0; **tidak ada** interval ke-11 berdurasi 0 |
| 3 menit (180 dtk, < 5 menit) | 1 × 180 dtk | **0,6**; P_i = p_i,0 karena bobot ternormalisasi |
| 30 detik | 1 × 30 dtk | 0,1 |

### 2.4 Waktu aktif dan waktu yang dapat dianalisis

Untuk peserta *s*, indikasi *i*, dan interval *k*:

```
a_i,k = detik indikasi aktif di dalam interval
        = Σ panjang irisan [episode] ∩ [interval]
        episode = cases.episodes_of(events indikasi i peserta s)
        → kejadian yang bertumpuk (worker + browser) digabung lebih dulu, jadi tidak terhitung dua kali (persyaratan 4)
        → episode yang melewati batas interval dipotong, dan tiap bagian masuk ke intervalnya sendiri

u_k  = detik yang dapat dianalisis di interval
     = detik dengan frame yang benar-benar dianalisis − detik CANNOT_ANALYZE (episode, digabung)

c_k  = u_k / d_k          cakupan pengamatan (0..1)
```

**p_i,k** (usulan K1):

```
bila u_k > 0:  p_i,k = a_i,k / u_k        (dibatasi 0..1)
bila u_k = 0:  p_i,k = 0, dengan alasan_tanpa_data      (keputusan pemilik proyek, persyaratan 7)
```

Alasan tanpa data, dari yang paling spesifik:

1. `belum_bergabung` / `sudah_keluar` (presence);
2. `tidak_ada_frame` (tidak ada frame dianalisis);
3. `tidak_dapat_dianalisis` (seluruh waktu `CANNOT_ANALYZE`);
4. `model_tidak_siap`.

### 2.5 Agregasi temporal (addendum)

```
P_i = Σ_k (w_k × p_i,k) / Σ_k w_k
```

Interval tanpa data ikut dihitung dengan p = 0. Itu keputusan pemilik proyek. Akibatnya P_i turun bila banyak interval tanpa data, sehingga P_i **wajib** ditampilkan bersama:

```
C_i = Σ_k (w_k × c_k) / Σ_k w_k        cakupan berbobot (sama untuk semua i)
n_tanpa_data = jumlah interval dengan u_k = 0
```

Jadi P_i = 0 dengan C = 0 % berarti "tidak teramati", bukan "bersih".

### 2.6 Agregasi indikasi (P_total)

Bobot jenis indikasi **hanya** dipakai di tahap ini, tidak dicampur dengan bobot durasi:

```
P_total = Σ_i (v_i × P_i) / Σ_i v_i
v_i      = bobot jenis dari config.yaml (session_summary.indicator_weights); bawaan 1 untuk semua → rata-rata biasa
```

Contoh uji pemilik proyek: HP 0,50, indikasi 2 0,60, indikasi 3 0,80, indikasi 4 0,50, v = 1 → (0,5 + 0,6 + 0,8 + 0,5) / 4 = **0,60**.

Contoh berbobot (ilustrasi uji, bukan usulan bobot): v = (2, 1, 1, 1) → (1,0 + 0,6 + 0,8 + 0,5) / 5 = **0,58**.

Bobot yang dipakai dan versi config **disimpan bersama hasil**, sehingga laporan bisa ditelusuri.

---

## 3. Sumber data dan kesenjangan

| Data | Ada sekarang? | Sumber |
|---|---|---|
| Episode per indikasi (timestamp aktual, gabungan) | **Ada** | tabel `events`, `cases.episodes_of` |
| Periode `CANNOT_ANALYZE` | **Ada** | tabel `events` (kategori `cannot_analyze`) |
| Bergabung / keluar | **Ada** | tabel `presence` (`joined_at`, `left_at`) |
| Detik yang benar-benar dianalisis per peserta | **Tidak ada** (hanya di memori, `PerfStats`, hilang saat restart) | **perlu tabel baru**, lihat 4.1 |
| Jendela sesi S/E | **Ada** | `exams.monitoring_started_at`, `report.session_end` |

### Cara menghitung detik yang dianalisis (timestamp aktual, bukan jumlah frame)

Untuk setiap frame yang dianalisis, dengan timestamp server t (jam server, sesuai G-F1), selisih dengan frame sebelumnya dari peserta yang sama dihitung sebagai:

```
Δ = t - t_prev,   dihitung sebagai waktu teramati hanya bila Δ ≤ G (usulan G = 2,0 dtk; keputusan K6)
```

Jeda yang lebih panjang dianggap **tidak teramati**, misalnya browser tertutup atau jaringan putus. Cara ini tetap benar walau laju frame berbeda: browser 2 fps, worker 5 fps.

---

## 4. Penyimpanan (perubahan skema; perlu persetujuan)

Sesuai aturan proyek, perubahan skema dijelaskan dulu. Semua perubahan bersifat **aditif**: tabel baru, tanpa mengubah atau menghapus kolom lama.

### 4.1 `observation_coverage`: waktu yang dianalisis, ditulis saat analisis berjalan

| Kolom | Tipe | Arti |
|---|---|---|
| exam_id, student_id | INTEGER | sesi dan peserta |
| bucket_start | TEXT (ISO UTC) | awal ember 60 detik (disejajarkan ke menit) |
| analysed_s | REAL | detik teramati (Δ ≤ G) di ember ini |
| frames | INTEGER | frame dianalisis (informasi, bukan dasar hitung) |
| source | TEXT | browser / jitsi / livekit |
| updated_at | TEXT | |

PK `(exam_id, student_id, bucket_start, source)`.

- Ember 60 detik, bukan 300, supaya interval yang dimulai dari S (tidak sejajar menit) bisa disusun ulang dengan galat ≤ 1 ember. Untuk ketelitian penuh di batas ember, `analysed_s` bisa dipecah per detik. Usulan: ember 60 dtk + pemotongan proporsional di batas (keputusan K7).
- **Ditulis oleh:** `AIManager.persist` (jalur browser/Jitsi) dan `POST /api/ai/status` (worker). Status worker sudah membawa `ts`. Penulisan dilakukan secara agregat (UPSERT per ember), tidak per frame, supaya beban SQLite kecil.
- **Retensi:** ikut umur data sesi (tidak memuat gambar atau data pribadi baru).

### 4.2 `session_summary_interval`: hasil per interval (dibekukan saat laporan difinalisasi)

| Kolom | Arti |
|---|---|
| exam_id, student_id, indicator, k | kunci |
| start_ts, end_ts, d_s, w | batas, durasi aktual, dan bobot interval (persyaratan 5) |
| active_s, analysable_s, coverage | a_i,k, u_k, c_k |
| p | p_i,k |
| no_data_reason | NULL bila ada data |
| algo_version, computed_at | |

### 4.3 `session_summary`: hasil per peserta

| Kolom | Arti |
|---|---|
| exam_id, student_id, indicator | kunci; indicator `*` = baris P_total |
| value | P_i atau P_total |
| sum_w, n_intervals, n_no_data, coverage | Σw, jumlah interval, interval tanpa data, C |
| weights_json, config_version, algo_version, computed_at, final | bobot v yang dipakai; final = 1 setelah laporan final |

### 4.4 Kapan dihitung

- **Sebelum final:** dihitung saat diminta (fungsi murni dari `events` + `observation_coverage` + `presence`), tidak disimpan, berlabel *sementara*.
- **Saat finalisasi laporan** (`finalize_report`): hasil ditulis ke 4.2 dan 4.3 dalam transaksi yang sama dengan `report_finals`, lalu PDF/XLSX final membaca hasil yang dibekukan. Pola ini sama dengan `report_frames`.

### 4.5 Dampak dan kompatibilitas

- Migrasi aditif (`CREATE TABLE IF NOT EXISTS`). Tidak ada perubahan pada `events`, `exam_summaries`, atau tabel lain.
- Sesi lama tidak punya `observation_coverage`, sehingga u_k = 0 di semua interval, p = 0, dan alasannya `tidak_ada_data_cakupan (sesi sebelum fitur)`. Laporan lama harus menampilkan "tidak tersedia untuk sesi sebelum <tanggal>", **bukan** 0 %. Ini pengecualian yang diusulkan atas aturan "tanpa data = 0" (keputusan K8).
- Database produksi baru tersentuh saat backend dijalankan dengan versi baru (migrasi otomatis). Tes memakai database sementara.

---

## 5. Indikasi yang dihitung

| Kelompok | Masuk P_i / P_total? | Catatan |
|---|---|---|
| FACE_ABSENT, MULTIPLE_PERSONS, HEAD_TURN, PHONE_VISIBLE, BOOK_VISIBLE | Ya | episode berdurasi |
| HEAD_TURN_REPEATED | **Usulan: tidak** | kejadian instan yang dibangun dari episode HEAD_TURN yang sudah dihitung. Memasukkannya berarti menghitung perilaku yang sama dua kali. Tetap tampil sebagai jumlah. (K3) |
| Label suara berkategori indikasi (OTHER_VOICE, WHISPER, BOOK_SOUND) | Ya, **hanya bila persetujuan audio diberikan**; tanpa persetujuan: dikecualikan (bukan 0) | (K4) |
| Kategori info (STUDENT_SPEECH, MEDIA_SOUND) | Tidak | konteks, bukan indikasi |
| CANNOT_ANALYZE | Tidak (menjadi cakupan) | |
| Indikasi backend (CAMERA_OFF, MIC_OFF, LOCKDOWN_LOST) | Usulan: tidak di versi pertama | sumber dan maknanya berbeda (K3) |

---

## 6. Tampilan

- **PDF** (bagian IV-b baru, setelah "Ringkasan per indikasi"): satu tabel **per peserta**. Baris = indikasi (P_i dalam persen satu desimal, cakupan C, interval tanpa data), ditambah baris **P_total** dengan keterangan bobot. Catatan kaki: "proporsi waktu terindikasi dari waktu yang dapat dianalisis; bukan peluang pelanggaran; status alert ditentukan aturan terpisah". Tabel per peserta menambah halaman sesuai jumlah peserta (keputusan K9: PDF per peserta atau hanya peserta yang punya indikasi).
- **XLSX:** sheet "Interval" (semua baris 4.2: d_k, w_k, a, u, c, p, alasan) dan sheet "Ringkasan sesi" (4.3). Detail interval tidak dimasukkan ke PDF.
- **API:** `GET /api/sessions/{id}/session-summary` (staf) mengembalikan struktur yang sama.

Status alert, yaitu `rule.met` dari `summary_rules`, ditampilkan di kolom terpisah dan **tidak** diturunkan dari P_i atau P_total (persyaratan 7 audit).

---

## 7. Rencana uji (data buatan, jawaban diketahui)

| # | Kasus | Harapan |
|---|---|---|
| T1 | Sesi 52 menit | 11 interval: 10 × w = 1,0 dan 1 × w = **0,4**; Σw = 10,4; batas tidak tumpang tindih; d_10 = 120 dtk |
| T2 | Sesi 50 menit (kelipatan tepat) | 10 interval; tidak ada interval d = 0 |
| T3 | Sesi 3 menit | 1 interval w = 0,6; P_i = p_i,0 |
| T4 | Agregasi temporal | p = (0,2 × 10 interval penuh, 0,5 di interval 0,4) → P = (2,0 + 0,2) / 10,4 = 0,2115 |
| T5 | Episode melewati batas interval | Episode 290–310 dtk → 10 dtk di k = 0, 10 dtk di k = 1 |
| T6 | Kejadian ganda (worker + browser bertumpuk) | Waktu aktif dihitung sekali |
| T7 | Interval tanpa data | p = 0, `no_data_reason` terisi, cakupan 0, tetap ikut Σw |
| T8 | Timestamp, bukan jumlah frame | 2 fps dan 5 fps pada perilaku yang sama → P_i sama |
| T9 | Jeda > G | tidak dihitung sebagai waktu teramati |
| T10 | P_total tanpa bobot | 0,5 / 0,6 / 0,8 / 0,5 → **0,60** |
| T11 | P_total berbobot | v = (2, 1, 1, 1) → 0,58; bobot durasi tidak berubah |
| T12 | Pemisahan alert | Mengubah `summary_rules` tidak mengubah P_i; mengubah episode tidak mengubah ambang |
| T13 | Finalisasi | Hasil dibekukan; PDF final membaca hasil beku; tidak berubah setelah data lain bertambah |
| T14 | Sesi lama tanpa cakupan | "tidak tersedia", bukan 0 % (bila K8 disetujui) |

---

## 8. Keputusan yang perlu disetujui

| ID | Pertanyaan | Usulan |
|---|---|---|
| **K1** | Makna p_i,k | Proporsi waktu terindikasi dari waktu yang **dapat dianalisis** (a/u). Alternatif: a/d_k, yang membuat celah pengamatan ikut menurunkan p. |
| **K2** | Jendela sesi S–E | Mulai pemantauan → `session_end`; sama untuk semua peserta |
| **K3** | HEAD_TURN_REPEATED dan indikasi backend | Tidak masuk P (tetap tampil sebagai jumlah) |
| **K4** | Indikasi suara tanpa persetujuan audio | Dikecualikan dari P_total, tidak dihitung 0 |
| **K5** | Bobot jenis v_i | Bawaan 1 (rata-rata biasa); nilai lain ditetapkan Program Studi di `config.yaml` |
| **K6** | Batas jeda G | 2,0 dtk |
| **K7** | Ukuran ember cakupan | 60 dtk dengan pemotongan proporsional |
| **K8** | Sesi sebelum fitur ini | "Tidak tersedia", bukan 0 % |
| **K9** | PDF | Tabel untuk semua peserta yang hadir, atau hanya yang punya indikasi |
| **K10** | Skema | Tiga tabel baru (bagian 4), migrasi aditif |

Implementasi baru dimulai setelah keputusan K1–K10 disetujui.
