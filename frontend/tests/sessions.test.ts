// Run: node --experimental-strip-types tests/sessions.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { ALL_STATUSES, filterSessions, sessionDateText, sessionTone, STATUS_OPTIONS } from "../src/sessions.ts";

const rows = [
  { name: "Ujian Akhir Matematika", subject: "Matematika", class_name: "XI IPA 2", status: "Sedang Berlangsung" as const },
  { name: "Evaluasi Bahasa", subject: "Bahasa Indonesia", class_name: "XI IPA 2", status: "Terjadwal" as const },
  { name: "UTS Fisika", subject: "Fisika", class_name: "XII", status: "Selesai" as const },
  { name: "Draf Kimia", subject: "Kimia", class_name: "X", status: "Draft" as const },
];

test("status filter: every option, including 'Semua status'", () => {
  assert.deepEqual(STATUS_OPTIONS, [ALL_STATUSES, "Sedang Berlangsung", "Terjadwal", "Draft", "Selesai"]);
  assert.equal(filterSessions(rows, "", ALL_STATUSES).length, 4);
  for (const s of ["Sedang Berlangsung", "Terjadwal", "Draft", "Selesai"]) {
    const r = filterSessions(rows, "", s);
    assert.equal(r.length, 1);
    assert.equal(r[0].status, s);
  }
});

test("search and status together; search covers name, subject and class", () => {
  assert.deepEqual(filterSessions(rows, "fisika", ALL_STATUSES).map((r) => r.name), ["UTS Fisika"]);
  assert.deepEqual(filterSessions(rows, "  XI IPA ", "Terjadwal").map((r) => r.name), ["Evaluasi Bahasa"]);
  assert.deepEqual(filterSessions(rows, "fisika", "Terjadwal"), []);
});

test("running sessions get the gold badge", () => {
  assert.equal(sessionTone("Sedang Berlangsung"), "gold");
  assert.equal(sessionTone("Terjadwal"), "blue");
  assert.equal(sessionTone("Selesai"), "green");
  assert.equal(sessionTone("Draft"), "gray");
});

test("date and time text in WIB", () => {
  assert.equal(sessionDateText({ date: "2026-11-05", start_time: "13:00" }), "5 Nov 2026 · 13.00 WIB");
  assert.equal(sessionDateText({ date: "", start_time: "" }), "Belum ada data");
});

test("Ujian Saya (siswa): filter by running, scheduled and finished; counts add up", async () => {
  const { filterStudentExams, studentFilterCounts, studentKind } = await import("../src/sessions.ts");
  const ex = (id: number, status: string) => ({ id, status }) as { id: number; status: "Sedang Berlangsung" | "Terjadwal" | "Selesai" };
  const list = [ex(1, "Sedang Berlangsung"), ex(2, "Terjadwal"), ex(3, "Selesai"), ex(4, "Selesai")];
  assert.deepEqual(filterStudentExams(list, "selesai").map((e) => e.id), [3, 4]);
  assert.deepEqual(filterStudentExams(list, "berlangsung").map((e) => e.id), [1]);
  assert.deepEqual(filterStudentExams(list, "terjadwal").map((e) => e.id), [2]);
  assert.equal(filterStudentExams(list, "semua").length, 4);
  const c = studentFilterCounts(list);
  assert.deepEqual(c, { semua: 4, berlangsung: 1, terjadwal: 1, selesai: 2 });
  assert.equal(c.berlangsung + c.terjadwal + c.selesai, c.semua);
  assert.equal(studentKind("Draft"), "terjadwal");
});
