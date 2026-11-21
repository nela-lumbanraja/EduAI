# Session Report Phase 5, Tahap 1: Audit D4 (Ketersediaan Model)

Tanggal: 21 November 2026 · Status: **Audit hanya-baca selesai. Pemilik proyek memilih S1 (21 November 2026); Tahap 2 kemudian diimplementasikan dan diterima** (lihat `EDUAI_SESSION_REPORT_PHASE5_TAHAP2_RESULTS.md`). *Status awal: "audit hanya-baca selesai. Tahap 2 dihentikan sebelum ada perubahan, menunggu keputusan pemilik proyek" (syarat persetujuan Phase 5 nomor 3).*

Tidak ada kode, config, database, model, atau data yang diubah. Tidak ada commit. Rencana induk: `docs/EDUAI_SESSION_REPORT_PHASE5_PLAN.md`.

---

## 1. Jalur yang diperiksa

| # | Jalur | Berkas |
|---|---|---|
| A | Pemuatan model saat backend start | `backend/app/ai_service.py` `init`, `load_models`; `ai/eduai-ai/src/eduai_ai/model_check.py` `inventory` |
| B | Set model per peserta (sumber browser/Jitsi) dan set cadangan | `ai_service._perception`, `_make_spare`; `perception.MediaPipePerception.__init__`, `_load` |
| C | Inference per frame | `perception.process`; `ai_service.submit_jpeg`, `_analyse`, `observe` |
| D | Worker LiveKit/OpenVidu (proses terpisah) | `eduai_ai/livekit_worker.py`, `backend_client.py`; `api.ingest_status`, `api.heartbeat` |
| E | Audio (YAMNet di browser peserta) | `frontend/src/audio.ts`; `ai_service.submit_audio` |

## 2. Temuan

| # | Situasi | Perilaku sekarang | Dampak pada Session Summary | Penilaian |
|---|---|---|---|---|
| A | Model yang aktif di config gagal dimuat saat start | Semua model aktif bersifat wajib. Satu gagal → status AI `FAILED`, tidak ada frame yang dianalisis. | Tidak ada observasi → cakupan 0 dan `coverage_note` | **Aman** (gagal tertutup) |
| B1 | Face detector tidak termuat di set model peserta | Setiap frame berstatus `model_unavailable`; `is_observed` = salah | Detik tidak dihitung teramati → cakupan turun | **Aman** (gagal tertutup) |
| B2 | Face landmarker tidak termuat di set model peserta | `_load` menangkap galat; `engine.head_pose_enabled = False` | HEAD_TURN tidak pernah muncul, P_i = 0 dengan cakupan penuh | **Celah D4** |
| B3 | Object detector tidak termuat di set model peserta | Tidak ada skor ponsel, buku (COCO), atau jumlah orang | PHONE_VISIBLE = 0. BOOK_VISIBLE hanya dari CLIP. MULTIPLE_PERSONS hanya dari jumlah wajah (melemah, tidak nol). | **Celah D4** |
| B4 | CLIP tidak dibagikan (gagal saat start) lalu gagal dimuat per peserta | Model `None`, tanpa jejak di laporan | BOOK_VISIBLE hanya dari COCO (melemah) | **Celah D4** (parsial) |
| B5 | Set cadangan (`_make_spare`) | Hasil `warm_up` diabaikan; cadangan dengan model gagal tetap diberikan ke peserta berikutnya | Sama dengan B2–B4 | **Celah D4** |
| C1 | Galat inference face/landmarker/object detector | Tidak ditangkap di `perception.process`; frame gagal dan `observe` tidak dipanggil | Detik tidak teramati → cakupan turun. Galat tunggal dapat terjembatani oleh `GAP_S` = 2 dtk. | **Aman** (gagal tertutup; efek kecil) |
| C2 | Galat inference CLIP | Ditangkap dan dicatat di log saja (`perception.py` baris 225) | BOOK_VISIBLE (bagian CLIP) bisa 0 tanpa jejak | **Celah D4** (parsial) |
| D1 | Worker: status model | Dikirim lewat heartbeat, tetapi hanya status set model **terakhir** dan per ujian (`workers.models_json`), bukan per peserta. Status ditimpa setiap kali peserta baru masuk. | Tidak dapat menunjukkan peserta mana yang terdampak | **Celah D4** |
| D2 | Worker: face detector tidak termuat | `frame_status = model_unavailable` → tidak teramati (`ingest_status`) | Cakupan turun | **Aman** |
| E1 | YAMNet gagal dimuat atau gagal mengklasifikasi di browser | Tidak ada skor yang dikirim | Tidak ada sampel audio → `no_audio_data` (T1) | **Aman** (ditangani T1) |

