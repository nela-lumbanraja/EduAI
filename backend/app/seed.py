"""Demo accounts and exams for local development (EDUAI_SEED_DEMO=true).

The names mirror the accounts the original frontend kept in localStorage, so the
existing "Akun uji" hint on the login page still works. Only users, exams and
enrolments are seeded: no AI events, statuses or evidence are ever seeded.
Turn seeding off (EDUAI_SEED_DEMO=false) and change passwords for any real use.
"""
from datetime import datetime, timedelta

from .db import now_iso
from .security import hash_password

DEMO_PASSWORD = "123456"

USERS = [
    ("siswa1@gmail.com", "Alya Putri", "siswa", "2301034", "XI IPA 2"),
    ("siswa2@gmail.com", "Bima Pratama", "siswa", "2301035", "XI IPA 2"),
    ("siswa3@gmail.com", "Citra Lestari", "siswa", "2301036", "XI IPA 2"),
    ("siswa4@gmail.com", "Dimas Saputra", "siswa", "2301037", "XI IPA 2"),
    ("siswa5@gmail.com", "Farah Nabila", "siswa", "2301038", "XI IPA 2"),
    ("siswa6@gmail.com", "Gilang Ramadhan", "siswa", "2301039", "XI IPA 2"),
    ("pengawas1@gmail.com", "Rina Setiawati", "pengawas", None, None),
    ("pengawas2@gmail.com", "Agus Wirawan", "pengawas", None, None),
    ("penyelenggara1@gmail.com", "Dedi Kurniawan", "penyelenggara", None, None),
    ("admin1@gmail.com", "Nadia Aulia", "admin", None, None),
    ("sekolah1@gmail.com", "Maya Sari", "sekolah", None, None),
]


def seed_demo(db):
    if db.one("SELECT id FROM users LIMIT 1"):
        return False
    pw = hash_password(DEMO_PASSWORD)      # one hash reused: demo data only
    ts = now_iso()
    for email, name, role, nis, cls in USERS:
        db.run("INSERT INTO users (email,name,role,password_hash,nis,class_name,created_at) VALUES (?,?,?,?,?,?,?)",
               (email, name, role, pw, nis, cls, ts))
    uid = {r["email"]: r["id"] for r in db.all("SELECT id, email FROM users")}
    admin = uid["admin1@gmail.com"]
    today = datetime.now()
    exams = [
        ("Ujian Akhir Matematika XI", "Ujian akhir: logika, himpunan, relasi, fungsi, dan teori graf.", "Matematika",
         today.strftime("%Y-%m-%d"), (today - timedelta(minutes=10)).strftime("%H:%M"), 120, "Sedang Berlangsung",
         uid["pengawas1@gmail.com"], [f"siswa{i}@gmail.com" for i in range(1, 7)]),
        ("Evaluasi Bahasa Indonesia XI", "Evaluasi membaca dan menulis teks eksposisi.", "Bahasa Indonesia",
         (today + timedelta(days=2)).strftime("%Y-%m-%d"), "09:30", 90, "Terjadwal",
         uid["pengawas1@gmail.com"], [f"siswa{i}@gmail.com" for i in range(1, 5)]),
        ("Ujian Tengah Semester Fisika", "Kinematika dan dinamika.", "Fisika",
         (today - timedelta(days=3)).strftime("%Y-%m-%d"), "10:00", 100, "Selesai",
         uid["pengawas2@gmail.com"], [f"siswa{i}@gmail.com" for i in range(1, 7)]),
    ]
    for name, desc, subject, date, start, dur, status, sup, studs in exams:
        eid = db.run("INSERT INTO exams (name,description,subject,class_name,date,start_time,duration_min,status,"
                     "supervisor_id,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (name, desc, subject, "XI IPA 2", date, start, dur, status, sup, admin, ts))
        db.many("INSERT INTO exam_students (exam_id, student_id) VALUES (?,?)", [(eid, uid[s]) for s in studs])
    return True
