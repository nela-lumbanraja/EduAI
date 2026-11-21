"""Consent page support (20 Nov 2026): the stored notice version records the periods shown to the student, and the
public health endpoint gives the page the retention values in force."""
from tests.test_api import client, login, uid  # noqa: F401


def test_notice_version_with_periods_is_stored_as_sent(client):
    hs = login(client, "siswa1@gmail.com")
    version = "2026-11-v3;r876000;h36500;f876000"                 # the longest form the page sends (33 chars)
    r = client.post("/api/exams/1/consent", headers=hs, json={"accepted": True, "notice_version": version})
    assert r.status_code == 200
    row = client.app.state.db.one("SELECT notice_version FROM consents WHERE exam_id=1 AND student_id=?",
                                  (uid(client, "siswa1@gmail.com"),))
    assert row["notice_version"] == version


def test_public_health_gives_the_consent_page_its_periods(client):
    h = client.get("/api/ai/health").json()                        # no login: the student page reads it before joining
    assert (h["evidence_retention_hours"], h["evidence_hold_days"], h["report_frame_retention_hours"]) == (24.0, 7.0, 24.0)
