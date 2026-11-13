// Indikasi page: indication kinds, filters (also kept in the URL query) and the summary numbers.
// Computed from API data only (GET /api/cases, GET /api/events). No React, so node:test can check it.
import type { AIEvent, CaseSummary, Decision, Exam } from "./api.ts";
import { caseStatus } from "./chartData.ts";

// ---------------------------------------------------------------- kinds the backend detects (backend/app/schemas.py INDICATORS)
export type JenisKey = "hp" | "orang" | "buku" | "wajah" | "menoleh" | "suara" | "media" | "kamera" | "mikrofon" | "tidak-terbaca";
export type JenisIcon = "phone" | "users" | "book" | "face-off" | "rotate" | "speaker" | "music" | "video-off" | "mic-off" | "camera-off";
export type Jenis = { key: JenisKey; label: string; short: string; icon: JenisIcon; codes: string[]; quality?: true };

/** Only kinds the backend can produce. "Keluar dari layar ujian" is not detected by the backend, so it has no button.
 *  "Tidak dapat dianalisis" is a quality problem (category cannot_analyze), not an indication: it never forms a case. */
export const JENIS: Jenis[] = [
  { key: "hp", label: "HP terlihat", short: "HP", icon: "phone", codes: ["PHONE_VISIBLE"] },
  { key: "orang", label: "Lebih dari satu orang", short: "Orang lain", icon: "users", codes: ["MULTIPLE_PERSONS"] },
  { key: "buku", label: "Buku terlihat", short: "Buku", icon: "book", codes: ["BOOK_VISIBLE", "BOOK_SOUND"] },   // also the paper/page sound
  { key: "wajah", label: "Wajah tidak terlihat", short: "Wajah", icon: "face-off", codes: ["FACE_ABSENT"] },
  { key: "menoleh", label: "Kepala menoleh", short: "Menoleh", icon: "rotate", codes: ["HEAD_TURN", "HEAD_TURN_REPEATED"] },
  { key: "suara", label: "Suara orang lain", short: "Suara", icon: "speaker", codes: ["OTHER_VOICE", "WHISPER", "BISIKAN", "BICARA_MULUT_DIAM"] },
  { key: "media", label: "Suara media", short: "Media", icon: "music", codes: ["MEDIA_SOUND", "MUSIK_MEDIA"] },
  // the student switched the camera / microphone off during monitoring (backend app/device.py): an indication
  { key: "kamera", label: "Kamera dimatikan", short: "Kamera", icon: "video-off", codes: ["CAMERA_OFF"] },
  { key: "mikrofon", label: "Mikrofon dimatikan", short: "Mikrofon", icon: "mic-off", codes: ["MIC_OFF"] },
  { key: "tidak-terbaca", label: "Tidak dapat dianalisis", short: "Tidak terbaca", icon: "camera-off", codes: ["CANNOT_ANALYZE"], quality: true },
];

/** Kind of an indicator code, or null for a code this page does not know (counted under "Semua" only). */
export function jenisOf(indicator: string): JenisKey | null {
  const code = indicator.toUpperCase();
  const hit = JENIS.find((j) => j.codes.includes(code) || (j.key === "hp" && code.startsWith("PHONE")) || (j.key === "buku" && code.startsWith("BOOK")));
  return hit ? hit.key : null;
}

// ---------------------------------------------------------------- review status (same rule as the backend and chartData.caseStatus)
export type StatusKey = "belum" | "valid" | "tidak-valid" | "lanjut" | "campuran";
export const STATUS: { key: StatusKey; label: string }[] = [
  { key: "belum", label: "Belum ditinjau" }, { key: "valid", label: "Valid" }, { key: "tidak-valid", label: "Tidak valid" },
  { key: "lanjut", label: "Perlu tinjauan lanjut" }, { key: "campuran", label: "Campuran" },
];
export function statusOf(c: Pick<CaseSummary, "unreviewed_count" | "review_status">): StatusKey {
  const s = caseStatus(c);
  return s === "tidak_valid" ? "tidak-valid" : s;
}

// ---------------------------------------------------------------- filter <-> URL query (?jenis=hp&status=belum)
export type Filter = { jenis: JenisKey | null; status: StatusKey | null };

export function parseFilter(search: string): Filter {
  const q = new URLSearchParams(search);
  const j = q.get("jenis"), s = q.get("status");
  // "Tidak dapat dianalisis" is not offered on the Indikasi page any more: an old ?jenis=tidak-terbaca link shows all cases.
  return { jenis: JENIS.some((x) => x.key === j && !x.quality) ? (j as JenisKey) : null, status: STATUS.some((x) => x.key === s) ? (s as StatusKey) : null };
}

