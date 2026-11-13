// Run: node --experimental-strip-types tests/chartData.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import type { CaseSummary, StudentRow } from "../src/api.ts";
import {
  attendanceParts, caseStatusBreakdown, casesByKind, clockLabelWib, EMPTY_CHART, hourLabel, hourSeries, indicationKind, isEmpty,
  monitorStatus, reportResults, reviewFunnel, sessionTimeline, timelineTicks, wibDate,
} from "../src/chartData.ts";

const kase = (review_status: CaseSummary["review_status"], unreviewed_count = 0, indicator = "MULTIPLE_PERSONS") => ({ review_status, unreviewed_count, indicator }) as CaseSummary;
const NOW = Date.parse("2026-11-05T07:20:00Z");     // 14.20 WIB
const sum = (s: { value: number }[]) => s.reduce((a, x) => a + x.value, 0);

test("empty data -> placeholder (every value 0)", () => {
  assert.equal(EMPTY_CHART, "Belum ada data untuk sesi ini.");
  assert.equal(isEmpty([0, 0, 0]), true);
  assert.equal(isEmpty([]), true);
  assert.equal(isEmpty([0, 2]), false);
  assert.equal(isEmpty(caseStatusBreakdown([], 0).segments.map((s) => s.value)), true);
  assert.equal(isEmpty(monitorStatus([]).segments.map((s) => s.value)), true);
  assert.equal(isEmpty(reviewFunnel(0, []).map((s) => s.value)), true);
  assert.equal(isEmpty(attendanceParts({ enrolled: 0, joined: 0, not_joined: 0 }).segments.map((s) => s.value)), true);
  assert.equal(isEmpty(reportResults({ total: 0, valid: 0, invalid: 0, further: 0, unreviewed: 0 }).segments.map((s) => s.value)), true);
  assert.equal(sessionTimeline([], NOW - 3600_000, NOW).points.length, 0);
});

test("donut: the parts add up to the total", () => {
  const b = caseStatusBreakdown([kase(null, 2), kase("Valid"), kase("Valid"), kase("Tidak Valid"), kase("Perlu Tinjauan Lanjut"), kase("Valid", 1)], 6);
  assert.deepEqual(b.segments.map((s) => [s.label, s.value]), [["Belum ditinjau", 2], ["Valid", 2], ["Tidak valid", 1], ["Perlu tinjauan lanjut", 1]]);
  assert.equal(b.sum, b.total);
  assert.equal(b.mismatch, null);
});

test("donut: a 'Campuran' case or a different API total is reported, never forced", () => {
  const b = caseStatusBreakdown([kase("Valid"), kase("Campuran")], 2);
  assert.equal(b.sum, 1);
  assert.match(b.mismatch ?? "", /Jumlah per status \(1\) tidak sama dengan total kasus dari API \(2\).*Campuran/);
  assert.match(caseStatusBreakdown([kase("Valid")], 3).mismatch ?? "", /Daftar kasus berisi 1 kasus/);
});

test("attendance donut: present + absent = enrolled; a mismatch is reported", () => {
  const a = attendanceParts({ enrolled: 6, joined: 4, not_joined: 2 });
  assert.equal(sum(a.segments), a.total);
  assert.equal(a.mismatch, null);
  assert.match(attendanceParts({ enrolled: 6, joined: 4, not_joined: 1 }).mismatch ?? "", /\(5\).*\(6\)/);
});

test("report results: valid + invalid + further + unreviewed = total", () => {
  const r = reportResults({ total: 7, valid: 2, invalid: 1, further: 1, unreviewed: 3 });
  assert.equal(sum(r.segments), r.total);
  assert.equal(r.mismatch, null);
});

