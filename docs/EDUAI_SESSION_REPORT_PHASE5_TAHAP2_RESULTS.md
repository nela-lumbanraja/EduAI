# Session Report Phase 5, Tahap 2: Pencatatan D4 (Ketersediaan Model per Peserta)

Tanggal: 21 November 2026 · Status: **diterima pemilik proyek (21 November 2026).** Tafsiran poin 7 (bagian 6) diterima: nilai numerik tetap mengikuti rumus Phase 4, indikasi terdampak hanya ditandai `model_unavailable`. K7 tetap terbuka; tidak ada nilai numerik yang diubah berdasarkan status D4 sebelum K7 diputuskan. Risiko R1–R9 (bagian 7) tetap tercatat sebagai catatan terbuka. Database produksi belum dimigrasi. Tahap 3 (mekanisme kalibrasi) menunggu evaluasi ruang lingkup dan persetujuan terpisah; Phase 6 belum dimulai. Tidak ada commit.

Dasar: keputusan S1 dan K4 (deteksi, pencatatan, penanda tanpa mengubah rumus). Audit Tahap 1: `docs/EDUAI_SESSION_REPORT_PHASE5_D4_AUDIT.md`. Cadangan semua file sebelum perubahan: `..\EduAI_cadangan_20261121\phase5_tahap2\`.

---

## 1. Ringkasan

- Tabel baru aditif `model_availability` menyimpan satu baris per ujian, peserta, model, dan sumber (`browser`, `jitsi`, `livekit`).
- Status yang dicatat: `available`, `disabled`, `inference_errors`, `warmup_failed`, `not_loaded`. Status hanya bisa memburuk selama sesi, sehingga kegagalan tetap tercatat sampai finalisasi, juga setelah pemantauan dihentikan atau backend dimuat ulang.
- Model dianggap tersedia hanya bila set model **peserta itu** benar-benar memuatnya, tidak cukup karena backend berhasil start.
- Session Summary (hasil live dan metadata snapshot) memuat blok `model_availability`. Isinya: status `lengkap`, `model_unavailable`, atau `tidak_tercatat`; indikasi terdampak beserta modelnya; dan catatan bahwa skornya tidak dapat dibaca sebagai "tidak terjadi".
- **Rumus Phase 4 tidak berubah.** P_i, P_total, bobot, penyebut, aturan data kosong, dan mekanisme finalisasi tetap sama. Tes membuktikan semua angka identik dengan dan tanpa catatan D4.

## 2. Perubahan file

| File | Perubahan |
|---|---|
| `backend/app/db.py` | Tabel `model_availability` (CHECK status dan sumber, PK ujian–peserta–model–sumber, tanpa FK seperti tabel AI lain). `D4_TABLES` masuk `_pending_migrations`, sehingga database lama dicadangkan otomatis sebelum tabel dibuat. Tidak ada tabel lama yang diubah. |
| `backend/app/model_availability.py` | **Baru.** Pencatat (upsert yang hanya memburuk; galat inferensi dijumlahkan sebagai delta), pemetaan model → indikasi, dan ringkasan untuk Session Summary |
| `backend/app/ai_service.py` | Mencatat status pemuatan set model per peserta sekali per analyser dan sumber, termasuk hasil pemanasan bila set itu set cadangan yang sudah dipanaskan. Mencatat galat inferensi baru setelah setiap frame, juga bila frame gagal (`finally`). Hasil pemanasan set cadangan kini disimpan, tidak lagi dibuang. Penanganan galat tidak berubah: masalah penyimpanan hanya dicatat di log. |
| `backend/app/api.py` | `POST /api/ai/heartbeat` menyimpan `student_models` per peserta (peserta tidak terdaftar diabaikan; tidak pernah menggagalkan heartbeat) |
| `backend/app/schemas.py` | `StudentModelsIn`; `HeartbeatIn.student_models` (opsional, maks. 500 peserta) |
| `backend/app/session_summary.py` | Blok `model_availability` di hasil per peserta, di metadata JSON baris `*` snapshot, dan di `read_snapshot`. Tidak ada perubahan perhitungan. |
| `ai/eduai-ai/src/eduai_ai/perception.py` | Penghitung `inference_errors` per model. Perilaku tetap: galat face/landmark/objek tetap menggagalkan frame (dilempar ulang), galat CLIP tetap dilewati. |
| `ai/eduai-ai/src/eduai_ai/pipeline.py` | `StudentAnalyzer.inference_errors()` dan `warmup_result()` |
| `ai/eduai-ai/src/eduai_ai/livekit_worker.py` | Heartbeat mengirim status model **setiap peserta**, tanpa path berkas, beserta galat inferensi baru. Hanya laporan yang diterima backend yang dianggap terkirim, sehingga tidak ada galat yang terhitung dua kali. Laporan analyser yang berhenti disimpan sampai terkirim. `models` (status set terakhir) tetap dikirim untuk tampilan admin. |
| `ai/eduai-ai/src/eduai_ai/backend_client.py` | Parameter `student_models` pada `heartbeat` |
| `ai/eduai-ai/tests/test_worker.py` | Isi pesan heartbeat yang diharapkan ditambah `student_models: {}`; tanda tangan heartbeat palsu |
| `docs/API.md` | Field heartbeat baru dan blok `model_availability` |
| Tes baru | `backend/tests/test_model_availability.py` (10), `ai/eduai-ai/tests/test_d4_model_availability.py` (5) |

Tidak berubah: `main.py`, frontend, PDF, alert, model, config, dan data historis. Tidak ada backfill.

## 3. Pemetaan model ke indikasi

| Model | Indikasi yang ditandai bila model gagal | Catatan |
|---|---|---|
| Face detector | FACE_ABSENT, MULTIPLE_PERSONS, HEAD_TURN, PHONE_VISIBLE, BOOK_VISIBLE, OTHER_VOICE | Tanpa face detector, frame tidak teramati sama sekali (cakupan turun); tetap ditandai |
| Face landmarker | HEAD_TURN, OTHER_VOICE | OTHER_VOICE memerlukan gerak mulut dari landmarker |
| Object detector | PHONE_VISIBLE, MULTIPLE_PERSONS, BOOK_VISIBLE | |
| CLIP | BOOK_VISIBLE | |
| YAMNet (browser) | — | Tidak masuk tabel ini. Tanpa sampel audio sudah ditangani T1 (`no_audio_data`). |

Hanya indikasi yang benar-benar dinilai untuk peserta itu yang ditandai. Indikasi yang sudah dikecualikan (tanpa persetujuan audio, config, `no_audio_data`) tidak ikut.

## 4. Hasil migrasi (salinan database produksi)

Skrip uji hanya **menyalin** berkas database produksi ke folder sementara. Hash berkas produksi sama sebelum dan sesudah uji.

| Langkah | Hasil |
|---|---|
| 0. Salinan dibawa ke keadaan Phase 4 (kode sebelum Tahap 2) | +3 tabel Session Report, tabel lama utuh, integrity ok |
| 1. Migrasi Tahap 2 | Cadangan otomatis dibuat. Tabel baru hanya `model_availability` (0 baris). Isi semua tabel lama sama (hash isi per tabel). integrity ok, foreign key ok. |
| 2. Isi cadangan otomatis | Sama persis dengan keadaan sebelum migrasi (25 tabel) |
| 3. Dibuka ulang | Tidak ada cadangan baru dan tidak ada perubahan (idempoten) |
| 4. Pemulihan A: kode lama membuka DB termigrasi | Berjalan normal (440 kejadian), tabel lama utuh |
| 5. Pemulihan B: `DROP TABLE model_availability` | Sama persis dengan sebelum migrasi |
| 6. Pemulihan C: salin balik cadangan otomatis | Sama persis dengan sebelum migrasi |
| 7. Produksi saat ini langsung ke kode baru | +4 tabel (3 Session Report + `model_availability`), tabel lama utuh, cadangan otomatis dibuat |

**Database produksi belum dimigrasi.** Migrasi terjadi otomatis saat backend dengan kode baru dijalankan, didahului cadangan otomatis di `backend/data/backup/`. Ini sama dengan status Phase 2 (R5): tabel Session Report juga belum ada di produksi.

## 5. Hasil tes

**Tes penerimaan D4 (rencana tes 12): 15 baru, semua lulus**

| Tes | Hasil |
|---|---|
| Tabel dan CHECK | Kolom sesuai; status tidak dikenal ditolak |
| Pemetaan status | Termuat → `available`; file/paket/galat → `not_loaded`; dimatikan → `disabled`; pemanasan gagal → `warmup_failed` |
| Hanya memburuk | Setelah `not_loaded`, set sehat berikutnya tidak menghapusnya; galat dijumlahkan (2 + 1 = 3); model dan sumber tak dikenal diabaikan |
| Ringkasan | Tanpa catatan → `tidak_tercatat`; semua tersedia → `lengkap`; landmarker gagal pemanasan dan CLIP galat → HEAD_TURN dan BOOK_VISIBLE ditandai; OTHER_VOICE ikut bila dinilai; peserta lain tidak terpengaruh |
| Analyser backend | Object detector `not_loaded`, landmarker `warmup_failed`, CLIP `inference_errors` = 2, face detector `available`, sumber `browser` |
| Frame gagal | Galat face detector tetap menggagalkan frame (perilaku lama) dan tercatat (`inference_errors` = 1) |
| **Skor tidak berubah** | Sesi yang sama dihitung dengan dan tanpa catatan D4. Cakupan, Σw, interval, alasan, `excluded`, semua P_i, dan P_total **identik**; FACE_ABSENT tetap 0,125. Hanya blok `model_availability` yang berbeda. |
| Live → final | `model_unavailable` muncul di live dan tetap ada di snapshot final dengan indikasi terdampak yang sama. P_total final = live. Kalibrasi `not_calibrated`, probabilitas `null`. Jumlah baris snapshot sama dengan Phase 4. Catatan baru setelah final tidak mengubah hasil (beku). |
| Bertahan | Setelah pemantauan berhenti (analyser dihapus) dan backend dimuat ulang, status tetap `model_unavailable` |
| Heartbeat worker | Semua peserta tercatat dengan sumber `livekit`; delta galat dijumlahkan; peserta tidak terdaftar diabaikan; worker lama tanpa field diterima; lebih dari 500 peserta → 422 |
| Penghitung perception (model nyata) | Galat object detector: frame tetap gagal, terhitung 1. Galat CLIP: frame tetap jalan, skor CLIP kosong, terhitung 1. |
| Laporan worker | Setiap peserta dilaporkan dan tidak ada path berkas. Galat dikirim sekali; dikirim ulang bila heartbeat gagal; analyser yang berhenti saat heartbeat sedang dikirim tidak terhitung dua kali. |

**Regresi**

| Paket | Hasil |
|---|---|
| Backend | **338 lulus**, 0 gagal, 2 dilewati (328 + 10 baru) |
| Modul AI | **127 lulus**, 2 dilewati (122 + 5 baru); satu tes lama disesuaikan karena isi heartbeat bertambah |
| Frontend | Tidak diubah |
| Data produksi | Hash 1.837 file `backend/data` sama dengan manifest Phase 2: 0 hilang, 0 baru, 0 berubah |

## 6. Tafsiran poin 7 persetujuan

Poin 7 meminta skor tidak "menjadi 0 dengan cakupan penuh" bila model tidak tersedia, sedangkan poin 6 dan K7 melarang perubahan rumus. Yang saya terapkan:
- nilai P_i tetap dihitung dengan rumus Phase 4;
- indikasi itu ditandai `model_unavailable` (model dan alasannya) di hasil live dan snapshot, dengan catatan bahwa skornya tidak dapat dibaca sebagai "tidak terjadi";
- sesi itu tidak akan pernah diberi probabilitas kalibrasi (Tahap 3).

Apakah nilai angka itu nanti diganti (misalnya dikecualikan atau dikosongkan) adalah keputusan K7, yang belum disetujui.

## 7. Risiko yang masih terbuka

| ID | Hal | Catatan |
|---|---|---|
| R1 | Migrasi produksi | Belum dijalankan; terjadi saat backend baru start, dengan cadangan otomatis (teruji di salinan) |
| R2 | Set model baru per peserta tidak dipanaskan | Hanya set cadangan yang dipanaskan. Model yang termuat tetapi rusak baru terlihat sebagai `inference_errors` pada frame pertama, tidak sebagai `warmup_failed`. Worker tidak memanaskan set per peserta. Perilaku analisis tidak saya ubah. |
| R3 | Set cadangan yang gagal pemanasan tetap diberikan ke peserta | Kini **tercatat** (`warmup_failed`), tetapi tetap dipakai. Membuangnya adalah perubahan perilaku analisis di luar persetujuan ini. |
| R4 | Penandaan konservatif | Satu galat inferensi saja sudah menandai indikasi terkait, termasuk galat face/landmark/objek yang sebenarnya gagal tertutup (detiknya tidak teramati). Jumlah galat tercatat untuk penilaian. |
| R5 | Celah waktu laporan worker | Galat ditahan worker sampai heartbeat berikutnya (±5 dtk). Bila worker mati mendadak (dibunuh) sebelum heartbeat terkirim, galat terakhir hilang; status pemuatan sudah terkirim di heartbeat sebelumnya. |
| R6 | Heartbeat diproses tetapi balasannya hilang | Worker mengirim ulang delta yang sama, sehingga jumlah galat bisa terhitung lebih; status tidak terpengaruh |
| R7 | Sesi lama | Tanpa backfill: semua sesi sebelum perubahan ini berstatus `tidak_tercatat` |
| R8 | Tampilan | Blok D4 tersedia di API dan snapshot; penyajian di PDF dan frontend adalah Phase 6 |
| R9 | K7 | Perlakuan angka skor indikasi terdampak belum diputuskan (bagian 6) |

Catatan kecil: skrip uji migrasi memuat `db.py` lama dari folder cadangan, sehingga Python membuat berkas cache `__pycache__/db.cpython-314.pyc` di folder cadangan itu. Berkas cadangan aslinya tidak berubah.
