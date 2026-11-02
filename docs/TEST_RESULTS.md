# Hasil pengujian

Lingkungan pengembangan: Linux container, 2 vCPU Intel Xeon 2,10 GHz, tanpa GPU; Python 3.13.16, MediaPipe 0.10.32, FastAPI 0.143.0, livekit (Python) 1.1.20, Node.js 22.22.0, Chromium (Playwright). Tanggal awal: 13 Oktober 2026; diperbarui 29 Oktober 2026 (audio, kasus, worker OpenVidu — lihat baris 16–22).
**Belum diuji di Windows.** Langkah Windows di README disusun dari dokumentasi alat, bukan dari eksekusi.

## Ringkasan

| # | Pengujian | Hasil |
|---|---|---|
| 1 | Unit test modul AI (`ai/eduai-ai`, `pytest`) | **LULUS** 51/51 (29 Okt; termasuk `test_voice.py`, `test_worker.py`) |
| 2 | Smoke test model nyata (`tests/test_models_smoke.py`, `scripts/smoke_test_models.py`) — BlazeFace | **LULUS** 2/2 |
| 3 | Smoke test Face Landmarker & EfficientDet-Lite0 | **TIDAK DIJALANKAN** — berkas model tidak dapat diunduh (HTTP 403 dari `storage.googleapis.com` di lingkungan ini) |
| 4 | Backend: tes API (TestClient, perception tiruan berskrip) | **LULUS** 50/50 (29 Okt; termasuk `test_audio.py`, `test_cases.py`, `test_worker_mgmt.py`) |
| 5 | Backend: tes HTTP dengan model nyata (`test_real_model_face_absent_via_http`) | **LULUS** 1/1 |
| 6 | Frontend: `npm install`, `npx tsc --noEmit`, `npm run build` | **LULUS** (peringatan ukuran bundle > 500 kB, tidak memblokir) |
| 7 | E2E browser jalur frame browser: Chromium + kamera palsu → backend → AI nyata → pop-up dasbor → evidence → validasi | **LULUS** (lihat bawah) |
| 8 | Crawl semua menu untuk 5 peran (galat runtime JavaScript) | **LULUS** — tidak ada galat aplikasi; satu galat jaringan berasal dari impor Google Fonts yang diblokir lingkungan ini |
| 9 | `scripts/run_webcam.py` pada berkas video + `scripts/evaluate.py` | **LULUS** sebagai uji fungsi skrip (bukan evaluasi akurasi; lihat bawah) |
| 10 | Token OpenVidu/LiveKit (klaim JWT, hak minimum) | **LULUS** (didekode dan diperiksa di tes 4) |
| 11 | Worker OpenVidu: impor, parsing argumen, gagal bersih bila server tidak ada | **LULUS** (keluar dengan kode 2 dan pesan "AI worker stopped: ConnectError…") |
| 12 | Ruang OpenVidu nyata: siswa publish, pengawas subscribe | **LULUS** dengan `livekit-server` 1.9.1 (Linux, mode lokal) — elemen `<video>` pengawas memutar video siswa, label LIVE. Paket Docker OpenVidu **tidak** diuji (tidak ada Docker daemon) |
| 13 | E2E jalur worker OpenVidu (`tests/e2e/e2e_livekit_worker.py`) | **LULUS** mode `stop` dan `kill` dengan server yang sama (lihat bawah). Jalur Windows **tidak** diuji |
| 14 | Uji beban / banyak siswa bersamaan | **TIDAK DIJALANKAN** — tidak ada klaim kapasitas |
| 15 | Uji dengan webcam fisik & siswa sungguhan | **TIDAK DIJALANKAN** — hanya kamera palsu Chromium |
| 16 | Frontend: `tests/notify.test.ts`, `tests/audioScores.test.ts` (`node --experimental-strip-types`) | **LULUS** 7/7 dan 4/4 |
| 17 | Frontend: `npx tsc --noEmit`, `npm run build` (29 Okt) | **LULUS** (peringatan ukuran bundle, tidak memblokir) |
| 18 | E2E #7 diulang pada kode akhir (regresi) | **LULUS** |
| 19 | E2E analisis suara: UI persetujuan audio, YAMNet nyata di Chromium dengan mikrofon palsu (rekaman ucapan), API & aturan nyata; perception video tiruan "1 wajah, mulut diam" | **LULUS** — indikasi `OTHER_VOICE`; mematikan mikrofon menghentikan analisis. Face Landmarker nyata (`jawOpen`) dan mikrofon fisik **tidak** diuji |
| 20 | Worker dimatikan paksa (simulasi `TerminateProcess` Windows) lalu Hentikan AI | **LULUS** setelah perbaikan — sebelum perbaikan **GAGAL** (1 kejadian tertinggal `open`) |
| 21 | Worker yatim: backend dimatikan paksa saat worker berjalan, backend dimulai ulang, Mulai AI lagi | **LULUS** — worker lama keluar ±1 dtk (heartbeat `stop`), tidak ada proses tertinggal setelah Hentikan AI |
| 22 | Siswa tidak dapat terhubung ke OpenVidu (URL publik salah) saat mode worker | **LULUS** — frame lewat jalur browser, indikasi `FACE_ABSENT` dengan `source=browser` |
| 23 | Jalur Windows worker (`CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT`, penangan `SIGBREAK`) | **TIDAK DIJALANKAN** — tidak ada Windows. Tes `test_worker_manager_stops_gracefully` memakai cabang Windows bila dijalankan di Windows |

