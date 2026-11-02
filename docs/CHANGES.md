# Daftar perubahan

Sumber awal: `eduai-main.zip` (aplikasi web) dan `eduai-ai-prototype_1.zip` (modul AI). Struktur hasil integrasi:

```
eduai/
  frontend/      ← isi eduai-main (dipindahkan apa adanya, lalu diubah seperlunya)
  backend/       ← baru (FastAPI)
  ai/eduai-ai/   ← isi eduai-ai-prototype (diperluas)
  docs/          ← baru
  tests/e2e/     ← baru
```

## frontend/ (aplikasi web yang sudah ada)

| Berkas | Status | Alasan |
|---|---|---|
| `src/App.tsx` | **Diubah** | Desain, komponen UI (Icon, Button, Badge, AppShell, Sidebar, Topbar), nama halaman, menu per peran, dan alur layar dipertahankan. Data contoh (`sessions`, `students`, `indications`, akun di `localStorage`, `CreatedExam` di memori) diganti data API. Perubahan per layar: Login → `POST /api/auth/login`/`register`; Sidebar/Topbar → nama pengguna asli, jam sekarang, notifikasi indikasi nyata + pop-up; Dasbor (semua peran) → `/api/dashboard`; Sesi/Detail/Ruang tunggu → ujian & presence nyata, tombol "Mulai Pemantauan"; Create Ujian → `POST /api/exams` dengan daftar siswa/pengawas dari API; Cek Perangkat → `getUserMedia`, level mikrofon, latensi ke server; Persetujuan → `POST consent`, teks retensi diganti "maks. 1 hari (24 jam)" dan analisis audio dihapus dari teks (audio tidak dianalisis); Ruang Ujian → join, publish OpenVidu atau kamera lokal, heartbeat presence, pengunggah frame, tombol kamera/mikrofon berfungsi; Monitoring → status siswa/AI/kejadian nyata, tombol Mulai/Hentikan AI, video OpenVidu bila ada, filter baru "Tidak dapat dianalisis", pemilih "Tampilan contoh" dihapus; Detail Siswa/Linimasa → `/timeline`; Detail Evidence → cuplikan JPEG terautentikasi, validasi & catatan manual tersimpan; Indikasi → `/api/events`; Laporan → `/report`, ekspor CSV & cetak PDF; Riwayat, Daftar Siswa, Manajemen User, Audit, Retensi, Konfigurasi, Role & Izin → data/aturan backend. |
| `src/App.tsx` (komponen `CreateSession`, `IndicationDetail`) | **Dihapus** | Tidak dipakai di router asli (layar `create` memakai `AdminCreateExam`, layar `detail` memakai `SupervisorEvidenceDetail`). |
| `src/api.ts` | Baru | Klien REST bertipe, sesi token (sessionStorage), format waktu/label. |
| `src/media.ts` | Baru | Kamera/mikrofon, koneksi OpenVidu (`livekit-client`), pengunggah frame terbatas, pengukur level mikrofon & latensi, hook video ruang pengawas. |
| `package.json`, `package-lock.json` | Diubah | Tambah `livekit-client@2.22.4`. |
| `vite.config.ts` | Diubah | Proxy `/api` → backend saat pengembangan (tanpa CORS). |
| `.env.example` | Baru | Variabel frontend (tanpa rahasia). |
| `.gitignore` | Diubah | Mengecualikan `.env.example` dari pola `.env*`. |
| `README.md` | Diubah | Petunjuk menjalankan bersama backend. |
| `index.html`, `src/main.tsx`, `src/index.css`, `src/vite-env.d.ts`, `tsconfig.json`, `.gitattributes` | Tidak diubah | — |

Bagian yang masih **data contoh / belum tersambung** (diberi label "Data contoh" atau tombol dinonaktifkan): pengaturan profil/notifikasi (simpan), tambah user dari UI, edit/hapus ujian, finalisasi laporan (status tidak disimpan), ilustrasi pada panel kiri halaman login (gambar dekoratif).

## backend/ (baru)

