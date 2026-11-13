// Run: node --experimental-strip-types --test tests/indikasi.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import type { AIEvent, CaseSummary } from "../src/api.ts";
import {
  activityFeed, axisTicks, drawerCases, drawerTitle, examProgress, filterCases, filterQuery, JENIS, jenisCounts, jenisOf, kindBars, kpi7, parseFilter, sinceIso,
  statusOf, statusSummary, supervisorLoad, unreadableByExam,
} from "../src/indikasi.ts";
import { opensIndications } from "../src/routes.ts";

const NOW = Date.parse("2026-11-05T07:00:00Z");
const ago = (days: number) => new Date(NOW - days * 86400_000).toISOString();
let n = 0;
const kase = (indicator: string, review_status: CaseSummary["review_status"] = null, unreviewed_count = review_status ? 0 : 1, o: Partial<CaseSummary> = {}) => {
  n += 1;
  return { case_id: `c${n}`, indicator, review_status, unreviewed_count, event_ids: [`e${n}`], first_start_ts: ago(1), updated_at: ago(1), ...o } as CaseSummary;
};
const ev = (event_id: string, start_ts: string, category: AIEvent["category"] = "indication") => ({ event_id, start_ts, category }) as AIEvent;

test("every backend indicator code has a kind; 'keluar layar' has none", () => {
  const expect: Record<string, string> = {
    PHONE_VISIBLE: "hp", MULTIPLE_PERSONS: "orang", BOOK_VISIBLE: "buku", FACE_ABSENT: "wajah", HEAD_TURN: "menoleh", HEAD_TURN_REPEATED: "menoleh",
    OTHER_VOICE: "suara", WHISPER: "suara", MEDIA_SOUND: "media", CAMERA_OFF: "kamera", MIC_OFF: "mikrofon", CANNOT_ANALYZE: "tidak-terbaca",
  };
  for (const [code, key] of Object.entries(expect)) assert.equal(jenisOf(code), key, code);
  assert.equal(jenisOf("TAB_SWITCH"), null);
  assert.equal(JENIS.some((j) => /keluar/i.test(j.label)), false);
  assert.equal(JENIS.filter((j) => j.quality).map((j) => j.key).join(), "tidak-terbaca");
});

test("filter in the URL query: read, write, ignore unknown values, keep other parameters", () => {
  assert.deepEqual(parseFilter("?jenis=hp&status=belum"), { jenis: "hp", status: "belum" });
  assert.deepEqual(parseFilter("?jenis=keluar&status=x"), { jenis: null, status: null });
  assert.equal(filterQuery({ jenis: "buku", status: "valid" }), "?jenis=buku&status=valid");
  assert.equal(filterQuery({ jenis: null, status: null }, "?jenis=hp&status=belum"), "");
  assert.equal(filterQuery({ jenis: "hp", status: null }, "?lang=id&status=valid"), "?lang=id&jenis=hp");
  assert.deepEqual(parseFilter(filterQuery({ jenis: "menoleh", status: "campuran" })), { jenis: "menoleh", status: "campuran" });
});

test("each kind button filters to that kind only; kind + status combine", () => {
  const cases = [kase("PHONE_VISIBLE"), kase("PHONE_VISIBLE", "Valid"), kase("BOOK_VISIBLE", "Valid"), kase("HEAD_TURN"), kase("HEAD_TURN_REPEATED", "Tidak Valid"),
    kase("FACE_ABSENT", "Campuran"), kase("OTHER_VOICE", "Perlu Tinjauan Lanjut"), kase("MULTIPLE_PERSONS")];
  for (const j of JENIS) {
    const got = filterCases(cases, { jenis: j.key, status: null });
    assert.ok(got.every((c) => jenisOf(c.indicator) === j.key), j.key);
    assert.equal(got.length, cases.filter((c) => jenisOf(c.indicator) === j.key).length, j.key);
  }
  assert.equal(filterCases(cases, { jenis: null, status: null }).length, 8);
  assert.deepEqual(filterCases(cases, { jenis: "hp", status: "valid" }).map((c) => c.indicator), ["PHONE_VISIBLE"]);
  assert.equal(filterCases(cases, { jenis: "menoleh", status: "belum" }).length, 1);
  assert.equal(filterCases(cases, { jenis: "wajah", status: "campuran" }).length, 1);
  assert.equal(filterCases(cases, { jenis: "tidak-terbaca", status: null }).length, 0);       // never a case
  assert.equal(statusOf(kase("HEAD_TURN", "Valid", 2)), "belum");                               // new unreviewed event wins
});