Verifikasi paket: ZIP diekstrak ke folder kosong, `pip install -e ai/eduai-ai`, `npm ci`. Tanpa berkas model: AI 24 lulus + 2 *skip* (tes model). Setelah model detektor wajah ditaruh di `models/`: AI 26 lulus, backend 17 lulus, frontend `tsc` + `build` lulus.

Tidak ada tes yang dilewati (skip) dalam rangkaian `pytest` di atas; tes model nyata akan otomatis *skip* bila berkas model atau `scikit-image` tidak ada.

## Detail

### 1–2. Modul AI

```
cd ai/eduai-ai && python -m pytest -v        → 26 passed
```
Cakupan: validasi config, pencarian berkas model, head pose dari matriks, alasan gerbang kualitas (gelap, terang, buram, beku, resolusi, wajah terlalu kecil), histeresis/cooldown/pengulangan, mesin kejadian (wajah hilang, beberapa orang, `cannot_analyze` bukan indikasi, `model_unavailable` tanpa kejadian, baseline, `warming_up`, kegagalan landmark diabaikan, ponsel), skema kejadian, buffer & penyimpanan evidence (jendela waktu, batas frame, enkripsi, retensi, penolakan path traversal), pipeline lengkap dengan perception tiruan, pencocokan evaluasi.
Smoke test model nyata: wajah terdeteksi pada foto `astronaut` (1 wajah), tidak ada wajah pada `coffee`, frame datar → `cannot_analyze`; pipeline nyata menghasilkan `FACE_ABSENT` open→closed pada urutan wajah→tanpa wajah→wajah.

Latensi pipeline satu siswa (BlazeFace saja, frame 480×480, 190 frame): median **5,0 ms**, p95 6,6 ms, maks 8,8 ms per frame di mesin ini. Angka ini **tidak** mencakup Face Landmarker/EfficientDet (tidak tersedia) dan bukan dasar klaim jumlah siswa bersamaan.

### 4–5. Backend

