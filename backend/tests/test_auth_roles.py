"""Login per portal role, server-side logout (jti + revoked_tokens), and tokens issued before jti existed."""
from datetime import datetime, timedelta, timezone

import jwt

from tests.test_api import client, login  # noqa: F401  (client = pytest fixture)

ROLES = {"admin1@gmail.com": "admin", "pengawas1@gmail.com": "pengawas", "penyelenggara1@gmail.com": "penyelenggara",
         "sekolah1@gmail.com": "sekolah", "siswa1@gmail.com": "siswa"}
MISMATCH = "Role akun tidak sesuai dengan pilihan login. Silakan pilih role yang benar."


def post_login(c, email, role, password="123456"):
    return c.post("/api/auth/login", json={"email": email, "password": password, "role": role})


def test_each_role_logs_in_only_with_its_own_role(client):
    for email, role in ROLES.items():
        r = post_login(client, email, role)
        assert r.status_code == 200 and r.json()["user"]["role"] == role, (email, r.text)
        for other in set(ROLES.values()) - {role}:
            r = post_login(client, email, other)
            assert r.status_code == 403 and r.json()["detail"] == MISMATCH and "token" not in r.json(), (email, other)


def test_portal_cases_from_the_audit(client):
    assert post_login(client, "admin1@gmail.com", "pengawas").status_code == 403      # tab Pengawas, Admin account
    assert post_login(client, "admin1@gmail.com", "siswa").status_code == 403         # Siswa portal, Admin account
    assert post_login(client, "siswa1@gmail.com", "pengawas").status_code == 403      # staff portal, Siswa account
    rows = client.app.state.db.all("SELECT action, status FROM audit WHERE action LIKE 'Login ditolak%'")
    assert len(rows) == 3 and all(r["status"] == "Ditolak" for r in rows)


def test_role_is_required_and_cannot_be_skipped(client):
    assert client.post("/api/auth/login", json={"email": "admin1@gmail.com", "password": "123456"}).status_code == 422
    assert post_login(client, "admin1@gmail.com", "superadmin").status_code == 422
    assert post_login(client, "admin1@gmail.com", "").status_code == 422


def test_wrong_password_never_reveals_the_role(client):
    r = post_login(client, "admin1@gmail.com", "pengawas", password="salah")
    assert r.status_code == 401 and r.json()["detail"] == "Email atau kata sandi salah."


def test_logout_revokes_the_token_everywhere(client):
    h = login(client, "admin1@gmail.com")
    assert client.get("/api/users", headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    for method, path in [("get", "/api/auth/me"), ("get", "/api/users"), ("get", "/api/exams"), ("get", "/api/dashboard"),
                         ("post", "/api/auth/logout")]:
        assert getattr(client, method)(path, headers=h).status_code == 401, path
    h2 = login(client, "admin1@gmail.com")                    # logging in again gives a new, working session
    assert h2 != h and client.get("/api/auth/me", headers=h2).status_code == 200


def test_logout_only_ends_that_session(client):
    a, b = login(client, "pengawas1@gmail.com"), login(client, "pengawas1@gmail.com")
    assert client.post("/api/auth/logout", headers=a).status_code == 200
    assert client.get("/api/auth/me", headers=a).status_code == 401
    assert client.get("/api/auth/me", headers=b).status_code == 200


def test_tokens_have_unique_jti(client):
    secret = client.app.state.settings.jwt_secret
    ids = {jwt.decode(login(client, "siswa1@gmail.com")["Authorization"][7:], secret, algorithms=["HS256"])["jti"] for _ in range(5)}
    assert len(ids) == 5


def test_token_issued_before_jti_still_works_and_can_be_revoked(client):
    """Sessions already open when this change ships (e.g. students in a running exam) are not cut off."""
    st = client.app.state
    uid = st.db.one("SELECT id FROM users WHERE email='siswa1@gmail.com'")["id"]
    now = datetime.now(timezone.utc)
    old = jwt.encode({"sub": str(uid), "role": "siswa", "iat": now, "exp": now + timedelta(hours=1)}, st.settings.jwt_secret, algorithm="HS256")
    h = {"Authorization": f"Bearer {old}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_revoked_rows_are_pruned_after_expiry(client):
    db = client.app.state.db
    db.run("INSERT INTO revoked_tokens (jti,user_id,revoked_at,expires_at) VALUES ('lama',1,'2000-01-01T00:00:00.000+00:00','2000-01-01T00:00:00.000+00:00')")
    assert client.post("/api/auth/logout", headers=login(client, "admin1@gmail.com")).status_code == 200
    assert not db.one("SELECT 1 FROM revoked_tokens WHERE jti='lama'")
