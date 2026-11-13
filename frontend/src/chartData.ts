// Data for the charts, computed from API responses only (no numbers are written here). No React.
import type { AIEvent, CaseSummary, StudentRow } from "./api.ts";

export const EMPTY_CHART = "Belum ada data untuk sesi ini.";
const WIB_OFFSET_MS = 7 * 3600_000;

export const isEmpty = (values: number[]) => values.every((v) => !v);
export type Segment<K extends string = string> = { key: K; label: string; value: number };
const sumOf = (s: { value: number }[]) => s.reduce((a, x) => a + x.value, 0);

/** Backend time (UTC; no offset = UTC) in epoch ms, or null. */
export function utcMs(iso?: string | null): number | null {
  const s = (iso ?? "").trim().replace(" ", "T");
  if (!s) return null;
  const t = Date.parse(/(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(s) ? s : `${s}Z`);
  return Number.isFinite(t) ? t : null;
}
/** "14.05 WIB" */
export function clockLabelWib(ms: number): string {
  const d = new Date(ms + WIB_OFFSET_MS);
  return `${String(d.getUTCHours()).padStart(2, "0")}.${String(d.getUTCMinutes()).padStart(2, "0")} WIB`;
}

// ---------------------------------------------------------------- review status of cases
export type CaseStatusKey = "belum" | "valid" | "tidak_valid" | "lanjut";
export const CASE_STATUS_LABEL: Record<CaseStatusKey, string> = {
  belum: "Belum ditinjau", valid: "Valid", tidak_valid: "Tidak valid", lanjut: "Perlu tinjauan lanjut",
};
const ORDER: CaseStatusKey[] = ["belum", "valid", "tidak_valid", "lanjut"];

/** The review status of one case: unreviewed events first (same rule as the backend). "Campuran" = reviewers disagreed. */
export function caseStatus(c: Pick<CaseSummary, "unreviewed_count" | "review_status">): CaseStatusKey | "campuran" {
  if (c.unreviewed_count > 0 || !c.review_status) return "belum";
  if (c.review_status === "Valid") return "valid";
  if (c.review_status === "Tidak Valid") return "tidak_valid";
  if (c.review_status === "Perlu Tinjauan Lanjut") return "lanjut";
  return "campuran";
}

/** Cases per review status. A "Campuran" case fits none of the four parts: it is counted in `outside` and
 *  reported, never forced into a part. `total` is the API's own case total. */
export function caseStatusBreakdown(cases: CaseSummary[], total: number) {
  const counts: Record<CaseStatusKey, number> = { belum: 0, valid: 0, tidak_valid: 0, lanjut: 0 };
  let outside = 0;
  for (const c of cases) { const k = caseStatus(c); if (k === "campuran") outside += 1; else counts[k] += 1; }
  const segments = ORDER.map((key) => ({ key, label: CASE_STATUS_LABEL[key], value: counts[key] }));
  const sum = sumOf(segments);
  let mismatch: string | null = null;
  if (sum !== total) {
    const parts = [`Jumlah per status (${sum}) tidak sama dengan total kasus dari API (${total}).`];
    if (outside) parts.push(`${outside} kasus berstatus "Campuran" (keputusan pengawas berbeda dalam satu kasus) tidak masuk kategori mana pun.`);
    if (cases.length !== total) parts.push(`Daftar kasus berisi ${cases.length} kasus.`);
    mismatch = parts.join(" ");
  }
  return { segments, sum, total, outside, mismatch };
}

// ---------------------------------------------------------------- detections per hour (server: /api/dashboard/detections-per-hour)
export type HourCounts = { date: string; hours: { hour: number; count: number }[]; total: number };

/** "2026-11-05": today's date in WIB, for the detections-per-hour endpoint. */
export function wibDate(now: number): string {
  return new Date(now + WIB_OFFSET_MS).toISOString().slice(0, 10);
}

/** "08.00" */
export const hourLabel = (h: number) => `${String(h).padStart(2, "0")}.00`;

/** Points for the line chart: every hour of the day, up to the current hour when the day is today. */
export function hourSeries(data: HourCounts, now: number) {
  const last = data.date === wibDate(now) ? new Date(now + WIB_OFFSET_MS).getUTCHours() : 23;
  const byHour = new Map(data.hours.map((h) => [h.hour, h.count]));
  const points = Array.from({ length: last + 1 }, (_, hour) => ({ hour, label: hourLabel(hour), count: byHour.get(hour) ?? 0 }));
  return { points, total: data.total };
}

// ---------------------------------------------------------------- kinds of indication (colour + shape + label)
export type KindKey = "orang" | "menoleh" | "berulang" | "suara" | "wajah" | "benda" | "perangkat" | "lain";
export const KINDS: { key: KindKey; label: string }[] = [
  { key: "orang", label: "Lebih dari satu orang" }, { key: "menoleh", label: "Kepala menoleh" },
  { key: "berulang", label: "Menoleh berulang" }, { key: "suara", label: "Suara orang lain" },
  { key: "wajah", label: "Wajah tidak terlihat" }, { key: "benda", label: "HP/buku terlihat" },
  { key: "perangkat", label: "Kamera/mikrofon dimatikan" }, { key: "lain", label: "Lainnya" },
];
export function indicationKind(indicator: string): KindKey {
  if (indicator === "MULTIPLE_PERSONS") return "orang";
  if (indicator === "HEAD_TURN_REPEATED") return "berulang";
  if (indicator.startsWith("HEAD_TURN")) return "menoleh";
  if (["OTHER_VOICE", "WHISPER", "BISIKAN", "BICARA_MULUT_DIAM"].includes(indicator)) return "suara";
  if (indicator === "FACE_ABSENT") return "wajah";
  if (indicator.startsWith("PHONE") || indicator.startsWith("BOOK")) return "benda";
  if (indicator === "CAMERA_OFF" || indicator === "MIC_OFF") return "perangkat";
  return "lain";
}
export const kindLabel = (k: KindKey) => KINDS.find((x) => x.key === k)!.label;

// ---------------------------------------------------------------- timeline of one session
export type TimelinePoint = { id: string; at: number; x: number; kind: KindKey; student: string; label: string; time: string };

/** Indications placed on the exam's time axis (0 = start, 1 = end). Events outside the session are counted, not drawn. */
export function sessionTimeline(events: Pick<AIEvent, "event_id" | "start_ts" | "indicator" | "label" | "category" | "student">[], start: number, end: number) {
  const points: TimelinePoint[] = [];
  let outside = 0;
  for (const e of events) {
    if (e.category !== "indication") continue;
    const t = utcMs(e.start_ts);
    if (t === null) continue;
    if (!(end > start) || t < start || t > end) { outside += 1; continue; }
    const kind = indicationKind(e.indicator);
    points.push({ id: e.event_id, at: t, x: (t - start) / (end - start), kind, student: e.student?.name ?? "Siswa tidak dikenal", label: e.label ?? kindLabel(kind), time: clockLabelWib(t) });
  }
  points.sort((a, b) => a.at - b.at);
  return { points, outside, start, end, startLabel: clockLabelWib(start), endLabel: clockLabelWib(end) };
}

/** Indications of the session grouped per time slot (stacked columns on Monitoring). The slot is 5, 10, 15, 30 or 60
 *  minutes, the smallest that keeps at most `maxBins` columns, counted from the scheduled start. */
export type SessionBin = { start: number; end: number; label: string; range: string; total: number; byKind: Partial<Record<KindKey, number>>; students: string[] };
export function sessionBins(data: { points: TimelinePoint[]; start: number; end: number }, maxBins = 24, fixedStep?: number): { stepMin: number; bins: SessionBin[] } {
  if (!(data.end > data.start)) return { stepMin: 0, bins: [] };
  const span = (data.end - data.start) / 60_000;
  const stepMin = fixedStep ?? [5, 10, 15, 30, 60].find((m) => Math.ceil(span / m) <= maxBins) ?? Math.ceil(span / maxBins);
  const n = Math.max(1, Math.ceil(span / stepMin));
  const clock = (t: number) => clockLabelWib(t).replace(" WIB", "");
  const bins: SessionBin[] = Array.from({ length: n }, (_, i) => {
    const start = data.start + i * stepMin * 60_000, end = Math.min(data.end, start + stepMin * 60_000);
    return { start, end, label: clock(start), range: `${clock(start)}–${clock(end)} WIB`, total: 0, byKind: {}, students: [] };
  });
  for (const p of data.points) {
    const b = bins[Math.min(n - 1, Math.max(0, Math.floor((p.at - data.start) / (stepMin * 60_000))))];
    b.total += 1; b.byKind[p.kind] = (b.byKind[p.kind] ?? 0) + 1;
    if (!b.students.includes(p.student)) b.students.push(p.student);
  }
  return { stepMin, bins };
}

/** Axis ticks every 15, 30, 60 or 120 minutes, whichever keeps about `maxTicks` labels. */
export function timelineTicks(start: number, end: number, maxTicks = 6): { x: number; label: string }[] {
  if (!(end > start)) return [];
  const span = (end - start) / 60_000;
  const step = [15, 30, 60, 120, 240].find((m) => span / m <= maxTicks) ?? 240;
  const first = Math.ceil((start + WIB_OFFSET_MS) / (step * 60_000)) * step * 60_000 - WIB_OFFSET_MS;
  const out = [];
  for (let t = first; t <= end; t += step * 60_000) out.push({ x: (t - start) / (end - start), label: clockLabelWib(t).replace(" WIB", "") });
  return out;
}

// ---------------------------------------------------------------- monitoring: student status (mutually exclusive)
export type MonitorKey = "online" | "perhatian" | "tidak_terbaca" | "offline";
export const needsAttention = (s: StudentRow) => (s.counts?.unreviewed ?? 0) > 0 || s.ai?.state === "indication";

/** Every student in exactly one part: Offline > Perlu perhatian > Tidak dapat dianalisis > Online, so the parts add up. */
export function monitorStatus(rows: StudentRow[]) {
  const counts: Record<MonitorKey, number> = { online: 0, perhatian: 0, tidak_terbaca: 0, offline: 0 };
  for (const s of rows) {
    if (!s.presence?.online) counts.offline += 1;
    else if (needsAttention(s)) counts.perhatian += 1;
    else if (s.ai?.state === "cannot_analyze") counts.tidak_terbaca += 1;
    else counts.online += 1;
  }
  const segments: Segment<MonitorKey>[] = [
    { key: "online", label: "Online", value: counts.online }, { key: "perhatian", label: "Perlu perhatian", value: counts.perhatian },
    { key: "tidak_terbaca", label: "Tidak dapat dianalisis", value: counts.tidak_terbaca }, { key: "offline", label: "Offline", value: counts.offline },
  ];
  return { segments, total: rows.length };
}

// ---------------------------------------------------------------- indications page
/** Funnel: detections -> cases -> not yet reviewed -> needs follow-up (all from GET /api/cases). */
export function reviewFunnel(totalEvents: number, cases: CaseSummary[]): Segment[] {
  return [
    { key: "deteksi", label: "Deteksi AI", value: totalEvents },
    { key: "kasus", label: "Kasus", value: cases.length },
    { key: "belum", label: "Belum ditinjau", value: cases.filter((c) => caseStatus(c) === "belum").length },
    { key: "lanjut", label: "Perlu tindak lanjut", value: cases.filter((c) => caseStatus(c) === "lanjut").length },
  ];
}

export type StatusKey = CaseStatusKey | "campuran";
export const STATUS_PARTS: { key: StatusKey; label: string }[] = [...ORDER.map((key) => ({ key, label: CASE_STATUS_LABEL[key] })), { key: "campuran", label: "Campuran" }];

/** Cases per kind of indication, each split per review status. "Kamera/mikrofon dimatikan" and "Lainnya" only when they have cases. */
export function casesByKind(cases: CaseSummary[]) {
  const rows = KINDS.map((k) => ({ key: k.key, label: k.label, parts: STATUS_PARTS.map((p) => ({ ...p, value: 0 })), total: 0 }));
  for (const c of cases) {
    const row = rows.find((r) => r.key === indicationKind(c.indicator))!;
    row.parts.find((p) => p.key === caseStatus(c))!.value += 1;
    row.total += 1;
  }
  return rows.filter((r) => (r.key !== "lain" && r.key !== "perangkat") || r.total > 0);
}

// ---------------------------------------------------------------- session report
/** Attendance donut: present + absent = enrolled. Unreadable periods are periods, not students, so they are
 *  returned apart and never added to the donut. */
export function attendanceParts(a: { enrolled: number; joined: number; not_joined: number }) {
  const segments: Segment[] = [{ key: "hadir", label: "Hadir", value: a.joined }, { key: "tidak_hadir", label: "Tidak hadir", value: a.not_joined }];
  const sum = sumOf(segments);
  return { segments, total: a.enrolled, mismatch: sum === a.enrolled ? null : `Hadir + tidak hadir (${sum}) tidak sama dengan total peserta dari API (${a.enrolled}).` };
}

/** Review results of the session's indications (events). Unreviewed ones get their own part so the bar adds up. */
export function reportResults(i: { total: number; valid: number; invalid: number; further: number; unreviewed: number }) {
  const segments: Segment[] = [
    { key: "valid", label: "Valid", value: i.valid }, { key: "tidak_valid", label: "Tidak valid", value: i.invalid },
    { key: "lanjut", label: "Perlu tinjauan", value: i.further }, { key: "belum", label: "Belum ditinjau", value: i.unreviewed },
  ];
  const sum = sumOf(segments);
  return { segments, total: i.total, mismatch: sum === i.total ? null : `Jumlah per status (${sum}) tidak sama dengan total indikasi dari API (${i.total}).` };
}

// ---------------------------------------------------------------- Riwayat Sesi: review result per finished session
export type HistoryKey = "valid" | "tidak_valid" | "lanjut" | "belum";
export const HISTORY_PARTS: { key: HistoryKey; label: string }[] = [
  { key: "valid", label: "Valid" }, { key: "tidak_valid", label: "Tidak valid" }, { key: "lanjut", label: "Perlu tinjauan" }, { key: "belum", label: "Belum ditinjau" },
];
export type HistoryRow = { id: number; name: string; date: string; total: number; parts: Record<HistoryKey, number> };
/** One row per finished session (newest first) from GET /api/sessions/{id}/report; totals for the summary line. */
export function historyRows(reports: { exam: { id: number; name: string; date: string; start_time?: string }; indications: { total: number; valid: number; invalid: number; further: number; unreviewed: number } }[]) {
  const rows: HistoryRow[] = reports.map((r) => ({ id: r.exam.id, name: r.exam.name, date: r.exam.date, total: r.indications.total,
    parts: { valid: r.indications.valid, tidak_valid: r.indications.invalid, lanjut: r.indications.further, belum: r.indications.unreviewed } }))
    .sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id);
  const total = rows.reduce((a, r) => a + r.total, 0), open = rows.reduce((a, r) => a + r.parts.belum, 0);
  return { rows, sessions: rows.length, total, reviewedPct: total ? Math.round(((total - open) / total) * 100) : 100, open };
}
