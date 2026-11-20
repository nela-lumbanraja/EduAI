# EduAI lewat HTTPS (agar kamera dan mikrofon jalan di HP)

> **Istilah.** Dokumen ini memakai istilah mitra Program Studi Informatika: mahasiswa, Program Studi, NIM, mata kuliah, dosen. Nama kode internal ditulis apa adanya: peran `siswa` (= mahasiswa), peran lama `sekolah` (= Penyelenggara Ujian/pihak Program Studi), kolom `nis` (= NIM), `class_name` (= kelas), jenis suara `BICARA_SISWA` (= mahasiswa berbicara), akun demo `siswa1`–`siswa6` dan `sekolah1`.

Browser hanya memberi kamera dan mikrofon pada halaman **HTTPS** (atau `http://localhost` di komputer itu sendiri).
Mahasiswa yang membuka `http://192.168.x.x:5173` dari HP tidak akan pernah mendapat kamera, apa pun isi kodenya.
Untuk ujian sungguhan EduAI perlu satu domain HTTPS dengan sertifikat yang sah (misalnya Let's Encrypt).

`localhost` di laptop **bukan** `localhost` di HP: bagi HP, `localhost` adalah HP itu sendiri. Semua alamat yang
diberikan ke browser (API, OpenVidu, Jitsi) harus alamat publik server.

## Susunan yang disarankan

```
HP / laptop  ──https──►  web server (nginx/Caddy) di https://ujian.prodi.ac.id
                           ├─ /            → frontend (isi folder frontend/dist dari `npm run build`)
                           ├─ /api/        → backend FastAPI (http://127.0.0.1:8000)
                           └─ /rtc         → OpenVidu/LiveKit (ws://127.0.0.1:7880), WebSocket   [bila OpenVidu dipakai]
```

Frontend memanggil `/api` di domain yang sama, jadi tidak perlu CORS dan `VITE_API_BASE_URL` dibiarkan kosong.

## Contoh nginx

```nginx
server {
    listen 443 ssl http2;
    server_name ujian.prodi.ac.id;
    ssl_certificate     /etc/letsencrypt/live/ujian.prodi.ac.id/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ujian.prodi.ac.id/privkey.pem;

    # Kamera dan mikrofon hanya untuk situs ini sendiri.
    add_header Permissions-Policy "camera=(self), microphone=(self), display-capture=()" always;
    add_header Strict-Transport-Security "max-age=31536000" always;

    root /srv/eduai/frontend/dist;
    location / { try_files $uri /index.html; }            # SPA: /login juga ke index.html

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        client_max_body_size 10m;                           # frame AI dari browser mahasiswa
    }

    # Hanya bila OpenVidu dipakai: sinyal WebSocket lewat domain yang sama (wss://).
    location /rtc {
        proxy_pass http://127.0.0.1:7880;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }
}
server { listen 80; server_name ujian.prodi.ac.id; return 301 https://$host$request_uri; }
```

Media OpenVidu (audio/video) berjalan lewat UDP/TCP di port milik OpenVidu sendiri (lihat dokumentasi
OpenVidu untuk port dan `node_ip`/alamat publik); hanya sinyalnya yang lewat `/rtc`.

## Nilai di `backend/.env`

| Variabel | Isi untuk HTTPS |
|---|---|
| `EDUAI_BACKEND_URL` | `https://ujian.prodi.ac.id` |
| `EDUAI_CORS_ORIGINS` | `https://ujian.prodi.ac.id` (hanya perlu bila frontend di domain lain) |
| `LIVEKIT_PUBLIC_URL` | `wss://ujian.prodi.ac.id` (lewat `/rtc` di atas) atau `wss://video.prodi.ac.id`; **bukan** `ws://localhost:7880` |
| `EDUAI_JITSI_DOMAIN` | domain Jitsi yang memakai HTTPS, mis. `meet.prodi.ac.id`; bukan `localhost:8443` |
| `EDUAI_SEED_DEMO` | `false` |

Bila alamat video masih `localhost` atau `ws://` pada halaman HTTPS, ruang ujian mahasiswa menampilkan peringatan
"Video langsung ke pengawas tidak dapat tersambung dari perangkat ini" (pemeriksaan di `frontend/src/mediaSupport.ts`,
`mediaServerProblem`). Kamera tetap dianalisis AI lewat frame yang dikirim ke `/api`.

## Satu proses backend saja

Jalankan backend dengan **satu** proses (`uvicorn app.main:app`, tanpa `--workers 2` atau lebih). Alasannya ada di kode saat ini:

- Analisis setiap mahasiswa (baseline arah kepala, durasi indikasi, cooldown) disimpan di memori proses. Bila frame seorang
  mahasiswa dibagi ke beberapa worker, setiap worker hanya melihat sebagian frame, sehingga indikasi bisa terlewat atau ganda.
- Setiap worker memuat semua model AI sendiri (lihat `GET /api/ai/status`), jadi RAM ikut berlipat.
- Setiap worker yang (di)mulai ulang mematikan pemantauan semua ujian (`monitoring_active=0`), termasuk saat uvicorn
  mengganti worker yang mati di tengah ujian.

Kapasitas satu proses diukur di uji beban (laporan integrasi). Untuk lebih banyak mahasiswa, tambah inti CPU atau
naikkan `EDUAI_AI_MAX_CONCURRENT` setelah diuji, bukan menambah worker.

## Uji di jaringan program studi sebelum ada domain

Lihat `frontend/README.md` bagian "Ujian lewat HP": sertifikat mkcert, `VITE_DEV_HTTPS_CERT`/`VITE_DEV_HTTPS_KEY`,
lalu buka `https://<ip-pc>:5173` di HP (CA mkcert harus dipercaya di HP). Ini hanya untuk pengujian.

## Daftar periksa setelah deployment

1. Buka `https://ujian.prodi.ac.id` di HP: gembok tampil, tanpa peringatan sertifikat.
2. Login mahasiswa → Mulai Ujian → Cek Perangkat → ketuk **Aktifkan kamera & mikrofon** → izinkan. Preview tampil, mikrofon bergerak.
3. Di DevTools/`curl -I`, header `Permissions-Policy` ada.
4. Bila OpenVidu dipakai: di Monitoring pengawas, video mahasiswa dari HP tampil.
