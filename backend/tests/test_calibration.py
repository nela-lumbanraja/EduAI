"""Session Report Phase 5, Tahap 3: applying a session calibrator in the backend (design revisi 4).

Synthetic calibrator files only; temporary databases only. Checks: no calibrator = Phase 4 behaviour; C6 (SHA-256 of
the approved artefact, separate setting, empty = not approved); C7 (model fingerprint, unavailable never matches,
models_mismatch with distinguishable details); the 10 approved reason codes; probability only at finalisation (T3-2);
frozen snapshot; scores, coverage, intervals and ALERT data unchanged."""
import importlib.util
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import calibration
from app import session_summary as ss
from app import summary
from eduai_ai import session_calibration as sc
from tests.test_api import jpeg, login, uid
from tests.test_report import client  # noqa: F401  (fixture: fresh app and database per test)
from tests.test_session_summary_aggregation import by_student, prepare

VIDEO = sorted(ss.VIDEO_INDICATORS)
GOOD_METRICS = {"calibration_slope": {"value": 1.0, "ci95": [0.9, 1.1], "undefined_fraction": 0.0},
                "calibration_intercept": {"value": 0.0, "ci95": [-0.1, 0.1], "undefined_fraction": 0.0},
                "brier_skill_score": {"value": 0.2, "ci95": [0.1, 0.3], "undefined_fraction": 0.0},
                "auroc": {"value": 0.8, "ci95": [0.7, 0.9], "undefined_fraction": 0.0}}


# ---------------------------------------------------------------- helpers
def full_session(client):
    """siswa1 analysed for the whole 2-minute exam (coverage 1.0), face absent 30..60 s; no audio consent."""
    db = client.app.state.db
    hs, hp = login(client, "siswa1@gmail.com"), login(client, "pengawas1@gmail.com")
    assert client.post("/api/exams/1/consent", headers=hs, json={"accepted": True}).status_code == 200
    assert client.post("/api/exams/1/join", headers=hs).status_code == 200
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
    db.run("UPDATE exams SET date=?, start_time='08:00', duration_min=2 WHERE id=1",
           ((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),))
    T = summary.exam_window(db.one("SELECT * FROM exams WHERE id=1"), client.app.state.settings.exam_timezone)[0].timestamp()
    for i in range(121):
        client.app.state.ai.clock = lambda i=i: T + i
        r = client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(100 if 30 <= i < 60 else 200), "image/jpeg")})
        assert r.status_code == 202, r.text
    assert client.post("/api/exams/1/monitoring/stop", headers=hp).status_code == 200
    for e in db.all("SELECT event_id FROM events WHERE exam_id=1 AND category='indication'"):   # finalisation needs reviews
        assert client.post(f"/api/events/{e['event_id']}/reviews", headers=hp, json={"decision": "Valid", "note": ""}).status_code == 201
    return hp, uid(client, "siswa1@gmail.com")


def report_without_signed_links(client, hp):
    """The session report (cases, ALERT rules, by_indicator, events) minus the time-dependent signed evidence links."""
    r = client.get("/api/sessions/1/report", headers=hp).json()
    r["events"] = [{k: v for k, v in e.items() if k != "evidence"} for e in r["events"]]
    return r


def cfg_version(client):
    cfg = client.app.state.ai.cfg
    return ss.config_version(cfg, ss.load_weights(cfg)["weights"])


def calibrator_doc(client, **over):
    doc = {"format": sc.FORMAT, "version": "uji-1", "method": "platt", "a": 4.0, "b": -3.0,
           "target_definition": "K1 (uji, data buatan)", "algo_version": sc.ALGO_VERSION,
           "weights_fingerprint": calibration.weights_fingerprint(cfg_version(client)), "indicator_set": VIDEO,
           "min_coverage": 0.5, "min_audio_coverage": 0.5,
           "trained_on": {"calibration": {"pos": 60, "neg": 60}, "test": {"pos": 120, "neg": 130}},
           "metrics_test": GOOD_METRICS, "evaluation_verdict": "memadai",
           "lineage": {"criteria_version": sc.CRITERIA_VERSION, "criteria_sha256": sc.criteria_sha256(),
                       "models_fingerprint": client.app.state.ai.models_fingerprint()},
           "synthetic_data": True, "approved_by": None}
    for k, v in over.items():
        if k == "lineage":
            doc["lineage"] = {**doc["lineage"], **v}
        else:
            doc[k] = v
    return doc


