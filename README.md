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
| Analisis suara (opsional, `OTHER_VOICE`) | YAMNet berjalan di browser siswa (hanya skor dikirim, tidak ada audio), pada sumber **Browser dan Jitsi**. Diuji E2E dengan mikrofon palsu Chromium (sumber Jitsi: suara TTS Windows). **Belum diuji dengan mikrofon & wajah sungguhan; ambang sementara.** **Mode worker OpenVidu: belum ada analisis suara**, karena relay skor ke worker dari paket `EduAI-arsitektur-AI.zip` belum diport. |
| Jenis suara | Setiap kejadian suara diberi label dari skor YAMNet dan gerak mulut: MUSIK/MEDIA (info), BISIKAN (indikasi), BICARA_MULUT_DIAM (`OTHER_VOICE`, indikasi), BICARA_SISWA (selalu info). Skor speech/whisper/media tampil di Detail Evidence dan laporan. Semua ambang dan kategori ada di `config.yaml`, **belum dikalibrasi**. **Tidak ada pengenalan suara orang dan tidak ada penghitungan jumlah pembicara** (alasannya di `docs/API.md`). Diuji E2E dengan rekaman musik sintetis, suara TTS, dan wajah dengan mulut yang digambar membuka-menutup. **Belum diuji dengan suara dan wajah sungguhan.** "Whispering" YAMNet bernilai 0 pada bisikan sintetis, jadi BISIKAN baru teruji di tingkat aturan. |
| Buku (`BOOK_VISIBLE`) | Kelas COCO `book` dari EfficientDet-Lite0 yang sama dengan ponsel. Skor ≥0,5 selama ≥3 dtk; pop-up setelah 3 episode per jam; dapat dimatikan di `config.yaml`. Aturannya diuji dengan tes. **Belum divalidasi dengan buku di depan webcam**: COCO dilatih dengan buku di rak/meja, dan uji webcam pertama membaca buku sebagai ponsel (skor 64%). |
| Pengelompokan kasus & notifikasi | Indikasi berulang digabung per kasus (jeda ≤120 dtk), pop-up hanya untuk kasus baru; diuji |
| Rapat Video (Jitsi Meet, `lib-jitsi-meet`) | Halaman terpisah dari pemantauan ujian dan tidak punya jalur ke AI; diuji E2E di Windows dengan Chrome, dua pengguna, kamera palsu, dan server uji publik. **Belum diuji dengan kamera sungguhan atau server Jitsi sendiri.** |
| Mode ujian Jitsi | Sumber analisis `jitsi`: frame masuk ke endpoint dan pipeline yang sama dengan kamera browser. Diuji dengan tes backend dan di Chrome memakai **Jitsi tiruan**. **Belum pernah dijalankan dengan server Jitsi sungguhan.** |
| Laporan Sesi | Ringkasan, validasi di tabel, gambar bukti, finalisasi, PDF sesuai template, dan Excel tersambung ke backend; diuji otomatis dan di Chrome dengan data uji (gambar sintetis). **Belum diuji dengan data ujian sungguhan.** Tabel kosong sampai ada kejadian AI, karena seed demo tidak membuat kejadian. |
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

Opsional, kop surat PDF laporan: `EDUAI_SCHOOL_NAME`, `EDUAI_SCHOOL_ADDRESS`, `EDUAI_SCHOOL_PHONE`, `EDUAI_SCHOOL_EMAIL`, `EDUAI_SCHOOL_CITY`. Bila kosong, PDF menampilkan isian template. Nomor surat, NIP, jalannya ujian, dan tindak lanjut diisi tangan.

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

## 7a. Sumber analisis

Pengawas memilih sumber saat menekan **Mulai AI** di halaman Monitoring. Pilihan disimpan di server (`exams.analysis_source`), jadi siswa tidak dapat menentukannya. Monitoring menampilkan sumber yang aktif, dan status, kejadian, serta evidence mencatat sumbernya.

