"""Startup check of every AI model EduAI uses: inventory, dependencies, load, warm-up inference, output validation.

A model is READY only after it produced a valid output on a dummy input, never because a file exists or a package
imports. The dummy input proves the runtime works and the output has the expected form; it says nothing about
accuracy (that is measured on real recordings, see scripts/evaluate.py).

Statuses: PENDING (not checked yet), LOADING, READY, FAILED, MISSING_DEPENDENCY, MISSING_MODEL_FILE, DISABLED.
"""
import importlib.util
import logging
import math
import time

import numpy as np

from .config import resolve_model_path
from .perception import find_model_files

log = logging.getLogger("eduai_ai.model_check")

PENDING, LOADING, READY, FAILED = "PENDING", "LOADING", "READY", "FAILED"
MISSING_DEPENDENCY, MISSING_MODEL_FILE, DISABLED = "MISSING_DEPENDENCY", "MISSING_MODEL_FILE", "DISABLED"

# Every model in config.yaml -> models. Order = order shown to users.
MODELS = {
    "face_detector": {"name": "BlazeFace short-range", "library": "MediaPipe Tasks (TFLite)", "package": "mediapipe",
                      "runs_in": "backend", "function": "Deteksi wajah: wajah tidak terlihat, lebih dari satu wajah"},
    "face_landmarker": {"name": "Face Landmarker", "library": "MediaPipe Tasks (TFLite)", "package": "mediapipe",
                        "runs_in": "backend", "function": "Arah kepala (menoleh, menunduk) dan gerak mulut"},
    "object_detector": {"name": "EfficientDet-Lite0 (COCO)", "library": "MediaPipe Tasks (TFLite)", "package": "mediapipe",
                        "runs_in": "backend", "function": "Ponsel, buku (kelas COCO), jumlah orang"},
    "book_classifier": {"name": "CLIP ViT-B/32 Book Classifier", "library": "ONNX Runtime", "package": "onnxruntime",
                        "runs_in": "backend", "function": "Buku dipegang atau dibuka di depan kamera"},
    "audio_classifier": {"name": "YAMNet", "library": "MediaPipe Tasks Audio (TFLite)", "package": "mediapipe",
                         "runs_in": "browser", "function": "Jenis suara (bicara, bisikan, media, kertas); dijalankan di "
                                                           "browser siswa, backend memeriksa dan menyajikan filenya"},
}