test("button counts follow the status filter; 'tidak dapat dianalisis' counts periods", () => {
  const cases = [kase("PHONE_VISIBLE"), kase("PHONE_VISIBLE", "Valid"), kase("BOOK_VISIBLE")];
  const cannot = [ev("a", ago(1), "cannot_analyze"), ev("b", ago(1), "cannot_analyze")];
  const all = jenisCounts(cases, cannot, null);
  assert.equal(all.semua, 3); assert.equal(all.hp, 2); assert.equal(all.buku, 1); assert.equal(all["tidak-terbaca"], 2);
  const belum = jenisCounts(cases, cannot, "belum");
  assert.equal(belum.semua, 2); assert.equal(belum.hp, 1);
});

test("KPI over 7 days: reviewed, detections of the filtered cases, new and unreviewed cases", () => {
  const a = kase("PHONE_VISIBLE", "Valid", 0, { updated_at: ago(2), first_start_ts: ago(2), event_ids: ["x1", "x2"] });
  const b = kase("PHONE_VISIBLE", "Valid", 0, { updated_at: ago(9), first_start_ts: ago(10), event_ids: ["x3"] });
  const c = kase("BOOK_VISIBLE", null, 1, { first_start_ts: ago(3), event_ids: ["x4"] });
  const d = kase("BOOK_VISIBLE", null, 1, { first_start_ts: ago(12), event_ids: ["x5"] });
  const det = [ev("x1", ago(2)), ev("x2", ago(1)), ev("x3", ago(9)), ev("x4", ago(3)), ev("x5", ago(6)), ev("zz", ago(1))];
  assert.deepEqual(kpi7([a, b, c, d], det, NOW), { ditinjau: 1, deteksi: 4, deteksiCapped: false, kasusBaru: 2, belum: 1 });
  const hp = filterCases([a, b, c, d], { jenis: "hp", status: null });
  assert.deepEqual(kpi7(hp, det, NOW), { ditinjau: 1, deteksi: 2, deteksiCapped: false, kasusBaru: 1, belum: 0 });
  assert.equal(kpi7([], det, NOW).deteksi, 0);
  assert.equal(kpi7([a], Array.from({ length: 500 }, (_, i) => ev(`q${i}`, ago(1))), NOW).deteksiCapped, true);
  assert.equal(sinceIso(NOW), ago(7));
});

test("status donut: parts add up to the total; empty data -> total 0", () => {
  const cases = [kase("HEAD_TURN"), kase("HEAD_TURN", "Valid"), kase("PHONE_VISIBLE", "Tidak Valid"), kase("FACE_ABSENT", "Campuran"), kase("BOOK_VISIBLE", "Perlu Tinjauan Lanjut")];
  const s = statusSummary(cases);
  assert.equal(s.total, 5);
  assert.equal(s.segments.reduce((x, y) => x + y.value, 0), s.total);
  assert.deepEqual(s.segments.map((x) => x.value), [1, 1, 1, 1, 1]);
  assert.equal(statusSummary([]).total, 0);
});

test("'tidak dapat dianalisis' grouped per exam, most periods first", () => {
  const e = (exam_id: number, student_id: number, d = 30) => ({ category: "cannot_analyze", exam_id, exam: { id: exam_id, name: `Ujian ${exam_id}` }, student_id, duration_s: d, start_ts: ago(1) }) as AIEvent;
  const rows = unreadableByExam([e(1, 10), e(2, 20), e(2, 21), e(2, 20, 90), { ...e(3, 1), category: "indication" } as AIEvent]);
  assert.deepEqual(rows.map((r) => [r.examId, r.periods, r.students, r.seconds]), [[2, 3, 2, 150], [1, 1, 1, 30]]);
  assert.deepEqual(unreadableByExam([]), []);
});

