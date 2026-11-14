"""Manajemen User: the admin edits accounts (PATCH /api/users/{id})."""
from tests.test_api import login, uid  # noqa: F401
from tests.test_api import client  # noqa: F401  pytest fixture


def edit(client, h, email, body):
    return client.patch(f"/api/users/{uid(client, email)}", headers=h, json=body)


def test_admin_edits_name_email_role_status_and_it_is_audited(client):
    ha = login(client, "admin1@gmail.com")
    r = edit(client, ha, "sekolah1@gmail.com", {"name": "  Maya  Sari Baru ", "email": " Maya.Baru@Sekolah.id "})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Maya Sari Baru" and r.json()["email"] == "maya.baru@sekolah.id"
    assert client.post("/api/auth/login", json={"email": "maya.baru@sekolah.id", "password": "123456", "role": "sekolah"}).status_code == 200   # new login email
    r = edit(client, ha, "penyelenggara1@gmail.com", {"role": "sekolah"})
    assert r.status_code == 200 and r.json()["role"] == "sekolah" and r.json()["role_label"] == "Pihak Sekolah"
    hs = login(client, "siswa3@gmail.com")
    r = edit(client, ha, "siswa3@gmail.com", {"active": False})
    assert r.status_code == 200 and r.json()["active"] is False
    assert client.get("/api/auth/me", headers=hs).status_code == 401                      # deactivated: session ends
    assert edit(client, ha, "siswa3@gmail.com", {"active": True, "nis": " 12345 ", "class_name": "XI IPA 9"}).json()["nis"] == "12345"
    actions = [a["action"] for a in client.app.state.db.all("SELECT action FROM audit WHERE action LIKE 'Mengubah data pengguna%' ORDER BY id")]
    assert actions == ["Mengubah data pengguna (nama, email)", "Mengubah data pengguna (peran)", "Mengubah data pengguna (status)",
                       "Mengubah data pengguna (status, NIS, kelas)"]
    before = len(actions)
    assert edit(client, ha, "siswa3@gmail.com", {"class_name": "XI IPA 9"}).status_code == 200      # no change: not audited
    assert client.app.state.db.one("SELECT COUNT(*) n FROM audit WHERE action LIKE 'Mengubah data pengguna%'")["n"] == before


def test_guards(client):
    ha = login(client, "admin1@gmail.com")
    me = uid(client, "admin1@gmail.com")
    assert client.patch(f"/api/users/{me}", headers=ha, json={"role": "pengawas"}).status_code == 409
    assert client.patch(f"/api/users/{me}", headers=ha, json={"active": False}).status_code == 409
    assert client.patch(f"/api/users/{me}", headers=ha, json={"name": "Admin Utama"}).status_code == 200   # own name is fine
    assert edit(client, ha, "siswa2@gmail.com", {"email": "pengawas1@gmail.com"}).status_code == 409      # email taken
    assert edit(client, ha, "siswa2@gmail.com", {"email": "bukan-email"}).status_code == 422
    assert edit(client, ha, "siswa2@gmail.com", {"role": "superadmin"}).status_code == 422
    assert edit(client, ha, "siswa2@gmail.com", {"password_hash": "x"}).status_code == 422
    r = edit(client, ha, "pengawas1@gmail.com", {"role": "siswa"})                                         # supervises exam 1
    assert r.status_code == 409 and "pengawas" in r.json()["detail"]
    r = edit(client, ha, "siswa1@gmail.com", {"role": "pengawas"})                                         # enrolled in exam 1
    assert r.status_code == 409 and "peserta" in r.json()["detail"]
    assert client.patch("/api/users/99999", headers=ha, json={"name": "X Y"}).status_code == 404


def test_last_active_admin_stays(client):
    ha = login(client, "admin1@gmail.com")
    db = client.app.state.db
    db.run("INSERT INTO users (email,name,role,password_hash,created_at) SELECT 'admin2@x.id','Admin Dua','admin',password_hash,created_at FROM users WHERE email='admin1@gmail.com'")
    assert edit(client, ha, "admin2@x.id", {"role": "pengawas"}).status_code == 200                      # another admin remains
    db.run("UPDATE users SET role='admin' WHERE email='admin2@x.id'")
    h2 = login(client, "admin2@x.id")
    db.run("UPDATE users SET active=0 WHERE email='admin1@gmail.com'")                                    # only admin2 is left
    r = client.patch(f"/api/users/{uid(client, 'admin2@x.id')}", headers=h2, json={"active": False})
    assert r.status_code == 409


