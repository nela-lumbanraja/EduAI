# Safe Exam Browser (SEB) untuk ujian EduAI

Kuncian ujian dikerjakan oleh **Safe Exam Browser**: layar penuh, tanpa navigasi browser, tanpa pindah ke aplikasi lain, dan hanya situs yang diizinkan filter URL. EduAI **tidak** meniru kuncian dengan mode layar penuh JavaScript. EduAI hanya memeriksa bahwa siswa benar-benar memakai SEB dengan konfigurasi yang ditetapkan sekolah, lalu menampilkan hasilnya kepada pengawas.

Dokumentasi resmi: https://safeexambrowser.org/developer/seb-integration.html dan https://safeexambrowser.org/developer/seb-config-key.html

## Cara kerja pemeriksaan

SEB menghitung `SHA256(URL tanpa fragmen + kunci)` untuk setiap halaman atau request. Ada dua jenis kunci:
- **Config Key**: bergantung hanya pada isi konfigurasi `.seb`, dan sama di Windows, macOS, dan iOS.
- **Browser Exam Key**: bergantung juga pada versi SEB, jadi berbeda per versi dan sistem operasi.

Backend menyimpan kunci yang diharapkan, menghitung ulang hash-nya, lalu membandingkan. Kunci tidak pernah dikirim ke browser siswa maupun pengawas.

| Jalur | Dari SEB | Kekuatan |
|---|---|---|
| Header HTTP | `X-SafeExamBrowser-ConfigKeyHash`, `X-SafeExamBrowser-RequestHash` pada request `POST /api/exams/{id}/seb/verify?n=<nonce>` | Terikat ke nonce sekali pakai, sehingga hash yang disadap tidak bisa dipakai ulang. |
| JavaScript API | `SafeExamBrowser.security.configKey` / `.browserExamKey` (SEB Windows 3.3.2+, macOS/iOS 3.0+) | Terikat ke URL halaman, yang sama setiap kali, sehingga hash yang disadap **bisa** dipakai ulang. |

Bila admin mengisi kedua jenis kunci, keduanya harus cocok. User agent `SEB/x.y` hanya dipakai sebagai keterangan, tidak pernah sebagai bukti.

## Langkah admin

1. **Siapkan konfigurasi SEB.** Buka `eduai-exam.template.xml` di SEB Config Tool (Windows) atau Preferences SEB (macOS), periksa setiap opsi, lalu:
   - Ubah `startURL` dan filter URL ke alamat frontend EduAI sekolah. Bila memakai Jitsi, tambahkan juga server Jitsi.
   - Isi **kata sandi keluar**.
   - Pastikan **kamera dan mikrofon diizinkan**, karena tanpa itu pemantauan AI tidak jalan.
   - Biarkan **Use Browser & Config Keys (send in HTTP header)** aktif.
   - Biarkan *content filter* mati, karena di SEB 3.x untuk macOS/iOS opsi ini mematikan JavaScript API.
2. **Simpan sebagai berkas `.seb`** (tujuan: *starting an exam*, sebaiknya terenkripsi). Salin **Config Key** yang ditampilkan tool tersebut.
3. **Isi pengaturan di EduAI:** Daftar Ujian, lalu Lihat Detail, lalu bagian **Keamanan ujian: Safe Exam Browser**.
   - Centang *Wajibkan Safe Exam Browser*.
   - Tempel Config Key. Browser Exam Key bersifat opsional; bila diisi, isi satu kunci per versi atau OS SEB yang dipakai.
   - Opsional: isi alamat berkas `.seb`. Siswa akan mendapat tautan `sebs://` (untuk https) atau `seb://` (untuk http).
4. **Atur alamat yang diterima** di `backend\.env`: `EDUAI_SEB_ALLOWED_ORIGINS=https://ujian.sekolah.sch.id`. Bila kosong, dipakai `EDUAI_CORS_ORIGINS`. Ini harus asal halaman ujian **sebagaimana dibuka di SEB**.

Setiap kali konfigurasi `.seb` diubah dan disimpan ulang, Config Key ikut berubah, jadi perbarui kuncinya di EduAI.

## Yang dialami siswa dan pengawas

- **Siswa** menekan **Mulai Ujian**, lalu masuk layar pemeriksaan SEB.
  - Browser biasa ditolak, beserta petunjuk dan tautan untuk membuka SEB. Konfigurasi yang salah ditolak dengan pesan "Konfigurasi SEB tidak sesuai".
  - Bila lolos, siswa lanjut ke Cek Perangkat, lalu Persetujuan, lalu Ruang Ujian.
  - Backend menolak `POST /join` tanpa pemeriksaan yang lolos dalam 3 menit terakhir, jadi melewati frontend tidak membantu.
  - Selama ujian, halaman memeriksa ulang setiap 60 detik.
- **Pengawas** melihat dua hal di Monitoring:
  - Ringkasan "Keamanan ujian", misalnya "Safe Exam Browser wajib · 5/6 siswa terverifikasi", beserta nama siswa yang bermasalah.
  - Lencana per siswa: *SEB terverifikasi*, *Bukan Safe Exam Browser*, *Konfigurasi SEB tidak sesuai*, *Verifikasi SEB kedaluwarsa*, atau *SEB belum diperiksa*.

  Pengawas tidak dapat melihat atau mengubah kunci.
- **Audit log** mencatat perubahan pengaturan, verifikasi pertama yang berhasil, setiap perubahan hasil, dan penolakan masuk.