```
cd backend && python -m pytest -v            → 17 passed
```
`test_health`, `test_login_register_and_limits` (login gagal, token rusak, pendaftaran hanya siswa, pembatasan 5 percobaan), `test_role_based_access` (siswa ditolak dari data pemantauan, pengawas lain ditolak, sekolah tidak bisa memulai pemantauan), `test_admin_creates_exam`, `test_join_requires_consent_and_frames_require_monitoring`, `test_frame_validation` (415, 413, frame rusak → `cannot_analyze/no_frame`), `test_face_absent_indication_end_to_end` (indikasi, evidence JPEG, audit, akses sekolah sebelum/sesudah validasi, laporan, linimasa), `test_cannot_analyze_is_not_an_indication` (tanpa evidence, tidak bisa divalidasi), `test_stop_monitoring_closes_open_events`, `test_evidence_retention` (410 setelah kedaluwarsa, purge), `test_busy_frames_are_dropped` (antrean ≤1/siswa), `test_worker_ingest_requires_service_key`, `test_worker_ingest_events_status_evidence`, `test_livekit_tokens_have_least_privilege`, `test_livekit_source_without_server_falls_back_to_browser`, `test_debug_inference_endpoint`, `test_real_model_face_absent_via_http`.

### 7. E2E browser (jalur frame browser)

Skrip: `tests/e2e/make_fake_camera.py` (klip Y4M: wajah 0–7 dtk, tanpa wajah 7–16 dtk, wajah 16–22 dtk) dan `tests/e2e/e2e_browser_flow.py`. Backend dengan basis data baru dan model BlazeFace nyata; frontend `vite` dev server; Chromium dengan `--use-file-for-fake-video-capture`.

```
[ok] supervisor started monitoring
[ok] student in exam room, frames uploading
[ok] supervisor received pop-up: Indikasi baru | Alya Putri · Wajah tidak terlihat · 03.33.09 | Perlu ditinjau pengawas — bukan keputusan pelanggaran. | Tinjau | Tutup
[ok] supervisor validated the indication
E2E PASSED
```
Data tersimpan: satu kejadian `FACE_ABSENT` (closed, 9,0 dtk, alasan "Wajah tidak terlihat di kamera selama 9.0 detik"), evidence 12 JPEG, `review_status = Valid`. 43 frame diunggah dan dianalisis, 0 dibuang karena sibuk. Log backend diperiksa: tidak ada token/JWT tercatat. Tangkapan layar: `docs/screenshots/`.

Batasan uji ini: kamera palsu (gambar statis + derau), satu siswa, browser dan server di mesin yang sama.

### 9. Skrip video dan evaluasi

`run_webcam.py --source fake.mp4` (klip yang sama, dikodekan H.264): satu `FACE_ABSENT` 7,1–16,0 dtk, tanpa kejadian lain; latensi median 5,4 ms. `evaluate.py` dengan label sintetis yang sesuai klip menghasilkan precision/recall/F1 = 1,0. **Ini hanya membuktikan skrip berjalan benar pada data buatan; ini bukan ukuran akurasi sistem.** Evaluasi nyata memerlukan video pilot berlabel.

Temuan selama uji ini: video terkompresi dari adegan sangat diam memiliki selisih antarframe 0,09–0,25, sehingga ambang "video beku" awal (1,0) menandai video normal sebagai beku. Ambang diubah menjadi 0,05 selama 5 dtk (`config.yaml`), masih bersifat sementara.

### 12–13, 20–22. OpenVidu / LiveKit (29 Oktober 2026)

Server: `livekit-server` 1.9.1 (biner rilis resmi, mode lokal, kunci khusus uji); backend asli dengan `EDUAI_ANALYSIS_SOURCE=livekit`; frontend `vite`; Chromium dengan kamera palsu; worker asli (`python -m eduai_ai.livekit_worker`, dijalankan oleh `WorkerManager`) dengan BlazeFace nyata.

