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
- `npm run build` menghasilkan `dist/` untuk disajikan oleh web server mana pun; arahkan `/api` ke backend (atau isi `VITE_API_BASE_URL`).
