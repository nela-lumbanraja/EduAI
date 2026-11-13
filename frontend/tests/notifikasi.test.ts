// Run: node --experimental-strip-types --test tests/notifikasi.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import type { AIEvent, CaseSummary } from "../src/api.ts";
import {
  buildRows, dismissedCaseIds, filterRows, groupByTime, isDismissed, isUnread, LEGACY_KEYS, nextPos, prevPos, ringOf, rowText, segmentFill, SLIDE_MS,
  storySegments, timeGroup, visibleRows, withMark,
} from "../src/notifikasi.ts";
import { opensIndications } from "../src/routes.ts";

// Thursday 5 Nov 2026, 14.00 WIB (07.00 UTC)
const NOW = Date.parse("2026-11-05T07:00:00Z");
const iso = (t: number) => new Date(t).toISOString();
let n = 0;
const kase = (o: Partial<CaseSummary> & { indicator: string }) => {
  n += 1;
  return { case_id: `c${n}`, exam_id: 1, student_id: 10, label: null, review_status: null, unreviewed_count: 1, evidence_count: 0, latest_evidence_id: null,
    last_start_ts: iso(NOW - 600_000), event_ids: [`e${n}`], student: { id: 10, name: "Alya Putri", nis: null, class_name: null }, exam: { id: 1, name: "Ujian Matematika" }, ...o } as CaseSummary;
};

test("time groups in WIB: today, this week (Monday-Sunday), this month, earlier", () => {
  assert.equal(timeGroup(NOW - 3600_000, NOW), "Hari ini");
  assert.equal(timeGroup(Date.parse("2026-11-04T17:30:00Z"), NOW), "Hari ini");        // 00.30 WIB on 5 Nov
  assert.equal(timeGroup(Date.parse("2026-11-04T16:30:00Z"), NOW), "Minggu ini");      // 23.30 WIB on 4 Nov
  assert.equal(timeGroup(Date.parse("2026-11-02T01:00:00Z"), NOW), "Minggu ini");      // Monday 2 Nov
  assert.equal(timeGroup(Date.parse("2026-11-01T10:00:00Z"), NOW), "Bulan ini");       // Sunday 1 Nov
  assert.equal(timeGroup(Date.parse("2026-10-31T16:59:00Z"), NOW), "Sebelumnya");      // 23.59 WIB on 31 Oct
  const rows = buildRows([kase({ indicator: "PHONE_VISIBLE" }), kase({ indicator: "BOOK_VISIBLE", student_id: 11, last_start_ts: iso(NOW - 40 * 86400_000), student: { id: 11, name: "Bima", nis: null, class_name: null } })]);
  assert.deepEqual(groupByTime(rows, NOW).map((g) => [g.group, g.rows.length]), [["Hari ini", 1], ["Sebelumnya", 1]]);
});

test("one row per student and exam with the kinds listed; cannot-analyse periods are a separate row", () => {
  const rows = buildRows([kase({ indicator: "MULTIPLE_PERSONS", label: "Lebih dari satu orang" }), kase({ indicator: "OTHER_VOICE", label: "Suara orang lain", review_status: "Valid", unreviewed_count: 0 }),
    kase({ indicator: "HEAD_TURN", label: "Kepala menoleh" })], [{ category: "cannot_analyze", exam_id: 1, student_id: 10, student: null, exam: null, start_ts: iso(NOW - 60_000) } as AIEvent]);
  assert.equal(rows.length, 2);
  const k = rows.find((r) => r.kind === "kasus")!;
  assert.equal(rowText(k), "Alya Putri – 3 indikasi: Lebih dari satu orang, Suara orang lain, Kepala menoleh");
  assert.equal(k.unreviewed, 2);
  assert.match(rowText(rows.find((r) => r.kind === "tidak-terbaca")!), /tidak dapat dianalisis: 1 periode/);
});

test("filters: unreviewed, kind groups and 'tidak dapat dianalisis'", () => {
  const rows = buildRows([kase({ indicator: "PHONE_VISIBLE" }), kase({ indicator: "BOOK_VISIBLE", review_status: "Valid", unreviewed_count: 0 }),
    kase({ indicator: "FACE_ABSENT", student_id: 12, student: { id: 12, name: "Citra", nis: null, class_name: null }, review_status: "Valid", unreviewed_count: 0 }),
    kase({ indicator: "WHISPER", student_id: 13, student: { id: 13, name: "Dewi", nis: null, class_name: null } })],
  [{ category: "cannot_analyze", exam_id: 1, student_id: 14, student: { id: 14, name: "Eka", nis: null, class_name: null }, exam: null, start_ts: iso(NOW) } as AIEvent]);
  assert.equal(filterRows(rows, "semua").length, 4);
  assert.deepEqual(filterRows(rows, "belum").map((r) => r.student.name).sort(), ["Alya Putri", "Dewi"]);
  const hp = filterRows(rows, "hp-buku");
  assert.equal(hp.length, 1); assert.equal(hp[0].cases.length, 2);
  assert.deepEqual(filterRows(rows, "wajah-menoleh").map((r) => r.student.name), ["Citra"]);
  assert.deepEqual(filterRows(rows, "suara").map((r) => r.student.name), ["Dewi"]);
  assert.deepEqual(filterRows(rows, "orang"), []);
  assert.deepEqual(filterRows(buildRows([kase({ indicator: "CAMERA_OFF", label: "Kamera dimatikan" }), kase({ indicator: "MIC_OFF" }), kase({ indicator: "PHONE_VISIBLE" })]), "perangkat")[0].labels,
    ["Kamera dimatikan", "MIC_OFF"]);                                    // camera/microphone switched off
  assert.deepEqual(filterRows(rows, "tidak-terbaca").map((r) => r.student.name), ["Eka"]);
  const only = filterRows(buildRows([kase({ indicator: "PHONE_VISIBLE" }), kase({ indicator: "FACE_ABSENT" })]), "hp-buku")[0];
  assert.equal(only.cases.length, 1);                                    // the row keeps only the matching kind
});