test("a filter in the URL opens Indikasi for signed-in staff only", () => {
  assert.equal(opensIndications("?jenis=hp", "Pengawas"), true);
  assert.equal(opensIndications("?status=belum", "Admin"), true);
  assert.equal(opensIndications("?jenis=hp", "Siswa"), false);
  assert.equal(opensIndications("?jenis=hp", null), false);
  assert.equal(opensIndications("", "Pengawas"), false);
});

// ---------------------------------------------------------------- step 2: rows 3–5 and the drawer
const stu = (id: number, name: string) => ({ student_id: id, student: { id, name, nis: null, class_name: null } });
const exm = (id: number, name: string) => ({ exam_id: id, exam: { id, name } });

test("recent activity: one entry per reviewer decision per case, newest first, only cases shown", () => {
  const a = kase("PHONE_VISIBLE", "Valid", 0, { event_ids: ["a1", "a2"], ...stu(1, "Alya"), ...exm(1, "Matematika") });
  const b = kase("BOOK_VISIBLE", "Tidak Valid", 0, { event_ids: ["b1"], ...stu(2, "Bima"), ...exm(1, "Matematika") });
  const r = (reviewer: string, decision: "Valid" | "Tidak Valid", at: string) => ({ reviewer, decision, note: "", created_at: at });
  const events = [{ event_id: "a1", last_review: r("Bu Sari", "Valid", ago(2)) }, { event_id: "a2", last_review: r("Bu Sari", "Valid", ago(2)) },
    { event_id: "b1", last_review: r("Pak Andi", "Tidak Valid", ago(1)) }, { event_id: "x9", last_review: r("Lain", "Valid", ago(0)) }, { event_id: "b2", last_review: null }];
  const feed = activityFeed([a, b], events);
  assert.deepEqual(feed.map((x) => [x.reviewer, x.case.case_id, x.decision, x.events]), [["Pak Andi", b.case_id, "Tidak Valid", 1], ["Bu Sari", a.case_id, "Valid", 2]]);
  assert.deepEqual(activityFeed([a], events).map((x) => x.reviewer), ["Bu Sari"]);             // kind/status filter applies
  assert.deepEqual(activityFeed([], []), []);
});

test("bars per kind: indication kinds only, counts and percentages; the table uses the same numbers", () => {
  const bars = kindBars([kase("PHONE_VISIBLE"), kase("PHONE_VISIBLE"), kase("BOOK_VISIBLE"), kase("HEAD_TURN_REPEATED")]);
  assert.equal(bars.some((b) => b.key === "tidak-terbaca"), false);
  assert.deepEqual(bars.filter((b) => b.value).map((b) => [b.key, b.value, b.pct]), [["hp", 2, 50], ["buku", 1, 25], ["menoleh", 1, 25]]);
  assert.ok(kindBars([]).every((b) => b.value === 0 && b.pct === 0));
  assert.deepEqual(axisTicks(3), [0, 1, 2, 3]);
  assert.deepEqual(axisTicks(9), [0, 5, 10]);
  assert.deepEqual(axisTicks(0), [0, 1]);
});

test("supervisor workload and progress per exam come from the cases and the exam's supervisor", () => {
  const cases = [kase("PHONE_VISIBLE", null, 1, exm(1, "Matematika")), kase("BOOK_VISIBLE", "Valid", 0, exm(1, "Matematika")),
    kase("FACE_ABSENT", null, 1, exm(2, "Fisika")), kase("FACE_ABSENT", "Valid", 0, exm(3, "Kimia"))];
  const exams = [{ id: 1, supervisor: { id: 7, name: "Bu Sari" } }, { id: 2, supervisor: { id: 8, name: "Pak Andi" } }, { id: 3, supervisor: null }];
  assert.deepEqual(supervisorLoad(cases, exams).map((l) => [l.name, l.cases, l.belum, l.pct]),
    [["Bu Sari", 2, 1, 50], ["Belum ada pengawas", 1, 0, 25], ["Pak Andi", 1, 1, 25]]);
  assert.deepEqual(examProgress(cases).map((p) => [p.exam, p.reviewed, p.total, p.pct]), [["Fisika", 0, 1, 0], ["Matematika", 1, 2, 50], ["Kimia", 1, 1, 100]]);
  assert.deepEqual(examProgress([]), []);
  assert.deepEqual(supervisorLoad([], exams), []);
});