| Berkas | Isi |
|---|---|
| `app/main.py` | Pembuatan aplikasi, lifespan (DB, seed demo, AI, evidence store, worker manager), CORS, tugas pemeliharaan (analisis idle, purge evidence) |
| `app/api.py` | Semua endpoint REST (lihat `docs/API.md`) |
| `app/ai_service.py` | Analisis frame browser: satu analyzer per siswa, ≤1 frame berjalan per siswa, semaphore global, thread pool |
| `app/livekit_service.py` | Token ruang OpenVidu hak minimum, manajer proses worker AI |
| `app/store.py` | Penyimpanan kejadian/evidence/status (dipakai kedua jalur frame), audit, purge |
| `app/security.py` | PBKDF2, JWT, dependensi peran, kunci layanan, pembatas login |
| `app/schemas.py` | Validasi body & kontrak kejadian schema 1.0 |
| `app/db.py` | Skema SQLite |
| `app/seed.py` | Akun & ujian demo (tanpa kejadian AI) |
| `app/settings.py` | Konfigurasi dari environment / `.env` |
| `tests/test_api.py`, `pytest.ini` | 17 tes API |
| `requirements.txt`, `.env.example`, `.gitignore` | Dependensi & contoh konfigurasi tanpa rahasia |

## ai/eduai-ai/ (prototipe yang sudah ada)

| Berkas | Status | Alasan |
|---|---|---|
| `config.yaml` | Diubah | Versi `0.2-provisional`; jalur model + fallback; ambang `CANNOT_ANALYZE`, baseline, evidence (maks. frame, lebar); ambang video beku 1,0→0,05 / 3→5 dtk (temuan uji). |
| `src/eduai_ai/signals.py` | Diubah | `status` eksplisit (`analyzed` / `cannot_analyze` / `model_unavailable`) + alasan. |
| `src/eduai_ai/quality.py` | Diubah | Alasan eksplisit (gelap, terang, buram, beku, resolusi, wajah terlalu kecil). |
| `src/eduai_ai/perception.py` | Diubah | Tiap model opsional & dilaporkan statusnya; hanya detektor wajah wajib; timestamp VIDEO mode monoton. |
| `src/eduai_ai/temporal.py` | Diubah | Pelacak `CANNOT_ANALYZE`, `flush()` saat pemantauan berhenti (menutup kejadian terbuka), `analysis_state()`, flag `head_pose_enabled` bila Face Landmarker tidak ada. |
| `src/eduai_ai/events.py` | Diubah | Validasi skema, kategori `indication`/`cannot_analyze`, versi model/config/skema, JSON Schema. |
| `src/eduai_ai/evidence.py` | Diubah | Evidence JPEG terbatas (bukan klip video), penyimpanan ber-ID acak, enkripsi opsional, retensi, penolakan path traversal. |
| `src/eduai_ai/config.py`, `__init__.py` | Diubah | Validasi config, resolusi jalur model, `MODEL_VERSION`. |
| `src/eduai_ai/headpose.py` | Tidak diubah | — |
| `src/eduai_ai/pipeline.py` | Baru | `StudentAnalyzer` (dipakai backend dan worker). |
| `src/eduai_ai/livekit_worker.py` | Baru | Worker OpenVidu (peserta tersembunyi, `rtc.VideoStream`). |
| `src/eduai_ai/backend_client.py` | Baru | Klien worker → backend (kunci layanan). |
| `scripts/run_webcam.py` | Diubah | Memakai `StudentAnalyzer`, opsi `--evidence-dir`, ringkasan latensi. |
| `scripts/download_models.sh` | Diubah | Unduh resmi + checksum. |
| `scripts/download_models.ps1`, `download_models.py`, `smoke_test_models.py` | Baru | Alternatif Windows, fallback wheel MediaPipe, smoke test model. |
| `scripts/evaluate.py` | Tidak diubah | — |
| `tests/test_core.py` | Diubah | 24 tes untuk API baru. |
| `tests/test_models_smoke.py` | Baru | Tes model nyata (skip bila model tidak ada). |
| `requirements.txt`, `pyproject.toml` | Diubah/baru | Paket dapat di-install (`pip install -e`). |
| `README.md` | Diubah | Petunjuk baru. |
| `models/` | — | Berkas model **tidak disertakan** di ZIP; unduh dengan skrip. |

## docs/ & tests/e2e/ (baru)

`README.md` (root), `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/MODELS.md`, `docs/TEST_RESULTS.md`, `docs/CHANGES.md`, `docs/screenshots/*.png`, `tests/e2e/make_fake_camera.py`, `tests/e2e/e2e_browser_flow.py`.

## Pembaruan 29 Oktober 2026 (audio, kasus, worker OpenVidu)

