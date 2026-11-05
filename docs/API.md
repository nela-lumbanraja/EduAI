# EduAI API (backend FastAPI)

Base URL saat pengembangan: `http://localhost:8000` (frontend memanggil `/api/...` lewat proxy Vite).
Dokumentasi interaktif otomatis: `http://localhost:8000/docs` (OpenAPI/Swagger).

## Autentikasi dan otorisasi

| Pemanggil | Mekanisme | Catatan |
|---|---|---|
| Pengguna (siswa, pengawas, penyelenggara, admin, sekolah) | `Authorization: Bearer <JWT>` dari `POST /api/auth/login` | HS256, masa berlaku `EDUAI_JWT_TTL_MIN` (default 480 menit). Token tidak pernah dikirim lewat URL, sehingga tidak tercatat di access log. |
| AI worker OpenVidu | Header `X-AI-Service-Key: <EDUAI_AI_SERVICE_KEY>` | Hanya untuk `/api/ai/events`, `/api/ai/evidence`, `/api/ai/status`, `/api/ai/heartbeat`. Dibandingkan secara constant-time. |

Aturan peran (diterapkan di `backend/app/api.py`):

- **siswa**: hanya ujian yang ia ikuti; persetujuan, join, presence, unggah frame. Tidak pernah bisa membaca status AI, indikasi, atau evidence.
- **pengawas**: hanya ujian dengan `supervisor_id` = dirinya. Pemantauan, indikasi, gambar evidence, validasi, catatan manual.
- **admin**: semua ujian, termasuk gambar evidence; juga membuat ujian dan membaca audit log.
- **penyelenggara**: semua ujian, tanpa gambar evidence.
- **sekolah**: daftar sesi, laporan, dan **hanya indikasi yang sudah divalidasi**, tanpa gambar evidence, video langsung, dan status AI real-time.

Gambar evidence hanya untuk pengawas yang ditugaskan di ujian itu dan admin. Aturan ini satu fungsi (`_can_open_evidence`) untuk `/api/evidence`, `/api/report-frames`, dan gambar di PDF. Penolakan menjawab 403 dan dicatat di audit (`Akses gambar bukti ditolak`, status `Ditolak`). Pencabutan akses penyelenggara dan sekolah dicatat sekali sebagai baris audit baru saat backend mulai; baris lama tidak diubah.

CORS: origin dari `EDUAI_CORS_ORIGINS` (default `http://localhost:5173`), metode GET/POST/PATCH, header `Authorization`, `Content-Type`.

Format galat: `{"detail": "<pesan dalam Bahasa Indonesia>"}` atau, untuk validasi body (422), `{"detail": [{"loc": [...], "msg": "..."}]}`.

| Kode | Arti |
|---|---|
| 400 | Permintaan tidak sesuai aturan (mis. memvalidasi kejadian `cannot_analyze`) |
| 401 | Token/kunci layanan tidak ada, salah, atau kedaluwarsa |
| 403 | Peran tidak berwenang atau sesi bukan milik pengawas |
| 404 | Data tidak ditemukan |
| 409 | Status tidak memungkinkan (ujian belum berlangsung, belum ada persetujuan) |
| 409 | Konflik keadaan, misalnya laporan sudah final atau belum semua indikasi ditinjau |
| 410 | Evidence atau gambar bukti laporan sudah melewati masa simpan dan dihapus |
| 413 / 415 | Frame terlalu besar / bukan JPEG |
| 422 | Body tidak valid (skema) |
| 429 | Terlalu banyak percobaan login (5 gagal per 5 menit per email) |
| 503 | Layanan AI atau kunci layanan belum dikonfigurasi |

## Ringkasan endpoint

