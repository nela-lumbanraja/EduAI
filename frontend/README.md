# EduAI — frontend (React + TypeScript + Vite + Tailwind)

Desain dan alur halaman dari versi Figma dipertahankan di `src/App.tsx`. Data sekarang berasal dari backend EduAI (`../backend`); lihat README di folder induk untuk menjalankan seluruh sistem.

## Menjalankan di VS Code

1. Pastikan Node.js 22.12+ terpasang dan backend berjalan di `http://localhost:8000`.
2. Terminal → New Terminal:

   ```bash
   npm install
   npm run dev
   ```

3. Buka `http://localhost:5173`. Permintaan `/api/...` diteruskan ke backend oleh proxy Vite (`vite.config.ts`); ubah target dengan `VITE_API_PROXY` di `.env.local` bila perlu.

## Berkas penting

- `src/App.tsx` — semua layar (struktur dan desain asli).
- `src/api.ts` — klien REST bertipe; token sesi disimpan di `sessionStorage` (hilang saat tab ditutup).
- `src/media.ts` — kamera/mikrofon, OpenVidu (`livekit-client`), pengunggah frame ke AI.

## Catatan

- Jangan menaruh rahasia di variabel `VITE_*`: semuanya terlihat di browser.
- Kamera hanya bisa dipakai di `https://` atau `http://localhost`.
- `npm run build` menghasilkan `dist/` untuk disajikan oleh web server mana pun; arahkan `/api` ke backend (atau isi `VITE_API_BASE_URL`). Web server perlu mengembalikan `index.html` untuk `/login` (fallback SPA; Vite sudah melakukannya).

## Ujian lewat HP (Android Chrome dan iPhone Safari)

Status: alur siswa sudah diuji dengan **emulasi** Android dan iPhone di Chrome headless, belum di HP sungguhan. Engine-nya tetap Chromium, jadi perilaku khas Safari iOS (WebKit) belum terbukti. Uji di HP nyata dengan langkah di bawah sebelum dipakai untuk ujian.

