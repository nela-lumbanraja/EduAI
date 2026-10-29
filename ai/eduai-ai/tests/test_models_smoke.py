"""Smoke tests with the REAL model files. Skipped when MediaPipe or the model files are
missing. They check that models load and produce sane signals on public sample
images (scikit-image); they are not an accuracy evaluation."""
import numpy as np
import pytest

from eduai_ai.config import load_config
from eduai_ai.perception import find_model_files

mp = pytest.importorskip("mediapipe")
skimage_data = pytest.importorskip("skimage.data")
cv2 = pytest.importorskip("cv2")


@pytest.fixture(scope="module")
def cfg():
    c = load_config()
    if not find_model_files(c)["face_detector"]["exists"]:
        pytest.skip("face detector model not present (scripts/download_models)")
    return c


def _bgr(img, noise_seed=None):
    out = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    if noise_seed is not None:            # identical frames would be treated as a frozen camera
        rng = np.random.default_rng(noise_seed)
        out = np.clip(out.astype(np.int16) + rng.integers(-6, 7, out.shape), 0, 255).astype(np.uint8)
    return out


def test_face_detector_on_sample_images(cfg):
    from eduai_ai.perception import MediaPipePerception
    p = MediaPipePerception(cfg)
    try:
        assert p.ready and p.status["face_detector"]["loaded"]
        face = p.process(_bgr(skimage_data.astronaut()), 1.0)
        assert face.status == "analyzed" and face.face_count == 1
        empty = p.process(_bgr(skimage_data.coffee()), 1.5)
        assert empty.status == "analyzed" and empty.face_count == 0
        flat = p.process(np.full((480, 640, 3), 128, np.uint8), 2.0)
        assert flat.status == "cannot_analyze"              # featureless frame is not "no face"
    finally:
        p.close()


def test_real_pipeline_face_absent(cfg):
    from eduai_ai.pipeline import StudentAnalyzer
    a = StudentAnalyzer(cfg, "S", "N")
    face, coffee = skimage_data.astronaut(), skimage_data.coffee()
    events, t, i = [], 0.0, 0
    for img, seconds in ((face, 4), (coffee, 8), (face, 7)):
        for _ in range(int(seconds * 2)):
            events += a.process(_bgr(img, i), t).events
            t += 0.5
            i += 1
    a.stop()
    fa = [e for e in events if e.indicator == "FACE_ABSENT"]
    assert [e.status for e in fa] == ["open", "closed"]
    assert all(e.category != "indication" or e.indicator == "FACE_ABSENT" for e in events)
