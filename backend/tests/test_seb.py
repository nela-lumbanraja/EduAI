"""Safe Exam Browser check: keys stay on the server, hashes follow the SEB spec, join is gated."""
import hashlib

import pytest
from fastapi.testclient import TestClient

from app import seb
from app.main import create_app
from tests.test_api import FakePerception, login, make_settings, uid

PAGE = "http://localhost:5173/"
CK = "a" * 64                         # Config Key as the SEB Config Tool would show it
BEK = "b" * 64                        # Browser Exam Key of one SEB build
OTHER = "c" * 64


def sha(url, key):
    return hashlib.sha256((url + key).encode()).hexdigest()


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)
    with TestClient(app) as c:
        yield c


def configure(c, required=True, ck=(CK,), bek=(), url="", who="admin1@gmail.com"):
    return c.put("/api/exams/1/seb", headers=login(c, who),
                 json={"required": required, "config_keys": list(ck), "browser_exam_keys": list(bek), "config_url": url})


def verify(c, h, *, page=PAGE, ck=None, bek=None, headers=None, request_url=None, nonce=None, version="SEB_Windows_3.8.0"):
    n = nonce or c.post("/api/exams/1/seb/challenge", headers=h).json()["nonce"]
    path = f"/api/exams/1/seb/verify?n={n}"
    body = {"nonce": n, "page_url": page, "request_url": request_url or f"http://localhost:5173{path}",
            "config_key": ck, "browser_exam_key": bek, "version": version}
    return c.post(path, headers={**h, **(headers or {})}, json=body)


def consent(c, h):
    assert c.post("/api/exams/1/consent", headers=h, json={"accepted": True}).status_code == 200


# ------------------------------------------------------------------ hash (SEB spec)
def test_hash_is_sha256_of_url_without_fragment_then_key():
    assert seb.url_hash("https://x.test/a?b=1#frag", CK) == sha("https://x.test/a?b=1", CK)
    assert seb.matches(PAGE, sha(PAGE, CK).upper(), [CK])          # hex case does not matter
    assert not seb.matches(PAGE, sha(PAGE, CK), [OTHER])
    assert not seb.matches("http://localhost:5173/other", sha(PAGE, CK), [CK])   # bound to the URL
    assert not seb.matches(PAGE, None, [CK]) and not seb.matches(PAGE, sha(PAGE, CK), [])


def test_key_validation():
    assert seb.normalize_keys(f"{CK.upper()}\n{CK}, {BEK}") == [CK, BEK]
    with pytest.raises(ValueError):
        seb.normalize_keys(["xyz"])


# ------------------------------------------------------------------ settings: who, and no leak of keys
def test_only_admin_and_organiser_change_settings(client):
    assert configure(client).status_code == 200
    assert configure(client, who="penyelenggara1@gmail.com").status_code == 200
    for who in ("pengawas1@gmail.com", "siswa1@gmail.com", "sekolah1@gmail.com"):
        assert configure(client, who=who).status_code == 403, who
        assert client.get("/api/exams/1/seb", headers=login(client, who)).status_code == 403, who


def test_required_without_key_or_bad_key_is_refused(client):
    assert configure(client, ck=()).status_code == 422
    assert configure(client, ck=("1234",)).status_code == 422
    assert configure(client, required=False, ck=()).status_code == 200


def test_keys_never_reach_students_or_supervisors(client):
    configure(client, bek=(BEK,), url="https://sekolah.test/ujian.seb")
    for who in ("siswa1@gmail.com", "pengawas1@gmail.com", "sekolah1@gmail.com"):
        h = login(client, who)
        texts = [client.get("/api/exams/1", headers=h).text, client.get("/api/exams", headers=h).text]
        if who != "siswa1@gmail.com":
            texts.append(client.get("/api/exams/1/students", headers=h).text)
        for t in texts:
            assert CK not in t and BEK not in t, who
    e = client.get("/api/exams/1", headers=login(client, "siswa1@gmail.com")).json()
    assert e["seb"] == {"required": True, "ready": True, "config_url": "https://sekolah.test/ujian.seb"}


# ------------------------------------------------------------------ verification
def test_not_required_keeps_old_flow(client):
    h = login(client, "siswa1@gmail.com")
    consent(client, h)
    assert client.post("/api/exams/1/join", headers=h).status_code == 200
    r = verify(client, h)
    assert r.status_code == 200 and r.json()["verified"] is True and r.json()["required"] is False


def test_normal_browser_cannot_join(client):
    configure(client)
    h = login(client, "siswa1@gmail.com")
    consent(client, h)
    r = verify(client, h)
    assert r.json()["state"] == "not_seb" and r.json()["verified"] is False
    r = client.post("/api/exams/1/join", headers=h)
    assert r.status_code == 403 and "Safe Exam Browser" in r.json()["detail"]
    acts = [a["action"] for a in client.app.state.db.all("SELECT action FROM audit WHERE status='Ditolak'")]
    assert any("Masuk ruang ujian ditolak" in a for a in acts) and any("not_seb" in a for a in acts)


