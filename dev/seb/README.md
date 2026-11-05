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

## Batasan (apa adanya)

- **Belum diuji dengan SEB sungguhan.** Uji integrasi memakai Chrome yang meniru SEB: JavaScript API, header, dan user agent dihitung persis menurut spesifikasi. Templat konfigurasi, nama kunci pengaturannya, kamera di dalam SEB, dan Jitsi di dalam SEB belum dicoba di SEB nyata.
- **Config Key bukan rahasia** bagi siapa pun yang memegang berkas `.seb`. Orang yang memegang berkas itu dan mampu menghitung hash-nya bisa meniru jalur JavaScript API. Lindungi berkas `.seb` (enkripsi dengan kata sandi), dan isi Browser Exam Key bila ingin mengikat ke versi SEB tertentu.
- **Hash JavaScript API dapat diputar ulang** karena terikat ke URL halaman yang tetap. Jalur header (bernonce) tidak bisa diputar ulang, tetapi belum dipastikan bahwa SEB mengirim header pada request `fetch` di setiap platform.
- **Pemeriksaan ulang 60 detik** membuat pengawas tahu bila siswa berhenti terverifikasi. Pemeriksaan ini tidak mencegah token login dipakai di browser lain di antara dua pemeriksaan.
- **Kamera di SEB:** halaman `http://` di luar `localhost` tidak mendapat izin kamera, karena bukan *secure context*. Untuk perangkat lain di jaringan, pakai HTTPS.
