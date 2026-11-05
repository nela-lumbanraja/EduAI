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

## Jitsi nyata, token, dan video langsung pengawas

| Berkas | Status | Alasan |
|---|---|---|
| `dev/jitsi/docker-compose.yml`, `LICENSE.docker-jitsi-meet` | Baru | Berkas resmi docker-jitsi-meet `stable-11248-2`, tanpa perubahan. |
| `dev/jitsi/.env.example`, `make-env.py`, `README.md` | Baru | JWT wajib, tanpa tamu, tanpa rekaman; pembuat `.env`; cara menjalankan dan troubleshooting. |
| `backend/app/jitsi.py` | Diubah | Domain XMPP, ruang per siswa, token satu ruang, pengecekan kesehatan. |
| `backend/app/api.py`, `settings.py`, `schemas.py`, `.env.example` | Diubah | `/jitsi/health`, `/jitsi/meeting-token`, `/exams/{id}/jitsi/watch`; `EDUAI_JITSI_XMPP_DOMAIN`, `_APP_ID`, `_APP_SECRET`. |
| `backend/tests/test_jitsi.py`, `test_api.py` | Diubah | Ruang per siswa, token, izin video langsung, token rapat, tiga status kesehatan. |
| `frontend/src/jitsi.ts`, `App.tsx`, `api.ts` | Diubah | Token, video pengawas per ruang siswa, kamera ujian dipakai ulang, pesan Rapat Video per peran. |
| `frontend/tests/meetingIsolation.test.ts` | Diubah | Rapat Video boleh memanggil kesehatan dan token rapat, tetap tanpa jalur ke analisis. |
| `README.md`, `docs/API.md`, `docs/TEST_RESULTS.md`, `.gitignore` | Diubah | Pengaturan `EDUAI_JITSI_*`, dev/jitsi, hasil uji, data server lokal diabaikan. |

## Safe Exam Browser (lockdown browser per ujian)

| Berkas | Status | Alasan |
|---|---|---|
| `backend/app/seb.py` | Baru | Hash SEB (`SHA256(URL tanpa fragmen + kunci)`), nonce sekali pakai, evaluasi Config Key / Browser Exam Key, status per siswa. |
| `backend/app/db.py` | Diubah | Tabel `exam_seb`, `seb_challenges`, `seb_status`. |
| `backend/app/api.py`, `schemas.py`, `settings.py`, `.env.example` | Diubah | `GET/PUT /exams/{id}/seb`, `/seb/challenge`, `/seb/verify`; `/join` menolak siswa tanpa SEB terverifikasi; status SEB per siswa untuk pengawas; `EDUAI_SEB_ALLOWED_ORIGINS`. |
| `backend/tests/test_seb.py` | Baru | 17 tes: hash, izin, tanpa kebocoran kunci, JS API, header bernonce, kedaluwarsa, audit. |
| `frontend/src/seb.ts`, `frontend/tests/seb.test.ts` | Baru | Membaca `window.SafeExamBrowser` (dengan `updateKeys`), tautan `seb://`/`sebs://`; 8 tes. |
| `frontend/src/App.tsx`, `api.ts` | Diubah | Layar pemeriksaan SEB sebelum Cek Perangkat, pemeriksaan ulang 60 detik di ruang ujian, panel admin di Detail Ujian, ringkasan dan lencana SEB di Monitoring. |
| `dev/seb/eduai-exam.template.xml`, `dev/seb/README.md` | Baru | Templat konfigurasi SEB (perlu ditinjau di SEB Config Tool) dan langkah admin. |
| `README.md`, `docs/API.md`, `docs/TEST_RESULTS.md` | Diubah | Bagian 7c, endpoint SEB, hasil uji. |

## Satu siaran per ujian: video mengikuti sumber AI

| Berkas | Status | Alasan |
|---|---|---|
| `backend/app/api.py` | Diubah | Token OpenVidu siswa ada di `monitoring.livekit` (join dan session-state) dan ditahan pada mode Jitsi; token OpenVidu staf juga ditahan pada mode Jitsi. |
| `backend/tests/test_jitsi.py` | Diubah | 2 tes: mode Jitsi tanpa token OpenVidu; beralih sumber memindahkan token tanpa masuk ulang. |
| `frontend/src/media.ts` | Diubah | Kamera dibuka sekali oleh halaman; siaran OpenVidu menjadi hook `useOpenViduBroadcast` yang menyiarkan track itu, hanya selama ada token, dan tidak mematikan kamera saat berhenti. |
| `frontend/src/jitsi.ts` | Diubah | Ruang ujian Jitsi hanya memakai salinan kamera halaman; tidak pernah membuka tangkapan kedua. |
| `frontend/src/App.tsx`, `api.ts` | Diubah | `useExamLiveVideo`: kartu, dialog Perbesar, dan halaman pantau siswa menampilkan video dari sumber AI ujian itu dan tidak membuka server lainnya. Label "Siaran langsung · Jitsi/OpenVidu". |
| `README.md`, `docs/API.md`, `docs/TEST_RESULTS.md` | Diubah | Aturan satu siaran, `monitoring.livekit`, hasil uji. |

## Buku (`BOOK_VISIBLE`) dan analisis suara di mode Jitsi

Bagian ini diport **selektif** dari `EduAI-arsitektur-AI.zip` (30 Okt). ZIP itu tidak disalin utuh, karena dibuat sebelum Laporan Sesi, Jitsi, SEB, dan aturan satu siaran, sehingga akan menimpa `api.py` dan `App.tsx`.

