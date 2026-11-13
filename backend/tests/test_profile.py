"""Pengaturan > Profil: a user changes their own full name (PATCH /api/auth/me)."""
from tests.test_api import login, uid  # noqa: F401
from tests.test_api import client  # noqa: F401  pytest fixture


def test_every_role_can_change_their_own_name_and_it_is_audited(client):
    for email in ("siswa2@gmail.com", "pengawas1@gmail.com", "admin1@gmail.com", "sekolah1@gmail.com", "penyelenggara1@gmail.com"):
        h = login(client, email)
        r = client.patch("/api/auth/me", headers=h, json={"name": "  Nama   Baru  Uji "})
        assert r.status_code == 200, (email, r.text)
        assert r.json()["name"] == "Nama Baru Uji" and r.json()["email"] == email
        assert client.get("/api/auth/me", headers=h).json()["name"] == "Nama Baru Uji"
        a = client.app.state.db.one("SELECT * FROM audit WHERE action='Mengubah nama profil' ORDER BY id DESC LIMIT 1")
        assert a["user_id"] == uid(client, email) and a["target"] == f"user:{uid(client, email)}"


def test_only_the_name_can_change_and_bad_names_are_refused(client):
    h = login(client, "siswa2@gmail.com")
    before = client.get("/api/auth/me", headers=h).json()
    for body in ({"name": "Bima", "email": "lain@x.id"}, {"name": "Bima", "role": "admin"}, {"name": ""}, {"name": " a "}, {"name": "x" * 121}, {}):
        assert client.patch("/api/auth/me", headers=h, json=body).status_code == 422, body
    after = client.get("/api/auth/me", headers=h).json()
    assert after == before                                                    # email, role unchanged
    assert client.patch("/api/auth/me", json={"name": "Tanpa Login"}).status_code == 401


def test_same_name_is_not_audited(client):
    h = login(client, "siswa2@gmail.com")
    name = client.get("/api/auth/me", headers=h).json()["name"]
    n = client.app.state.db.one("SELECT COUNT(*) n FROM audit WHERE action='Mengubah nama profil'")["n"]
    assert client.patch("/api/auth/me", headers=h, json={"name": name}).status_code == 200
    assert client.app.state.db.one("SELECT COUNT(*) n FROM audit WHERE action='Mengubah nama profil'")["n"] == n