| Di layar | Nilai di data | Asal frame | Syarat |
|---|---|---|---|
| Browser | `browser` | Kamera siswa ke `POST /api/exams/{id}/frames` | Tidak ada |
| OpenVidu | `livekit` | Worker AI di ruang OpenVidu | `LIVEKIT_*` |
| Jitsi | `jitsi` | Kamera siswa ke endpoint yang sama dengan Browser | `EDUAI_JITSI_DOMAIN` |

Tombol **Mulai Pemantauan Ujian** di Ruang Tunggu Ujian memakai sumber bawaan `EDUAI_ANALYSIS_SOURCE`; pilihan sumber hanya ada di Monitoring. `EDUAI_ANALYSIS_SOURCE` hanya menerima `browser` atau `livekit`; nilai lain, termasuk `jitsi`, dibaca sebagai `browser`. Mode Jitsi dipilih per ujian di Monitoring. Tombolnya menunjukkan sumber yang akan dikirim (misalnya **Mulai AI · Jitsi**). Bila sumber yang dipakai server berbeda dari pilihan, Monitoring menampilkan peringatan.

**Satu siaran, yaitu yang dianalisis AI.** Halaman ruang ujian membuka kamera satu kali. Track itu dipakai untuk pratinjau siswa, frame AI, dan siaran ke pengawas, sehingga evidence berasal dari kamera yang sama dengan yang ditonton pengawas.

| Sumber AI | Siaran siswa | Video di Monitoring dan halaman pantau siswa |
|---|---|---|
| Jitsi (pemantauan aktif) | Hanya Jitsi; backend tidak memberi token OpenVidu (`monitoring.livekit = null`) | Hanya Jitsi; pengawas tidak membuka OpenVidu |
| OpenVidu, Browser, atau AI belum aktif | Hanya OpenVidu (bila `LIVEKIT_*` terisi); tidak ada ruang Jitsi | Hanya OpenVidu |

Token mengikuti `GET /session-state` (tiap 5 detik), jadi saat pengawas mengganti sumber, siaran siswa ikut berpindah tanpa masuk ulang. Kamera tetap hidup selama perpindahan.

## 7b. Jitsi Meet (Rapat Video dan mode ujian)

Tidak ada server Jitsi bawaan di kode. Untuk pengembangan, jalankan server lokal di `dev\jitsi\` (docker-jitsi-meet resmi; lihat `dev\jitsi\README.md`). Lalu isi `backend\.env` dan mulai ulang backend:

```
EDUAI_JITSI_DOMAIN=localhost:8443       # host[:port] web Jitsi; kosong = Rapat Video dan sumber Jitsi mati
EDUAI_JITSI_XMPP_DOMAIN=meet.jitsi      # domain XMPP; bawaan: domain tanpa port (server publik). docker-jitsi-meet: meet.jitsi
EDUAI_JITSI_MUC=muc.meet.jitsi          # bawaan conference.<domain XMPP>
EDUAI_JITSI_SERVICE_URL=                # bawaan wss://<domain>/xmpp-websocket
EDUAI_JITSI_APP_ID=eduai                # issuer/audience JWT yang diterima server
EDUAI_JITSI_APP_SECRET=                 # rahasia JWT yang sama dengan server Jitsi; kosong = tanpa token (server terbuka)
EDUAI_JITSI_OPERATOR=dev                # school HANYA jika server itu dikelola sekolah
```

Bila `EDUAI_JITSI_APP_SECRET` terisi, backend menandatangani token untuk setiap orang yang bergabung, dan server menolak siapa pun tanpa token yang sah. Setiap token hanya membuka satu ruang. Tanpa rahasia ini, server bersifat terbuka: siapa pun yang tahu nama ruang bisa bergabung.

**Pengecekan kesehatan.** `GET /api/jitsi/health` mengembalikan `not_configured`, `unreachable`, atau `ready` (diperiksa ke `https://<domain>/libs/lib-jitsi-meet.min.js`, batas waktu 2,5 detik, disimpan 15 detik). Di Rapat Video, admin melihat variabel yang kosong beserta contoh nilainya, atau alasan teknis server tidak terjangkau. Peran lain hanya melihat "Rapat Video belum tersedia. Hubungi admin."