```
python tests/e2e/e2e_livekit_worker.py --y4m fake.y4m --mode kill
[ok] student in exam room, publishing to the room
[info] start monitoring -> {'active': True, 'source': 'livekit', 'note': None}
[ok] worker heartbeat (worker.alive) (1s)
[ok] student AI status from the worker (1s)
[ok] FACE_ABSENT indication from the worker with evidence (13s)
[ok] evidence readable: 12 frame(s)
[ok] dashboard cases: 1
[ok] an open worker event exists before stopping (39s)
[info] worker hard-killed
[info] stop monitoring -> {'active': False}
[ok] open worker events after stop: 0
[ok] worker processes after stop: []
WORKER E2E PASSED
```
Log backend: `closed 1 event(s) left open by the AI worker for exam 1`. Mode `stop`: hasil sama, worker menutup kejadiannya sendiri (backend tidak perlu menutup).

Temuan sebelum perbaikan (kode dasar, server yang sama): jalur normal lulus, tetapi bila worker dimatikan paksa — yang terjadi di Windows karena `Popen.terminate()` = `TerminateProcess` — satu kejadian tertinggal `open` selamanya; worker yang tertinggal setelah backend dimatikan paksa terus berjalan tanpa batas; dan siswa yang gagal terhubung ke OpenVidu tidak dianalisis sama sekali. Ketiganya diperbaiki dan diuji ulang (baris 20–22).

Batasan: satu siswa, satu mesin, server LiveKit biasa (bukan paket OpenVidu lengkap dengan Caddy/Redis/ingress), Linux saja.

### Rapat Video / Jitsi Meet (30 Oktober 2026)

Windows 11, Chrome headless (`--use-fake-device-for-media-stream`), server uji `alpha.jitsi.net`, `pengawas1` dan `siswa1` di ruang acak. **LULUS:** keduanya bergabung (2 peserta), video diterima dua arah dan stabil selama 16 dtk, elemen audio remote terpasang, video lokal tampil lagi setelah kamera dimatikan lalu dinyalakan, tidak ada ubin tersisa setelah peserta keluar. `tsc --noEmit` dan `npm run build` lulus.

**Tidak diuji:** kamera dan mikrofon sungguhan, suara yang benar-benar terdengar, server Jitsi sendiri, koneksi putus di tengah rapat, lebih dari dua peserta. Skrip uji tidak disimpan di repo.

## Laporan Sesi

Windows 11, Chrome headless, backend dan frontend terpisah di basis data sementara dengan tiga kejadian uji dan gambar sintetis.

| Uji | Hasil |
|---|---|
| `backend/tests/test_report.py` | **Lulus** |
| Angka ringkasan, thumbnail, perbesar, kejadian tanpa gambar | **Lulus** |
| Ubah status dan catatan di tabel, ringkasan ikut berubah, tersimpan setelah muat ulang | **Lulus** |
| Peringatan finalisasi, finalisasi, tabel terkunci, gambar dari salinan final | **Lulus** |
| Ekspor PDF dan Excel dari tombol; PDF final dan DRAF diperiksa per halaman (3 halaman) | **Lulus** |
| Pindah sesi lewat dropdown, kondisi kosong, galat dengan Coba lagi | **Lulus** |
| Peran sekolah tanpa gambar, halaman Retensi Data | **Lulus** |

**Tidak diuji:** data ujian sungguhan, retensi yang benar-benar menunggu 24 jam atau 7 hari (diuji dengan memundurkan waktu paket), URL gambar di server HTTPS, dan nama dengan huruf di luar Latin di PDF.

## Mode ujian Jitsi

Windows 11, Chrome headless, kamera palsu Chrome, kode frontend asli melawan `window.JitsiMeetJS` **tiruan**, backend terpisah di basis data sementara dengan AI nyata.

| Uji | Hasil |
|---|---|
| Tes backend seluruhnya (termasuk `test_jitsi.py`) | **132 lulus, 0 gagal, 2 dilewati** |
| Tes modul AI | **48 lulus, 0 gagal, 2 dilewati** |
| Tes frontend (`notify`, `audioScores`, `meetingIsolation`, `consent`) | **24 lulus, 0 gagal** |
| Uji mutasi `test_jitsi.py` (14 kerusakan sengaja, dengan kontrol tanpa mutasi) | **14 tertangkap, 0 lolos** |
| Skenario browser (sumber, siswa Jitsi, terputus, gagal masuk, track mati, Rapat Video, belum dikonfigurasi, pesan OpenVidu, teks persetujuan, logo build produksi) | **46 dari 46 lulus** |
| Rekaman jaringan Rapat Video | Siswa: 0 panggilan API. Pengawas: hanya polling notifikasi `/api/cases` dan `/api/summaries`. Kontrol perekam lulus |
| `npm run lint` | Saat itu gagal (9 error, 1 peringatan); sudah diperbaiki, lihat bagian berikut |