| Metode & path | Peran | Fungsi |
|---|---|---|
| `GET /api/health` | publik | Status backend, AI tersedia/tidak, OpenVidu terkonfigurasi/tidak |
| `GET /api/ai/health` | publik | Kesiapan model per komponen, retensi evidence, worker aktif |
| `POST /api/auth/login` | publik | Login → `{token, user}` |
| `POST /api/auth/register` | publik | Daftar mandiri **khusus siswa** (dapat dimatikan) |
| `GET /api/auth/me` | semua | Profil pengguna |
| `GET /api/users?role=` | admin, penyelenggara | Daftar pengguna |
| `GET /api/dashboard` | semua | Ringkasan sesuai peran |
| `GET /api/exams` · `POST /api/exams` | semua · admin | Daftar (difilter peran) · buat ujian |
| `GET /api/exams/{id}` · `PATCH /api/exams/{id}` | sesuai akses · admin, penyelenggara | Detail · ubah status |
| `GET /api/exams/{id}/students` | staf | Peserta + presence + status AI + jumlah indikasi |
| `GET /api/exams/{id}/students/{sid}/timeline` | pengawas, penyelenggara, admin | Linimasa siswa |
| `POST /api/exams/{id}/consent` | siswa | Persetujuan perekaman |
| `POST /api/exams/{id}/join` | siswa / staf pemantau | Token ruang OpenVidu + info pemantauan. Siswa: 403 bila ujian mewajibkan Safe Exam Browser dan belum terverifikasi (lihat bagian Safe Exam Browser). |
| `GET /api/exams/{id}/session-state` | siswa | Status ujian & pemantauan (dipoll tiap 5 dtk) |
| `POST /api/exams/{id}/presence` | siswa | Heartbeat kamera/mikrofon/koneksi |
| `POST /api/exams/{id}/leave` | siswa | Keluar; analisis siswa dihentikan dan kejadian terbuka ditutup |
| `POST /api/exams/{id}/frames` | siswa | **Jalur frame browser**: satu JPEG |
| `POST /api/exams/{id}/monitoring/start` · `/stop` · `GET .../monitoring` | pengawas, penyelenggara, admin | Mulai/hentikan analisis AI, status worker |
| `GET /api/exams/{id}/events` | staf | Kejadian AI per ujian (`student_id`, `category`, `since`, `review`, `limit`) |
| `GET /api/events` | staf | Kejadian dari semua ujian yang boleh diakses (notifikasi, halaman Indikasi) |
| `GET /api/events/{event_id}` | staf | Detail + riwayat validasi |
| `POST /api/events/{event_id}/reviews` | pengawas, penyelenggara, admin | Keputusan: Valid / Tidak Valid / Perlu Tinjauan Lanjut |
| `POST /api/exams/{id}/audio` | siswa (dengan persetujuan suara) | Tiga skor YAMNet dari browser siswa: `speech`, `whisper`, `media` (0–1). Tanpa audio |
| `GET /api/ai/models/yamnet.tflite` | publik | File model YAMNet (Google, AudioSet) untuk browser siswa |
| `GET /api/cases` · `GET /api/exams/{id}/cases` | staf | Kasus = indikasi berulang yang dikelompokkan (filter `review`, `student_id`, `exam_id`). Lihat "Pengelompokan kasus" |
| `GET /api/cases/{case_id}` | staf | Ringkasan kasus + semua kejadian aslinya (skor, alasan, `evidence_id`, riwayat validasi) |
| `POST /api/cases/{case_id}/reviews` | pengawas, penyelenggara, admin | Satu keputusan untuk kejadian yang dilihat (`event_ids`); dicatat sebagai validasi biasa per kejadian |
| `POST /api/exams/{id}/notes` | pengawas, penyelenggara, admin | Catatan manual |
| `GET /api/evidence/{id}` | pengawas yang ditugaskan, admin | Metadata evidence (diaudit) |
| `GET /api/evidence/{id}/frames/{i}` | idem | Satu JPEG evidence (`Cache-Control: no-store`) |
| `GET /api/jitsi/config` | semua pengguna | Server Jitsi: `configured`, `domain`, `operator` (`school` / `third_party`), `xmpp_domain`, `muc`, `service_url`, `auth` (server memakai token). Tanpa nama ruang ujian dan tanpa rahasia. |
| `GET /api/jitsi/health` | semua pengguna | `{state}`: `not_configured` / `unreachable` / `ready`. Admin juga menerima `missing` (variabel kosong), `examples`, dan `detail` (alasan teknis). Diperiksa ke `https://<domain>/libs/lib-jitsi-meet.min.js`, batas waktu 2,5 dtk, disimpan 15 dtk. |
| `POST /api/jitsi/meeting-token` | semua pengguna | Body `{room}` (huruf kecil, angka, `-`, maks 64). Mengembalikan `{room, token}`; `token` null bila server tanpa JWT. Nama ruang ujian (`eduai-exam-...`) ditolak 403 dan diaudit. |
| `GET /api/exams/{id}/jitsi/watch` | pengawas yang ditugaskan, admin | Video langsung: `{server, rooms: [{student_id, name, room, token}]}` untuk siswa yang sudah memberi persetujuan, hanya saat pemantauan berjalan dengan sumber `jitsi` (selain itu `rooms: []`). Peran lain 403 dan diaudit. Pemakaian diaudit sekali per 5 menit. |
| `GET /api/sessions/{id}/report` (juga `/api/exams/{id}/report`) | staf | Info sesi, kehadiran, ringkasan indikasi, semua kejadian, status final. Sekolah: hanya yang sudah ditinjau, tanpa gambar |
| `PATCH /api/events/{event_id}/review` | pengawas sesi, admin | Ubah status dan/atau catatan dari tabel laporan; mengembalikan baris dan ringkasan baru |
| `GET /api/report-frames/{event_id}?sig=...` | URL bertanda tangan (5 menit) | Satu JPEG gambar bukti (`no-store`, diaudit) |
| `POST /api/sessions/{id}/finalize` | pengawas sesi, admin | Mengunci data sesi dan menyalin gambar bukti |
| `GET /api/sessions/{id}/report.pdf` | staf | PDF "Laporan Hasil Pengawasan Ujian"; gambar hanya untuk pengawas sesi dan admin; tanda DRAF sebelum final |
| `GET /api/sessions/{id}/report.xlsx` | staf | Excel berisi tabel indikasi, tanpa gambar |
| `GET /api/audit` | admin | Audit log |
| `POST /api/ai/infer` | admin, penyelenggara | Inferensi 1–10 gambar (debug; tidak disimpan) |
| `POST /api/ai/events` · `/evidence` · `/status` · `/heartbeat` | AI worker (service key) | Hasil dari worker OpenVidu |

