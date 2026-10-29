# EduAI – modul AI (v0.2)

Frame kamera → gerbang kualitas → MediaPipe (wajah, pose kepala, ponsel) → aturan temporal → kejadian JSON + evidence.
Semua kejadian kategori `indication` adalah **indikasi untuk ditinjau pengawas**, bukan bukti kecurangan. Kategori `cannot_analyze` berarti kualitas video kurang dan tidak pernah dihitung sebagai indikasi.

Modul ini dipakai oleh backend (`backend/app/ai_service.py`, jalur frame browser) dan oleh worker OpenVidu (`eduai_ai.livekit_worker`). Petunjuk lengkap sistem: `../../README.md`.

## Pemasangan mandiri (tanpa backend)

```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1        # Linux/macOS: source .venv/bin/activate
pip install -e .[models,livekit,crypto] pytest
powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1    # atau: bash scripts/download_models.sh
python scripts\smoke_test_models.py --image foto-wajah.jpg
python scripts\run_webcam.py --source 0                     # webcam -> events.jsonl
python scripts\run_webcam.py --source video.mp4 --events-out preds\video.jsonl --evidence-dir evidence
python -m pytest -q
```
`--show` (jendela debug) membutuhkan `opencv-python` (bukan `-headless`).

## Struktur

```
config.yaml                 ambang (SEMENTARA, belum dikalibrasi), jalur model, evidence
src/eduai_ai/
  signals.py                FrameSignals + status: analyzed | cannot_analyze | model_unavailable
  quality.py                gerbang kualitas dengan alasan eksplisit
  headpose.py               yaw/pitch dari matriks transformasi wajah MediaPipe
  perception.py             Face Detector (wajib), Face Landmarker, Object Detector (opsional)
  temporal.py               durasi minimum, histeresis, cooldown, baseline per siswa, flush
  events.py                 skema kejadian 1.0 (URS A-03) + JSON Schema
  evidence.py               buffer cincin + penyimpanan evidence (retensi, enkripsi opsional)
  pipeline.py               StudentAnalyzer: satu siswa, satu alur
  livekit_worker.py         worker OpenVidu (peserta tersembunyi, rtc.VideoStream)
  backend_client.py         worker -> backend (X-AI-Service-Key)
scripts/
  run_webcam.py             webcam/video -> JSONL kejadian (+ latensi)
  evaluate.py               precision, recall, F1, indikasi palsu per jam (butuh label)
  download_models.{sh,ps1,py}  unduh model resmi (+ fallback wheel MediaPipe)
  smoke_test_models.py      bukti model termuat dan berjalan
tests/test_core.py          24 tes logika (tanpa model)
tests/test_models_smoke.py  2 tes model nyata (skip bila model/scikit-image tidak ada)
```

## Indikator

| Indikator | Butuh model | Aturan (config.yaml) |
|---|---|---|
| `FACE_ABSENT` | Face Detector | tidak ada wajah ≥ 5 dtk |
| `MULTIPLE_PERSONS` | Face Detector (+ Object Detector) | > 1 wajah/orang ≥ 2 dtk |
| `HEAD_TURN` | Face Landmarker | simpangan dari acuan > 30° ≥ 3 dtk (lepas < 20°), acuan 45 dtk pertama |
| `HEAD_TURN_REPEATED` | Face Landmarker | ≥ 5 lirikan dalam 120 dtk |
| `PHONE_VISIBLE` | Object Detector | `cell phone` skor ≥ 0,4 selama ≥ 1,5 dtk |
| `CANNOT_ANALYZE` | — | frame gagal kualitas ≥ 2 dtk (gelap, terang, buram, beku, resolusi, wajah terlalu kecil, frame rusak) |

Bila model opsional tidak ada, indikatornya nonaktif dan dilaporkan di `MediaPipePerception.status` serta `GET /api/ai/health`.

## Catatan

- Ambang adalah titik awal rekayasa, bukan angka dari paper. Kalibrasi dengan video pilot berlabel + `evaluate.py`.
- Tanda (+/−) yaw belum dicek dengan webcam sungguhan; indikator hanya memakai besar simpangan.
- Evidence berupa cuplikan JPEG (bukan klip video, tanpa audio) dan selesai ditulis ±5 dtk setelah indikasi terbuka.
- Video pilot, prediksi, dan evidence jangan di-commit ke repositori.
