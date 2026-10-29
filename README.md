# EduAI — sistem indikasi kecurangan ujian online (terintegrasi)

Web app siswa & pengawas (React) + backend (FastAPI) + modul AI (MediaPipe) + OpenVidu 3 (opsional).
AI **hanya memberi indikasi** untuk ditinjau pengawas; video yang tidak dapat dianalisis dicatat terpisah dan tidak pernah dihitung sebagai indikasi.

| Dokumen | Isi |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Komponen, **alur frame ke AI** (2 jalur), dari frame ke kejadian |
| [docs/API.md](docs/API.md) | Endpoint, autentikasi, galat, contoh request/response, contoh JSON kejadian |
| [docs/MODELS.md](docs/MODELS.md) | Pemilihan model dan status masing-masing |
| [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) | Hasil uji: lulus / gagal / tidak dijalankan |
| [docs/CHANGES.md](docs/CHANGES.md) | Berkas yang dibuat, diubah, dihapus, dan alasannya |

## Status singkat (jujur)

| Bagian | Status |
|---|---|
| Login, peran, ujian, persetujuan, cek perangkat, ruang ujian, dasbor pengawas, indikasi, evidence, validasi, laporan, audit | Tersambung ke backend nyata dan diuji |
| Jalur frame **browser → backend → AI → dasbor + pop-up** | **Diuji end-to-end** (Chromium + kamera palsu, model BlazeFace nyata) |
| Deteksi wajah (BlazeFace) | Diuji dengan inferensi nyata |
| Arah kepala (Face Landmarker), ponsel (EfficientDet-Lite0) | Kode siap, **belum diuji** dengan model nyata (berkas tidak dapat diunduh di lingkungan pengembangan) |
| OpenVidu: video langsung ke pengawas & worker AI di ruang | **Diuji end-to-end dengan server LiveKit 1.9.1 (media server OpenVidu 3) di Linux**: siswa publish, pengawas melihat video LIVE, worker menerima frame → indikasi + evidence → dasbor, berhenti bersih (juga bila worker dimatikan paksa). **Paket Docker OpenVidu dan Windows belum diuji.** |
| Analisis suara (opsional, `OTHER_VOICE`) | YAMNet berjalan di browser siswa (hanya skor dikirim, tidak ada audio); diuji E2E dengan mikrofon palsu Chromium. **Belum diuji dengan mikrofon & wajah sungguhan; ambang sementara.** |
| Pengelompokan kasus & notifikasi | Indikasi berulang digabung per kasus (jeda ≤120 dtk), pop-up hanya untuk kasus baru; diuji |
| Kapasitas banyak siswa | **Belum diuji beban** — tidak ada klaim jumlah siswa |
| Ambang aturan AI | Sementara (`0.2-provisional`), belum dikalibrasi pada data sekolah |
| Windows | Langkah di bawah belum dijalankan di Windows oleh pengembang; dilaporkan bila ada kendala |

## Prasyarat (Windows 10/11 + VS Code)

1. **Python 3.11 atau 3.12, 64-bit** — https://www.python.org/downloads/ (centang *Add python.exe to PATH*). Hindari 3.13 di Windows sampai wheel MediaPipe/LiveKit untuk versi itu dipastikan tersedia.
2. **Node.js 22.12+ LTS** — https://nodejs.org/
3. **VS Code** + ekstensi *Python* (Microsoft).
4. (Opsional, untuk OpenVidu) **Docker Desktop** dan **Git**.
5. Webcam. Browser Chrome/Edge versi terbaru.

## 1. Siapkan proyek

Ekstrak ZIP ke folder tanpa spasi, misalnya `C:\EduAI`, lalu di VS Code: **File → Open Folder → C:\EduAI**. Buka terminal (**Terminal → New Terminal**, PowerShell).