**Mode ujian.** Bila pengawas memilih Jitsi, setiap siswa yang sudah memberi persetujuan masuk ke **ruangnya sendiri** (`eduai-exam-` + HMAC dari ujian dan siswa). Token siswa hanya membuka ruang itu, jadi siswa tidak pernah menerima video siswa lain. Server Jitsi menolak percobaan itu (`notAllowed`), dan ini sudah diuji dengan server nyata. Hanya video yang dikirim, tanpa audio. Ruang ujian memakai kamera yang sudah dibuka halaman (salinan track), jadi kamera tidak dibuka dua kali.

**Video langsung untuk pengawas.** Pengawas yang ditugaskan di ujian itu, dan admin, menerima video kamera siswa di Monitoring. Monitoring bergabung ke setiap ruang siswa tanpa kamera dan mikrofon, lewat `GET /api/exams/{id}/jitsi/watch`. Penyelenggara, pihak sekolah, siswa lain, dan pengawas ujian lain ditolak (403), dan penolakannya dicatat di audit. Video langsung **tidak direkam**: tidak ada Jibri, dan opsi rekaman, streaming, serta transkripsi dimatikan di server dan di token. Yang disimpan tetap hanya evidence sesuai aturan retensi. Analisis suara `OTHER_VOICE` nonaktif di mode ini.

**Bila ada gangguan:**

| Keadaan | Yang terjadi |
|---|---|
| Jitsi gagal atau terputus, kamera lokal hidup | Ujian dan analisis tetap jalan, karena frame langsung dikirim ke backend. Dicatat sebagai kejadian koneksi di presence dan linimasa, **bukan indikasi**. Siswa melihat pemberitahuan, pengawas melihat catatan di Monitoring, dan browser mencoba menyambung lagi tiap 30 detik. |
| Track mati atau kamera dimatikan | Status **Tidak dapat dianalisis**, bukan indikasi. |
| Frame berhenti masuk (browser tertutup, jaringan putus) | Status **Tidak dapat dianalisis** setelah ±8 detik. Tanpa heartbeat, pemeriksaan server berjalan tiap 30 detik. |

**Rapat Video** tersedia untuk semua peran dan terpisah dari ujian: tidak dianalisis AI, tidak direkam, dan tidak mengirim frame. Token rapat diminta lewat `POST /api/jitsi/meeting-token`, yang menolak nama ruang ujian. `frontend\tests\meetingIsolation.test.ts` menjaga bahwa halaman ini tidak punya jalur ke analisis.

**Batasan:**
- Sumber `jitsi` berlaku per ujian, bukan per siswa.
- Status koneksi dan kamera dilaporkan browser siswa; server hanya dapat memverifikasi apakah frame masih masuk.
- Monitoring membuka satu koneksi per siswa. Dengan banyak siswa, beban browser pengawas naik, dan ini belum diuji di atas 2 siswa.
- Pakai server Jitsi sendiri untuk siswa. Di server uji publik, video peserta melewati pihak ketiga dan ketersediaannya tidak dijamin.

**Troubleshooting:** lihat tabel di `dev\jitsi\README.md` (sertifikat belum diterima, `passwordRequired`, video hitam karena UDP 10000 atau `JVB_ADVERTISE_IPS`, `videobridgeNotAvailable`).

### Teks persetujuan siswa

**Status: perlu disetujui pihak sekolah sebelum dipakai ujian sungguhan.** Teks ada di `frontend\src\consent.ts`:

> Bukti berupa beberapa cuplikan gambar disimpan 24 jam, atau sampai laporan final dan paling lama 7 hari setelah ujian selesai; gambar pada laporan final dihapus 24 jam setelah finalisasi. Bukti hanya dapat dibuka oleh pengawas yang ditugaskan dan admin. Video penuh dan audio tidak pernah direkam atau disimpan.

