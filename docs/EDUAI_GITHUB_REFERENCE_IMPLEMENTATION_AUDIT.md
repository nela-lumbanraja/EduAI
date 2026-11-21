# Audit Kesesuaian EduAI terhadap Lima Repositori GitHub Referensi

Tanggal: 20 November 2026 · Cabang EduAI: `istilah-prodi` (termasuk perubahan Tahap 1–2 yang belum di-commit)

Audit ini **hanya membaca**. Tidak ada kode, `.env`, database, model, bukti, atau dokumen lama yang diubah. Satu-satunya file baru adalah dokumen ini. Tidak ada commit.

## Cara audit dilakukan

**Repositori referensi.** Kelima repositori publik di-*clone* dangkal (`--depth 1`) ke folder sementara di luar proyek, lalu README, dokumen, dan kode sumbernya dibaca. Tidak ada kode referensi yang dijalankan. Versi yang dibaca:

| # | Repositori | Commit | Isi |
|---|---|---|---|
| R1 | AnasMultani17/Cheating-Detection-From-Video | `80f7205` (29 Nov 2025) | `README.md`, `main.ipynb` (2 file) |
| R2 | khalequzzamanlikhon/sentinel-video-anomaly-detection | `1e44bd8` (16 Sep 2026) | Paket `sentinel/`, `scripts/`, `tests/`, `config/`, `demo_outputs/` (158 file) |
| R3 | vardanagarwal/Proctoring-AI | `4f284a3` (10 Des 2024) | Modul Python per fungsi + model (184 file) |
| R4 | Kevalshah91/Advanced-Proctoring-System | `173bac3` (30 Mar 2025) | `proc.py`, `proc1.py`, `proc2.py`, model Caffe, log (13 file) |
| R5 | jeeva5655/ProctorAI | `37fa097` (20 Apr 2026) | Aplikasi web `js/`, dokumen perencanaan, metadata YOLO (24 file) |

**Keterbatasan:**

- File biner lebih dari 2 MB (bobot model besar) tidak diunduh. Dataset eksternal (OEP, Roboflow, MSU) tidak tersedia di repositori mana pun, jadi angka hasil pelatihan referensi **tidak dapat diverifikasi ulang**.
- Model YOLO R5 diunduh saat runtime dari Hugging Face dan tidak diperiksa.
- Klaim di README yang tidak punya kode pendukung ditandai sebagai "klaim README".

**EduAI.** Yang diperiksa adalah jalur pemanggilan yang benar-benar berjalan (dari endpoint/worker sampai SQLite dan PDF), bukan nama file atau komentar. Rujukan baris memakai keadaan file saat audit.

**Status di tabel:**

- **Sudah** — pendekatan setara ada dan terhubung ke pipeline utama.
- **Sebagian** — ada, tetapi tidak lengkap atau tidak terhubung penuh.
- **Belum** — tidak ada di kode EduAI.
- **Tidak Relevan** — sengaja tidak diadopsi karena bertentangan dengan tujuan, privasi, atau data EduAI.

---

## 1. Ringkasan tingkat kesesuaian per repositori

| Repositori | Inti teknis yang sebenarnya ada di kodenya | Kesesuaian EduAI | Catatan utama |
|---|---|---|---|
| R1 AnasMultani17 | CNN biner 48×48 grayscale per frame; split per subjek; P/R/F1, confusion matrix, ROC | **Rendah, dan sebagian besar disengaja.** Klasifikasi "curang/tidak" tidak relevan. Yang relevan adalah praktik evaluasinya: pemisahan per subjek sudah ada di protokol, confusion matrix/ROC belum. | Kode notebook tidak konsisten dengan keluarannya (bagian 2.1). Hasil uji: recall 0,019, F1 0,034. |
| R2 Sentinel | Rule engine berbasis persistensi, deduplikasi per sumber/tipe/track, severity, thumbnail + klip, SQLite dengan tanda false positive, metrik Prometheus (FPS, lag, frame dibuang), skrip benchmark FPS dan *soak test* | **Tinggi untuk logika kejadian. Rendah untuk pemantauan kinerja.** Persistensi, dedup, episode, bukti, dan tinjauan sudah ada (lebih lengkap). FPS, lag, memori, dan benchmark berulang belum. | Track ID, multi-kamera, klip video, dan LSTM tidak relevan atau dilarang. |
| R3 Proctoring-AI | Modul terpisah: eye tracking (threshold piksel), mulut terbuka, YOLOv3 orang/ponsel, head pose (solvePnP), face spoofing, audio speech-to-text; tabel FPS i5 | **Sedang.** Head pose, mulut, orang, dan ponsel ada dengan pendekatan lebih baru. Eye tracking dan anti-spoofing belum. Tabel FPS per perangkat belum. | `main.py` menjalankan modul berurutan pada video dan hanya `print()`. Tidak ada logika temporal atau penyimpanan. |
| R4 Kevalshah91 | Penghitung frame berturut-turut + ambang (ponsel >5, wajah hilang >30, menoleh >45), Haar cascade, Face Mesh, logging berkas | **Tinggi untuk konsep, EduAI lebih ketat.** Seluruh perilaku yang benar-benar berjalan sudah ada di EduAI dengan aturan berbasis detik. | Klaim README (alarm audio, screenshot, laporan) **tidak ada di kode**. Ada dua bug deteksi ponsel (bagian 2.4). |
| R5 jeeva5655/ProctorAI | Aplikasi browser: Face Mesh (iris aktif) untuk yaw/pitch berbasis rasio, COCO-SSD + YOLOv8 kustom 8 kelas, Hands, emosi, earphone heuristik, *throttle* alert 2 dtk, FPS di UI, skor ancaman 0–5 | **Sedang.** Wajah, banyak orang, objek, alert, dan analisis di sisi browser (audio) ada. Gaze/iris, earphone, dan tampilan FPS belum. Emosi dan skor ancaman tidak relevan. | Rencana benchmark (mAP vs waktu inferensi) hanya dokumen, tanpa hasil. Log aktivitas hanya di DOM (maks. 50 baris, hilang saat muat ulang). |

