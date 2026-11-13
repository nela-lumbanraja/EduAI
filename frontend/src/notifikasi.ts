// Notification panel and story viewer: grouping, filters, time groups, evidence ring and story navigation.
// Computed from API data (GET /api/cases, GET /api/events?category=cannot_analyze, GET /api/cases/{id}). No React.
//
// Read, dismissed ("Abaikan") and evidence-seen state comes from the server per account (GET /api/notifications/state,
// pengawas of the exam and admin only); nothing is kept in the browser. Student photos do not exist in the API:
// rows show initials.
import type { AIEvent, CaseSummary, NotifState } from "./api.ts";
import { caseStatus } from "./chartData.ts";
import { jenisOf, type JenisKey } from "./indikasi.ts";

const WIB_MS = 7 * 3600_000;
const DAY = 86400_000;
export const ms = (iso?: string | null): number => {
  const s = (iso ?? "").trim().replace(" ", "T");
  const t = Date.parse(/(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(s) ? s : `${s}Z`);
  return Number.isFinite(t) ? t : 0;
};

// ---------------------------------------------------------------- filters
export type NotifFilter = "semua" | "belum" | "hp-buku" | "orang" | "wajah-menoleh" | "suara" | "perangkat" | "tidak-terbaca";
export const NOTIF_FILTERS: { key: NotifFilter; label: string }[] = [
  { key: "semua", label: "Semua" }, { key: "belum", label: "Belum ditinjau" }, { key: "hp-buku", label: "HP/buku" },
  { key: "orang", label: "Orang lain" }, { key: "wajah-menoleh", label: "Wajah/menoleh" }, { key: "suara", label: "Suara" },
  { key: "perangkat", label: "Kamera/mikrofon mati" },
  { key: "tidak-terbaca", label: "Tidak dapat dianalisis" },
];
const FILTER_KINDS: Partial<Record<NotifFilter, JenisKey[]>> = {
  "hp-buku": ["hp", "buku"], orang: ["orang"], "wajah-menoleh": ["wajah", "menoleh"], suara: ["suara", "media"], perangkat: ["kamera", "mikrofon"],
};

// ---------------------------------------------------------------- rows: one per student and exam
export type NotifRow = {
  key: string; kind: "kasus" | "tidak-terbaca";
  student: { id: number; name: string }; exam: { id: number; name: string };
  cases: CaseSummary[]; periods: number;          // periods: "tidak dapat dianalisis" rows only
  labels: string[]; latest: number; unreviewed: number; evidence: number;
};

const label = (c: CaseSummary) => c.label ?? c.indicator;

/** Indication cases grouped per student + exam (newest first), plus one row per student + exam with
 *  "tidak dapat dianalisis" periods (a quality problem, not an indication: no review buttons). */
export function buildRows(cases: CaseSummary[], cannot: Pick<AIEvent, "category" | "exam_id" | "student_id" | "student" | "exam" | "start_ts">[] = []): NotifRow[] {
  const m = new Map<string, NotifRow>();
  for (const c of cases) {
    const key = `k:${c.exam_id}:${c.student_id}`;
    const r = m.get(key) ?? { key, kind: "kasus" as const, student: { id: c.student_id, name: c.student?.name ?? "Siswa" }, exam: { id: c.exam_id, name: c.exam?.name ?? `Ujian ${c.exam_id}` },
      cases: [], periods: 0, labels: [], latest: 0, unreviewed: 0, evidence: 0 };
    r.cases.push(c);
    if (!r.labels.includes(label(c))) r.labels.push(label(c));
    r.latest = Math.max(r.latest, ms(c.last_start_ts));
    if (caseStatus(c) === "belum") r.unreviewed += 1;
    r.evidence += c.evidence_count ?? 0;
    m.set(key, r);
  }
  for (const e of cannot) {
    if (e.category !== "cannot_analyze") continue;
    const key = `t:${e.exam_id}:${e.student_id}`;
    const r = m.get(key) ?? { key, kind: "tidak-terbaca" as const, student: { id: e.student_id, name: e.student?.name ?? "Siswa" }, exam: { id: e.exam_id, name: e.exam?.name ?? `Ujian ${e.exam_id}` },
      cases: [], periods: 0, labels: ["Tidak dapat dianalisis"], latest: 0, unreviewed: 0, evidence: 0 };
    r.periods += 1; r.latest = Math.max(r.latest, ms(e.start_ts));
    m.set(key, r);
  }
  return [...m.values()].sort((a, b) => b.latest - a.latest || a.student.name.localeCompare(b.student.name));
}

/** Rows for a filter. Kind filters keep only the matching cases of each row (and drop rows left empty). */
export function filterRows(rows: NotifRow[], f: NotifFilter): NotifRow[] {
  if (f === "semua") return rows;
  if (f === "tidak-terbaca") return rows.filter((r) => r.kind === "tidak-terbaca");
  const kase = rows.filter((r) => r.kind === "kasus");
  if (f === "belum") return kase.filter((r) => r.unreviewed > 0);
  const kinds = FILTER_KINDS[f] ?? [];
  return kase.map((r) => {
    const cases = r.cases.filter((c) => { const k = jenisOf(c.indicator); return k !== null && kinds.includes(k); });
    return cases.length === r.cases.length ? r : { ...r, cases, labels: [...new Set(cases.map(label))], unreviewed: cases.filter((c) => caseStatus(c) === "belum").length,
      evidence: cases.reduce((a, c) => a + (c.evidence_count ?? 0), 0), latest: Math.max(...cases.map((c) => ms(c.last_start_ts)), 0) };
  }).filter((r) => r.cases.length > 0);
}

/** "Alya Putri – 3 indikasi: Lebih dari satu orang, Suara orang lain" (the panel clamps it to 2 lines). */
export function rowText(r: NotifRow): string {
  if (r.kind === "tidak-terbaca") return `${r.student.name} – tidak dapat dianalisis: ${r.periods} periode (kualitas video, bukan indikasi)`;
  return `${r.student.name} – ${r.cases.length} indikasi: ${r.labels.join(", ")}`;
}

// ---------------------------------------------------------------- time groups (WIB calendar)
export type TimeGroup = "Hari ini" | "Minggu ini" | "Bulan ini" | "Sebelumnya";
export const TIME_GROUPS: TimeGroup[] = ["Hari ini", "Minggu ini", "Bulan ini", "Sebelumnya"];

/** Today (WIB date), this week (Monday–Sunday, WIB), this month (WIB), earlier. */
export function timeGroup(t: number, now: number): TimeGroup {
  const day = (x: number) => Math.floor((x + WIB_MS) / DAY);
  const d = new Date(t + WIB_MS), n = new Date(now + WIB_MS);
  if (day(t) === day(now)) return "Hari ini";
  const monday = day(now) - ((n.getUTCDay() + 6) % 7);
  if (day(t) >= monday && day(t) < day(now)) return "Minggu ini";
  if (d.getUTCFullYear() === n.getUTCFullYear() && d.getUTCMonth() === n.getUTCMonth()) return "Bulan ini";
  return "Sebelumnya";
}

export function groupByTime(rows: NotifRow[], now: number): { group: TimeGroup; rows: NotifRow[] }[] {
  return TIME_GROUPS.map((group) => ({ group, rows: rows.filter((r) => timeGroup(r.latest, now) === group) })).filter((g) => g.rows.length);
}

// ---------------------------------------------------------------- read / dismissed / evidence seen (server state)
// A row holds the cases of one student in one exam. The server resets read/dismissed of a case when it gets a new
// event, so a row is unread when any of its cases is unread, and hidden only while all its cases are dismissed.
// "Tidak dapat dianalisis" rows are not cases: no read state, no Abaikan.
const kasusOnly = (r: NotifRow) => r.kind === "kasus" && r.cases.length > 0;
export const isUnread = (r: NotifRow, st: NotifState) => kasusOnly(r) && r.cases.some((c) => !st[c.case_id]?.read);
export const isDismissed = (r: NotifRow, st: NotifState) => kasusOnly(r) && r.cases.every((c) => st[c.case_id]?.dismissed);
export const visibleRows = (rows: NotifRow[], st: NotifState) => rows.filter((r) => !isDismissed(r, st));
/** Cases of the dismissed rows (for "Tampilkan lagi"). */
export const dismissedCaseIds = (rows: NotifRow[], st: NotifState) => rows.filter((r) => isDismissed(r, st)).flatMap((r) => r.cases.map((c) => c.case_id));
/** Optimistic local update after a PUT/DELETE succeeded or while it is in flight. */
export function withMark(st: NotifState, caseIds: string[], field: "read" | "dismissed", value: boolean): NotifState {
  const n = { ...st };
  const empty = { read: false, dismissed: false, evidence_seen: false };
  for (const id of caseIds) n[id] = { ...(n[id] ?? empty), [field]: value };
  return n;
}
/** Keys the earlier version kept in localStorage; removed so nothing stays in the browser. */
export const LEGACY_KEYS = (userId: number) => [`eduai_notif_read_${userId}`, `eduai_notif_hidden_${userId}`, `eduai_evidence_viewed_${userId}`];

// ---------------------------------------------------------------- evidence ring
export type Ring = "baru" | "dilihat" | "tidak-ada";
/** Gold ring: evidence the user may open and has not viewed yet (own audit log); grey: all viewed; none: no evidence or not allowed. */
export function ringOf(r: NotifRow, st: NotifState, canOpen: boolean): Ring {
  if (!canOpen || r.kind !== "kasus") return "tidak-ada";
  const withEv = r.cases.filter((c) => (c.evidence_count ?? 0) > 0);
  if (!withEv.length) return "tidak-ada";
  return withEv.every((c) => st[c.case_id]?.evidence_seen) ? "dilihat" : "baru";
}

// ---------------------------------------------------------------- story: one segment per event with evidence
export type Segment = { evidenceId: string; eventId: string; caseId: string; indicator: string; label: string; start: string; score: number | null };

export function storySegments(details: { caseId: string; events: Pick<AIEvent, "event_id" | "evidence_id" | "indicator" | "label" | "start_ts" | "score">[] }[]): Segment[] {
  return details.flatMap((d) => d.events.filter((e) => e.evidence_id).map((e) => ({ evidenceId: e.evidence_id!, eventId: e.event_id, caseId: d.caseId,
    indicator: e.indicator, label: e.label ?? e.indicator, start: e.start_ts, score: e.score })))
    .sort((a, b) => ms(a.start) - ms(b.start));
}

export type StoryPos = { seg: number; frame: number; done: boolean };
export const SLIDE_MS = 4000;

/** Next image: next frame of the same evidence, then the first frame of the next one; after the last: done. */
export function nextPos(p: StoryPos, frames: number[]): StoryPos {
  const n = Math.max(1, frames[p.seg] ?? 1);
  if (p.frame + 1 < n) return { ...p, frame: p.frame + 1 };
  if (p.seg + 1 < frames.length) return { seg: p.seg + 1, frame: 0, done: false };
  return { ...p, done: true };
}
/** Previous image: previous frame, else the last frame of the previous evidence; stays at the very first. */
export function prevPos(p: StoryPos, frames: number[]): StoryPos {
  if (p.frame > 0) return { ...p, frame: p.frame - 1, done: false };
  if (p.seg > 0) return { seg: p.seg - 1, frame: Math.max(1, frames[p.seg - 1] ?? 1) - 1, done: false };
  return { seg: 0, frame: 0, done: false };
}
/** Fill (0..1) of each progress segment: past = 1, future = 0, current = share of its frames shown. */
export function segmentFill(p: StoryPos, frames: number[], elapsed: number): number[] {
  return frames.map((f, i) => {
    if (i < p.seg) return 1;
    if (i > p.seg) return 0;
    if (p.done) return 1;
    const n = Math.max(1, f);
    return Math.min(1, (p.frame + Math.min(1, elapsed / SLIDE_MS)) / n);
  });
}