/** Query string for a filter, keeping other parameters of `search`. "" when nothing is left. */
export function filterQuery(f: Filter, search = ""): string {
  const q = new URLSearchParams(search);
  q.delete("jenis"); q.delete("status");
  if (f.jenis) q.set("jenis", f.jenis);
  if (f.status) q.set("status", f.status);
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function filterCases(cases: CaseSummary[], f: Filter): CaseSummary[] {
  return cases.filter((c) => (!f.jenis || jenisOf(c.indicator) === f.jenis) && (!f.status || statusOf(c) === f.status));
}

/** Number on each kind button: cases of that kind (status filter applied); for "tidak dapat dianalisis" the periods. */
export function jenisCounts(cases: CaseSummary[], cannot: Pick<AIEvent, "category">[], status: StatusKey | null): Record<JenisKey | "semua", number> {
  const out = Object.fromEntries([...JENIS.map((j) => [j.key, 0]), ["semua", 0]]) as Record<JenisKey | "semua", number>;
  for (const c of cases) {
    if (status && statusOf(c) !== status) continue;
    out.semua += 1;
    const k = jenisOf(c.indicator);
    if (k) out[k] += 1;
  }
  out["tidak-terbaca"] = cannot.filter((e) => e.category === "cannot_analyze").length;
  return out;
}

// ---------------------------------------------------------------- KPI: last 7 days
export const DAYS = 7;
const ms = (iso?: string | null) => {
  const s = (iso ?? "").trim().replace(" ", "T");
  const t = Date.parse(/(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(s) ? s : `${s}Z`);
  return Number.isFinite(t) ? t : null;
};
/** ISO time `days` before `now`, for `since=` in GET /api/events. */
export const sinceIso = (now: number, days = DAYS) => new Date(now - days * 86400_000).toISOString();

export type Kpi = { ditinjau: number; deteksi: number; deteksiCapped: boolean; kasusBaru: number; belum: number };

/** cases: already filtered by kind/status. detections: indication events since 7 days (GET /api/events, at most `cap`).
 *  - Kasus ditinjau: fully reviewed cases whose last change (the review) is within 7 days.
 *  - Deteksi baru: detections within 7 days that belong to one of the (filtered) cases, so kind and status filters apply.
 *  - Kasus baru: cases whose first event started within 7 days; Belum ditinjau: those still unreviewed. */
export function kpi7(cases: CaseSummary[], detections: Pick<AIEvent, "event_id" | "start_ts" | "category">[], now: number, cap = 500): Kpi {
  const from = now - DAYS * 86400_000;
  const within = (iso?: string | null) => { const t = ms(iso); return t !== null && t >= from && t <= now + 60_000; };
  const ids = new Set(cases.flatMap((c) => c.event_ids));
  const fresh = cases.filter((c) => within(c.first_start_ts));
  return {
    ditinjau: cases.filter((c) => statusOf(c) !== "belum" && within(c.updated_at)).length,
    deteksi: detections.filter((e) => e.category === "indication" && within(e.start_ts) && ids.has(e.event_id)).length,
    deteksiCapped: detections.length >= cap,
    kasusBaru: fresh.length,
    belum: fresh.filter((c) => statusOf(c) === "belum").length,
  };
}

// ---------------------------------------------------------------- status overview (donut)
/** Cases per status for the donut. `cases` filtered by kind only, so every status stays visible. Sum = cases.length. */
export function statusSummary(cases: CaseSummary[]) {
  const counts = Object.fromEntries(STATUS.map((s) => [s.key, 0])) as Record<StatusKey, number>;
  for (const c of cases) counts[statusOf(c)] += 1;
  return { segments: STATUS.map((s) => ({ key: s.key, label: s.label, value: counts[s.key] })), total: cases.length };
}

// ---------------------------------------------------------------- "tidak dapat dianalisis" per exam
export type UnreadableRow = { examId: number; exam: string; periods: number; seconds: number; students: number; last: string };
/** Periods of category cannot_analyze per exam, most periods first. */
export function unreadableByExam(events: Pick<AIEvent, "category" | "exam_id" | "exam" | "duration_s" | "student_id" | "start_ts">[]): UnreadableRow[] {
  const m = new Map<number, UnreadableRow & { ids: Set<number> }>();
  for (const e of events) {
    if (e.category !== "cannot_analyze") continue;
    const r = m.get(e.exam_id) ?? { examId: e.exam_id, exam: e.exam?.name ?? `Ujian ${e.exam_id}`, periods: 0, seconds: 0, students: 0, last: e.start_ts, ids: new Set<number>() };
    r.periods += 1; r.seconds += e.duration_s ?? 0; r.ids.add(e.student_id);
    if ((ms(e.start_ts) ?? 0) > (ms(r.last) ?? 0)) r.last = e.start_ts;
    m.set(e.exam_id, r);
  }
  return [...m.values()].map(({ ids, ...r }) => ({ ...r, students: ids.size })).sort((a, b) => b.periods - a.periods || a.exam.localeCompare(b.exam));
}

// ---------------------------------------------------------------- 3. recent activity (reviews)
// From GET /api/events (category=indication): each event carries its LAST review (reviewer, decision, time).
// One activity = one reviewer saving one decision for one case (a case review writes a row per event).
// Limits (reported): only the last review per event is in the API, and only the 500 newest events.
export type Activity = { key: string; reviewer: string; decision: Decision; at: string; case: CaseSummary; events: number };
export function activityFeed(cases: CaseSummary[], events: Pick<AIEvent, "event_id" | "last_review">[], max = 50): Activity[] {
  const byEvent = new Map<string, CaseSummary>();
  for (const c of cases) for (const id of c.event_ids) byEvent.set(id, c);
  const m = new Map<string, Activity>();
  for (const e of events) {
    const r = e.last_review, c = byEvent.get(e.event_id);
    if (!r || !c) continue;
    const key = `${c.case_id}|${r.reviewer}|${r.created_at}|${r.decision}`;
    const a = m.get(key) ?? { key, reviewer: r.reviewer, decision: r.decision, at: r.created_at, case: c, events: 0 };
    a.events += 1;
    m.set(key, a);
  }
  return [...m.values()].sort((a, b) => (ms(b.at) ?? 0) - (ms(a.at) ?? 0)).slice(0, max);
}

// ---------------------------------------------------------------- 4. cases per kind (bars) and distribution (table)
export type KindBar = { key: JenisKey; label: string; short: string; icon: JenisIcon; value: number; pct: number };
/** Indication kinds only ("tidak dapat dianalisis" is not an indication). `cases` with the status filter applied. */
export function kindBars(cases: CaseSummary[]): KindBar[] {
  const kinds = JENIS.filter((j) => !j.quality);
  const n = Object.fromEntries(kinds.map((j) => [j.key, 0])) as Record<JenisKey, number>;
  for (const c of cases) { const k = jenisOf(c.indicator); if (k && k in n) n[k] += 1; }
  const total = kinds.reduce((a, j) => a + n[j.key], 0);
  return kinds.map((j) => ({ key: j.key, label: j.label, short: j.short, icon: j.icon, value: n[j.key], pct: total ? Math.round((n[j.key] / total) * 100) : 0 }));
}
/** Y axis: 0 and up to 4 more whole-number ticks, the top one >= max. */
export function axisTicks(max: number): number[] {
  if (max <= 0) return [0, 1];
  const raw = max / 4, mag = 10 ** Math.floor(Math.log10(raw)), step = [1, 2, 5, 10].map((f) => Math.max(1, f * mag)).find((s) => s >= raw)!;
  const ticks: number[] = [];
  for (let v = 0; v < max + step; v += step) ticks.push(v);
  return ticks;
}

// ---------------------------------------------------------------- 5. supervisor workload and review progress per exam
export type Load = { id: number | null; name: string; cases: number; belum: number; pct: number };
/** Cases per supervisor of the exam (GET /api/exams gives the supervisor). Share of all given cases. */
export function supervisorLoad(cases: CaseSummary[], exams: Pick<Exam, "id" | "supervisor">[]): Load[] {
  const sup = new Map(exams.map((e) => [e.id, e.supervisor]));
  const m = new Map<string, Load>();
  for (const c of cases) {
    const s = sup.get(c.exam_id) ?? null;
    const k = s ? `u${s.id}` : "none";
    const r = m.get(k) ?? { id: s?.id ?? null, name: s?.name ?? "Belum ada pengawas", cases: 0, belum: 0, pct: 0 };
    r.cases += 1; if (statusOf(c) === "belum") r.belum += 1;
    m.set(k, r);
  }
  const total = cases.length;
  return [...m.values()].map((r) => ({ ...r, pct: total ? Math.round((r.cases / total) * 100) : 0 })).sort((a, b) => b.cases - a.cases || a.name.localeCompare(b.name));
}
export type Progress = { examId: number; exam: string; total: number; reviewed: number; pct: number };
/** Reviewed cases (any decision, not "belum") out of all cases per exam; least progress first. */
export function examProgress(cases: CaseSummary[]): Progress[] {
  const m = new Map<number, Progress>();
  for (const c of cases) {
    const r = m.get(c.exam_id) ?? { examId: c.exam_id, exam: c.exam?.name ?? `Ujian ${c.exam_id}`, total: 0, reviewed: 0, pct: 0 };
    r.total += 1; if (statusOf(c) !== "belum") r.reviewed += 1;
    m.set(c.exam_id, r);
  }
  return [...m.values()].map((r) => ({ ...r, pct: Math.round((r.reviewed / r.total) * 100) })).sort((a, b) => a.pct - b.pct || a.exam.localeCompare(b.exam));
}

// ---------------------------------------------------------------- drawer: students behind a click
export type DrawerSource = { jenis: JenisKey | null; status: StatusKey | null; kinds?: JenisKey[]; label?: string };
/** Title of the drawer: "HP terlihat · Belum ditinjau", "Semua indikasi". */
export function drawerTitle(s: DrawerSource): string {
  const parts = [s.label ?? (s.jenis ? JENIS.find((j) => j.key === s.jenis)!.label : null), s.status ? STATUS.find((x) => x.key === s.status)!.label : null].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Semua indikasi";
}
/** Cases for the drawer, newest activity first. */
export function drawerCases(cases: CaseSummary[], s: DrawerSource): CaseSummary[] {
  const list = s.kinds ? filterCases(cases, { jenis: null, status: s.status }).filter((c) => { const k = jenisOf(c.indicator); return k !== null && s.kinds!.includes(k); })
    : filterCases(cases, s);
  return list.sort((a, b) => (ms(b.last_start_ts) ?? 0) - (ms(a.last_start_ts) ?? 0));
}

// ---------------------------------------------------------------- donuts: kinds and supervisor load
// Categorical colours in a fixed order (dataviz reference palette; validated: lightness band, chroma floor, adjacent CVD
// separation and normal-vision floor pass). A palette has at most 8 distinguishable hues, so the donut joins
// "Kamera dimatikan" and "Mikrofon dimatikan" into one part; the filter buttons and bars keep them apart.
export const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
export const OTHER_COLOR = "#9aa2ac";
export type KindSlice = { key: string; label: string; kinds: JenisKey[]; color: string; value: number; icon: JenisIcon };
const SLICES: Omit<KindSlice, "value">[] = [
  { key: "hp", label: "HP terlihat", kinds: ["hp"], color: PALETTE[0], icon: "phone" },
  { key: "orang", label: "Lebih dari satu orang", kinds: ["orang"], color: PALETTE[1], icon: "users" },
  { key: "buku", label: "Buku terlihat", kinds: ["buku"], color: PALETTE[2], icon: "book" },
  { key: "wajah", label: "Wajah tidak terlihat", kinds: ["wajah"], color: PALETTE[3], icon: "face-off" },
  { key: "menoleh", label: "Kepala menoleh", kinds: ["menoleh"], color: PALETTE[4], icon: "rotate" },
  { key: "suara", label: "Suara orang lain", kinds: ["suara"], color: PALETTE[5], icon: "speaker" },
  { key: "media", label: "Suara media", kinds: ["media"], color: PALETTE[6], icon: "music" },
  { key: "perangkat", label: "Kamera/mikrofon dimatikan", kinds: ["kamera", "mikrofon"], color: PALETTE[7], icon: "video-off" },
];
/** Cases per kind for the donut (fixed order and colour per kind; status filter already applied to `cases`). */
export function kindSlices(cases: CaseSummary[]): KindSlice[] {
  return SLICES.map((s) => ({ ...s, value: cases.filter((c) => { const k = jenisOf(c.indicator); return k !== null && s.kinds.includes(k); }).length }));
}
export type LoadSlice = { key: string; label: string; color: string; value: number; belum: number; pct: number };
/** Supervisor load for the donut. Colour follows the supervisor (by id), not the rank; more than 7 supervisors:
 *  the smallest are joined into "Lainnya". */
export function loadSlices(rows: Load[]): LoadSlice[] {
  const byId = [...rows].filter((r) => r.id !== null).sort((a, b) => a.id! - b.id!);
  const colorOf = new Map(byId.map((r, i) => [r.id, i < 7 ? PALETTE[i] : OTHER_COLOR]));
  const sorted = [...rows].sort((a, b) => b.cases - a.cases);
  const keep = sorted.length > 8 ? sorted.slice(0, 7) : sorted, rest = sorted.length > 8 ? sorted.slice(7) : [];
  const out: LoadSlice[] = keep.map((r) => ({ key: r.id === null ? "none" : String(r.id), label: r.name, color: r.id === null ? OTHER_COLOR : colorOf.get(r.id)!, value: r.cases, belum: r.belum, pct: r.pct }));
  if (rest.length) out.push({ key: "lain", label: `Lainnya (${rest.length} pengawas)`, color: OTHER_COLOR, value: rest.reduce((a, r) => a + r.cases, 0),
    belum: rest.reduce((a, r) => a + r.belum, 0), pct: rest.reduce((a, r) => a + r.pct, 0) });
  return out;
}