---

## 2. Temuan penting dari kode referensi

Bagian ini penting karena di beberapa referensi, kode sumbernya berbeda dari yang diklaim README.

### 2.1 R1: AnasMultani17/Cheating-Detection-From-Video (`main.ipynb`)

- `extract_frames()` (sel 3) mengambil 1 frame/detik, grayscale 48×48. Timestamp dihitung `time_sec = idx / fps` (sel 4), padahal `idx` adalah indeks frame **setelah** sampling. Waktu sebenarnya `idx * step / fps`, jadi pemetaan ke ground truth `gt.txt` (mulai, selesai, tipe) bergeser.
- Di versi yang di-commit, `OEPDataset.__init__` (sel 4) tidak pernah menambahkan sampel ke `self.data`. Loop berhenti di `time_sec = …`, padahal keluaran sel 5 menunjukkan 14.242/10.911 sampel. Notebook diubah setelah dijalankan, jadi hasilnya **tidak dapat direproduksi** dari kode ini.
- Split: subjek "acting" untuk latih, subjek "real" untuk uji (sel 5). Ini split per subjek, praktik yang benar.
- Hasil uji (sel 8): akurasi 0,716, presisi 0,210, **recall 0,019, F1 0,034**. Akurasi tinggi hanya karena kelas tidak seimbang.
- ROC (sel 9) dihitung dari prediksi kelas keras (`all_preds`), bukan skor probabilitas, sehingga kurvanya hanya satu titik. Sel 9 juga berisi teks rusak (`plt.title("ROC Curve")8ipbg0t00`) yang membuatnya gagal dijalankan.

### 2.2 R2: Sentinel

- `sentinel/capture/frame_buffer.py:31-36`: timestamp diambil **saat frame ditangkap** (`put`). Riwayat terbatas waktu dipakai untuk klip sebelum/sesudah kejadian.
- `sentinel/anomaly/rule_engine.py`: aturan dengan `min_persist_sec` / `min_duration_sec` per detektor.
- `sentinel/alerts/deduplicator.py:7-21`: kunci (sumber, tipe, track_id) dalam `dedup_window_sec`. Waktu terakhir **selalu** diperbarui, termasuk untuk duplikat, sehingga kejadian yang terus berulang tidak pernah memicu alert lagi selama jaraknya < jendela.
- `sentinel/alerts/alert_manager.py`: severity tetap per tipe (19-25), thumbnail langsung, klip menyusul lewat `threading.Timer` setelah `post_event_sec` (81-87).
- `sentinel/alerts/storage.py:12-27`: tabel `alerts` dengan `confidence`, `thumbnail_path`, `clip_path`, `details_json`, `false_positive` (tanda tinjauan manusia).
- `sentinel/core/metrics.py:12-24` + `core/pipeline.py:106, 141-148`: gauge `inference_fps`, `stream_lag_seconds` (sekarang − timestamp tangkap), counter frame diproses/dibuang.
- `scripts/benchmark_fps.py`: pemanasan dikecualikan, lalu N frame diukur. `scripts/stress_test.py`: soak test dengan RSS (psutil). Hasil mentah ada di `demo_outputs/` (32,3 FPS, GPU; soak 3 menit, memori +2,7 MB).
- README bagian "Honest reading of the results" menyatakan MOTA/IDF1/mAP **tidak diukur**.
- `sentinel/anomaly/lstm_autoencoder.py` **tidak dipanggil** oleh pipeline. Tes unit ada untuk dedup, alert, dan aturan (`tests/`).

### 2.3 R3: vardanagarwal/Proctoring-AI

- `main.py:13-19`: endpoint FastAPI menjalankan `track_eye`, `detect_head_pose`, `mouth_opening_detector`, dan `detect_phone_and_person` **berurutan** pada video yang sama. Tiap fungsi membuka `VideoCapture` sendiri dan memakai `cv2.imshow`, jadi butuh GUI. Hasilnya hanya `print()` dan respons `{"message": "Success"}`.
- `person_and_phone.py:330-356`: YOLOv3 COCO, kelas 0 = orang dan 67 = ponsel. Tidak ada ambang yang tertulis eksplisit di loop. Status dicetak **per frame** tanpa persistensi.
- `head_pose_estimation.py:170-215`: `solvePnP` + sudut garis, ambang ±48°, keluaran `print`.
- `eye_tracker.py:43-54, 163, 192-193`: posisi pupil dari threshold biner. Ambang diatur manual lewat *trackbar* GUI, dibuat saat modul diimpor.
- `mouth_opening_detector.py:20-60`: kalibrasi 100 frame pertama, lalu jarak bibir dibandingkan.
- `face_spoofing.py`: skrip mandiri (`VideoCapture(0)` di tingkat modul) dan **tidak dipanggil** dari `main.py`. README sendiri menyebut akurasinya belum baik.
- README 86-96: tabel FPS di Intel i5 (orang+ponsel 1,3 FPS; head pose 8,5 FPS). **Tidak ada skrip pengukur di repositori**, jadi angka itu klaim README.
- `audio_part.py`: speech-to-text Google + NLTK dibandingkan dengan soal.