def install(client, tmp_path, doc=None, text=None, approve=True, name="cal.json"):
    """Write a calibrator and set both settings (T3-1 location, C6 approved SHA-256 of exactly this file)."""
    p = tmp_path / name
    p.write_text(text if text is not None else json.dumps(doc), encoding="utf-8")
    s = client.app.state.settings
    s.session_calibrator = str(p)
    s.session_calibrator_sha256 = sc.file_sha256(p) if approve is True else (approve or "")
    return p


def live(client, hp, sid):
    return by_student(client.get("/api/sessions/1/session-summary", headers=hp).json(), sid)


def numbers(st):
    """Everything Phase 4 computes for a student (must never depend on calibration)."""
    return {"indicators": {i: v["duration_score"] for i, v in st["indicators"].items()}, "coverage": st["coverage"],
            "sum_w": st["sum_w"], "observed_s": st["observed_s"], "excluded": st["excluded"],
            "total": st["total"]["duration_score"], "weights_used": st["total"]["weights_used"],
            "model_availability": st.get("model_availability"), "intervals": st.get("intervals")}


# ---------------------------------------------------------------- no calibrator: Phase 4 behaviour
def test_without_a_calibrator_nothing_changes(client):
    hp, sid = full_session(client)
    db = client.app.state.db
    phase4 = by_student(ss.compute_exam(db, db.one("SELECT * FROM exams WHERE id=1"), client.app.state.settings.exam_timezone,
                                        weights=ss.load_weights(client.app.state.ai.cfg), cfg=client.app.state.ai.cfg), sid)
    me = live(client, hp, sid)
    assert numbers(me) == numbers(phase4)                                  # identical to the Phase 4 computation
    cal = me["total"]["calibration"]
    assert cal["status"] == "not_calibrated" and cal["probability"] is None and cal["reasons"] == ["no_calibrator"]
    assert "Belum tersedia" in cal["note"]
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    f = live(client, hp, sid)
    assert f["total"]["calibration"] == {"status": "not_calibrated", "version": None, "probability": None}
    assert f["calibration_reasons"] == ["no_calibrator"] and f["calibration_approved_sha256"] is None
    assert len(f["models_fingerprint"]) == 64                              # C7: recorded at finalisation
    assert db.one("SELECT COUNT(*) n FROM session_participant_summary WHERE calibrated_probability IS NOT NULL")["n"] == 0


# ---------------------------------------------------------------- valid and approved: probability only when final
def test_valid_calibrator_gives_a_probability_only_in_the_final_snapshot(client, tmp_path):
    hp, sid = full_session(client)
    install(client, tmp_path, calibrator_doc(client))
    me = live(client, hp, sid)
    assert me["coverage"] == pytest.approx(1.0) and me["model_availability"]["status"] == "lengkap"
    cal = me["total"]["calibration"]
    assert cal["status"] == "not_calibrated" and cal["probability"] is None             # T3-2: live has no number
    assert cal["reasons"] == [] and cal["eligible_at_finalization"] is True and "snapshot final" in cal["note"]

    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    f = live(client, hp, sid)
    R = f["total"]["duration_score"]
    expected = 1 / (1 + math.exp(-(4.0 * R - 3.0)))
    assert f["total"]["calibration"]["status"] == "calibrated" and f["total"]["calibration"]["version"] == "uji-1"
    assert f["total"]["calibration"]["probability"] == pytest.approx(expected, rel=1e-12, abs=1e-15)
    assert f["calibration_reasons"] == [] and f["calibration_approved_sha256"] == client.app.state.settings.session_calibrator_sha256
    assert f["total"]["duration_score"] == pytest.approx(me["total"]["duration_score"])   # R itself unchanged
    # per-indicator rows never carry a probability
    db = client.app.state.db
    assert db.one("SELECT COUNT(*) n FROM session_participant_summary WHERE indicator<>'*' AND calibrated_probability IS NOT NULL")["n"] == 0


def test_final_snapshot_stays_frozen_when_the_calibrator_changes(client, tmp_path):
    hp, sid = full_session(client)
    p = install(client, tmp_path, calibrator_doc(client))
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    snap = client.get("/api/sessions/1/session-summary", headers=hp).json()
    install(client, tmp_path, calibrator_doc(client, a=9.0, version="uji-2"))             # replaced and re-approved
    assert client.get("/api/sessions/1/session-summary", headers=hp).json() == snap
    p.unlink()                                                                            # removed
    assert client.get("/api/sessions/1/session-summary", headers=hp).json() == snap
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 409