Dasar: `EduAI-integrated.zip`. Hasil uji: `docs/TEST_RESULTS.md` baris 16–23.

### Frontend
| Berkas | Status | Alasan |
|---|---|---|
| `src/App.tsx` | Diubah | (1) Persetujuan: sakelar analisis suara **opsional** terpisah dari persetujuan wajib; teks diperbarui. (2) Ruang ujian: menjalankan analisis suara di browser bila disetujui; status "Analisis suara aktif… (audio tidak dikirim)". (3) **Perbaikan**: dalam mode worker, siswa yang gagal terhubung ke OpenVidu kini mengirim frame lewat jalur browser (sebelumnya tidak dianalisis sama sekali). (4) Daftar indikasi/dasbor memakai kasus (indikasi berulang digabung), pop-up hanya untuk kasus baru. |
| `src/audio.ts` | Baru | YAMNet (MediaPipe Tasks Audio) di browser; hanya 3 skor dikirim per ±1 dtk; berhenti saat mikrofon dimatikan. |
| `src/audioScores.ts` | Baru | Pemetaan kategori YAMNet → skor ucapan/bisikan/musik (dapat diuji tanpa browser). |
| `src/notify.ts` | Baru | Logika pop-up per kasus (tanpa duplikat). |
| `src/api.ts` | Diubah | Tipe & panggilan `/audio`, `/cases`, info audio di `MonitoringInfo`. |
| `scripts/copy-mediapipe-wasm.mjs` | Baru | Menyalin WASM MediaPipe Audio ke `public/mediapipe-audio` (dijalankan `predev`/`prebuild`); berkas tidak diambil dari CDN. |
| `package.json`, `package-lock.json` | Diubah | `@mediapipe/tasks-audio@0.10.32` (versi sama dengan MediaPipe Python); hook `predev`/`prebuild`. |
| `.gitignore` | Diubah | Mengecualikan `public/mediapipe-audio/` (hasil salinan). |
| `tests/notify.test.ts`, `tests/audioScores.test.ts` | Baru | Tes unit (`node --experimental-strip-types`). |

### Backend
| Berkas | Status | Alasan |
|---|---|---|
| `app/api.py` | Diubah | `POST /exams/{id}/audio` (siswa, butuh persetujuan audio), `GET /ai/models/yamnet.tflite`; endpoint kasus `/cases`, `/exams/{id}/cases`, `/cases/{id}`, `/cases/{id}/reviews`; **perbaikan worker**: status `monitoring_active` disimpan sebelum worker dijalankan, Hentikan AI / ganti ke frame browser menutup kejadian yang ditinggalkan worker, heartbeat menjawab `stop` untuk worker yang tidak berlaku, `/frames` menerima frame cadangan dalam mode worker bila worker tidak melihat siswa itu (alasan `worker_active` bila melihat). |
| `app/cases.py` | Baru | Pengelompokan kejadian per (ujian, siswa, indikator) dengan jeda ≤ `EDUAI_CASE_GAP_S`. |
| `app/livekit_service.py` | Diubah | **Perbaikan Windows**: worker dijalankan dengan `CREATE_NEW_PROCESS_GROUP` dan dihentikan dengan `CTRL_BREAK_EVENT` (sebelumnya `terminate()` = `TerminateProcess`, worker tidak sempat menutup kejadian); POSIX: SIGTERM; tenggang 10 dtk lalu kill; `EDUAI_WORKER_ID` acak per worker. |
| `app/store.py` | Diubah | `close_open_events()` — menutup kejadian `open` tanpa mengubah data awal. |
| `app/main.py` | Diubah | Saat start: menutup kejadian worker yang tertinggal; saat shutdown: `stop_all` di thread (tidak memblokir event loop). |
| `app/schemas.py` | Diubah | `AudioScoresIn`, persetujuan `audio`, `HeartbeatIn.worker_id`, indikator `OTHER_VOICE`, skema review kasus. |
| `app/db.py` | Diubah | Kolom `consents.audio_accepted` (migrasi otomatis untuk DB lama), `run_all()` transaksional. |
| `app/ai_service.py` | Diubah | `submit_audio()` (batas frekuensi, butuh frame video lebih dulu). |
| `app/settings.py`, `.env.example` | Diubah | `EDUAI_AUDIO_ANALYSIS`, `EDUAI_CASE_GAP_S` (keduanya punya nilai bawaan; tidak wajib diisi). |
| `tests/test_audio.py`, `tests/test_cases.py`, `tests/test_worker_mgmt.py` | Baru | Regresi untuk fitur & perbaikan di atas (termasuk proses nyata untuk stop graceful/kill). |