### 2.4 R4: Kevalshah91/Advanced-Proctoring-System

- `proc2.py:26-33, 126-193`: penghitung per perilaku. Ponsel memicu bila > 5 frame, wajah hilang > 30, mata tak terlihat > 10, menoleh > 45. **Banyak wajah langsung memicu tanpa ambang.** Ambang dalam **frame**, bukan detik, sehingga bergantung pada FPS.
- **Bug 1:** `proc2.py:65-77`, `detect_phone()` menghitung **semua** deteksi YOLOv5 dengan conf > 0,5 sebagai ponsel, tanpa filter kelas. Orang yang terdeteksi pun dianggap ponsel.
- **Bug 2:** `proc.py:94-110` memakai MobileNet-SSD Caffe dengan `num_classes: 21` (`proc_models/deploy.prototxt:3091`), tetapi mencari `class_id == 67`. Ponsel **tidak akan pernah** terdeteksi di varian ini.
- Menoleh = jarak horizontal hidung–tengah mata > 15 % lebar frame (`proc2.py:103-119`). `proc1.py:150-170` memakai rasio terhadap jarak antarmata.
- Logging: `proctoring_log_*.txt` mencatat satu baris per frame. Contoh `proctoring_logs/proctoring_log_20250119.txt` berisi "Multiple faces detected" berkali-kali dalam detik yang sama, artinya **tanpa deduplikasi**.
- README mengklaim "Live audio alerts", "Capture Screenshot & Record", dan "Generate Report". Di ketiga file `.py` **tidak ada** `imwrite`, kode audio, atau pembuat laporan.

### 2.5 R5: jeeva5655/ProctorAI

- `js/main.js:163-375` (`gameLoop`, `requestAnimationFrame`):
  - gaze tiap 3 frame, objek tiap 10, tangan tiap 5, emosi tiap 45, earphone tiap 15;
  - FPS dihitung dan ditampilkan (`main.js:145-175`);
  - jadwal berbasis **jumlah frame**, sehingga laju nyata bergantung pada FPS perangkat.
- `js/detectors/face_monitor.js`: wajah hilang atau banyak wajah > 30 frame (≈1 dtk pada 30 fps).
- `js/detectors/gaze_tracker.js`: FaceMesh dengan `refineLandmarks: true` (iris, baris 26). Yaw/pitch dari **rasio jarak** landmark dengan ambang tetap (76-95). Komentar di kode sendiri menyebut ambangnya belum pasti.
- `js/detectors/object_detector.js`:
  - COCO-SSD `lite_mobilenet_v2` dengan skor min **0,25** (118);
  - YOLOv8 kustom 8 kelas (`models/yolo/metadata.yaml`: earphone, hand_gestures, head_rotation, mobile_phone, normal, paper_passing, peeking, smartwatch) dengan ambang **0,08** + NMS (234-236).
- `main.js:545-556`, `triggerAlert`: *throttle* satu alert per tipe per 2 dtk.
- `main.js:63-80`, `logActivity`: hanya ke DOM, maks. 50 entri, tanpa penyimpanan atau ekspor.
- `main.js:629-638`: skor ancaman = jumlah bobot status aktif (maks. 5).
- Dokumen `ALGORITHM_COMPARISON.md`, `TRAINING_GUIDE.md`, dan `PROJECT_REPORT_ALGORITHMS.md` merencanakan perbandingan YOLOv8 / SSD / Faster R-CNN / DETR dengan mAP@50 vs waktu inferensi. **Tidak ada angka hasil** di repositori. `DATASET_ANALYSIS.md` menegaskan dataset Roboflow berisi gambar lepas, bukan video, jadi LSTM tidak bisa dilatih.

---

## 3. Tabel perbandingan fitur

Lokasi EduAI ditulis sebagai `file:baris`. File AI berada di `ai/eduai-ai/src/eduai_ai/`; backend di `backend/app/`.

### 3.1 Frame extraction dan timestamp