```powershell
cd C:\EduAI
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```
Jika muncul galat *running scripts is disabled*: jalankan `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, lalu ulangi baris terakhir. Di VS Code pilih interpreter `.venv` (**Ctrl+Shift+P → Python: Select Interpreter**).

## 2. Pasang backend + modul AI

```powershell
cd C:\EduAI\backend
python -m pip install --upgrade pip
pip install -r requirements.txt
```
`requirements.txt` juga memasang modul AI dari `..\ai\eduai-ai` (MediaPipe, OpenCV, LiveKit Python SDK, cryptography).

## 3. Unduh model

```powershell
cd C:\EduAI\ai\eduai-ai
powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1
pip install scikit-image            # opsional: gambar contoh untuk smoke test & tes model
python scripts\smoke_test_models.py
```
Hasil yang diharapkan: `face_detector: loaded: true`, dan pada gambar contoh `face_count: 1`. Skrip juga mengunduh `yamnet.tflite` (analisis suara di browser; disajikan backend di `/api/ai/models/yamnet.tflite`). Tanpa berkas ini analisis suara nonaktif dengan pesan yang jelas; fitur lain tetap berjalan. Jika jaringan memblokir `storage.googleapis.com`, pakai `python scripts\download_models.py --from-mediapipe-wheel` (hanya detektor wajah; lihat [docs/MODELS.md](docs/MODELS.md)).

## 4. Konfigurasi backend

```powershell
cd C:\EduAI\backend
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"     # salin ke EDUAI_JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(32))"     # salin ke EDUAI_AI_SERVICE_KEY
```
Buka `backend\.env` di VS Code dan isi kedua nilai tersebut. Nilai lain boleh dibiarkan default untuk uji lokal. Opsional, enkripsi evidence: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` → `EDUAI_EVIDENCE_KEY`.

`EDUAI_SEED_DEMO=true` membuat akun demo (kata sandi `123456`): `siswa1`–`siswa6`, `pengawas1`, `pengawas2`, `penyelenggara1`, `admin1`, `sekolah1` (semua `@gmail.com`) dan tiga ujian contoh; "Ujian Akhir Matematika XI" berstatus *Sedang Berlangsung* hari ini. **Matikan (`false`) dan ganti kata sandi untuk penggunaan nyata.** Seed tidak pernah membuat kejadian AI.

## 5. Jalankan

Terminal 1 — backend:
```powershell
cd C:\EduAI\backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```
Cek: http://localhost:8000/api/health → `"ai": {"available": true}`. Dokumentasi API interaktif: http://localhost:8000/docs.

Terminal 2 — frontend:
```powershell
cd C:\EduAI\frontend
npm install
npm run dev
```
`npm install`/`npm run dev` otomatis menyalin berkas WASM MediaPipe Audio ke `public/mediapipe-audio` (skrip `scripts/copy-mediapipe-wasm.mjs`; folder ini tidak perlu di-commit).

Buka http://localhost:5173. Vite meneruskan `/api` ke backend, jadi tidak perlu pengaturan CORS saat pengembangan.

## 6. Uji satu peserta (disarankan pertama)

1. **Tab 1** — login `pengawas1@gmail.com` → menu **Monitoring** → klik **Mulai AI**.
2. **Tab 2** (tab baru di browser yang sama boleh; sesi disimpan per tab) — login `siswa1@gmail.com` → **Cek perangkat & masuk** → izinkan kamera → **Lanjut ke Persetujuan** → centang → **Setuju & Masuk Ujian**.
3. Duduk menghadap kamera ±10 detik, lalu geser keluar dari bingkai kamera (ruangan tetap terang) lebih dari 5 detik. Jangan menutup kamera dengan tangan: gambar menjadi gelap dan hasilnya "Tidak dapat dianalisis", bukan indikasi.
4. Di Tab 1 muncul pop-up **Indikasi baru**; ubin siswa berwarna kuning. Klik **Tinjau** → cuplikan evidence tampil (tersimpan ±5 detik setelah indikasi terbuka) → pilih keputusan → **Simpan Validasi**.
5. Ruangan gelap atau kamera sangat buram menghasilkan status **Tidak dapat dianalisis**, bukan indikasi.

