// Run: node --experimental-strip-types tests/dashboard.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import type { Exam, StudentRow } from "../src/api.ts";
import { activeExams, analysisGaps, indicatorIcon, remainingText, statText, upcomingExams } from "../src/dashboard.ts";

const exam = (o: Partial<Exam>): Exam => ({
  id: 1, name: "Ujian", description: "", subject: "", class_name: "XI", date: "2026-11-05", start_time: "13:00", duration_min: 90,
  status: "Sedang Berlangsung", monitoring_active: true, analysis_source: "browser", monitoring_started_at: null, supervisor: null,
  student_count: 6, ...o,
});
const student = (o: Partial<StudentRow>): StudentRow => ({ id: 1, name: "Siswa", nis: null, class_name: null, ...o });

test("'Tidak dapat dianalisis' counts camera and sound quality gaps per student", () => {
  const rows = [
    student({ id: 1, ai: { state: "cannot_analyze", last_state: "cannot_analyze", frame_status: null, reason: "dark", face_count: null, latency_ms: null, updated_at: null, source: null } }),
    student({ id: 2, counts: { indications: 0, unreviewed: 0, open_indications: 0, open_cannot_analyze: 1 } }),
    student({ id: 3, audio: { consented: true, active: false, reason: "mic_off" } }),
    student({ id: 4, audio: { consented: false, active: false, reason: "not_consented" } }),   // no consent: not a quality gap
    student({ id: 5, ai: { state: "normal", last_state: "normal", frame_status: null, reason: null, face_count: 1, latency_ms: 20, updated_at: null, source: null } }),
  ];
  assert.deepEqual(analysisGaps(rows), { camera: 2, sound: 1, students: 3, label: "Tidak dapat dianalisis: 3 siswa (kamera 2, suara 1)" });
});

test("no gaps: no 'Tidak dapat dianalisis' label, and it is never an indication", () => {
  assert.equal(analysisGaps([]).label, null);
  assert.doesNotMatch(analysisGaps([student({ counts: { indications: 0, unreviewed: 0, open_indications: 0, open_cannot_analyze: 1 } })]).label ?? "", /indikasi|kecurangan/i);
});

test("numbers come from the API: 0 stays 0, a missing value is 'Belum ada data'", () => {
  assert.equal(statText(0), "0");
  assert.equal(statText(11), "11");
  assert.equal(statText(undefined), "Belum ada data");
  assert.equal(statText(null), "Belum ada data");
});

test("remaining time uses the WIB exam schedule", () => {
  const e = exam({ date: "2026-11-05", start_time: "13:00", duration_min: 90 });   // ends 14.30 WIB = 07.30 UTC
  assert.equal(remainingText(e, Date.parse("2026-11-05T06:48:00Z")), "42 mnt");
  assert.equal(remainingText(e, Date.parse("2026-11-05T06:18:00Z")), "1 jam 12 mnt");
  assert.equal(remainingText(e, Date.parse("2026-11-05T08:00:00Z")), "Waktu ujian habis");
});

test("active and upcoming sessions", () => {
  const list = [exam({ id: 1 }), exam({ id: 2, status: "Terjadwal", date: "2026-11-07" }), exam({ id: 3, status: "Terjadwal", date: "2026-11-06" }), exam({ id: 4, status: "Selesai" })];
  assert.deepEqual(activeExams(list).map((e) => e.id), [1]);
  assert.deepEqual(upcomingExams(list).map((e) => e.id), [3, 2]);
  assert.deepEqual(upcomingExams([]), []);
});

test("indicator icons", () => {
  assert.equal(indicatorIcon("PHONE_VISIBLE"), "phone");
  assert.equal(indicatorIcon("MULTIPLE_PERSONS"), "users");
  assert.equal(indicatorIcon("HEAD_TURN_REPEATED"), "eye");
  assert.equal(indicatorIcon("WHISPER"), "mic");
  assert.equal(indicatorIcon("SOMETHING_NEW"), "bell");
});