| Repo | Fitur / pendekatan | Lokasi di referensi | Lokasi EduAI | Status | Bukti implementasi | Rekomendasi |
|---|---|---|---|---|---|---|
| R2 | Timestamp saat frame ditangkap | `capture/frame_buffer.py:31-36` | `frontend/src/media.ts:170-193`, `ai_service.py` (`submit_jpeg`), `livekit_worker.py:136-153` | **Sebagian** | Worker: `ts = time.time()` saat frame dibaca dari track. Jalur browser: `ts` = waktu server **menerima** JPEG; waktu ambil di browser tidak dikirim | Kirim waktu ambil dari browser sebagai metadata, dan catat selisihnya (lag) |
| R2 | Ukur lag tangkap→proses | `core/pipeline.py:106` | — | **Belum** | Tidak ada pengukuran lag | Satukan dengan G-K1 (bagian 5) |
| R1 | Sampling tetap dari berkas video, timestamp dari indeks | notebook sel 3-4 | `scripts/run_webcam.py:74-77` | **Sudah** (lebih benar) | Video berkas: `ts = CAP_PROP_POS_MSEC/1000`. R1 salah menghitung waktu (`idx/fps`) | — |
| R5 | Jadwal per model berdasarkan jumlah frame | `main.js:182-211` | `perception.py:185-209` | **Sudah** (berbasis detik) | Detektor objek dan CLIP jalan per `phone_every_s` / `every_s` = 0,5 dtk, tidak bergantung FPS | — |
| — | Back-pressure | R2: antrean + `FRAMES_DROPPED` | `ai_service.py` (`submit_jpeg`: satu frame diproses per mahasiswa), `media.ts` (satu unggahan sekaligus) | **Sebagian** | Frame "busy" dibuang; penghitungnya hanya global dan di memori (`/ai/health`) | Hitung per mahasiswa per sesi |

### 3.2 Deteksi wajah dan wajah tidak ada

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R3, R4, R5 | Deteksi wajah (DNN Caffe / Haar / FaceMesh) | R3 `face_detector.py`; R4 `proc2.py:145-150`; R5 `gaze_tracker.js` | `perception.py:86-90, 166-169` | **Sudah** | BlazeFace short-range, `min_confidence` 0,5, dipakai di setiap frame berkualitas | — |
| R4, R5 | Wajah hilang setelah N frame | R4 `proc2.py:147-152` (>30); R5 `face_monitor.js` (>30) | `temporal.py:444-448` + `SustainedIndicator` (`temporal.py:27-106`) | **Sudah** (lebih ketat) | `FACE_ABSENT` ≥ 5 dtk, rilis 1 dtk, cooldown 30 dtk; frame gelap/buram/beku tidak dihitung (`quality.py`) | — |
| R3 | Anti-spoofing wajah | `face_spoofing.py` (tidak terhubung ke `main.py`) | — | **Belum** | Tidak ada | Jangka panjang. Butuh data. Model R3 sendiri disebut belum akurat |

### 3.3 Deteksi banyak orang

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R3 | Hitung orang (YOLOv3 kelas 0) | `person_and_phone.py:341-350` | `perception.py:200`, `temporal.py:450-457` | **Sudah** | `person_count` dari EfficientDet-Lite0 (skor ≥ 0,4) **atau** jumlah wajah ≥ 2, bertahan ≥ 2 dtk | — |
| R4, R5 | Banyak wajah | R4 `proc2.py:153-156` (langsung); R5 `face_monitor.js` (>30 frame) | idem | **Sudah** | Persistensi 2 dtk; R4 tanpa persistensi | — |

### 3.4 Head pose dan eye tracking

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R3 | Head pose (solvePnP, ±48°) | `head_pose_estimation.py:170-215` | `perception.py:171-178`, `headpose.py:14-30`, `temporal.py:459-472` | **Sudah** (lebih baik) | Matriks transformasi FaceLandmarker → yaw/pitch; deviasi dari **baseline per mahasiswa** (median 45 dtk); histeresis 30°/20°; ≥ 3 dtk | Validasi tanda kiri/kanan dengan kamera nyata (`headpose.py:5-7`) |
| R4, R5 | Menoleh dari rasio landmark | R4 `proc2.py:103-119`; R5 `gaze_tracker.js:76-95` | idem | **Sudah** (pendekatan berbeda) | EduAI memakai sudut 3D, bukan rasio piksel | — |
| R4 | Tolehan berulang | — (R4 hanya penghitung) | `temporal.py:121-150, 474-477` | **Sudah** (EduAI punya, referensi tidak) | `HEAD_TURN_REPEATED`: 5 episode ≥ 1 dtk dalam 120 dtk | Bukti foto belum ada (E8 audit sebelumnya) |
| R3, R5 | Eye tracking / gaze (pupil, iris) | R3 `eye_tracker.py:43-54`; R5 `gaze_tracker.js:26` (`refineLandmarks`) | — | **Belum** | Pencarian `iris`, `eyeLook`, `gaze` di `ai/eduai-ai/src`, `backend/app`, `frontend/src` tidak menemukan apa pun. FaceLandmarker hanya membaca `jawOpen` (`perception.py:179-181`) | Sinyal eksperimen dari blendshape `eyeLook*` yang **sudah** dihasilkan model yang sama, tanpa indikator sampai ada data validasi |
| R3 | Mulut terbuka | `mouth_opening_detector.py:20-60` | `perception.py:179-181`, `temporal.py` (`_sound_signals`) | **Sudah** (digabung dengan audio) | `jawOpen` dipakai untuk membedakan "mahasiswa bicara" (info) dari "suara saat mulut diam" (indikasi) | — |

