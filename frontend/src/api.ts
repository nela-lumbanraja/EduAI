// Typed client for the EduAI backend (FastAPI). No secrets live here: the browser only
// holds the user's own session token (sessionStorage, cleared when the tab closes).

import type { JitsiServer } from "./jitsi";
export type RoleCode = "siswa" | "pengawas" | "penyelenggara" | "admin" | "sekolah";
export type User = { id: number; email: string; name: string; role: RoleCode; role_label: string; nis?: string | null; class_name?: string | null };
export type ExamStatus = "Draft" | "Terjadwal" | "Sedang Berlangsung" | "Selesai";
export type Exam = {
  id: number; name: string; description: string; subject: string; class_name: string; date: string; start_time: string;
  duration_min: number; status: ExamStatus; monitoring_active: boolean; analysis_source: AnalysisSource | null;
  monitoring_started_at: string | null; supervisor: { id: number; name: string } | null; student_count: number;
  indications?: { total: number; unreviewed: number }; online?: number; consent?: boolean; audio_consent?: boolean;
};
// not_started / no_data / ai_offline are dashboard states set by the backend (see GET /exams/{id}/students):
// AI monitoring off, on but no analysis result yet, on but the analysis itself is down.
export type AnalysisState = "not_started" | "no_data" | "ai_offline" | "warming_up" | "normal" | "indication" | "cannot_analyze" | "model_unavailable";
export type AnalysisSource = "browser" | "livekit" | "jitsi";
export type StudentRow = {
  id: number; name: string; nis: string | null; class_name: string | null; consent?: boolean;
  presence?: { joined: boolean; online: boolean; joined_at: string | null; last_seen: string | null; camera_on: boolean | null; mic_on: boolean | null; connection: string | null; rtt_ms: number | null; jitsi?: "connected" | "disconnected" | null };
  ai?: { state: AnalysisState | null; last_state: AnalysisState | null; frame_status: string | null; reason: string | null; face_count: number | null; latency_ms: number | null; updated_at: string | null; source: string | null };
  counts?: { indications: number; unreviewed: number; session_indications?: number; open_indications: number; open_cannot_analyze: number };
  last_indication?: { label: string | null; indicator: string; start_ts: string; end_ts?: string | null; status?: "open" | "closed"; current_session?: boolean } | null;
  audio?: { consented: boolean; active: boolean; reason?: AudioReason | null };
};
export type Decision = "Valid" | "Tidak Valid" | "Perlu Tinjauan Lanjut";
export type Review = { id?: number; decision: Decision; note: string; created_at: string; reviewer: string; reviewer_role?: string };
export type AIEvent = {
  event_id: string; exam_id: number; student_id: number; indicator: string; category: "indication" | "cannot_analyze";
  status: "open" | "closed"; start_ts: string; end_ts: string | null; score: number | null; reason: string; label: string | null;
  evidence_id: string | null; model_version: string; config_version: string; schema_version: string; source: string;
  review_status: Decision | null; created_at: string; updated_at: string; duration_s: number | null;
  student: { id: number; name: string; nis: string | null; class_name: string | null } | null;
  exam: { id: number; name: string } | null; last_review: Review | null; reviews?: Review[];
};
export type EvidenceMeta = { evidence_id: string; event_id: string; exam_id: number; student_id: number; frame_count: number; frame_ts: number[]; key_index: number; created_at: string; expires_at: string; encrypted: boolean };
export type JoinInfo = {
  exam: Exam; identity: string; livekit: { url: string; room: string; token: string } | null; livekit_reason: string | null;
  monitoring: MonitoringInfo;
};
export type MonitoringInfo = {
  active: boolean; source: AnalysisSource | null; jitsi: (JitsiServer & { room: string }) | null; upload_fps: number; max_width: number; jpeg_quality: number;
  // optional speech-sound analysis in the student's browser (YAMNet); only scores are sent
  audio?: { available: boolean; consented: boolean; reason?: AudioReason | null; model_url: string; interval_ms: number };
};
export type MonitoringState = {
  active: boolean; source: AnalysisSource | null; started_at: string | null; ai: { available: boolean; reason: string };
  worker: { process_running: boolean; last_heartbeat: string | null; alive: boolean; students: number }; livekit_configured: boolean;
};
export type TimelineItem = { ts: string; kind: string; title: string; event_id?: string; status?: string; review_status?: string | null; reason?: string; note?: string; end_ts?: string | null; evidence_id?: string | null; time_text?: string };
export type ReportSummary = { total: number; valid: number; invalid: number; further: number; unreviewed: number; cannot_analyze: number; cannot_analyze_s: number };
export type ReportEvent = AIEvent & { evidence: { state: "available" | "deleted" | "none"; url: string | null } };
export type Report = {
  exam: Exam; attendance: { enrolled: number; joined: number; not_joined: number }; absent: string[];
  indications: ReportSummary; events: ReportEvent[];
  final: { finalized_at: string; finalized_by: string } | null; can_edit: boolean; can_view_evidence: boolean;
  ai_notice: string; retention_text: string; restricted_text: string; frame_retention_hours: number;
  activity: { ts: string; user_name: string; role: string; action: string; target: string; status: string }[];
};
export type AuditRow = { id: number; ts: string; user_id: number | null; user_name: string; role: string; action: string; target: string; status: string };
export type Dashboard = { exams: Exam[]; summary?: { active_sessions: number; students_online: number; unreviewed: number; valid: number; further: number; cases_total?: number; cases_unreviewed?: number; detections_total?: number }; recent_indications?: AIEvent[]; recent_cases?: CaseSummary[] };
// A case = repeated indication events of one student, one exam and one indicator (see backend app/cases.py).
export type CaseSummary = {
  case_id: string; exam_id: number; student_id: number; indicator: string; label: string | null;
  event_count: number; event_ids: string[]; first_event_id: string; first_start_ts: string; last_start_ts: string;
  last_end_ts: string | null; status: "open" | "closed"; total_duration_s: number; max_score: number | null;
  // distinct qualifying episodes (overlapping events = one) and the configured supervisor rule
  episode_count?: number; episodes?: CaseEpisode[]; rule?: CaseRule;
  evidence_count: number; latest_evidence_id: string | null;
  review_status: Decision | "Campuran" | null; review_counts: Record<string, number>; unreviewed_count: number; updated_at: string;
  student: AIEvent["student"]; exam: AIEvent["exam"];
};
export type CaseEpisode = { start_ts: string; end_ts: string | null; event_ids: string[]; evidence_id: string | null; duration_s: number };
export type CaseRule = { min_count: number; window_s: number | null; met: boolean; met_at: string | null; max_in_window: number };
// Consolidated exam summary (backend app/summary.py): one per exam, 10 min before the end or final.
export type SummaryIndication = {
  indicator: string; label: string | null; case_id: string; occurrences: number; events: number;
  first_ts: string; last_ts: string; last_end_ts: string | null; evidence_count: number; unreviewed: number;
  episodes: { start_ts: string; end_ts: string | null; evidence_id: string | null }[]; rule: CaseRule;
};
export type SummaryStudent = {
  student_id: number; name: string; nis: string | null; analysis: "analysed" | "no_data";
  cannot_analyze: { periods: number; total_s: number }; indications: SummaryIndication[]; rules_met: number;
};
export type ExamSummary = {
  exam_id: number; kind: "pre_end" | "final" | null; preview?: boolean; created_at: string | null;
  scheduled_end: string | null; scheduled_at?: string | null;
  summary: { exam_id: number; exam_name: string; generated_at: string; students: SummaryStudent[];
    unsupported: { behavior: string; reason: string; rule: string }[]; note: string };
};
export type CaseList = { server_time: string; gap_s: number; total_events: number; cases: CaseSummary[] };
export type CaseDetail = { server_time: string; gap_s: number; case: CaseSummary; events: AIEvent[]; reviewed_event_ids?: string[] };
export type Health = { status: string; time: string; ai: { available: boolean; reason: string }; livekit: { configured: boolean }; analysis_source: string };
export type AIHealth = {
  available: boolean; reason: string; config_version: string | null; models: Record<string, { loaded: boolean; exists: boolean; reason: string; file: string }>;
  active_analyzers: number; max_concurrent: number; evidence_retention_hours: number; evidence_encrypted: boolean;
  evidence_hold_days: number; report_frame_retention_hours: number;
};
export type UserRow = User & { active: boolean; created_at: string };

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
/** Absolute URL for a public backend file (e.g. the YAMNet model). */
export const assetUrl = (path: string) => `${BASE}${path}`;
const TOKEN_KEY = "eduai_token";
const USER_KEY = "eduai_user";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

