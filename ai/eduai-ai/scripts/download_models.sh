#!/usr/bin/env bash
# Download the pretrained MediaPipe model assets into ./models (macOS / Linux / Git Bash).
# Windows PowerShell: scripts\download_models.ps1   (or: python scripts\download_models.py)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models
BASE=https://storage.googleapis.com/mediapipe-models
get() {
  if [ -s "models/$1" ]; then echo "[skip] $1"; return; fi
  curl -fL --retry 2 -o "models/$1.part" "$2" && mv "models/$1.part" "models/$1"
}
get blaze_face_short_range.tflite "$BASE/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
get face_landmarker.task          "$BASE/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
get efficientdet_lite0.tflite     "$BASE/object_detector/efficientdet_lite0/int8/latest/efficientdet_lite0.tflite"
get yamnet.tflite                 "$BASE/audio_classifier/yamnet/float32/latest/yamnet.tflite"
ls -lh models