### 3.5 Deteksi ponsel dan objek

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R3, R4 | Ponsel dengan detektor COCO | R3 `person_and_phone.py:345` (kelas 67); R4 `proc2.py:65-77` (tanpa filter kelas), `proc.py:102` (kelas 67 pada model 21 kelas) | `perception.py:97-102, 185-196`, `temporal.py:479-485` | **Sudah** | EfficientDet-Lite0 dengan allowlist `cell phone`, skor ≥ 0,5 selama ≥ 1,5 dtk; skor puncak dan rata-rata disimpan (`details.confidence`, sejak Tahap 2) | Kalibrasi ambang di data validasi per peserta |
| R5 | Buku (COCO `book`) + YOLO kustom (`paper_passing`) | `object_detector.js:20-23, 206-236` | `perception.py:197-209`, `book_clip.py`, `temporal.py:487-505` | **Sudah** (pendekatan berbeda) | COCO `book` ≥ 0,35 **atau** CLIP zero-shot ≥ 0,6; sumber disimpan terpisah (`details.book_sources`) | — |
| R5 | Earphone, smartwatch, gestur tangan | `main.js:379-480` (heuristik warna telinga), YOLO kelas 0/7, `hand_gesture_detector.js` | — | **Belum** | Tidak ada kelas atau detektor | Belum dapat diverifikasi kelayakannya: R5 tidak menerbitkan metrik untuk kelas-kelas ini, dan EduAI belum punya data |
| R5 | YOLOv8 kustom 8 kelas | `models/yolo/metadata.yaml` | — | **Belum** (sengaja) | EduAI memakai model umum tanpa pelatihan ulang (`EVALUATION_PROTOCOL.md` §8) | Hanya sebagai pembanding di benchmark, bukan pengganti, sampai ada data berlabel per peserta |
| R2 | Ekspor ONNX | `scripts/export_onnx.py` | `book_clip.py:67-86` | **Sebagian** | Hanya CLIP yang ONNX; sisanya TFLite (MediaPipe) | Tidak perlu diubah |

### 3.6 Pemrosesan kejadian temporal

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R2 | Aturan berbasis persistensi (detik) | `anomaly/rule_engine.py` | `temporal.py:27-106` (`SustainedIndicator`) | **Sudah** | Buka setelah `min_duration_s`, tutup setelah `release_s`, nilai tak diketahui tidak bisa membuka | — |
| R4, R5 | Penghitung frame berturut-turut | R4 `proc2.py:26-33`; R5 `face_monitor.js` | idem | **Sudah** (berbasis detik) | Tidak bergantung FPS | — |
| R2 | LSTM autoencoder | `anomaly/lstm_autoencoder.py` (tidak dipanggil) | — | **Tidak Relevan** | Tidak ada data sekuens berlabel. Di R2 pun tidak terhubung | — |
| R5 | Skor ancaman 0–5 | `main.js:629-638` | — | **Tidak Relevan** | EduAI tidak menyatakan tingkat ancaman atau peluang curang (`events.py:4-5`, `report.py` `AI_NOTICE`) | Paling jauh: urutan prioritas tinjauan |
| R5 | Analisis emosi | `emotion_detector.js`, `main.js:166-174` | — | **Tidak Relevan** | Tidak ada kebutuhan dan data validasi | — |

### 3.7 Deduplikasi kejadian dan manajemen episode

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R2 | Dedup per (sumber, tipe, track) dalam jendela | `alerts/deduplicator.py:7-21` | `temporal.py:61-103` (cooldown), `cases.py:131-165` (`merge_episodes`, `episodes_of`, `episode_seconds`), `cases.py:94` (`group_events`) | **Sudah** (berlapis) | Cooldown di AI; kejadian bertumpuk ≤ 2 dtk digabung jadi satu episode; kasus per mahasiswa+indikator; satu aturan hitung untuk laporan, ringkasan, dan daftar kasus (Tahap 1) | Catat jumlah episode yang tertekan cooldown (E9) |
| R5 | Throttle alert per tipe 2 dtk | `main.js:545-556` | idem + `summary_rules` (`config.yaml`, `cases.py:168-180` `rule_status`) | **Sudah** | Pop-up pengawas menunggu aturan `min_count`/`window_s` | — |
| R2 | Severity per tipe | `alert_manager.py:19-25` | — | **Belum** | Hanya status aturan terpenuhi/tidak | Urutan prioritas tinjauan, bukan severity "ancaman" |
| R4 | Log per frame | `proctoring_logs/*.txt` | — | **Tidak Relevan** | EduAI menyimpan satu baris per kejadian (open → closed, `event_id` sama: `store.py:65-86`) | — |

### 3.8 Penangkapan dan penyimpanan bukti

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R2 | Thumbnail saat alert | `alert_manager.py:60-63`, `video_clipper.py` | `evidence.py:36-90` (`EvidenceBuffer`), `pipeline.py:53-56` | **Sudah** | 5 dtk sebelum + 5 dtk sesudah, maks. 12 JPEG 480 px; dimulai saat indikasi dibuka | Tambahkan bukti untuk `HEAD_TURN_REPEATED` (E8) |
| R2 | Klip video sebelum/sesudah | `video_clipper.py`, `alert_manager.py:81-99` | — | **Tidak Relevan** | Kebijakan EduAI: tanpa video penuh dan tanpa audio (`evidence.py:3-11`) | — |
| R2 | SQLite alert + path berkas | `alerts/storage.py:12-27` | `db.py` (`events`, `evidence`, `reviews`), `store.py:89-103`, `evidence.py:92-188` | **Sudah** (lebih lengkap) | Id acak, enkripsi Fernet opsional, akses berizin + audit, retensi | — |
| R2 | Tanda false positive oleh manusia | `storage.py:23` | `api.py` (`review_event`, `_add_review`), tabel `reviews` | **Sudah** (lebih lengkap) | Valid / Tidak Valid / Perlu Tinjauan Lanjut, append-only, riwayat utuh | — |
| R4 | Screenshot (klaim README) | tidak ada di kode | idem | **Sudah** di EduAI | — | — |

