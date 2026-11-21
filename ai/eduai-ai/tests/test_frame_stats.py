"""Frame statistics per episode in Event.details (Tahap 2, 20 Nov 2026; temporal.FRAME_STATS, stats_version 1).

peak and mean are kept apart; confidence exists only where a model score exists (phone, book sources);
FACE_ABSENT / MULTIPLE_PERSONS / HEAD_TURN get a frame count and nothing that looks like a confidence."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eduai_ai.config import load_config  # noqa: E402
from eduai_ai.signals import ANALYZED, FrameSignals  # noqa: E402
from eduai_ai.temporal import BOOK_SCORE_NOTE, PHONE_SOURCE, EventEngine, SustainedIndicator  # noqa: E402

A = pytest.approx


@pytest.fixture
def cfg():
    return load_config(ROOT / "config.yaml")


def frame(ts, faces=1, phone=None, book=None, clip=None):
    return FrameSignals(ts=ts, status=ANALYZED, face_count=faces, phone_score=phone, book_score=book, book_clip_score=clip)


def run(engine, frames):
    out = []
    for f in frames:
        out += engine.update(f)
    return out


def only(events, indicator, status):
    got = [e for e in events if e.indicator == indicator and e.status == status]
    assert len(got) == 1, [(e.indicator, e.status) for e in events]
    return got[0]


def test_sustained_indicator_counts_active_frames_and_resets(cfg):
    t = SustainedIndicator(min_duration_s=1.0, release_s=0.5)
    t.update(0.0, True, 0.4)
    t.update(0.2, False)                                   # candidate broken: everything starts again
    assert t.stats() == {"n_active": 0, "n_valued": 0, "value_sum": 0.0, "peak": None}
    for ts, v in ((1.0, 0.6), (1.5, None), (2.0, 0.8)):
        t.update(ts, True, v)
    assert t.is_open and t.stats()["n_active"] == 3 and t.stats()["n_valued"] == 2
    t.update(2.2, False)
    t.update(2.8, False)                                   # released: stats move to closed_stats
    assert not t.is_open and t.closed_stats == {"n_active": 3, "n_valued": 2, "value_sum": A(1.4), "peak": 0.8}
    assert t.stats()["n_active"] == 0


def test_phone_has_peak_mean_and_frame_count(cfg):
    e = EventEngine(cfg, "1", "7")
    ev = run(e, [frame(t, phone=p) for t, p in ((0.0, 0.6), (0.5, 0.8), (1.0, 0.7), (1.5, 0.9))])
    o = only(ev, "PHONE_VISIBLE", "open")
    assert o.details["stats_version"] == 1 and o.details["n_frames"] == 4
    assert o.details["confidence"] == {"source": PHONE_SOURCE, "peak": 0.9, "mean": A(0.75), "n": 4}
    ev = run(e, [frame(2.0, phone=0.5)] + [frame(t, phone=0.1) for t in (2.5, 3.0, 3.5, 4.0)])
    c = only(ev, "PHONE_VISIBLE", "closed")
    assert c.event_id == o.event_id and c.score == 0.9
    assert c.details["n_frames"] == 5 and c.details["confidence"]["mean"] == A(0.7) and c.details["confidence"]["peak"] == 0.9
    # the next episode (after the 30 s cooldown) starts from zero
    ev = run(e, [frame(40 + i * 0.5, phone=0.55) for i in range(4)])
    n = only(ev, "PHONE_VISIBLE", "open")
    assert n.details["n_frames"] == 4 and n.details["confidence"]["mean"] == A(0.55)


def test_face_absent_has_frame_count_but_no_confidence(cfg):
    e = EventEngine(cfg, "1", "7")
    ev = run(e, [frame(round(i * 0.2, 3), faces=0) for i in range(31)])          # 0.0 .. 6.0 s
    o = only(ev, "FACE_ABSENT", "open")
    assert o.score is None and o.details == {"stats_version": 1, "n_frames": 26}  # opened at 5.0 s
    ev = run(e, [frame(round(6.2 + i * 0.2, 3)) for i in range(8)])
    c = only(ev, "FACE_ABSENT", "closed")
    assert c.score is None and c.details == {"stats_version": 1, "n_frames": 31}
    assert "confidence" not in c.details and "book_sources" not in c.details


def test_book_keeps_coco_and_clip_apart(cfg):
    e = EventEngine(cfg, "1", "7")
    pairs = ((0.0, 0.1, 0.7), (0.5, None, 0.8), (1.0, 0.5, 0.65), (1.5, 0.2, 0.9))
    ev = run(e, [frame(t, phone=0.0 if b is not None else None, book=b, clip=c) for t, b, c in pairs])
    o = only(ev, "BOOK_VISIBLE", "open")
    src = o.details["book_sources"]
    assert src["coco"]["n"] == 3 and src["coco"]["passed"] == 1 and src["coco"]["peak"] == 0.5
    assert src["coco"]["mean"] == A(0.8 / 3, abs=1e-3)
    assert src["clip"]["n"] == 4 and src["clip"]["passed"] == 4 and src["clip"]["peak"] == 0.9
    assert src["clip"]["mean"] == A(0.7625, abs=1e-3)
    assert o.details["score_note"] == BOOK_SCORE_NOTE and o.details["n_frames"] == 4 and "confidence" not in o.details
    ev = run(e, [frame(t, phone=0.0, book=0.0, clip=0.1) for t in (2.0, 2.5, 3.0, 3.5)])
    c = only(ev, "BOOK_VISIBLE", "closed")
    assert c.details["book_sources"] == src and c.score == 0.9      # inactive frames are not added
    assert e._book_acc == {}                                        # episode over: next one starts fresh


def test_flush_sends_the_real_peak(cfg):
    e = EventEngine(cfg, "1", "7")
    run(e, [frame(t, phone=0.6) for t in (0.0, 0.5, 1.0, 1.5)])
    run(e, [frame(2.0, phone=0.95)])
    c = only(e.flush(), "PHONE_VISIBLE", "closed")
    assert c.score == 0.95                                           # was None before 20 Nov 2026
    assert c.details["n_frames"] == 5 and c.details["confidence"]["peak"] == 0.95


def test_sound_labels_details_are_unchanged(cfg):
    e = EventEngine(cfg, "1", "7")
    e.update_audio(0.0, speech=0.0, whisper=0.0, media=0.0, paper=0.6)
    ev = []
    for i in range(10):
        e.update_audio(i * 0.2, speech=0.0, whisper=0.0, media=0.0, paper=0.6)
        ev += e.update(frame(round(i * 0.2, 3)))
    o = only(ev, "BOOK_SOUND", "open")
    assert "n_frames" not in o.details and "stats_version" not in o.details and o.details["sound_type"] == "KERTAS_BUKU"
