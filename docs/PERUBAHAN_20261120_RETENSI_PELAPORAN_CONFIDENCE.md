# Perubahan 20 November 2026: retensi uji coba, satuan hitung laporan, statistik frame

Dasar: [EDUAI_TECHNICAL_CODEBASE_AUDIT.md](EDUAI_TECHNICAL_CODEBASE_AUDIT.md). Ruang lingkup disetujui pengguna dalam empat keputusan.

Yang **tidak** diubah:

- skema SQLite;
- model (ONNX maupun TFLite);
- mekanisme `run_retention`;
- metadata bukti lama;
- eye tracking;
- P5;
- tampilan frontend.

Cadangan file sebelum diubah ada di `..\EduAI_cadangan_20261120\` (`tahap1/`, `tahap2/`), di luar repositori.

---

## Keputusan 1: retensi bukti selama uji coba

**Perubahan di `backend/.env`.** File ini diabaikan git. Cadangannya: `backend/.env.bak-20261120-retensi`.

| Kunci | Sebelum | Sesudah |
|---|---|---|
| `EDUAI_EVIDENCE_RETENTION_HOURS` | 24 | 876000 (±100 tahun) |
| `EDUAI_EVIDENCE_HOLD_DAYS` | tidak diatur (bawaan 7) | 36500 |
| `EDUAI_REPORT_FRAME_RETENTION_HOURS` | tidak diatur (bawaan 24) | 876000 |

**Verifikasi (hanya baca, tanpa menjalankan backend atau `run_retention`):**

- `load_settings()` membaca ketiga nilai baru, dan tidak ada variabel lingkungan OS yang menimpanya. Backend memakai nilai baru setiap kali dijalankan ulang.
- Ada **148 paket** di `backend/data/evidence`, semuanya dengan `meta.json` valid.
- Dengan rumus yang sama seperti `EvidenceStore._expired` (`max(created_at + retensi_saat_ini, hold_until) < sekarang`), **148/148 tidak kedaluwarsa**. Paket tertua (15 Nov 2026) baru akan kedaluwarsa pada 22 Okt 2126.
- Paket lama ikut terlindungi tanpa mengubah metadatanya, karena `_expired` memakai retensi *saat ini*, bukan nilai yang tersimpan saat paket dibuat.
- Kolom `evidence.expires_at` di database tetap menampilkan tanggal lama. Kolom ini hanya informasi dan tidak dipakai untuk menghapus (lihat E17 di audit).
- Saat perubahan dibuat, backend tidak sedang berjalan.

**Hal yang perlu diketahui:**

- ~~Teks persetujuan mahasiswa masih menyebut "24 jam … 7 hari".~~ **Sudah diperbaiki**, lihat bagian "Teks persetujuan mahasiswa" di bawah. Teks kini mengikuti pengaturan yang berlaku.
- Akibat sampingan di tes: lihat bagian Tahap 0.

**Cara mengembalikan setelah uji coba:**

1. Hentikan backend.
2. Di `backend/.env`, ubah kembali nilainya:
   ```
   EDUAI_EVIDENCE_RETENTION_HOURS=24
   EDUAI_EVIDENCE_HOLD_DAYS=7
   EDUAI_REPORT_FRAME_RETENTION_HOURS=24
   ```
   Dua baris terakhir boleh dihapus, karena bawaannya sama.
3. Sadari dampaknya **sebelum** menjalankan backend lagi: pada `run_retention` pertama (saat backend mulai, lalu tiap 30 detik), semua paket yang lebih tua dari 24 jam akan terhapus permanen. Pengecualiannya paket milik sesi yang belum final dan masih dalam 7 hari setelah ujian. Arsipkan dulu bila bukti uji coba masih dibutuhkan.

---

## Tahap 0: baseline tes (`.venv`: Python 3.14.3)

| Paket | Hasil |
|---|---|
| Backend | 229 lulus, **5 gagal**, 2 dilewati (109 dtk) |
| Modul AI | 77 lulus, 2 dilewati (4 dtk) |
| Frontend `npm test` | 116 lulus |
| Frontend `npm run lint` | 1 error di `src/SnapshotVideo.tsx:8` (file belum di-commit, di luar ruang lingkup, tidak disentuh) |
| E2E | tidak dijalankan: butuh backend dan frontend nyata dengan database demo |

**Kelima kegagalan backend disebabkan perubahan `.env` di Keputusan 1, bukan bug kode:**

- Tes yang gagal: `test_health`, `test_event_without_image_and_deleted_image`, `test_final_copy_expires_24h_after_finalisation_and_is_audited`, `test_hold_ends_seven_days_after_session_end`, dan `test_marking_selesai_early_starts_the_clock`.
- Penyebabnya: `backend/app/main.py:121` menjalankan `create_app()` saat modul diimpor. `load_settings()` lalu memasukkan isi `.env` asli ke `os.environ` proses tes, sementara `make_settings()` di tes tidak menetapkan nilai retensi.
- Kelima tes lulus bila nilai lama dipasang hanya di proses tes:
  ```
  EDUAI_EVIDENCE_RETENTION_HOURS=24 EDUAI_EVIDENCE_HOLD_DAYS=7 EDUAI_REPORT_FRAME_RETENTION_HOURS=24
  ```
- Database dan folder bukti tes selalu di `tmp_path`, dan `.env` asli hanya dibaca, tidak ditulis.
- Hash 1.834 file di `backend/data` identik sebelum dan sesudah semua tes.
- **Sudah diperbaiki**, lihat bagian "Isolasi tes dari `.env` lokal" di bawah. Nilai retensi lama di proses tes tidak diperlukan lagi.

**Dilewati:** dua tes butuh `scikit-image`, yang tidak terpasang. Dua lainnya khusus POSIX.

---

## Tahap 1: satu satuan hitung untuk laporan, ringkasan, dan daftar kasus

**Definisi**, ditulis di `cases.episodes_of`:

- **Kejadian** = satu baris tabel `events`. Ini satuan yang ditinjau pengawas dan yang didaftar di tabel IV PDF.
- **Indikasi (episode)** = kejadian dengan ujian, mahasiswa, dan indikator yang sama, yang waktunya bertumpuk atau bersambung (≤ `EPISODE_JOIN_S` = 2 dtk). Kumpulan ini dihitung **satu**. Contoh sumbernya: worker restart, atau frame fallback browser yang dianalisis bersamaan dengan worker.

**Masalah yang diperbaiki:**

| Masalah (audit) | Sebelum | Sesudah |
|---|---|---|
| E5: jumlah di PDF berbeda dari ringkasan pengawas | Kalimat PDF memakai jumlah baris kejadian; ringkasan memakai episode | Kalimat PDF memakai `episodes` dari fungsi yang sama dengan ringkasan. Bila ada kejadian yang digabung, kalimat menjelaskan berapa baris kejadian di tabel. |
| E6: durasi kasus dihitung ganda | `total_duration_s` = jumlah durasi semua kejadian | Jumlah durasi episode gabungan |
| E7: waktu "tidak dapat dianalisis" | PDF melewatkan periode yang masih terbuka; ringkasan memakai waktu sekarang; keduanya menghitung baris yang bertumpuk dua kali | Keduanya memakai `episodes_of` + `episode_seconds`: periode bertumpuk dihitung sekali, periode terbuka berakhir "sekarang" |

**Yang tetap:**

- Tabel IV PDF tetap satu baris per kejadian.
- Peninjauan dan finalisasi tetap per kejadian.
- Kunci `total`, `valid`, `invalid`, `further`, dan `unreviewed` tetap menghitung kejadian.
- Tampilan frontend tidak diubah.
- Laporan kini punya kunci tambahan `indications.episodes`.

**File yang diubah:**

| File | Perubahan |
|---|---|
| `backend/app/cases.py` | Fungsi baru `episodes_of()` dan `episode_seconds()`; `summarize()` menghitung `total_duration_s` dari episode |
| `backend/app/summary.py` | `cannot_analyze.periods` dan `total_s` memakai `episodes_of` |
| `backend/app/api.py` | `_report_summary()` menambah `episodes` dan memakai aturan episode untuk periode tidak dapat dianalisis; `_report_rows()` mengambil kolom lengkap untuk periode itu |
| `backend/app/report_export.py` | Kalimat bagian IV memakai jumlah indikasi |
| `backend/tests/test_report.py` | Ekspektasi `indications` ditambah `"episodes": 1` (tiga kejadian di detik yang sama) |
| `backend/tests/test_counting_units.py` | **Baru**, 6 tes: jumlah laporan = ringkasan, durasi tanpa hitung ganda, waktu tidak dapat dianalisis sama di kedua tempat, periode terbuka, dua varian kalimat PDF |

**Regresi:** backend 240 lulus, 0 gagal, 2 dilewati.

---

## Tahap 2: confidence dan jumlah frame di kolom `details`

Disimpan di kolom JSON `events.details` yang sudah ada (`stats_version: 1`). Skema SQLite tidak berubah.

| Indikator | `n_frames` | Confidence |
|---|---|---|
| `PHONE_VISIBLE` | Ya: frame tempat detektor berjalan dan sinyal aktif | `confidence = {source, peak, mean, n}` dari skor EfficientDet-Lite0 `cell phone` |
| `BOOK_VISIBLE` | Ya | `book_sources.coco` dan `book_sources.clip` **terpisah**, masing-masing `{source, n, passed, peak, mean}`, hanya dari frame tempat model itu berjalan. `score_note` menjelaskan bahwa `score` event = nilai tertinggi dari sinyal yang lolos, dengan skala berbeda |
| `FACE_ABSENT`, `MULTIPLE_PERSONS`, `HEAD_TURN`, `CANNOT_ANALYZE` | Ya | **Tidak ada**, karena tidak ada confidence model. Nilai `HEAD_TURN` adalah sudut dan nilai `MULTIPLE_PERSONS` adalah jumlah orang, jadi tidak disimpan sebagai confidence |
| Label suara (`OTHER_VOICE`, `WHISPER`, …) | Tidak | Tidak diubah. Skor YAMNet datang dengan laju berbeda dari frame video, dan satu sampel audio dipakai ulang di beberapa frame, sehingga rata-rata per frame akan bias. `details` lama (puncak per jenis suara) tetap. |
| `HEAD_TURN_REPEATED` | Tidak | Kejadian instan tanpa rangkaian frame |

**Catatan definisi:**

- `n_frames` dihitung dari frame aktif pertama masa kandidat (sebelum event dibuka) sampai event ditutup. Frame non-aktif selama masa rilis tidak ikut dihitung.
- Event `open` membawa statistik sampai saat dibuka. Event `closed` membawa statistik seluruh episode dan menggantikan nilai `open` di database.
- `mean` adalah **rata-rata confidence deteksi** atas frame episode. Ini bukan peluang kecurangan dan bukan akurasi.
- Data historis tidak diisi ulang. Event lama tanpa `details` tetap tanpa statistik ("tidak tersedia", bukan 0).

**Perbaikan terkait (E3):** saat pemantauan dihentikan (`flush`), event penutup kini membawa skor puncak sebenarnya. Sebelumnya skornya `None`, sehingga database menyimpan puncak dari saat event dibuka.

**Validasi di jalur worker OpenVidu.** Sebelumnya `EventIn.details` hanya menerima `SoundDetails` (`extra="forbid"`, wajib `sound_type`). Tanpa perubahan schema, setiap kiriman event ponsel/buku dengan statistik akan **ditolak 422 seluruh batch-nya, dan event-nya hilang**. Sekarang `details` menerima `SoundDetails` atau `FrameStatsDetails`. Keduanya tetap `extra="forbid"`, dengan batas nilai 0–1 untuk peak/mean dan n ≥ 1. Kunci asing seperti `cheating_probability` tetap ditolak.

**File yang diubah:**

| File | Perubahan |
|---|---|
| `ai/eduai-ai/src/eduai_ai/temporal.py` | `SustainedIndicator`: `n_active`, `n_valued`, `value_sum`, `stats()`, `closed_stats`. `EventEngine`: `FRAME_STATS`, `_with_stats()`, `_score_of()`, akumulator per sumber buku `_book_acc`; `flush()` mengirim skor puncak |
| `ai/eduai-ai/src/eduai_ai/events.py` | Komentar bentuk `details` |
| `backend/app/schemas.py` | Model baru `ConfidenceStats`, `BookSourceStats`, `FrameStatsDetails`; `EventIn.details` menerima salah satu |
| `backend/app/api.py` | `ingest_events`: statistik frame disimpan tanpa kunci kosong; impor `FrameStatsDetails` |
| `ai/eduai-ai/tests/test_frame_stats.py` | **Baru**, 6 tes |
| `backend/tests/test_frame_stats_ingest.py` | **Baru**, 3 tes: event asli dari `EventEngine` lewat `/api/ai/events` tersimpan, kunci/nilai salah ditolak, data lama tidak diisi |

**Regresi akhir:**

| Paket | Hasil |
|---|---|
| Modul AI | 83 lulus, 0 gagal, 2 dilewati |
| Backend | 243 lulus, 0 gagal, 2 dilewati (dengan nilai retensi lama di proses tes, lihat Tahap 0) |
| Frontend `npm test` | 116 lulus (frontend tidak diubah) |
| Data produksi | Hash `backend/data` identik dengan sebelum Tahap 0 (0 hilang, 0 baru, 0 berubah) |

`backend/app/api.py` juga berisi perubahan Anda yang belum di-commit (endpoint snapshot/`live_frames`). Perubahan tahap ini terbatas pada `_report_summary`, `_report_rows`, `ingest_events`, dan baris impor schema.

---

## G-K1: pemantauan FPS dan latensi

Dasar: [EDUAI_GITHUB_REFERENCE_IMPLEMENTATION_AUDIT.md](EDUAI_GITHUB_REFERENCE_IMPLEMENTATION_AUDIT.md) B1, padanan `sentinel/core/metrics.py` (Sentinel) dan penghitung FPS `js/main.js` (ProctorAI). Cadangan file ada di `EduAI_cadangan_20261120\gk1_fps_latensi\`.

**Yang diukur, hanya di memori** (tanpa tabel, tanpa skema, tanpa dependency baru):

| Ukuran | Sumber |
|---|---|
| Latensi total `StudentAnalyzer.process` per frame | `pipeline.py` |
| Latensi per komponen yang benar-benar berjalan: `prepare` (resize + konversi warna), `quality`, `face`, `landmarks`, `objects`, `clip` | `perception.py` → `FrameSignals.metrics["timing_ms"]` |
| `decode` (JPEG → gambar) dan `queue_wait` (antre di semafor analisis global) | `ai_service.py` (jalur browser/Jitsi) |
| FPS efektif = (n − 1) / rentang waktu frame dalam jendela 60 dtk | `perf.py` |
| Frame diterima dan dibuang "busy" per mahasiswa | `ai_service.py` (`_Entry`) |
| Jumlah frame per status (`analyzed` / `cannot_analyze` / `model_unavailable`) | `perf.py` |

Persentil memakai *nearest rank*. Bila sebuah aliran berhenti, sampel di luar jendela dibuang, sehingga `fps` menjadi `None`, bukan angka lama.

**Akses.** `GET /api/ai/performance` hanya untuk **admin**, karena memuat id ujian dan mahasiswa. `/api/ai/health` yang publik **tidak diubah** dan tidak memuat data per mahasiswa (ada tesnya).

**Overhead terukur** di laptop yang sama dengan audit, `.venv` proyek:

- `PerfStats.record()`: 0,73 µs/frame;
- `snapshot()` dengan jendela penuh (301 sampel): 0,18 ms per panggilan, dan hanya terjadi saat admin membuka endpoint.

**Contoh angka nyata.** `StudentAnalyzer` dengan model asli, 40 frame acak 640×480 tanpa wajah, jam simulasi 5 fps:

| Komponen | n | Median (ms) | p90 (ms) |
|---|---|---|---|
| total | 40 | 8,7 | 96,0 |
| prepare | 40 | 0,4 | 0,7 |
| quality | 40 | 3,8 | 4,4 |
| face | 40 | 2,0 | 3,5 |
| landmarks | 3 | 10,4 | 14,5 |
| objects | 14 | 30,9 | 50,8 |
| clip | 14 | 45,2 | 74,1 |

Catatan tentang angka ini:

- Hanya contoh, bukan benchmark: frame acak, satu perangkat, satu proses. Benchmark yang bisa diulang adalah G-K2.
- `landmarks` jalan 3 kali karena BlazeFace sesekali "menemukan" wajah pada derau acak.
- **Temuan sampingan:** pada 5 fps, detektor objek dan CLIP efektif berjalan tiap **0,6 dtk** (14 dari 40 frame), bukan 0,5 dtk. Penyebabnya: syarat `ts − terakhir ≥ phone_every_s` baru terpenuhi di setiap frame ketiga. Perilaku ini tidak diubah.

**Belum tercakup:**

- Lag ambil→proses di jalur browser: waktu ambil di browser belum dikirim (G-F1).
- Analyser di worker OpenVidu: `StudentAnalyzer.perf` sudah terisi di proses worker, tetapi belum dikirim ke backend.
- Tampilan di UI admin.
- Memori/CPU proses (G-K2, butuh `psutil` untuk soak test).

**File:**

| File | Perubahan |
|---|---|
| `ai/eduai-ai/src/eduai_ai/perf.py` | **Baru**: `PerfStats` (jendela waktu, thread-safe), `summarize_ms` |
| `ai/eduai-ai/src/eduai_ai/perception.py` | `process()` mengisi `metrics["timing_ms"]`; metrik kualitas tetap ada |
| `ai/eduai-ai/src/eduai_ai/pipeline.py` | `StudentAnalyzer.perf`; `process()` mencatat setiap frame |
| `backend/app/ai_service.py` | `_Entry.received/dropped`; `queue_wait` dan `decode` dicatat; `AIManager.performance()` |
| `backend/app/api.py` | `GET /api/ai/performance` (admin) |
| `docs/API.md` | Baris endpoint baru |
| `ai/eduai-ai/tests/test_perf.py` | **Baru**, 5 tes (termasuk model MediaPipe asli) |
| `backend/tests/test_ai_performance.py` | **Baru**, 4 tes: hanya admin, `/ai/health` tetap tanpa data per mahasiswa, FPS/latensi dari frame browser, hitungan busy per mahasiswa |

**Regresi:**

| Paket | Hasil |
|---|---|
| Modul AI | 88 lulus, 0 gagal, 2 dilewati |
| Backend | 247 lulus, 0 gagal, 2 dilewati (nilai retensi lama di proses tes) |
| Frontend | tidak diubah |

---

## G-K2: benchmark per komponen dan soak test

Padanan `scripts/benchmark_fps.py` dan `scripts/stress_test.py` di Sentinel. Tanpa dependency baru: memori diukur tanpa `psutil`. Kedua skrip tidak menulis ke database, folder bukti, atau model. Hasil dicetak ke layar; `--out` menulis satu JSON baru dan menolak menimpa file yang sudah ada. Cadangan `perf.py` ada di `EduAI_cadangan_20261120\gk2_benchmark_soak\`.

**Cara pakai** (dari `ai/eduai-ai`):

```
python scripts/benchmark_models.py                                  # 200 frame, ritme produksi
python scripts/benchmark_models.py --frames 200 --every-frame       # detektor/CLIP di setiap frame
python scripts/soak_test.py --duration 10m --students 4             # 4 mahasiswa x 2 fps, maks 2 bersamaan
python scripts/soak_test.py --duration 5m --students 4 --hold 10s   # gambar ditahan: jalur kejadian + bukti ikut teruji
```

**Sumber frame bawaan:** enam frame demo yang sudah di-commit dan dipakai tes (`frontend/public/images/ai-signals/`). `--source` menerima folder, video, atau `synthetic`. Tidak memakai `dataset_raw`. Tiap frame diberi derau ±2 supaya tidak dianggap kamera beku.

**Isi laporan:**

- benchmark: perangkat, versi pustaka, provider ONNX Runtime, berkas model (ukuran + SHA-256 12 karakter), median/p90/maks latensi total dan per komponen, throughput nyata (1 thread), memori sebelum muat / sesudah muat / sesudah jalan;
- soak: per interval FPS per mahasiswa, p90, frame selesai/terlewat/galat, dan RSS; di akhir, pertumbuhan memori sejak interval pertama, puncak memori, kejadian per indikator, dan jumlah paket bukti (hanya di memori).

**Hasil, 20 Nov 2026.** Laptop yang sama dengan audit: Intel, 8 CPU logis, Windows 11, Python 3.14.3, mediapipe 0.10.35, onnxruntime 1.32.0 (CPU), config `0.2-provisional`. Berkas JSON mentah ada di scratchpad sesi (tidak di repositori).

*Benchmark, 1 mahasiswa, 1 thread:*

| | Ritme produksi (jam 5 fps), 300 frame | Detektor/CLIP tiap frame, 200 frame |
|---|---|---|
| Throughput | 24,6 frame/dtk | 11,1 frame/dtk |
| Total median / p90 / maks (ms) | 16,2 / 83,2 / 104,1 | 82,6 / 95,0 / 158,1 |
| prepare | 0,3 / 0,4 | 0,3 / 0,4 |
| quality | 2,7 / 4,0 | 2,8 / 4,3 |
| face | 1,8 / 2,7 | 1,8 / 2,9 |
| landmarks | 8,3 / 11,0 (n = 250) | 8,4 / 11,1 (n = 167) |
| objects | 28,0 / 29,5 (n = 100) | 28,5 / 31,1 (n = 200) |
| clip | 38,5 / 41,6 (n = 100) | 39,6 / 46,6 (n = 200) |
| Memori sebelum / sesudah muat / puncak | 52 / 303 / 328 MB | 53 / 303 / 328 MB |

*Soak test, 4 mahasiswa × 2 fps, maks 2 analisis bersamaan:*

| | 10 menit, gambar berganti tiap frame | 5 menit, tiap gambar ditahan 10 dtk |
|---|---|---|
| Frame dianalisis / terlewat / galat | 4.804 / 0 / 0 | 2.404 / 0 / 0 |
| FPS per mahasiswa (semua interval) | 2,0–2,0 | 2,0–2,0 |
| Latensi total interval terakhir, median / p90 / maks | 93,2 / 119,1 / 199,2 ms | 103,7 / 118,8 / 185,2 ms |
| p90 per interval | 108–173 ms | 119–144 ms |
| RSS setelah interval 1 → akhir | 414 → 383 MB (−31) | 410 → 403 MB (−6) |
| Puncak memori (saat memuat 4 set model) | 572 MB | 574 MB |
| Kejadian | **0**: jalur kejadian/bukti **tidak** teruji | 76 dibuka dan 76 ditutup (BOOK_VISIBLE 20, FACE_ABSENT 20, MULTIPLE_PERSONS 20, HEAD_TURN 16); 76 paket bukti |

**Cara membaca:**

- Pada beban ini (8 frame/dtk total), CPU masih punya cadangan: tidak ada frame yang terlewat, dan p90 < 0,2 dtk jauh di bawah jeda 0,5 dtk antar frame. Latensi per frame naik dari ±16 ms (1 mahasiswa) ke ±93–104 ms (4 mahasiswa, 2 bersamaan) karena berebut CPU.
- **Tidak ada tanda kebocoran memori** dalam 10 menit. RSS di Windows adalah *working set*, yang bisa menyusut, jadi pertumbuhan negatif berarti stabil, bukan "memori berkurang".
- Untuk membuktikan tidak ada kebocoran pada durasi ujian penuh (90–120 menit), perlu soak yang lebih lama.
- **Soak pertama tidak menguji jalur kejadian.** Gambar demo berganti tiap 0,5 dtk, jadi tidak ada kondisi yang bertahan. Karena itu ditambahkan opsi `--hold`.
- Pada soak kedua, setiap kejadian yang dibuka juga ditutup, dan setiap indikasi menghasilkan satu paket bukti.
- **Pengamatan, bukan ukuran akurasi:** gambar demo `1_phone_in_view.png` ditahan 10 dtk tetapi **tidak** memicu `PHONE_VISIBLE` (skor COCO `cell phone` tidak mencapai 0,5 selama 1,5 dtk). Ini sejalan dengan recall ponsel yang rendah pada pengukuran precision/recall sebelumnya, tetapi hanya satu gambar. Kalibrasi tetap harus memakai data validasi per peserta.
- Detektor objek dan CLIP berjalan pada 100 dari 300 frame di ritme produksi. Ini menegaskan temuan G-K1: pada 5 fps keduanya efektif berjalan tiap 0,6 dtk.

**Batasan:**

- Satu perangkat; frame demo yang berulang, bukan video ujian nyata.
- Tanpa jaringan, decode JPEG dari browser, atau penulisan bukti ke disk/SQLite. Ketiganya tercakup oleh `/api/ai/performance` (G-K1) saat backend berjalan.
- Ulangi di server target dengan video pilot yang sudah disetujui sebelum menentukan kapasitas (jumlah mahasiswa per server).

**File:**

| File | Perubahan |
|---|---|
| `ai/eduai-ai/src/eduai_ai/perf.py` | `rss_mb()` (Windows via ctypes, Linux `/proc`, macOS puncak saja); `PerfStats.totals_ms()` |
| `ai/eduai-ai/scripts/bench_common.py` | **Baru**: sumber frame, `FrameFeeder` (derau, `repeat`), lingkungan, inventaris model, `write_json` tanpa menimpa |
| `ai/eduai-ai/scripts/benchmark_models.py` | **Baru** |
| `ai/eduai-ai/scripts/soak_test.py` | **Baru** (exit 1 bila ada galat) |
| `ai/eduai-ai/tests/test_bench_scripts.py` | **Baru**, 8 tes: `rss_mb`, sumber frame, tidak menimpa, parser durasi, benchmark singkat, soak singkat, soak dengan `--hold` memicu indikasi (model asli) |
| `docs/MODELS.md` | Baris perintah benchmark/soak |

**Regresi:**

| Paket | Hasil |
|---|---|
| Modul AI | 96 lulus, 0 gagal, 2 dilewati |
| Backend | 247 lulus, 0 gagal, 2 dilewati |
| Data produksi | Hash `backend/data` identik dengan sebelum Tahap 0 |

---

## G-E1: perbaikan alat evaluasi

Acuan: `docs/EVALUATION_PROTOCOL.md` bagian 3–5 dan tabel celah di bagian 7, yang sekarang diberi pembaruan status. Semua alat offline: tanpa dependency baru (tanpa `scipy`), tidak menyentuh backend, database, atau model, dan tidak pernah menimpa berkas hasil. Cadangan `evaluate.py`, `test_core.py`, dan `EVALUATION_PROTOCOL.md` ada di `EduAI_cadangan_20261120\ge1_evaluasi\`.

| Skrip | Isi |
|---|---|
| `eval_stats.py` (baru) | Wilson; Poisson eksak (Garwood) lewat bisection CDF; kuartil; Cohen's kappa; AP; ROC-AUC (Mann–Whitney, ties = ½). Nilai tak terdefinisi = `None`. |
| `evaluate.py` (diperbaiki) | Pencocokan **maksimum** (augmenting path), bukan *greedy*. Toleransi awal ±2 dtk (`--tolerance-s`, bawaan sesuai protokol). Tanda ganda dihitung FP dan dilaporkan terpisah. Interval Wilson (P, R) dan Garwood (FP/jam). Jam paparan per indikasi (`--exposure`). Waktu sampai tanda (median/IQR). `CANNOT_ANALYZE` hanya dengan `--include-cannot-analyze`. `--meta` + `--split` + `--group-by` (pemisahan per peserta; kebocoran = berhenti). Hash label, versi config, dan opsional `--config` SHA-256. Kasus kosong tidak error. `--out` / `--json` tidak menimpa. Fungsi `evaluate()` lama tetap kompatibel. |
| `label_agreement.py` (baru) | Kappa per indikasi pada segmen 1 dtk (titik tengah segmen); kasus adjudikator (batas > 1 dtk, hanya A, hanya B); label otomatis (rata-rata batas bila ≤ 1 dtk). |
| `eval_detector.py` (baru) | `score`: menilai gambar berlabel dengan model EduAI (hanya membaca gambar). `eval`: AP, ROC-AUC, confusion matrix, P/R + Wilson pada ambang tetap (mis. nilai produksi) dan pada ambang yang **dipilih hanya di split kalibrasi** untuk target precision, lalu diterapkan ke split uji; titik kurva PR/ROC ke CSV; cek kebocoran peserta. |

**Perubahan perilaku `evaluate.py` yang perlu diketahui:**

- Toleransi awal 2 dtk sekarang aktif secara bawaan. Pakai `--tolerance-s 0` untuk perilaku lama.
- Precision tanpa prediksi kini kosong, bukan 0,0.
- Label `CANNOT_ANALYZE` tidak lagi dinilai diam-diam.
- `eval_results.csv` yang sudah ada tidak ditimpa.

**Uji** (`tests/test_evaluation_tools.py`, 26 tes, data buatan dengan jawaban diketahui):

- Wilson 8/10 = 0,4902–0,9433; 0/10; 10/10; 1/1 = 0,2065–1.
- Garwood k = 0/1/5/10 cocok dengan tabel baku.
- Kappa hitungan tangan 0,870.
- AP dan AUC contoh kecil.
- Kasus yang membuat cara *greedy* lama gagal.
- Tanda ganda, toleransi, kasus kosong, kebocoran peserta, versi config campuran, dan ambang yang tidak pernah dipilih di data uji.
- Satu tes memakai model asli pada dua frame demo.
- Tes lama `test_core.test_event_level_matching` tetap lulus tanpa diubah.

**Temuan data:** `ai/eduai-ai/labels.csv` berisi sisa teks perintah PowerShell di kolom `notes` baris terakhir (`pegang HPGet-Content labels.csv`). Berkas ini tidak diubah. Isinya tetap terbaca benar karena kolom yang dipakai (video, indicator, start_s, end_s) utuh.

**Belum tercakup:**

- Penyusunan `exposure.csv` dari log sesi (baseline, persetujuan audio, periode `CANNOT_ANALYZE`).
- Data pilot berlabel per peserta. Tanpa data itu, alat ini belum menghasilkan angka akurasi apa pun.

---

## G-R1: tabel ringkasan per indikasi di PDF

Cadangan `report.py`, `report_export.py`, dan `api.py` ada di `EduAI_cadangan_20261120\gr1_tabel_pdf\`. Skema, model, dan frontend tidak diubah.

**Satu sumber angka:** `report.by_indicator(rows)`. Hasilnya masuk ke data laporan (`by_indicator`, `confidence_note`), lalu dipakai oleh PDF dan XLSX. Isinya, per indikator kejadian berkategori indikasi:

| Kolom | Definisi |
|---|---|
| Jumlah indikasi | Episode menurut `cases.episodes_of`, aturan yang sama dengan ringkasan pengawas (kejadian bertumpuk dihitung sekali) |
| Kejadian tercatat | Baris `events` (satuan tinjauan) |
| Rata-rata confidence deteksi | Dari `events.details` (Tahap 2), dibobot jumlah frame: Σ(mean × n) / Σn, beserta puncak dan jumlah frame. Ponsel: EfficientDet-Lite0. Buku: CLIP dan COCO **terpisah**. |
| Status tinjauan | Jumlah kejadian Valid / Tidak Valid / Perlu Tinjauan Lanjut / Belum ditinjau |

**Bila confidence tidak tersedia,** sebabnya ditulis dan angka 0 tidak pernah dipakai:

- "indikasi ini tidak memakai skor model": `FACE_ABSENT`, `MULTIPLE_PERSONS`, `HEAD_TURN`, `HEAD_TURN_REPEATED`;
- "kejadian tercatat tanpa statistik frame (sebelum 20 Nov 2026)": ponsel/buku dari data lama;
- "tidak ada statistik frame untuk indikasi ini": label suara dan indikasi backend.

Bila hanya sebagian kejadian punya statistik, cakupannya ditulis ("dari 2 dari 3 kejadian").

**PDF:**

- Tabel ditempatkan di **awal halaman 3** sebagai lanjutan bagian IV, diikuti catatan kaki kecil. Catatan itu menyatakan bahwa angkanya bukan peluang pelanggaran dan bukan akurasi, dan bahwa status tinjauan dihitung per kejadian.
- Penempatan di halaman 2 sempat dicoba, tetapi membuat templat menjadi 4 halaman (dua tes lama gagal), jadi dipindahkan.
- Templat tetap **3 halaman** untuk sesi tanpa indikasi atau dengan beberapa jenis indikasi (diuji). Pada sesi dengan 8 jenis indikasi PDF menjadi 4 halaman, seperti tabel rincian kejadian yang juga memanjang mengikuti isinya.
- Tabel rincian kejadian dan bagian lain tidak berubah.
- Format angka memakai koma desimal dan tanpa tanda persen.

**XLSX:** sheet baru "Ringkasan indikasi", satu baris per sumber skor, angka tetap numerik. Sheet "Catatan" memuat catatan confidence.

**Batasan:** kejadian ganda yang bertumpuk (worker + fallback browser) menyumbang frame dua kali ke rata-rata confidence, karena frame dari dua sumber tidak bisa dipisahkan secara pasti. Jumlah indikasi tetap dihitung sekali.

**Pemeriksaan visual:** tidak ada perender PDF di `.venv` (tidak dipasang). Contoh PDF dari data buatan dibuat di scratchpad sesi (`contoh_laporan_GR1.pdf`, 3 halaman) untuk diperiksa manual.

**File:**

| File | Perubahan |
|---|---|
| `backend/app/report.py` | `by_indicator()`, `CONFIDENCE_NOTE`, helper `_details`, `_pool` |
| `backend/app/api.py` | `_report_data` menambah `by_indicator` dan `confidence_note` |
| `backend/app/report_export.py` | `confidence_text`, `review_text`, `indicator_table`, `summary_sheet`, gaya `NOTE`; tabel di halaman 3; kalimat bagian IV menyebut "tabel rincian" |
| `docs/API.md` | Isi laporan dan ekspor |
| `backend/tests/test_report_by_indicator.py` | **Baru**, 8 tes: rata-rata berbobot dan cakupan, sumber buku terpisah, alasan "tidak tersedia", episode = ringkasan, format tanpa persen, ujung-ke-ujung dari `EventEngine` lewat `/api/ai/events` ke laporan/PDF/XLSX, templat 3 halaman, sesi kosong |

**Regresi:** backend 255 lulus, 0 gagal, 2 dilewati (nilai retensi lama di proses tes). Modul AI dan frontend tidak diubah.

---

## G-F1: waktu ambil frame dari browser

Cadangan `media.ts`, `mediaSupport.ts`, `api.ts` (berisi perubahan pengguna yang belum di-commit; hanya baris `uploadFrame` yang diubah), `api.py`, `ai_service.py`, dan `perf.py` ada di `EduAI_cadangan_20261120\gf1_waktu_ambil\`.

**Keputusan desain: waktu dari browser hanya metrik.** Jam laptop dikendalikan mahasiswa: bisa salah, diubah, atau mundur. Waktu analisis, waktu kejadian, dan urutan frame **tetap memakai jam server**, dan tesnya membuktikan jam laptop yang mundur 10 jam tidak menggeser waktu analisis. Perilaku analisis tidak berubah.

**Browser** (`FrameUploader.tick`) mengirim field berikut bersama JPEG. Semuanya dibentuk oleh fungsi murni `frameTimingFields` di `mediaSupport.ts`, dan nilai yang tidak masuk akal tidak dikirim (tidak pernah dikirim sebagai 0).

| Field | Arti |
|---|---|
| `captured_at` | `Date.now()` tepat sebelum frame digambar dari kamera |
| `client_age_ms` | Ambil → mulai kirim (gambar + encode JPEG), diukur dengan `performance.now()`, sehingga tidak terpengaruh jam laptop yang salah |
| `prev_rtt_ms` | Bolak-balik unggahan sebelumnya yang berhasil (kirim + analisis + jawaban) |

**Backend:**

- `frame_timing()` memvalidasi ketiga field sebagai input tidak tepercaya. Selisih jam lebih dari 1 hari, NaN, negatif, atau terlalu besar → diabaikan. Frame **tidak pernah ditolak**, jadi browser lama tetap berjalan.
- Nilai dicatat di `PerfStats` per mahasiswa (termasuk frame yang dibuang "busy").
- `/api/ai/performance` per mahasiswa memuat:
  - `extra_ms.capture_to_receive`, `extra_ms.client_encode`, `extra_ms.client_rtt`;
  - `capture_lag_ms` = {`raw`, `above_min`, `min_raw`}. `raw` masih berisi selisih jam laptop–server yang konstan. `above_min` mengurangkan lag terkecil dalam jendela, sehingga yang tersisa variasi encode/jaringan/antre, dengan asumsi jam laptop tidak melompat.

**Belum tercakup:**

- Jalur worker OpenVidu: waktu frame LiveKit tidak dikirim ke backend.
- Tampilan di UI admin.

**File:**

| File | Perubahan |
|---|---|
| `frontend/src/mediaSupport.ts` | `frameTimingFields()` |
| `frontend/src/media.ts` | `FrameUploader`: catat waktu ambil, kirim field, simpan RTT |
| `frontend/src/api.ts` | `uploadFrame(..., timing)` (parameter opsional; baris lain tidak disentuh) |
| `backend/app/ai_service.py` | `frame_timing()`, `capture_lag()`, `submit_jpeg(..., timing)`, `capture_lag_ms` di `performance()` |
| `backend/app/api.py` | `upload_frame` menerima tiga field form opsional, mencatat waktu terima |
| `ai/eduai-ai/src/eduai_ai/perf.py` | `PerfStats.extra_values()` |
| `docs/API.md` | Field form baru |
| `frontend/tests/frameMeta.test.ts` | **Baru**, 3 tes |
| `backend/tests/test_frame_capture_time.py` | **Baru**, 4 tes: validasi, `above_min` menghapus selisih jam, field sampai ke `/api/ai/performance` dan frame tanpa/dengan field rusak tetap diterima, jam laptop salah tidak menggeser waktu analisis |

**Regresi:**

| Paket | Hasil |
|---|---|
| Backend | 259 lulus, 0 gagal, 2 dilewati |
| Modul AI | 122 lulus |
| Frontend `npm test` | 119 lulus |
| `tsc --noEmit` (strict, `src`) | lulus |
| `npm run lint` | 1 error lama di `SnapshotVideo.tsx` (berkas pengguna, tidak disentuh) |
| Data produksi | Hash identik |

---

## G-P1: urutan prioritas tinjauan

**Keputusan pengguna** (20 Nov 2026):

- faktor **netral**, tanpa bobot per jenis perilaku;
- tampilan **urutan + alasan**, tanpa label tingkat;
- urutan prioritas sebagai **bawaan**, dengan pilihan kembali ke "Terbaru".

Cadangan `cases.py`, `api.py`, `api.ts`, `indikasi.ts`, `App.tsx`, dan `indikasi.test.ts` ada di `EduAI_cadangan_20261120\gp1_prioritas\`. `App.tsx` dan `api.ts` berisi perubahan pengguna yang belum di-commit; hanya baris yang disebut di bawah yang diubah.

**Urutan** (`cases.priority_key`, makin atas makin dulu):

1. ada kejadian belum ditinjau;
2. aturan ringkasan (`summary_rules`) terpenuhi;
3. masih berlangsung;
4. jumlah indikasi (episode);
5. total durasi episode;
6. aktivitas terbaru.

Jenis perilaku **tidak** memengaruhi urutan (ada tesnya). Tidak ada skor model, label "tinggi/sedang/rendah", atau peluang.

**Alasan per kasus** (`priority_reasons`, berupa fakta): "belum ditinjau" atau "N kejadian baru belum ditinjau" atau "sudah ditinjau"; "aturan ringkasan terpenuhi"; "masih berlangsung"; "N kali"; "total X mnt Y dtk".

**API:** `GET /api/cases` dan `GET /api/exams/{id}/cases` menerima `sort=priority|latest` (bawaan `priority`; nilai lain 422). Setiap kasus memuat `priority_rank` dan `priority_reasons`; respons memuat `sort` dan `priority_order`.

**Frontend (halaman Indikasi):**

- tombol "Prioritas tinjauan / Terbaru" di samping judul "Daftar kasus";
- kalimat penjelas: "Urutan tinjauan, bukan tingkat pelanggaran: …";
- alasan tampil di kolom Status saat urutan prioritas dipilih;
- kasus pertama (yang terpilih otomatis) adalah kasus prioritas teratas.

Drawer mahasiswa tetap "terbaru dulu". Penarik notifikasi memakai `sort: "latest"`, karena toast-nya menampilkan kasus baru yang paling akhir. Perilakunya tidak berubah.

**Batas pemeriksaan:** tampilan tidak dicoba di browser. Menjalankan aplikasi berarti menyalakan backend terhadap database produksi, dan saat start backend menulis ke database. Logikanya diuji lewat tes unit dan API.

**File:**

| File | Perubahan |
|---|---|
| `backend/app/cases.py` | `PRIORITY_ORDER`, `priority_key`, `priority_reasons`, `rank_and_sort` |
| `backend/app/api.py` | `_case_list(..., sort)`, parameter `sort` di dua endpoint kasus (`CASE_SORT`) |
| `frontend/src/indikasi.ts` | `SortKey`, `SORTS`, `sortCases`, `priorityText` |
| `frontend/src/api.ts` | `CaseSummary.priority_rank/priority_reasons`; `api.cases({ sort })` |
| `frontend/src/App.tsx` | Impor; state `sortKey`; `visible` diurutkan; tombol urutan dan kalimat penjelas; alasan di kolom Status; penarik notifikasi `sort: "latest"` |
| `docs/API.md` | Parameter dan field baru |
| `backend/tests/test_case_priority.py` | **Baru**, 5 tes: urutan sesuai faktor, jenis perilaku tidak berpengaruh, alasan berupa fakta tanpa kata tingkat, API bawaan prioritas dan `latest` sama dengan urutan lama, kasus yang sudah ditinjau turun |
| `frontend/tests/indikasi.test.ts` | +2 tes: `sortCases`, `priorityText` |

**Regresi:**

| Paket | Hasil |
|---|---|
| Backend | 264 lulus, 0 gagal, 2 dilewati; tidak ada tes lama yang bergantung pada urutan terbaru |
| Frontend `npm test` | 121 lulus |
| `tsc` | lulus |
| Lint | 1 error lama di `SnapshotVideo.tsx` |

---

## Isolasi tes backend dari `.env` lokal

**Masalah** (Tahap 0): `backend/app/main.py:121` membuat `app = create_app()` saat modul diimpor. `load_settings()` lalu menyalin setiap `KEY=VALUE` dari `backend/.env` ke `os.environ` proses tes (lewat `setdefault`). Akibatnya hasil tes bergantung pada mesin pengembang. Dengan retensi uji coba 876000 jam, lima tes retensi gagal.

**Perbaikan, hanya di sisi tes** (kode produksi tidak diubah). File baru `backend/tests/conftest.py`:

1. mencatat nama variabel lingkungan;
2. mengimpor `app.main` sekali sebelum modul tes mana pun;
3. menghapus setiap variabel yang **ditambahkan** oleh impor itu.

Karena `setdefault` tidak pernah menimpa, variabel yang memang sudah ada di lingkungan nyata tetap utuh. Nilai dari `.env` tidak disimpan dan tidak dicetak; yang dicatat hanya nama variabel.

**Tes penjaga** `backend/tests/test_env_isolation.py` (3 tes):

- tidak ada variabel `.env` yang tersisa;
- `make_settings()` menghasilkan nilai bawaan (24 / 7 / 24 jam, tanpa kunci enkripsi, database di folder sementara) apa pun isi `.env` lokal;
- yang dihapus hanya nama yang ada di `.env`. Tes ini membaca nama kunci saja, bukan nilainya.

**Bukti:**

- seluruh suite backend **267 lulus, 0 gagal** tanpa nilai retensi tambahan di proses, padahal `backend/.env` berisi nilai uji coba 876000;
- dengan `--noconftest`, `test_hold_ends_seven_days_after_session_end` gagal lagi seperti sebelumnya; dengan `conftest.py`, tes itu lulus.

**Catatan:** `pytest` dari folder `backend` memuat `tests/conftest.py` secara otomatis, juga saat menjalankan satu berkas tes saja.

---

## Teks persetujuan mahasiswa

Cadangan `consent.ts`, `App.tsx` dan `api.ts` (keduanya berisi perubahan pengguna yang belum di-commit; hanya baris di bawah yang diubah), serta `consent.test.ts`, ada di `EduAI_cadangan_20261120\persetujuan\`.

**Masalah yang diperbaiki:**

| Bagian | Sebelum | Sesudah |
|---|---|---|
| Akses dan masa penyimpanan | Tertulis tetap "24 jam … 7 hari … 24 jam". Tidak benar selama retensi uji coba, dan harus diubah tangan setiap kali `.env` diubah. | `evidenceNotice(policy)` menyusun kalimat dari nilai yang berlaku (`GET /api/ai/health`, publik). Nilai bawaan → kalimat **persis sama** dengan redaksi Oktober 2026 (diuji). ≥ 1 tahun → "tanpa penghapusan otomatis (sesuai pengaturan sistem saat ini)". Tidak dapat dimuat → dikatakan demikian, tanpa menebak. |
| Analisis AI | "…objek menyerupai ponsel" | "…objek menyerupai ponsel **atau buku**" (deteksi buku aktif sejak Nov 2026) |
| Pilihan suara | "…bicara, bisikan, atau musik/TV … hanya **tiga** angka skor … Jika terdengar suara bicara saat mulut tampak diam…" | "…bicara, bisikan, musik/TV, atau **suara kertas/halaman buku** … hanya **empat** angka skor … Jika terdengar suara bicara saat mulut tampak diam, bisikan, atau suara kertas/halaman buku…". Ini sesuai `audio.ts` (mengirim `paper`) dan `config.yaml` (`WHISPER` dan `BOOK_SOUND` berkategori indikasi). |
| Versi yang disimpan | Selalu `2026-10-v2` | `2026-11-v3;r<jam>;h<hari>;f<jam>`, yaitu teks dan masa simpan yang benar-benar ditampilkan (≤ 40 karakter, batas skema `ConsentIn`) |

Tombol setuju menunggu masa simpan selesai dimuat, sama seperti pemberitahuan Jitsi. Bila gagal dimuat, mahasiswa tetap bisa melanjutkan, dengan kalimat "tidak dapat dimuat" dan versi `…;masa-simpan-tidak-dimuat` yang tercatat.

**Status:** redaksi baru **perlu disetujui program studi** sebelum dipakai di ujian sungguhan (README bagian "Teks persetujuan mahasiswa", sudah diperbarui). Catatan README "Belum sesuai kode: … video langsung" tidak tercakup di sini.

**File:**

| File | Perubahan |
|---|---|
| `frontend/src/consent.ts` | `RetentionPolicy`, `CONSENT_VERSION`, `DEFAULT_POLICY`, `evidenceNotice()`, `noticeVersion()`, `AI_ANALYSIS_NOTICE`, `AUDIO_NOTICE`; `EVIDENCE_NOTICE` = teks bawaan |
| `frontend/src/App.tsx` | Halaman Persetujuan: impor, ambil `api.aiHealth()`, teks dari `consent.ts`, kirim `noticeVersion`, tombol menunggu masa simpan |
| `frontend/src/api.ts` | `consent(examId, audio, noticeVersion)` (parameter opsional) |
| `README.md` | Bagian teks persetujuan diperbarui |
| `frontend/tests/consent.test.ts` | +6 tes: bawaan = redaksi Okt 2026, periode lain, pengaturan uji coba tanpa "24 jam", tidak diketahui, versi ≤ 40 karakter, teks AI/suara lengkap |
| `backend/tests/test_consent_notice.py` | **Baru**, 2 tes: versi terpanjang tersimpan apa adanya; `/ai/health` publik memberi ketiga nilai |

**Regresi:**

| Paket | Hasil |
|---|---|
| Frontend `npm test` | 127 lulus |
| `tsc` | lulus |
| Lint | 1 error lama di `SnapshotVideo.tsx` |
| Backend | 269 lulus, 0 gagal (tanpa nilai tambahan di proses tes) |
| Data produksi | Hash identik |

Tampilan halaman tidak dicoba di browser, dengan alasan yang sama seperti G-P1.

---

## Label "kejadian" dan "indikasi" di frontend

**Istilah yang dipakai di seluruh aplikasi** (sama dengan backend dan PDF, lihat Tahap 1):

- **kejadian** = satu catatan sistem (baris `events`), satuan yang ditinjau pengawas: `event_count`, `indications.total`, dan semua hitungan status tinjauan;
- **indikasi** / "N kali" / "N×" = kejadian dengan mahasiswa dan perilaku yang sama yang waktunya bertumpuk, dihitung sekali: `episode_count`, `occurrences`, `indications.episodes`;
- **deteksi** (KPI dan grafik "Deteksi hari ini") tetap dipakai untuk aliran catatan AI. Istilah ini bermakna kejadian, sehingga tidak bertentangan dan tidak diubah.

**Yang diperbaiki: hanya label yang bertentangan dengan angkanya.** Cadangan file ada di `EduAI_cadangan_20261120\label_kejadian\`; `App.tsx` dan `api.ts` hanya diubah pada baris yang disebut di bawah.

| Tempat | Sebelum | Sesudah |
|---|---|---|
| Laporan sesi, kotak ringkasan | "Total Indikasi" = `total` (kejadian); "Sudah/Belum ditinjau" | Kotak baru "Indikasi" = `episodes` (sama dengan PDF), "Kejadian tercatat", "Kejadian ditinjau", "Kejadian belum ditinjau" |
| Laporan sesi, peringatan dan pesan finalisasi (frontend dan backend `finalize_report`) | "N indikasi belum ditinjau" | "N kejadian belum ditinjau" |
| Riwayat laporan: kolom tabel, donat, ringkasan, bar hasil | Satuan "indikasi" | "kejadian" (angkanya memang per kejadian; Valid/Tidak Valid dihitung per kejadian) |
| Grafik linimasa (setiap titik = satu kejadian): teks alternatif, *hover*, legenda, "di luar jadwal", sub judul | "N indikasi" | "N kejadian" |
| Daftar kasus (halaman Indikasi): kolom ke-2 dan ke-3 | "Indikasi" (jenis) dan "Kejadian" berisi `episode_count` | "Jenis indikasi" dan "Jumlah indikasi" |
| Panel detail kasus | Hanya "Jumlah kejadian" | Ditambah "Jumlah indikasi: N kali" |
| Badge status kasus | "2 baru belum ditinjau" | "2 kejadian baru belum ditinjau" |
| Halaman Indikasi | — | Satu kalimat penjelas istilah di bawah judul "Daftar kasus" |
| `chartData.reportResults` pesan selisih | "total indikasi dari API" | "total kejadian dari API" |

Label yang memang menghitung kasus atau sesi ("Kasus per jenis indikasi", "Sesi dengan indikasi", "Alur tinjauan indikasi") dan nama jenis ("jenis indikasi") tidak diubah.

**File:** `frontend/src/App.tsx`, `frontend/src/api.ts` (komentar dan `ReportSummary.episodes`), `frontend/src/charts.tsx`, `frontend/src/chartData.ts`, `backend/app/api.py` (pesan finalisasi), `frontend/tests/chartData.test.ts` (+1 tes), `backend/tests/test_report.py` (ekspektasi pesan "2 kejadian", karena angkanya memang kejadian yang belum ditinjau).

**Regresi:**

| Paket | Hasil |
|---|---|
| Frontend | 128 lulus |
| `tsc` | lulus |
| Lint | 1 error lama di `SnapshotVideo.tsx` |
| Backend | 269 lulus |
| Data produksi | Hash identik |

Tampilan tidak dicoba di browser.

---

## Panel "Performa AI" di halaman admin

**Keputusan pengguna:** panel di halaman **admin**, bukan halaman login. Data per mahasiswa tetap khusus admin, karena `/api/ai/performance` memuat id dan nama.

**Letak:** Konfigurasi Sistem → tab baru **"Performa AI"**. Halaman Konfigurasi hanya untuk peran Admin (`routes.ts`). Data diambil tiap 5 detik, hanya selama tab itu terbuka.

**Isi:**

- Baris ringkasan: analisis aktif (maks. bersamaan), total FPS, frame dibuang dari frame diterima.
- Tabel per mahasiswa:
  - nama, ujian, sumber;
  - FPS;
  - latensi median / p90;
  - komponen terberat (median tertinggi: persiapan, cek kualitas, wajah, landmark, detektor objek, CLIP);
  - antre p90;
  - lag kamera → server (p90 di atas minimum, selisih jam laptop sudah dikurangkan);
  - frame dibuang;
  - status frame 60 detik terakhir.
- Keterangan singkat tiap istilah.

Tidak ada ambang "lambat/cepat" yang dikarang; panel hanya menampilkan nilai terukur. Nilai yang tidak ada ditulis "—", tidak pernah 0. Teks panel menegaskan bahwa ini angka operasional dari memori backend, **bukan akurasi**, dan bahwa analisis worker OpenVidu tidak termasuk.

**Backend:** `GET /api/ai/performance` (tetap admin saja) menambahkan `student_name` dan `exam_name`. Nama diambil dari `users`/`exams` dengan id sebagai parameter terikat.

**File:**

| File | Perubahan |
|---|---|
| `frontend/src/perfView.ts` | **Baru**: fungsi murni `msPair`, `heaviest`, `dropText`, `lagText`, `statusText`, `perfRows`, `perfSummary` |
| `frontend/src/AiPerformancePanel.tsx` | **Baru**: komponen tampilan (data lewat props) |
| `frontend/src/App.tsx` | `ConfigurationPage`: tab "Performa AI", `usePoll` 5 detik saat tab terbuka, impor panel. Hanya baris ini yang diubah. |
| `frontend/src/api.ts` | Tipe `MsSummary`, `AIPerformanceStudent`, `AIPerformance`; `api.aiPerformance()` |
| `backend/app/api.py` | `ai_performance`: nama mahasiswa dan ujian |
| `frontend/tests/perfView.test.ts` | **Baru**, 5 tes |
| `backend/tests/test_ai_performance.py` | Ekspektasi nama mahasiswa/ujian |

Cadangan ada di `EduAI_cadangan_20261120\panel_performa\`.

**Regresi:**

| Paket | Hasil |
|---|---|
| Frontend | 133 lulus |
| `tsc` | lulus |
| Lint | 1 error lama di `SnapshotVideo.tsx` |
| Backend | 269 lulus |
| Data produksi | Hash identik |

Tampilan tidak dicoba di browser; mohon dicek oleh pengguna.

## Belum dikerjakan (perlu keputusan)

1. ~~Menampilkan statistik di PDF~~ (selesai di G-R1). Tampilan di UI halaman laporan/indikasi belum; datanya sudah ada di API (`by_indicator`).
2. ~~Label frontend yang mencampur "kejadian" dan "episode"~~ (selesai, lihat bagian "Label kejadian dan indikasi").
3. ~~Tes backend agar tidak bergantung pada `.env` lokal~~ (selesai: `tests/conftest.py`).
4. ~~Teks persetujuan mahasiswa selama retensi uji coba~~ (selesai; redaksi baru tetap perlu disetujui program studi).