### 3.9 FPS, latensi, dan pemantauan sumber daya

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R2, R5 | FPS efektif live | R2 `metrics.py:12-14`, `pipeline.py:141-148`; R5 `main.js:145-175` | — | **Belum** | Tidak ada FPS per mahasiswa | Akumulator FPS per analyzer, tampil di `/ai/health` |
| R2 | Latensi / lag | `metrics.py:18-20` | `pipeline.py:47, 58` (`latency_ms`), `store.py` (`upsert_status`) | **Sebagian** | `latency_ms` pipeline per frame disimpan di `ai_status`, tetapi **ditimpa** tiap frame; tanpa per-komponen, persentil, atau lag | Latensi per komponen via `FrameSignals.metrics` + median/p90 |
| R2 | Frame diproses/dibuang | `metrics.py:21-24` | `ai_service.py` (`frames_in`, `frames_dropped`, `health()`) | **Sebagian** | Global, di memori, hilang saat restart | Per mahasiswa per sesi |
| R2 | Memori (RSS) dalam soak test | `scripts/stress_test.py:40-73` | — | **Belum** | `psutil` tidak terpasang | Skrip soak terpisah, tidak di produksi |
| — | Waktu muat dan pemanasan model | — | `model_check.py:99-117`, `ai_service.py` (`load_models`, `status()`) | **Sudah** (EduAI punya, referensi tidak) | `load_ms`, `warmup_ms` per model di `/api/ai/status` | — |

### 3.10 Agregasi sesi dan laporan PDF

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R2 | Dashboard analitik alert | `dashboard/pages/2_Analytics.py` | `cases.py:183-216` (`summarize`), `summary.py:104-136` (`build`), frontend halaman Indikasi | **Sudah** | Jumlah kejadian/episode, durasi episode, skor maks., bukti, status tinjauan, aturan | — |
| R4 | Laporan pelanggaran (klaim README) | tidak ada di kode | `report_export.py:133-209` (`build_pdf`), `report_export.py:212` (`build_xlsx`), `api.py:1375-1436` (`_report_summary`, `_report_data`) | **Sudah** di EduAI | PDF template resmi + XLSX; jumlah indikasi memakai aturan episode yang sama dengan ringkasan (Tahap 1) | — |
| — | Rata-rata confidence dan jumlah frame per episode | — | `temporal.py:197, 309-324` (`details` sejak Tahap 2) | **Sebagian** | Tersimpan di `events.details`, **belum** ditampilkan di UI/PDF | Tabel per indikasi di PDF (jumlah / rata-rata confidence deteksi / status tinjauan) |
| R5 | Log aktivitas | `main.js:63-80` (DOM, 50 entri) | `audit` + `events` di SQLite | **Sudah** (persisten) | — | — |

### 3.11 Benchmark dan evaluasi model

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R2 | Skrip benchmark FPS berulang | `scripts/benchmark_fps.py` | `scripts/smoke_test_models.py`, `model_check.warm_up` | **Sebagian** | Ada uji muat/pemanasan; belum ada skrip benchmark N-frame per komponen. Pengukuran 20 Nov 2026 (audit teknis) dilakukan dengan skrip sementara di luar repositori | Tambahkan `scripts/benchmark_models.py` (median/p90 per komponen, CPU, ukuran model) |
| R3 | Tabel FPS per perangkat | README 86-96 (tanpa skrip) | `docs/EDUAI_TECHNICAL_CODEBASE_AUDIT.md` lampiran 4 | **Sebagian** | Satu perangkat, frame acak tanpa wajah | Ulangi dengan frame nyata di ≥ 2 perangkat |
| R5 | Perbandingan YOLOv8/SSD/Faster R-CNN/DETR (mAP@50 vs ms) | `ALGORITHM_COMPARISON.md`, `TRAINING_GUIDE.md` (rencana, tanpa hasil) | — | **Belum** | EduAI tidak punya fungsi pelatihan atau evaluasi mAP | Evaluasi mAP@50 hanya bila ada anotasi kotak per peserta; model tidak diganti tanpa hasil |
| R1 | P/R/F1, confusion matrix, ROC | notebook sel 8-9 | `scripts/evaluate.py:37-70` | **Sebagian** | P/R/F1 + FP/jam di tingkat kejadian. Confusion matrix dan ROC belum. ROC R1 sendiri salah (dari prediksi keras) | Tambahkan PR/ROC dari **skor** model di tingkat frame/model |

### 3.12 Dataset, ground truth, dan evaluasi temporal

