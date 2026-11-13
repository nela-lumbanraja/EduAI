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


## Desain Figma di frontend (tahap 1–4)

| Berkas | Status | Alasan |
|---|---|---|
| `frontend/src/index.css`, `frontend/src/main.tsx` | Diubah | Warna navy `#14213D`, emas `#C9A227`, dan latar `#F7F6F2`. Huruf Public Sans dan Libre Baskerville disimpan lokal lewat `@fontsource`, tanpa Google Fonts. Ditambah animasi layar roket. |
| `frontend/src/App.tsx` | Diubah | Sidebar, top bar, badge, Beranda, layar roket, Login (Portal Siswa / Sekolah), dan dasbor pengawas mengikuti desain Figma. Logika data, video, dan AI tidak berubah. |
| `frontend/src/routes.ts` | Baru | Layar awal dari alamat halaman, tombol Beranda ("Kembali ke Dasbor" bila sudah masuk), dasbor per peran, dan pesan galat login yang tidak membocorkan apakah akun ada. |
| `frontend/src/time.ts` | Baru | Waktu UTC dari backend ditampilkan dalam WIB: "baru saja", "x mnt lalu", "x jam lalu", "x hari lalu", lalu tanggal dan jam. Ujian yang sudah selesai selalu memakai tanggal dan jam. |
| `frontend/src/dashboard.ts` | Baru | Angka dasbor dari API ("Belum ada data" bila kosong), sisa waktu ujian, dan status "Tidak dapat dianalisis" per siswa (kamera atau suara). |
| `frontend/tests/routes.test.ts`, `time.test.ts`, `dashboard.test.ts` | Baru | Tes unit untuk modul di atas. |
| `frontend/e2e/` | Baru | Tes ujung-ke-ujung dengan backend dan DB uji baru (bukan DB asli). Kata sandi diambil dari `EDUAI_E2E_PASSWORD`. |
| `backend/app/api.py` | Diubah | `GET /api/health` ikut mengirim `school_name` (`EDUAI_SCHOOL_NAME`, juga dipakai kop PDF); nilai kosong dikirim sebagai `null`. |

Keterbatasan yang diketahui: alamat di bilah browser tidak berganti saat berpindah halaman, karena SEB memakai URL halaman (lihat `frontend/README.md`). Ukuran bundle JS sekitar 974 kB dan akan dipecah per halaman nanti.

## Grafik dasbor, Monitoring, Indikasi, dan Laporan Sesi

| Berkas | Status | Alasan |
|---|---|---|
| `backend/app/api.py` | Diubah | Endpoint baca-saja `GET /api/dashboard/detections-per-hour?date=YYYY-MM-DD`: deteksi AI per jam WIB, dihitung dari tabel `events` yang sudah ada, hanya untuk ujian yang boleh dilihat pengguna. Tanpa tabel baru; logika lain tidak berubah. |
| `backend/tests/test_detections_per_hour.py` | Baru | Batas hari WIB (17.00 UTC), hari tanpa data, akses per peran (pengawas hanya ujian miliknya, pihak sekolah hanya indikasi tertinjau, siswa ditolak), dan tanggal tidak valid. |
| `frontend/src/charts.tsx` | Baru | Grafik SVG tanpa pustaka tambahan, dimuat secara lazy (chunk terpisah): donat, bar bertumpuk, garis per jam, linimasa, corong, dan bar per jenis. Setiap grafik punya label teks, teks alternatif, dan tabel tersembunyi. |
| `frontend/src/chartData.ts` | Baru | Data grafik dari API: status tinjauan kasus, status siswa, linimasa WIB, corong tinjauan, kasus per jenis, kehadiran, hasil indikasi. |
| `frontend/src/sessions.ts` | Baru | Filter status Sesi Ujian, badge emas untuk "Sedang Berlangsung", tanggal WIB. |

### Rencana (belum dikerjakan)