**Tidak diuji:** server Jitsi sungguhan, kamera sungguhan, indikasi dan evidence jalur Jitsi di browser (kamera palsu tidak melewati fase acuan; hanya tes backend), sambung ulang tiap 30 detik, mode OpenVidu setelah perubahan ini, dan `tests/e2e` (butuh Playwright).

## Akses gambar bukti dan perbaikan ESLint

Windows 11, kode final (belum di-commit saat diuji), Chrome headless dengan kamera palsu, backend terpisah di basis data sementara.

| Uji | Hasil |
|---|---|
| Tes backend seluruhnya (termasuk matriks akses evidence) | **138 lulus, 0 gagal, 2 dilewati** |
| Tes modul AI | **48 lulus, 0 gagal, 2 dilewati** |
| Tes frontend | **24 lulus, 0 gagal** |
| `tsc --noEmit`, `npm run lint`, `npm run build` | **Bersih, 0 temuan, build berhasil** |
| Uji mutasi pemeriksaan izin evidence (16 kerusakan sengaja, dengan kontrol tanpa mutasi) | **16 tertangkap, 0 lolos** |
| Browser: akses evidence per peran (pengawas, admin, penyelenggara, sekolah: laporan, Indikasi, Detail Evidence, jumlah permintaan gambar), Ruang Tunggu, ganti akun | **48 dari 48 lulus** |
| Browser: mode ujian Jitsi (skenario yang sama seperti di atas) | **46 dari 46 lulus** |

ESLint diperbaiki dalam 7 langkah; tiap langkah diuji `tsc`, tes frontend, dan uji browser terkait. Tidak ada aturan yang dimatikan. Perilaku yang terlihat pengguna tidak berubah.

**Tidak diuji:** pesan "Pilih ujian..." di Ruang Ujian (tidak dapat dicapai lewat alur normal), server Jitsi dan kamera sungguhan, mode OpenVidu, dan `tests/e2e` (butuh Playwright).

## Langkah verifikasi OpenVidu untuk tim (paket OpenVidu / Windows)

1. Jalankan OpenVidu local deployment (README, bagian OpenVidu), isi `LIVEKIT_*`, `EDUAI_AI_SERVICE_KEY`, `EDUAI_ANALYSIS_SOURCE=livekit`, mulai ulang backend.
2. Siswa masuk ruang ujian → pesan "Siaran ke pengawas aktif" di footer ruang ujian.
3. Pengawas membuka Monitoring → ubin siswa menampilkan "LIVE" dan video.
4. Klik "Mulai AI" → dalam ±10 dtk `GET /api/exams/1/monitoring` menunjukkan `worker.alive: true`; status AI siswa berubah dari "Belum ada data video".
5. Siswa keluar dari bingkai kamera >5 dtk (ruangan tetap terang) → indikasi `FACE_ABSENT` dengan `source: "livekit"` dan evidence.
6. Klik "Hentikan AI" → dalam ±10 dtk tidak ada lagi proses `python ... eduai_ai.livekit_worker` (Task Manager → Details, kolom Command line) dan tidak ada kejadian `open` dengan `source: "livekit"`.
7. Otomatis: `python tests\e2e\e2e_livekit_worker.py --y4m fake.y4m --mode stop` lalu `--mode kill` (basis data baru untuk tiap jalan; `pip install psutil`).
8. Catat hasil di dokumen ini (lulus/gagal + log worker).
