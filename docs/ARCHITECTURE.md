# Arsitektur & alur frame EduAI

## Komponen

```
┌──────────────────────┐        ┌────────────────────────────┐        ┌─────────────────────┐
│ frontend/ (React 19) │  HTTPS │ backend/ (FastAPI)          │        │ OpenVidu 3 (LiveKit) │
│  siswa: kamera,      │───────▶│  auth JWT + RBAC            │──token▶│  ruang eduai-exam-N  │
│  pengawas: dasbor    │◀───────│  ujian, presence, persetujuan│        │  ws://…:7880         │
└─────────┬────────────┘  JSON  │  event API, evidence, audit │        └──────────┬──────────┘
          │ WebRTC (opsional)   │  AIManager (in-process)     │                   │ WebRTC
          └────────────────────▶│  WorkerManager (subprocess) │◀──X-AI-Service-Key─┤
                                └──────────────┬──────────────┘                   │
                                               │ import                           │
                                ┌──────────────▼──────────────┐   ┌───────────────▼───────────┐
                                │ ai/eduai-ai (paket Python)  │   │ eduai_ai.livekit_worker    │
                                │ quality → perception →      │   │ peserta tersembunyi,       │
                                │ temporal → events/evidence  │◀──│ subscribe kamera siswa     │
                                └─────────────────────────────┘   └────────────────────────────┘
```

| Bagian | Isi |
|---|---|
| `frontend/` | Aplikasi web asli (desain dan struktur halaman dipertahankan). `src/api.ts` klien REST, `src/media.ts` kamera, OpenVidu (`livekit-client`), pengunggah frame. |
| `backend/` | FastAPI + SQLite. `app/api.py` semua endpoint, `app/ai_service.py` analisis frame browser, `app/livekit_service.py` token & worker, `app/store.py` penyimpanan hasil AI, `app/security.py` JWT/RBAC/kunci layanan. |
| `ai/eduai-ai/` | Modul AI: gerbang kualitas, MediaPipe (Face Detector, Face Landmarker, Object Detector), aturan temporal, skema kejadian, evidence, worker OpenVidu. |

## Dua jalur frame menuju AI

Bergabung ke ruang OpenVidu **tidak** otomatis memberi AI akses ke piksel video. Piksel hanya didapat bila ada proses yang (a) menjadi peserta ruang dan berlangganan track, lalu (b) membuka stream dekode frame. EduAI menyediakan dua jalur:

### Jalur A — frame dari browser (default, sudah diuji E2E)

```
kamera siswa ──getUserMedia──▶ <video> pratinjau
   └─ tiap 1/EDUAI_UPLOAD_FPS dtk (default 0,5 dtk): canvas (lebar ≤ 640) → JPEG 0,8
        └─ POST /api/exams/{id}/frames  (JWT siswa, persetujuan wajib, ujian berlangsung, pemantauan aktif)
             └─ AIManager.submit_jpeg: ≤1 frame berjalan per siswa (frame berikut dibuang bila sibuk),
                semaphore global EDUAI_AI_MAX_CONCURRENT, analisis di thread (asyncio.to_thread)
                  └─ StudentAnalyzer.process → events / evidence / status
                       └─ store.upsert_event / save_evidence / upsert_status (SQLite + folder evidence)
dasbor pengawas ◀─ polling 3 dtk: GET /students, GET /events ; notifikasi 4 dtk: GET /api/events
```

Bila kamera dimatikan, browser tidak mengirim frame; status AI siswa menjadi "Belum ada data video" setelah 10 detik dan presence menampilkan "Kamera mati".

### Jalur B — worker AI di ruang OpenVidu (kode lengkap, belum diuji tanpa server OpenVidu)

```
siswa ──publish kamera (token: canPublish, canSubscribe=false)──▶ OpenVidu ruang eduai-exam-N
pengawas klik "Mulai AI" (EDUAI_ANALYSIS_SOURCE=livekit)
   └─ backend membuat token worker (hidden, canSubscribe, canPublish=false) dan menjalankan
      python -m eduai_ai.livekit_worker --session N   (token & kunci lewat environment, bukan argv)
         └─ rtc.Room.connect → event track_subscribed (hanya identity "student-<id>", sumber kamera)
              └─ rtc.VideoStream(track, capacity=2)  ← antrean terbatas, frame lama dibuang
                   └─ sampling analysis_fps (5) → frame.convert(RGB24) → StudentAnalyzer di thread
                        └─ POST /api/ai/events | /api/ai/evidence | /api/ai/status | /api/ai/heartbeat
                           (header X-AI-Service-Key)
```

Bila worker gagal dijalankan (OpenVidu belum dikonfigurasi, kunci layanan kosong), backend otomatis jatuh ke Jalur A dan memberi tahu pengawas.

Pengawas melihat **video langsung** hanya lewat OpenVidu (token subscribe-only). Tanpa OpenVidu, dasbor tetap menampilkan status kamera, status AI, indikasi, dan evidence; ubin video menampilkan siluet.

## Dari frame ke kejadian

1. **Kualitas** (`quality.py`): resolusi, kecerahan, ketajaman, video beku. Gagal → `cannot_analyze` dengan alasan; frame ini tidak pernah dihitung sebagai indikasi dan tidak disimpan sebagai evidence.
2. **Persepsi** (`perception.py`): BlazeFace (wajib) → jumlah wajah; Face Landmarker (opsional) → matriks transformasi → yaw/pitch; EfficientDet-Lite0 (opsional, tiap 0,5 dtk) → `cell phone`, `person`. Komponen yang tidak ada dilewati; indikator yang bergantung padanya tidak aktif.
3. **Temporal** (`temporal.py`): durasi minimum, histeresis, cooldown, acuan pose kepala per siswa (45 dtk). Ambang ada di `config.yaml` dan bersifat **sementara** (belum dikalibrasi pada data sekolah).
4. **Kejadian** (`events.py`): dikirim saat terbuka dan saat ditutup; skema 1.0.
5. **Evidence** (`evidence.py`): buffer cincin di memori (5 dtk sebelum) + 5 dtk sesudah indikasi terbuka, maks. 12 JPEG lebar ≤ 480 px. Disimpan dengan ID acak, opsional terenkripsi (Fernet), dihapus otomatis setelah `EDUAI_EVIDENCE_RETENTION_HOURS` (default 24 jam, sesuai keputusan URS "riwayat 1 hari"). Akses hanya lewat endpoint berautentikasi dan dicatat di audit log.

## Keputusan desain

- **Tidak ada penyimpanan video penuh/audio.** Evidence berupa cuplikan gambar kecil. Ini konsekuensi privasi yang disengaja; bila sekolah menghendaki klip video, perlu rekaman OpenVidu (Egress) dan kebijakan retensi tersendiri.
- **Indikasi ≠ pelanggaran.** UI selalu menyatakan keputusan ada pada pengawas; `cannot_analyze` dipisahkan dari indikasi di data, API, dan UI.
- **Polling, bukan WebSocket.** Sederhana dan cukup untuk satu sekolah; interval 3–5 dtk. Dapat diganti SSE/WebSocket bila diperlukan.
- **SQLite + satu proses backend.** Cocok untuk uji coba. Untuk beberapa proses/host: PostgreSQL, penyimpanan evidence bersama (S3/MinIO), dan antrean kerja terpisah.