## Analisis suara opsional (indikator `OTHER_VOICE`)

- **Opsional dan terpisah dari persetujuan utama.** `POST /exams/{id}/consent` menerima `audio: true|false`
  (bawaan `false`, kolom `consents.audio_accepted`). Siswa tetap bisa ujian tanpa analisis suara.
- **Audio tidak pernah keluar dari perangkat siswa.** YAMNet (MediaPipe Audio Classifier, 521 kelas AudioSet)
  berjalan di browser lewat WebAssembly. Setiap 0,5 detik browser mengirim tiga angka:
  `speech` (Speech/Conversation/Narration/Babbling/Child speech), `whisper` (Whispering), `media`
  (Music/… music/Television/Radio). Tidak ada rekaman, file audio, atau transkrip.
- Backend menggabungkan skor dengan gerak mulut (`jawOpen` dari Face Landmarker pada frame video) dan memberi
  **jenis suara**. Pada satu saat paling banyak satu jenis aktif, dengan urutan pemeriksaan:

  | Jenis suara (`details.sound_type`) | Indikator | Syarat (nilai sementara, `config.yaml`) | Kategori bawaan |
  |---|---|---|---|
  | `MUSIK_MEDIA` | `MEDIA_SOUND` | media ≥ 0,30 dan ≥ speech dan whisper; ≥ 3 dtk, cooldown 60 dtk; tidak perlu wajah | `info` (dapat diubah ke `indication`) |
  | `BISIKAN` | `WHISPER` | whisper ≥ 0,20 dan > speech; ≥ 2 dtk, cooldown 30 dtk | `indication` (dapat diubah ke `info`) |
  | `BICARA_MULUT_DIAM` | `OTHER_VOICE` | speech ≥ 0,30, tepat satu wajah, rentang `jawOpen` 2 dtk < 0,08; ≥ 2 dtk, cooldown 30 dtk | `indication` |
  | `BICARA_SISWA` | `STUDENT_SPEECH` | speech ≥ 0,30, tepat satu wajah, rentang `jawOpen` ≥ 0,08; ≥ 2 dtk, cooldown 60 dtk | selalu `info` |

- Kategori **`info`**: dicatat sebagai konteks saja. Tidak dihitung sebagai indikasi, tidak punya gambar bukti, tidak
  memunculkan pop-up atau kasus, dan tidak dapat divalidasi. Tampil di daftar aktivitas, linimasa (`kind: "info"`),
  dan laporan (`sound_info`). `GET /events?category=info` menyaringnya.
- Setiap kejadian suara menyimpan `details = {sound_type, speech, whisper, media, mouth_movement}`, yaitu skor puncak
  episode itu (bukan audio). Respons kejadian dan linimasa menambah `sound_text`, misalnya
  "Jenis suara: bicara saat mulut siswa diam (speech 0,82, whisper 0,00, media 0,05)". Teks ini tampil di Detail
  Evidence, Laporan Sesi, PDF, dan Excel. `POST /api/ai/events` menolak (422) `sound_type` di luar empat nilai di atas,
  kunci tambahan pada `details`, `STUDENT_SPEECH` selain `info`, dan indikator lain berkategori `info`.
- **Tidak didukung, dan sengaja tidak dibuat:**
  - **Pengenalan suara orang (siapa yang bicara).** Ini butuh sidik suara (data biometrik) setiap siswa, rekaman
    pendaftaran, dan audio yang dikirim atau disimpan. Semua itu bertentangan dengan prinsip "audio tidak keluar dari
    perangkat". Selain itu, kesalahan identifikasi berdampak serius bagi siswa.
  - **Penghitungan jumlah pembicara.** YAMNet hanya menilai jenis suara per potongan 1 detik, bukan siapa atau berapa
    orang. Diarization (memisahkan pembicara) butuh model lain dan audio utuh, serta tidak andal untuk mikrofon laptop
    di ruangan bergema. Jadi `BICARA_MULUT_DIAM` hanya berarti "ada suara bicara, dan mulut siswa tampak diam". Itu
    tidak membuktikan ada orang lain: bisa juga video, panggilan, atau gema.
- Berjalan pada sumber `browser` dan `jitsi`. Mode worker OpenVidu belum: relay skor belum diport. Dimatikan total
  dengan `EDUAI_AUDIO_ANALYSIS=false`.
- `join` / `session-state` mengembalikan `monitoring.audio = {available, consented, reason, model_url, interval_ms}`;
  `GET /exams/{id}/students` menambah `audio = {consented, active, reason}` untuk pengawas. `active` = skor suara
  benar-benar diterima dalam 5 detik terakhir (bukan sekadar mikrofon menyala). `reason` (null bila aktif):
  `not_consented`, `monitoring_off`, `disabled` (`EDUAI_AUDIO_ANALYSIS=false`/`OTHER_VOICE` mati), `ai_unavailable`,
  `model_missing` (`models/yamnet.tflite` tidak ada), `worker_mode` (mode worker OpenVidu: analisis suara tidak
  tersedia; relay skor ke worker belum diport), `mic_off`, `no_scores` (diizinkan, tetapi browser siswa tidak mengirim skor: model masih dimuat atau gagal).