- **Riwayat untuk sparkline "Sesi aktif" dan "Siswa sedang ujian".** API hanya mengirim nilai saat ini, jadi sparkline disembunyikan dan dasbor menampilkan angkanya saja. Bila diperlukan, rencananya: cuplikan berkala di backend (misalnya setiap menit) dan endpoint `GET /api/dashboard/history?hours=8` → `[{ts, active_sessions, students_online}]`. Ini butuh penyimpanan baru, karena tabel `presence` hanya menyimpan waktu terakhir siswa terlihat.
- **"Periode tidak terbaca" per siswa di Laporan Sesi.** `GET /api/sessions/{id}/report` hanya mengirim jumlah periode (`indications.cannot_analyze`) dan durasinya, tanpa rincian per siswa. Karena itu donat Kehadiran hanya berisi Hadir dan Tidak hadir, dan periode tidak terbaca ditampilkan sebagai angka terpisah. Agar bisa menjadi bagian donat (dalam satuan siswa), laporan perlu kolom tambahan, misalnya `attendance.unreadable_students` (jumlah siswa hadir yang punya minimal satu periode tidak terbaca).
- **Linimasa Monitoring** mengambil indikasi lewat `GET /api/exams/{id}/events`, maksimal 500 per permintaan. Bila batas itu tercapai, halaman memberi tahu bahwa yang tampil 500 indikasi terbaru.

## Beranda: foto lokal dan ukuran mengikuti situs University of Edinburgh

- Kartu Beranda dan bagian "Visi kami" memakai foto Unsplash yang sama dengan desain Figma. Foto disimpan lokal sebagai WebP di `frontend/public/images/beranda/` (sumber dan fotografer di `CREDITS.md`). Aplikasi tidak memuat gambar dari internet.
- Ukuran dan proporsi Beranda diukur dari https://local.ed.ac.uk/ dan diterapkan ke EduAI: tinggi menu dan header, font menu dan judul, padding kiri-kanan, dan jarak. Kartu foto kemudian diubah menjadi 3 kolom (sekitar 307 px, jarak 20 px, foto 16:9, judul 18 px, deskripsi 12 px, Kabar terbaru di sel keenam) dalam container maks 960 px; "Yang diperhatikan AI" memakai container dan grid yang sama. Warna, font, dan isi tetap milik EduAI. Tabel ukuran dan perbedaan yang disengaja ada di [beranda-ukuran.md](beranda-ukuran.md).
- Struktur lebar penuh: bilah menu navy (di HP menjadi tombol Menu), header putih dengan lambang dan tombol Masuk, banner kolase webcam tim EduAI (`banner_indikasi.webp`, utuh tanpa dipotong), pita judul "VISI KAMI", lalu kartu foto, "Yang diperhatikan AI", Kabar terbaru, dan footer. Latar setiap bilah selebar layar; isinya maks 1440 px dengan padding 32 px (16 px di HP). Kelas `.bd-band`.

## Logo

- Logo aplikasi diganti dengan logo "Smart Exam Integrity" (`frontend/public/brand/smart-exam-integrity.webp`, 512 × 512 px, latar di luar lingkaran transparan), dipakai di Beranda, Login, sidebar, dan header siswa. Berkas logo lama (`eduai-seal.*`) tetap ada. Favicon belum diganti.
- Sidebar sebelumnya menunjuk ke `/brand/MontserratSemiBold.png` yang tidak ada (gambar rusak); sekarang memakai logo baru.

## Sidebar ikon

