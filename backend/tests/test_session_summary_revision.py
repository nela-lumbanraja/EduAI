"""Session Report, Phase 4 revision (findings T1-T5): audio without samples, coverage 0 %, weights fingerprint,
indicators that follow the active configuration, full precision. Expected values are derived by hand in the comments.
Temporary databases only."""
import pytest

from app import session_summary as ss
from tests.test_session_summary_engine import World, A

ONES = {i: 1.0 for i in ss.SCORED}


# ---------------------------------------------------------------- T1: audio coverage apart from video coverage
def test_consented_audio_without_any_sample_is_excluded_not_zero(tmp_path):
    """Audio consent, 5 minutes of video, not one audio sample: the three sound labels leave the mean (no_audio_data).
    FACE_ABSENT 30 s of 300 s -> 0.1; P_total = 0.1 / 5 video indicators = 0.02 (not 0.1 / 8 = 0.0125)."""
    w = World(tmp_path, 5, audio=True)
    w.observe(0, 300)
    w.event("FACE_ABSENT", 0, 30)
    st = w.student()
    for i in ss.AUDIO_INDICATORS:
        assert i not in st["indicators"] and st["excluded"][i].startswith("no_audio_data")
    assert st["audio_accepted"] is True and st["audio_coverage"] == 0 and st["audio_samples"] == 0
    assert st["coverage"] == 1.0                                        # video coverage is reported apart
    assert ss.aggregate(st, ONES)["duration_score"] == A(0.02)


def test_partial_audio_interval_without_samples_counts_zero_with_reason(tmp_path):
    """10 minutes, video all the time, audio only in the first interval. OTHER_VOICE 0..30 s:
    interval 0 -> 30/300 = 0.1; interval 1 has no audio -> 0 with reason no_audio_data. P = (0.1 + 0) / 2 = 0.05.
    Audio coverage: interval 0 = 1.0, interval 1 = 0 -> 0.5; video coverage 1.0."""
    w = World(tmp_path, 10, audio=True)
    w.observe(0, 600)
    w.hear(0, 300)
    w.event("OTHER_VOICE", 0, 30)
    result = w.run()
    st = result["students"][0]
    k0, k1 = st["intervals"]
    assert k0["audio_coverage"] == 1.0 and k1["audio_coverage"] == 0 and k1["audio_s"] == 0
    assert k0["indicators"]["OTHER_VOICE"]["duration_score"] == A(0.1) and k0["indicators"]["OTHER_VOICE"]["no_data_reason"] is None
    assert k1["indicators"]["OTHER_VOICE"] == {**k1["indicators"]["OTHER_VOICE"], "duration_score": 0.0, "no_data_reason": "no_audio_data"}
    assert k1["indicators"]["FACE_ABSENT"]["no_data_reason"] is None         # video is fine in that interval
    assert st["indicators"]["OTHER_VOICE"]["duration_score"] == A(0.05)
    assert st["audio_coverage"] == A(0.5) and st["coverage"] == 1.0
    # the reason is stored with the interval row of the snapshot
    rows = ss.snapshot_statements({**result, "status": "lengkap"}, "v", "t")
    reason = {(p[2], p[3], p[4]): p[15] for _, p in rows if len(p) == 19}
    assert reason[("OTHER_VOICE", 1, "")] == "no_audio_data" and reason[("FACE_ABSENT", 1, "")] is None


def test_without_audio_consent_there_is_no_audio_coverage(tmp_path):
    w = World(tmp_path, 5, audio=False)
    w.observe(0, 300)
    st = w.student()
    assert st["audio_coverage"] is None and st["audio_samples"] is None and st["intervals"][0]["audio_s"] is None


# ---------------------------------------------------------------- T2: coverage 0 %
def test_zero_coverage_keeps_score_zero_but_says_it_is_not_supported(tmp_path):
    """Observed but never analysable (a cannot-analyse episode over the whole time): coverage 0, scores 0 (option a)
    and a note that 0 is not evidence of no indication."""
    w = World(tmp_path, 5)
    w.observe(0, 300)
    w.event("CANNOT_ANALYZE", 0, 300, category="cannot_analyze")
    result = w.run()
    st = result["students"][0]
    assert st["coverage"] == 0 and st["analysable_s"] == 0
    assert "Cakupan pengamatan 0%" in st["coverage_note"] and "bukan bukti" in st["coverage_note"]
    assert ss.aggregate(st, ONES)["duration_score"] == 0.0
    rows = ss.snapshot_statements({**result, "status": "lengkap"}, "v", "t")
    star = [p for _, p in rows if len(p) == 20 and p[2] == "*"][0]
    import json
    assert "bukan bukti" in json.loads(star[13])["coverage_note"]
    ok = World(tmp_path, 5, name="ok.sqlite3")
    ok.observe(0, 300)
    assert ok.student()["coverage_note"] is None