Bila `EDUAI_JITSI_DOMAIN` terisi, ditambahkan satu kalimat: "Bila ujian memakai Jitsi, video kamera melewati server Jitsi yang dikelola sekolah." bila `EDUAI_JITSI_OPERATOR=school`; selain itu "...server Jitsi pihak ketiga (domain), bukan server milik sekolah." Kalimat "hanya dapat dibuka oleh pengawas yang ditugaskan dan admin" kini ditegakkan backend: `GET /api/evidence/...`, URL gambar laporan, dan gambar di PDF memakai satu pemeriksaan izin. Penyelenggara dan pihak sekolah tetap melihat laporan, status validasi, dan catatan, dengan keterangan "Gambar bukti hanya untuk pengawas dan admin". Percobaan yang ditolak dan pencabutan akses per peran dicatat di audit log tanpa mengubah baris lama. Domain tidak dapat membuktikan pemilik server, jadi `EDUAI_JITSI_OPERATOR` wajib diisi dengan benar. Masa simpan di teks ini tertulis tetap; bila pengaturan retensi diubah, ubah juga teksnya.

**Belum sesuai kode:** teks ini belum menyebut bahwa pengawas yang ditugaskan dapat melihat video kamera siswa secara langsung. Usulan redaksi baru menunggu persetujuan dan belum dipasang.

Menu **Rapat Video** tersedia untuk semua peran: isi nama ruang, klik **Gabung**, lalu izinkan kamera dan mikrofon. `lib-jitsi-meet` dimuat dari server Jitsi itu sendiri (`https://<domain>/libs/lib-jitsi-meet.min.js`), jadi versinya selalu cocok dengan server dan tidak ada dependensi npm tambahan. Bila kamera tidak dapat dibuka lewat Jitsi (ukuran tidak didukung), halaman membukanya langsung lalu menyerahkannya ke Jitsi.

## 7c. Safe Exam Browser (lockdown browser, per ujian)

Kuncian ujian (layar penuh, tanpa navigasi, tanpa pindah aplikasi, filter URL) dikerjakan oleh **Safe Exam Browser** sesuai konfigurasi `.seb` sekolah. EduAI tidak memakai layar penuh JavaScript sebagai penggantinya. EduAI memeriksa bahwa siswa memakai SEB dengan konfigurasi yang benar, dengan membandingkan hash Config Key / Browser Exam Key dari SEB terhadap kunci yang disimpan di backend.

- **Admin/penyelenggara** mengatur ujian lewat Daftar Ujian → Lihat Detail → **Keamanan ujian**: centang wajib SEB, isi Config Key (dan bila perlu Browser Exam Key), lalu alamat berkas `.seb` bila ada. Kunci hanya disimpan di backend.
- **Siswa:** **Mulai Ujian** membuka pemeriksaan SEB lebih dulu. Browser biasa atau konfigurasi lain ditolak. `POST /join` juga menolak (403) tanpa pemeriksaan yang lolos dalam 3 menit terakhir, dan ruang ujian memeriksa ulang setiap 60 detik.
- **Pengawas:** Monitoring menampilkan ringkasan "Keamanan ujian" dan lencana SEB per siswa.
- `backend\.env`: `EDUAI_SEB_ALLOWED_ORIGINS` adalah alamat halaman ujian sebagaimana dibuka di SEB. Bila kosong, dipakai `EDUAI_CORS_ORIGINS`.

Templat konfigurasi, langkah admin, dan batasan ada di `dev\seb\README.md`. **Belum diuji dengan SEB sungguhan**; uji integrasi meniru SEB di Chrome.

## 8. Menjalankan tes