test("drawer: the students behind a click (kind + status), newest first, with a readable title", () => {
  const old = kase("PHONE_VISIBLE", null, 1, { last_start_ts: ago(3), ...stu(1, "Alya") });
  const neu = kase("PHONE_VISIBLE", null, 1, { last_start_ts: ago(0), ...stu(2, "Bima") });
  const done = kase("PHONE_VISIBLE", "Valid", 0, { last_start_ts: ago(1), ...stu(3, "Citra") });
  const book = kase("BOOK_VISIBLE", null, 1, { last_start_ts: ago(0), ...stu(4, "Dewi") });
  const all = [old, neu, done, book];
  assert.deepEqual(drawerCases(all, { jenis: "hp", status: null }).map((c) => c.student!.name), ["Bima", "Citra", "Alya"]);
  assert.deepEqual(drawerCases(all, { jenis: "hp", status: "belum" }).map((c) => c.student!.name), ["Bima", "Alya"]);
  assert.deepEqual(drawerCases(all, { jenis: null, status: "valid" }).map((c) => c.student!.name), ["Citra"]);
  assert.deepEqual(drawerCases(all, { jenis: "orang", status: null }), []);
  assert.equal(drawerTitle({ jenis: "hp", status: "belum" }), "HP terlihat · Belum ditinjau");
  assert.equal(drawerTitle({ jenis: null, status: null }), "Semua indikasi");
});

test("donuts: kinds in a fixed order and colour (camera + microphone joined), supervisor colour follows the person", async () => {
  const { kindSlices, loadSlices, PALETTE, OTHER_COLOR } = await import("../src/indikasi.ts");
  const ks = kindSlices([kase("PHONE_VISIBLE"), kase("CAMERA_OFF"), kase("MIC_OFF"), kase("FACE_ABSENT")]);
  assert.equal(ks.length, 8);
  assert.deepEqual(ks.filter((s) => s.value).map((s) => [s.key, s.value]), [["hp", 1], ["wajah", 1], ["perangkat", 2]]);
  assert.equal(new Set(ks.map((s) => s.color)).size, 8);                         // eight distinct hues, one per part
  assert.equal(ks.reduce((a, s) => a + s.value, 0), 4);
  const load = (id: number | null, name: string, cases: number) => ({ id, name, cases, belum: 1, pct: 0 });
  const a = loadSlices([load(7, "Rina", 5), load(3, "Agus", 9)]);
  assert.deepEqual(a.map((s) => [s.label, s.color]), [["Agus", PALETTE[0]], ["Rina", PALETTE[1]]]);   // biggest first, colour by id
  const b = loadSlices([load(7, "Rina", 50), load(3, "Agus", 1)]);
  assert.equal(b.find((s) => s.label === "Rina")!.color, PALETTE[1]);            // same colour although the rank changed
  const many = loadSlices(Array.from({ length: 10 }, (_, i) => load(i + 1, `P${i + 1}`, 20 - i)));
  assert.equal(many.length, 8); assert.equal(many[7].label, "Lainnya (3 pengawas)"); assert.equal(many[7].color, OTHER_COLOR);
  assert.equal(loadSlices([load(null, "Belum ada pengawas", 2)])[0].color, OTHER_COLOR);
});

test("drawer for a joined donut part lists both kinds", () => {
  const cam = kase("CAMERA_OFF", null, 1, { last_start_ts: ago(1) }), mic = kase("MIC_OFF", null, 1, { last_start_ts: ago(0) }), hp = kase("PHONE_VISIBLE");
  assert.deepEqual(drawerCases([cam, mic, hp], { jenis: null, status: null, kinds: ["kamera", "mikrofon"], label: "Kamera/mikrofon dimatikan" }).map((c) => c.case_id),
    [mic.case_id, cam.case_id]);
  assert.equal(drawerTitle({ jenis: null, status: "belum", kinds: ["kamera", "mikrofon"], label: "Kamera/mikrofon dimatikan" }), "Kamera/mikrofon dimatikan · Belum ditinjau");
});

test("'tidak dapat dianalisis' is no longer a filter on the Indikasi page (old links show all cases)", () => {
  assert.equal(parseFilter("?jenis=tidak-terbaca").jenis, null);
  assert.equal(parseFilter("?jenis=kamera").jenis, "kamera");
});
