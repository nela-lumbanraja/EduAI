# Download the pretrained MediaPipe model assets into .\models (Windows PowerShell).
# Run from the ai\eduai-ai folder:   powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force -Path models | Out-Null
$base = "https://storage.googleapis.com/mediapipe-models"
$assets = @{
  "blaze_face_short_range.tflite" = "$base/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
  "face_landmarker.task"          = "$base/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
  "efficientdet_lite0.tflite"     = "$base/object_detector/efficientdet_lite0/int8/latest/efficientdet_lite0.tflite"
  "yamnet.tflite"                 = "$base/audio_classifier/yamnet/float32/latest/yamnet.tflite"
}
foreach ($name in $assets.Keys) {
  $dest = Join-Path "models" $name
  if ((Test-Path $dest) -and ((Get-Item $dest).Length -gt 0)) { Write-Host "[skip] $name"; continue }
  Write-Host "[get ] $($assets[$name])"
  Invoke-WebRequest -Uri $assets[$name] -OutFile "$dest.part" -UseBasicParsing
  Move-Item -Force "$dest.part" $dest
  $hash = (Get-FileHash $dest -Algorithm SHA256).Hash.ToLower()
  Write-Host "[ok  ] $name sha256=$hash"
}
Get-ChildItem models