**Ringkasan:**
- Kegagalan face detector, kegagalan saat start, dan kegagalan audio sudah gagal tertutup, sehingga cakupan turun atau muncul `no_audio_data`.
- Celah D4 yang nyata adalah model **opsional per peserta** yang tidak termuat (landmarker, object detector, CLIP) atau galat CLIP saat inference. Kondisi ini menghasilkan 0 yang tampak sah.
- Celah ini terjadi di backend (B2–B5, C2) maupun di worker (D1).

## 3. Mengapa Tahap 2 dihentikan

K4 meminta status ketersediaan model **dicatat per peserta** sampai finalisasi. Hasil audit menunjukkan tidak ada tempat penyimpanan yang sesuai tanpa perubahan skema:

| Tempat yang ada | Masalah |
|---|---|
| Memori `ai_service` saja | Analyser dihapus saat pemantauan dihentikan (`stop_student`), sebelum finalisasi. Hilang juga bila backend dimuat ulang. Pencatatan menjadi tidak lengkap tanpa tanda. |
| `ai_status` | Satu baris per peserta yang terus ditimpa, tanpa kolom untuk status model |
| `workers.models_json` | Per ujian dan hanya untuk worker |
| `events` kategori `info` | Tidak perlu kolom baru, tetapi akan muncul di daftar kejadian, laporan, dan PDF, sehingga mengubah tampilan laporan dan perilaku di luar lingkup |
| `audit` | Log tindakan pengguna yang ditampilkan di halaman admin; bukan tempat data analisis |

Memasang pencatatan yang andal memerlukan perubahan skema (tabel baru). Sesuai syarat 3, saya **berhenti sebelum mengubah apa pun**.

## 4. Opsi untuk diputuskan

| Opsi | Isi | Kelebihan | Kekurangan |
|---|---|---|---|
| **S1 (saran)** | Tabel baru aditif, misalnya `model_availability`: satu baris per ujian, peserta, model, dan sumber, berisi status awal, waktu pertama tidak tersedia, jumlah galat inference, dan alasan. Diisi oleh backend (B, C2) dan dari worker lewat `/api/ai/status` atau heartbeat per peserta (D1). Migrasi aditif dengan cadangan otomatis seperti Phase 2. | Andal setelah restart dan setelah pemantauan berhenti. Tidak mengubah tabel lain, rumus, atau snapshot Phase 4. Status masuk ke metadata JSON baris `*` tanpa kolom baru. | Perlu migrasi skema produksi (aditif), yang perlu persetujuan terpisah |
| S2 | Memori saja, disimpan sampai finalisasi; bila backend pernah dimuat ulang selama sesi, status menjadi "ketersediaan model tidak tercatat lengkap" | Tanpa perubahan skema | Pencatatan lemah. Restart membuat sesi tidak bisa dikalibrasi. Bergantung pada deteksi restart. |
| S3 | Tunda penanganan D4. Kerjakan dulu mekanisme kalibrasi (Tahap 3) dengan syarat "status D4 harus diketahui"; karena belum ada pencatatan, semua sesi menjadi `not_calibrated` dengan alasan "ketersediaan model tidak tercatat" | Tidak ada perubahan skema; aman, karena tetap tidak ada probabilitas | D4 tetap tidak terlihat di laporan sampai S1/S2 dikerjakan |

Apa pun pilihannya, rumus P_total, P_i, bobot, penyebut, normalisasi, dan snapshot Phase 4 tidak berubah, dan tidak ada probabilitas di produksi.

## 5. Yang saya perlukan dari pemilik proyek

1. Pilihan S1, S2, atau S3. Saran saya **S1**; S3 dapat dijalankan sementara bila migrasi belum ingin dilakukan.
2. Bila S1: persetujuan migrasi skema aditif (satu tabel baru, tanpa mengubah tabel lain dan data historis), dengan cadangan otomatis dan uji di salinan database seperti Phase 2. Termasuk persetujuan perubahan kecil pada pesan heartbeat/status worker agar status model terkirim per peserta.