## Pengelompokan kasus (tampilan dan validasi; deteksi AI tidak berubah)

- Satu kasus = kejadian `category='indication'` dengan **ujian, siswa, dan jenis indikator yang sama** untuk seluruh
  ujian (default `EDUAI_CASE_GAP_S=0`: satu indikasi terkonsolidasi per siswa dan perilaku). Opsional
  `EDUAI_CASE_GAP_S > 0`: kasus dipecah bila jarak (selesai → mulai berikutnya) lebih dari nilai itu (perilaku lama, dulu 120).
  Ujian, siswa, atau indikator berbeda tidak pernah digabung (`HEAD_TURN` dan `HEAD_TURN_REPEATED` juga terpisah).
- Satu kejadian = satu episode yang memenuhi aturan temporal AI (frame berulang tidak dihitung). Kejadian satu kasus yang
  tumpang-tindih atau berjarak ≤ 2 dtk (mis. worker dimulai ulang, frame cadangan browser) dihitung **satu** episode:
  `episode_count`, `episodes[] = {start_ts, end_ts, event_ids, evidence_id, duration_s}`; `event_count` tetap jumlah baris asli.
- `rule = {min_count, window_s, met, met_at, max_in_window}` dari `config.yaml → summary_rules` (nilai awal produk, belum
  divalidasi): ponsel, orang kedua, suara, wajah hilang, menoleh lama = 1 episode; `HEAD_TURN_REPEATED` = 4 episode dalam
  3600 dtk; `BOOK_VISIBLE` = 3 episode dalam 3600 dtk. Bila `BOOK_VISIBLE` dimatikan atau detektor objek tidak dimuat, ringkasan ujian mencantumkan buku di `unsupported`. Kasus selalu tampil; pop-up pengawas muncul **sekali per kasus**, saat
  `rule.met` pertama kali benar. Kejadian berikutnya hanya menambah hitungan.
- Kasus dihitung ulang dari tabel `events` setiap permintaan; tidak ada baris yang diubah atau dihapus.
  `case_id = "c-" + event_id` kejadian pertama (tetap sama saat kejadian baru masuk).
- `review_status` kasus: `null` bila masih ada kejadian belum ditinjau (`unreviewed_count > 0`); keputusan itu bila semua
  kejadian sama; `"Campuran"` bila semua sudah ditinjau dengan keputusan berbeda.
- Validasi kasus menulis satu baris `reviews` per kejadian (keputusan dan catatan sama) dan satu entri audit.
  Hanya `event_ids` yang dikirim (yang dilihat peninjau) yang ditinjau. Kejadian yang masuk kemudian **tetap belum
  ditinjau**; tidak pernah mewarisi keputusan. `event_ids` di luar kasus → 409.
- Hak akses sama dengan `/api/events/{id}`: pengawas hanya ujian yang ditugaskan, siswa 403, sekolah hanya kejadian yang
  sudah divalidasi dan tidak dapat memvalidasi.
- `GET /api/dashboard` menambah `summary.cases_total`, `summary.cases_unreviewed`, `summary.detections_total`, dan
  `recent_cases`; field lama tidak berubah.

## Ringkasan ujian terkonsolidasi (app/summary.py)

- Dibuat **oleh backend** (loop pemeliharaan tiap 30 dtk dan saat start), bukan timer browser. Satu ringkasan per ujian:
  tabel baru `exam_summaries` (`exam_id` PRIMARY KEY, `INSERT OR IGNORE`) → restart backend, pemeriksaan berulang, atau
  banyak dasbor tidak dapat membuat duplikat. Tabel lain tidak diubah.
- `pre_end`: saat sisa ≤ 10 menit sebelum jadwal selesai (`date` + `start_time` + `duration_min`, dibaca ulang tiap
  pemeriksaan sehingga perubahan jadwal ikut terbaca sampai ringkasan dibuat). Waktu ujian = waktu lokal server, atau
  `EDUAI_TIMEZONE` (IANA; di Windows butuh `pip install tzdata`).
- `final`: saat/setelah jadwal selesai atau saat status ujian diubah ke "Selesai", bila `pre_end` belum ada (mis. ujian
  ditutup lebih awal, atau pemantauan baru dimulai < 10 menit sebelum selesai → tidak ada ringkasan prematur).
- Tanpa jadwal yang terbaca: tidak ada ringkasan terjadwal; hanya `final` saat ujian ditutup. Ujian yang pemantauan AI-nya
  tidak pernah dimulai tidak mendapat ringkasan.
- Isi: per siswa terdaftar → per indikator `{occurrences (episode), events, first_ts, last_ts, episodes[], evidence_count,
  unreviewed, rule}`, `cannot_analyze {periods, total_s}` (terpisah, bukan perilaku), `analysis` (`analysed`/`no_data`),
  `unsupported` (perilaku tanpa detektor), `note` (indikasi potensial, bukan bukti pelanggaran).
