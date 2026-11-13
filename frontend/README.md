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

## Tes

- `npm test`: tes unit (`tests/*.test.ts`) tanpa dependensi tambahan.
- `e2e/run_e2e.py`: tes ujung-ke-ujung di browser dengan backend dan DB uji terpisah. Lihat [e2e/README.md](e2e/README.md).

## Keterbatasan yang diketahui

- **Alamat di bilah browser tidak berganti saat berpindah halaman.** Contohnya, setelah masuk dari `/login`, alamat tetap `/login` walaupun yang tampil dasbor. Ini disengaja: Safe Exam Browser memasukkan URL halaman ke dalam kunci yang diperiksa backend, sehingga mengganti URL setelah halaman dimuat (`history.pushState`) bisa menggagalkan verifikasi SEB siswa. Alamat hanya dibaca sekali saat halaman dibuka (`src/routes.ts`): `/login` membuka Login, atau dasbor bila sudah masuk; alamat lain membuka Beranda, atau dasbor bila sudah masuk.
- **Ukuran bundle JavaScript sekitar 974 kB** (peringatan Vite "chunks are larger than 500 kB"). Rencana: pecah kode per halaman dengan `import()` dinamis.
- Gambar Beranda dan Login adalah ilustrasi SVG orisinal EduAI di `public/images/` (`sinyal-ai/`, `beranda/`, `login/`), sehingga tampil di salinan repo yang baru. Foto Figma lama di `public/images/ai-signals/` tetap tidak di-commit dan tidak dipakai lagi. Bila sebuah gambar gagal dimuat, `public/images/fallback-gambar.svg` ditampilkan sebagai gantinya.
