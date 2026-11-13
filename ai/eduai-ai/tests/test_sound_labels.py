"""Sound labels: MUSIK/MEDIA, BICARA_SISWA (info), BICARA_MULUT_DIAM (OTHER_VOICE), BISIKAN. What was heard, never who."""
import copy

import pytest

from test_voice import cfg, play, opened  # noqa: F401  (fixture + helpers)
from eduai_ai.events import Event, SOUND_TYPES
from eduai_ai.temporal import STATE_INDICATION, EventEngine

TALK = lambda t: 0.05 if int(t * 2) % 2 else 0.4                     # noqa: E731  mouth opens and closes


def closed(events, name):
    return [e for e in events if e.indicator == name and e.status == "closed"]


def test_still_mouth_speech_carries_scores_and_type(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, t = play(e, 4, speech=0.82, media=0.05)
    o = opened(ev)[0]
    assert o.category == "indication"
    assert o.details == {"sound_type": "BICARA_MULUT_DIAM", "speech": 0.82, "whisper": 0.0, "media": 0.05,
                         "mouth_movement": 0.0}
    ev, _ = play(e, 4, t0=t)                                         # silence closes it, same scores kept
    c = closed(ev, "OTHER_VOICE")[0]
    assert c.event_id == o.event_id and c.details["speech"] == 0.82 and c.to_dict()["details"]["sound_type"] == "BICARA_MULUT_DIAM"


def test_student_talking_is_info_never_indication(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 6, speech=0.9, jaw=TALK)
    assert opened(ev) == []
    s = opened(ev, "STUDENT_SPEECH")
    assert len(s) == 1 and s[0].category == "info" and s[0].details["sound_type"] == "BICARA_SISWA"
    assert s[0].details["mouth_movement"] >= cfg["indicators"]["OTHER_VOICE"]["mouth_still_max"]
    assert e.analysis_state() != STATE_INDICATION                   # info does not make the student "indication"


def test_student_speech_cannot_be_configured_as_indication(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["indicators"]["STUDENT_SPEECH"]["category"] = "indication"
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 6, speech=0.9, jaw=TALK)
    assert opened(ev, "STUDENT_SPEECH")[0].category == "info"


def test_music_dominant_is_media_info_and_not_voice(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 6, speech=0.3, media=0.9)
    assert opened(ev) == [] and opened(ev, "STUDENT_SPEECH") == []
    m = opened(ev, "MEDIA_SOUND")
    assert len(m) == 1 and m[0].category == "info" and m[0].details == {
        "sound_type": "MUSIK_MEDIA", "speech": 0.3, "whisper": 0.0, "media": 0.9, "mouth_movement": 0.0}


def test_media_category_and_thresholds_come_from_config(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["indicators"]["MEDIA_SOUND"].update(category="indication", media_min=0.95)
    e = EventEngine(cfg, "1", "1")
    assert opened(play(e, 6, media=0.9)[0], "MEDIA_SOUND") == []    # below the configured threshold
    ev, _ = play(e, 6, media=0.97, t0=10)
    assert opened(ev, "MEDIA_SOUND")[0].category == "indication"
    cfg["indicators"]["MEDIA_SOUND"]["category"] = "keputusan"
    with pytest.raises(ValueError):
        EventEngine(cfg, "1", "1")


def test_media_needs_no_face_but_speech_labels_do(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 6, speech=0.9, faces=0)
    assert opened(ev) == [] and opened(ev, "STUDENT_SPEECH") == []   # mouth unknown -> no speech label
    ev, _ = play(e, 6, media=0.9, faces=0, t0=10)
    assert len(opened(ev, "MEDIA_SOUND")) == 1


def test_each_label_has_its_own_cooldown(cfg):
    e = EventEngine(cfg, "1", "1")
    evs, t = [], 0.0
    for _ in range(3):                                               # 3 media episodes 8 s apart; cooldown 60 s
        ev, t = play(e, 4, media=0.9, t0=t); evs += ev
        ev, t = play(e, 4, t0=t); evs += ev
    assert len(opened(evs, "MEDIA_SOUND")) == 1
    ev, _ = play(e, 4, speech=0.8, t0=t)                             # another label is not blocked by it
    assert len(opened(ev)) == 1


def test_exactly_one_label_at_a_time(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 6, speech=0.6, whisper=0.7, media=0.2)
    names = {x.indicator for x in ev if x.status == "open"}
    assert names == {"WHISPER"}


def test_peaks_reset_between_episodes(cfg):
    e = EventEngine(cfg, "1", "1")
    ev, t = play(e, 4, speech=0.95)
    ev, t = play(e, 40, t0=t)                                        # closes; past the 30 s cooldown
    ev, _ = play(e, 4, speech=0.5, t0=t)
    assert opened(ev)[0].details["speech"] == 0.5


def test_flush_keeps_category_and_details(cfg):
    e = EventEngine(cfg, "1", "1")
    play(e, 6, speech=0.9, jaw=TALK)
    out = [x for x in e.flush() if x.indicator == "STUDENT_SPEECH"]
    assert out[0].category == "info" and out[0].details["sound_type"] == "BICARA_SISWA"


def test_sound_types_never_name_a_person():
    assert set(SOUND_TYPES) == {"BICARA_MULUT_DIAM", "BICARA_SISWA", "BISIKAN", "MUSIK_MEDIA", "KERTAS_BUKU"}   # kinds of sound, never a person
    with pytest.raises(ValueError):
        Event("1", "1", "OTHER_VOICE", "keputusan", "open", 0.0)


def paper_play(engine, seconds, paper, t0=0.0, faces=1):
    from test_voice import frame, DT
    events, t = [], t0
    while t < t0 + seconds - 1e-9:
        engine.update_audio(t, 0.0, 0.0, 0.0, paper)
        events += engine.update(frame(t, 0.05, faces))
        t += DT
    return events, t


def test_paper_sound_is_a_book_indication_with_its_score(cfg):
    assert SOUND_TYPES["KERTAS_BUKU"].startswith("kertas")
    e = EventEngine(cfg, "1", "1")
    ev, t = paper_play(e, 0.5, 0.6)
    assert opened(ev, "BOOK_SOUND") == []                         # under min_duration (1 s)
    ev, t = paper_play(e, 1.5, 0.6, t0=t)
    o = opened(ev, "BOOK_SOUND")
    assert len(o) == 1 and o[0].category == "indication" and o[0].details["sound_type"] == "KERTAS_BUKU" and o[0].details["paper"] == 0.6
    ev, _ = paper_play(e, 3, 0.0, t0=t)
    c = closed(ev, "BOOK_SOUND")
    assert c and c[0].event_id == o[0].event_id and "kertas" in c[0].reason


def test_paper_sound_below_threshold_or_from_old_browsers_never_opens(cfg):
    e = EventEngine(cfg, "1", "1")
    assert opened(paper_play(e, 5, 0.2)[0], "BOOK_SOUND") == []    # paper_min 0.25
    e = EventEngine(cfg, "1", "1")
    ev, _ = play(e, 5, speech=0.1)                                # older browser: no paper score at all
    assert opened(ev, "BOOK_SOUND") == []


def test_paper_sound_needs_no_face(cfg):
    e = EventEngine(cfg, "1", "1")
    assert len(opened(paper_play(e, 3, 0.7, faces=0)[0], "BOOK_SOUND")) == 1