def test_only_admin_and_school_may_edit_users(client):
    for email in ("penyelenggara1@gmail.com", "pengawas1@gmail.com", "siswa1@gmail.com"):
        assert edit(client, login(client, email), "siswa2@gmail.com", {"name": "Tidak Boleh"}).status_code == 403, email
    assert client.patch(f"/api/users/{uid(client, 'siswa2@gmail.com')}", json={"name": "X Y"}).status_code == 401


def test_school_manages_student_accounts_only(client):
    hk = login(client, "sekolah1@gmail.com")
    listed = client.get("/api/users", headers=hk).json()
    assert listed and {u["role"] for u in listed} == {"siswa"}                              # "Akun Siswa": students only
    assert {u["role"] for u in client.get("/api/users?role=admin", headers=hk).json()} == {"siswa"}
    r = edit(client, hk, "siswa2@gmail.com", {"name": "Bima P", "email": "bima.p@sekolah.id", "nis": "999", "class_name": "XII", "active": False})
    assert r.status_code == 200 and r.json()["email"] == "bima.p@sekolah.id" and r.json()["active"] is False
    assert edit(client, hk, "bima.p@sekolah.id", {"role": "pengawas"}).status_code == 403           # no role change
    assert edit(client, hk, "bima.p@sekolah.id", {"role": "siswa", "active": True}).status_code == 200
    for staff in ("pengawas1@gmail.com", "admin1@gmail.com", "penyelenggara1@gmail.com", "sekolah1@gmail.com"):
        assert edit(client, hk, staff, {"name": "Tidak Boleh"}).status_code == 403, staff          # staff accounts: no
    a = client.app.state.db.one("SELECT * FROM audit WHERE action LIKE 'Mengubah data pengguna%' ORDER BY id LIMIT 1")
    assert a["user_id"] == uid(client, "sekolah1@gmail.com") and a["role"] == "sekolah"


# ------------------------------------------------------------------ Tambah User (POST /api/users)
def new(client, h, **body):
    base = {"name": "Pengguna Baru", "email": "baru@sekolah.id", "role": "pengawas", "password": "rahasia-123"}
    return client.post("/api/users", headers=h, json={**base, **body})


def test_admin_adds_each_role_and_the_account_can_log_in(client):
    ha = login(client, "admin1@gmail.com")
    cases = [("siswa", {"nis": "2301099", "class_name": "XI IPA 3"}), ("pengawas", {}), ("penyelenggara", {}), ("admin", {}), ("sekolah", {})]
    for role, extra in cases:
        email = f"{role}.baru@sekolah.id"
        r = new(client, ha, name=f"  Akun  {role} ", email=email.upper(), role=role, **extra)
        assert r.status_code == 201, (role, r.text)
        u = r.json()
        assert u["email"] == email and u["role"] == role and u["active"] is True and u["name"] == f"Akun {role}"
        assert (u["nis"], u["class_name"]) == ((extra.get("nis"), extra.get("class_name")) if role == "siswa" else (None, None))
        r = client.post("/api/auth/login", json={"email": email, "password": "rahasia-123", "role": role})
        assert r.status_code == 200 and r.json()["user"]["role"] == role                     # can log in with the initial password
    actions = [a["action"] for a in client.app.state.db.all("SELECT action FROM audit WHERE action LIKE 'Menambah pengguna%' ORDER BY id")]
    assert actions == ["Menambah pengguna (Siswa)", "Menambah pengguna (Pengawas)", "Menambah pengguna (Penyelenggara Ujian)",
                       "Menambah pengguna (Admin)", "Menambah pengguna (Pihak Sekolah)"]
    assert "rahasia" not in str(client.app.state.db.all("SELECT * FROM audit"))                  # the password is never logged


def test_add_user_rules(client):
    ha = login(client, "admin1@gmail.com")
    assert new(client, ha, role="siswa").status_code == 422                                       # student without NIS/class
    assert new(client, ha, role="siswa", nis="1").status_code == 422
    assert new(client, ha, role="pengawas", nis="1", class_name="X").status_code == 422           # staff with NIS/class
    assert new(client, ha, email="pengawas1@gmail.com").status_code == 409                        # email taken
    assert new(client, ha, email="bukan-email").status_code == 422
    assert new(client, ha, password="1234567").status_code == 422                                 # min 8 characters
    assert new(client, ha, role="superadmin").status_code == 422
    assert new(client, ha, active=False).status_code == 422                                       # unknown field
    for email in ("sekolah1@gmail.com", "penyelenggara1@gmail.com", "pengawas1@gmail.com", "siswa1@gmail.com"):
        assert new(client, login(client, email), email="x@y.id").status_code == 403, email
    assert client.post("/api/users", json={"name": "X Y", "email": "x@y.id", "role": "pengawas", "password": "rahasia-123"}).status_code == 401
