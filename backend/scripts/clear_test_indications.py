"""Permanently remove AI indication test data (events, their reviews, evidence images and exam summaries).

Accounts, exams, participants, consents, presence, audit log and settings are NOT touched.

Safety:
  * Default is a DRY RUN: it only prints what would be deleted.
  * --apply first makes a backup (database copy via SQLite's backup API + a copy of the evidence
    folder) in backend/data/backups/<timestamp>/, then deletes in one transaction.
  * Refuses to run while the backend answers on 127.0.0.1:<port> (stop it with Ctrl+C first).

Run from the backend folder:
  python scripts/clear_test_indications.py                 # preview, all exams
  python scripts/clear_test_indications.py --exam 1        # preview, one exam
  python scripts/clear_test_indications.py --exam 1 --apply
"""
import argparse
import shutil
import socket
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.settings import load_settings  # noqa: E402


def backend_running(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def counts(con, exam_ids):
    out = []
    for eid in exam_ids:
        name = (con.execute("SELECT name FROM exams WHERE id=?", (eid,)).fetchone() or ["(ujian tidak ada)"])[0]
        ind, ca = con.execute("SELECT SUM(category='indication'), SUM(category='cannot_analyze') FROM events WHERE exam_id=?",
                              (eid,)).fetchone()
        unrev = con.execute("SELECT COUNT(*) FROM events WHERE exam_id=? AND category='indication' AND review_status IS NULL",
                            (eid,)).fetchone()[0]
        rev = con.execute("SELECT COUNT(*) FROM reviews WHERE event_id IN (SELECT event_id FROM events WHERE exam_id=?)",
                          (eid,)).fetchone()[0]
        evid = con.execute("SELECT COUNT(*) FROM evidence WHERE exam_id=?", (eid,)).fetchone()[0]
        summ = con.execute("SELECT COUNT(*) FROM exam_summaries WHERE exam_id=?", (eid,)).fetchone()[0] if has_table(con, "exam_summaries") else 0
        out.append((eid, name, ind or 0, unrev, ca or 0, rev, evid, summ))
    return out


def has_table(con, name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exam", type=int, action="append", help="exam id (repeatable); default: every exam with events")
    ap.add_argument("--apply", action="store_true", help="really delete (after an automatic backup)")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()

    s = load_settings()
    db_path, ev_dir = Path(s.db_path), Path(s.evidence_dir)
    print(f"Database : {db_path}")
    print(f"Evidence : {ev_dir}")
    if not db_path.is_file():
        sys.exit("Database tidak ditemukan. Tidak ada yang dilakukan.")
    if backend_running(a.port):
        sys.exit(f"Backend masih berjalan di port {a.port}. Hentikan dulu (Ctrl+C di terminal backend), lalu ulangi.")

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    exam_ids = a.exam or [r[0] for r in con.execute("SELECT DISTINCT exam_id FROM events ORDER BY exam_id")]
    if not exam_ids:
        print("Tidak ada data indikasi. Tidak ada yang dihapus.")
        return
    rows = counts(con, exam_ids)
    print("\nAkan dihapus:" if a.apply else "\nPRATINJAU (belum ada yang dihapus):")
    print(f"{'ujian':>5}  {'indikasi':>8}  {'belum ditinjau':>14}  {'tdk dpt dianalisis':>18}  {'validasi':>8}  {'evidence':>8}  {'ringkasan':>9}  nama")
    for eid, name, ind, unrev, ca, rev, evid, summ in rows:
        print(f"{eid:>5}  {ind:>8}  {unrev:>14}  {ca:>18}  {rev:>8}  {evid:>8}  {summ:>9}  {name}")
    if not a.apply:
        print("\nTidak ada yang dihapus. Untuk menghapus, jalankan lagi dengan --apply (backup dibuat otomatis).")
        return

    # 1) backup: consistent DB copy (includes WAL content) + evidence folder
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = db_path.parent / "backups" / stamp
    bdir.mkdir(parents=True)
    dst = sqlite3.connect(str(bdir / db_path.name))
    con.backup(dst)
    dst.close()
    if ev_dir.is_dir():
        shutil.copytree(ev_dir, bdir / "evidence")
    print(f"\nBackup dibuat: {bdir}")

    # 2) delete in one transaction
    q = ",".join("?" * len(exam_ids))
    ev_ids = [r[0] for r in con.execute(f"SELECT evidence_id FROM evidence WHERE exam_id IN ({q})", exam_ids)]
    with con:
        con.execute(f"DELETE FROM reviews WHERE event_id IN (SELECT event_id FROM events WHERE exam_id IN ({q}))", exam_ids)
        con.execute(f"DELETE FROM evidence WHERE exam_id IN ({q})", exam_ids)
        con.execute(f"DELETE FROM events WHERE exam_id IN ({q})", exam_ids)
        if has_table(con, "exam_summaries"):
            con.execute(f"DELETE FROM exam_summaries WHERE exam_id IN ({q})", exam_ids)
        con.execute("INSERT INTO audit (ts,user_id,user_name,role,action,target,status) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().astimezone().isoformat(timespec="milliseconds"), None, "Sistem", "sistem",
                     "Menghapus data indikasi uji coba", f"exam:{','.join(map(str, exam_ids))} backup:{stamp}", "Berhasil"))
    # 3) evidence image folders (after the database commit)
    removed = 0
    for eid in ev_ids:
        d = ev_dir / eid
        if d.is_dir() and d.parent == ev_dir:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    left = counts(con, exam_ids)
    con.close()
    print(f"Selesai. Folder evidence dihapus: {removed}.")
    for eid, name, ind, unrev, ca, rev, evid, summ in left:
        print(f"  ujian {eid}: indikasi {ind}, evidence {evid}, ringkasan {summ}  ({name})")
    print(f"Untuk mengembalikan: hentikan backend, lalu salin {bdir / db_path.name} ke {db_path}"
          f" (dan folder evidence-nya).")


if __name__ == "__main__":
    main()