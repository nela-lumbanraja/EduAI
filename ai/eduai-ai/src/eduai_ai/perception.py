"""Perception layer: one frame -> FrameSignals, using MediaPipe Tasks (VIDEO mode).

Components (each is optional except the face detector):
  - Face Detector (BlazeFace short-range)          -> number of faces, face size
  - Face Landmarker + facial transformation matrix -> head yaw/pitch of the main face
  - Object Detector (EfficientDet-Lite0, COCO)     -> "cell phone" / "book" scores, "person" count
  - Book classifier (CLIP ViT-B/32 zero-shot, ONNX) -> P(book held/opened in view); optional, see book_clip.py

Only APIs that exist in the `mediapipe` Tasks Python package are used:
vision.FaceDetector / FaceLandmarker / ObjectDetector with create_from_options(),
detect_for_video(image, timestamp_ms) and close().

One instance per video stream: VIDEO mode keeps tracking state and needs
strictly increasing timestamps, so instances must not be shared between students.
"""
import logging
import time
from pathlib import Path

import cv2
import numpy as np

from .config import resolve_model_path
from .headpose import yaw_pitch_from_matrix
from .quality import QualityGate
from .signals import ANALYZED, CANNOT_ANALYZE, MODEL_UNAVAILABLE, FrameSignals

log = logging.getLogger("eduai_ai.perception")


def find_model_files(cfg: dict) -> dict:
    """Return {component: {"path": str|None, "enabled": bool, "exists": bool}} without loading anything."""
    m = cfg["models"]
    out = {}
    fd = m["face_detector"]
    candidates = [fd["path"], *fd.get("fallback_paths", [])]
    found = next((resolve_model_path(p) for p in candidates if resolve_model_path(p).is_file()), None)
    out["face_detector"] = {"path": str(found or resolve_model_path(fd["path"])), "enabled": True,
                            "exists": found is not None}
    for name in ("face_landmarker", "object_detector"):
        c = m[name]
        p = resolve_model_path(c["path"])
        out[name] = {"path": str(p), "enabled": bool(c.get("enabled", True)), "exists": p.is_file()}
    bc = m.get("book_classifier")                       # optional section; missing = off
    if bc:
        p, t = resolve_model_path(bc["path"]), resolve_model_path(bc["prompts_path"])
        out["book_classifier"] = {"path": str(p), "prompts_path": str(t), "enabled": bool(bc.get("enabled", True)),
                                  "exists": p.is_file() and t.is_file()}
    return out


def _clip_classifier(model_path, prompts_path, threads):
    from .book_clip import ClipBookClassifier
    return ClipBookClassifier(model_path, prompts_path, threads)


