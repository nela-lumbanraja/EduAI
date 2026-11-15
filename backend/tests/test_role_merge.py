"""Pihak Sekolah and Penyelenggara Ujian are one role ("penyelenggara"). Old "sekolah" accounts move over at startup."""
from app import store
from app.security import verify_password
from tests.test_api import client, login, uid  # noqa: F401  (client = pytest fixture)


def test_old_school_accounts_are_merged_once_and_keep_their_password(client):
    db = client.app.state.db
    db.run("INSERT INTO users (email,name,role,password_hash,created_at) SELECT 'lama@sekolah.id','Akun Lama','sekolah',"
           "password_hash,created_at FROM users WHERE email='sekolah1@gmail.com'")
    before = db.one("SELECT * FROM users WHERE email='lama@sekolah.id'")
    assert store.merge_school_role(db) == 1
    after = db.one("SELECT * FROM users WHERE email='lama@sekolah.id'")
    assert after["role"] == "penyelenggara"
    assert {k: after[k] for k in ("email", "password_hash", "active", "name")} == {k: before[k] for k in ("email", "password_hash", "active", "name")}
    assert verify_password("123456", after["password_hash"])
    assert db.one("SELECT 1 FROM audit WHERE action=? AND target=?", (store.MERGE_ACTION, f"user:{after['id']}"))
    assert store.merge_school_role(db) == 0                                    # a restart changes nothing
    assert not db.one("SELECT 1 FROM users WHERE role='sekolah'")


def test_school_account_logs_in_on_the_penyelenggara_tab_only(client):
    ok = client.post("/api/auth/login", json={"email": "sekolah1@gmail.com", "password": "123456", "role": "penyelenggara"})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "penyelenggara"
    assert ok.json()["user"]["role_label"] == "Penyelenggara Ujian"
    assert client.post("/api/auth/login", json={"email": "sekolah1@gmail.com", "password": "123456", "role": "sekolah"}).status_code == 422


def test_merged_role_has_both_sets_of_rights(client):
    h = login(client, "penyelenggara1@gmail.com")
    assert client.get("/api/users?role=pengawas", headers=h).status_code == 200            # menu "Pengawas"
    students = client.get("/api/users?role=siswa", headers=h).json()                       # menu "Akun Siswa"
    assert students and {u["role"] for u in students} == {"siswa"}
    r = client.patch(f"/api/users/{uid(client, 'siswa4@gmail.com')}", headers=h, json={"class_name": "XII IPA 2"})
    assert r.status_code == 200 and r.json()["class_name"] == "XII IPA 2"
    assert client.patch(f"/api/users/{uid(client, 'siswa4@gmail.com')}", headers=h, json={"role": "admin"}).status_code == 403
    assert client.post("/api/users", headers=h, json={"name": "X Y", "email": "x@y.id", "role": "siswa",
                                                      "password": "rahasia-123", "nis": "1", "class_name": "X"}).status_code == 403
