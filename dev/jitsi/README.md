# Server Jitsi untuk pengembangan

Server Jitsi lokal dari **docker-jitsi-meet resmi**, rilis `stable-11248-2`. `docker-compose.yml` di folder ini adalah berkas asli rilis itu tanpa perubahan; lisensinya di `LICENSE.docker-jitsi-meet`.

Hanya untuk pengembangan di satu laptop. Ini **bukan** server yang dikelola sekolah. Jangan dipakai untuk ujian sungguhan.

## Yang diatur

- **Hanya token dari backend EduAI** yang bisa masuk (`ENABLE_AUTH=1`, `AUTH_TYPE=jwt`, tanpa tamu). Token hanya membuka satu ruang.
- **Tanpa rekaman, streaming, atau transkripsi.** Jibri dan Jigasi tidak dijalankan, dan semua opsi rekaman mati.
- **P2P mati.** Video selalu lewat bridge (JVB), tidak pernah langsung antarpeserta.

## Menjalankan

Butuh Docker Desktop yang sedang berjalan.

```powershell
cd C:\EduAI
python dev\jitsi\make-env.py          # membuat dev\jitsi\.env (kata sandi dan rahasia JWT acak)
cd dev\jitsi
docker compose up -d
```

`make-env.py` mencetak baris yang perlu ditambahkan ke `backend\.env`. Skrip itu tidak menulis `backend\.env` sendiri.

```
EDUAI_JITSI_DOMAIN=localhost:8443
EDUAI_JITSI_XMPP_DOMAIN=meet.jitsi
EDUAI_JITSI_MUC=muc.meet.jitsi
EDUAI_JITSI_OPERATOR=dev
EDUAI_JITSI_APP_ID=eduai
EDUAI_JITSI_APP_SECRET=<sama dengan JWT_APP_SECRET di dev\jitsi\.env>
```

Setelah itu mulai ulang backend.

**Sekali per browser:** buka https://localhost:8443, lalu terima sertifikat self-signed. Tanpa langkah ini, browser menolak memuat `lib-jitsi-meet` dan Rapat Video gagal.

Menghentikan server: `docker compose down` di folder ini. Data server ada di `dev\jitsi\.jitsi-cfg\` dan diabaikan git.

## Port dan alamat

| Port | Untuk |
|---|---|
| 8443/TCP | HTTPS: halaman, `lib-jitsi-meet`, websocket XMPP |
| 8180/TCP | HTTP. Bawaan resminya 8000, dipindah karena 8000 dipakai backend EduAI |
| **10000/UDP** | Video (JVB). Tanpa port ini peserta tersambung tetapi tidak ada video |

**`JVB_ADVERTISE_IPS`** adalah alamat yang diberikan JVB ke browser untuk mengirim video. Nama lamanya `DOCKER_HOST_ADDRESS`, yang sudah deprecated tetapi masih dibaca.

- Isi dengan **IP LAN laptop**, misalnya `192.168.18.78` (lihat `ipconfig`).
- **Jangan isi `127.0.0.1`.** Chrome tidak memakai kandidat loopback, sehingga peserta tersambung tetapi video tidak pernah mengalir. Ini sudah terbukti saat diuji.
- Kalau IP laptop berganti (pindah Wi-Fi), ubah nilainya lalu jalankan `docker compose up -d jvb`.

## Perangkat lain (HP atau laptop lain di jaringan yang sama)

- **HTTPS wajib.** Kamera di browser hanya jalan di HTTPS atau di `localhost`. Jadi EduAI dan Jitsi harus dibuka lewat HTTPS dengan sertifikat yang dipercaya perangkat itu. Sertifikat self-signed harus diterima manual di setiap perangkat.
- `EDUAI_JITSI_DOMAIN` dan `PUBLIC_URL` harus memakai alamat yang bisa dijangkau perangkat itu (IP LAN atau nama host), bukan `localhost`.
- Firewall Windows harus mengizinkan masuk **TCP 8443** dan **UDP 10000**.

## Troubleshooting

| Gejala | Penyebab dan perbaikan |
|---|---|
| Rapat Video: "Server Jitsi tidak terjangkau" (admin) | Kontainer belum jalan (`docker compose ps`), atau `EDUAI_JITSI_DOMAIN` salah. |
| Bergabung gagal, error `passwordRequired` | Token ditolak: `EDUAI_JITSI_APP_SECRET` berbeda dari `JWT_APP_SECRET`, atau backend belum dimulai ulang. |
| `notAllowed` | Token untuk ruang lain. Ini disengaja untuk ruang ujian siswa lain. |
| Tersambung, peserta terlihat, tetapi video hitam | UDP 10000 tidak sampai: periksa `JVB_ADVERTISE_IPS` (IP LAN, bukan 127.0.0.1) dan firewall. |
| `videobridgeNotAvailable` / "no operational bridges" di log jicofo | JVB lambat atau kehabisan memori, misalnya saat stack OpenVidu juga berjalan. Jalankan `docker compose restart jvb jicofo`. |
| Error `lib-jitsi-meet tidak tersedia` di browser | Sertifikat https://localhost:8443 belum diterima. |