## 7. OpenVidu (opsional: video langsung ke pengawas + worker AI di ruang)

Tanpa OpenVidu semua fitur di atas tetap berjalan (jalur frame browser); hanya video langsung di dasbor yang tidak tampil.

```powershell
cd C:\
git clone https://github.com/OpenVidu/openvidu-local-deployment -b 3.9.0
cd openvidu-local-deployment\community
.\configure_lan_private_ip_windows.bat
docker compose up
```
Tunggu sampai semua kontainer berjalan. Bawaan local deployment: URL `ws://localhost:7880`, API key `devkey`, secret `secret` (hanya untuk pengembangan lokal). Lalu di `backend\.env`:

```
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
EDUAI_ANALYSIS_SOURCE=livekit
EDUAI_AI_SERVICE_KEY=<sudah diisi di langkah 4>
EDUAI_BACKEND_URL=http://localhost:8000
```
Mulai ulang backend. Sekarang:
- Siswa mem-publish kamera & mikrofon ke ruang `eduai-exam-<id>` (token: publish saja, tidak bisa melihat siswa lain).
- Pengawas berlangganan video (token: subscribe saja); ubin menampilkan **LIVE**.
- **Mulai AI** menjalankan `python -m eduai_ai.livekit_worker` yang bergabung sebagai peserta tersembunyi dan membaca frame kamera siswa. Bila worker gagal berjalan, backend otomatis memakai frame browser; bila worker berjalan tetapi tidak mengirim heartbeat, dasbor menampilkan peringatan dan tombol **Pakai frame dari browser**.
- Bila browser siswa tidak dapat terhubung ke OpenVidu, frame kamera siswa itu otomatis dikirim lewat jalur browser sehingga tetap dianalisis (backend menerimanya selama worker tidak melaporkan siswa tersebut dalam 10 dtk terakhir).
- **Hentikan AI**: backend meminta worker berhenti dengan sopan (POSIX: SIGTERM; Windows: CTRL_BREAK ke grup proses worker), menunggu ≤10 dtk, lalu mematikan paksa. Kejadian yang masih terbuka ditutup oleh backend dengan catatan "(pemantauan dihentikan)"; saat backend dimulai ulang dicatat "(backend dimulai ulang)".
- Worker juga berhenti sendiri bila heartbeat dijawab `stop` (pemantauan dihentikan atau worker sudah diganti, mis. setelah backend dimulai ulang) atau bila backend tidak terjangkau 12 heartbeat berturut-turut (±1 menit). Ini mencegah worker yatim.

