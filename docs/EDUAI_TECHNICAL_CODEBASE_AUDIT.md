# Audit Teknis Kode EduAI

Tanggal: 20 November 2026 · Cabang: `istilah-prodi` · Konfigurasi AI: `ai/eduai-ai/config.yaml` versi `0.2-provisional`

Audit ini hanya membaca. Tidak ada kode, skema, model, konfigurasi `.env`, atau bukti yang diubah. Satu-satunya berkas baru adalah dokumen ini. Pengukuran waktu inferensi (bagian 4) dijalankan dengan skrip sementara di luar repositori, tanpa menulis ke proyek.

Status di tabel memakai tiga tingkat:

- **Sudah Ada** — jalurnya ditelusuri dari masukan sampai keluaran di kode.
- **Sebagian** — ada di kode, tetapi tidak lengkap untuk kebutuhan EduAI.
- **Belum Ada** — tidak ditemukan di kode; masih rekomendasi.

Tentang lima repositori referensi: **yang dibaca hanya README-nya**, bukan kode sumbernya. Klaim tentang isi repositori referensi berasal dari README, dan nama berkas sumber di repositori itu **belum dapat diverifikasi**.

---

## A. Ringkasan kondisi EduAI saat ini

1. **Pipeline AI sudah terhubung dari kamera sampai laporan PDF**, lewat tiga jalur sumber frame: browser, Jitsi, dan OpenVidu/LiveKit. Ketiganya memakai satu kelas analisis yang sama, `StudentAnalyzer` ([pipeline.py:29](../ai/eduai-ai/src/eduai_ai/pipeline.py#L29)), dan satu fungsi penyimpanan yang sama, `store.upsert_event` ([store.py:65](../backend/app/store.py#L65)).
2. **Pemrosesan temporal sudah matang.** Komponennya:
   - durasi minimum, masa rilis, dan cooldown;
   - histeresis sudut kepala;
   - baseline posisi kepala per mahasiswa;
   - penghitung tolehan berulang;
   - aturan "nilai tidak diketahui tidak boleh membuka kejadian".

   Semua ada di [temporal.py](../ai/eduai-ai/src/eduai_ai/temporal.py). Deduplikasi berlapis tiga: cooldown di AI, penggabungan episode ≤2 detik, dan pengelompokan kasus.
3. **Hanya satu model ONNX** yang dipakai: CLIP ViT-B/32 (bagian vision, terkuantisasi, 89 MB) untuk buku. Deteksi wajah, landmark, dan objek memakai MediaPipe Tasks (TFLite). Suara memakai YAMNet yang berjalan di browser mahasiswa.
4. **Belum ada eye tracking/gaze.** Yang ada hanya arah kepala (yaw/pitch).
5. **Confidence hanya tersimpan untuk sebagian indikator**, dan nilainya adalah **puncak** episode, bukan rata-rata:
   - ada untuk `PHONE_VISIBLE`, `BOOK_VISIBLE`, dan label suara;
   - `FACE_ABSENT`, `MULTIPLE_PERSONS`, `HEAD_TURN`, `HEAD_TURN_REPEATED`, dan `CANNOT_ANALYZE` disimpan dengan `score = NULL`.

   Akibatnya, "rata-rata confidence deteksi per sesi" **belum dapat dihitung** dari data yang ada.
6. **Agregasi per sesi sudah ada sebagian** (jumlah episode, durasi, skor maksimum, status tinjauan). Namun **PDF menghitung baris kejadian, sedangkan ringkasan pengawas menghitung episode**. Kedua angka bisa berbeda untuk sesi yang sama.
7. **Pemantauan FPS dan latensi minim.** Yang ada:
   - `latency_ms` frame terakhir, yang ditimpa setiap frame;
   - penghitung frame masuk dan frame dibuang, hanya di memori.

   Belum ada riwayat latensi, FPS per sesi, atau latensi per model di produksi.

---

## B. Struktur kode dan modul penting

```
frontend/src/media.ts            FrameUploader: kanvas → JPEG → POST /exams/{id}/frames
backend/app/
  api.py          upload_frame (882), ingest_events (1666), ingest_evidence (1682), review_event (1073),
                  _report_summary (1374), _report_data (1412), report_pdf (1515)
  ai_service.py   AIManager: load_models (94), submit_jpeg (236), _analyse (319), persist (325), health (208)
  store.py        upsert_event (65), save_evidence (89), upsert_status (117), purge_expired_evidence (126)
  cases.py        group_events (94), merge_episodes (131), rule_status (153), summarize (168)
  summary.py      build (104): ringkasan pre_end / final
  report.py       copy_frames (77), sync_holds (114), run_retention (146)
  report_export.py build_pdf (133), build_xlsx (208)
  db.py           tabel events, reviews, evidence, report_frames, exam_summaries, ...
  main.py         loop pemeliharaan tiap 30 dtk (MAINTENANCE_EVERY_S, baris 23) → run_retention
ai/eduai-ai/src/eduai_ai/
  perception.py   MediaPipePerception.process (150): kualitas → wajah → landmark → objek → CLIP
  book_clip.py    ClipBookClassifier (67): ONNX Runtime, CPU
  quality.py      QualityGate.check (42)
  headpose.py     yaw_pitch_from_matrix (14), angular_deviation (26)
  temporal.py     SustainedIndicator (27), Hysteresis (90), RepeatCounter (103), Baseline (135), EventEngine (210)
  events.py       Event, INDICATORS, kategori indication / cannot_analyze / info
  evidence.py     EvidenceBuffer (36), EvidenceStore (92)
  pipeline.py     StudentAnalyzer.process (46), stop (64)
  livekit_worker.py  _consume (136), _send (163)
  backend_client.py  _post (31): retry 2x, lalu menyerah
ai/eduai-ai/scripts/evaluate.py   evaluasi tingkat kejadian (P/R/F1/FP per jam)
```

Hubungan antarmodul diperiksa lewat pemanggilan fungsinya, bukan dari nama berkas:

- `api.upload_frame` → `AIManager.submit_jpeg` → `StudentAnalyzer.process` → `MediaPipePerception.process` + `EventEngine.update` + `EvidenceBuffer.push/start`.
- Hasil analisis → `AIManager.persist` → `store.upsert_event` / `save_evidence` / `upsert_status`.
- Jalur OpenVidu: `livekit_worker._consume` → `StudentAnalyzer.process` → `BackendClient` → `api.ingest_events` / `ingest_evidence` → fungsi `store` yang sama.

---

## C. Tabel kesenjangan implementasi

| Komponen | Status | File dan fungsi | Cara kerja saat ini | Kesenjangan | Rekomendasi | Prioritas |
|---|---|---|---|---|---|---|
| ONNX inference | Sudah Ada (1 model) | [book_clip.py:67-86](../ai/eduai-ai/src/eduai_ai/book_clip.py#L67-L86) | ONNX Runtime CPU, 2 thread. Input `pixel_values` [B,3,224,224] → `image_embeds` [B,512]. Softmax atas 14 prompt teks; P(buku) = jumlah 7 prompt "buku". | Hanya CPU. Latensi tidak dicatat di produksi. | Catat latensi per komponen (lihat baris FPS). Model tidak diganti. | Sedang |
| Deteksi objek | Sudah Ada | [perception.py:97-102](../ai/eduai-ai/src/eduai_ai/perception.py#L97-L102), [185-200](../ai/eduai-ai/src/eduai_ai/perception.py#L185-L200) | EfficientDet-Lite0 COCO (MediaPipe), allowlist `cell phone`/`book`/`person`, ambang = minimum kebutuhan (0,35). Jalan paling sering tiap 0,5 dtk. | Kotak deteksi (`sig.boxes`) tidak disimpan ke event atau bukti. Belum ada mAP pada data EduAI. | Simpan kotak puncak di `details` (tanpa ubah skema). Benchmark mAP@50 pada data berlabel. | Sedang |
| Wajah ada / tidak ada | Sudah Ada | [perception.py:166-169](../ai/eduai-ai/src/eduai_ai/perception.py#L166-L169), [temporal.py:385-388](../ai/eduai-ai/src/eduai_ai/temporal.py#L385-L388) | BlazeFace `min_confidence` 0,5. `FACE_ABSENT` bila 0 wajah ≥5 dtk, hanya pada frame berkualitas baik. | `score` NULL; confidence detektor tidak disimpan. | Simpan statistik per episode (lihat agregasi). | Sedang |
| Banyak wajah/orang | Sudah Ada | [temporal.py:391-397](../ai/eduai-ai/src/eduai_ai/temporal.py#L391-L397) | Wajah ≥2 **atau** orang (COCO ≥0,4) ≥2, selama ≥2 dtk. | `score` NULL. Jumlah orang hanya muncul di teks `reason`. | Simpan jumlah maksimum di `details`. | Rendah |
| Eye tracking / gaze | **Belum Ada** | — (FaceLandmarker hanya membaca `jawOpen`, [perception.py:179-181](../ai/eduai-ai/src/eduai_ai/perception.py#L179-L181)) | Tidak ada. | Blendshape `eyeLook*` dari model yang sama tersedia tetapi tidak dibaca. | Tahap eksperimen: catat `eyeLook*` sebagai sinyal mentah, **tanpa** indikator baru sampai ada data validasi. | Rendah |
| Head pose | Sudah Ada | [headpose.py:14-30](../ai/eduai-ai/src/eduai_ai/headpose.py#L14-L30), [temporal.py:400-412](../ai/eduai-ai/src/eduai_ai/temporal.py#L400-L412) | Matriks transformasi → yaw/pitch. Deviasi dari baseline median 45 dtk. Histeresis 30°/20°, ≥3 dtk. | `score` NULL (deviasi puncak tidak disimpan, hanya di `reason`). Tanda kiri/kanan belum dicek dengan kamera nyata (komentar baris 5-7). | Simpan deviasi puncak di `details`. | Sedang |
| Ponsel | Sudah Ada | [temporal.py:420-425](../ai/eduai-ai/src/eduai_ai/temporal.py#L420-L425) | COCO `cell phone` ≥0,5 selama ≥1,5 dtk. `score` = puncak. | Tidak ada rata-rata atau jumlah frame. Recall rendah di data uji sebelumnya. | Agregasi per episode. Kalibrasi ambang di data validasi, bukan data uji. | Tinggi |
| Buku | Sudah Ada | [temporal.py:293-309](../ai/eduai-ai/src/eduai_ai/temporal.py#L293-L309), [428-433](../ai/eduai-ai/src/eduai_ai/temporal.py#L428-L433) | COCO `book` ≥0,35 **atau** CLIP ≥0,6, ≥1,5 dtk. `score` = maksimum sinyal yang lolos. | `score` mencampur dua skala berbeda (skor detektor dan softmax CLIP) tanpa penanda sumbernya. | Simpan sumber (`coco`/`clip`) dan nilai masing-masing di `details`. | Tinggi |
| Ekstraksi frame dan timestamp | Sebagian | [media.ts:170-193](../frontend/src/media.ts#L170-L193), [ai_service.py:236-257](../backend/app/ai_service.py#L236-L257), [livekit_worker.py:145-153](../ai/eduai-ai/src/eduai_ai/livekit_worker.py#L145-L153) | Browser: JPEG ≤640 px, q 0,8, `EDUAI_UPLOAD_FPS`=2, satu unggahan sekaligus. Server memberi `ts = time.time()` saat frame **diterima**. Worker: `analysis_fps`=5, ts saat frame dibaca. | Waktu ambil di browser tidak dikirim. Laju frame berbeda antarjalur (2 vs 5 fps). Frame "busy" dibuang tanpa catatan per mahasiswa. | Catat jumlah frame dianalisis/dibuang per mahasiswa per sesi. Dokumentasikan perbedaan laju. | Sedang |
| Pemrosesan temporal | Sudah Ada | [temporal.py:27-87](../ai/eduai-ai/src/eduai_ai/temporal.py#L27-L87) | Kandidat → buka setelah `min_duration_s` → tutup setelah `release_s` tanpa sinyal. Nilai tidak diketahui hanya bisa menutup. | — | Pertahankan. | — |
| Episode dan cooldown | Sudah Ada | [temporal.py:60-64](../ai/eduai-ai/src/eduai_ai/temporal.py#L60-L64), [79](../ai/eduai-ai/src/eduai_ai/temporal.py#L79), [cases.py:131-150](../backend/app/cases.py#L131-L150) | Episode dalam cooldown dibuka secara internal tetapi **tidak dikirim** (`suppressed`). Backend menggabungkan kejadian yang berjarak ≤2 dtk. | Jumlah episode yang ditekan cooldown tidak tercatat, sehingga frekuensi sebenarnya tidak diketahui. | Hitung episode tertekan di memori; kirim sebagai jumlah di `details` kejadian berikutnya. | Sedang |
| Alert dan deduplikasi | Sudah Ada | [cases.py:94](../backend/app/cases.py#L94), [153-165](../backend/app/cases.py#L153-L165), [summary.py:147-170](../backend/app/summary.py#L147-L170) | Kasus = mahasiswa + indikator per ujian. Pop-up menunggu `summary_rules`. Ringkasan `INSERT OR IGNORE` agar tidak ganda. | Belum ada urutan prioritas tinjauan. | Prioritas tinjauan (bukan "ancaman") dari aturan yang terpenuhi dan durasi. | Rendah |
| SQLite events dan reviews | Sudah Ada | [db.py](../backend/app/db.py), [store.py:65-86](../backend/app/store.py#L65-L86), [api.py:1073-1093](../backend/app/api.py#L1073-L1093) | Open → insert, closed → update (`event_id` sama). Peninjauan append-only + audit. `review_status` disalin ke `events`. | Kolom `score` tunggal (puncak). Tidak ada `mean`/`n_frames`. | Pakai kolom `details` (JSON) yang sudah ada sebelum menambah kolom. Perlu persetujuan. | Tinggi |
| Penangkapan bukti | Sebagian | [pipeline.py:53-56](../ai/eduai-ai/src/eduai_ai/pipeline.py#L53-L56), [evidence.py:55-85](../ai/eduai-ai/src/eduai_ai/evidence.py#L55-L85) | Ring buffer 5 dtk + 5 dtk, ≤12 JPEG 480 px q70. Dimulai hanya saat indikasi berstatus `open`. | `HEAD_TURN_REPEATED` dibuat langsung `closed` ([temporal.py:415-417](../ai/eduai-ai/src/eduai_ai/temporal.py#L415-L417)), sehingga **tidak pernah punya bukti**. | Mulai bukti juga untuk indikasi yang langsung `closed`. | Sedang |
| Penyimpanan bukti | Sudah Ada | [evidence.py:113-188](../ai/eduai-ai/src/eduai_ai/evidence.py#L113-L188), [store.py:89-103](../backend/app/store.py#L89-L103) | Folder id acak + `meta.json`, Fernet opsional (kunci terisi di `.env`). Disajikan hanya lewat endpoint berizin. | Lihat bagian 5 (retensi). | — (P5 ditunda) | — |
| Agregasi sesi | Sebagian | [cases.py:168-202](../backend/app/cases.py#L168-L202), [summary.py:104-136](../backend/app/summary.py#L104-L136) | Per indikator: jumlah kejadian, jumlah episode, total durasi, `max_score`, jumlah bukti, status tinjauan. | Tidak ada rata-rata confidence, jumlah frame valid, atau frekuensi per jam pemantauan. `total_duration_s` menjumlahkan kejadian yang tumpang tindih. | Lihat rekomendasi G1–G3. | Tinggi |
| Laporan PDF | Sebagian | [report_export.py:133-205](../backend/app/report_export.py#L133-L205), [api.py:1374-1434](../backend/app/api.py#L1374-L1434) | Tabel IV per kejadian: nama, waktu, label, hasil tinjauan, catatan. Lampiran 1 gambar per kejadian. Tidak menampilkan skor. | Belum ada tabel per indikasi (jumlah / rata-rata confidence / status tinjauan). Satuan hitung berbeda dari ringkasan. | Tabel ringkasan per indikasi memakai satuan episode. Confidence diberi label "rata-rata confidence deteksi", bukan persentase kecurangan. | Tinggi |
| Pemantauan FPS dan inferensi | Sebagian | [pipeline.py:47](../ai/eduai-ai/src/eduai_ai/pipeline.py#L47), [store.py:117](../backend/app/store.py#L117), [ai_service.py:208-217](../backend/app/ai_service.py#L208-L217) | `latency_ms` per frame (seluruh pipeline) ditimpa di `ai_status`. `/ai/health` memberi `frames_received` dan `frames_dropped_busy` (global, di memori). | Tidak ada latensi per model, persentil, FPS efektif per mahasiswa, atau riwayat. | Akumulator latensi/FPS di memori + endpoint ringkasan, tanpa tabel baru. | Sedang |

---

## D. Alur kerja aktual sistem

```
Webcam (browser mahasiswa)
  │  media.ts FrameUploader.tick: kanvas ≤640 px → JPEG q0,8, tiap 1/EDUAI_UPLOAD_FPS (2) dtk,
  │  maks 1 unggahan sekaligus (frame lain dilewati)
  ▼
POST /exams/{id}/frames (api.py:882)
  │  cek: ujian berlangsung, persetujuan, monitoring aktif, sumber, JPEG, ≤400 kB
  ▼
AIManager.submit_jpeg (ai_service.py:236)         ┌─ Jalur OpenVidu: livekit_worker._consume (136)
  │  ts = waktu server saat frame diterima          │   VideoStream → RGB → BGR, ts = time.time(),
  │  1 frame diproses per mahasiswa ("busy")        │   sampling analysis_fps (5)
  ▼                                                 ▼
StudentAnalyzer.process (pipeline.py:46)  ◄─────────┘
  ├─ QualityGate.check: gelap / terlalu terang / buram / beku / resolusi rendah → cannot_analyze
  ├─ BlazeFace → face_count, face_width_ratio
  ├─ FaceLandmarker (bila wajah ≥6 % lebar) → yaw, pitch, jawOpen
  ├─ EfficientDet-Lite0 (≥0,5 dtk sekali) → phone_score, book_score, person_count, boxes
  └─ CLIP ONNX (≥0,5 dtk sekali) → book_clip_score
  ▼  FrameSignals
EventEngine.update (temporal.py:371)
  │  SustainedIndicator / Hysteresis / Baseline / RepeatCounter → Event(open|closed, score = puncak)
  ▼
EvidenceBuffer.start/push → EvidencePackage (≤12 JPEG) setelah jendela 5 dtk
  ▼
AIManager.persist (ai_service.py:325)  |  worker: BackendClient → /api/ai/events, /api/ai/evidence
  │  store.upsert_event → tabel events;  store.save_evidence → disk + tabel evidence + events.evidence_id
  │  store.upsert_status → ai_status (state, latency_ms)
  ▼
cases.group_events / merge_episodes / rule_status → pop-up pengawas, halaman Indikasi
summary.build → exam_summaries (pre_end / final)
reviews (append-only) → events.review_status
  ▼
_report_data (api.py:1412) → report_export.build_pdf (133) → PDF
report.run_retention (tiap 30 dtk) → hapus bukti kedaluwarsa
```

**Pemeriksaan sambungan antartahap**

| Sambungan | Hasil |
|---|---|
| Frame → analisis | Terhubung. Frame yang dibuang karena "busy" hanya dihitung secara global ([ai_service.py:248-250](../backend/app/ai_service.py#L248-L250)). |
| Hasil deteksi → event | Terhubung. Kotak deteksi (`boxes`) dan confidence detektor wajah **hilang** di tahap ini; tidak masuk ke event. |
| Event → SQLite | Terhubung. Open/closed memakai `event_id` sama. `COALESCE(score)` mempertahankan skor lama bila skor baru NULL ([store.py:74-77](../backend/app/store.py#L74-L77)). |
| Event → bukti | Terhubung untuk indikasi yang dibuka. **Tidak** untuk `HEAD_TURN_REPEATED`. |
| `session_id` ↔ `exam_id` | Jalur browser: `str(exam_id)` langsung. Jalur worker: `_ingest_ids` memetakan session_id ke exam. Konsisten. |
| `event_id` ↔ evidence | `save_evidence` menolak bukti untuk event yang tidak dikenal ([store.py:93-95](../backend/app/store.py#L93-L95)). Pada jalur in-process, event selalu disimpan lebih dulu, jadi aman. |
| SQLite → agregasi → PDF | Terhubung. Satuan hitung tidak seragam (lihat masalah E5). |

---

## E. Masalah teknis yang ditemukan

Setiap masalah di bawah sudah ditelusuri di kode. Belum ada yang diperbaiki.

| ID | Masalah | Lokasi | Dampak |
|---|---|---|---|
| E1 | `score` NULL untuk `FACE_ABSENT`, `MULTIPLE_PERSONS`, `HEAD_TURN`, `HEAD_TURN_REPEATED`, `CANNOT_ANALYZE`. `_emit` memakai `score_fn` bawaan yang mengembalikan `None`. | [temporal.py:267](../ai/eduai-ai/src/eduai_ai/temporal.py#L267), [386-417](../ai/eduai-ai/src/eduai_ai/temporal.py#L386-L417) | Kolom confidence di laporan akan kosong untuk sebagian besar indikator. |
| E2 | Skor = **puncak** episode, bukan rata-rata. Skor per frame tidak disimpan. | [temporal.py:53](../ai/eduai-ai/src/eduai_ai/temporal.py#L53) | "Rata-rata confidence deteksi" tidak dapat dihitung dari data yang ada. Data lama tidak bisa dihitung ulang. |
| E3 | Saat pemantauan berhenti (`flush`), skor event penutup NULL, sehingga database tetap memegang skor saat event **dibuka**. Puncak sesudahnya hilang. | [temporal.py:453-455](../ai/eduai-ai/src/eduai_ai/temporal.py#L453-L455), [store.py:77](../backend/app/store.py#L77) | `max_score` bisa lebih rendah dari puncak sebenarnya untuk episode yang terpotong. |
| E4 | Skor `BOOK_VISIBLE` mencampur skala detektor COCO dan softmax CLIP tanpa penanda sumber. | [temporal.py:304-309](../ai/eduai-ai/src/eduai_ai/temporal.py#L304-L309) | Rata-rata atas skor buku tidak bermakna sampai sumbernya dipisahkan. |
| E5 | PDF menghitung **baris kejadian** (`_report_summary`), sedangkan ringkasan menghitung **episode** gabungan (`summary.build`). | [api.py:1374-1382](../backend/app/api.py#L1374-L1382), [summary.py:118-121](../backend/app/summary.py#L118-L121) | Angka di PDF bisa berbeda dari ringkasan untuk sesi yang sama. Contoh pemicu: worker restart, atau frame fallback browser bersamaan dengan worker. |
| E6 | `total_duration_s` menjumlahkan durasi semua kejadian, bukan durasi episode gabungan. | [cases.py:172](../backend/app/cases.py#L172) | Durasi terhitung ganda bila kejadian tumpang tindih. |
| E7 | Durasi "tidak dapat dianalisis" di PDF melewatkan kejadian yang masih terbuka. `summary.py` memakai waktu sekarang. | [api.py:1377-1379](../backend/app/api.py#L1377-L1379), [summary.py:128](../backend/app/summary.py#L128) | Inkonsistensi kecil. |
| E8 | `HEAD_TURN_REPEATED` tidak pernah punya bukti, karena bukti hanya dimulai untuk event `open`. | [pipeline.py:54-56](../ai/eduai-ai/src/eduai_ai/pipeline.py#L54-L56), [temporal.py:415-417](../ai/eduai-ai/src/eduai_ai/temporal.py#L415-L417) | Lampiran PDF untuk indikasi ini selalu "Tidak ada gambar". |
| E9 | Episode yang tertekan cooldown tidak dikirim dan tidak dihitung. | [temporal.py:60-64](../ai/eduai-ai/src/eduai_ai/temporal.py#L60-L64), [79](../ai/eduai-ai/src/eduai_ai/temporal.py#L79) | "Jumlah alert" ≠ jumlah kemunculan perilaku. Harus dijelaskan di laporan. |
| E10 | Jalur worker: setelah 2 kali retry gagal, `_post` mengembalikan `None` tanpa antrean ulang. | [backend_client.py:31-47](../ai/eduai-ai/src/eduai_ai/backend_client.py#L31-L47) | Event `closed` bisa hilang (event tetap `open` sampai `close_open_events`). Bukti untuk event yang gagal tersimpan ditolak dengan 422. |
| E11 | `ingest_evidence` memakai `ts[0]` sebagai `event_ts`, bukan waktu kejadian sebenarnya. | [api.py:1704-1705](../backend/app/api.py#L1704-L1705) | Kecil: `key_index` tetap dari meta. Hanya `event_ts` paket yang tidak tepat. |
| E12 | Timestamp jalur browser = waktu frame **diterima** server, bukan waktu ambil. Laju 2 fps (browser) vs 5 fps (worker). `analysis_fps` hanya dipakai worker dan `run_webcam.py`. | [ai_service.py:252-253](../backend/app/ai_service.py#L252-L253), [settings.py:129](../backend/app/settings.py#L129) | Aturan temporal tetap benar karena berbasis detik. Agregasi berbasis jumlah frame tidak sebanding antarjalur. |
| E13 | Tidak ada riwayat latensi/FPS. `ai_status.latency_ms` ditimpa per frame; penghitung frame hanya global di memori. | [store.py:117-123](../backend/app/store.py#L117-L123), [ai_service.py:55](../backend/app/ai_service.py#L55) | Kinerja per sesi tidak bisa dilaporkan. |
| E14 | `evaluate.py` gagal (`rows[0]`) bila tidak ada label maupun prediksi. Pencocokan rakus; tanpa interval kepercayaan. | [evaluate.py:91](../ai/eduai-ai/scripts/evaluate.py#L91) | Sudah tercatat di `EVALUATION_PROTOCOL.md` §7. |
| E15 | `EVALUATION_PROTOCOL.md` §8 butir 6 masih menyebut "buku belum ada detektor". | [docs/EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md) | Dokumen usang. |
| E16 | Lingkungan `.venv` saat ini: Python 3.14.3, mediapipe 0.10.35, onnxruntime 1.32.0, opencv 5.0.0. README menyarankan Python 3.11/3.12; dokumen uji menyebut mediapipe 0.10.32. | `.venv`, [README.md](../README.md) | Hasil uji lama belum tentu berlaku di lingkungan ini. Perlu uji regresi ulang. |
| E17 | Kolom `evidence.expires_at` di database diisi saat bukti disimpan. Penghapusan nyata memakai retensi **saat ini** ditambah `hold_until` ([evidence.py:168-170](../ai/eduai-ai/src/eduai_ai/evidence.py#L168-L170)). | [store.py:97-101](../backend/app/store.py#L97-L101) | Tanggal kedaluwarsa yang tampil bisa berbeda dari kapan bukti benar-benar dihapus. Lihat bagian 5. |

---

## F. Perbandingan dengan lima repositori referensi

Sumber: hanya README. Kode sumber repositori referensi **belum dibaca**, dan nama berkas sumbernya **belum dapat diverifikasi**.

| Repositori (README) | Teknik di README | Di EduAI | Keputusan |
|---|---|---|---|
| khalequzzamanlikhon/sentinel-video-anomaly-detection | Aturan berbasis persistensi | Sudah Ada (`SustainedIndicator`) | — |
| ″ | Deduplikasi alert, severity | Dedup Sudah Ada. Severity Belum Ada. | Severity hanya sebagai urutan prioritas tinjauan |
| ″ | Thumbnail + klip | Thumbnail Sudah Ada. Klip tidak. | Klip **tidak diadopsi** (video penuh dilarang) |
| ″ | Multi-kamera, BoT-SORT | Tidak ada | **Tidak perlu** (satu kamera per mahasiswa) |
| ″ | Benchmark dan uji ketahanan yang jujur, metrik operasional | Sebagian (E13) | **Direkomendasikan** (G4) |
| jeeva5655/ProctorAI | COCO-SSD ponsel/buku/earphone | Ponsel/buku Sudah Ada (model lain). Earphone tidak ada. | Earphone belum dapat diverifikasi kelayakannya (bukan kelas COCO; tanpa data) |
| ″ | Gaze dari Face Mesh | Belum Ada | Eksperimen dari blendshape `eyeLook*`, tanpa indikator sebelum ada validasi (G6) |
| ″ | MediaPipe Hands | Tidak ada | Tidak sekarang |
| ″ | Emosi (face-api.js) | Tidak ada | **Tidak diadopsi** |
| ″ | Skor ancaman 5 tingkat | Tidak ada | **Tidak diadopsi** sebagai "ancaman" |
| kevalshah91/advanced-proctoring-system | YOLOv5 ponsel | Ponsel Sudah Ada (EfficientDet-Lite0) | Hanya pembanding benchmark, bukan pengganti |
| ″ | Haar cascade, log, screenshot | BlazeFace (lebih baru); log/bukti Sudah Ada | — |
| ″ | Peringatan audio | Label suara YAMNet Sudah Ada (skor saja, tanpa audio) | — |
| vardanagarwal/Proctoring-AI | Mulut terbuka, head pose | Sudah Ada (`jawOpen`, yaw/pitch) | — |
| ″ | Eye tracking | Belum Ada | Sama dengan G6 |
| ″ | Tabel FPS per perangkat | Belum Ada | **Direkomendasikan** (G4) |
| ″ | Anti-spoofing wajah | Belum Ada | Kandidat jangka panjang; butuh data |
| ″ | Speech-to-text + NLTK | Tidak ada | **Tidak diadopsi** (privasi) |
| AnasMultani17/Cheating-Detection-From-Video | CNN biner "cheating" 48×48 | Tidak ada | **Tidak diadopsi**: label "cheating" tidak cocok dengan tugas EduAI (indikasi untuk ditinjau) |
| ″ | Split per subjek, confusion matrix, ROC | Split per peserta ada di protokol. Confusion matrix/ROC belum ada di skrip. | **Direkomendasikan** untuk evaluasi tingkat model (G5) |

---

## G. Rekomendasi pengembangan berdasarkan prioritas

Tidak ada rekomendasi yang mengganti model. Tidak ada yang mengubah skema tanpa persetujuan.

**Prioritas tinggi**

- **G1. Statistik confidence per episode tanpa mengubah skema.**
  - Di `SustainedIndicator`, simpan jumlah dan total skor frame valid di samping `peak`.
  - Kirim `{"score_mean": …, "n_frames": …, "score_source": "coco|clip|…"}` di `details` (kolom JSON yang sudah ada).
  - Tujuannya mengatasi E1–E4. Untuk indikator tanpa skor detektor (wajah tidak ada, menoleh), statistiknya berbeda makna dan harus diberi nama sendiri. Contoh: rata-rata deviasi sudut, bukan "confidence".
  - Kejadian lama tetap "tidak tersedia", bukan 0.
- **G2. Satu satuan agregasi.**
  - `_report_summary` dan PDF memakai episode dari `cases.merge_episodes`, sama dengan ringkasan (E5).
  - `total_duration_s` memakai durasi episode (E6).
  - Durasi kejadian terbuka diperlakukan sama di kedua tempat (E7).
- **G3. Tabel ringkasan per indikasi di PDF**, dengan kolom:
  - indikasi;
  - jumlah episode;
  - rata-rata confidence deteksi (bila tersedia, dengan n frame);
  - status tinjauan.

  Disertai catatan bahwa confidence bukan persentase kecurangan, dan bahwa episode dalam cooldown tidak dihitung (E9).

**Prioritas sedang**

- **G4. Pemantauan kinerja.**
  - Latensi per komponen (kualitas, wajah, landmark, detektor, CLIP) diukur di `perception.process` dan dikirim lewat `FrameSignals.metrics`, yang sudah ada.
  - Akumulator median/p90 dan FPS efektif per mahasiswa disimpan di memori `AIManager`.
  - Hasilnya ditampilkan di `/ai/health`.
- **G5. Evaluasi tiga tingkat**, dilaporkan terpisah:
  - **model:** P/R/F1, mAP@50, confusion matrix, ROC per kelas, split per peserta;
  - **kejadian:** `evaluate.py` yang diperbaiki (E14);
  - **sesi:** kecocokan ringkasan dengan label sesi.
- **G7. Bukti untuk `HEAD_TURN_REPEATED`** (E8).
- **G8. Ketahanan jalur worker** (E10): antrean ulang terbatas di `BackendClient`.
- **G9. Penghitung frame per mahasiswa** (diterima, dianalisis, dibuang, tidak dapat dianalisis), untuk penyebut agregasi (E12).

**Prioritas rendah**

- **G6. Sinyal gaze eksperimental** dari blendshape `eyeLook*` yang sudah dihasilkan FaceLandmarker. Hanya dicatat, tanpa indikator.
- **G10. Simpan kotak deteksi puncak** di `details` agar pengawas tahu objek mana yang dimaksud.
- **G11. Perbarui `EVALUATION_PROTOCOL.md`** (E15).

---

## H. Daftar file yang berpotensi perlu diperbaiki atau dikembangkan

| File | Terkait |
|---|---|
| `ai/eduai-ai/src/eduai_ai/temporal.py` | G1 (statistik episode), G7, E3, E9 |
| `ai/eduai-ai/src/eduai_ai/perception.py` | G4 (latensi per komponen), G6, G10 |
| `ai/eduai-ai/src/eduai_ai/pipeline.py` | G7 (bukti untuk indikasi langsung `closed`) |
| `ai/eduai-ai/src/eduai_ai/backend_client.py` | G8 |
| `backend/app/ai_service.py` | G4, G9 |
| `backend/app/cases.py` | G2 (durasi episode) |
| `backend/app/api.py` (`_report_summary`, `_report_data`) | G2, G3 |
| `backend/app/report_export.py` | G3 |
| `backend/app/summary.py` | G2 (konsistensi durasi) |
| `ai/eduai-ai/scripts/evaluate.py` | G5, E14 |
| `docs/EVALUATION_PROTOCOL.md` | G11 |
| Tes: `backend/tests/test_report.py`, `test_summary.py`, `test_cases.py`, `ai/eduai-ai/tests/test_core.py` | Regresi untuk G1–G3 |

---

## I. Risiko apabila fitur baru langsung diimplementasikan

1. **Mengubah angka laporan.** G2 mengubah jumlah di PDF. Laporan yang sudah difinalisasi tidak boleh berubah diam-diam. Perubahan perlu diberi versi dan dicatat.
2. **Makna "confidence" disalahartikan.** Rata-rata skor detektor ponsel bukan peluang mahasiswa curang. Tanpa label dan catatan yang jelas, angka ini mudah dikutip keliru.
3. **Data lama tidak lengkap.** Kejadian sebelum G1 tidak punya statistik. Bila dirata-ratakan bersama data baru tanpa penanda, hasilnya bias.
4. **Skema.** Menambah kolom berarti migrasi `db.py`, yang sudah pernah membangun ulang tabel `events` (`events_new`). Memakai `details` lebih aman, tetapi sulit di-query dengan SQL.
5. **Beban CPU.** Pipeline penuh ±180 ms per frame di laptop ini (bagian 4). Menambah sinyal gaze atau model baru menurunkan jumlah mahasiswa per server.
6. **Lingkungan berbeda dari yang terdokumentasi (E16).** Tes harus dijalankan ulang di `.venv` saat ini sebelum perubahan apa pun, agar kegagalan lama tidak tertukar dengan kegagalan baru.
7. **Ambang belum dikalibrasi** (`0.2-provisional`). Indikator baru di atas ambang yang belum tervalidasi menambah alarm palsu.

---

## J. Roadmap pengembangan bertahap

| Tahap | Isi | Syarat selesai |
|---|---|---|
| 0 | Jalankan semua tes yang ada di `.venv` saat ini; catat hasil apa adanya | Daftar lulus/gagal sebagai garis dasar |
| 1 | G2 + E7: satu satuan agregasi (tanpa skema baru) | Tes PDF dan ringkasan menghasilkan angka yang sama untuk data sama |
| 2 | G1: statistik episode di `details`; E3 | Tes unit `SustainedIndicator`; kejadian lama tampil "tidak tersedia" |
| 3 | G3: tabel ringkasan per indikasi di PDF | Tes PDF; teks catatan confidence ada |
| 4 | G4 + G9: latensi per komponen, FPS, penghitung frame | Angka muncul di `/ai/health`; overhead diukur |
| 5 | G7, G8, G10, G11 | Tes regresi masing-masing |
| 6 | G5: evaluasi tiga tingkat pada data berlabel per peserta | Laporan dengan n, interval kepercayaan, versi konfigurasi |
| 7 | G6 (gaze eksperimental), hanya bila ada data validasi | Keputusan terpisah |

Setiap tahap baru dikerjakan setelah disetujui. Perubahan skema dijelaskan terlebih dahulu.

---

## Lampiran 4. Pemeriksaan model

| Model | Berkas (ukuran) | Arsitektur | Masukan / keluaran | Prapemrosesan | Label / ambang | Pascapemrosesan |
|---|---|---|---|---|---|---|
| CLIP vision (ONNX) | `clip_vit_b32_vision_quantized.onnx` (89,1 MB) | ViT-B/32, kuantisasi (`producer: onnx.quantize`) | `pixel_values` float [batch, 3, H, W] → `image_embeds` float [batch, 512] | Letterbox 224×224, isi warna rata-rata CLIP, normalisasi mean/std CLIP ([book_clip.py:23-34](../ai/eduai-ai/src/eduai_ai/book_clip.py#L23-L34)) | 14 prompt teks (`clip_book_prompts.npz`), 7 berarti "buku". Ambang 0,6 | Softmax skala 100; P(buku) = jumlah share prompt buku |
| BlazeFace | `blaze_face_short_range.tflite` (0,23 MB) | BlazeFace short-range | Diurus MediaPipe Tasks (tensor internal **belum diverifikasi** dari berkas) | RGB, lebar kerja 640 | `min_confidence` 0,5 | Jumlah deteksi, lebar kotak terbesar |
| FaceLandmarker | `face_landmarker.task` (3,8 MB) | Bundel MediaPipe (detektor + landmark + blendshape) | Diurus MediaPipe | Dilewati bila wajah <6 % lebar frame | `num_faces` 1 | Matriks transformasi → yaw/pitch; blendshape `jawOpen` |
| EfficientDet-Lite0 | `efficientdet_lite0.tflite` (4,6 MB) | EfficientDet-Lite0 COCO | Diurus MediaPipe | — | Allowlist `cell phone`, `book`, `person`; ambang detektor 0,35; ponsel 0,5; orang 0,4 | Skor maksimum per kelas; jumlah orang ≥0,4 |
| YAMNet | `yamnet.tflite` (4,1 MB) | YAMNet (AudioSet) | Berjalan di **browser** (`@mediapipe/tasks-audio`); backend hanya menerima skor | — | speech 0,30; whisper 0,20; media 0,30; paper 0,25 | Lihat `_sound_signals` ([temporal.py:311](../ai/eduai-ai/src/eduai_ai/temporal.py#L311)) |

**CPU/GPU.** ONNX Runtime yang terpasang hanya punya `CPUExecutionProvider` (dan `AzureExecutionProvider`, tidak dipakai). CLIP dipaksa ke CPU ([book_clip.py:78](../ai/eduai-ai/src/eduai_ai/book_clip.py#L78)). MediaPipe memakai delegasi XNNPACK di CPU (pesan log saat dimuat). Tidak ada GPU yang dipakai.

**Waktu inferensi (diukur 20 November 2026).**

Kondisi pengukuran:

- laptop ini: Intel, 8 CPU logis;
- `.venv` proyek;
- frame acak 640×480 **tanpa wajah**;
- 30 pengulangan setelah 3 pemanasan (pipeline: 20).

| Komponen | Median | p90 |
|---|---|---|
| BlazeFace | 3,3 ms | 3,6 ms |
| FaceLandmarker | 3,6 ms | 3,9 ms |
| EfficientDet-Lite0 | 69,7 ms | 76,1 ms |
| CLIP `score()` (2 thread) | 100,7 ms | 112,5 ms |
| `perception.process` lengkap (kualitas + wajah + detektor + CLIP) | 178,5 ms | 191,9 ms |

Keterbatasan angka ini:

- Frame acak tanpa wajah, jadi angka FaceLandmarker **tidak mewakili** kasus wajah ada.
- Satu perangkat, satu proses, tanpa beban mahasiswa lain.
- Memori tidak diukur, karena `psutil` tidak terpasang dan tidak dipasang sesuai aturan audit.
- Waktu muat: BlazeFace 383 ms, landmarker 66 ms, detektor 44 ms.

---

## Lampiran 5. Analisis retensi bukti (tanpa perubahan)

Keputusan sementara pengguna: penghapusan setelah 1 hari **ditunda** selama uji coba. `.env` dan mekanisme retensi tidak diubah. P5 tidak diperbaiki.

**Konfigurasi aktif di `backend/.env`.** Hanya `EDUAI_EVIDENCE_RETENTION_HOURS=24`, `EDUAI_EVIDENCE_DIR=data/evidence`, dan kunci enkripsi (terisi) yang diatur. Dua nilai lain memakai bawaan [settings.py](../backend/app/settings.py):

- `EDUAI_EVIDENCE_HOLD_DAYS` = 7 (baris 122);
- `EDUAI_REPORT_FRAME_RETENTION_HOURS` = 24 (baris 121).

**Cara kerja `run_retention`.** Fungsi ini ada di [report.py:146-150](../backend/app/report.py#L146-L150) dan dijalankan saat backend mulai dan setiap 30 detik ([main.py:23](../backend/app/main.py#L23), baris 51 dan 93). Urutannya:

1. `sync_holds` ([report.py:114-123](../backend/app/report.py#L114-L123)):
   - Untuk sesi yang **belum final**, `hold_until` = akhir sesi + 7 hari.
   - Untuk sesi yang **sudah final**, hold dihapus.
2. `purge_expired_evidence` ([store.py:126-137](../backend/app/store.py#L126-L137)) → `EvidenceStore.purge_expired` ([evidence.py:175-188](../ai/eduai-ai/src/eduai_ai/evidence.py#L175-L188)). Paket dihapus bila `max(created_at + retensi_saat_ini, hold_until) < sekarang` ([evidence.py:168-170](../ai/eduai-ai/src/eduai_ai/evidence.py#L168-L170)). Baris `evidence` dihapus, `events.evidence_id` dikosongkan, `evidence_deleted_at` diisi, dan tindakan dicatat di audit.
3. `purge_report_frames`: salinan gambar laporan dihapus 24 jam setelah finalisasi.

**Akibatnya pada kondisi sekarang:**

- Bukti sesi yang **belum difinalisasi** bertahan paling lama 7 hari setelah sesi berakhir, lalu dihapus otomatis.
- Bila laporan sesi yang sudah lebih dari 24 jam **difinalisasi**, hold dicabut dan bukti aslinya terhapus pada siklus pemeliharaan berikutnya (≤30 detik). Yang tersisa hanya salinan satu gambar per kejadian, yang juga dihapus 24 jam kemudian.
- Saat audit ini, ada **148 paket bukti** di `backend/data/evidence` dan 0 salinan laporan. Paket ini akan terhapus mengikuti aturan di atas selama backend berjalan.
- Koreksi atas penjelasan sebelumnya di percakapan: karena `_expired` memakai retensi **saat ini**, menaikkan `EDUAI_EVIDENCE_RETENTION_HOURS` juga memperpanjang umur paket lama yang belum terhapus. Kolom `evidence.expires_at` di database tidak ikut berubah (E17).

**Catatan untuk keputusan berikutnya** (tidak dikerjakan dalam audit ini): agar bukti tidak terhapus selama uji coba, nilai retensi dan hold di `.env` perlu dinaikkan. Itu memerlukan persetujuan eksplisit.
