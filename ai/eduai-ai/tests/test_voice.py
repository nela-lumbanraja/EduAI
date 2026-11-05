"""OTHER_VOICE rule: speech-sound scores (from the student's browser) + mouth movement (jawOpen)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eduai_ai.config import load_config  # noqa: E402
from eduai_ai.events import INDICATORS  # noqa: E402
from eduai_ai.signals import ANALYZED, CANNOT_ANALYZE, FrameSignals  # noqa: E402
from eduai_ai.temporal import STATE_INDICATION, VOICE_DEFAULTS, EventEngine  # noqa: E402

DT = 0.5          # browser path uploads ~2 frames per second


@pytest.fixture
def cfg():
    return load_config(ROOT / "config.yaml")


def frame(t, jaw=0.05, faces=1, status=ANALYZED):
    return FrameSignals(ts=t, status=status, face_count=faces if status == ANALYZED else None,
                        jaw_open=jaw if status == ANALYZED else None)


def play(engine, seconds, *, speech=0.0, whisper=0.0, media=0.0, jaw=lambda t: 0.05, faces=1, t0=0.0,
         audio=True, status=ANALYZED):
    events, t = [], t0
    while t < t0 + seconds - 1e-9:
        if audio:
            engine.update_audio(t, speech, whisper, media)
        events += engine.update(frame(t, jaw(t), faces, status))
        t += DT
    return events, t


def opened(events, name="OTHER_VOICE"):
    return [e for e in events if e.indicator == name and e.status == "open"]


def test_config_section_and_label(cfg):
    assert cfg["indicators"]["OTHER_VOICE"]["enabled"] is True
    assert INDICATORS["OTHER_VOICE"] == "Suara bicara terdengar saat mulut siswa diam"


def test_speech_with_still_mouth_opens_after_min_duration(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 1.5, speech=0.8)
    assert opened(ev) == []                                       # 2 s not reached yet
    ev, _ = play(e, 2.0, speech=0.8, t0=1.5)
    o = opened(ev)
    assert len(o) == 1 and o[0].category == "indication" and o[0].score == 0.8
    assert "mulut siswa tampak diam" in o[0].reason
    assert e.analysis_state() == STATE_INDICATION


def test_student_talking_moving_mouth_is_not_flagged(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 10, speech=0.9, jaw=lambda t: 0.05 if int(t * 2) % 2 else 0.4)   # mouth opens/closes
    assert opened(ev) == []


def test_silence_and_quiet_scores_are_not_flagged(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 10, speech=0.1, whisper=0.05)
    assert opened(ev) == []


def test_whisper_dominant_is_its_own_label(cfg):
    """Whisper above the speech score is BISIKAN (WHISPER), no longer counted as OTHER_VOICE."""
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 4, whisper=0.35)
    assert opened(ev) == []
    w = opened(ev, "WHISPER")
    assert len(w) == 1 and w[0].score == 0.35 and w[0].details["sound_type"] == "BISIKAN"


def test_music_or_tv_dominating_is_not_flagged(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 10, speech=0.4, media=0.7)
    assert opened(ev) == []


def test_no_audio_means_unknown_never_opens(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 10, audio=False)
    assert opened(ev) == []


def test_stale_audio_is_ignored(cfg):
    e = EventEngine(cfg, "1", "1")
    e.update_audio(0.0, 0.9, 0.0, 0.0)                            # one old sample, then nothing
    ev = []
    for i in range(20):
        ev += e.update(frame(5.0 + i * DT))
    assert opened(ev) == []


def test_two_faces_or_no_face_is_not_this_rule(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 10, speech=0.9, faces=2)
    assert opened(ev) == []                                       # MULTIPLE_PERSONS covers this case
    e2 = EventEngine(cfg, "1", "2")
    ev2, _ = play(e2, 10, speech=0.9, faces=0)
    assert opened(ev2) == []


def test_bad_video_quality_does_not_open(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 10, speech=0.9, status=CANNOT_ANALYZE)
    assert opened(ev) == []


def test_closes_with_same_event_id_when_student_starts_talking(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, t = play(e, 4, speech=0.8)
    first = opened(ev)[0]
    ev2, _ = play(e, 4, speech=0.8, jaw=lambda t: 0.05 if int(t * 2) % 2 else 0.4, t0=t)
    closed = [x for x in ev2 if x.indicator == "OTHER_VOICE" and x.status == "closed"]
    assert len(closed) == 1 and closed[0].event_id == first.event_id


def test_cooldown_prevents_repeated_popups(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, t = play(e, 4, speech=0.8)
    ev2, t = play(e, 2, speech=0.0, t0=t)                         # closes
    ev3, _ = play(e, 6, speech=0.8, t0=t)                         # within 30 s cooldown
    assert len(opened(ev)) == 1 and opened(ev3) == []


def test_config_without_section_uses_defaults(cfg):
    old = {**cfg, "indicators": {k: v for k, v in cfg["indicators"].items() if k != "OTHER_VOICE"}}
    e = EventEngine(old, "1", "1")
    assert e.voice == VOICE_DEFAULTS
    ev, _ = play(e, 4, speech=0.8)
    assert len(opened(ev)) == 1


def test_can_be_disabled(cfg):
    off = {**cfg, "indicators": {**cfg["indicators"], "OTHER_VOICE": {**cfg["indicators"]["OTHER_VOICE"],
                                                                      "enabled": False}}}
    e = EventEngine(off, "1", "1")
    ev, _ = play(e, 10, speech=0.9)
    assert opened(ev) == []


def test_flush_closes_open_voice_event(cfg):
    e = EventEngine(cfg, "1", "1")
    play(e, 4, speech=0.8)
    out = e.flush()
    assert any(x.indicator == "OTHER_VOICE" and x.status == "closed" for x in out)