Langkah verifikasi OpenVidu ada di [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md#langkah-verifikasi-openvidu-untuk-tim-paket-openvidu--windows). Catatan: browser hanya mengizinkan kamera di `https://` atau `http://localhost`; untuk perangkat lain di jaringan sekolah diperlukan HTTPS (reverse proxy dengan sertifikat) baik untuk frontend maupun OpenVidu.

## 8. Menjalankan tes

```powershell
cd C:\EduAI\ai\eduai-ai ; python -m pytest -q          # 51 tes (beberapa butuh model + scikit-image)
cd C:\EduAI\backend     ; python -m pytest -q          # 50 tes
cd C:\EduAI\frontend    ; npx tsc --noEmit ; npm run build
node --experimental-strip-types tests\notify.test.ts ; node --experimental-strip-types tests\audioScores.test.ts
```
E2E browser (butuh `pip install playwright` dan `python -m playwright install chromium`; backend & frontend berjalan dengan basis data baru):
```powershell
python tests\e2e\make_fake_camera.py fake.y4m
python tests\e2e\e2e_browser_flow.py --y4m fake.y4m --out e2e-screenshots
```
E2E worker OpenVidu (butuh server OpenVidu/LiveKit berjalan, backend dengan `EDUAI_ANALYSIS_SOURCE=livekit` dan basis data baru, frontend berjalan; mode `kill` butuh `pip install psutil`):
```powershell
python tests\e2e\e2e_livekit_worker.py --y4m fake.y4m --mode stop
python tests\e2e\e2e_livekit_worker.py --y4m fake.y4m --mode kill
```

## CPU / GPU dan kinerja

- Semua inferensi berjalan di **CPU** (MediaPipe TFLite + XNNPACK). Tidak ada kode GPU; GPU tidak diperlukan.
- Terukur di mesin pengembangan (2 vCPU, BlazeFace saja): median 5 ms per frame per siswa. Face Landmarker dan EfficientDet akan menambah waktu; ukur ulang setelah model dipasang (`run_webcam.py` mencetak latensi).
- Pengaman beban: ≤1 frame berjalan per siswa (frame berikut dibuang, tidak diantrikan), batas analisis paralel `EDUAI_AI_MAX_CONCURRENT`, ukuran frame maks. `EDUAI_FRAME_MAX_BYTES`, frame dikecilkan di browser (lebar ≤ 640). Worker OpenVidu memakai `VideoStream(capacity=2)`.
- **Belum ada uji beban.** Sebelum ujian dengan banyak siswa, uji bertahap (1 → 5 → 10 → kelas penuh) dan pantau `GET /api/ai/health` (`frames_dropped_busy`) serta CPU server.

## Privasi & keamanan (ringkas)

- Rahasia (JWT secret, LiveKit secret, kunci layanan AI, kunci evidence) hanya di `backend\.env`; frontend hanya menerima token sesi miliknya dan token ruang berumur pendek.
- Token tidak dikirim lewat URL dan tidak dicatat di log; frame tidak pernah ditulis ke log.
- Tidak ada penyimpanan video penuh atau audio. Analisis suara (bila siswa menyetujui secara terpisah) berjalan di browser siswa; yang dikirim hanya tiga skor (ucapan/bisikan/musik) per ±1 dtk. Evidence = maks. 12 cuplikan JPEG kecil per indikasi, ID acak, opsional terenkripsi, dihapus otomatis setelah 24 jam (`EDUAI_EVIDENCE_RETENTION_HOURS`), akses hanya lewat endpoint berautentikasi dan tercatat di audit log.
- Siswa tidak pernah dapat membaca status AI, indikasi, atau evidence. Pihak sekolah hanya melihat indikasi yang sudah divalidasi.

## Langkah manual yang masih diperlukan

1. Isi `backend\.env` (JWT secret, kunci layanan) dan unduh model di setiap komputer/server.
2. Unduh dan uji `face_landmarker.task` serta `efficientdet_lite0.tflite` (`smoke_test_models.py`), lalu uji ulang indikator kepala & ponsel dengan webcam sungguhan.
3. Jalankan paket OpenVidu (bagian 7) di Windows dan jalankan `tests\e2e\e2e_livekit_worker.py` (mode `stop` dan `kill`); catat hasilnya. Jalur ini sudah lulus dengan server LiveKit di Linux, tetapi jalur Windows (CTRL_BREAK) dan paket Docker OpenVidu belum.
4. Uji analisis suara dengan mikrofon dan wajah sungguhan (orang lain berbicara saat mulut siswa diam) sebelum memakai indikator `OTHER_VOICE`.
5. Kalibrasi ambang dengan video pilot berlabel (dengan persetujuan) memakai `run_webcam.py` + `evaluate.py`.
6. Untuk produksi: HTTPS, `EDUAI_SEED_DEMO=false`, akun nyata, PostgreSQL bila lebih dari satu proses backend, kebijakan retensi data teks (indikasi/validasi) dari sekolah, dan uji beban.
7. Fitur UI yang belum tersambung backend (diberi label "Data contoh" atau tombol nonaktif): simpan pengaturan profil/notifikasi, tambah user dari UI, edit/hapus ujian, status laporan final.