# ---------------------------------------------------------------- C6: approval by SHA-256
def test_c6_empty_or_wrong_approval_or_edited_file_is_refused(client, tmp_path):
    hp, sid = full_session(client)
    doc = calibrator_doc(client)
    install(client, tmp_path, doc, approve="")                                            # setting empty
    cal = live(client, hp, sid)["total"]["calibration"]
    assert cal["reasons"] == ["invalid_calibrator"] and "belum ada sidik persetujuan" in cal["details"]["invalid_calibrator"][0]
    install(client, tmp_path, doc, approve="0" * 64)                                     # wrong SHA-256
    assert "tidak cocok" in live(client, hp, sid)["total"]["calibration"]["details"]["invalid_calibrator"][0]
    p = install(client, tmp_path, doc)                                                    # approved ...
    edited = json.dumps({**doc, "metrics_test": GOOD_METRICS, "a": 4.000001})            # ... then one value edited
    p.write_text(edited, encoding="utf-8")
    cal = live(client, hp, sid)["total"]["calibration"]
    assert cal["reasons"] == ["invalid_calibrator"] and "tidak cocok" in cal["details"]["invalid_calibrator"][0]
    # the approved SHA-256 is recorded in the snapshot even when the result is not calibrated
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    f = live(client, hp, sid)
    assert f["total"]["calibration"]["status"] == "not_calibrated"
    assert f["calibration_approved_sha256"] == client.app.state.settings.session_calibrator_sha256
    assert f["calibration_reasons"] == ["invalid_calibrator"]


def test_invalid_content_is_refused_and_finalisation_still_runs(client, tmp_path):
    hp, sid = full_session(client)
    bad_metrics = {**GOOD_METRICS, "calibration_slope": {"value": 2.0, "ci95": [1.5, 2.5], "undefined_fraction": 0.0}}
    cases = {
        "JSON tidak valid": None,
        "a harus": calibrator_doc(client, a=-1.0),
        "a harus angka": calibrator_doc(client, a=float("nan")),
        "metode tidak dikenal": calibrator_doc(client, method="isotonic"),
        "version harus": calibrator_doc(client, version=""),
        "putusan dihitung ulang": calibrator_doc(client, metrics_test=bad_metrics),       # verdict says memadai, metrics not
        "evaluation_verdict bukan": calibrator_doc(client, evaluation_verdict="belum_memadai"),
        "versi kriteria": calibrator_doc(client, lineage={"criteria_version": "lama"}),
        "models_fingerprint kosong": calibrator_doc(client, lineage={"models_fingerprint": ""}),
        "indicator_set harus": calibrator_doc(client, indicator_set=["FACE_ABSENT", "FACE_ABSENT"]),
    }
    for expected, doc in cases.items():
        install(client, tmp_path, doc, text="{bukan json" if doc is None else None)
        cal = live(client, hp, sid)["total"]["calibration"]
        assert cal["status"] == "not_calibrated" and cal["probability"] is None
        assert cal["reasons"][0] == "invalid_calibrator", expected
        assert any(expected in e for e in cal["details"]["invalid_calibrator"]), (expected, cal["details"])
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200                  # K6


# ---------------------------------------------------------------- C7: model fingerprint
def test_c7_models_mismatch_distinguishes_unavailable_from_different(client, tmp_path, monkeypatch):
    hp, sid = full_session(client)
    install(client, tmp_path, calibrator_doc(client))
    ai = client.app.state.ai
    monkeypatch.setattr(ai, "models_fingerprint", lambda: "")                             # AI not READY / unreadable
    cal = live(client, hp, sid)["total"]["calibration"]
    assert cal["reasons"] == ["models_mismatch"] and cal["details"]["models_mismatch"].startswith("tidak_tersedia")
    monkeypatch.setattr(ai, "models_fingerprint", lambda: "e" * 64)                       # other model files
    cal = live(client, hp, sid)["total"]["calibration"]
    assert cal["reasons"] == ["models_mismatch"] and cal["details"]["models_mismatch"].startswith("berbeda")
    calls = []
    monkeypatch.setattr(calibration, "probability", lambda *a: calls.append(a) or 0.5)
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    f = live(client, hp, sid)
    assert f["total"]["calibration"]["status"] == "not_calibrated" and calls == []          # never computed
    assert f["calibration_reasons"] == ["models_mismatch"]