| Repo | Fitur | Lokasi referensi | Lokasi EduAI | Status | Bukti | Rekomendasi |
|---|---|---|---|---|---|---|
| R1 | Ground truth interval (mulai, selesai, tipe) | `gt.txt` via `parse_gt` (sel 3) | `scripts/evaluate.py` (`labels.csv`: video, indicator, start_s, end_s), `docs/EVALUATION_PROTOCOL.md` §3 | **Sudah** (format) | Pencocokan interval berbasis irisan (`--min-overlap`) | — |
| R1 | Split per subjek | sel 5 | `docs/EVALUATION_PROTOCOL.md` §4 | **Sebagian** | Ada di protokol; belum ada pemisahan yang dipaksakan di skrip | Tambahkan kolom peserta + pemisahan di `evaluate.py` |
| R1 | Dataset berlabel nyata | OEP (tidak ada di repositori) | `ai/eduai-ai/labels.csv`, `hours.csv`, `eval_behaviour.csv` | **Sebagian** | Berkas berisi sangat sedikit data (≤ 2 baris data); protokol menyebut 1 video ±3 menit, sehingga angkanya tidak boleh dikutip | Kumpulkan data pilot per protokol sebelum klaim akurasi |
| — | Evaluasi temporal (FP/jam, waktu sampai tanda, interval kepercayaan) | tidak ada di referensi mana pun | `evaluate.py` (FP/jam ada) | **Sebagian** | Waktu sampai tanda, Wilson/Poisson, dan kappa belum ada; error pada daftar kosong (`evaluate.py:91`) | Perluas sebelum set uji dibuka (`EVALUATION_PROTOCOL.md` §7) |
| R5 | Analisis dataset (gambar vs video) | `DATASET_ANALYSIS.md` | `EVALUATION_PROTOCOL.md` | **Sudah** (setara) | — | — |
| R3 | Audio speech-to-text + NLTK | `audio_part.py` | `frontend/src/audio.ts` (YAMNet di browser, skor saja) | **Tidak Relevan** | EduAI sengaja tidak mengirim atau menyimpan audio | — |

---

## 4. Daftar fitur yang belum diterapkan

| # | Fitur | Sumber referensi | Catatan |
|---|---|---|---|
| B1 | FPS efektif per mahasiswa, lag tangkap→proses, latensi per komponen, persentil | R2 (`metrics.py`, `pipeline.py`), R5 (`main.js`) | Hanya `latency_ms` terakhir yang ada |
| B2 | Skrip benchmark per komponen yang bisa diulang + soak test dengan memori | R2 (`benchmark_fps.py`, `stress_test.py`), R3 (tabel FPS) | |
| B3 | Waktu ambil frame dari browser | R2 (`frame_buffer.py`) | Jalur browser memakai waktu terima server |
| B4 | Eye tracking / gaze | R3 (`eye_tracker.py`), R5 (`gaze_tracker.js`) | Blendshape `eyeLook*` sudah tersedia dari model yang dipakai |
| B5 | Prioritas tinjauan (padanan severity) | R2 (`alert_manager.py`) | Tanpa label "ancaman" |
| B6 | Confusion matrix / PR / ROC dari skor model | R1 (sel 9, versi yang benar) | |
| B7 | Evaluasi mAP@50 detektor pada data EduAI | R5 (rencana) | Butuh anotasi kotak |
| B8 | Split per peserta yang dipaksakan di skrip evaluasi | R1 (sel 5) | |
| B9 | Statistik confidence di UI/PDF | — (lanjutan Tahap 2 EduAI) | Data sudah tersimpan di `details` |
| B10 | Anti-spoofing wajah | R3 (`face_spoofing.py`) | Model R3 sendiri belum akurat |
| B11 | Earphone, smartwatch, gestur tangan | R5 | Tanpa metrik di R5; tanpa data di EduAI |

**Sengaja tidak diadopsi:** klip video (R2), track ID multi-kamera (R2), LSTM autoencoder (R2), klasifikasi biner "cheating" (R1), skor ancaman (R5), emosi (R5), speech-to-text (R3), log per frame (R4).

---

## 5. Prioritas pengembangan

Skala: Manfaat T/S/R (tinggi/sedang/rendah); Risiko = kemungkinan merusak fitur, privasi, atau klaim; Kompleksitas = perkiraan usaha.

| Kode | Item | Manfaat | Risiko | Kompleksitas | Prioritas | Alasan |
|---|---|---|---|---|---|---|
| G-K1 | B1: FPS, lag, latensi per komponen, frame diproses/dibuang per mahasiswa (di memori, lewat `/ai/health`) | T | R (tanpa skema baru) | R–S | **1** | Dasar untuk menilai kapasitas server dan membaca hasil evaluasi |
| G-K2 | B2: `scripts/benchmark_models.py` + soak test terpisah | T | R (tidak menyentuh produksi) | S | **2** | Mengganti pengukuran sekali jalan dengan yang bisa diulang dan dilaporkan jujur, seperti R2 |
| G-E1 | B6 + B8 + perbaikan `evaluate.py` (E14, interval kepercayaan, split per peserta) | T | R | S | **3** | Syarat sebelum angka akurasi apa pun boleh dikutip |
| G-R1 | B9: tabel per indikasi di PDF (jumlah / rata-rata confidence deteksi / status tinjauan) | S–T | S (salah tafsir confidence) | R–S | **4** | Data sudah ada sejak Tahap 2; perlu kalimat batasan yang jelas |
| G-F1 | B3: waktu ambil frame dari browser + lag | S | S (mengubah kontrak unggah frame) | S | **5** | Memperbaiki ketepatan waktu kejadian di jalur browser/Jitsi |
| G-P1 | B5: urutan prioritas tinjauan | S | S (bisa terbaca sebagai "tingkat kecurangan") | R | **6** | Bermanfaat untuk sesi besar; wording harus netral |
| G-E2 | B7: mAP@50 + pembanding YOLOv8/SSD | S | R | T (butuh anotasi) | **7** | Hanya setelah ada data berlabel per peserta |
| G-G1 | B4: sinyal gaze eksperimental (`eyeLook*`), tanpa indikator | S | S (alarm palsu bila langsung jadi indikator) | S | **8** | Belum ada data validasi |
| G-X | B10, B11 | R | T | T | **Tunda** | Tanpa data dan metrik pendukung |

