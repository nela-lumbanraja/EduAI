Letakkan berkas model MediaPipe di folder ini (tidak disertakan di repositori/ZIP):

- blaze_face_short_range.tflite   (wajib)  — atau face_detection_short_range.tflite via --from-mediapipe-wheel
- face_landmarker.task            (opsional; mengaktifkan indikator arah kepala)
- efficientdet_lite0.tflite       (opsional; mengaktifkan indikator ponsel)
- clip_vit_b32_vision_quantized.onnx (opsional, ~89 MB; buku yang dipegang/dibuka di depan kamera; perlu `pip install onnxruntime`)
- clip_book_prompts.npz           (ikut di repositori; deskripsi teks untuk CLIP, dibuat dengan scripts/build_book_prompts.py)

Unduh: scripts/download_models.ps1 (Windows), scripts/download_models.sh, atau scripts/download_models.py.