- Sidebar semua peran menjadi kolom ikon putih 72 px (border kanan #E2E5EA). Logo di atas membuka Beranda (sesi tetap aktif). Menu aktif memakai ikon terisi + `aria-current="page"`; menu lain ikon garis. Tooltip nama menu saat kursor atau fokus keyboard; mulai 1280 px sidebar melebar ke 240 px saat kursor di atasnya (atau saat fokus keyboard) dan menampilkan nama menu.
- Daftar menu per peran tidak berubah (`frontend/src/nav.ts`). "Profil" pindah ke avatar di bawah; ikon ≡ membuka "Lainnya" (Pengaturan, Keluar).
- Badge merah pada "Indikasi" = jumlah kasus belum ditinjau (dari `/api/cases`, sama dengan halaman Indikasi); tersembunyi bila 0. Pihak sekolah tidak mendapat badge karena hanya melihat kasus yang sudah ditinjau.
- Di bawah 768 px: bilah navigasi bawah dengan 4 menu pertama + "Lainnya" (menu sisanya, Profil, Pengaturan, Keluar).

## Panel notifikasi dan penampil bukti bergaya story

- Lonceng membuka panel kanan (400 px, layar penuh di HP): filter, kelompok waktu WIB, satu baris per siswa dan ujian, tombol Tinjau/Abaikan. Kode: `frontend/src/NotifPanel.tsx`, logika `frontend/src/notifikasi.ts`.
- Foto siswa bercincin emas bila ada bukti yang boleh dibuka (pengawas ujian itu dan admin), abu bila sudah dilihat. Penampil story memutar cuplikan gambar yang sudah disimpan backend (4 detik per gambar), tanpa video/audio dan tanpa perekaman baru. Membuka bukti tetap lewat `GET /api/evidence/{id}` yang membatasi peran dan mencatat log audit.
- Keputusan pengawas dari penampil memakai `POST /api/cases/{id}/reviews` yang sudah ada. "Salin tautan kasus" membuat tautan `?kasus=<id>` yang membuka halaman Indikasi dengan kasus itu.
- Status dibaca, diabaikan, dan bukti sudah dilihat kini disimpan di server per akun (lihat bagian berikut); penyimpanan di browser dihapus. Foto siswa tidak ada di API (ditunda), jadi baris memakai inisial.

## Status notifikasi di server, case_id di log audit

- Tabel baru di DB: lihat "Perubahan DB: tabel notification_marks" di bawah.
- Endpoint `GET /api/notifications/state`, `PUT /api/notifications/{case_id}/read`, `PUT`/`DELETE /api/notifications/{case_id}/dismiss`. Hanya pengawas ujian itu dan admin; peran lain 403.
- Cincin abu (bukti sudah dilihat) diambil dari baris audit "Melihat evidence" milik pengguna itu sendiri.
- Target audit "Melihat evidence" kini menyertakan `case:{case_id}`. Baris "Akses gambar bukti ditolak" tidak diubah.
- Panel: titik biru dan tombol Abaikan hanya untuk pengawas ujian dan admin; baris "tidak dapat dianalisis" bukan kasus, jadi tanpa titik biru dan tanpa Abaikan. Kunci lama di localStorage dihapus saat panel dimuat.
- Tes: `backend/tests/test_notifications.py` (dibaca/diabaikan per akun, reset oleh kejadian baru, cincin dari audit sendiri, akses per peran).

## Halaman Indikasi langkah 2

- Baris 3 "Aktivitas terbaru": keputusan tinjauan terakhir per kasus (pengulas, kasus, status baru, waktu), bisa digulir, tombol perbesar. Sumber: `last_review` di `GET /api/events` (500 deteksi terbaru); riwayat keputusan sebelumnya per kejadian tidak ikut.
- Baris 4 "Indikasi per jenis" (batang SVG, bisa dengan keyboard, batang terpilih emas, sinkron dengan tombol jenis) dan "Jenis indikasi" (tabel distribusi).
- Baris 5 "Beban pengawas" (kasus per pengawas ujian, dari `GET /api/exams`) dan "Progres tinjauan per ujian".
- Drawer kanan (layar penuh di HP) muncul saat tombol jenis, batang, nama jenis, atau bagian donat diklik: siswa, ujian, waktu WIB, jumlah kejadian, status. Cuplikan bukti dimuat hanya saat tombol "Tampilkan cuplikan" diklik, karena setiap pembukaan bukti tercatat di log audit. Klik siswa membuka tinjauan kasus yang sudah ada.
- Panel tinjauan kasus (di samping daftar kasus) juga tidak lagi memuat cuplikan bukti otomatis saat kasus dipilih: placeholder abu + tombol "Tampilkan cuplikan". Memilih kasus atau mengklik grafik tidak menambah baris audit dan tidak mengubah cincin notifikasi; satu klik "Tampilkan cuplikan" (atau satu bukti di story) = tepat satu baris audit.
- Kode: `frontend/src/IndikasiDetail.tsx`, logika di `frontend/src/indikasi.ts`, hook bersama di `frontend/src/hooks.ts`.


## Perubahan DB: tabel `notification_marks`

Tabel ini sudah terbuat di DB asli (`backend/data/eduai.sqlite3`) saat backend dijalankan pada 5 Nov 2026. Tabel lain tidak diubah, tidak ada kolom yang ditambah, dan tidak ada data yang dihapus.

| Kolom | Tipe | Isi |
|---|---|---|
| `user_id` | INTEGER, NOT NULL, `REFERENCES users(id)` | Akun pengawas/admin pemilik status |
| `case_id` | TEXT, NOT NULL | ID kasus (`c-` + event_id kejadian pertama) |
| `kind` | TEXT, NOT NULL, `CHECK (kind IN ('read','dismissed'))` | `read` = sudah dibaca, `dismissed` = diabaikan |
| `mark` | TEXT, NOT NULL | Aktivitas kasus saat ditandai: `jumlah_kejadian:event_id_terakhir`. Bila kasus mendapat kejadian baru, nilainya tidak cocok lagi, jadi kasus kembali belum dibaca dan tidak diabaikan |
| `updated_at` | TEXT, NOT NULL | Waktu UTC (ISO) penandaan terakhir |

Kunci utama: `(user_id, case_id, kind)`. Tidak ada indeks tambahan.

**Kapan dibuat:** otomatis setiap kali backend mulai (`Database.__init__` menjalankan `SCHEMA` di `backend/app/db.py` dengan `CREATE TABLE IF NOT EXISTS`). Bila tabel sudah ada, tidak terjadi apa-apa. Tidak ada migrasi lain.

**Cadangkan DB sebelum memperbarui** (contoh PowerShell, dari folder proyek). DB memakai mode WAL, jadi salin ketiga berkas (`.sqlite3`, `-wal`, `-shm`) **setelah backend dihentikan**:

```powershell
# 1. Hentikan backend (Ctrl+C di terminal uvicorn), lalu:
$tgl = Get-Date -Format "yyyy-MM-dd_HHmm"
$tujuan = "backend\data\backups\$tgl"
New-Item -ItemType Directory -Force $tujuan | Out-Null
Copy-Item backend\data\eduai.sqlite3* $tujuan
Get-ChildItem $tujuan          # periksa: eduai.sqlite3, eduai.sqlite3-wal, eduai.sqlite3-shm
```

Bila backend tidak bisa dihentikan, pakai salinan konsisten bawaan SQLite (aman saat backend berjalan):

```powershell
$tgl = Get-Date -Format "yyyy-MM-dd_HHmm"
New-Item -ItemType Directory -Force "backend\data\backups\$tgl" | Out-Null
.venv\Scripts\python.exe -c "import sqlite3,sys; s=sqlite3.connect('backend/data/eduai.sqlite3'); d=sqlite3.connect(sys.argv[1]); s.backup(d); d.close(); s.close()" "backend\data\backups\$tgl\eduai.sqlite3"
```

Folder evidence (`backend/data/evidence`, `backend/data/report-frames`) tidak ikut perubahan ini; cadangkan terpisah bila perlu. Untuk mengembalikan: hentikan backend, lalu salin berkas cadangan kembali ke `backend\data\`.

## Kamera atau mikrofon dimatikan siswa = indikasi

Keputusan produk 6 Nov 2026: bila siswa mematikan kamera atau mikrofon selama pemantauan AI berjalan, itu dicatat sebagai **indikasi** yang perlu ditinjau pengawas (menjadi kasus, notifikasi, dan masuk laporan), bukan lagi hanya masalah kualitas.

- Kode: `backend/app/device.py`, dipanggil dari `POST /api/exams/{id}/presence` (heartbeat siswa setiap 5 detik). Berlaku untuk semua sumber analisis (browser, Jitsi, OpenVidu). Sebelumnya, di mode browser kamera mati tidak tercatat sama sekali.
- Indikator baru: `CAMERA_OFF` ("Kamera dimatikan") dan `MIC_OFF` ("Mikrofon dimatikan"), kategori `indication`, sumber `presence`, tanpa gambar bukti (tidak ada yang bisa direkam), tanpa skor model.
- Aturan:
  - Hanya saat pemantauan aktif.
  - Perlu 2 heartbeat berturut-turut dalam keadaan mati (sekitar 5 detik), supaya gangguan sesaat tidak dicatat. Waktu mulai = heartbeat mati pertama.
  - `MIC_OFF` hanya bila siswa menyetujui pemakaian mikrofon (persetujuan suara). Tanpa persetujuan itu mikrofon memang tidak dibuka.
  - Kejadian ditutup saat perangkat menyala lagi, siswa keluar, siswa terputus (tanpa heartbeat 20 detik), atau pemantauan dihentikan.
  - Aturan kasus: 1 kejadian sudah memenuhi ambang (`cases.py`).
- Mode Jitsi: kamera mati tetap juga dicatat "tidak dapat dianalisis" seperti sebelumnya.
- Frontend: jenis "Kamera dimatikan" dan "Mikrofon dimatikan" di halaman Indikasi (tombol, grafik, tabel), filter notifikasi "Kamera/mikrofon mati", dan baris "Kamera/mikrofon dimatikan" di grafik Monitoring (hanya bila ada kasus).
- Tes: `backend/tests/test_device.py` (5 tes). Empat tes di `test_jitsi.py` yang mengunci aturan lama ("kamera mati bukan indikasi") disesuaikan: jalur AI tetap sama, ditambah pemeriksaan indikasi `CAMERA_OFF`.
- Perbaikan tata letak: panel kasus di halaman Indikasi tidak lagi melebar di HP bila alasan kejadian panjang.

## Status ujian otomatis mengikuti jadwal

- Kode: `backend/app/exam_status.py`. Dijalankan saat backend mulai, setiap 30 detik di loop pemeliharaan (`app/main.py`), dan setiap kali daftar atau detail ujian dibuka (`GET /api/exams`, `GET /api/exams/{id}`).
- Aturan (waktu dibaca di `EDUAI_TIMEZONE`, mis. Asia/Jakarta):
  - sebelum jam mulai: **Terjadwal**;
  - antara mulai dan mulai + durasi: **Sedang Berlangsung**;
  - setelah itu: **Selesai** (`finished_at` diisi jam selesai terjadwal bila belum ada).
- Hanya **maju** (Terjadwal → Sedang Berlangsung → Selesai), tidak pernah mundur: ujian yang dimulai lebih awal atau diakhiri lebih awal secara manual tetap pada status itu. **Draft** tidak pernah diubah.
- Ujian yang menjadi Selesai: pemantauan AI dihentikan oleh loop pemeliharaan; ringkasan akhir dibuat dengan aturan ringkasan yang sudah ada.
- Setiap perubahan otomatis dicatat di log audit oleh "Sistem": "Status ujian otomatis menjadi … (sesuai jadwal)".
- Tes: `backend/tests/test_exam_status.py` (4 tes).

## Profil dan Manajemen User bisa disimpan

- **Pengaturan > Profil (semua peran):** nama lengkap bisa diubah dan disimpan lewat `PATCH /api/auth/me` (hanya akun sendiri, hanya nama). Email, institusi, dan peran hanya-baca dengan keterangan siapa yang mengaturnya. Dicatat di audit "Mengubah nama profil". Tes: `backend/tests/test_profile.py`.
- **Manajemen User (admin):** kolom Aksi dengan tombol "Ubah" membuka dialog untuk nama, email, peran, status (aktif/nonaktif), serta NIS dan kelas untuk siswa. Endpoint `PATCH /api/users/{id}` (hanya admin). Pengaman:
  - email harus unik dan berformat benar (huruf kecil);
  - admin tidak bisa mengubah peran atau menonaktifkan akunnya sendiri;
  - harus selalu ada minimal satu admin aktif;
  - peran tidak bisa diubah selama akun masih menjadi pengawas atau peserta di ujian yang belum selesai;
  - akun yang dinonaktifkan langsung keluar (token ditolak);
  - setiap perubahan dicatat di audit "Mengubah data pengguna (field yang berubah)".
  Tes: `backend/tests/test_user_admin.py`. "Tambah User" dan ganti kata sandi masih belum tersedia.
- **Pihak Sekolah > Akun Siswa (menu baru):** daftar akun siswa saja (kolom Nama, Email, NIS/NISN, Kelas, Status) dengan aksi "Ubah" untuk nama, email, NIS, kelas, dan status. Peran tidak bisa diubah dan akun staf tidak bisa disentuh (backend: `GET /api/users` untuk peran sekolah selalu `role=siswa`; `PATCH /api/users/{id}` menolak 403 bila targetnya bukan siswa atau peran diubah). Matriks "Role & Izin" ikut diperbarui.
- **Manajemen User > Tambah User (admin):** dialog yang menyesuaikan peran. Siswa: wajib NIS/NISN dan kelas; pengawas, penyelenggara, pihak sekolah: tanpa NIS/kelas; admin: wajib centang konfirmasi akses penuh. Kata sandi awal minimal 8 karakter (bisa "Buat acak"), tidak dicatat di log. Endpoint `POST /api/users` (hanya admin; 409 bila email dipakai, 422 bila isian tidak sesuai peran). Audit "Menambah pengguna (Peran)". Dialog "Tambah Pengawas" milik penyelenggara masih contoh.
- **Indikasi:** klik tombol jenis di baris filter langsung menyaring dan menggulir ke "Daftar kasus" ("Tidak dapat dianalisis" ke kartunya). Batang grafik, nama jenis, dan donat tetap membuka drawer siswa.
- **Laporan Sesi:** grafik "Linimasa indikasi" dihapus (semua peran). Linimasa di Monitoring tetap ada.

## Indikasi buku lebih cepat: gambar dan suara kertas

Permintaan 10 Nov 2026: buku yang dipegang atau dibuka harus cepat terindikasi, juga dari suara buku.

- **Dari gambar (BOOK_VISIBLE, `ai/eduai-ai/config.yaml`):** skor minimal 0,5 → **0,35**, harus terlihat 3 → **1,5 detik**, jeda antar-episode 60 → 30 detik. Notifikasi ke pengawas sejak **episode pertama** (dulu 3 episode per jam). Nilai belum divalidasi: kemungkinan salah deteksi lebih besar, dan setiap indikasi tetap ditinjau pengawas.
- **Dari suara (indikator baru BOOK_SOUND, "Suara kertas/halaman buku terdengar"):** browser siswa kini menghitung skor `paper` dari kelas YAMNet *Rustle*, *Crumpling, crinkling*, *Tearing*, dan *Flap* (nama dicek di daftar label model). Skor ≥ 0,25 selama ≥ 1 detik menjadi indikasi; jeda 30 detik; notifikasi sejak episode pertama. Hanya bila siswa menyetujui analisis suara. Tetap hanya angka: audio tidak direkam atau dikirim.
- Jalur data: `frontend/src/audioScores.ts` → `POST /api/exams/{id}/audio` (`paper`, opsional untuk browser lama) → `eduai_ai.temporal` (aturan BOOK_SOUND) → event dengan `details.sound_type = "KERTAS_BUKU"` dan `details.paper`. Di halaman Indikasi, BOOK_SOUND masuk jenis **Buku**.
- Tes: `ai/eduai-ai/tests/test_book.py`, `test_sound_labels.py` (bunyi kertas), `backend/tests/test_audio.py` (2 tes baru), `frontend/tests/audioScores.test.ts`.