### AI (`ai/eduai-ai`)
| Berkas | Status | Alasan |
|---|---|---|
| `src/eduai_ai/livekit_worker.py` | Diubah | Heartbeat tiap 5 dtk dengan `worker_id`; berhenti bila backend menjawab `stop`/pemantauan tidak aktif atau 12 heartbeat gagal (mencegah worker yatim); penangan berhenti lintas platform (`SIGBREAK`/`SIGINT` di Windows, karena `add_signal_handler` tidak didukung di sana). |
| `src/eduai_ai/backend_client.py` | Diubah | Coba ulang untuk galat jaringan/5xx dengan back-off (tidak untuk 4xx); `heartbeat()` mengembalikan jawaban backend. |
| `src/eduai_ai/temporal.py`, `events.py`, `pipeline.py`, `signals.py`, `perception.py`, `config.yaml` | Diubah | Indikator `OTHER_VOICE` (ucapan terdengar saat tepat satu wajah dengan mulut diam); `jawOpen` dari blendshape Face Landmarker; ambang sementara. |
| `scripts/download_models.{py,sh,ps1}` | Diubah | Juga mengunduh `yamnet.tflite`. |
| `tests/test_voice.py`, `tests/test_worker.py` | Baru | Aturan suara; coba ulang klien, berhenti via heartbeat, penangan sinyal, urutan kirim. |

### Tes & dokumentasi
| Berkas | Status | Alasan |
|---|---|---|
| `tests/e2e/e2e_livekit_worker.py` | Baru | E2E jalur worker OpenVidu (mode `stop` dan `kill`). |
| `README.md`, `docs/TEST_RESULTS.md`, `docs/API.md`, `docs/CHANGES.md` | Diubah | Status jujur, langkah audio & worker, hasil uji baru, kontrak heartbeat/`worker_active`. |

## Rapat Video (Jitsi Meet)

| Berkas | Status | Alasan |
|---|---|---|
| `frontend/src/jitsi.ts` | Baru | Memuat `lib-jitsi-meet` dari server Jitsi; hook `useJitsiRoom` dan `useJitsiTrack`. |
| `frontend/src/App.tsx` | Diubah | Layar `meeting` (`MeetingPage`), menu **Rapat Video**, dan izin layar untuk semua peran. |
| `frontend/.env.example` | Diubah | `VITE_JITSI_DOMAIN`, `VITE_JITSI_MUC`, `VITE_JITSI_SERVICE_URL`. |

## Desain baru (lambang, login, dasbor)

| Berkas | Status | Alasan |
|---|---|---|
| `frontend/public/brand/` | Baru | `eduai-seal.svg` (lambang vektor, teks sudah menjadi kurva), `eduai-mark.svg` (versi sederhana untuk ukuran ≤64 px), PNG turunan, dan ilustrasi login dari mockup. |
| `frontend/src/index.css` | Diubah | Tema navy-emas, font bawaan sistem (seperti Instagram; Segoe UI di Windows); berlaku untuk semua halaman. |
| `frontend/src/App.tsx` | Diubah | `Logo`, `Login`, `Sidebar`, `Topbar`, `PageTitle`, `SupervisorDashboard` mengikuti mockup. |
| `frontend/index.html` | Diubah | Favicon dan warna tema. |
| `tests/e2e/e2e_browser_flow.py`, `tests/e2e/e2e_livekit_worker.py` | Diubah | Placeholder login baru. |

Navigasi responsif: sidebar penuh di atas 1264px, ikon + tooltip di 768–1264px, top app bar + bottom navigation di bawah 768px (menu kelima dan seterusnya serta tombol keluar ada di **Lainnya**).

Belum tersambung backend: tombol SSO nonaktif; pilihan peran di login tidak memengaruhi peran (peran mengikuti akun).

## Laporan Sesi (backend, gambar bukti, ekspor, finalisasi, retensi)