test("detections per hour from the server: WIB date, hours up to now", () => {
  assert.equal(wibDate(NOW), "2026-11-05");
  assert.equal(wibDate(Date.parse("2026-11-05T17:30:00Z")), "2026-11-06");      // 00.30 WIB next day
  const s = hourSeries({ date: "2026-11-05", hours: [{ hour: 7, count: 2 }, { hour: 13, count: 1 }], total: 3 }, NOW);
  assert.equal(s.points.length, 15);                                              // 00.00 .. 14.00
  assert.equal(s.points[7].count, 2);
  assert.equal(s.points[7].label, "07.00");
  assert.equal(s.total, 3);
  assert.equal(hourSeries({ date: "2026-11-04", hours: [], total: 0 }, NOW).points.length, 24);   // a past day: all hours
  assert.equal(hourLabel(0), "00.00");
});

test("timeline: WIB time labels and position on the session axis", () => {
  const start = Date.parse("2026-11-05T06:00:00Z"), end = Date.parse("2026-11-05T08:00:00Z");   // 13.00-15.00 WIB
  const ev = (id: string, ts: string, indicator = "PHONE_VISIBLE", category: "indication" | "cannot_analyze" = "indication") =>
    ({ event_id: id, start_ts: ts, indicator, label: null, category, student: { id: 1, name: "Alya", nis: null, class_name: null } });
  const t = sessionTimeline([ev("a", "2026-11-05T07:00:00+00:00"), ev("b", "2026-11-05 06:30:00", "HEAD_TURN_REPEATED"),
    ev("c", "2026-11-05T05:00:00Z"), ev("d", "2026-11-05T07:10:00Z", "FACE_ABSENT", "cannot_analyze")], start, end);
  assert.deepEqual(t.points.map((p) => [p.id, p.time, p.x, p.kind]), [["b", "13.30 WIB", 0.25, "berulang"], ["a", "14.00 WIB", 0.5, "benda"]]);
  assert.equal(t.outside, 1);
  assert.equal(t.startLabel, "13.00 WIB");
  assert.equal(t.endLabel, "15.00 WIB");
  assert.equal(clockLabelWib(Date.parse("2026-11-04T17:05:00Z")), "00.05 WIB");
  assert.deepEqual(timelineTicks(start, end).map((x) => x.label), ["13.00", "13.30", "14.00", "14.30", "15.00"]);
});

test("monitoring status: each student in exactly one part", () => {
  const st = (o: Partial<StudentRow>) => ({ id: 1, name: "S", nis: null, class_name: null, ...o }) as StudentRow;
  const on = { joined: true, online: true, joined_at: null, last_seen: null, camera_on: true, mic_on: true, connection: null, rtt_ms: null };
  const rows = [st({ presence: on }), st({ presence: { ...on, online: false } }), st({}),
    st({ presence: on, counts: { indications: 1, unreviewed: 1, open_indications: 0, open_cannot_analyze: 0 } }),
    st({ presence: on, ai: { state: "cannot_analyze", last_state: null, frame_status: null, reason: null, face_count: null, latency_ms: null, updated_at: null, source: null } })];
  const m = monitorStatus(rows);
  assert.deepEqual(m.segments.map((s) => [s.label, s.value]), [["Online", 1], ["Perlu perhatian", 1], ["Tidak dapat dianalisis", 1], ["Offline", 2]]);
  assert.equal(sum(m.segments), m.total);
});

test("indications: funnel and cases per kind split by status", () => {
  const cases = [kase(null, 1, "MULTIPLE_PERSONS"), kase("Valid", 0, "PHONE_VISIBLE"), kase("Perlu Tinjauan Lanjut", 0, "BOOK_VISIBLE"), kase("Campuran", 0, "WHISPER")];
  assert.deepEqual(reviewFunnel(9, cases).map((s) => s.value), [9, 4, 1, 1]);
  const k = casesByKind(cases);
  assert.deepEqual(k.map((r) => r.label), ["Lebih dari satu orang", "Kepala menoleh", "Menoleh berulang", "Suara orang lain", "Wajah tidak terlihat", "HP/buku terlihat"]);
  const benda = k.find((r) => r.key === "benda")!;
  assert.equal(benda.total, 2);
  assert.equal(sum(benda.parts), benda.total);
  assert.equal(k.find((r) => r.key === "suara")!.parts.find((p) => p.key === "campuran")!.value, 1);
  assert.equal(indicationKind("SOMETHING_NEW"), "lain");
  assert.equal(indicationKind("CAMERA_OFF"), "perangkat"); assert.equal(indicationKind("MIC_OFF"), "perangkat");
  assert.deepEqual(casesByKind([kase(null, 1, "CAMERA_OFF")]).find((r) => r.key === "perangkat")?.total, 1);
  assert.equal(casesByKind([kase(null, 1, "SOMETHING_NEW")]).at(-1)!.label, "Lainnya");
});