class MediaPipePerception:
    def __init__(self, cfg: dict, book_classifier=None):
        """book_classifier: an already loaded ClipBookClassifier to share (ONNX Runtime sessions are thread-safe and
        CLIP keeps no per-stream state), so the 89 MB model is in memory once, not once per student."""
        import mediapipe as mp                          # imported lazily so tests run without it
        from mediapipe.tasks.python import BaseOptions, vision
        self._mp, self._vision, self._BaseOptions = mp, vision, BaseOptions

        q, s, m = cfg["quality"], cfg["sampling"], cfg["models"]
        self.work_width = s["work_width"]
        self.phone_every_s = s["phone_every_s"]
        self.min_face_width_ratio = q.get("min_face_width_ratio", 0.0)
        self.quality = QualityGate(**q)
        self._last_phone_ts = None
        self._last_book_ts = None
        self._last_ms = -1
        self.status = {}
        # One detector pass serves three rules. Before 15 Nov 2026 it used the object threshold (0.4) for everything,
        # so BOOK_VISIBLE.min_score 0.35 could never apply. Now: the lowest threshold any rule needs.
        ind = cfg.get("indicators", {})
        self.person_min_score = m["object_detector"]["min_score"]
        book = ind.get("BOOK_VISIBLE") or {}
        needs = [self.person_min_score, ind.get("PHONE_VISIBLE", {}).get("min_score", 1.0)]
        if book.get("enabled"):
            needs.append(book.get("min_score", 1.0))
        self.detector_threshold = min(needs)
        files = find_model_files(cfg)
        VIDEO = vision.RunningMode.VIDEO

        self.face_detector = self._load(
            "face_detector", files["face_detector"],
            lambda p: vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=p), running_mode=VIDEO,
                min_detection_confidence=m["face_detector"]["min_confidence"])))
        self.landmarker = self._load(
            "face_landmarker", files["face_landmarker"],
            lambda p: vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=p), running_mode=VIDEO, num_faces=1,
                output_facial_transformation_matrixes=True,
                output_face_blendshapes=True)))         # jawOpen = mouth movement (voice rule)
        self.object_detector = self._load(
            "object_detector", files["object_detector"],
            lambda p: vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
                base_options=BaseOptions(model_asset_path=p), running_mode=VIDEO,
                score_threshold=self.detector_threshold,
                category_allowlist=["cell phone", "book", "person"])))
        bc = m.get("book_classifier") or {}
        self.book_every_s = float(bc.get("every_s", self.phone_every_s))
        self.book_classifier = None
        self._shared_book = book_classifier is not None
        if book_classifier is not None:
            self.book_classifier = book_classifier
            self.status["book_classifier"] = {"loaded": True, "reason": "", "path": files.get("book_classifier", {}).get("path"),
                                              "shared": True, "load_ms": 0.0}
        elif "book_classifier" in files:
            self.book_classifier = self._load(
                "book_classifier", files["book_classifier"],
                lambda p: _clip_classifier(p, files["book_classifier"]["prompts_path"], bc.get("threads", 2)))

    def _load(self, name, info, factory):
        if not info["enabled"]:
            self.status[name] = {"loaded": False, "reason": "disabled in config", "path": info["path"]}
            return None
        if not info["exists"]:
            self.status[name] = {"loaded": False, "reason": "model file not found", "path": info["path"]}
            return None
        t0 = time.perf_counter()
        try:
            task = factory(info["path"])
            self.status[name] = {"loaded": True, "reason": "", "path": info["path"],
                                 "load_ms": round((time.perf_counter() - t0) * 1000, 1)}
            return task
        except ModuleNotFoundError as e:                 # e.g. the CLIP book helper without `onnxruntime`
            log.warning("could not load %s: Python package '%s' is not installed (pip install -r requirements.txt)",
                        name, e.name)
            self.status[name] = {"loaded": False, "reason": f"package not installed: {e.name}", "path": info["path"]}
            return None
        except Exception as e:                           # corrupt or incompatible model file
            log.warning("could not load %s: %s", name, type(e).__name__)
            self.status[name] = {"loaded": False, "reason": f"load failed: {type(e).__name__}",
                                 "path": info["path"]}
            return None

    @property
    def ready(self) -> bool:
        return self.face_detector is not None

    def _resize(self, frame):
        h, w = frame.shape[:2]
        if w <= self.work_width:
            return frame
        return cv2.resize(frame, (self.work_width, int(h * self.work_width / w)))

    def process(self, frame_bgr, ts: float) -> FrameSignals:
        if frame_bgr is None:
            return FrameSignals(ts=ts, status=CANNOT_ANALYZE, reason="no_frame")
        frame = self._resize(frame_bgr)
        q = self.quality.check(frame, ts)
        if not q.ok:
            return FrameSignals(ts=ts, status=CANNOT_ANALYZE, reason=q.reason, metrics=q.metrics)
        if not self.ready:
            return FrameSignals(ts=ts, status=MODEL_UNAVAILABLE, reason="face_detector", metrics=q.metrics)

        ms = max(int(ts * 1000), self._last_ms + 1)      # VIDEO mode: strictly increasing
        self._last_ms = ms
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB,
                               data=np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        w = frame.shape[1]

        faces = self.face_detector.detect_for_video(image, ms).detections
        sig = FrameSignals(ts=ts, status=ANALYZED, face_count=len(faces), metrics=q.metrics)
        if faces:
            sig.face_width_ratio = round(max(d.bounding_box.width for d in faces) / w, 3)

        if faces and self.landmarker is not None:
            if sig.face_width_ratio is not None and sig.face_width_ratio < self.min_face_width_ratio:
                sig.reason = "face_too_small"            # head pose not analysed; not an indication
            else:
                lm = self.landmarker.detect_for_video(image, ms)
                if lm.facial_transformation_matrixes:
                    sig.landmarks_ok = True
                    sig.yaw, sig.pitch = yaw_pitch_from_matrix(lm.facial_transformation_matrixes[0])
                if lm.face_blendshapes:
                    sig.jaw_open = next((round(c.score, 3) for c in lm.face_blendshapes[0]
                                         if c.category_name == "jawOpen"), None)
                else:
                    sig.landmarks_ok = False

        if self.object_detector is not None and (
                self._last_phone_ts is None or ts - self._last_phone_ts >= self.phone_every_s):
            self._last_phone_ts = ts
            dets = self.object_detector.detect_for_video(image, ms).detections
            top = [(d.categories[0].category_name, d.categories[0].score) for d in dets if d.categories]
            fh, fw = frame.shape[:2]
            sig.boxes = [{"label": d.categories[0].category_name, "score": round(d.categories[0].score, 3),
                          "box": [round(d.bounding_box.origin_x / fw, 4), round(d.bounding_box.origin_y / fh, 4),
                                  round(d.bounding_box.width / fw, 4), round(d.bounding_box.height / fh, 4)]}
                         for d in dets if d.categories]
            phones = [sc for name, sc in top if name == "cell phone"]
            sig.phone_score = round(max(phones), 3) if phones else 0.0
            books = [sc for name, sc in top if name == "book"]
            sig.book_score = round(max(books), 3) if books else 0.0
            # The detector runs at the lowest threshold any rule needs; persons keep their own threshold.
            sig.person_count = sum(1 for name, sc in top if name == "person" and sc >= self.person_min_score)

        # CLIP book score: only on the frames it ran (None in between, like the detector scores)
        if self.book_classifier is not None and (
                self._last_book_ts is None or ts - self._last_book_ts >= self.book_every_s):
            self._last_book_ts = ts
            try:
                sig.book_clip_score = self.book_classifier.score(frame)
            except Exception as e:                       # never stop the analysis for the optional book model
                log.warning("book classifier failed: %s", type(e).__name__)
        return sig

    def close(self):
        own_book = None if self._shared_book else self.book_classifier       # a shared CLIP stays open for the others
        for task in (self.face_detector, self.landmarker, self.object_detector, own_book):
            if task is not None:
                try:
                    task.close()
                except Exception:
                    pass