export const session = {
  token(): string | null { try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; } },
  user(): User | null { try { const raw = sessionStorage.getItem(USER_KEY); return raw ? JSON.parse(raw) as User : null; } catch { return null; } },
  set(token: string, user: User) { try { sessionStorage.setItem(TOKEN_KEY, token); sessionStorage.setItem(USER_KEY, JSON.stringify(user)); } catch { /* private mode */ } },
  clear() { try { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(USER_KEY); } catch { /* ignore */ } },
};

let onUnauthorized: () => void = () => undefined;
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

async function request<T>(method: string, path: string, body?: unknown, opts: { raw?: boolean; form?: FormData; signal?: AbortSignal } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = session.token();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (opts.form) payload = opts.form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body: payload, signal: opts.signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Server EduAI tidak dapat dihubungi. Periksa koneksi atau pastikan backend berjalan.");
  }
  if (res.status === 401 && token) { session.clear(); onUnauthorized(); }
  if (!res.ok) {
    let msg = `Permintaan gagal (HTTP ${res.status}).`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = "Data yang dikirim tidak valid: " + j.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch { /* not JSON */ }
    throw new ApiError(res.status, msg);
  }
  if (opts.raw) return res as unknown as T;
  return (res.status === 204 ? undefined : await res.json()) as T;
}