test("ring: gold for evidence not seen yet (server, own audit), grey when seen, none without evidence or permission", () => {
  const [withEv] = buildRows([kase({ indicator: "PHONE_VISIBLE", evidence_count: 2, latest_evidence_id: "ev1" })]);
  const [noEv] = buildRows([kase({ indicator: "PHONE_VISIBLE" })]);
  const id = withEv.cases[0].case_id;
  assert.equal(ringOf(withEv, {}, true), "baru");
  assert.equal(ringOf(withEv, { [id]: { read: false, dismissed: false, evidence_seen: true } }, true), "dilihat");
  assert.equal(ringOf(withEv, {}, false), "tidak-ada");                  // e.g. penyelenggara, pihak sekolah
  assert.equal(ringOf(noEv, {}, true), "tidak-ada");
});

test("read and dismissed come from the server per case; a row is hidden only while all its cases are dismissed", () => {
  const rows = buildRows([kase({ indicator: "PHONE_VISIBLE" }), kase({ indicator: "BOOK_VISIBLE" })],
    [{ category: "cannot_analyze", exam_id: 1, student_id: 14, student: { id: 14, name: "Eka", nis: null, class_name: null }, exam: null, start_ts: iso(NOW) } as AIEvent]);
  const r = rows.find((x) => x.kind === "kasus")!;
  const t = rows.find((x) => x.kind === "tidak-terbaca")!;
  const [a, b] = r.cases.map((c) => c.case_id);
  assert.equal(isUnread(r, {}), true);
  let st = withMark({}, [a], "read", true);
  assert.equal(isUnread(r, st), true);                                   // one case still unread
  st = withMark(st, [b], "read", true);
  assert.equal(isUnread(r, st), false);
  assert.equal(isUnread(t, st), false);                                  // "tidak dapat dianalisis" has no read state
  st = withMark(st, [a], "dismissed", true);
  assert.equal(isDismissed(r, st), false);
  st = withMark(st, [b], "dismissed", true);
  assert.equal(isDismissed(r, st), true);
  assert.deepEqual(visibleRows(rows, st).map((x) => x.kind), ["tidak-terbaca"]);
  assert.deepEqual(dismissedCaseIds(rows, st).sort(), [a, b].sort());
  assert.equal(st[a].read, true);                                        // dismissing keeps the read flag
  // the server resets the flags when a new event arrives: the row is visible and unread again
  const fresh = { ...st, [a]: { read: false, dismissed: false, evidence_seen: false } };
  assert.equal(isDismissed(r, fresh), false); assert.equal(isUnread(r, fresh), true);
  assert.deepEqual(LEGACY_KEYS(7), ["eduai_notif_read_7", "eduai_notif_hidden_7", "eduai_evidence_viewed_7"]);
});

test("story: one segment per event with evidence, in time order", () => {
  const ev = (id: string, t: number, evidence_id: string | null) => ({ event_id: id, evidence_id, indicator: "PHONE_VISIBLE", label: "Ponsel terlihat", start_ts: iso(NOW - t), score: 0.8 });
  const s = storySegments([{ caseId: "c1", events: [ev("a", 100, "x1"), ev("b", 300, null), ev("c", 200, "x2")] }, { caseId: "c2", events: [ev("d", 500, "x3")] }]);
  assert.deepEqual(s.map((x) => [x.evidenceId, x.caseId]), [["x3", "c2"], ["x2", "c1"], ["x1", "c1"]]);
});

test("story navigation: next/previous frame and evidence, auto end, progress fill", () => {
  const frames = [2, 3];
  let p = { seg: 0, frame: 0, done: false };
  p = nextPos(p, frames); assert.deepEqual(p, { seg: 0, frame: 1, done: false });
  p = nextPos(p, frames); assert.deepEqual(p, { seg: 1, frame: 0, done: false });      // next evidence
  p = prevPos(p, frames); assert.deepEqual(p, { seg: 0, frame: 1, done: false });      // back to the last frame of the previous one
  p = { seg: 1, frame: 2, done: false };
  p = nextPos(p, frames); assert.equal(p.done, true);                                   // after the last image: done
  assert.deepEqual(prevPos({ seg: 0, frame: 0, done: false }, frames), { seg: 0, frame: 0, done: false });
  assert.deepEqual(segmentFill({ seg: 1, frame: 1, done: false }, frames, SLIDE_MS / 2), [1, 0.5]);
  assert.deepEqual(segmentFill({ seg: 0, frame: 0, done: false }, frames, 0), [0, 0]);
  assert.deepEqual(segmentFill({ seg: 1, frame: 2, done: true }, frames, 0), [1, 1]);
});

test("a copied case link (?kasus=) opens Indikasi for signed-in staff", () => {
  assert.equal(opensIndications("?kasus=k:1:2:x", "Pengawas"), true);
  assert.equal(opensIndications("?kasus=k:1:2:x", "Siswa"), false);
});