| Berkas | Status | Alasan |
|---|---|---|
| `ai/eduai-ai/src/eduai_ai/perception.py`, `signals.py`, `events.py`, `temporal.py` | Diubah | Detektor objek juga mengembalikan skor `book` (putaran yang sama dengan ponsel); aturan `BOOK_VISIBLE` (≥0,5 selama ≥3 dtk, lepas 2 dtk, cooldown 60 dtk; mati bila bagian config tidak ada). |
| `ai/eduai-ai/config.yaml` | Diubah | `indicators.BOOK_VISIBLE` (aktif) dan `summary_rules.BOOK_VISIBLE` (3 episode/jam); komentar `OTHER_VOICE` menyebut sumber Browser dan Jitsi. |
| `ai/eduai-ai/tests/test_book.py` | Baru | 5 tes aturan buku (dari ZIP). |
| `backend/app/schemas.py`, `cases.py`, `summary.py`, `main.py` | Diubah | Indikator `BOOK_VISIBLE` diterima; aturan kasus 3/jam; ringkasan hanya mencantumkan buku sebagai "tidak didukung" bila indikatornya mati. |
| `backend/app/api.py` | Diubah | `_audio_block` menerima sumber `jitsi` (sebelumnya `jitsi_mode`). |
| `frontend/src/App.tsx` | Diubah | YAMNet di browser siswa berjalan pada sumber Browser dan Jitsi. |
| `backend/tests/test_audio.py`, `test_jitsi.py`, `test_summary.py` | Diubah | `OTHER_VOICE` bersumber jitsi; audio tanpa persetujuan tetap mati; buku di ringkasan. |

**Belum diport dari ZIP:**
- Relay skor suara ke worker OpenVidu (`GET /api/ai/audio`, `backend_client.py`, `livekit_worker.py`). Akibatnya, mode worker OpenVidu tetap tanpa analisis suara (`worker_mode`).
- Sudut roll (tidak dipakai aturan mana pun).
- `docs/AI_ARCHITECTURE.md`.

## Jenis suara pada setiap kejadian suara

| Berkas | Status | Alasan |
|---|---|---|
| `ai/eduai-ai/src/eduai_ai/temporal.py`, `events.py` | Diubah | Satu jenis suara per saat: MUSIK_MEDIA, BISIKAN, BICARA_MULUT_DIAM (`OTHER_VOICE`), BICARA_SISWA. Indikator baru `MEDIA_SOUND`, `WHISPER`, `STUDENT_SPEECH`, masing-masing dengan ambang dan cooldown sendiri. Kategori baru `info` (tanpa gambar bukti, tidak menjadikan status siswa "indikasi"). Skor puncak per episode di `Event.details`. Bisikan tidak lagi dihitung sebagai `OTHER_VOICE`. |
| `ai/eduai-ai/config.yaml` | Diubah | Bagian `WHISPER`, `MEDIA_SOUND`, `STUDENT_SPEECH` (ambang, `category`, cooldown); aturan kasus `WHISPER`. |
| `ai/eduai-ai/tests/test_sound_labels.py`, `test_voice.py` | Baru / diubah | 11 tes label suara; tes bisikan disesuaikan. |
| `backend/app/db.py` | Diubah | Kolom `events.details`. CHECK `category` menerima `info`; basis data lama dibangun ulang otomatis dalam satu transaksi (baris dan review dipertahankan, `foreign_key_check` diperiksa). |
| `backend/app/schemas.py`, `store.py`, `api.py`, `cases.py` | Diubah | Validasi kategori per indikator dan `details` (tanpa kunci tambahan); `sound_text`; filter `category=info`; linimasa `kind: "info"`; `sound_info` di laporan; aturan kasus `WHISPER`. |
| `backend/app/report_export.py` | Diubah | Jenis suara dan skor di kolom kejadian (PDF dan Excel); baris "Catatan suara (info, bukan indikasi)". |
| `backend/tests/test_sound_labels.py` | Baru | 4 tes: label dan skor sampai laporan, musik sebagai info, validasi kategori dan `details`, migrasi DB lama. |
| `frontend/src/App.tsx`, `api.ts` | Diubah | Detail Evidence (kategori info, baris jenis suara), Laporan Sesi (jenis suara per baris, bagian catatan suara), linimasa, ikon mikrofon untuk info. |

**Sengaja tidak dibuat:** pengenalan suara orang dan penghitungan jumlah pembicara. Alasannya ada di `docs/API.md`.

## Masuk ulang ruang Jitsi dan pemeriksaan kategori info

| Berkas | Status | Alasan |
|---|---|---|
| `frontend/src/jitsi.ts` | Diubah | Keluar dari ruang (`conference.leave()`, lalu `dispose()` track lokal, lalu `connection.disconnect()`) dijalankan berurutan dalam satu antrean per halaman. Setiap bergabung (ruang ujian siswa, video pengawas, Rapat Video) menunggu antrean itu selesai. Saat tab ditutup atau dimuat ulang (`pagehide`), conference langsung ditinggalkan, tidak menunggu server mendeteksi peserta yang hilang. |
| `backend/tests/test_sound_labels.py` | Diubah | Tes bahwa kejadian `info` tidak masuk jumlah indikasi, kasus/pop-up, dasbor, ringkasan ujian, `rules_met`, atau jumlah indikasi laporan, walaupun `summary_rules` menyebut indikatornya. |

Tidak ada perubahan skema DB pada bagian ini.