- `GET /api/summaries` (pengawas, penyelenggara, admin): ringkasan yang sudah dibuat → frontend menampilkan satu pop-up per
  ringkasan dan satu item lonceng per siswa. `GET /api/exams/{id}/summary`: ringkasan tersimpan, atau pratinjau langsung
  (`preview: true`, tidak disimpan, tanpa notifikasi) beserta `scheduled_at`. Siswa dan sekolah: 403.

## Sumber analisis dan mode Jitsi

**Token Jitsi (JWT, HS256)**, ditandatangani dengan `EDUAI_JITSI_APP_SECRET`: `iss` dan `aud` = `EDUAI_JITSI_APP_ID`, `sub` = domain XMPP, `room` = **satu** nama ruang (tidak pernah `*`), `exp` 4 jam, `moderator: false`, `context.user {id, name}`, dan `context.features` rekaman/streaming/transkripsi `false`. Server Jitsi yang memakai `ENABLE_AUTH=1, AUTH_TYPE=jwt` menolak koneksi tanpa token (`passwordRequired`) dan token untuk ruang lain (`notAllowed`).

`POST /api/exams/{id}/monitoring/start` menerima `{"source": "browser" | "livekit" | "jitsi"}` dan hanya untuk pengawas, penyelenggara, dan admin. Tanpa `source`, dipakai `EDUAI_ANALYSIS_SOURCE`. Nilai tersimpan di `exams.analysis_source` dan muncul sebagai `source` di `GET /api/exams/{id}/monitoring`, serta di `ai_status` dan kejadian. Di layar `livekit` tampil sebagai OpenVidu. Pilihan `jitsi` menjawab 409 bila `EDUAI_JITSI_DOMAIN` kosong.

Endpoint frame tidak menerima sumber dari klien: `POST /api/exams/{id}/frames` membaca sumber dari data ujian di server, dan tetap menolak siswa tidak terdaftar (403) serta siswa tanpa persetujuan (409).

- `monitoring.livekit` pada `POST /join` dan `GET /session-state` (siswa saja) berisi `{url, room, token}` untuk menyiarkan ke OpenVidu, atau `null`. Nilainya `null` bila OpenVidu tidak dikonfigurasi **atau** saat mode Jitsi (pemantauan aktif dengan sumber `jitsi`). Pada mode Jitsi, `livekit` di `POST /join` juga `null` untuk siswa dan staf, dengan `livekit_reason` "Mode Jitsi: video langsung lewat Jitsi". Jadi satu ujian hanya punya satu siaran, yaitu yang dianalisis AI.
- `monitoring.jitsi` pada `POST /join` dan `GET /session-state` berisi `{configured, domain, operator, xmpp_domain, muc, service_url, auth, room, token}`. `room` adalah ruang milik siswa itu sendiri (satu ruang per siswa per ujian), dan `token` hanya membuka ruang itu. Hanya terisi untuk siswa terdaftar yang sudah memberi persetujuan, saat pemantauan aktif dengan sumber `jitsi`; selain itu `null`.
- `POST /api/exams/{id}/presence` menerima `jitsi`: `connected` atau `disconnected`. Nilai ini hanya dibaca pada mode Jitsi. Perubahan dicatat dan tampil di linimasa sebagai `kind: "connection"`, bukan indikasi, dan tidak menghentikan analisis.
- Pada mode Jitsi, `camera_on: false` atau tidak ada frame ±8 detik menjalankan pipeline dengan frame kosong, sehingga status menjadi `cannot_analyze` (`reason`: `track_ended` atau `no_frames`).
- `GET /api/exams/{id}/students` menambah `presence.jitsi`; `ai.source` menunjukkan sumber hasil terakhir.
- Analisis suara berjalan juga pada mode Jitsi, karena frame tetap dikirim dari browser siswa. `jitsi_mode` tidak lagi dikembalikan; nilainya hanya tersisa di tipe frontend untuk data lama.

## Safe Exam Browser (app/seb.py)

Hash menurut spesifikasi SEB: `SHA256(URL absolut tanpa fragmen + kunci)`, heksadesimal huruf kecil. Kunci yang diharapkan (Config Key, Browser Exam Key) hanya ada di backend.