---

## 6. Rekomendasi urutan implementasi

1. **G-K1: pemantauan kinerja di memori.**
   - Tambahkan durasi per komponen ke `FrameSignals.metrics` di `perception.process`.
   - Tambahkan akumulator median/p90 dan FPS efektif per analyzer di `AIManager`, ditampilkan di `/ai/health`.
   - Tanpa tabel baru. Tes: nilai muncul dan overhead terukur.
2. **G-K2: skrip benchmark dan soak** di `ai/eduai-ai/scripts/`.
   - Video sampel dengan wajah; N frame setelah pemanasan; laporkan perangkat, versi pustaka, median/p90, dan ukuran model.
   - Tidak dijalankan di server produksi.
3. **G-E1: alat evaluasi.**
   - Perbaiki `evaluate.py` (daftar kosong, pencocokan, interval kepercayaan, split per peserta).
   - Tambahkan PR/ROC berbasis skor untuk detektor ponsel/buku.
   - Uji dengan data buatan yang jawabannya diketahui, **sebelum** set uji dibuka.
4. **G-R1: tabel ringkasan per indikasi di PDF.** Memakai `details` Tahap 2 dan `cases.episodes_of`, dengan catatan bahwa confidence ≠ peluang kecurangan.
5. **G-F1: waktu ambil frame dari browser.** Perlu perubahan kontrak API `/frames` dan frontend; uji regresi jalur browser dan Jitsi.
6. **G-P1: prioritas tinjauan.** Setelah wording disetujui.
7. **G-E2 dan G-G1** hanya setelah ada data pilot berlabel per peserta.

---

## 7. Kesimpulan

**Sudah benar-benar diadopsi** (terhubung ke pipeline utama, terbukti dari jalur pemanggilan):

- Deteksi wajah, wajah tidak ada, dan banyak orang dengan persistensi berbasis detik (R2/R3/R4/R5). EduAI lebih ketat karena memakai gerbang kualitas frame.
- Head pose relatif terhadap baseline per mahasiswa dan tolehan berulang (R3/R4/R5); mulut bergerak dipakai bersama skor suara (R3).
- Deteksi ponsel dengan filter kelas yang benar. Kedua bug deteksi ponsel di R4 tidak ada di EduAI.
- Mesin kejadian temporal berbasis persistensi, cooldown, dan rilis (R2).
- Deduplikasi berlapis dan manajemen episode dengan satu aturan hitung bersama (R2/R5).
- Bukti foto di sekitar kejadian, SQLite kejadian + tinjauan manusia append-only (R2). EduAI tanpa klip video, sesuai kebijakan.
- Laporan sesi PDF/XLSX. Laporan yang diklaim R4 tidak ada di kodenya, sedangkan di EduAI ada.
- Format ground truth interval dan evaluasi tingkat kejadian P/R/F1 + FP/jam (R1 dalam bentuk interval).

**Baru sebagian:**

- Timestamp frame: benar di jalur worker dan video berkas, tetapi jalur browser memakai waktu terima server.
- Latensi: hanya nilai terakhir; frame dibuang hanya dihitung global.
- Benchmark: uji muat/pemanasan ada, tetapi belum ada skrip benchmark per komponen yang bisa diulang (R2/R3).
- Evaluasi: P/R/F1 ada, tetapi confusion matrix/ROC, interval kepercayaan, dan split per peserta di skrip belum (R1).
- Data berlabel: format ada, isinya terlalu sedikit untuk klaim apa pun.
- Statistik confidence per episode: tersimpan sejak Tahap 2, belum tampil di UI/PDF.
- ONNX: hanya CLIP.

**Masih rencana:**

- FPS dan lag live, soak test dengan memori (R2/R5).
- Eye tracking/gaze (R3/R5).
- Prioritas tinjauan (padanan severity R2).
- mAP@50 dan perbandingan arsitektur detektor (R5; di R5 sendiri juga masih rencana).
- Anti-spoofing (R3).
- Earphone, smartwatch, dan gestur (R5).

**Sengaja tidak diadopsi:** klasifikasi biner "cheating" (R1); klip video, track ID, dan LSTM (R2); speech-to-text (R3); log per frame (R4); emosi dan skor ancaman (R5). Alasannya: bertentangan dengan prinsip EduAI (indikasi untuk ditinjau, bukan vonis; tanpa video penuh dan audio) atau tidak didukung data.