const qs = (o: Record<string, string | number | undefined | null>) => {
  const p = Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return p.length ? `?${p.join("&")}` : "";
};

export const api = {
  health: () => request<Health>("GET", "/api/health"),
  aiHealth: () => request<AIHealth>("GET", "/api/ai/health"),
  login: (email: string, password: string) => request<{ token: string; user: User }>("POST", "/api/auth/login", { email, password }),
  register: (name: string, email: string, password: string) => request<{ token: string; user: User }>("POST", "/api/auth/register", { name, email, password }),
  users: (role?: RoleCode) => request<UserRow[]>("GET", `/api/users${qs({ role })}`),
  dashboard: () => request<Dashboard>("GET", "/api/dashboard"),
  exams: () => request<Exam[]>("GET", "/api/exams"),
  exam: (id: number) => request<Exam>("GET", `/api/exams/${id}`),
  createExam: (body: { name: string; description: string; subject?: string; class_name?: string; date: string; start_time: string; duration_min: number; status: ExamStatus; supervisor_id: number; student_ids: number[] }) => request<Exam>("POST", "/api/exams", body),
  students: (examId: number) => request<StudentRow[]>("GET", `/api/exams/${examId}/students`),
  timeline: (examId: number, studentId: number) => request<TimelineItem[]>("GET", `/api/exams/${examId}/students/${studentId}/timeline`),
  consent: (examId: number, audio = false) => request<{ ok: boolean; audio: boolean }>("POST", `/api/exams/${examId}/consent`, { accepted: true, notice_version: "2026-10-v2", audio }),
  audioScores: (examId: number, s: { speech: number; whisper: number; media: number }) => request<{ accepted: boolean; reason?: string }>("POST", `/api/exams/${examId}/audio`, s),
  join: (examId: number) => request<JoinInfo>("POST", `/api/exams/${examId}/join`),
  sessionState: (examId: number) => request<{ status: ExamStatus; monitoring: MonitoringInfo }>("GET", `/api/exams/${examId}/session-state`),
  presence: (examId: number, p: { camera_on: boolean; mic_on: boolean; connection: "baik" | "lemah" | "terputus"; rtt_ms?: number | null; jitsi?: "connected" | "disconnected" | null }) => request<{ ok: boolean }>("POST", `/api/exams/${examId}/presence`, p),
  leave: (examId: number) => request<{ ok: boolean }>("POST", `/api/exams/${examId}/leave`),
  uploadFrame: (examId: number, blob: Blob, signal?: AbortSignal) => { const f = new FormData(); f.append("frame", blob, "frame.jpg"); return request<{ accepted: boolean; reason?: string }>("POST", `/api/exams/${examId}/frames`, undefined, { form: f, signal }); },
  jitsiConfig: () => request<JitsiServer>("GET", "/api/jitsi/config"),
  startMonitoring: (examId: number, source?: AnalysisSource) => request<{ active: boolean; source: AnalysisSource; note: string | null }>("POST", `/api/exams/${examId}/monitoring/start`, { source: source ?? null }),
  stopMonitoring: (examId: number) => request<{ active: boolean }>("POST", `/api/exams/${examId}/monitoring/stop`),
  monitoring: (examId: number) => request<MonitoringState>("GET", `/api/exams/${examId}/monitoring`),
  examEvents: (examId: number, o: { student_id?: number; category?: string; since?: string; limit?: number } = {}) => request<{ server_time: string; events: AIEvent[] }>("GET", `/api/exams/${examId}/events${qs(o)}`),
  events: (o: { category?: string; since?: string; review?: string; limit?: number } = {}) => request<{ server_time: string; events: AIEvent[] }>("GET", `/api/events${qs(o)}`),
  event: (id: string) => request<AIEvent>("GET", `/api/events/${encodeURIComponent(id)}`),
  review: (id: string, decision: Decision, note: string) => request<AIEvent>("POST", `/api/events/${encodeURIComponent(id)}/reviews`, { decision, note }),
  cases: (o: { review?: string; student_id?: number; exam_id?: number } = {}) => request<CaseList>("GET", `/api/cases${qs(o)}`),
  caseDetail: (id: string) => request<CaseDetail>("GET", `/api/cases/${encodeURIComponent(id)}`),
  summaries: () => request<{ server_time: string; summaries: ExamSummary[] }>("GET", "/api/summaries"),
  examSummary: (examId: number) => request<ExamSummary>("GET", `/api/exams/${examId}/summary`),
  reviewCase: (id: string, decision: Decision, note: string, eventIds: string[]) => request<CaseDetail>("POST", `/api/cases/${encodeURIComponent(id)}/reviews`, { decision, note, event_ids: eventIds }),
  addNote: (examId: number, body: { student_id?: number | null; time_text?: string; kind?: string; note: string }) => request<unknown>("POST", `/api/exams/${examId}/notes`, body),
  evidence: (id: string) => request<EvidenceMeta>("GET", `/api/evidence/${encodeURIComponent(id)}`),
  // Evidence images need the Authorization header, so they are fetched as blobs (never via a public URL).
  evidenceFrameUrl: async (id: string, index: number) => {
    const res = await request<Response>("GET", `/api/evidence/${encodeURIComponent(id)}/frames/${index}`, undefined, { raw: true });
    return URL.createObjectURL(await res.blob());
  },
  report: (examId: number) => request<Report>("GET", `/api/sessions/${examId}/report`),
  reviewPatch: (id: string, body: { decision?: Decision; note?: string }) => request<{ event: ReportEvent; indications: ReportSummary }>("PATCH", `/api/events/${encodeURIComponent(id)}/review`, body),
  finalizeReport: (examId: number) => request<Report>("POST", `/api/sessions/${examId}/finalize`),
  reportFrameSrc: (url: string) => `${BASE}${url}`,
  exportReport: async (examId: number, kind: "pdf" | "xlsx") => {
    const res = await request<Response>("GET", `/api/sessions/${examId}/report.${kind}`, undefined, { raw: true });
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url; a.download = `laporan-sesi-${examId}.${kind}`; a.click();
    URL.revokeObjectURL(url);
  },
  audit: () => request<AuditRow[]>("GET", "/api/audit"),
};