test("session bins: slot size keeps at most 24 columns, every indication in exactly one slot", async () => {
  const { sessionBins } = await import("../src/chartData.ts");
  const start = Date.parse("2026-11-06T01:00:00Z"), min = 60_000;            // 08.00 WIB
  const pt = (m: number, kind: "orang" | "suara", student: string) => ({ id: `${m}${kind}`, at: start + m * min, x: 0, kind, student, label: kind, time: "" });
  const points = [pt(0, "orang", "Alya"), pt(4.9, "suara", "Alya"), pt(5, "suara", "Bima"), pt(119.9, "orang", "Citra"), pt(120, "orang", "Dewi")];
  const r = sessionBins({ points, start, end: start + 120 * min });
  assert.equal(r.stepMin, 5); assert.equal(r.bins.length, 24);
  assert.deepEqual([r.bins[0].total, r.bins[0].byKind, r.bins[0].students], [2, { orang: 1, suara: 1 }, ["Alya"]]);
  assert.equal(r.bins[0].range, "08.00–08.05 WIB");
  assert.equal(r.bins[1].total, 1);
  assert.equal(r.bins[23].total, 2);                                          // the very end belongs to the last slot
  assert.equal(r.bins.reduce((a, b) => a + b.total, 0), points.length);
  assert.equal(sessionBins({ points: [], start, end: start + 300 * min }).stepMin, 15);
  assert.equal(sessionBins({ points: [], start, end: start + 20 * min }).bins.length, 4);
  assert.deepEqual(sessionBins({ points: [], start, end: start }).bins, []);
});

test("history: one row per finished session, newest first, parts from the report; summary numbers", async () => {
  const { historyRows } = await import("../src/chartData.ts");
  const rep = (id: number, date: string, total: number, valid: number, invalid: number, further: number) =>
    ({ exam: { id, name: `Ujian ${id}`, date }, indications: { total, valid, invalid, further, unreviewed: total - valid - invalid - further } });
  const h = historyRows([rep(1, "2026-11-03", 10, 6, 1, 1), rep(2, "2026-11-06", 4, 0, 0, 0), rep(3, "2026-11-01", 0, 0, 0, 0)]);
  assert.deepEqual(h.rows.map((r) => r.id), [2, 1, 3]);
  assert.deepEqual(h.rows[1].parts, { valid: 6, tidak_valid: 1, lanjut: 1, belum: 2 });
  assert.deepEqual([h.sessions, h.total, h.open, h.reviewedPct], [3, 14, 6, 57]);
  assert.equal(historyRows([]).reviewedPct, 100);
});

test("session bins with a fixed slot: the dashboard uses one column per hour since 00.00 WIB", async () => {
  const { sessionBins } = await import("../src/chartData.ts");
  const start = Date.parse("2026-11-06T00:00:00+07:00"), h = 3600_000;
  const pt = (t: number) => ({ id: String(t), at: start + t, x: 0, kind: "orang" as const, student: "A", label: "", time: "" });
  const r = sessionBins({ points: [pt(10 * 60_000), pt(4.5 * h)], start, end: start + 5 * h + 10 * 60_000 }, 24, 60);
  assert.equal(r.stepMin, 60); assert.equal(r.bins.length, 6);
  assert.deepEqual([r.bins[0].label, r.bins[0].total, r.bins[4].total], ["00.00", 1, 1]);
});