# ---------------------------------------------------------------- T3: weights fingerprint
def test_config_version_changes_with_the_weights():
    cfg = {"version": "0.2-provisional"}
    a, b = ss.config_version(cfg, ONES), ss.config_version(cfg, {**ONES, "PHONE_VISIBLE": 2.0})
    assert a.startswith("0.2-provisional;w=") and a != b
    assert a == ss.config_version(cfg, dict(reversed(list(ONES.items()))))          # order does not matter


# ---------------------------------------------------------------- T4: indicators follow the active configuration
def test_config_exclusions():
    from eduai_ai.config import load_config
    assert ss.config_exclusions(load_config(None)) == {}                 # project config: everything active
    assert ss.config_exclusions(None) == {}
    cfg = {"indicators": {"BOOK_VISIBLE": {"enabled": False}, "WHISPER": {"enabled": True, "category": "info"},
                          "BOOK_SOUND": {"enabled": False}},
           "models": {"object_detector": {"enabled": True}, "face_landmarker": {"enabled": False},
                      "book_classifier": {"enabled": True}}}
    ex = ss.config_exclusions(cfg)
    assert set(ex) == {"BOOK_VISIBLE", "WHISPER", "BOOK_SOUND", "HEAD_TURN"}
    assert "kategori info" in ex["WHISPER"] and "dinonaktifkan" in ex["BOOK_SOUND"] and "face landmarker" in ex["HEAD_TURN"]
    # BOOK_VISIBLE is off by default in eduai_ai.temporal; no object detector -> no phone
    ex2 = ss.config_exclusions({"indicators": {}, "models": {"object_detector": {"enabled": False}, "face_landmarker": {}}})
    assert set(ex2) == {"BOOK_VISIBLE", "PHONE_VISIBLE"}


def test_excluded_by_config_is_left_out_of_the_mean_not_zero(tmp_path):
    """BOOK_VISIBLE disabled in the config: 4 video indicators remain. FACE_ABSENT 0.1 -> P_total 0.1 / 4 = 0.025."""
    w = World(tmp_path, 5)
    w.observe(0, 300)
    w.event("FACE_ABSENT", 0, 30)
    cfg = {"indicators": {"BOOK_VISIBLE": {"enabled": False}}, "models": {"object_detector": {}, "face_landmarker": {}}}
    result = ss.compute_exam(w.db, w.exam(), "UTC", w_now(), cfg=cfg)
    st = result["students"][0]
    assert "BOOK_VISIBLE" not in st["indicators"] and "dinonaktifkan" in st["excluded"]["BOOK_VISIBLE"]
    assert result["config_excluded"] == {"BOOK_VISIBLE": st["excluded"]["BOOK_VISIBLE"]}
    assert ss.aggregate(st, ONES)["duration_score"] == A(0.025)


def w_now():
    from tests.test_session_summary_engine import FAR
    return FAR


# ---------------------------------------------------------------- T5: full precision, weighted mean is not coverage x
def test_weighted_mean_is_not_a_multiplication_by_coverage_and_keeps_full_precision(tmp_path):
    """10 minutes, video only 0..150 s (coverage = (150/300 + 0) / 2 = 0.25).
    FACE_ABSENT 60..90 s -> 30/150 = 0.2 in interval 0, 0 in interval 1 -> P = 0.1.
    PHONE_VISIBLE 0..10 s -> 10/150 = 1/15 -> P = 1/30.
    P_total = (0.1 + 1/30 + 0 + 0 + 0) / 5 = (4/30) / 5 = 4/150 = 0.026666...
    A multiplication by coverage would give (0.1 + 1/30) x 0.25 = 0.0333 or 0.0267 x 0.25 = 0.0067 - both differ."""
    w = World(tmp_path, 10)
    w.observe(0, 150)
    w.event("FACE_ABSENT", 60, 90)
    w.event("PHONE_VISIBLE", 0, 10)
    st = w.student()
    assert st["coverage"] == A(0.25)
    assert st["indicators"]["FACE_ABSENT"]["duration_score"] == A(0.1)
    assert st["indicators"]["PHONE_VISIBLE"]["duration_score"] == pytest.approx(1 / 30, rel=1e-12)
    total = ss.aggregate(st, ONES)["duration_score"]
    assert total == pytest.approx(4 / 150, rel=1e-12)
    assert total != round(total, 4)                                     # not rounded before the end
    assert total != A((0.1 + 1 / 30) * st["coverage"]) and total != A(total * st["coverage"])
