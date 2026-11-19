# Catatan keamanan

## 1. Peran pada pendaftaran mandiri ditentukan dari awalan email (belum diperbaiki)

**Status:** dicatat 2026-11-20. **Kode belum diubah**; menunggu keputusan opsi di bawah.

### Perilaku saat ini
- `POST /api/auth/register` (`backend/app/api.py`, fungsi `register`) menerima email apa pun yang **diawali `mahasiswa` atau `siswa`** dan berisi `@`.
- Akun yang dibuat langsung aktif dengan peran internal `siswa` (= mahasiswa), dan tokennya langsung diterbitkan.
- Fitur ini **aktif secara bawaan**: `EDUAI_ALLOW_SELF_REGISTER=true` (`backend/app/settings.py`, `backend/.env.example`).
- Tidak ada pemeriksaan bahwa pendaftar **memiliki** email itu: tidak ada tautan atau kode verifikasi, dan backend tidak punya fungsi pengiriman email.
- Tidak ada pemeriksaan domain kampus. `mahasiswa.palsu@gmail.com` diterima.
- Pendaftaran mandiri **tidak meminta NIM/kelas**, padahal akun mahasiswa buatan admin wajib punya NIM dan kelas (`create_user`).
- Endpoint `register` **tidak dibatasi lajunya**. Pembatas percobaan (`st.limiter`) hanya ada di `login`.

### Mengapa ini masalah
Awalan email bukan bukti identitas. Siapa pun yang dapat membuka aplikasi bisa:
1. **Membuat akun mahasiswa palsu** dengan nama mahasiswa lain. Bila staf mendaftarkan peserta ujian berdasarkan nama, akun palsu bisa salah terpilih.
2. **Mendahului mahasiswa asli.** Bila email kampus asli seorang mahasiswa sudah lebih dulu didaftarkan orang lain, mahasiswa itu mendapat galat 409 ("Email ini sudah terdaftar").
3. **Membanjiri tabel pengguna** dengan akun, karena tidak ada batas laju.

Batas dampaknya: peran yang didapat selalu `siswa`, bukan staf atau admin, sehingga tidak ada kenaikan hak akses. Mahasiswa juga hanya melihat ujian tempat ia didaftarkan oleh staf (kueri `exam_students` di `api.py`). Akun palsu tidak otomatis bisa masuk ke ujian mana pun.

### Opsi perbaikan (pilih salah satu; belum dikerjakan)

**Opsi A — Verifikasi domain email kampus dan kepemilikan email**
- Hanya email dengan domain kampus yang diterima, diatur lewat konfigurasi baru, misalnya `EDUAI_STUDENT_EMAIL_DOMAIN`. Awalan email tidak lagi dipakai.
- Akun baru berstatus **belum aktif** sampai pendaftar membuka tautan atau memasukkan kode yang dikirim ke email itu.
- Ditambah batas laju pada `register`.
- Kebutuhan: server SMTP kampus (alamat, akun pengirim) dan templat email.
- **File terdampak:**
  - `backend/app/settings.py`, `backend/.env.example`: domain, SMTP, masa berlaku kode;
  - `backend/app/api.py`: `register`, endpoint verifikasi baru, `login` menolak akun belum terverifikasi;
  - `backend/app/schemas.py`: input verifikasi;
  - `backend/app/db.py`: kolom status verifikasi dan token/kode;
  - modul baru pengirim email, misalnya `backend/app/mailer.py`;
  - `frontend/src/App.tsx` dan `frontend/src/api.ts`: teks pendaftaran dan layar "periksa email Anda";
  - `backend/tests/test_api.py` dan tes baru verifikasi;
  - `frontend/e2e/run_e2e.py` bila alur pendaftaran diuji;
  - `docs/API.md`, `docs/DEPLOY_HTTPS.md`, `README.md`.
- **Kelebihan:** mahasiswa tetap bisa mendaftar sendiri, dan email terbukti milik pendaftar.
- **Kekurangan:** butuh SMTP. Identitas tetap hanya sebatas email kampus, belum dicocokkan dengan NIM.

**Opsi B — Akun dibuat admin dari daftar NIM (pendaftaran mandiri dimatikan)**
- `EDUAI_ALLOW_SELF_REGISTER` diubah menjadi `false` secara bawaan, dan tombol daftar disembunyikan bila fitur mati.
- Admin atau Penyelenggara mengimpor daftar mahasiswa resmi dari Program Studi (CSV: NIM, nama, email, kelas). Akun dibuat dengan kata sandi awal yang wajib diganti saat masuk pertama.
- **File terdampak:**
  - `backend/app/settings.py`, `backend/.env.example`: nilai bawaan `false`;
  - `backend/app/api.py`: endpoint impor CSV baru, misalnya `POST /api/users/import`, dengan validasi NIM unik;
  - `backend/app/schemas.py`;
  - `backend/app/db.py`: penanda "wajib ganti kata sandi" bila belum ada;
  - `frontend/src/App.tsx`: unggah CSV di Manajemen User/Akun Mahasiswa; tombol daftar mengikuti konfigurasi;
  - `frontend/src/api.ts`;
  - `backend/tests/test_user_admin.py`, `backend/tests/test_api.py`: tes pendaftaran mandiri yang ditolak bila dimatikan;
  - `frontend/e2e/run_e2e.py`;
  - `docs/API.md`, `README.md`.
- **Kelebihan:** identitas dicocokkan dengan data resmi (NIM) dan tanpa SMTP. Fitur tambah/ubah akun yang sudah ada juga bisa dipakai lebih dulu, tanpa impor.
- **Kekurangan:** ada beban administrasi awal setiap semester.

**Langkah sementara tanpa mengubah kode:** set `EDUAI_ALLOW_SELF_REGISTER=false` di `backend/.env` dan buat akun mahasiswa lewat Manajemen User. Dukungan untuk ini sudah ada.
