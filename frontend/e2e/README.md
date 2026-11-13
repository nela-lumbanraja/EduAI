# Tes ujung-ke-ujung (browser)

`run_e2e.py` menjalankan alur Beranda, Login, dan dasbor pengawas di Chrome sungguhan (Playwright), lalu memeriksa tata letak di lebar 1440, 1024, dan 390 px.

## Data uji terpisah

- `server.py` menyalakan backend uji dengan **DB baru yang kosong** di folder sementara. DB itu diisi akun demo (`EDUAI_SEED_DEMO`) dan beberapa kejadian contoh tanpa gambar.
- `backend/data` dan `backend/.env` tidak pernah dibaca atau ditulis. Server uji menolak berjalan bila folder kerjanya ada di `backend/data`.
- Jitsi dan OpenVidu dimatikan, dan rahasia JWT acak di setiap putaran. Dengan begitu, tidak ada ruang video yang sama dengan aplikasi asli.
- Aplikasi yang sedang berjalan di port 8000 dan 5173 tidak disentuh. Tes memakai port 8872 dan 5302.

## Menjalankan

Kata sandi akun demo tidak ditulis di kode tes. Isi lewat variabel lingkungan. Nilainya sama dengan `DEMO_PASSWORD` di `backend/app/seed.py`.

```powershell
cd C:\Users\nelae\Downloads\EduAI
$env:EDUAI_E2E_PASSWORD = "<kata sandi akun demo>"
.venv\Scripts\python.exe -I frontend\e2e\run_e2e.py
```

Variabel opsional:

- `EDUAI_E2E_SHOTS`: folder screenshot.
- `EDUAI_E2E_FIGMA_URL`: alamat desain Figma (misalnya `http://127.0.0.1:5180`) untuk screenshot pembanding.
- `EDUAI_E2E_BACKEND_PORT` dan `EDUAI_E2E_FRONTEND_PORT`: port lain bila 8872 atau 5302 sedang dipakai.

Hasilnya berupa baris `LULUS` atau `GAGAL` untuk setiap pemeriksaan dan ringkasan di akhir. Kode keluar 0 berarti semua pemeriksaan lulus.

Prasyarat: `.venv` proyek dengan `playwright`, Chrome terpasang, dan `npm install` di `frontend/`.