| Endpoint | Peran | Keterangan |
|---|---|---|
| `GET /api/exams/{id}/seb` | admin, penyelenggara | `{required, config_keys, browser_exam_keys, config_url, ready, allowed_origins, updated_at, updated_by}`. Peran lain 403. |
| `PUT /api/exams/{id}/seb` | admin, penyelenggara | Body `{required, config_keys[], browser_exam_keys[], config_url}`. Kunci harus 64 karakter heksadesimal (422 bila tidak). `required: true` tanpa kunci ditolak 422. Perubahan diaudit (jumlah kunci, tanpa nilainya). |
| `POST /api/exams/{id}/seb/challenge` | siswa terdaftar | `{nonce, ttl_s: 120}`. Nonce sekali pakai, terikat ke siswa dan ujian. |
| `POST /api/exams/{id}/seb/verify?n=<nonce>` | siswa terdaftar | Body `{nonce, page_url, request_url, config_key, browser_exam_key, version}`, diisi dari `window.SafeExamBrowser`. Header `X-SafeExamBrowser-ConfigKeyHash` / `-RequestHash` dibaca dari request ini, dengan URL = `request_url`, yang path dan query-nya harus sama dengan request ini. Hasil: `{required, state, method: "header" \| "js" \| null, verified, message}`. `state`: `verified`, `not_seb`, `key_mismatch`, `url_mismatch`, `not_configured`. Nonce tidak sah atau sudah dipakai: 409. Ujian tanpa kewajiban SEB: `{required: false, verified: true}`. |

- **Asal halaman yang diterima** (`page_url`, `request_url`) diatur lewat `EDUAI_SEB_ALLOWED_ORIGINS`. Bila kosong, dipakai `EDUAI_CORS_ORIGINS`.
- **Bila kedua jenis kunci diisi**, keduanya harus cocok. Untuk satu jenis, cukup salah satu kunci dalam daftarnya yang cocok.
- **`POST /api/exams/{id}/join`** untuk siswa menjawab 403 bila ujian mewajibkan SEB dan tidak ada hasil `verified` dalam 180 detik terakhir. Penolakan ini diaudit.
- **`GET /api/exams` dan `GET /api/exams/{id}`** menambah `seb: {required, ready, config_url}` untuk semua peran, tanpa kunci.
- **`GET /api/exams/{id}/students`** (pengawas, penyelenggara, admin) menambah `seb: {required, state, method, version, checked_at, fresh}` per siswa. `fresh` bernilai true bila hasil terakhir `verified` dan berumur ≤ 180 detik.
- **Audit:** verifikasi diaudit hanya saat hasilnya berubah ("Safe Exam Browser terverifikasi", atau "Verifikasi Safe Exam Browser gagal (<state>)" dengan status `Ditolak`).

## Laporan sesi (app/report.py, app/report_export.py)

"Sesi" adalah `exam`, jadi `{id}` sama dengan id ujian. Catatan AI hanya penanda hal yang perlu diperiksa, bukan bukti pelanggaran (`ai_notice`).

`GET /api/sessions/1/report` →

```json
{
  "exam": {"id": 1, "name": "Ujian Akhir Matematika XI"},
  "attendance": {"enrolled": 6, "joined": 5, "not_joined": 1},
  "absent": ["Gilang Ramadhan"],
  "indications": {"total": 3, "valid": 1, "invalid": 1, "further": 1, "unreviewed": 0, "cannot_analyze": 2, "cannot_analyze_s": 84.5},
  "events": [{
    "event_id": "9f2c...", "student": {"name": "Alya Putri"}, "label": "Wajah tidak terlihat", "start_ts": "2026-11-02T02:07:48+00:00",
    "review_status": "Valid", "last_review": {"decision": "Valid", "note": "Keluar bingkai", "reviewer": "Rina Setiawati"},
    "evidence": {"state": "available", "url": "/api/report-frames/9f2c...?sig=..."}
  }],
  "final": {"finalized_at": "2026-11-02T03:00:00+00:00", "finalized_by": "Rina Setiawati"},
  "can_edit": false,
  "ai_notice": "...", "retention_text": "Gambar bukti sudah dihapus sesuai kebijakan retensi", "frame_retention_hours": 24.0,
  "activity": []
}
```

- `evidence.state`: `available`, `deleted` (dihapus retensi), atau `none` (tidak pernah ada gambar). `url` hanya terisi untuk pengawas sesi dan admin. `can_view_evidence` menyatakan hal yang sama untuk seluruh laporan, dan `restricted_text` adalah keterangan untuk peran lain; PDF dan Excel memakai keterangan yang sama.
- Gambar diambil dari sumber yang sama dengan Lihat Evidence (frame kunci, satu per kejadian), atau dari salinannya setelah final.
- `PATCH /api/events/{event_id}/review` menerima `{"decision": "Tidak Valid", "note": "..."}`; keduanya opsional, tetapi kejadian yang belum punya status wajib menyertakan `decision` (400). Peninjauan bersifat tambah-saja, jadi riwayat keputusan tetap tersimpan. Hasil: `{"event": {...}, "indications": {...}}`.
- **URL gambar**: JWT dengan kunci turunan terpisah dari token sesi, berisi pengguna, kejadian, dan masa berlaku 5 menit. Peran, status akun, dan penugasan diperiksa ulang tiap permintaan. Galat: 403 tidak valid, kedaluwarsa, atau izin hilang; 410 gambar sudah dihapus. URL kedaluwarsa diperbarui dengan memuat ulang laporan.
- **Finalisasi** menjawab 409 bila ada indikasi belum ditinjau, pemantauan masih aktif, ada kejadian terbuka, atau laporan sudah final. "Perlu Tinjauan Lanjut" dihitung sudah ditinjau. Finalisasi tidak dapat dibatalkan.
- Setelah final, semua penulisan untuk sesi itu menjawab 409: `PATCH /events/.../review`, `POST /events/.../reviews`, `POST /cases/.../reviews`, `POST /exams/.../notes`, `POST /exams/.../monitoring/start`, `POST /ai/evidence`. `POST /ai/events` menaruh kejadian itu di `rejected`.
- **Retensi**: lihat README, bagian Privasi & keamanan. `GET /api/ai/health` memuat `evidence_hold_days` dan `report_frame_retention_hours`.