def test_models_fingerprint_is_unavailable_unless_ready(client):
    ai = client.app.state.ai
    fp = ai.models_fingerprint()
    assert len(fp) == 64 and fp == ai.models_fingerprint()
    ai.state = "FAILED"
    assert ai.models_fingerprint() == ""
    ai.state = "READY"


# ---------------------------------------------------------------- the other reasons, all collected
def test_compatibility_reasons_are_all_collected(client, tmp_path):
    hp, sid = full_session(client)
    install(client, tmp_path, calibrator_doc(client, algo_version="session-summary-0", weights_fingerprint="w=00000000",
                                             indicator_set=VIDEO[:4]))
    cal = live(client, hp, sid)["total"]["calibration"]
    assert cal["reasons"] == ["algo_version_mismatch", "weights_mismatch", "indicator_set_mismatch"]
    assert set(cal["reasons"]) <= set(calibration.REASONS)


def test_coverage_and_d4_reasons(client, tmp_path):
    hp, sid = prepare(client)                                                             # coverage 0.2
    install(client, tmp_path, calibrator_doc(client))
    cal = live(client, hp, sid)["total"]["calibration"]
    assert cal["reasons"] == ["coverage_below_threshold"] and "cakupan video" in cal["details"]["coverage_below_threshold"][0]
    db = client.app.state.db
    client.app.state.ai.availability.record_load(1, sid, "browser", {"object_detector": {"loaded": False, "reason": "x"}})
    assert "model_unavailable" in live(client, hp, sid)["total"]["calibration"]["reasons"]
    db.run("DELETE FROM model_availability")
    assert "model_availability_not_recorded" in live(client, hp, sid)["total"]["calibration"]["reasons"]


def test_no_probability_is_computed_for_any_failure(client, tmp_path, monkeypatch):
    hp, sid = prepare(client)                                                             # coverage below threshold
    install(client, tmp_path, calibrator_doc(client))
    calls = []
    monkeypatch.setattr(calibration, "probability", lambda *a: calls.append(a) or 0.5)
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    assert calls == [] and live(client, hp, sid)["total"]["calibration"]["probability"] is None
    db = client.app.state.db
    assert db.one("SELECT COUNT(*) n FROM session_participant_summary WHERE calibrated_probability IS NOT NULL")["n"] == 0


# ---------------------------------------------------------------- scores and ALERT data never change
def test_scores_coverage_intervals_and_alert_data_are_identical(client, tmp_path):
    hp, sid = full_session(client)
    s = client.app.state.settings
    report_before = report_without_signed_links(client, hp)
    base = numbers(live(client, hp, sid))
    install(client, tmp_path, calibrator_doc(client))                                    # valid
    assert numbers(live(client, hp, sid)) == base
    install(client, tmp_path, None, text="{rusak")                                       # invalid
    assert numbers(live(client, hp, sid)) == base
    s.session_calibrator = s.session_calibrator_sha256 = ""
    assert report_without_signed_links(client, hp) == report_before                  # cases / ALERT rules untouched
    install(client, tmp_path, calibrator_doc(client))
    assert report_without_signed_links(client, hp) == report_before


# ---------------------------------------------------------------- script artefact accepted by the backend
def test_a_script_made_artefact_is_accepted_only_with_its_approval(client, tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2] / "ai" / "eduai-ai"
    spec = importlib.util.spec_from_file_location("calibrate_session", root / "scripts" / "calibrate_session.py")
    cs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cs)
    spec_t = importlib.util.spec_from_file_location("t_cal", root / "tests" / "test_calibrate_session.py")
    t = importlib.util.module_from_spec(spec_t)
    spec_t.loader.exec_module(t)
    monkeypatch.setitem(sc.CRITERIA, "bootstrap_b", 300)                                  # speed; same code path
    data = t.write_csv(tmp_path / "d.csv", t.synth(2, 1500, 600))
    code, rep = cs.run(cs.parse_args(t.argv(tmp_path, data)))
    assert code == cs.EXIT_OK, rep["evaluation"].get("failed_conditions")
    path = tmp_path / "cal.json"
    assert calibration.load(str(path), "")["state"] == "invalid"                          # not approved yet
    ok = calibration.load(str(path), rep["calibrator_sha256"])
    assert ok["state"] == "ok" and ok["calibrator"]["lineage"]["models_fingerprint"] == t.MF
    monkeypatch.undo()                                                                    # criteria back to the approved ones
    again = calibration.load(str(path), rep["calibrator_sha256"])
    assert again["state"] == "invalid" and any("versi kriteria" in e for e in again["errors"])