def _has_package(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def inventory(cfg: dict, audio_enabled: bool = True) -> dict:
    """{key: entry} for every model, before anything is loaded. Disabled models are DISABLED and not required;
    a missing file or package is reported now (it cannot become READY later without a restart)."""
    files = find_model_files(cfg)
    ac = (cfg.get("models") or {}).get("audio_classifier")
    if ac:
        p = resolve_model_path(ac.get("path", "models/yamnet.tflite"))
        files["audio_classifier"] = {"path": str(p), "enabled": bool(ac.get("enabled", True)) and audio_enabled,
                                     "exists": p.is_file()}
    out = {}
    for key, meta in MODELS.items():
        f = files.get(key)
        e = {**meta, "key": key, "file": None, "path": None, "exists": False, "enabled": False, "required": False,
             "status": DISABLED, "error": "", "load_ms": None, "warmup_ms": None, "warmup": "not run", "output": None}
        if f is not None:
            e.update(path=f["path"], file=str(f["path"]).replace("\\", "/").split("/")[-1], exists=bool(f["exists"]),
                     enabled=bool(f["enabled"]))
        if f is None:
            e["error"] = "tidak ada di config.yaml"
        elif not f["enabled"]:
            e["error"] = ("EDUAI_AUDIO_ANALYSIS=false" if key == "audio_classifier" and not audio_enabled
                          else "dimatikan di config.yaml")
        else:
            e["required"] = True
            if not _has_package(meta["package"]):
                e.update(status=MISSING_DEPENDENCY, error=f"paket Python '{meta['package']}' belum terpasang")
            elif not f["exists"]:
                e.update(status=MISSING_MODEL_FILE, error=f"file model tidak ditemukan: {e['file']}")
            else:
                e["status"] = PENDING
        out[key] = e
    return out


def status_from_load(info: dict) -> tuple:
    """MediaPipePerception.status[...] -> (status, error)."""
    if info.get("loaded"):
        return LOADING, ""                                  # loaded, warm-up still to come
    reason = info.get("reason", "")
    if reason == "disabled in config":
        return DISABLED, "dimatikan di config.yaml"
    if reason == "model file not found":
        return MISSING_MODEL_FILE, "file model tidak ditemukan"
    if reason.startswith("package not installed"):
        return MISSING_DEPENDENCY, f"paket Python '{reason.split(':', 1)[1].strip()}' belum terpasang"
    return FAILED, reason or "gagal dimuat"


def dummy_frame(w: int = 640, h: int = 480) -> np.ndarray:
    return np.full((h, w, 3), 128, np.uint8)               # plain grey: nothing to find, any count is still valid


def warm_up(perception, include_book: bool = True) -> dict:
    """Run every loaded model of a MediaPipePerception once on a dummy frame and validate the output form.
    Returns {key: {"ok", "warmup_ms", "output", "error"}}. Uses timestamps below any real one and leaves the
    perception's clock so later frames stay strictly increasing (VIDEO mode)."""
    mp = perception._mp
    frame = dummy_frame()
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame[:, :, ::-1]))
    ms = max(perception._last_ms, 0) + 1
    out = {}

    def run(key, fn, check):
        nonlocal ms
        t0 = time.perf_counter()
        try:
            res = fn(ms)
            desc = check(res)
            out[key] = {"ok": True, "warmup_ms": round((time.perf_counter() - t0) * 1000, 1), "output": desc, "error": ""}
        except Exception as e:                       # noqa: BLE001 - any failure means not ready
            out[key] = {"ok": False, "warmup_ms": round((time.perf_counter() - t0) * 1000, 1), "output": None,
                        "error": f"inferensi pemanasan gagal: {type(e).__name__}: {e}"}
        ms += 1

    def list_of(res, attr):
        v = getattr(res, attr)
        if not isinstance(v, list):
            raise TypeError(f"{attr} bukan list")
        return v

    if perception.face_detector is not None:
        run("face_detector", lambda t: perception.face_detector.detect_for_video(image, t),
            lambda r: f"output valid ({len(list_of(r, 'detections'))} deteksi)")
    if perception.landmarker is not None:
        run("face_landmarker", lambda t: perception.landmarker.detect_for_video(image, t),
            lambda r: f"output valid ({len(list_of(r, 'face_landmarks'))} wajah)")
    if perception.object_detector is not None:
        def objs(r):
            d = list_of(r, "detections")
            if any(not c.categories or not 0.0 <= c.categories[0].score <= 1.0 for c in d):
                raise ValueError("skor deteksi di luar 0-1")
            return f"output valid ({len(d)} objek)"
        run("object_detector", lambda t: perception.object_detector.detect_for_video(image, t), objs)
    if include_book and perception.book_classifier is not None:
        def prob(p):
            if not isinstance(p, float) or math.isnan(p) or not 0.0 <= p <= 1.0:
                raise ValueError(f"P(buku) tidak valid: {p!r}")
            return f"output valid (P(buku)={p:.2f} untuk gambar uji)"
        run("book_classifier", lambda t: perception.book_classifier.score(frame), prob)
    perception._last_ms = ms
    return out


def check_audio(path: str) -> dict:
    """YAMNet runs in the student's browser; the backend proves the file is a working model by classifying 1 s of
    silence with MediaPipe Audio, then closes it. {"ok", "load_ms", "warmup_ms", "output", "error"}."""
    t0 = time.perf_counter()
    try:
        from mediapipe.tasks.python import BaseOptions, audio
        from mediapipe.tasks.python.components.containers import audio_data
        clf = audio.AudioClassifier.create_from_options(audio.AudioClassifierOptions(
            base_options=BaseOptions(model_asset_path=path), running_mode=audio.RunningMode.AUDIO_CLIPS, max_results=3))
    except ModuleNotFoundError as e:
        return {"ok": False, "status": MISSING_DEPENDENCY, "load_ms": None, "warmup_ms": None, "output": None,
                "error": f"paket Python '{e.name}' belum terpasang"}
    except Exception as e:                           # noqa: BLE001
        return {"ok": False, "status": FAILED, "load_ms": round((time.perf_counter() - t0) * 1000, 1), "warmup_ms": None,
                "output": None, "error": f"gagal dimuat: {type(e).__name__}: {e}"}
    load_ms = round((time.perf_counter() - t0) * 1000, 1)
    t1 = time.perf_counter()
    try:
        res = clf.classify(audio_data.AudioData.create_from_array(np.zeros(16000, np.float32), 16000))
        cats = res[0].classifications[0].categories if res and res[0].classifications else []
        if not cats or not all(0.0 <= c.score <= 1.0 for c in cats):
            raise ValueError("tidak ada kategori suara yang valid")
        out = {"ok": True, "status": READY, "output": f"output valid (hening -> {cats[0].category_name})", "error": ""}
    except Exception as e:                           # noqa: BLE001
        out = {"ok": False, "status": FAILED, "output": None, "error": f"inferensi pemanasan gagal: {type(e).__name__}: {e}"}
    finally:
        try:
            clf.close()
        except Exception:                            # noqa: BLE001
            pass
    return {**out, "load_ms": load_ms, "warmup_ms": round((time.perf_counter() - t1) * 1000, 1)}