## Skema kejadian AI (schema 1.0, URS A-03)

Dikirim AI dua kali dengan `event_id` yang sama: saat terbuka (`status: "open"`) dan saat selesai (`status: "closed"`). Backend memperbarui satu baris.

| Field | Tipe | Keterangan |
|---|---|---|
| `event_id` | string (UUID) | Kunci idempoten |
| `session_id` | string | ID ujian EduAI |
| `student_id` | string | ID pengguna siswa |
| `indicator` | enum | `FACE_ABSENT`, `MULTIPLE_PERSONS`, `HEAD_TURN`, `HEAD_TURN_REPEATED`, `PHONE_VISIBLE`, `CANNOT_ANALYZE` |
| `category` | enum | `indication` (perlu ditinjau manusia) atau `cannot_analyze` (kualitas video kurang). `CANNOT_ANALYZE` wajib `cannot_analyze`; indikator lain wajib `indication`. |
| `status` | enum | `open` / `closed` |
| `start_ts`, `end_ts` | ISO-8601 UTC | Waktu mulai (sudah termasuk durasi minimum aturan) dan selesai |
| `score` | number 0–1 / null | Hanya untuk deteksi objek (ponsel). Aturan durasi tidak punya skor. |
| `reason` | string | Penjelasan singkat Bahasa Indonesia |
| `label` | string | Label tampilan |
| `evidence_id` | string / null | Diisi backend setelah evidence tersimpan |
| `model_version`, `config_version`, `schema_version` | string | Jejak versi untuk audit |

Contoh nyata dari uji E2E (jalur frame browser, model BlazeFace):

```json
{
  "event_id": "e68a5f2d-1456-40ef-8424-249eda4bb66c",
  "exam_id": 1,
  "student_id": 1,
  "indicator": "FACE_ABSENT",
  "category": "indication",
  "status": "closed",
  "start_ts": "2026-10-13T03:33:09.903070+00:00",
  "end_ts": "2026-10-13T03:33:18.904459+00:00",
  "score": null,
  "reason": "Wajah tidak terlihat di kamera selama 9.0 detik",
  "label": "Wajah tidak terlihat",
  "evidence_id": "pxAmBrzYPgwzrksiLKBP5g",
  "model_version": "eduai-ai-0.2.0",
  "config_version": "0.2-provisional",
  "schema_version": "1.0",
  "source": "browser",
  "review_status": "Valid",
  "created_at": "2026-10-13T03:33:14.915+00:00",
  "updated_at": "2026-10-13T03:33:23.860+00:00",
  "duration_s": 9.0,
  "student": {"id": 1, "name": "Alya Putri", "nis": "2301034", "class_name": "XI IPA 2"},
  "exam": {"id": 1, "name": "Ujian Akhir Matematika XI"},
  "last_review": {"decision": "Valid", "note": "E2E: wajah tidak terlihat pada cuplikan.", "created_at": "...", "reviewer": "Rina Setiawati"}
}
```

Status analisis per siswa (`ai.state` pada `/students`): `not_started` (pemantauan AI belum dimulai/dihentikan; video bisa tetap LIVE), `no_data` (pemantauan aktif tetapi belum ada hasil analisis ≤10 dtk untuk siswa ini), `ai_offline` (pemantauan aktif tetapi analisis tidak berjalan: worker OpenVidu tanpa heartbeat ≥20 dtk/proses berhenti setelah 15 dtk masa mulai, atau model AI backend tidak tersedia pada jalur frame browser), `warming_up` (membangun acuan pose kepala), `normal`, `indication` (ada indikasi terbuka), `cannot_analyze` (gelap/buram/beku/wajah terlalu kecil/frame rusak), `model_unavailable`. `ai.last_state` = status terakhir yang tersimpan apa pun umurnya.

`counts.session_indications` = indikasi sejak pemantauan terakhir dimulai (`monitoring_started_at`); `counts.indications`/`unreviewed` mencakup semua sesi ujian ini. `last_indication` mendahulukan indikasi yang masih terbuka, lalu yang terbaru, dan berisi `status`, `end_ts`, `current_session` (false = dari sesi pemantauan sebelumnya). Indikasi lama tidak dihapus atau disembunyikan: tetap perlu ditinjau pengawas.

## Contoh permintaan

### Login

```http
POST /api/auth/login
Content-Type: application/json

{"email": "pengawas1@gmail.com", "password": "123456"}
```

```json
{"token": "eyJhbGciOi...", "user": {"id": 7, "email": "pengawas1@gmail.com", "name": "Rina Setiawati", "role": "pengawas", "role_label": "Pengawas", "nis": null, "class_name": null}}
```