// ---- display helpers ----
export const EVIDENCE_RESTRICTED = "Gambar bukti hanya untuk pengawas dan admin";
export const ROLE_LABEL: Record<RoleCode, "Siswa" | "Pengawas" | "Penyelenggara Ujian" | "Admin" | "Pihak Sekolah"> = {
  siswa: "Siswa", pengawas: "Pengawas", penyelenggara: "Penyelenggara Ujian", admin: "Admin", sekolah: "Pihak Sekolah",
};
export const STATE_LABEL: Record<AnalysisState, string> = {
  not_started: "AI belum dimulai", no_data: "Menunggu hasil analisis", ai_offline: "Analisis AI terputus", warming_up: "Menyiapkan acuan", normal: "Normal", indication: "Indikasi aktif",
  cannot_analyze: "Tidak dapat dianalisis", model_unavailable: "AI belum tersedia",
};
// Why speech-sound analysis is not running (backend: _audio_block / _audio_state). [short, full]
export type AudioReason = "not_consented" | "monitoring_off" | "disabled" | "ai_unavailable" | "model_missing" | "worker_mode" | "jitsi_mode" | "mic_off" | "no_scores";
export const AUDIO_REASON: Record<AudioReason, [string, string]> = {
  not_consented: ["tidak disetujui", "Siswa tidak menyetujui analisis suara."],
  monitoring_off: ["AI belum dimulai", "Pemantauan AI belum dimulai."],
  disabled: ["dimatikan", "Analisis suara dimatikan di konfigurasi server (EDUAI_AUDIO_ANALYSIS / OTHER_VOICE)."],
  ai_unavailable: ["AI belum siap", "Layanan AI di server belum siap."],
  model_missing: ["model tidak ada", "Model suara (ai/eduai-ai/models/yamnet.tflite) tidak ditemukan di server."],
  worker_mode: ["mode OpenVidu", "Hanya tersedia pada mode frame browser; worker OpenVidu hanya menganalisis video."],
  jitsi_mode: ["mode Jitsi", "Hanya tersedia pada mode frame browser; mode Jitsi hanya menganalisis video."],
  mic_off: ["mikrofon mati", "Mikrofon siswa mati."],
  no_scores: ["belum ada skor", "Belum ada skor suara dari browser siswa (model masih dimuat atau gagal di perangkat siswa)."],
};
export const SOURCE_LABEL: Record<AnalysisSource, string> = { browser: "Browser", livekit: "OpenVidu", jitsi: "Jitsi" };
export const FRAME_REASON: Record<string, string> = {
  track_ended: "kamera mati atau track berhenti", no_frames: "tidak ada frame yang masuk",
  no_frame: "tidak ada frame", low_resolution: "resolusi terlalu rendah", dark: "terlalu gelap", overexposed: "terlalu terang",
  blurry: "gambar buram", frozen: "video membeku", face_too_small: "wajah terlalu kecil/jauh", ai_unavailable: "layanan AI belum siap",
  face_detector: "model wajah belum tersedia",
};
export const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
export const fmtTime = (iso?: string | null) => iso ? new Date(iso).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).replace(/:/g, ".") : "—";
export const fmtDate = (d?: string | null) => d ? new Date(d.length === 10 ? `${d}T00:00:00` : d).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" }) : "—";
export const fmtDateTime = (iso?: string | null) => iso ? `${fmtDate(iso)}, ${fmtTime(iso)}` : "—";
export const fmtDuration = (s?: number | null) => s == null ? "—" : s < 60 ? `${Math.round(s)} detik` : `${Math.floor(s / 60)} mnt ${Math.round(s % 60)} dtk`;
export const minutesAgo = (iso: string) => { const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000)); return m < 1 ? "baru saja" : `${m} mnt lalu`; };
export function examWindow(e: Pick<Exam, "date" | "start_time" | "duration_min">) {
  const start = new Date(`${e.date}T${e.start_time}:00`);
  const end = new Date(start.getTime() + e.duration_min * 60000);
  return { start, end };
}
export function remaining(e: Pick<Exam, "date" | "start_time" | "duration_min">, now = Date.now()) {
  const ms = Math.max(0, examWindow(e).end.getTime() - now);
  const h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000), s = Math.floor((ms % 60000) / 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