def test_js_api_with_right_config_key_lets_student_join(client):
    configure(client)
    h = login(client, "siswa1@gmail.com")
    consent(client, h)
    r = verify(client, h, ck=sha(PAGE, CK))
    assert r.json() == {"required": True, "state": "verified", "method": "js", "verified": True,
                        "message": "Safe Exam Browser terverifikasi."}
    assert client.post("/api/exams/1/join", headers=h).status_code == 200


def test_wrong_configuration_is_rejected(client):
    configure(client)
    h = login(client, "siswa1@gmail.com")
    consent(client, h)
    assert verify(client, h, ck=sha(PAGE, OTHER)).json()["state"] == "key_mismatch"
    # a hash made for another page is not accepted for this one
    assert verify(client, h, ck=sha("http://localhost:5173/x", CK)).json()["state"] == "key_mismatch"
    assert client.post("/api/exams/1/join", headers=h).status_code == 403


def test_page_from_unlisted_origin_is_rejected(client):
    configure(client)
    h = login(client, "siswa1@gmail.com")
    evil = "http://evil.test/"
    assert verify(client, h, page=evil, ck=sha(evil, CK)).json()["state"] == "url_mismatch"


def test_both_key_kinds_must_match_when_both_are_set(client):
    configure(client, bek=(BEK,))
    h = login(client, "siswa1@gmail.com")
    assert verify(client, h, ck=sha(PAGE, CK)).json()["state"] == "key_mismatch"
    assert verify(client, h, ck=sha(PAGE, CK), bek=sha(PAGE, BEK)).json()["state"] == "verified"


def test_any_listed_browser_exam_key_is_accepted(client):
    configure(client, ck=(), bek=(OTHER, BEK))          # two SEB builds (e.g. Windows and macOS)
    h = login(client, "siswa1@gmail.com")
    assert verify(client, h, bek=sha(PAGE, BEK)).json()["state"] == "verified"


def test_header_hashes_bound_to_the_one_time_url(client):
    configure(client, bek=(BEK,))
    h = login(client, "siswa1@gmail.com")
    n = client.post("/api/exams/1/seb/challenge", headers=h).json()["nonce"]
    url = f"http://localhost:5173/api/exams/1/seb/verify?n={n}"
    hdr = {"X-SafeExamBrowser-ConfigKeyHash": sha(url, CK), "X-SafeExamBrowser-RequestHash": sha(url, BEK)}
    r = verify(client, h, nonce=n, headers=hdr)
    assert r.json()["state"] == "verified" and r.json()["method"] == "header"
    # replaying the same headers with a new nonce fails: the URL changed
    assert verify(client, h, headers=hdr).json()["state"] == "key_mismatch"
    # claiming the old URL for a new request does not help either
    assert verify(client, h, headers=hdr, request_url=url).json()["state"] == "url_mismatch"


def test_nonce_is_single_use_and_personal(client):
    configure(client)
    h1, h2 = login(client, "siswa1@gmail.com"), login(client, "siswa2@gmail.com")
    n = client.post("/api/exams/1/seb/challenge", headers=h1).json()["nonce"]
    assert verify(client, h1, nonce=n, ck=sha(PAGE, CK)).status_code == 200
    assert verify(client, h1, nonce=n, ck=sha(PAGE, CK)).status_code == 409          # used
    n = client.post("/api/exams/1/seb/challenge", headers=h1).json()["nonce"]
    assert verify(client, h2, nonce=n, ck=sha(PAGE, CK)).status_code == 409          # someone else's
    assert verify(client, h1, nonce="x" * 20, ck=sha(PAGE, CK)).status_code == 409   # unknown


def test_expired_check_no_longer_admits(client):
    configure(client)
    h = login(client, "siswa1@gmail.com")
    consent(client, h)
    verify(client, h, ck=sha(PAGE, CK))
    client.app.state.db.run("UPDATE seb_status SET checked_at='2020-01-01T00:00:00.000+00:00'")
    assert client.post("/api/exams/1/join", headers=h).status_code == 403


def test_supervisor_sees_state_per_student(client):
    configure(client)
    hs, hs2 = login(client, "siswa1@gmail.com"), login(client, "siswa2@gmail.com")
    verify(client, hs, ck=sha(PAGE, CK))
    verify(client, hs2)
    rows = {r["id"]: r for r in client.get("/api/exams/1/students", headers=login(client, "pengawas1@gmail.com")).json()}
    a, b = rows[uid(client, "siswa1@gmail.com")]["seb"], rows[uid(client, "siswa2@gmail.com")]["seb"]
    assert a["required"] and a["state"] == "verified" and a["fresh"] and a["method"] == "js" and a["version"]
    assert b["state"] == "not_seb" and not b["fresh"]


def test_settings_change_is_audited(client):
    configure(client, bek=(BEK,))
    a = client.app.state.db.one("SELECT * FROM audit WHERE action LIKE '%Safe Exam Browser%' ORDER BY id DESC")
    assert "wajib: ya" in a["action"] and "1 Config Key" in a["action"] and CK not in a["action"]