## Lockdown terputus, keluar setelah ujian, dan Android (15 Nov 2026)

**Indikasi "Lockdown terputus" (`LOCKDOWN_LOST`).** Hanya berlaku untuk ujian yang mewajibkan SEB, selama ujian berlangsung, dan untuk siswa yang sudah masuk ruang ujian. Indikasi ini tidak bergantung pada pemantauan AI.

- **Dibuka bila:**
  - pemeriksaan SEB gagal setelah siswa itu terverifikasi (dibuka di luar SEB, konfigurasi lain, alamat lain);
  - tidak ada verifikasi baru selama lebih dari 3 menit (SEB ditutup atau halaman ditinggalkan);
  - sinyal kehadiran siswa juga berhenti (koneksi terputus).
- **Ditutup bila:** SEB terverifikasi lagi, siswa keluar dari ujian, atau ujian selesai.
- **Isi setiap kejadian:** waktu, siswa, ujian, jenis perangkat (dari user-agent, hanya keterangan), aplikasi lockdown, status verifikasi, dan waktu mulai lockdown. Tidak ada gambar bukti.
- Indikasi ini masuk ke kasus pengawas dan **perlu ditinjau**. Ini **bukan bukti kecurangan**: aplikasi yang tertutup sendiri atau jaringan yang putus terlihat sama.
- **Pengawas** melihat, di halaman detail siswa, panel *Lockdown ujian*: aplikasi, perangkat, waktu mulai lockdown, pemeriksaan terakhir, dan riwayat status. Kartu siswa di Monitoring menampilkan "Lockdown terputus sejak ...".

**Keluar dari SEB setelah ujian (Quit URL).**
1. Di berkas `.seb`, isi `quitURL` dengan alamat yang panjang dan sulit ditebak di alamat EduAI, misalnya `https://ujian.sekolah.sch.id/seb-keluar-7f3a9c`.
2. Isi alamat yang **sama persis** di EduAI: Detail Ujian, lalu *Keamanan ujian*, lalu **Quit URL**.
3. Setelah server menyatakan ujian **Selesai**, siswa melihat tombol **Keluar dari Safe Exam Browser** di ruang ujian. Backend (`GET /api/exams/{id}/seb/quit`) menolak memberikan alamat itu selama ujian masih berlangsung. Alamat ini juga tidak ada di data ujian yang dibaca siswa, dan setiap pemakaian dicatat di audit log.
4. Kata sandi keluar SEB tetap dipegang pengawas untuk keadaan darurat.

**Android.** Safe Exam Browser tidak tersedia untuk Android, jadi siswa Android **tidak dapat** mengikuti ujian yang mewajibkan SEB. Mereka mendapat pemberitahuan yang jelas di layar pemeriksaan SEB, dan backend menolak masuk ruang ujian. EduAI tidak memakai *screen pinning* sebagai pengganti. Ujian yang tidak mewajibkan SEB tetap bisa diikuti dari Android seperti biasa. Aplikasi kiosk Android untuk perangkat milik sekolah (Lock Task Mode lewat *device owner* atau Android Management API) direncanakan setelah infrastruktur dan perangkat uji tersedia.

**Database.** Saat backend dimulai, migrasi otomatis hanya menambah kolom `seb_status.first_verified_at`, `seb_status.platform`, dan `exam_seb.quit_url`, serta tabel `seb_history`. Bila database lama perlu diubah, backend lebih dulu menyalinnya ke `backend/data/backup/eduai-sebelum-migrasi-<waktu>.sqlite3`. Migrasi ini aman dijalankan berulang: bila semua sudah ada, tidak ada salinan baru dan tidak ada yang diubah.

## Batasan (apa adanya)

- **Lockdown terputus, Quit URL, dan panel lockdown juga belum diuji dengan SEB sungguhan** (Windows, macOS, iPhone/iPad). Nama kunci `quitURL`/`quitURLConfirm` di templat perlu dicocokkan di SEB Config Tool versi yang dipakai.
- **Belum diuji dengan SEB sungguhan.** Uji integrasi memakai Chrome yang meniru SEB: JavaScript API, header, dan user agent dihitung persis menurut spesifikasi. Templat konfigurasi, nama kunci pengaturannya, kamera di dalam SEB, dan Jitsi di dalam SEB belum dicoba di SEB nyata.
- **Config Key bukan rahasia** bagi siapa pun yang memegang berkas `.seb`. Orang yang memegang berkas itu dan mampu menghitung hash-nya bisa meniru jalur JavaScript API. Lindungi berkas `.seb` (enkripsi dengan kata sandi), dan isi Browser Exam Key bila ingin mengikat ke versi SEB tertentu.
- **Hash JavaScript API dapat diputar ulang** karena terikat ke URL halaman yang tetap. Jalur header (bernonce) tidak bisa diputar ulang, tetapi belum dipastikan bahwa SEB mengirim header pada request `fetch` di setiap platform.
- **Pemeriksaan ulang 60 detik** membuat pengawas tahu bila siswa berhenti terverifikasi. Pemeriksaan ini tidak mencegah token login dipakai di browser lain di antara dua pemeriksaan.
- **Kamera di SEB:** halaman `http://` di luar `localhost` tidak mendapat izin kamera, karena bukan *secure context*. Untuk perangkat lain di jaringan, pakai HTTPS.