**Syarat:**
- Kamera di browser HP hanya bisa dibuka lewat **HTTPS**. `http://<ip-pc>:5173` tidak mendapat kamera.
- Untuk uji lewat Wi-Fi:
  1. Buat sertifikat dengan [mkcert](https://github.com/FiloSottile/mkcert): `mkcert -install`, lalu `mkcert 192.168.x.x localhost`.
  2. Isi `VITE_DEV_HTTPS_CERT` dan `VITE_DEV_HTTPS_KEY` di `.env.local`.
  3. Jalankan `npm run dev -- --host 0.0.0.0` dan buka `https://192.168.x.x:5173` di HP.
  4. Di iPhone, pasang dan percayai root CA mkcert (Pengaturan → Umum → Info → Pengaturan Kepercayaan Sertifikat). Di Android, pasang CA-nya lewat Pengaturan → Keamanan → Enkripsi & kredensial.
- Video langsung ke pengawas memerlukan OpenVidu (`LIVEKIT_URL` di backend) atau Jitsi. Dari halaman HTTPS, alamat OpenVidu juga harus `wss://`. Untuk uji LAN, isi `VITE_LIVEKIT_PROXY=ws://localhost:7880` dan `LIVEKIT_PUBLIC_URL=wss://192.168.x.x:5173` supaya sinyal OpenVidu ikut lewat server Vite. Tanpa OpenVidu atau Jitsi, kamera tetap dianalisis AI lewat frame yang dikirim browser, tetapi pengawas tidak melihat video langsung.
- Safe Exam Browser hanya ada untuk Windows, macOS, dan iOS. Siswa Android tidak bisa mengikuti ujian yang mewajibkan SEB.

**Langkah uji manual (lakukan di Android Chrome dan iPhone Safari):**
1. Login sebagai siswa, buka **Ujian Saya**, lalu ketuk **Mulai Ujian** pada ujian yang sedang berlangsung.
2. Saat browser meminta izin, tolak dulu. Pastikan muncul pesan langkah mengizinkan kamera untuk HP itu dan tombol **Coba lagi**. Izinkan lewat pengaturan situs, lalu ketuk **Coba lagi**.
3. Pastikan yang terbuka **kamera depan** dan lencana "Kamera aktif" muncul. Di iPhone, ketuk layar sekali bila indikator mikrofon diam.
4. Buka aplikasi Kamera atau panggilan video, lalu kembali dan ketuk **Coba lagi**. Pesan "dipakai aplikasi lain" harus hilang.
5. Lanjut ke persetujuan, lalu ruang ujian. Cek tidak ada yang terpotong, tombol **Keluar**, mikrofon, dan kamera bisa disentuh, dan layar tidak mati sendiri.
6. Di HP lain atau komputer, login sebagai pengawas lalu buka **Monitoring**. Kamera siswa harus tercatat aktif, status AI harus berjalan, dan bila OpenVidu aktif video langsungnya harus tampil.
7. Pindah ke aplikasi lain selama 10 detik, lalu kembali. Kamera harus aktif lagi sendiri, atau muncul tombol **Aktifkan ulang kamera**. Di Monitoring, kamera harus sempat tercatat mati.
8. Matikan Wi-Fi atau data selama beberapa detik. Status harus langsung "Koneksi terputus", lalu pulih saat tersambung kembali.
9. Ketuk **Keluar** dan pastikan kembali ke Ujian Saya.

**Belum ada di EduAI:** soal, pilihan jawaban, dan pengiriman jawaban. EduAI hanya mengawasi; soal dikerjakan di sistem ujian sekolah (misalnya lewat SEB).

## Tes

- `npm test`: tes unit (`tests/*.test.ts`) tanpa dependensi tambahan. `tests/mediaSupport.test.ts` berisi aturan kamera dan mikrofon untuk Android dan iOS.
- `e2e/run_e2e.py`: tes ujung-ke-ujung di browser dengan backend dan DB uji terpisah. Lihat [e2e/README.md](e2e/README.md).
- `e2e/mobile_cdp_e2e.py`: alur siswa di HP (emulasi Android, iPhone, dan desktop) lewat Chrome headless. Tes ini membuat ujian uji, jadi **jalankan hanya pada salinan database**. Caranya ada di bagian atas berkas.

## Keterbatasan yang diketahui

- **Alamat di bilah browser tidak berganti saat berpindah halaman.** Contohnya, setelah masuk dari `/login`, alamat tetap `/login` walaupun yang tampil dasbor. Ini disengaja: Safe Exam Browser memasukkan URL halaman ke dalam kunci yang diperiksa backend, sehingga mengganti URL setelah halaman dimuat (`history.pushState`) bisa menggagalkan verifikasi SEB siswa. Alamat hanya dibaca sekali saat halaman dibuka (`src/routes.ts`): `/login` membuka Login, atau dasbor bila sudah masuk; alamat lain membuka Beranda, atau dasbor bila sudah masuk.
- **Ukuran bundle JavaScript sekitar 974 kB** (peringatan Vite "chunks are larger than 500 kB"). Rencana: pecah kode per halaman dengan `import()` dinamis.
- Foto Beranda dan Login ada di `public/images/` dan disimpan dengan Git LFS: `ai-signals/` (kartu "Yang diperhatikan AI"), `beranda/` (kartu dan banner; sumber di `beranda/CREDITS.md`), dan `login/` (foto tim dan robot roket di layar loading). Jalankan `git lfs pull` bila foto tampil rusak. Bila foto sinyal AI gagal dimuat, kartu memakai ilustrasi dari `public/images/sinyal-ai/` (dibuat dengan `scripts/generate-illustrations.py`); gambar lain memakai `public/images/fallback-gambar.svg`.
