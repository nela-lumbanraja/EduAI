"""BOOK_VISIBLE: COCO "book" from the same EfficientDet-Lite0 pass as the phone (rule tests; ported from the AI architecture package)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eduai_ai.config import load_config  # noqa: E402
from eduai_ai.events import INDICATORS  # noqa: E402
from eduai_ai.signals import ANALYZED, CANNOT_ANALYZE, FrameSignals  # noqa: E402
from eduai_ai.temporal import EventEngine  # noqa: E402

DT = 0.2


@pytest.fixture
def cfg():
    return load_config(ROOT / "config.yaml")



# ------------------------------------------------------------------ BOOK_VISIBLE
def sig(ts, book=None, phone=0.0, status=ANALYZED, faces=1, clip=None):
    if status != ANALYZED:
        return FrameSignals(ts=ts, status=status, reason="dark")
    return FrameSignals(ts=ts, status=ANALYZED, face_count=faces, book_score=book, phone_score=phone, book_clip_score=clip)


def feed(engine, frames):
    out = []
    for s in frames:
        out += engine.update(s)
    return out


def book_frames(t0, seconds, score):
    """Object detector runs every 0.5 s (phone_every_s); frames in between carry book_score=None."""
    out, t = [], t0
    while t < t0 + seconds - 1e-9:
        on_detector = abs((t * 2) - round(t * 2)) < 1e-6
        out.append(sig(t, book=score if on_detector else None))
        t = round(t + DT, 3)
    return out


def test_book_visible_needs_sustained_detection(cfg):
    assert INDICATORS["BOOK_VISIBLE"] == "Objek menyerupai buku terlihat"
    e = EventEngine(cfg, "1", "7")
    short = feed(e, book_frames(0.0, 1.0, 0.8) + book_frames(1.0, 4.0, 0.1))   # 1 s < min_duration 1.5 s
    assert [x for x in short if x.indicator == "BOOK_VISIBLE"] == []
    evs = feed(e, book_frames(6.0, 5.0, 0.72) + book_frames(11.0, 4.0, 0.0))
    book = [x for x in evs if x.indicator == "BOOK_VISIBLE"]
    assert [x.status for x in book] == ["open", "closed"]
    assert book[0].event_id == book[1].event_id and book[1].score == 0.72
    assert book[0].category == "indication" and "buku" in book[1].reason


def test_book_below_threshold_or_unknown_never_opens(cfg):
    e = EventEngine(cfg, "1", "7")
    frames = book_frames(0.0, 10.0, 0.34)                                       # min_score 0.35
    frames += [sig(10.0 + i * DT, book=None) for i in range(50)]               # detector not run / not loaded
    frames += [sig(20.0 + i * DT, status=CANNOT_ANALYZE) for i in range(50)]   # bad video
    assert [x for x in feed(e, frames) if x.indicator == "BOOK_VISIBLE"] == []


def test_book_cooldown_suppresses_repeats(cfg):
    e = EventEngine(cfg, "1", "7")
    evs = []
    t = 0.0
    for _ in range(3):                                   # 3 episodes 10 s apart, cooldown 30 s
        evs += feed(e, book_frames(t, 4.0, 0.9) + book_frames(t + 4.0, 6.0, 0.0))
        t += 10.0
    assert [x.status for x in evs if x.indicator == "BOOK_VISIBLE"] == ["open", "closed"]


def test_book_indicator_can_be_switched_off(cfg):
    cfg["indicators"]["BOOK_VISIBLE"]["enabled"] = False
    e = EventEngine(cfg, "1", "7")
    assert [x for x in feed(e, book_frames(0.0, 10.0, 0.95)) if x.indicator == "BOOK_VISIBLE"] == []
    del cfg["indicators"]["BOOK_VISIBLE"]                # older config file: indicator off, no crash
    e = EventEngine(cfg, "1", "7")
    assert [x for x in feed(e, book_frames(0.0, 10.0, 0.95)) if x.indicator == "BOOK_VISIBLE"] == []


def test_phone_and_book_are_independent(cfg):
    e = EventEngine(cfg, "1", "7")
    frames = [sig(i * 0.5, book=0.9, phone=0.0) for i in range(12)]
    names = {x.indicator for x in feed(e, frames)}
    assert "BOOK_VISIBLE" in names and "PHONE_VISIBLE" not in names




def test_book_is_caught_faster_since_nov_2026(cfg):
    """Config values requested on 10 Nov 2026: a held/opened book (lower score) is reported after 1.5 s."""
    b = cfg["indicators"]["BOOK_VISIBLE"]
    assert (b["min_score"], b["min_duration_s"]) == (0.35, 1.5)
    e = EventEngine(cfg, "1", "7")
    evs = feed(e, book_frames(0.0, 3.0, 0.4))            # weak "book" score (held at the webcam), 3 s
    assert [x.status for x in evs if x.indicator == "BOOK_VISIBLE"] == ["open"]


# ------------------------------------------------------------------ CLIP book classifier (15 Nov 2026)
# A spiral notebook held at the webcam: COCO "book" < 0.05, CLIP P(book) 0.93. Either signal may open BOOK_VISIBLE.
def clip_frames(t0, seconds, clip, coco=0.0, clip_every=0.5):
    """5 fps; COCO every 0.5 s, CLIP every `clip_every` s; None on frames a model did not run."""
    out, t = [], t0
    while t < t0 + seconds - 1e-9:
        on_coco = abs((t * 2) - round(t * 2)) < 1e-6
        on_clip = abs(t / clip_every - round(t / clip_every)) < 1e-6
        out.append(sig(t, book=coco if on_coco else None, clip=clip if on_clip else None))
        t = round(t + DT, 3)
    return out


def test_clip_alone_opens_book_visible_when_coco_sees_nothing(cfg):
    assert cfg["indicators"]["BOOK_VISIBLE"]["clip_min_score"] == 0.6
    e = EventEngine(cfg, "1", "7")
    evs = feed(e, clip_frames(0.0, 4.0, clip=0.93, coco=0.0) + clip_frames(4.0, 4.0, clip=0.05, coco=0.0))
    book = [x for x in evs if x.indicator == "BOOK_VISIBLE"]
    assert [x.status for x in book] == ["open", "closed"] and book[1].score == 0.93


def test_clip_below_threshold_never_opens(cfg):
    e = EventEngine(cfg, "1", "7")
    assert [x for x in feed(e, clip_frames(0.0, 10.0, clip=0.34)) if x.indicator == "BOOK_VISIBLE"] == []   # bookshelf


def test_models_on_different_frames_keep_their_last_value(cfg):
    """CLIP every 1 s, COCO every 0.5 s: COCO 0.0 in between must not reset a CLIP detection."""
    e = EventEngine(cfg, "1", "7")
    evs = feed(e, clip_frames(0.0, 3.0, clip=0.9, coco=0.0, clip_every=1.0))
    assert [x.status for x in evs if x.indicator == "BOOK_VISIBLE"] == ["open"]


def test_a_bad_frame_forgets_the_last_clip_value(cfg):
    e = EventEngine(cfg, "1", "7")
    frames = clip_frames(0.0, 1.0, clip=0.9) + [sig(1.0, status=CANNOT_ANALYZE)]
    frames += [sig(1.2 + i * DT, book=None) for i in range(20)]               # nothing measured afterwards
    assert [x for x in feed(e, frames) if x.indicator == "BOOK_VISIBLE"] == []


def test_book_probability_is_the_share_of_book_prompts():
    np = pytest.importorskip("numpy")
    from eduai_ai.book_clip import book_probability
    text = np.eye(4, dtype=np.float32)
    is_book = np.array([True, True, False, False])
    assert book_probability(np.array([1, 0, 0, 0], np.float32), text, is_book) > 0.99
    assert book_probability(np.array([0, 0, 0, 1], np.float32), text, is_book) < 0.01
    assert abs(book_probability(np.ones(4, np.float32), text, is_book) - 0.5) < 1e-6


SIGNALS = ROOT.parents[1] / "frontend" / "public" / "images" / "ai-signals"


def test_real_clip_model_on_sample_frames(cfg):
    """Real model (skipped without onnxruntime or the model file). A sanity check, not an accuracy evaluation."""
    pytest.importorskip("onnxruntime")
    cv2 = pytest.importorskip("cv2")
    from eduai_ai.book_clip import ClipBookClassifier
    from eduai_ai.perception import find_model_files
    info = find_model_files(cfg).get("book_classifier")
    if not info or not info["exists"]:
        pytest.skip("CLIP model not present (scripts/download_models.py --only book)")
    images = {n: cv2.imread(str(SIGNALS / n)) for n in ("2_book_in_view.png", "1_phone_in_view.png", "4_looking_away.png")}
    if any(v is None for v in images.values()):
        pytest.skip("sample images not present (git lfs pull)")
    c = ClipBookClassifier(info["path"], info["prompts_path"])
    thr = cfg["indicators"]["BOOK_VISIBLE"]["clip_min_score"]
    scores = {n: c.score(img) for n, img in images.items()}
    assert scores["2_book_in_view.png"] >= thr, scores
    assert scores["1_phone_in_view.png"] < thr and scores["4_looking_away.png"] < thr, scores