| Berkas | Status | Alasan |
|---|---|---|
| `backend/app/report.py` | Baru | Status final, URL gambar bertanda tangan, salinan gambar, aturan retensi. |
| `backend/app/report_export.py` | Baru | PDF sesuai template "Laporan Hasil Pengawasan Ujian" dan Excel. |
| `backend/app/assets/eduai-seal.png` | Baru | Logo segel untuk PDF. |
| `backend/tests/test_report.py` | Baru | Hitungan ringkasan, akses, gambar, finalisasi, retensi, PDF, Excel. |
| `backend/app/api.py` | Diubah | Rute laporan, PATCH validasi, finalisasi, ekspor, penguncian jalur tulis. Audit laporan tidak lagi tercampur antarsesi (`exam:1` dan `exam:10`). |
| `backend/app/db.py`, `store.py`, `main.py`, `settings.py`, `schemas.py`, `.env.example`, `requirements.txt` | Diubah | Tabel `report_finals` dan `report_frames`, kolom `exams.finished_at` dan `events.evidence_deleted_at`, pengaturan retensi dan kop surat, `reportlab`, `openpyxl`. |
| `ai/eduai-ai/src/eduai_ai/evidence.py` | Diubah | `set_hold`: paket evidence dapat ditahan melewati masa simpan normal. |
| `backend/tests/test_api.py` | Diubah | Folder gambar laporan dialihkan ke direktori sementara. |
| `frontend/src/App.tsx`, `frontend/src/api.ts` | Diubah | Halaman Laporan dan Retensi Data. Ekspor CSV digantikan `.xlsx` dari backend. |
| `README.md`, `docs/API.md`, `docs/TEST_RESULTS.md` | Diubah | Aturan retensi, kontrak API, hasil uji. |

## Mode ujian Jitsi dan ESLint

| Berkas | Status | Alasan |
|---|---|---|
| `backend/app/jitsi.py` | Baru | Pengaturan server dan nama ruang ujian. |
| `backend/tests/test_jitsi.py` | Baru | Tes jalur Jitsi, sumber analisis, rapat biasa, dan gangguan koneksi. |
| `backend/app/api.py`, `ai_service.py`, `main.py`, `db.py`, `schemas.py`, `settings.py`, `.env.example` | Diubah | Sumber `jitsi` ditentukan server, `connection_log`, `presence.jitsi_state`, "tidak dapat dianalisis" saat track mati atau frame berhenti, `EDUAI_JITSI_*`. |
| `frontend/src/jitsi.ts`, `frontend/.env.example` | Diubah | Server Jitsi dibaca dari backend; `alpha.jitsi.net` dan `VITE_JITSI_*` dihapus. |
| `frontend/src/consent.ts`, `frontend/tests/consent.test.ts` | Baru | Teks persetujuan; perlu disetujui pihak sekolah. |
| `frontend/tests/meetingIsolation.test.ts` | Baru | Rapat Video tidak punya jalur ke analisis. |
| `frontend/src/App.tsx`, `frontend/src/api.ts` | Diubah | Pilihan dan label sumber, ruang ujian Jitsi, catatan koneksi, Rapat Video, teks persetujuan, jalur logo rail untuk build produksi. |
| `frontend/eslint.config.js`, `frontend/package.json`, `frontend/package-lock.json` | Baru/Diubah | ESLint untuk React + TypeScript, skrip `npm run lint`. |
| `tests/e2e/e2e_browser_flow.py` | Diubah | Teks persetujuan baru. |


## Akses gambar bukti

| Berkas | Status | Alasan |
|---|---|---|
| `backend/app/api.py` | Diubah | Satu pemeriksaan izin untuk `/api/evidence`, URL gambar laporan, dan PDF; penolakan diaudit; `can_view_evidence` dan `restricted_text` di laporan. |
| `backend/app/report.py`, `main.py` | Diubah | Keterangan akses dan baris audit pencabutan akses per peran. |
| `backend/app/report_export.py` | Diubah | Keterangan yang sama di PDF dan Excel; gambar rusak kini berlabel "Gambar tidak dapat dibaca". |
| `backend/tests/test_report.py` | Diubah | Matriks akses, audit, laporan tanpa gambar, PDF. |
| `frontend/src/App.tsx`, `frontend/src/api.ts` | Diubah | Keterangan untuk penyelenggara dan sekolah; layar evidence tidak lagi meminta gambar untuk mereka. |
| `README.md`, `docs/API.md` | Diubah | Aturan akses; paragraf Jitsi yang usang di README diperbaiki. |