```powershell
cd C:\EduAI\ai\eduai-ai ; python -m pytest -q          # 50 tes (beberapa butuh model + scikit-image)
cd C:\EduAI\backend     ; python -m pytest -q          # 134 tes (beberapa dilewati bila model tidak ada)
cd C:\EduAI\frontend    ; npm run lint ; npx tsc --noEmit ; npm run build
node --experimental-strip-types tests\notify.test.ts ; node --experimental-strip-types tests\audioScores.test.ts
node --experimental-strip-types tests\meetingIsolation.test.ts ; node --experimental-strip-types tests\consent.test.ts
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
- Token sesi tidak dikirim lewat URL dan tidak dicatat di log; frame tidak pernah ditulis ke log. Satu-satunya tanda tangan di URL adalah tautan gambar bukti laporan: berlaku 5 menit, hanya untuk satu kejadian, tidak bisa dipakai sebagai token sesi, dan izin penerbitnya diperiksa ulang setiap kali dibuka. Selama 5 menit itu, siapa pun yang memegang URL-nya dapat membuka gambar tersebut, dan URL dapat muncul di log akses server.
- Tidak ada penyimpanan video penuh atau audio. Analisis suara (bila siswa menyetujui secara terpisah) berjalan di browser siswa; yang dikirim hanya tiga skor (ucapan/bisikan/musik) per ±1 dtk. Evidence = maks. 12 cuplikan JPEG kecil per indikasi, ID acak, opsional terenkripsi, dihapus otomatis setelah 24 jam (`EDUAI_EVIDENCE_RETENTION_HOURS`), akses hanya lewat endpoint berautentikasi dan tercatat di audit log.
- **Retensi evidence dan laporan:** evidence sesi yang laporannya belum final ditahan sampai finalisasi, paling lama 7 hari sejak sesi selesai (`EDUAI_EVIDENCE_HOLD_DAYS`), lalu dihapus walaupun laporan belum final. "Sesi selesai" berarti waktu yang lebih awal antara status Selesai dan jadwal berakhir, sehingga sesi yang tidak pernah ditutup tetap punya batas. Finalisasi menyalin satu gambar per kejadian; salinan ini dihapus otomatis 24 jam setelah finalisasi (`EDUAI_REPORT_FRAME_RETENTION_HOURS`) dan penghapusannya dicatat di audit log. Setelah itu laporan menampilkan "Gambar bukti sudah dihapus sesuai kebijakan retensi". Pemeriksaan berjalan tiap 10 menit, tetapi gambar yang kedaluwarsa langsung berhenti disajikan.
- **Berkas PDF dan Excel yang diunduh berada di luar penghapusan otomatis.** PDF dari pengawas atau admin memuat gambar bukti, jadi simpan sesuai kebijakan sekolah. Setiap ekspor tercatat di audit log.
- Gambar bukti di laporan hanya untuk pengawas sesi dan admin; penyelenggara dan pihak sekolah melihat laporan tanpa gambar dan tanpa hak ubah. Catatan AI hanya penanda hal yang perlu diperiksa, bukan bukti pelanggaran.
- Siswa tidak pernah dapat membaca status AI, indikasi, atau evidence. Pihak sekolah hanya melihat indikasi yang sudah divalidasi.

## Langkah manual yang masih diperlukan

1. Isi `backend\.env` (JWT secret, kunci layanan) dan unduh model di setiap komputer/server.
2. Unduh dan uji `face_landmarker.task` serta `efficientdet_lite0.tflite` (`smoke_test_models.py`), lalu uji ulang indikator kepala & ponsel dengan webcam sungguhan.
3. Jalankan paket OpenVidu (bagian 7) di Windows dan jalankan `tests\e2e\e2e_livekit_worker.py` (mode `stop` dan `kill`); catat hasilnya. Jalur ini sudah lulus dengan server LiveKit di Linux, tetapi jalur Windows (CTRL_BREAK) dan paket Docker OpenVidu belum.
4. Uji analisis suara dengan mikrofon dan wajah sungguhan (orang lain berbicara saat mulut siswa diam) sebelum memakai indikator `OTHER_VOICE`.
5. Kalibrasi ambang dengan video pilot berlabel (dengan persetujuan) memakai `run_webcam.py` + `evaluate.py`.
6. Untuk produksi: HTTPS, `EDUAI_SEED_DEMO=false`, akun nyata, PostgreSQL bila lebih dari satu proses backend, kebijakan retensi data teks (indikasi/validasi) dari sekolah, dan uji beban.
7. Fitur UI yang belum tersambung backend (diberi label "Data contoh" atau tombol nonaktif): simpan pengaturan profil/notifikasi, tambah user dari UI, edit/hapus ujian, SSO.