### Siswa bergabung (setelah persetujuan)

```http
POST /api/exams/1/consent         {"accepted": true, "notice_version": "2026-10-v1"}
POST /api/exams/1/join
```

```json
{
  "identity": "student-1",
  "livekit": {"url": "ws://localhost:7880", "room": "eduai-exam-1", "token": "<JWT ruang, berlaku 3 jam>"},
  "livekit_reason": null,
  "monitoring": {"active": true, "source": "browser", "upload_fps": 2.0, "max_width": 640, "jpeg_quality": 0.8},
  "exam": {"id": 1, "name": "Ujian Akhir Matematika XI", "...": "..."}
}
```

Token ruang siswa: `roomJoin`, `canPublish` (kamera, mikrofon), **`canSubscribe: false`** (siswa tidak bisa melihat siswa lain). Token staf: `canSubscribe: true`, `canPublish: false`. Token worker AI: `hidden: true`, `canSubscribe: true`, `canPublish: false`. Bila OpenVidu belum dikonfigurasi, `livekit` bernilai `null` dan `livekit_reason` berisi alasannya.

### Unggah frame (jalur browser)

```http
POST /api/exams/1/frames
Authorization: Bearer <token siswa>
Content-Type: multipart/form-data; boundary=...

frame=<JPEG, maks. EDUAI_FRAME_MAX_BYTES (400 kB)>
```

| Respons 202 | Arti |
|---|---|
| `{"accepted": true}` | Frame dianalisis |
| `{"accepted": false, "reason": "busy"}` | Frame sebelumnya siswa ini masih dianalisis; frame dibuang (antrean dibatasi 1 per siswa) |
| `{"accepted": false, "reason": "monitoring_inactive"}` | Pemantauan belum dimulai |
| `{"accepted": false, "reason": "worker_active"}` | Mode worker OpenVidu dan worker sudah melaporkan siswa ini dalam 10 dtk terakhir. Bila worker tidak melihat siswa (mis. siswa gagal terhubung ke OpenVidu), frame diterima sebagai cadangan |
| `{"accepted": false, "reason": "ai_unavailable"}` | Model belum siap; status siswa menjadi `model_unavailable` |

### Mulai pemantauan

```http
POST /api/exams/1/monitoring/start
{"source": "livekit"}            // atau "browser"; kosong = EDUAI_ANALYSIS_SOURCE
```

```json
{"active": true, "source": "browser", "note": "Worker OpenVidu tidak berjalan (LiveKit/OpenVidu belum dikonfigurasi). Analisis memakai frame dari browser siswa."}
```

### Validasi pengawas

```http
POST /api/events/e68a5f2d-1456-40ef-8424-249eda4bb66c/reviews
{"decision": "Valid", "note": "Peserta keluar dari bingkai kamera."}
```

Kejadian `cannot_analyze` ditolak dengan 400: kualitas video bukan indikasi.

### Evidence

```http
GET /api/evidence/pxAmBrzYPgwzrksiLKBP5g
```

```json
{"evidence_id": "pxAmBrzYPgwzrksiLKBP5g", "event_id": "e68a5f2d-...", "exam_id": 1, "student_id": 1, "frame_count": 12,
 "frame_ts": [1760326385.4, "..."], "key_index": 0, "encrypted": false,
 "created_at": "2026-10-13T03:33:19.919+00:00", "expires_at": "2026-10-14T03:33:19.919+00:00"}
```

`GET /api/evidence/{id}/frames/{i}` mengembalikan `image/jpeg`. Frontend mengambilnya dengan header Authorization lalu menampilkan sebagai blob URL; tidak ada URL statis publik.

### Worker OpenVidu → backend

```http
POST /api/ai/events
X-AI-Service-Key: <EDUAI_AI_SERVICE_KEY>
{"events": [ { ...skema kejadian... } ]}
```

```json
{"stored": 1, "rejected": []}
```

```http
POST /api/ai/evidence            (multipart)
meta={"session_id":"1","student_id":"2","event_id":"...","key_index":0,"frame_ts":[...]}
frames=<JPEG> (1–30 berkas)

POST /api/ai/status
{"session_id": "1", "students": [{"student_id": "2", "state": "normal", "frame_status": "analyzed", "reason": "", "face_count": 1, "latency_ms": 6.1}]}

POST /api/ai/heartbeat
{"session_id": "1", "models": {...}, "students": 3, "source": "livekit"}
```

Heartbeat (tiap 5 dtk) menjawab `{"ok": true, "monitoring_active": true, "stop": false}`. `worker_id` (opsional, maks. 64 karakter, diisi backend lewat env `EDUAI_WORKER_ID` saat menjalankan worker) memungkinkan backend mengenali worker lama. `stop: true` bila pemantauan tidak berjalan dalam mode worker atau `worker_id` bukan milik worker yang sedang dijalankan backend; worker lalu menutup kejadiannya dan keluar. Worker juga keluar sendiri setelah 12 heartbeat gagal berturut-turut.
