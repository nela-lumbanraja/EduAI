# Pemilihan model

Prinsip: tidak ada pelatihan model pada tahap ini, dan tidak ada model yang dinyatakan "siap" tanpa berkas bobotnya benar-benar dimuat dan diuji.

| Model | Fungsi di EduAI | Sumber resmi | Status di paket ini |
|---|---|---|---|
| **BlazeFace short-range** (MediaPipe Face Detector) | Ada/tidaknya wajah, jumlah wajah, ukuran wajah | `storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite` | **Terintegrasi dan diuji** dengan inferensi nyata (smoke test, uji API, uji E2E browser). Di lingkungan pengembangan URL resmi diblokir (HTTP 403), jadi yang diuji adalah `face_detection_short_range.tflite` dari wheel resmi `mediapipe==0.10.14` (jaringan BlazeFace short-range yang sama, dimuat lewat Tasks `FaceDetector`). |
| **Face Landmarker** (MediaPipe) | Matriks transformasi wajah → yaw/pitch → `HEAD_TURN`, `HEAD_TURN_REPEATED` | `…/face_landmarker/face_landmarker/float16/latest/face_landmarker.task` | Kode terintegrasi (`output_facial_transformation_matrixes=True`), **belum diuji dengan model nyata** karena berkas tidak dapat diunduh di lingkungan pengembangan. Bila berkas tidak ada, indikator kepala otomatis nonaktif dan status `/api/ai/health` menunjukkan "model file not found". |
| **EfficientDet-Lite0** (MediaPipe Object Detector, COCO) | Objek `cell phone` → `PHONE_VISIBLE`; `book` → `BOOK_VISIBLE`; `person` → pendukung `MULTIPLE_PERSONS` | `…/object_detector/efficientdet_lite0/int8/latest/efficientdet_lite0.tflite` | Kode terintegrasi (`category_allowlist=["cell phone","book","person"]`, dijalankan tiap 0,5 dtk), **belum diuji dengan model nyata** (alasan sama). |
| 6DRepNet | Head pose regresi (alternatif Face Landmarker) | Repositori penulis (bobot PyTorch) | **Tidak diintegrasikan.** Tidak ada bobot di paket/ZIP yang diberikan, menambah PyTorch ke jalur real-time CPU, dan Face Landmarker sudah memberi matriks pose. Dapat dibandingkan nanti pada data pilot. |
| L2CS-Net | Estimasi arah pandang (gaze) | Repositori penulis (bobot PyTorch) | **Tidak diintegrasikan.** Tidak ada bobot; akurasi gaze webcam sangat dipengaruhi pencahayaan dan kacamata, perlu validasi tersendiri sebelum dipakai untuk indikasi. |
| LightGBM | Penggabung sinyal (fusion) terlatih | — | **Tidak diintegrasikan.** Memerlukan model terlatih dari data berlabel; tidak ada. Aturan temporal yang transparan dipakai sebagai gantinya. |

## Mengunduh model

```powershell
cd ai\eduai-ai
powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1     # Windows
# atau: bash scripts/download_models.sh  |  python scripts/download_models.py
python scripts\smoke_test_models.py --image C:\path\ke\foto-wajah.jpg     # bukti model termuat & berjalan
```

Bila `storage.googleapis.com` diblokir jaringan sekolah, alternatif untuk detektor wajah saja:

```powershell
python scripts\download_models.py --from-mediapipe-wheel
```

Perintah ini mengunduh wheel resmi `mediapipe==0.10.14` dari PyPI dan mengekstrak `face_detection_short_range.tflite` (dipakai otomatis lewat `fallback_paths` di `config.yaml`). Face Landmarker dan EfficientDet-Lite0 tidak ada di wheel tersebut dan tetap harus diunduh dari URL resmi.

## Ambang aturan

Semua ambang di `ai/eduai-ai/config.yaml` (`version: 0.2-provisional`) adalah titik awal rekayasa, **bukan angka dari paper** dan **belum dikalibrasi**. Rencana kalibrasi: kumpulkan video pilot berlabel (dengan persetujuan), jalankan `scripts/run_webcam.py --source <video> --events-out preds/<nama>.jsonl`, lalu `scripts/evaluate.py` untuk precision, recall, F1, dan indikasi palsu per jam; ubah ambang dan naikkan `version`.
