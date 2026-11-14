import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode, type SyntheticEvent } from "react";
import {
  api, ApiError, examWindow, fmtDate, fmtDateTime, fmtDuration, fmtTime, FRAME_REASON, initials, remaining, ROLE_LABEL, EVIDENCE_RESTRICTED,
  session, setUnauthorizedHandler, SOURCE_LABEL, STATE_LABEL, AUDIO_REASON,
  type AIEvent, type AIHealth, type AnalysisState, type AuditRow, type CaseSummary, type Decision, type Exam, type ExamSummary, type Health, type MonitoringInfo,
  type MonitoringState, type AnalysisSource, type SebResult, type SebRow, type SebSettings, type Report as ReportData, type ReportEvent, type ReportSummary, type StudentRow, type TimelineItem, type User, type UserRow, type RoleCode,
} from "./api";
import { loadSeen, newCaseIds, newSummaryKeys, notifiableCaseIds, saveSeen, seenKey, seenSummariesKey } from "./notify";
import { SpeechScorer } from "./audio";
import { alarmMuted, playAlarm, setAlarmMuted } from "./alarm";
import { FrameUploader, measureLatency, mediaErrorMessage, startStudentMedia, useExamVideoRoom, useMicLevel, useOpenViduBroadcast, useVideo, type StudentMedia } from "./media";
import type { RemoteTrack } from "livekit-client";
import { EVIDENCE_NOTICE, JITSI_NOTICE_UNKNOWN, jitsiNotice } from "./consent";
import { jitsiRoomName, useJitsiRoom, useJitsiTrack, useJitsiWatch, type JitsiTrack } from "./jitsi";
import { readSeb, sebLaunchLink, SEB_STATE_LABEL } from "./seb";
import { ALLOWED_SCREENS, authErrorMessage, dashboardKind, initialScreen, landingAction, opensIndications, type Role } from "./routes";
import { greetingWib, NO_DATA as NO_DATA_TEXT, timeAgo } from "./time";
import { activeExams, analysisGaps, examTimes, indicatorIcon, remainingText, upcomingExams } from "./dashboard";
import { attendanceParts, caseStatus, historyRows, caseStatusBreakdown, monitorStatus, reportResults, sessionTimeline, utcMs, wibDate } from "./chartData";
import { BADGE_ROLES, NAV_MENUS, PROFILE_SCREEN, badgeText, isActive, mobileSplit, type NavItem } from "./nav";
import { NavIcon } from "./navIcons";
import { NotifPanel } from "./NotifPanel";
import { useFocusTrap } from "./hooks";
import { activityFeed, drawerCases, filterCases, filterQuery, jenisCounts, kindBars, kindSlices, kpi7, loadSlices, parseFilter, sinceIso, statusSummary, supervisorLoad, type DrawerSource, type Filter, type JenisKey, type StatusKey } from "./indikasi";
import { FilterRow, KpiRow, StatusDonut } from "./IndikasiRingkasan";
import { ActivityCard, KindBarChart, KindDonut, LoadDonut, StudentDrawer } from "./IndikasiDetail";
import { ALL_STATUSES, filterSessions, filterStudentExams, sessionDateText, sessionTone, STATUS_OPTIONS, STUDENT_FILTERS, studentFilterCounts, type StudentFilter } from "./sessions";

// Grafik dimuat terpisah (chunk sendiri) hanya saat halamannya dibuka.
const DashboardCharts = lazy(() => import("./charts"));
const HistoryChart = lazy(() => import("./charts").then((m) => ({ default: m.HistoryChart })));
const MonitoringCharts = lazy(() => import("./charts").then((m) => ({ default: m.MonitoringCharts })));
const ReportAttendance = lazy(() => import("./charts").then((m) => ({ default: m.ReportAttendance })));
const ReportResults = lazy(() => import("./charts").then((m) => ({ default: m.ReportResults })));
const ChartSkeleton = ({ h = 180 }: { h?: number }) => <div aria-hidden="true" className="rounded border border-line bg-white" style={{ height: h }} />;

type Screen =
  | "beranda"
  | "loading"
  | "login"
  | "entering"
  | "dashboard"
  | "sessions"
  | "create"
  | "exam-detail"
  | "waiting"
  | "consent"
  | "device"
  | "seb-check"
  | "exam"
  | "monitor"
  | "student-detail"
  | "detail"
  | "timeline"
  | "report"
  | "indications"
  | "history"
  | "my-exams"
  | "users"
  | "configuration"
  | "retention"
  | "audit"
  | "access-denied"
  | "students"
  | "meeting"
  | "settings";

const RoleContext = createContext<{ role: Role; setRole: (role: Role) => void }>({ role: "Pengawas", setRole: () => undefined });
const useRole = () => useContext(RoleContext);
const UserContext = createContext<{ user: User | null; setUser: (u: User | null) => void }>({ user: null, setUser: () => undefined });
const useUser = () => useContext(UserContext);
type Selection = { examId: number | null; setExamId: (id: number | null) => void; studentId: number | null; setStudentId: (id: number | null) => void; eventId: string | null; setEventId: (id: string | null) => void };
const SelectionContext = createContext<Selection>({ examId: null, setExamId: () => undefined, studentId: null, setStudentId: () => undefined, eventId: null, setEventId: () => undefined });
const useSel = () => useContext(SelectionContext);
type Notify = {
  items: CaseSummary[]; unread: number; markRead: () => void; toast: CaseSummary | null; dismiss: () => void;
  summaries: ExamSummary[]; summaryToast: ExamSummary | null; dismissSummary: () => void;
  summaryExam: number | null; openSummary: (examId: number) => void; closeSummary: () => void;
};
const NotifyContext = createContext<Notify>({ items: [], unread: 0, markRead: () => undefined, toast: null, dismiss: () => undefined,
  summaries: [], summaryToast: null, dismissSummary: () => undefined, summaryExam: null, openSummary: () => undefined, closeSummary: () => undefined });
const MONITOR_ROLES: Role[] = ["Pengawas", "Penyelenggara Ujian", "Admin"];

/** Load data (optionally polling). Keeps the last good data when a refresh fails. */
function usePoll<T>(fn: () => Promise<T>, deps: unknown[], every = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadedDeps, setLoadedDeps] = useState(deps);
  if (deps.some((d, i) => !Object.is(d, loadedDeps[i]))) { setLoadedDeps(deps); setLoading(true); }
  const fnRef = useRef(fn);
  useEffect(() => { fnRef.current = fn; });        // declared first: the load effect below sees the latest fn
  const load = useCallback(async () => {
    try { setData(await fnRef.current()); setError(""); } catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }, []);
  useEffect(() => {
    void load();
    if (!every) return;
    const t = window.setInterval(() => void load(), every);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading, reload: load, setData };
}

/** The exam staff pages work on: the selected one, else the first running one, else the first. */
function useCurrentExam() {
  const { examId, setExamId } = useSel();
  const list = usePoll(() => api.exams(), []);
  const exams = list.data ?? [];
  const exam = exams.find((e) => e.id === examId) ?? exams.find((e) => e.status === "Sedang Berlangsung") ?? exams[0] ?? null;
  useEffect(() => { if (exam && exam.id !== examId) setExamId(exam.id); }, [exam, examId, setExamId]);
  return { exam, exams, loading: list.loading, error: list.error, reload: list.reload };
}

// Nama sekolah dari EDUAI_SCHOOL_NAME (lewat /api/health), diambil sekali per halaman. Kosong = belum diisi.
const NO_DATA = NO_DATA_TEXT;
let schoolName: Promise<string | null> | null = null;
function useSchoolName(): string | null | undefined {
  const r = usePoll(() => (schoolName ??= api.health().then((h) => h.school_name ?? null).catch((e) => { schoolName = null; throw e; })), []);
  return r.loading ? undefined : r.data;
}

function Notice({ children, tone = "amber" }: { children: ReactNode; tone?: "amber" | "red" | "blue" }) {
  const s = { amber: "border-amber-200 bg-amber-50 text-amber-900", red: "border-red-200 bg-red-50 text-red-700", blue: "border-blue-100 bg-blue-50 text-blue-800" };
  return <div role={tone === "red" ? "alert" : "status"} className={`mb-5 rounded-md border px-4 py-3 text-sm leading-6 ${s[tone]}`}>{children}</div>;
}

function SampleTag() {
  return <span className="ml-2 inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 align-middle text-[11px] font-semibold text-slate-500 ring-1 ring-inset ring-slate-200" title="Bagian ini belum tersambung ke backend">Data contoh</span>;
}

type IconName =
  | "edit"
  | "grid"
  | "monitor"
  | "report"
  | "settings"
  | "search"
  | "plus"
  | "upload"
  | "calendar"
  | "clock"
  | "users"
  | "camera"
  | "mic"
  | "wifi"
  | "bell"
  | "chevron"
  | "arrow"
  | "check"
  | "video"
  | "download"
  | "more"
  | "menu"
  | "close"
  | "shield"
  | "logout"
  | "phone"
  | "eye"
  | "book"
  | "file";

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    monitor: <><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></>,
    report: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h6" /></>,
    edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 9 19.37a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.63 15 1.7 1.7 0 0 0 3.08 14H3v-4h.08A1.7 1.7 0 0 0 4.63 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.63a1.7 1.7 0 0 0 1-1.55V3h4v.08A1.7 1.7 0 0 0 15 4.63a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.37 9a1.7 1.7 0 0 0 1.55 1H21v4h-.08A1.7 1.7 0 0 0 19.4 15z" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    plus: <path d="M12 5v14M5 12h14" />,
    upload: <><path d="M12 16V4M7 9l5-5 5 5M4 20h16" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
    camera: <><path d="M15 10l4.5-2.5v9L15 14z" /><rect x="2" y="6" width="13" height="12" rx="2" /></>,
    mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8" /></>,
    wifi: <><path d="M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0" /><circle cx="12" cy="20" r="1" /></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    arrow: <path d="m15 18-6-6 6-6" />,
    check: <path d="m5 12 4 4L19 6" />,
    video: <><rect x="3" y="5" width="14" height="14" rx="2" /><path d="m17 10 4-2v8l-4-2" /></>,
    download: <><path d="M12 3v12M7 10l5 5 5-5M4 21h16" /></>,
    more: <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>,
    menu: <path d="M4 7h16M4 12h16M4 17h16" />,
    close: <path d="M6 6l12 12M18 6 6 18" />,
    shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></>,
    logout: <path d="M10 5H5v14h5M14 8l4 4-4 4M18 12H9" />,
    phone: <><rect x="7" y="2" width="10" height="20" rx="2" /><path d="M10 5h4M11 18h2" /></>,
    eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></>,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z" /><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function Logo({ large = false, inverse = false, tagline = "Pengawasan Ujian" }: { large?: boolean; inverse?: boolean; tagline?: string }) {
  return (
    <div className="flex items-center gap-3">
      <img src="/brand/smart-exam-integrity.webp" alt="Logo EduAI Smart Exam Integrity" className={large ? "size-20" : "size-11"} />
      <div className="leading-tight"><div className={`font-extrabold tracking-tight ${inverse ? "text-white" : "text-navy"} ${large ? "text-3xl" : "text-[1.4rem]"}`}>Edu<span className="text-gold-500">AI</span></div><div className={`brand-caps mt-0.5 ${inverse ? "text-blue-300" : "text-gold-700"} ${large ? "text-xs" : "text-[10px]"}`}>{tagline}</div></div>
    </div>
  );
}

function Button({ children, variant = "primary", icon, disabled, onClick, className = "", type = "button" }: { children: ReactNode; variant?: "primary" | "secondary" | "ghost" | "success"; icon?: IconName; disabled?: boolean; onClick?: () => void; className?: string; type?: "button" | "submit" }) {
  const styles = { primary: "bg-navy text-gold-300 hover:bg-navy-2", secondary: "border border-line bg-white text-navy hover:bg-paper", ghost: "text-slate-600 hover:bg-paper", success: "bg-[#23856d] text-white hover:bg-[#1d6f5b]" };
  return <button type={type} disabled={disabled} onClick={onClick} className={`inline-flex h-10 items-center justify-center gap-2 rounded px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none ${styles[variant]} ${className}`}>{icon && <Icon name={icon} size={18} />}{children}</button>;
}

function Badge({ children, tone = "gray", pulse = false }: { children: ReactNode; tone?: "blue" | "green" | "amber" | "gray" | "red" | "gold"; pulse?: boolean }) {
  const styles = { gold: "bg-[#f5edd0] text-[#745b0d]", blue: "bg-[#e6eef8] text-[#3d628e]", green: "bg-[#e5f3ed] text-[#26745f]", amber: "bg-[#f7edcf] text-[#8c621a]", gray: "bg-[#eceff1] text-[#687386]", red: "bg-[#f8e6e4] text-[#9b3f3f]" };
  return <span className={`inline-flex w-fit items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold ${styles[tone]}`}><i aria-hidden="true" className={`size-1.5 shrink-0 rounded-full bg-current ${pulse ? "animate-pulse" : ""}`} />{children}</span>;
}

function Field({ label, placeholder, type = "text", value, name }: { label: string; placeholder?: string; type?: string; value?: string; name?: string }) {
  return <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">{label}</span><input name={name} type={type} defaultValue={value} placeholder={placeholder} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-50" /></label>;
}

const statusTone = sessionTone;
const stateTone = (s?: AnalysisState | null) => (s === "normal" ? "green" : s === "indication" || s === "ai_offline" ? "amber" : s === "warming_up" ? "blue" : "gray") as "green" | "amber" | "blue" | "gray";
const mayOpenEvidence = (role: Role) => role === "Pengawas" || role === "Admin";   // the backend enforces this; here it only avoids 403s
const reviewTone = (l?: string | null) => (l === "Valid" ? "green" : !l || l === "Perlu Tinjauan Lanjut" ? "amber" : "gray") as "green" | "amber" | "gray";
const reviewLabel = (l?: string | null) => l ?? "Belum ditinjau";
const eventTitle = (e: AIEvent | CaseSummary) => e.label ?? e.indicator;
// Review status of a grouped case. A case with unreviewed events counts as "Belum ditinjau" even if older
// events of it were reviewed (new events never inherit a decision).
const caseLabel = (c: CaseSummary) => (c.unreviewed_count > 0 ? (c.unreviewed_count < c.event_count ? `${c.unreviewed_count} baru belum ditinjau` : "Belum ditinjau") : c.review_status ?? "Belum ditinjau");
const caseTone = (c: CaseSummary) => (c.unreviewed_count > 0 ? "amber" : reviewTone(c.review_status === "Campuran" ? "Perlu Tinjauan Lanjut" : c.review_status));
const scoreText = (e: AIEvent) => (e.score == null ? "—" : `${Math.round(e.score * 100)}%`);
const examTime = (e: Exam) => { const { end } = examWindow(e); return `${e.start_time.replace(":", ".")}–${end.toTimeString().slice(0, 5).replace(":", ".")} WIB`; };

// Tab peran di portal staf: dikirim ke backend saat login dan dicocokkan dengan peran akun di database.
const STAFF_TABS = ["Penyelenggara", "Pengawas", "Admin", "Sekolah"];
const STAFF_TAB_ROLE: Record<string, RoleCode> = { Penyelenggara: "penyelenggara", Pengawas: "pengawas", Admin: "admin", Sekolah: "sekolah" };

type Portal = "siswa" | "sekolah";

// Beranda (desain Figma "Landing"). Isinya teks tetap tentang cara kerja EduAI; tidak ada angka, berita, atau tautan contoh.
// Foto sinyal AI: public/images/ai-signals (Git LFS, dikonfirmasi pemilik 13 Nov 2026). Bila foto gagal dimuat,
// kartu memakai ilustrasi yang sesuai dari public/images/sinyal-ai.
const SIGNALS: [string, string, string, string][][] = [
  [["Ponsel terlihat", "Ponsel dipegang atau terlihat di depan kamera.", "/images/ai-signals/1_phone_in_view.png", "/images/sinyal-ai/ponsel-terlihat.svg"],
    ["Buku terlihat", "Buku terbuka terlihat di depan kamera.", "/images/ai-signals/2_book_in_view.png", "/images/sinyal-ai/buku-terlihat.svg"]],
  [["Orang lain terlihat", "Lebih dari satu wajah muncul di kamera.", "/images/ai-signals/3_another_person.png", "/images/sinyal-ai/orang-lain-terlihat.svg"],
    ["Sering menoleh", "Kepala berulang kali menoleh dari layar.", "/images/ai-signals/4_looking_away.png", "/images/sinyal-ai/sering-menoleh.svg"]],
  [["Wajah tidak terlihat", "Wajah keluar dari kamera atau tertutup.", "/images/ai-signals/5_face_not_visible.png", "/images/sinyal-ai/wajah-tidak-terlihat.svg"],
    ["Suara lain terdengar", "Suara bicara lain atau bisikan selama ujian.", "/images/ai-signals/6_other_voice.png", "/images/sinyal-ai/suara-lain-terdengar.svg"]],
];
// Bila sebuah gambar gagal dimuat, ganti sekali dengan ilustrasi cadangan agar tidak muncul ikon gambar rusak.
const IMG_FALLBACK = "/images/fallback-gambar.svg";
const imgFallback = (e: SyntheticEvent<HTMLImageElement>) => { const img = e.currentTarget; if (!img.src.endsWith(IMG_FALLBACK)) img.src = IMG_FALLBACK; };
const SIGNAL_ROWS = ["md:grid-rows-[340px_260px]", "md:grid-rows-[260px_340px]", "md:grid-rows-[380px_220px]"];
// Photos: local copies of the Figma design's Unsplash photos (sources in public/images/beranda/CREDITS.md).
// The app never loads images from the internet.
const LANDING_CARDS: { image: string; alt: string; title: string; text: string; id?: string }[] = [
  { image: "/images/beranda/cek-perangkat.webp", alt: "Seorang anak belajar dengan laptop di meja", title: "Cek perangkat", text: "Periksa kamera, mikrofon, peramban, dan koneksi sebelum ujian dimulai." },
  { image: "/images/beranda/panduan-siswa.webp", alt: "Sekelompok pelajar berkumpul di sekitar sebuah laptop", title: "Panduan siswa", text: "Panduan singkat untuk bersiap dan mengikuti ujian EduAI.", id: "siswa" },
  { image: "/images/beranda/laporan-pengawas.webp", alt: "Seorang perempuan bekerja dengan laptop di ruang kelas (foto hitam putih)", title: "Laporan pengawas", text: "Tinjau kemungkinan masalah lengkap dengan waktu, konteks, dan catatan keputusan.", id: "pengawas" },
  { image: "/images/beranda/cara-kerja-ai.webp", alt: "Dua orang memperhatikan layar laptop bersama", title: "Cara kerja AI", text: "Apa yang dapat ditandai EduAI, dan mengapa EduAI tidak pernah membuat keputusan akhir." },
  { image: "/images/beranda/privasi-persetujuan.webp", alt: "Seorang pengajar bekerja dengan laptop di depan papan tulis", title: "Privasi dan persetujuan", text: "Cara data ujian dikumpulkan, dilindungi, dan dihapus sesuai masa simpan.", id: "privasi" },
];

function Landing({ start, user, toDashboard }: { start: (p: Portal) => void; user: User | null; toDashboard: () => void }) {
  const [active, setActive] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const action = landingAction(!!user);
  const enter = (p: Portal) => (action.next === "dashboard" ? toDashboard() : start(p));
  const menu: [string, string][] = [["#beranda", "Beranda"], ["#kabar", "Kabar"], ["#cara-kerja", "Cara Kerja"], ["#siswa", "Siswa"], ["#pengawas", "Pengawas"], ["#privasi", "Privasi"], ["#kontak", "Kontak"]];
  const portals = user
    ? <button onClick={toDashboard} className="tap relative whitespace-nowrap underline-offset-4 hover:underline">{action.label}</button>
    : <><button onClick={() => enter("sekolah")} className="tap relative whitespace-nowrap underline-offset-4 hover:underline">Sekolah</button>
      <button onClick={() => enter("siswa")} className="tap relative whitespace-nowrap underline-offset-4 hover:underline">Portal Siswa</button></>;
  return <div className="min-h-screen bg-white text-[#273141]">
    {/* Struktur lebar penuh seperti local.ed.ac.uk; ukuran di index.css (.bd-*) dan docs/beranda-ukuran.md. */}
    {/* 1. Bilah menu atas (navy). Di bawah 1024 px menu menjadi tombol "Menu". */}
    <div className="bg-navy text-white"><div className="bd-band">
      <div className="bd-nav flex min-h-11 items-center justify-between gap-x-6 lg:min-h-[59.4px]">
        <nav aria-label="Navigasi utama" className="hidden lg:block"><ul className="flex gap-x-8">
          {menu.map(([href, label], i) => <li key={href}><a href={href} aria-current={i === 0 ? "page" : undefined}
            className={`block whitespace-nowrap border-b-4 pb-2.5 pt-3.5 hover:text-gold-300 ${i === 0 ? "border-gold-500" : "border-transparent"}`}>{label}</a></li>)}
        </ul></nav>
        <button type="button" onClick={() => setMenuOpen((v) => !v)} aria-expanded={menuOpen} aria-controls="menu-hp" className="flex min-h-11 items-center gap-2 lg:hidden">
          <Icon name={menuOpen ? "close" : "menu"} size={22} />Menu</button>
        <nav aria-label={user ? "Dasbor" : "Masuk"} className="flex items-center gap-x-6">{portals}</nav>
      </div>
      {menuOpen && <nav id="menu-hp" aria-label="Navigasi utama (HP)" className="bd-nav border-t border-[#3c4861] pb-3 lg:hidden"><ul>
        {menu.map(([href, label]) => <li key={href}><a href={href} onClick={() => setMenuOpen(false)} className="flex min-h-11 items-center hover:text-gold-300">{label}</a></li>)}
      </ul></nav>}
    </div></div>

    {/* 2. Header putih: lambang + nama. Masuk lewat tautan portal di bilah menu navy. */}
    <header className="bg-white"><div className="bd-band flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-[5px] sm:min-h-[79px] sm:py-5">
      <a href="#beranda" className="flex items-center gap-3 sm:gap-4">
        <img src="/brand/smart-exam-integrity.webp" alt="" className="h-14 w-14 sm:h-[79px] sm:w-[79px]" />
        <span className="font-sans font-semibold text-2xl leading-tight text-navy sm:text-[32px]">Smart Exam Integrity</span>
      </a>
    </div></header>

    <main id="beranda">
      {/* 3. Banner lebar penuh: kolase webcam tim EduAI (4120x760). Tidak dipotong (contain, rasio asli), tanpa filter atau lapisan warna,
             tanpa lazy loading karena terlihat saat halaman dibuka. */}
      <img src="/images/beranda/banner_indikasi.webp" onError={imgFallback} alt="Kolase foto webcam peserta ujian dengan bingkai deteksi emas sebagai contoh indikasi AI."
        width={4120} height={760} loading="eager" decoding="async" fetchPriority="high" className="block aspect-[4120/760] w-full object-contain" />

      {/* 4. Pita judul navy. */}
      <section aria-labelledby="visi" className="bg-navy text-white"><div className="bd-band bd-title-top bd-title-bottom">
        <h1 id="visi" className="bd-h1 bd-caps text-white">Visi kami</h1>
        <p className="bd-text mt-3 max-w-[60rem]">Ujian daring yang adil bagi sekolah. AI hanya menandai indikasi. Pengawas yang mengambil keputusan.</p>
        <a href="#cara-kerja" className="tap relative bd-text mt-3 inline-flex items-center gap-2 font-bold text-gold-300 underline underline-offset-4">Baca pendekatan kami <span aria-hidden="true">→</span></a>
      </div></section>

      {/* 5. Kartu foto: container maks 960 px di tengah, 3 kolom dengan jarak 20 px (sekitar 307 px per kartu), foto 16:9.
             Grid dan container sama dengan "Yang diperhatikan AI", sehingga kolomnya sejajar. */}
      <section id="cara-kerja" aria-label="Panduan dan informasi" className="scroll-mt-4 bg-paper pb-[78px] pt-6"><div className="bd-band bd-narrow">
        <div className="grid items-start gap-5 md:grid-cols-3">
          {LANDING_CARDS.map(({ image, alt, title, text, id }) => <article key={title} id={id} className="bd-card-shadow min-w-0 scroll-mt-4 border-t-8 border-navy bg-white max-md:grid max-md:grid-cols-[7.5rem_1fr] max-md:grid-rows-[auto_1fr]">
            <img src={image} alt={alt} onError={imgFallback} width={1200} height={675} loading="lazy" decoding="async" className="block aspect-[16/9] w-full bg-paper object-cover max-md:row-span-2 max-md:aspect-auto max-md:h-full max-md:min-h-28" />
            <h2 className="bd-card-title px-4 pt-4 max-md:pt-3">{title}</h2>
            <p className="bd-card-text px-4 pb-5 pt-1.5 text-[#334052] max-md:pb-3">{text}</p>
          </article>)}
          <article id="kabar" aria-labelledby="kabar-judul" className="bd-card-shadow min-w-0 scroll-mt-4 border-t-8 border-navy bg-white">
            <h2 id="kabar-judul" className="bd-card-title px-4 pt-4">Kabar terbaru</h2>
            <ul className="bd-card-text px-4 pb-3 pt-1.5">{["Mode ujian Jitsi kini tersedia", "Safe Exam Browser per ujian", "Hasil uji deteksi buku dan ponsel"].map((t) =>
              <li key={t} className="flex min-h-11 items-center border-b border-[#d6d8da] font-bold text-[#765d0e] last:border-b-0">{t}</li>)}</ul>
          </article>
        </div>
      </div></section>

      <section className="bg-white py-12 md:py-20"><div className="bd-band bd-narrow">
        <div className="mb-6 md:mb-[38px]"><h2 className="text-[1.75rem] leading-[1.2] md:text-[42px]">Yang diperhatikan AI</h2><p className="mt-[13px] text-[15px] leading-[1.7] text-[#555f6c]">Ini tanda, bukan bukti. Pengawas selalu memeriksanya terlebih dahulu.</p></div>
        <div className="grid gap-3 md:grid-cols-3 md:gap-5">{SIGNALS.map((column, c) => <div key={c} className={`grid grid-cols-2 gap-3 md:grid-cols-1 md:gap-5 ${SIGNAL_ROWS[c]}`}>
          {column.map(([title, text, image, illustration]) => {
            const still = title === "Suara lain terdengar";            // Figma: kartu suara tidak dapat dipilih
            const on = active === title && !still;
            return <article key={title} tabIndex={still ? undefined : 0} role={still ? undefined : "button"} aria-pressed={still ? undefined : on}
              onClick={() => { if (!still) setActive(title); }} onKeyDown={(e) => { if (!still && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setActive(title); } }}
              className={`group relative h-40 overflow-hidden bg-[#c8ccd0] min-[480px]:h-48 md:h-auto ${still ? "cursor-default" : "cursor-pointer focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-gold-500"}`}>
              <img src={image} alt={title} onError={(e) => { const img = e.currentTarget; if (!img.src.endsWith(illustration)) img.src = illustration; }} className={`block size-full bg-[#c8ccd0] object-cover ${c === 0 ? "object-[center_70%]" : "object-center"}`} />
              <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,rgba(20,33,61,.48),rgba(20,33,61,.8))]" />
              {!still && <div className={`pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,rgba(201,162,39,0),rgba(201,162,39,.92))] transition-opacity duration-250 ${on ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`} />}
              <div className="absolute inset-x-0 bottom-0 p-3.5 text-white sm:p-6">
                <h3 className="font-sans text-[15px] font-bold leading-[1.25] text-white sm:text-[22px]">{title}</h3>
                <p className={`max-w-[310px] overflow-hidden text-xs leading-normal transition-all sm:text-sm duration-250 ${still ? "max-h-0 opacity-0" : on ? "mt-2 max-h-12 opacity-100" : "max-h-0 opacity-0 group-hover:mt-2 group-hover:max-h-12 group-hover:opacity-100"}`}>{text}</p>
              </div>
            </article>;
          })}
        </div>)}</div>
        <p className="mt-6 text-xs leading-[1.6] text-[#707985]">Bila kamera terlalu gelap atau buram, kejadian ditandai &lsquo;Tidak dapat dianalisis&rsquo;, bukan sebagai indikasi.</p>
      </div></section>

      <section className="bg-paper px-6 py-16 text-center">
        <h2 className="text-[2rem] md:text-4xl">{user ? "Lanjutkan pekerjaan Anda" : "Siap memulai?"}</h2>
        <p className="mt-3.5 text-[13px] text-[#64707e]">{user ? `Anda masuk sebagai ${user.name} (${ROLE_LABEL[user.role]}).` : "Siswa masuk lewat Portal Siswa. Penyelenggara, pengawas, dan admin masuk lewat Sekolah."}</p>
        <button onClick={() => enter("siswa")} className="mt-[25px] inline-flex min-h-11 items-center justify-center bg-navy px-[21px] text-xs font-bold text-white hover:underline">{action.label}</button>
      </section>
    </main>

    <footer id="kontak" className="bg-navy pb-[30px] pt-[58px] text-white"><div className={`bd-band grid gap-10 md:grid-cols-[1.5fr_1fr_.7fr] md:gap-20`}>
      <div><h2 className="text-[27px] text-white">EduAI</h2><p className="mt-[17px] max-w-[470px] text-xs leading-[1.7] text-[#c5cbd5]">Proyek pengawasan ujian sekolah yang mengutamakan keadilan, privasi, dan penilaian manusia. Untuk bantuan akun, hubungi admin sekolah Anda.</p></div>
      <nav aria-label="Tautan halaman" className="grid grid-cols-2 content-start gap-x-6 gap-y-3.5 pt-2 text-xs">{[["#cara-kerja", "Cara kerja"], ["#privasi", "Privasi"], ["#siswa", "Panduan siswa"], ["#pengawas", "Laporan pengawas"]].map(([href, label]) => <a key={href} href={href} className="tap relative w-fit underline underline-offset-3">{label}</a>)}</nav>
      <div className="flex flex-col items-start gap-7 pt-2"><button onClick={() => enter("siswa")} className="tap relative text-xs underline underline-offset-3">{action.label}</button><span className="text-xs text-[#c5cbd5]">© 2026 EduAI</span></div>
    </div></footer>
  </div>;
}

// Layar transisi ke halaman masuk (desain Figma "LoginLoadingScreen"): logo EduAI, 1,5 detik, lalu halaman Login.
// Animasi mati bila pengguna memilih reduced motion (index.css).
function LoginLoading({ onComplete }: { onComplete: () => void }) {
  useEffect(() => { const t = window.setTimeout(onComplete, 1500); return () => window.clearTimeout(t); }, [onComplete]);
  return <main className="grid min-h-screen place-items-center overflow-hidden bg-navy text-white" aria-live="polite">
    <div className="flex w-[min(310px,calc(100%-3rem))] flex-col items-center">
      <div className="logo-stage relative size-[150px]" aria-hidden="true">
        <span className="logo-ring absolute inset-[6px] rounded-full" />
        <img src="/brand/smart-exam-integrity.webp" alt="" width={512} height={512} loading="eager" decoding="async"
          onError={(e) => { e.currentTarget.style.visibility = "hidden"; }}
          className="relative block size-full object-contain drop-shadow-[0_14px_12px_rgba(0,0,0,0.3)]" />
      </div>
      <p className="mt-5 text-sm font-medium tracking-[0.1px]">Membuka halaman masuk…</p>
      <div className="mt-[23px] h-0.5 w-[230px] overflow-hidden bg-white/[0.17]" aria-hidden="true"><span className="rocket-progress block size-full origin-left bg-gold-500" /></div>
    </div>
  </main>;
}

// Layar transisi setelah berhasil masuk (semua peran): robot di atas roket, 1,5 detik, lalu dasbor.
// Gaya sama dengan LoginLoading; animasi mati bila pengguna memilih reduced motion (index.css).
function AccountLoading({ user, onComplete }: { user: User; onComplete: () => void }) {
  useEffect(() => { const t = window.setTimeout(onComplete, 1500); return () => window.clearTimeout(t); }, [onComplete]);
  return <main className="grid min-h-screen place-items-center overflow-hidden bg-navy text-white" aria-live="polite">
    <div className="flex w-[min(310px,calc(100%-3rem))] flex-col items-center text-center">
      {/* Robot di atas roket (latar transparan, 425x425; dari gambar pemilik proyek). Api roket sudah ada di gambar. */}
      <div className="rocket-stage relative size-[170px]" aria-hidden="true">
        <img src="/images/login/roket-robot.webp" alt="" width={425} height={425} loading="eager" decoding="async"
          onError={(e) => { e.currentTarget.style.visibility = "hidden"; }}
          className="block size-full object-contain drop-shadow-[0_14px_12px_rgba(0,0,0,0.3)]" />
      </div>
      <p className="mt-6 text-base font-semibold">Halo, {user.name}</p>
      <p className="mt-1 text-sm font-medium tracking-[0.1px] text-white/75">Membuka dasbor {ROLE_LABEL[user.role]}…</p>
      <div className="mt-[23px] h-0.5 w-[230px] overflow-hidden bg-white/[0.17]" aria-hidden="true"><span className="rocket-progress block size-full origin-left bg-gold-500" /></div>
    </div>
  </main>;
}

function Login({ go, portal = "siswa" }: { go: (s: Screen) => void; portal?: Portal }) {
  const { setRole } = useRole();
  const { setUser } = useUser();
  const [mode, setMode] = useState<Portal>(portal);
  const [register, setRegister] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [staffTab, setStaffTab] = useState(portal === "sekolah" ? "Sekolah" : STAFF_TABS[0]);   // Beranda "Sekolah" -> tab Sekolah
  const student = mode === "siswa";
  const signup = student && register;               // self-registration exists for students only

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const mail = email.trim().toLowerCase();
    if (signup && password.length < 6) return setError("Kata sandi minimal 6 karakter.");
    setBusy(true);
    setError("");
    try {
      const res = signup ? await api.register(name.trim(), mail, password) : await api.login(mail, password, student ? "siswa" : STAFF_TAB_ROLE[staffTab]);
      session.set(res.token, res.user);
      setUser(res.user);
      setRole(ROLE_LABEL[res.user.role]);             // the account decides the role, never the tab
      go("entering");                                  // logo transition, then the dashboard
    } catch (err) {
      setError(authErrorMessage(err instanceof ApiError ? err.status : 0, (err as Error).message, signup));
    } finally {
      setBusy(false);
    }
  };
  const switchPortal = () => { setMode(student ? "sekolah" : "siswa"); setRegister(false); setError(""); };
  const field = "h-14 w-full rounded-lg border border-[#d8dee5] bg-white px-4 text-base text-[#263246] outline-none placeholder:text-[#9ba6b3] focus:border-navy";
  const label = "mt-3.5 grid gap-[9px] text-base font-bold text-navy";
  const title = signup ? "Daftar akun siswa" : student ? "Masuk Siswa" : "Masuk Staf Sekolah";
  const lead = signup ? "Untuk siswa dengan email sekolah yang diawali siswa, misalnya siswa7@gmail.com." : student ? "Masuk untuk memulai ujian Anda." : "Kelola dan awasi ujian sekolah.";

  return (
    <main className="relative grid min-h-[100dvh] content-start overflow-hidden bg-paper text-navy min-[801px]:min-h-screen min-[801px]:content-stretch min-[801px]:grid-cols-[55%_45%] min-[801px]:bg-white">
      <section className="max-[800px]:contents relative grid min-h-[430px] grid-rows-[auto_auto_1fr] overflow-hidden border-b border-[#dfe2e5] px-6 py-[25px] min-[801px]:min-h-screen min-[801px]:border-b-0 min-[801px]:border-r min-[801px]:p-12">
        <img src="/brand/smart-exam-integrity.webp" alt="" aria-hidden="true" className="pointer-events-none absolute left-[calc(39%-235px)] top-[calc(-13%-235px)] w-[536px] max-w-none opacity-[0.045] max-[800px]:-right-28 max-[800px]:bottom-[-6rem] max-[800px]:left-auto max-[800px]:top-auto max-[800px]:z-0 max-[800px]:w-[360px]" />
        <button type="button" onClick={() => go("beranda")} aria-label="Kembali ke Beranda" className="relative z-[2] flex w-fit items-center gap-[13px] text-left max-[800px]:order-1 max-[800px]:w-full max-[800px]:gap-3 max-[800px]:border-b max-[800px]:border-[#e0e3e6] max-[800px]:bg-white max-[800px]:px-[max(1.25rem,env(safe-area-inset-left))] max-[800px]:pb-3 max-[800px]:pt-[max(0.75rem,env(safe-area-inset-top))]">
          <img src="/brand/smart-exam-integrity.webp" alt="" className="size-11 min-[801px]:size-16" />
          <span className="flex flex-col gap-[3px]"><strong className="text-lg tracking-[5px] text-navy min-[801px]:text-[21px] min-[801px]:tracking-[6px]">EDUAI</strong><small className="font-sans font-semibold text-[11px] font-medium tracking-[1.3px] text-[#8a6b0d] min-[801px]:text-xs">SMART EXAM INTEGRITY</small></span>
        </button>
        <p className="relative z-[2] mt-5 max-w-[650px] text-base leading-[1.65] text-[#536173] max-[800px]:order-3 max-[800px]:mx-auto max-[800px]:mt-1 max-[800px]:px-6 max-[800px]:text-center max-[800px]:text-sm min-[801px]:mt-[30px] min-[801px]:text-lg">EduAI memantau ujian daring secara langsung dengan computer vision, membantu sekolah menjaga integritas tanpa mengganggu siswa.</p>
        {/* Foto tim EduAI (latar transparan, 1151x798): langsung di atas latar panel, tidak dipotong, tanpa lazy loading. */}
        <img src="/images/login/grid_indikasi.webp" onError={imgFallback} width={1151} height={798} loading="eager" decoding="async"
          alt="Tiga layar ujian siswa dengan bingkai deteksi emas serta label 'Ponsel terlihat' dan 'Perlu ditinjau', sebagai contoh indikasi AI."
          className="relative z-[2] mt-6 block h-auto w-[min(78%,430px)] self-center justify-self-center object-contain max-[800px]:order-4 max-[800px]:mb-[max(2rem,env(safe-area-inset-bottom))] max-[800px]:mt-4 max-[800px]:w-[min(72%,300px)] min-[801px]:mt-0 min-[801px]:w-[min(100%,720px)]" />
      </section>

      <section className="flex items-center justify-center bg-paper px-4 pb-4 pt-5 max-[800px]:order-2 sm:px-6 min-[801px]:min-h-screen min-[801px]:p-8">
        <form onSubmit={submit} className="flex w-[min(100%,480px)] flex-col rounded-xl border border-[#e0e3e6] bg-white px-5 py-7 shadow-[0_1px_2px_rgba(20,33,61,0.05)] sm:p-12 min-[801px]:rounded-none min-[801px]:shadow-none">
          <img src="/brand/smart-exam-integrity.webp" alt="Logo EduAI Smart Exam Integrity" className="size-14 self-center min-[801px]:size-[67px]" />
          <h1 className="mt-2.5 text-center font-sans text-[28px] font-bold leading-[1.18] tracking-[-0.5px] text-navy sm:text-[40px] min-[801px]:mt-3 min-[801px]:tracking-[-1px]">{title}</h1>
          <p className="mt-1.5 text-center text-[15px] leading-[1.45] text-[#778392] sm:text-lg">{lead}</p>

          {!student && <div className="mt-[18px] grid grid-cols-2 rounded-3xl bg-[#f0f2f5] p-1 min-[400px]:grid-cols-4" role="group" aria-label="Peran staf" title="Pilih peran sesuai akun Anda">
            {STAFF_TABS.map((t) => <button key={t} type="button" aria-pressed={staffTab === t} onClick={() => setStaffTab(t)} className={`min-h-11 rounded-[22px] px-0.5 text-xs ${staffTab === t ? "bg-navy font-bold text-white" : "text-navy"}`}>{t}</button>)}
          </div>}

          {signup && <label className={label}>Nama lengkap<input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" className={`${field} font-normal`} placeholder="Nama sesuai data sekolah" /></label>}
          <label className={label}>Email kampus<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" className={`${field} font-normal`} placeholder="contoh: nama@kampus.ac.id" /></label>
          <div className={label}>
            <span className="flex items-center justify-between"><label htmlFor="login-password">Kata sandi</label>{!signup && <button type="button" onClick={() => alert("Hubungi admin sekolah untuk mengatur ulang kata sandi.")} className="tap relative text-xs font-normal text-navy hover:underline">Lupa kata sandi?</button>}</span>
            <div className="relative"><input id="login-password" type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={signup ? "new-password" : "current-password"} className={`${field} pr-28 font-normal`} placeholder={signup ? "Minimal 6 karakter" : "Masukkan kata sandi"} />
              <button type="button" onClick={() => setShow(!show)} className="tap absolute right-4 top-1/2 -translate-y-1/2 text-xs font-normal text-[#6d7888] hover:text-navy">{show ? "Sembunyikan" : "Tampilkan"}</button></div>
          </div>
          {error && <p role="alert" className="mt-3.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm leading-5 text-red-700">{error}</p>}
          <button type="submit" disabled={!email || !password || (signup && !name.trim()) || busy} className="mt-3.5 h-14 rounded-lg bg-navy text-base font-extrabold tracking-[2px] text-gold-300 transition hover:bg-navy-2 disabled:cursor-not-allowed">{busy ? "MEMPROSES…" : signup ? "DAFTAR" : "MASUK"}</button>

          <p className="mt-3 text-center text-[13px] text-[#667386]">{student
            ? <>{signup ? "Sudah punya akun?" : "Belum punya akun?"} <button type="button" onClick={() => { setRegister(!register); setError(""); }} className="tap relative font-extrabold text-navy">{signup ? "Masuk" : "Daftar"}</button></>
            : "Akun staf dibuat oleh admin sekolah."}</p>
          <button type="button" onClick={switchPortal} className="tap relative mx-auto mt-2.5 w-fit text-[13px] font-bold text-[#806411] underline underline-offset-4">{student ? "Staf sekolah? Masuk di sini" : "Siswa? Masuk di sini"}</button>
          <p className="mt-3 text-center text-xs text-[#8290a0]">Bahasa Indonesia · © 2026 EduAI</p>
        </form>
      </section>
    </main>
  );
}

function Sidebar({ active, go }: { active: Screen; go: (s: Screen) => void }) {
  // Narrow icon sidebar (72 px, white). From 1280 px it widens to 240 px while the pointer (or keyboard focus) is on it.
  // Phone (< 768 px): a bottom bar with 5 places; the other menus, Profil and Keluar are under "Lainnya".
  const [more, setMore] = useState(false);
  const { role } = useRole();
  const { user } = useUser();
  const notify = useContext(NotifyContext);
  const nav = NAV_MENUS[role] as (NavItem & { id: Screen })[];
  const unreviewed = BADGE_ROLES.includes(role) ? notify.items.filter((c) => caseStatus(c) === "belum").length : 0;
  const badge = (id: Screen) => (id === "indications" ? badgeText(unreviewed) : null);
  const labelOf = (item: NavItem) => { const b = badge(item.id as Screen); return b ? `${item.label}, ${b} belum ditinjau` : item.label; };
  const logout = () => { setMore(false); const t = session.token(); if (t) void api.logout(t); session.clearAll(); go("login"); };
  const open = (id: Screen) => { setMore(false); go(id); };
  const profileOn = active === PROFILE_SCREEN;
  const { bar, more: rest } = mobileSplit(nav) as { bar: typeof nav; more: typeof nav };
  const PROFILE = PROFILE_SCREEN as Screen;
  const moreOn = more || profileOn || rest.some((item) => isActive(active, item.id));
  const moreRef = useRef<HTMLDivElement>(null), barRef = useRef<HTMLDivElement>(null), sheetRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!more) return;
    const inside = (t: Node) => [moreRef, barRef, sheetRef].some((r) => r.current?.contains(t));
    const close = (e: Event) => { if (e instanceof KeyboardEvent ? e.key === "Escape" : !inside(e.target as Node)) setMore(false); };
    document.addEventListener("keydown", close); document.addEventListener("mousedown", close);
    return () => { document.removeEventListener("keydown", close); document.removeEventListener("mousedown", close); };
  }, [more]);
  const ring = "outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#c9a227]";
  const wideLabel = "hidden whitespace-nowrap min-[1280px]:group-hover/side:inline min-[1280px]:group-has-[:focus-visible]/side:inline";
  const tip = (text: string) => <span role="tooltip" className="pointer-events-none invisible fixed left-[80px] z-[60] whitespace-nowrap rounded bg-navy px-2.5 py-1.5 text-xs font-medium text-white group-hover/item:visible group-focus-visible/item:visible min-[1280px]:hidden">{text}</span>;
  const badgeEl = (text: string | null) => text ? <span aria-hidden="true" data-badge className="absolute -right-2.5 -top-2 h-[18px] min-w-[18px] rounded-full bg-[#D92D20] px-1 text-center text-[11px] font-semibold leading-[18px] text-white ring-2 ring-white">{text}</span> : null;
  const avatar = (size: string) => <span className={`grid ${size} shrink-0 place-items-center rounded-full bg-gold-500 text-[11px] font-bold text-navy ${profileOn ? "ring-2 ring-navy ring-offset-2" : ""}`}>{initials(user?.name ?? "")}</span>;
  const moreMenu = (id: string, bottom: string, phone: boolean) => <div id={id} role="menu" aria-label="Lainnya" className={`absolute z-[70] w-56 rounded border border-[#E2E5EA] bg-white py-1.5 text-sm text-navy shadow-[0_4px_12px_rgba(20,33,61,0.12)] ${bottom}`}>
    {phone && rest.map((item) => { const on = isActive(active, item.id); return <button key={item.id} type="button" role="menuitem" onClick={() => open(item.id)} aria-current={on ? "page" : undefined} className={`flex h-11 w-full items-center gap-3 px-4 text-left hover:bg-[#F4F5F7] ${ring} ${on ? "font-semibold" : ""}`}><span className="relative"><NavIcon name={item.icon} filled={on} size={20} />{badgeEl(badge(item.id))}</span>{labelOf(item)}</button>; })}
    {phone && <button type="button" role="menuitem" onClick={() => open(PROFILE)} aria-current={profileOn ? "page" : undefined} className={`flex h-11 w-full items-center gap-3 px-4 text-left hover:bg-[#F4F5F7] ${ring}`}>{avatar("size-5")}Profil</button>}
    <button type="button" role="menuitem" onClick={() => open(PROFILE)} className={`flex h-11 w-full items-center gap-3 px-4 text-left hover:bg-[#F4F5F7] ${ring}`}><Icon name="settings" size={20} />Pengaturan</button>
    <div className="my-1.5 border-t border-[#E2E5EA]" />
    <button type="button" role="menuitem" onClick={logout} className={`flex h-11 w-full items-center gap-3 px-4 text-left hover:bg-[#F4F5F7] ${ring}`}><Icon name="logout" size={20} />Keluar</button>
  </div>;
  return <>
    <aside aria-label="Sidebar" className="group/side fixed inset-y-0 left-0 z-50 hidden w-[72px] flex-col border-r border-[#E2E5EA] bg-white py-5 text-navy transition-[width] duration-200 ease-out md:flex min-[1280px]:hover:w-60 min-[1280px]:has-[:focus-visible]:w-60">
      <button type="button" onClick={() => go("beranda")} aria-label="Beranda Smart Exam Integrity" className={`group/item mb-5 flex h-14 shrink-0 items-center gap-3 px-[14px] text-left ${ring}`}>
        <img src="/brand/smart-exam-integrity.webp" alt="" className="size-11 shrink-0" />
        <span data-brand-name className="hidden leading-tight min-[1280px]:group-hover/side:block min-[1280px]:group-has-[:focus-visible]/side:block">
          <span className="block whitespace-nowrap text-[15px] font-bold text-navy">Smart Exam</span>
          <span className="block whitespace-nowrap text-[15px] font-bold text-navy">Integrity</span>
        </span>{tip("Beranda")}
      </button>
      {/* No scrollbar: rows are 52 px and shrink together (down to 32 px) when the screen is short, e.g. the 9 admin menus. */}
      <nav aria-label="Menu utama" className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {nav.map((item) => { const on = isActive(active, item.id); return <button key={item.id} type="button" onClick={() => go(item.id)} aria-label={labelOf(item)} aria-current={on ? "page" : undefined}
          className={`group/item flex min-h-8 w-full shrink basis-[52px] items-center gap-4 px-6 text-left text-[15px] ${ring} ${on ? "font-semibold" : ""}`}>
          <span className="relative transition-transform duration-150 group-hover/item:scale-105"><NavIcon name={item.icon} filled={on} />{badgeEl(badge(item.id))}</span>
          <span className={wideLabel}>{item.label}</span>{tip(item.label)}
        </button>; })}
      </nav>
      <div ref={moreRef} className="relative mt-3 shrink-0">
        <button type="button" onClick={() => open(PROFILE)} aria-label="Profil" aria-current={profileOn ? "page" : undefined} className={`group/item flex h-[52px] w-full items-center gap-4 px-[22px] text-left text-[15px] ${ring} ${profileOn ? "font-semibold" : ""}`}>
          <span className="transition-transform duration-150 group-hover/item:scale-105">{avatar("size-7")}</span><span className={wideLabel}>Profil</span>{tip("Profil")}
        </button>
        <button type="button" onClick={() => setMore(!more)} aria-label="Lainnya" aria-expanded={more} aria-haspopup="menu" aria-controls="menu-lainnya" className={`group/item flex h-[52px] w-full items-center gap-4 px-6 text-left text-[15px] ${ring}`}>
          <span className="transition-transform duration-150 group-hover/item:scale-105"><NavIcon name="menu" filled={more} /></span><span className={wideLabel}>Lainnya</span>{!more && tip("Lainnya")}
        </button>
        {more && moreMenu("menu-lainnya", "bottom-14 left-3 hidden md:block", false)}
      </div>
    </aside>

    <nav aria-label="Navigasi bawah" className="fixed inset-x-0 bottom-0 z-50 flex border-t border-[#E2E5EA] bg-white px-[env(safe-area-inset-left)] pb-[env(safe-area-inset-bottom)] text-navy shadow-[0_-1px_3px_rgba(20,33,61,0.04)] md:hidden">
      {bar.map((item) => { const on = isActive(active, item.id); return <button key={item.id} type="button" onClick={() => open(item.id)} aria-label={labelOf(item)} aria-current={on ? "page" : undefined} className={`flex h-16 min-w-0 flex-1 flex-col items-center justify-center gap-1 ${ring} ${on ? "text-navy" : "text-[#5b6577]"}`}>
        <span className="relative"><NavIcon name={item.icon} filled={on} />{badgeEl(badge(item.id))}</span><span aria-hidden="true" className={`max-w-full truncate px-1 text-[10.5px] leading-none ${on ? "font-bold" : "font-medium"}`}>{item.label}</span></button>; })}
      <div ref={barRef} className="relative flex min-w-0 flex-1">
        <button type="button" onClick={() => setMore(!more)} aria-label="Lainnya" aria-expanded={more} aria-haspopup="menu" aria-controls="menu-lainnya-hp" className={`flex h-16 min-w-0 flex-1 flex-col items-center justify-center gap-1 ${ring} ${moreOn ? "text-navy" : "text-[#5b6577]"}`}>
          <span className="relative"><NavIcon name="menu" filled={moreOn} />{badgeEl(rest.some((i) => badge(i.id)) ? "•" : null)}</span><span aria-hidden="true" className={`text-[10.5px] leading-none ${moreOn ? "font-bold" : "font-medium"}`}>Lainnya</span></button>
      </div>
    </nav>
    {more && <div className="md:hidden">
      <button type="button" className="fixed inset-0 z-[60] bg-[#14213d]/20" aria-label="Tutup menu lainnya" onClick={() => setMore(false)} />
      <div ref={sheetRef} className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-[70]">{moreMenu("menu-lainnya-hp", "inset-x-0 bottom-0 w-full rounded-b-none", true)}</div>
    </div>}
  </>;
}

function Topbar({ title, go }: { title: string; go: (s: Screen) => void }) {
  const { role } = useRole();
  const { user } = useUser();
  const { setEventId, setExamId } = useSel();
  const notify = useContext(NotifyContext);
  const school = useSchoolName();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [muted, setMuted] = useState(alarmMuted);
  const toggleSound = () => { const next = !muted; setAlarmMuted(next); setMuted(next); if (!next) playAlarm(); };
  const staff = role !== "Siswa";
  // Pop-up "Tinjau": the new case's first event in the existing evidence page. Bell item: the case on the Indikasi page.
  const openToast = (c: CaseSummary) => { setExamId(c.exam_id); setEventId(c.first_event_id); go(role === "Pihak Sekolah" ? "indications" : "detail"); };
  const openCase = (c: CaseSummary) => { setNotificationsOpen(false); setExamId(c.exam_id); setEventId(c.first_event_id); go("indications"); };
  return <header className="sticky top-0 z-30 flex h-[calc(4rem+env(safe-area-inset-top))] items-center justify-between gap-3 border-b border-slate-200 bg-white px-[max(1rem,env(safe-area-inset-left))] pt-[env(safe-area-inset-top)] sm:px-8 md:h-[4.875rem] md:pt-0">
    <div className="flex min-w-0 items-center gap-3"><button type="button" onClick={() => go("beranda")} aria-label="Beranda EduAI" title="Beranda" className="shrink-0 md:hidden"><img src="/brand/smart-exam-integrity.webp" alt="" className="size-10" /></button><div className="min-w-0"><p data-page-title className="truncate font-sans font-semibold text-[1.2rem] leading-tight text-navy sm:text-[1.4rem]">{title}</p><p className="mt-0.5 truncate text-xs text-[#77818f] md:mt-1">{school ?? role}</p></div></div>
    <div className="flex items-center gap-3 sm:gap-4">
      {staff && <button onClick={() => { setNotificationsOpen(true); notify.markRead(); }} className="relative grid size-10 place-items-center rounded-lg border border-[#dfe2e5] bg-white text-navy hover:bg-paper md:size-9 md:rounded" aria-label="Buka notifikasi" aria-haspopup="dialog" aria-expanded={notificationsOpen}><Icon name="bell" size={19} />{notify.unread > 0 && <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-gold-500 ring-2 ring-white" />}</button>}
      {staff && user && <NotifPanel open={notificationsOpen} onClose={() => setNotificationsOpen(false)} cases={notify.items} summaries={notify.summaries} user={user}
        canOpenEvidence={mayOpenEvidence(role)} canMark={mayOpenEvidence(role)} canReview={role === "Pengawas" || role === "Penyelenggara Ujian" || role === "Admin"}
        onReview={openCase} onReport={(id) => { setNotificationsOpen(false); setExamId(id); go("report"); }} onOpenSummary={notify.openSummary} />}
      <div className="flex items-center gap-3"><div className="grid size-10 place-items-center rounded-full bg-gold-500 text-xs font-extrabold text-navy md:size-9">{initials(user?.name ?? "")}</div><div className="hidden sm:block"><p className="text-sm font-bold text-slate-800">{user?.name}</p><p className="text-xs text-slate-500">{role}</p></div></div>
    </div>
    {notify.summaryToast && <div role="alert" className="fixed right-4 top-20 z-[60] w-[min(20rem,calc(100vw-2rem))] rounded-md sm:right-6 border border-blue-300 bg-white p-4 shadow-lg"><div className="flex items-start gap-3"><span className="mt-0.5 text-blue-700"><Icon name="report" size={18} /></span><div className="min-w-0 flex-1"><p className="text-sm font-bold text-slate-900">{notify.summaryToast.kind === "pre_end" ? "Ringkasan indikasi · 10 menit lagi selesai" : "Ringkasan akhir indikasi"}</p><p className="mt-1 text-xs leading-5 text-slate-600">{notify.summaryToast.summary.exam_name} · {notify.summaryToast.summary.students.filter((s) => s.indications.length).length} siswa dengan indikasi tercatat</p><p className="mt-1 text-[11px] text-slate-400">Indikasi potensial untuk ditinjau — bukan keputusan pelanggaran.</p><div className="mt-3 flex gap-2"><Button className="h-8 px-3 text-xs" onClick={() => { const s = notify.summaryToast!; notify.dismissSummary(); notify.openSummary(s.exam_id); }}>Lihat ringkasan</Button><Button variant="ghost" className="h-8 px-3 text-xs" onClick={notify.dismissSummary}>Tutup</Button></div></div></div></div>}
    {notify.summaryExam !== null && <SummaryDialog examId={notify.summaryExam} onClose={notify.closeSummary} go={go} />}
    {notify.toast && <div role="alert" className="fixed bottom-20 right-4 md:bottom-6 md:right-6 z-[60] w-[min(20rem,calc(100vw-2rem))] rounded-md border border-amber-300 bg-white p-4 shadow-lg"><div className="flex items-start gap-3"><span className="mt-0.5 text-amber-600"><Icon name="bell" size={18} /></span><div className="min-w-0 flex-1"><p className="text-sm font-bold text-slate-900">Indikasi baru</p><p className="mt-1 text-xs leading-5 text-slate-600">{notify.toast.student?.name} · {eventTitle(notify.toast)} · {fmtTime(notify.toast.first_start_ts)}</p><p className="mt-1 text-[11px] text-slate-500">Satu notifikasi untuk siswa dan perilaku ini. Kejadian berikutnya hanya menambah hitungan di kasus yang sama.</p><p className="mt-1 text-[11px] text-slate-400">Perlu ditinjau pengawas — bukan keputusan pelanggaran.</p><div className="mt-3 flex gap-2"><Button className="h-8 px-3 text-xs" onClick={() => { const t = notify.toast!; notify.dismiss(); openToast(t); }}>Tinjau</Button><Button variant="ghost" className="h-8 px-3 text-xs" onClick={notify.dismiss}>Tutup</Button><button type="button" onClick={toggleSound} aria-pressed={muted} className="tap relative ml-auto self-center text-[11px] font-semibold text-slate-500 underline-offset-2 hover:underline">{muted ? "Bunyikan" : "Senyapkan bunyi"}</button></div></div></div></div>}
  </header>;
}

/** Consolidated exam summary: per student and behaviour, occurrences + rule + time range + evidence.
 *  Shows the stored summary (10 min before the end / final) or a live preview before it exists. */
function SummaryDialog({ examId, onClose, go }: { examId: number; onClose: () => void; go: (s: Screen) => void }) {
  const { setExamId, setEventId } = useSel();
  const data = usePoll(() => api.examSummary(examId), [examId], 15000);
  const d = data.data;
  const st = d?.summary.students ?? [];
  const withInd = st.filter((s) => s.indications.length);
  const clean = st.filter((s) => !s.indications.length && s.analysis === "analysed");
  const noData = st.filter((s) => s.analysis === "no_data");
  const ruleText = (r: { min_count: number; window_s: number | null; met: boolean; max_in_window: number }) =>
    r.met ? "Ambang terpenuhi" : `Di bawah ambang (${r.max_in_window}/${r.min_count}${r.window_s ? ` dalam ${Math.round(r.window_s / 60)} mnt` : ""})`;
  const open = (caseId: string) => { setExamId(examId); setEventId(caseId.slice(2)); onClose(); go("indications"); };
  return <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/60 p-4"><section role="dialog" aria-modal="true" aria-label="Ringkasan indikasi" className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg bg-white">
    <div className="flex items-start justify-between gap-3 border-b border-slate-100 p-5"><div><h2 className="font-bold text-slate-900">Ringkasan indikasi{d ? ` — ${d.summary.exam_name}` : ""}</h2><p className="mt-1 text-xs text-slate-500">{!d ? "Memuat..." : d.preview ? `Pratinjau langsung (belum dibuat). ${d.scheduled_at ? `Ringkasan otomatis pukul ${fmtTime(d.scheduled_at)} (10 menit sebelum selesai).` : "Jadwal selesai tidak diketahui: ringkasan dibuat saat ujian ditutup."}` : `${d.kind === "pre_end" ? "Dibuat 10 menit sebelum selesai" : "Ringkasan akhir"} · ${fmtTime(d.created_at)}`}</p></div><button onClick={onClose} aria-label="Tutup" className="tap relative"><Icon name="close" /></button></div>
    <div className="overflow-y-auto p-5">
      {data.error && <Notice tone="red">{data.error}</Notice>}
      <p className="mb-4 rounded-md bg-blue-50 p-3 text-xs leading-5 text-blue-900">{d?.summary.note ?? "Indikasi potensial untuk ditinjau pengawas, bukan bukti pelanggaran."} Satu kejadian = satu episode yang memenuhi aturan deteksi; frame berulang dan duplikat tidak dihitung ganda.</p>
      {d && withInd.length === 0 && <p className="rounded-md border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">Tidak ada indikasi tercatat pada ujian ini.</p>}
      <div className="space-y-4">{withInd.map((s) => <div key={s.student_id} className="rounded-md border border-slate-200"><div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5"><p className="text-sm font-semibold text-slate-900">{s.name}<span className="ml-2 text-xs font-normal text-slate-400">NIS {s.nis ?? "—"}</span></p><span className="text-xs text-slate-500">{s.rules_met} perilaku memenuhi ambang</span></div>
        <table className="w-full text-left text-xs"><tbody>{s.indications.map((i) => <tr key={i.case_id} className="border-t border-slate-50 first:border-t-0"><td className="px-4 py-2.5 font-medium text-slate-800">{i.label ?? i.indicator}</td><td className="px-2 py-2.5 font-semibold text-slate-900">{i.occurrences}×</td><td className="px-2 py-2.5"><Badge tone={i.rule.met ? "amber" : "gray"}>{ruleText(i.rule)}</Badge></td><td className="whitespace-nowrap px-2 py-2.5 text-slate-500">{fmtTime(i.first_ts)}{i.occurrences > 1 ? ` – ${fmtTime(i.last_ts)}` : ""}</td><td className="px-2 py-2.5 text-slate-500">{i.evidence_count} evidence{i.unreviewed ? ` · ${i.unreviewed} belum ditinjau` : ""}</td><td className="px-4 py-2.5 text-right"><button onClick={() => open(i.case_id)} className="font-semibold text-blue-700">Tinjau</button></td></tr>)}</tbody></table>
        {s.cannot_analyze.periods > 0 && <p className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-500">Tidak dapat dianalisis: {s.cannot_analyze.periods} periode ({fmtDuration(s.cannot_analyze.total_s)}) — kualitas video kurang, bukan perilaku.</p>}</div>)}</div>
      {d && (clean.length > 0 || noData.length > 0) && <div className="mt-4 space-y-1 text-xs text-slate-500">{clean.length > 0 && <p>Tanpa indikasi tercatat: {clean.map((s) => s.name).join(", ")}{clean.some((s) => s.cannot_analyze.periods) ? " (sebagian periode tidak dapat dianalisis)" : ""}.</p>}{noData.length > 0 && <p>Tidak ada data analisis AI (tidak hadir atau video tidak sampai): {noData.map((s) => s.name).join(", ")}.</p>}</div>}
      {d && d.summary.unsupported.length > 0 && <p className="mt-3 text-[11px] text-slate-400">Belum dapat dideteksi: {d.summary.unsupported.map((u) => `${u.behavior} — ${u.reason}`).join("; ")}</p>}
    </div></section></div>;
}

function AppShell({ children, active, go, title }: { children: ReactNode; active: Screen; go: (s: Screen) => void; title: string }) {
  return <div className="min-h-screen bg-paper"><Sidebar active={active} go={go} /><div className="pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0 md:pl-[72px]"><Topbar title={title} go={go} />{children}</div></div>;
}

function PageTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: ReactNode; description: string; action?: ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div>{eyebrow && <p className="brand-caps mb-2 text-xs font-semibold text-gold-700">{eyebrow}</p>}<h1 className="text-2xl leading-tight tracking-tight text-navy sm:text-[1.875rem]">{title}</h1><p className="mt-2 text-sm text-[#687483]">{description}</p></div>{action}</div>;
}

function greeting() { return greetingWib(); }

function Dashboard({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const kind = dashboardKind(role);
  if (kind === "siswa") return <StudentDashboard go={go} />;
  if (kind === "admin") return <AdminDashboard go={go} />;
  if (kind === "institusi") return <InstitutionDashboard go={go} role={role as "Penyelenggara Ujian" | "Pihak Sekolah"} />;
  return <SupervisorDashboard go={go} />;
}

/** Re-render every `every` ms so relative times ("5 mnt lalu") stay current. */
function useNow(every = 30_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), every); return () => window.clearInterval(t); }, [every]);
  return now;
}

// Dasbor pengawas (desain Figma "ProctorPortalDashboard"). Semua angka dari API; kosong = "Belum ada data".
// Hanya teks dan angka: tidak ada video atau audio di halaman ini.
// Diagram Admin dan Pengawas dipusatkan di Dasbor masing-masing. Halaman Monitoring, Indikasi, dan Riwayat tidak
// menampilkan diagram untuk kedua peran ini (peran lain tidak berubah). Laporan Sesi: diagramnya per sesi, jadi tidak
// dipindahkan; kedua peran ini melihat angkanya sebagai teks (StatRows).
const DASHBOARD_CHART_ROLES: Role[] = ["Pengawas", "Admin"];
const chartsOnDashboard = (role: Role) => DASHBOARD_CHART_ROLES.includes(role);

/** Diagram yang dipindahkan dari Monitoring, Indikasi, dan Riwayat. Komponen, API, dan rumusnya sama dengan halaman
 *  asalnya; klik bagian diagram membuka halaman Indikasi dengan filter yang sesuai (?jenis= / ?status=). */
function DashboardChartHub({ go, withStatusDonut, lead }: { go: (s: Screen) => void; withStatusDonut: boolean; lead?: ReactNode }) {
  const cases = usePoll(() => api.cases(), [], 15000);
  const exams = usePoll(() => api.exams(), [], 60000);
  // Monitoring: per sesi yang sedang berlangsung, sama seperti halaman Monitoring (siswa + 500 indikasi terbaru)
  const active = activeExams(exams.data ?? []);
  const activeIds = active.map((e) => e.id).join(",");
  const sessions = usePoll(() => Promise.all(active.map(async (e) => {
    const [students, ind] = await Promise.all([api.students(e.id), api.examEvents(e.id, { category: "indication", limit: 500 })]);
    return { exam: e, students, ind };
  })), [activeIds], 5000);
  // Riwayat: sama seperti halaman Riwayat (laporan setiap sesi yang sudah selesai)
  const history = usePoll(async () => {
    const finished = (await api.exams()).filter((e) => e.status === "Selesai");
    return Promise.all(finished.map((e) => api.report(e.id)));
  }, []);
  const rows = cases.data?.cases ?? [];
  const toIndications = (f: Filter) => {
    const { pathname, search, hash } = window.location;
    window.history.replaceState(window.history.state, "", pathname + filterQuery(f, search) + hash);
    go("indications");
  };
  // Pengawas: 2 + 2/sesi + 2 + 1 + 2 kartu = ganjil, jadi kartu terakhir (Ringkasan riwayat) memakai dua kolom.
  const spanLast = !withStatusDonut;
  const flat = "contents [&>div]:contents";       // komponen berisi dua kartu: tiap kartu menjadi satu sel grid
  return <section aria-labelledby="judul-diagram" className="chart-hub mt-8">
    <h2 id="judul-diagram" className="mb-3 text-[17px] leading-[1.3]">Diagram dan grafik</h2>
    <div className="grid gap-[18px] min-[900px]:grid-cols-2">
      {lead && <div className={flat}>{lead}</div>}
      {(sessions.data ?? []).map(({ exam: e, students, ind }) => { const win = examTimes(e); return <div key={e.id} className="contents">
        <h3 className="-mb-1.5 mt-1 text-[15px] font-semibold leading-snug text-navy min-[900px]:col-span-2">Pemantauan sesi · {e.name}{ind.events.length >= 500 && <span className="ml-2 text-xs font-normal text-[#8c621a]">Linimasa menampilkan 500 indikasi terbaru dari sesi ini.</span>}</h3>
        <div className={flat}><Suspense fallback={<><ChartSkeleton h={260} /><ChartSkeleton h={260} /></>}><MonitoringCharts status={monitorStatus(students)} timeline={sessionTimeline(ind.events, win.start, win.end)} /></Suspense></div>
      </div>; })}
      {withStatusDonut && <StatusDonut data={cases.data ? statusSummary(rows) : null} selected={null} onSelect={(st) => toIndications({ jenis: null, status: st })} onAll={() => go("indications")} />}
      <KindDonut slices={cases.data ? kindSlices(rows) : null} selected={null}
        onSelect={(sl) => toIndications({ jenis: sl.kinds.length === 1 ? sl.kinds[0] : null, status: null })} />
      <LoadDonut slices={cases.data && exams.data ? loadSlices(supervisorLoad(rows, exams.data)) : null} />
      <KindBarChart bars={cases.data ? kindBars(rows) : null} selected={null} onSelect={(k) => toIndications({ jenis: k, status: null })} />
      <div className={`${flat} ${spanLast ? "min-[900px]:[&>div>section:last-child]:col-span-2" : ""}`}><Suspense fallback={<><ChartSkeleton h={260} /><ChartSkeleton h={260} /></>}><HistoryChart data={history.data ? historyRows(history.data) : null} /></Suspense></div>
    </div>
  </section>;
}

function SupervisorDashboard({ go }: { go: (s: Screen) => void }) {
  const { user } = useUser();
  const { setExamId, setEventId } = useSel();
  const now = useNow();
  const d = usePoll(() => api.dashboard(), [], 10000);
  const s = d.data?.summary;
  const caseList = usePoll(() => api.cases(), [], 15000);
  const day = wibDate(now);
  // today's indications (WIB day) for the stacked hourly columns, same chart as Monitoring
  const dayStart = Date.parse(`${day}T00:00:00+07:00`);
  const todayEvents = usePoll(() => api.events({ category: "indication", since: new Date(dayStart).toISOString(), limit: 500 }), [dayStart], 30000);
  const breakdown = caseList.data && s?.cases_total != null ? caseStatusBreakdown(caseList.data.cases, s.cases_total) : null;
  const today = todayEvents.data ? { data: sessionTimeline(todayEvents.data.events, dayStart, Math.max(now, dayStart + 60_000)), capped: todayEvents.data.events.length >= 500 } : null;
  const exams = d.data?.exams ?? [];
  const active = activeExams(exams);
  const upcoming = upcomingExams(exams);
  const statusOf = new Map(exams.map((e) => [e.id, e.status]));
  const activeIds = active.map((e) => e.id).join(",");
  const rows = usePoll(() => Promise.all(active.map((e) => api.students(e.id).then((r) => [e.id, r] as const))), [activeIds], 10000);
  const gaps = new Map((rows.data ?? []).map(([id, r]) => [id, analysisGaps(r)]));
  // Kartu angka: hanya data yang sudah dimuat halaman ini. Siswa offline memakai rumus diagram Status siswa (monitorStatus).
  const live = (rows.data ?? []).map(([, r]) => monitorStatus(r));
  const liveTotal = live.reduce((a, m) => a + m.total, 0);
  const liveOffline = live.reduce((a, m) => a + (m.segments.find((x) => x.key === "offline")?.value ?? 0), 0);
  const unreviewedCases = breakdown ? breakdown.segments.find((x) => x.key === "belum")?.value ?? 0 : null;
  const dash = (v: number | null | undefined) => (v == null ? "—" : String(v));
  const kpis: [string, string][] = [
    [dash(s?.active_sessions ?? (d.data ? active.length : null)), "Sesi aktif"],
    [dash(rows.data ? liveTotal : null), "Siswa di sesi aktif"],
    [dash(rows.data ? liveTotal - liveOffline : null), "Siswa online"],
    [dash(rows.data ? liveOffline : null), "Siswa offline"],
    [todayEvents.data ? `${todayEvents.data.events.length}${todayEvents.data.events.length >= 500 ? "+" : ""}` : "—", "Deteksi hari ini"],
    [dash(unreviewedCases), "Kasus belum ditinjau"],
  ];
  const cases = (d.data?.recent_cases ?? []).slice(0, 3);
  const loading = d.loading && !d.data;
  const openExam = (id: number, screen: Screen) => { setExamId(id); go(screen); };
  const panel = "overflow-hidden rounded border border-line bg-white";
  const heading = (title: string, sub: string, action?: ReactNode) => <div className="flex min-h-[68px] items-start justify-between gap-3 border-b border-[#e4e6e8] px-[18px] py-4"><div><h2 className="text-[17px] leading-[1.3]">{title}</h2><p className="mt-1 text-xs text-[#89919d]">{sub}</p></div>{action}</div>;
  const link = (label: string, to: Screen) => <button onClick={() => go(to)} className="tap relative shrink-0 text-xs font-bold text-[#836713] underline underline-offset-3">{label}</button>;
  const empty = (text: string) => <div className="px-6 py-10 text-center"><p className="text-sm font-bold text-navy">{loading ? "Memuat…" : NO_DATA}</p>{!loading && <p className="mx-auto mt-1.5 max-w-72 text-xs leading-5 text-[#7d8794]">{text}</p>}</div>;

  return <AppShell active="dashboard" go={go} title="Dasbor"><main className="p-4 sm:p-8">
    <section className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
      <div><h1 className="text-[1.6rem] leading-[1.2] tracking-[-0.5px] sm:text-[30px]">{greeting()}, {user?.name.split(" ")[0] ?? ""}</h1><p className="mt-[7px] text-xs text-[#687483] sm:text-[13px]">Ringkasan ujian yang ditugaskan kepada Anda hari ini.</p></div>
    </section>
    {d.error && <div className="mt-4"><Notice tone="red">{d.error}</Notice></div>}

    <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 xl:grid-cols-6" aria-label="Ringkasan angka">{kpis.map(([value, label]) =>
      <section key={label} className="rounded-md border border-slate-200 bg-white p-4 sm:p-5"><p className="text-xl font-bold tabular-nums text-slate-900 sm:text-2xl">{value}</p><p className="mt-1 text-sm leading-5 text-slate-500">{label}</p></section>)}</div>

    <div className="mt-5 grid items-start gap-[18px] lg:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)]">
      <section className={panel}>
        {heading("Sesi aktif", "Ujian yang sedang ditugaskan kepada Anda", link("Lihat semua", "sessions"))}
        {active.length === 0 ? empty("Tidak ada sesi yang sedang berlangsung.") : active.map((e) => { const g = gaps.get(e.id); return (
          <article key={e.id} className="grid gap-[18px] border-b border-[#e5e7e9] px-[18px] py-[17px] last:border-b-0 sm:min-h-[137px] sm:grid-cols-[1fr_160px]">
            <div className="min-w-0">
              <span className="flex w-fit items-center gap-1.5 text-xs font-bold text-[#586474]"><i className="size-1.5 rounded-full bg-gold-500" />Berlangsung</span>
              <h3 className="mt-[7px] font-sans text-[15px] font-semibold leading-[1.35] text-[#273246]">{e.name}</h3>
              <p className="mt-[5px] flex flex-wrap items-center gap-2 text-xs text-[#798391]">{e.class_name || NO_DATA}<span className="size-[3px] rounded-full bg-[#aeb5bd]" />{examTime(e)}</p>
              {g?.label && <p className="mt-2.5"><Badge tone="gray">{g.label}</Badge></p>}
              <div className="mt-[15px] flex flex-wrap gap-5 text-xs text-[#7c8694]">
                <span><b className="mr-[3px] text-[13px] text-navy">{e.student_count}</b>Peserta</span>
                <span><b className="mr-[3px] text-[13px] text-navy">{e.online ?? 0}</b>Terhubung</span>
                <span><b className="mr-[3px] text-[13px] text-navy">{e.indications?.total ?? 0}</b>Indikasi</span>
              </div>
            </div>
            <div className="flex items-end justify-between gap-3 border-t border-[#e4e6e8] pt-3 sm:flex-col sm:items-end sm:border-l sm:border-t-0 sm:pl-[17px] sm:pt-0">
              <div className="sm:text-right"><small className="block text-xs text-[#8b949f]">Sisa waktu</small><strong className="mt-[3px] block text-sm text-navy">{remainingText(e, now)}</strong></div>
              <button onClick={() => openExam(e.id, "monitor")} className="flex min-h-[34px] w-[150px] items-center justify-center gap-1.5 rounded bg-navy text-xs font-bold text-white hover:bg-navy-2 sm:mt-auto">Buka pemantauan <Icon name="chevron" size={14} /></button>
            </div>
          </article>); })}
      </section>

      <div className="grid gap-[18px]">
        <section className={panel}>
          {heading("Ujian berikutnya", "Jadwal yang ditugaskan kepada Anda")}
          {upcoming.length === 0 ? empty("Belum ada ujian terjadwal.") : <table className="w-full border-collapse text-left">
            <thead><tr><th className="px-3.5 py-2.5">Waktu</th><th className="px-3.5 py-2.5">Ujian</th><th className="px-3.5 py-2.5">Kelas</th></tr></thead>
            <tbody>{upcoming.map((e) => <tr key={e.id} onClick={() => openExam(e.id, "waiting")} className="cursor-pointer border-t border-[#e5e7e9]">
              <td className="whitespace-nowrap px-3.5 py-3 text-xs text-[#536071]">{fmtDate(e.date)}<br />{e.start_time.replace(":", ".")} WIB</td>
              <td className="px-3.5 py-3 text-[13px] font-bold text-navy">{e.name}</td>
              <td className="px-3.5 py-3 text-xs text-[#536071]">{e.class_name || NO_DATA}</td></tr>)}</tbody>
          </table>}
        </section>

        <section className={panel}>
          {heading("Indikasi terbaru", "Aktivitas terbaru yang perlu ditinjau", link("Tinjau semua", "indications"))}
          {cases.length === 0 ? empty("Indikasi dari AI akan muncul di sini selama ujian berlangsung.") : cases.map((c) => (
            <button key={c.case_id} onClick={() => { setExamId(c.exam_id); setEventId(c.first_event_id); go("indications"); }} className="grid min-h-[70px] w-full grid-cols-[34px_1fr] items-center gap-[11px] border-b border-[#e5e7e9] px-4 py-3 text-left last:border-b-0 hover:bg-[#fbfaf7]">
              <span className="grid size-8 place-items-center rounded border border-[#dfd8bd] bg-[#faf7ea] text-[#806511]"><Icon name={indicatorIcon(c.indicator)} size={17} /></span>
              <span className="min-w-0"><strong className="block text-[13px] leading-[1.4] text-[#334054]">{eventTitle(c)} — {c.episode_count ?? c.event_count} kali</strong>
                <span className="mt-[5px] flex justify-between gap-3 text-xs text-[#7d8794]"><span className="truncate">{c.student?.name ?? NO_DATA}{c.exam?.name ? ` · ${c.exam.name}` : ""}</span><span className="shrink-0 text-[#9aa2ac]">{timeAgo(c.last_start_ts, now, { finished: statusOf.get(c.exam_id) === "Selesai" })}</span></span></span>
            </button>))}
          <p className="border-t border-[#e5e7e9] bg-[#fbfaf7] px-4 py-2.5 text-xs leading-5 text-[#687382]">Indikasi bukan bukti pelanggaran. Keputusan tetap di tangan pengawas.</p>
        </section>
      </div>
    </div>
    <DashboardChartHub go={go} withStatusDonut={false} lead={<Suspense fallback={<><ChartSkeleton h={260} /><ChartSkeleton h={260} /></>}><DashboardCharts breakdown={breakdown} today={today} /></Suspense>} />
  </main></AppShell>;
}

// Sesi Ujian (desain Figma "ExamSessionsPage"): pencarian, filter status, tabel; kartu bertumpuk di HP.
function Sessions({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const { setExamId } = useSel();
  const canCreate = role === "Admin";
  const list = usePoll(() => api.exams(), []);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>(ALL_STATUSES);
  const rows = filterSessions(list.data ?? [], q, status);
  const title = role === "Admin" ? "Daftar Ujian" : "Sesi Ujian";
  const desc = role === "Pengawas" ? "Sesi ujian yang ditugaskan kepada Anda." : role === "Admin" ? "Atur jadwal, peserta, pengawas, dan status ujian." : "Jadwal dan aktivitas ujian sekolah.";
  const open = (id: number) => { setExamId(id); go("exam-detail"); };
  const detail = (id: number, name: string) => <button onClick={() => open(id)} aria-label={`Lihat detail ${name}`} className="tap relative text-xs font-bold text-[#806511] underline underline-offset-3">Lihat detail</button>;
  const emptyText = list.loading && !list.data ? "Memuat…" : (list.data ?? []).length ? "Tidak ada sesi yang cocok dengan pencarian atau status ini." : NO_DATA;
  return <AppShell active="sessions" go={go} title={title}><main className="p-4 sm:p-8">
    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
      <div><h1 className="text-[1.6rem] leading-[1.2] tracking-[-0.5px] sm:text-[30px]">{title}</h1><p className="mt-[7px] text-xs text-[#687483]">{desc}</p></div>
      <div className="flex items-center gap-4"><span className="text-xs text-[#7b8593]" aria-live="polite">{list.data ? `${rows.length} sesi` : ""}</span>{canCreate && <Button icon="plus" onClick={() => go("create")}>Buat Ujian</Button>}</div>
    </div>
    {list.error && <div className="mt-4"><Notice tone="red">{list.error}</Notice></div>}
    <div className="mt-[25px] flex flex-col gap-3.5 rounded border border-line bg-white p-[15px] sm:flex-row sm:items-end">
      <label className="relative flex h-[42px] flex-1 items-center"><span className="sr-only">Cari sesi ujian</span><span className="absolute left-[13px] text-[#7c8795]"><Icon name="search" size={17} /></span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari nama ujian, mata pelajaran, atau kelas" className="h-[42px] w-full rounded border border-[#d9dde1] bg-white pl-10 pr-[13px] text-sm text-[#2f3a4b] outline-none focus:border-navy" /></label>
      <label className="grid gap-1.5 text-xs font-bold text-[#687382]">Status
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="h-[42px] rounded border border-[#d9dde1] bg-white pl-3 pr-8 text-sm font-normal text-[#344053] outline-none focus:border-navy">{STATUS_OPTIONS.map((o) => <option key={o}>{o}</option>)}</select></label>
    </div>
    <section className="mt-4 overflow-hidden rounded border border-line bg-white" aria-label="Daftar sesi ujian">
      {rows.length > 0 && <table className="hidden w-full border-collapse text-left lg:table">
        <thead><tr>{["Nama ujian", "Tanggal & waktu", "Durasi", "Peserta", "Pengawas", "Status", "Aksi"].map((h) => <th key={h} className="px-[15px] py-[13px]">{h}</th>)}</tr></thead>
        <tbody>{rows.map((e) => <tr key={e.id} className="border-t border-[#e5e7e9]">
          <td className="w-[27%] px-[15px] py-4"><strong className="block text-[13px] text-[#263246]">{e.name}</strong><span className="mt-1 block text-xs text-[#8b949f]">{[e.subject, e.class_name].filter(Boolean).join(" · ") || NO_DATA}</span></td>
          <td className="whitespace-nowrap px-[15px] py-4 text-[13px] text-[#657080]">{sessionDateText(e)}</td>
          <td className="whitespace-nowrap px-[15px] py-4 text-[13px] text-[#657080]">{e.duration_min} menit</td>
          <td className="whitespace-nowrap px-[15px] py-4 text-[13px] text-[#657080]">{e.student_count} siswa</td>
          <td className="px-[15px] py-4 text-[13px] text-[#657080]">{e.supervisor?.name ?? NO_DATA}</td>
          <td className="px-[15px] py-4"><Badge tone={sessionTone(e.status)}>{e.status}</Badge></td>
          <td className="px-[15px] py-4">{detail(e.id, e.name)}</td>
        </tr>)}</tbody>
      </table>}
      {rows.length > 0 && <ul className="divide-y divide-[#e5e7e9] lg:hidden">{rows.map((e) => <li key={e.id} className="px-4 py-4">
        <div className="flex items-start justify-between gap-3"><div className="min-w-0"><strong className="block text-[14px] text-[#263246]">{e.name}</strong><span className="mt-1 block text-xs text-[#8b949f]">{[e.subject, e.class_name].filter(Boolean).join(" · ") || NO_DATA}</span></div><Badge tone={sessionTone(e.status)}>{e.status}</Badge></div>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-[#657080] sm:grid-cols-4">
          <div><dt className="text-[#8b949f]">Tanggal & waktu</dt><dd className="mt-0.5 text-[#344053]">{sessionDateText(e)}</dd></div>
          <div><dt className="text-[#8b949f]">Durasi</dt><dd className="mt-0.5 text-[#344053]">{e.duration_min} menit</dd></div>
          <div><dt className="text-[#8b949f]">Peserta</dt><dd className="mt-0.5 text-[#344053]">{e.student_count} siswa</dd></div>
          <div><dt className="text-[#8b949f]">Pengawas</dt><dd className="mt-0.5 text-[#344053]">{e.supervisor?.name ?? NO_DATA}</dd></div>
        </dl>
        <div className="mt-3">{detail(e.id, e.name)}</div>
      </li>)}</ul>}
      {rows.length === 0 && <p className="px-5 py-14 text-center text-xs text-[#7c8694]">{emptyText}</p>}
    </section>
    {role === "Admin" && <p className="mt-3 text-xs text-[#8b949f]">Edit dan hapus ujian belum tersedia di backend.</p>}
  </main></AppShell>;
}

// Admin / organiser: per-exam Safe Exam Browser requirement. Keys are typed here and kept by the backend;
// students and supervisors never receive them.
function SebSettingsPanel({ examId }: { examId: number }) {
  const settings = usePoll(() => api.sebSettings(examId), [examId]);
  const [form, setForm] = useState<{ required: boolean; ck: string; bek: string; url: string } | null>(null);
  const [loaded, setLoaded] = useState<SebSettings | null>(null);
  const [msg, setMsg] = useState<[string, "blue" | "red"] | null>(null);
  if (settings.data && settings.data !== loaded) {
    setLoaded(settings.data);
    setForm({ required: settings.data.required, ck: settings.data.config_keys.join("\n"), bek: settings.data.browser_exam_keys.join("\n"), url: settings.data.config_url });
  }
  const split = (t: string) => t.split(/[\s,;]+/).filter(Boolean);
  const save = async () => {
    if (!form) return;
    try {
      await api.saveSebSettings(examId, { required: form.required, config_keys: split(form.ck), browser_exam_keys: split(form.bek), config_url: form.url.trim() });
      setMsg(["Pengaturan Safe Exam Browser disimpan.", "blue"]); void settings.reload();
    } catch (e) { setMsg([(e as Error).message, "red"]); }
  };
  if (settings.error) return <Notice tone="red">{settings.error}</Notice>;
  if (!form) return <p className="mt-3 text-sm text-slate-500">Memuat pengaturan...</p>;
  const area = "mt-1 w-full rounded-md border border-slate-200 p-2.5 font-mono text-xs outline-none focus:border-blue-500";
  return <div className="mt-4 space-y-4 text-sm" data-testid="seb-settings">
    <label className="flex items-start gap-3"><input type="checkbox" checked={form.required} onChange={(e) => setForm({ ...form, required: e.target.checked })} className="mt-0.5 size-5 accent-blue-600" /><span><span className="block font-semibold text-slate-800">Wajibkan Safe Exam Browser</span><span className="text-xs text-slate-500">Siswa hanya dapat masuk ruang ujian dari SEB dengan konfigurasi yang kuncinya terdaftar di bawah.</span></span></label>
    <label className="block"><span className="font-semibold text-slate-700">Config Key</span><span className="block text-xs text-slate-500">Satu per baris. Lihat di SEB Config Tool setelah berkas .seb disimpan. Sama untuk Windows, macOS, dan iOS.</span><textarea aria-label="Config Key" rows={2} value={form.ck} onChange={(e) => setForm({ ...form, ck: e.target.value })} className={area} /></label>
    <label className="block"><span className="font-semibold text-slate-700">Browser Exam Key (opsional)</span><span className="block text-xs text-slate-500">Berbeda untuk tiap versi dan sistem operasi SEB. Bila diisi, kunci ini juga harus cocok.</span><textarea aria-label="Browser Exam Key" rows={2} value={form.bek} onChange={(e) => setForm({ ...form, bek: e.target.value })} className={area} /></label>
    <label className="block"><span className="font-semibold text-slate-700">Alamat berkas konfigurasi .seb (opsional)</span><span className="block text-xs text-slate-500">Dipakai untuk tautan "Buka di Safe Exam Browser" bagi siswa.</span><input aria-label="Alamat berkas konfigurasi" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://ujian.sekolah.sch.id/seb/ujian.seb" className={area} /></label>
    <p className="text-xs text-slate-500">Alamat halaman ujian yang diterima: {loaded?.allowed_origins.join(", ") || "—"}. Siswa yang sedang di ruang ujian diperiksa ulang tiap 60 detik dengan kunci terbaru.</p>
    {msg && <Notice tone={msg[1]}>{msg[0]}</Notice>}
    <div className="flex justify-end"><Button onClick={() => void save()}>Simpan pengaturan SEB</Button></div>
  </div>;
}

function ExamDetail({ go }: { go: (s: Screen) => void }) {
  const [tab, setTab] = useState("Ringkasan");
  const { role } = useRole();
  const { examId } = useSel();
  const exam = usePoll(() => (examId ? api.exam(examId) : Promise.reject(new Error("Pilih sesi ujian terlebih dahulu."))), [examId]);
  const canMonitor = MONITOR_ROLES.includes(role);
  const students = usePoll(() => (examId && role !== "Siswa" ? api.students(examId) : Promise.resolve([] as StudentRow[])), [examId], 10000);
  const e = exam.data;
  const st = students.data ?? [];
  const joined = st.filter((s) => s.presence?.online).length;
  const deviceIssues = st.filter((s) => s.presence?.online && (s.presence.camera_on === false || s.presence.mic_on === false)).length;
  return <AppShell active="exam-detail" go={go} title="Detail Ujian"><main className="p-4 sm:p-8">
    <button onClick={() => go("sessions")} className="tap relative mb-5 flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-800"><Icon name="arrow" size={18} />Kembali ke daftar ujian</button>
    {exam.error && <Notice tone="red">{exam.error}</Notice>}
    {e && <>
      <div className="rounded-md border border-slate-200 bg-white p-6"><div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-start"><div><div className="flex items-center gap-3"><Badge tone={statusTone(e.status)}>{e.status}</Badge><span className="text-xs text-slate-400">Kode ujian EX-{e.id}</span></div><h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-900">{e.name}</h1><p className="mt-2 text-sm text-slate-500">{e.subject} • Kelas {e.class_name}</p></div><div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => go("students")}>Daftar Siswa</Button><Button variant="secondary" onClick={() => go("indications")}>Lihat Indikasi</Button><Button variant="secondary" onClick={() => go("report")}>Lihat Laporan</Button>{canMonitor && <Button icon="monitor" onClick={() => go("monitor")}>Mulai Monitoring</Button>}</div></div>
        <div className="mt-7 grid gap-4 border-t border-slate-100 pt-6 sm:grid-cols-2 lg:grid-cols-4">{[["Tanggal & waktu", `${fmtDate(e.date)}, ${e.start_time.replace(":", ".")}`, "calendar"], ["Durasi", `${e.duration_min} menit`, "clock"], ["Peserta", `${e.student_count} siswa`, "users"], ["Pengawas", e.supervisor?.name ?? "—", "shield"]].map(([k, v, i]) => <div key={k} className="flex gap-3"><div className="grid size-9 shrink-0 place-items-center rounded-md bg-slate-50 text-slate-500"><Icon name={i as IconName} size={17} /></div><div><p className="text-xs text-slate-400">{k}</p><p className="mt-1 text-sm font-semibold text-slate-800">{v}</p></div></div>)}</div>
      </div>
      <div className="mt-6 border-b border-slate-200"><div className="flex gap-7 overflow-x-auto">{["Ringkasan", "Peserta", "Pemantauan", "Laporan"].map((x) => <button key={x} onClick={() => setTab(x)} className={`whitespace-nowrap border-b-2 px-1 pb-3 text-sm font-semibold ${tab === x ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500"}`}>{x}</button>)}</div></div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_.8fr]"><section className="rounded-md border border-slate-200 bg-white p-6"><h2 className="font-bold text-slate-900">{tab}</h2>{tab === "Ringkasan" ? <><p className="mt-3 text-sm leading-7 text-slate-600">{e.description} Seluruh peserta wajib mengaktifkan kamera dan mikrofon selama sesi.</p><div className="mt-6 rounded-md bg-blue-50 p-4"><div className="flex gap-3"><span className="text-blue-700"><Icon name="shield" size={19} /></span><div><p className="text-sm font-bold text-blue-900">Pemantauan bertanggung jawab</p><p className="mt-1 text-xs leading-5 text-blue-800">AI hanya memberikan Indikasi dan bukti pendukung. Pengawas meninjau bukti sebelum menentukan keputusan.</p></div></div></div></> : tab === "Peserta" ? <div className="mt-4 divide-y divide-slate-100">{st.map((s) => <div key={s.id} className="flex items-center justify-between py-2.5 text-sm"><span className="font-semibold text-slate-800">{s.name}</span><span className="text-xs text-slate-500">NIS {s.nis ?? "—"}</span></div>)}</div> : <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 p-10 text-center"><Icon name={tab === "Laporan" ? "report" : "monitor"} size={28} /><p className="mt-3 text-sm font-semibold text-slate-700">{tab === "Laporan" ? (e.status === "Selesai" ? "Laporan siap ditinjau" : "Laporan lengkap tersedia setelah ujian selesai") : e.monitoring_active ? `Pemantauan AI aktif (${e.analysis_source === "livekit" ? "OpenVidu" : "frame browser"})` : "Pemantauan AI belum dimulai"}</p><Button variant="secondary" className="mt-4" onClick={() => go(tab === "Laporan" ? "report" : "monitor")}>{tab === "Laporan" ? "Buka laporan" : "Buka pemantauan"}</Button></div>}</section>
        <aside className="rounded-md border border-slate-200 bg-white p-6"><h2 className="font-bold text-slate-900">Kesiapan sesi</h2><div className="mt-5 space-y-4">{[["Peserta terdaftar", String(e.student_count), "green"], ["Sudah terhubung", String(joined), "green"], ["Masalah perangkat", String(deviceIssues), deviceIssues ? "amber" : "gray"], ["Belum bergabung", String(Math.max(0, e.student_count - joined)), "gray"]].map(([k, v, t]) => <div key={k} className="flex items-center justify-between"><span className="text-sm text-slate-500">{k}</span><Badge tone={t as "green" | "amber" | "gray"}>{v}</Badge></div>)}</div>{canMonitor && <Button variant="secondary" className="mt-6 w-full" onClick={() => go("waiting")}>Periksa ruang tunggu</Button>}</aside></div>
      <section className="mt-6 rounded-md border border-slate-200 bg-white p-6"><div className="flex flex-wrap items-center gap-3"><span className="text-blue-700"><Icon name="shield" size={19} /></span><h2 className="font-bold text-slate-900">Keamanan ujian: Safe Exam Browser</h2><Badge tone={e.seb?.required ? (e.seb.ready ? "green" : "amber") : "gray"}>{e.seb?.required ? "Wajib" : "Tidak diwajibkan"}</Badge></div>{(role === "Admin" || role === "Penyelenggara Ujian") ? <SebSettingsPanel examId={e.id} /> : <p className="mt-3 text-sm text-slate-500">{e.seb?.required ? "Siswa hanya dapat masuk dari Safe Exam Browser dengan konfigurasi yang ditetapkan admin. Status tiap siswa tampil di halaman Pemantauan." : "Ujian ini tidak mewajibkan Safe Exam Browser."}</p>}</section>
    </>}
  </main></AppShell>;
}

function WaitingRoom({ go }: { go: (s: Screen) => void }) {
  const { exam } = useCurrentExam();
  const students = usePoll(() => (exam ? api.students(exam.id) : Promise.resolve([] as StudentRow[])), [exam?.id], 5000);
  const [err, setErr] = useState("");
  const rows = students.data ?? [];
  const [q, setQ] = useState("");
  const statusOf = (s: StudentRow) => !s.presence?.online ? "Belum bergabung" : s.presence.camera_on === false ? "Masalah kamera" : s.presence.mic_on === false ? "Masalah mikrofon" : "Siap";
  const joined = rows.filter((s) => s.presence?.online).length;
  const ready = rows.filter((s) => statusOf(s) === "Siap").length;
  const issues = rows.filter((s) => ["Masalah kamera", "Masalah mikrofon"].includes(statusOf(s))).length;
  const start = async () => {
    if (!exam) return;
    try { const r = await api.startMonitoring(exam.id); if (r.note) alert(r.note); go("monitor"); } catch (e) { setErr((e as Error).message); }
  };
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(t);
  }, []);
  const minsToStart = exam ? Math.round((examWindow(exam).start.getTime() - now) / 60000) : 0;
  return <AppShell active="waiting" go={go} title="Ruang Tunggu Ujian"><main className="p-4 sm:p-8">
    <PageTitle eyebrow={exam ? (minsToStart > 0 ? `Mulai dalam ${minsToStart} menit` : exam.status) : undefined} title="Ruang Tunggu Ujian" description={exam ? `${exam.name} • ${fmtDate(exam.date)}, ${exam.start_time.replace(":", ".")} WIB` : "Memuat..."} action={<Button icon="monitor" disabled={!exam || exam.status !== "Sedang Berlangsung"} onClick={start}>Mulai Pemantauan Ujian</Button>} />
    {err && <Notice tone="red">{err}</Notice>}
    <div className="overflow-x-auto rounded-md border border-slate-200 bg-white"><div className="flex min-w-[620px] divide-x divide-slate-200">{[[`${joined}/${rows.length}`, "Sudah bergabung", "users", "blue"], [String(ready), "Siap mengikuti", "check", "green"], [String(issues), "Masalah perangkat", "camera", "amber"], [String(rows.length - joined), "Belum bergabung", "clock", "gray"]].map(([n, l, i, t]) => <div key={l} className="flex flex-1 items-center gap-3 px-4 py-3"><span className={t === "amber" ? "text-amber-600" : t === "green" ? "text-emerald-600" : "text-slate-400"}><Icon name={i as IconName} size={17} /></span><div><p className="text-lg font-bold leading-5 text-slate-900">{n}</p><p className="mt-0.5 whitespace-nowrap text-xs text-slate-500">{l}</p></div></div>)}</div></div>
    <section className="mt-6 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex flex-col gap-3 border-b border-slate-100 p-5 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="font-bold text-slate-900">Status peserta</h2><p className="mt-1 text-xs text-slate-500">Status diperbarui otomatis dari perangkat siswa setiap 5 detik.</p></div><div className="relative"><span className="absolute left-3 top-2.5 text-slate-400"><Icon name="search" size={17} /></span><input value={q} onChange={(e) => setQ(e.target.value)} className="h-10 rounded-md border border-slate-200 pl-9 pr-3 text-sm" placeholder="Cari siswa" /></div></div><div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Siswa</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Kamera</th><th className="px-5 py-3">Mikrofon</th><th className="px-5 py-3">Koneksi</th><th className="px-5 py-3">Persetujuan</th></tr></thead><tbody>{rows.filter((r) => r.name.toLowerCase().includes(q.toLowerCase())).map((r) => { const s = statusOf(r); const on = r.presence?.online; return <tr key={r.id} className="border-t border-slate-100"><td className="px-5 py-4"><p className="font-semibold text-slate-800">{r.name}</p><p className="text-xs text-slate-400">{r.nis}</p></td><td className="px-5 py-4"><Badge tone={s === "Siap" ? "green" : s === "Belum bergabung" ? "gray" : "amber"}>{s}</Badge></td><td className="px-5 py-4 text-slate-600">{on ? (r.presence?.camera_on ? "Aktif" : "Tidak aktif") : "—"}</td><td className="px-5 py-4 text-slate-600">{on ? (r.presence?.mic_on ? "Aktif" : "Tidak aktif") : "—"}</td><td className="px-5 py-4 text-slate-600">{on ? `${r.presence?.connection === "baik" ? "Stabil" : r.presence?.connection ?? "—"}${r.presence?.rtt_ms ? ` · ${Math.round(r.presence.rtt_ms)} ms` : ""}` : "—"}</td><td className="px-5 py-4 text-slate-600">{r.consent ? "Sudah" : "Belum"}</td></tr>; })}</tbody></table></div></section>
    {issues > 0 && <div className="mt-5 flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-4"><span className="text-amber-600"><Icon name="bell" size={18} /></span><div><p className="text-sm font-bold text-amber-900">{issues} peserta memerlukan bantuan</p><p className="mt-1 text-xs leading-5 text-amber-800">Pastikan masalah kamera dan mikrofon diselesaikan sebelum memulai pemantauan.</p></div></div>}
  </main></AppShell>;
}

function AdminCreateExam({ go }: { go: (s: Screen) => void }) {
  const { setExamId } = useSel();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [subject, setSubject] = useState("");
  const [className, setClassName] = useState("XI IPA 2");
  const [date, setDate] = useState("");
  const [start, setStart] = useState("08:00");
  const [duration, setDuration] = useState("60");
  const [supervisor, setSupervisor] = useState("");
  const [status, setStatus] = useState<Exam["status"]>("Draft");
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const supervisors = usePoll(() => api.users("pengawas"), []);
  const studentsList = usePoll(() => api.users("siswa"), []);
  const options = studentsList.data ?? [];
  const supName = supervisors.data?.find((s) => String(s.id) === supervisor)?.name;
  const toggle = (id: number) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const submit = async () => {
    if (!name || !description || !date || !start || !duration || !supervisor || selected.length === 0) { setError("Lengkapi seluruh field wajib dan pilih minimal satu peserta."); return; }
    setBusy(true);
    try {
      const e = await api.createExam({ name, description, subject, class_name: className, date, start_time: start, duration_min: Number(duration), status, supervisor_id: Number(supervisor), student_ids: selected });
      setExamId(e.id);
      go("sessions");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return <AppShell active="create" go={go} title="Create Ujian"><main className="mx-auto max-w-6xl p-4 sm:p-8">
    <button onClick={() => go("sessions")} className="tap relative mb-5 flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-800"><Icon name="arrow" size={18} />Kembali ke Daftar Ujian</button>
    <PageTitle eyebrow="Khusus Admin" title="Create Ujian" description="Tentukan jadwal, peserta yang diizinkan, dan pengawas sebelum menerbitkan ujian." />
    {error && <div role="alert" className="mb-5 flex gap-3 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm font-semibold text-amber-900"><Icon name="bell" size={18} />{error}</div>}
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]"><div className="space-y-6">
      <section className="rounded-md border border-slate-200 bg-white p-6"><div className="mb-6 flex items-center gap-3"><div className="grid size-9 place-items-center rounded-md bg-blue-50 text-blue-700"><Icon name="file" size={18} /></div><div><h2 className="font-bold text-slate-900">Informasi ujian</h2><p className="text-xs text-slate-500">Field bertanda wajib harus diisi.</p></div></div><div className="grid gap-5 sm:grid-cols-2"><label className="block sm:col-span-2"><span className="mb-2 block text-sm font-semibold text-slate-700">Nama Ujian *</span><input value={name} onChange={(e) => setName(e.target.value)} className="h-11 w-full rounded-md border border-slate-200 px-3.5 text-sm outline-none focus:border-blue-500" placeholder="Contoh: Ujian Akhir Matematika XI" /></label><label className="block sm:col-span-2"><span className="mb-2 block text-sm font-semibold text-slate-700">Deskripsi *</span><textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="w-full resize-none rounded-md border border-slate-200 p-3.5 text-sm outline-none focus:border-blue-500" placeholder="Jelaskan materi dan ketentuan ujian" /></label><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Mata pelajaran</span><input value={subject} onChange={(e) => setSubject(e.target.value)} className="h-11 w-full rounded-md border border-slate-200 px-3.5 text-sm" placeholder="Matematika" /></label><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Kelas</span><input value={className} onChange={(e) => setClassName(e.target.value)} className="h-11 w-full rounded-md border border-slate-200 px-3.5 text-sm" /></label><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Tanggal Ujian *</span><input value={date} onChange={(e) => setDate(e.target.value)} type="date" className="h-11 w-full rounded-md border border-slate-200 px-3 text-sm" /></label><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Jam Mulai *</span><input value={start} onChange={(e) => setStart(e.target.value)} type="time" className="h-11 w-full rounded-md border border-slate-200 px-3 text-sm" /></label><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Durasi *</span><div className="flex"><input value={duration} onChange={(e) => setDuration(e.target.value)} type="number" min="1" className="h-11 min-w-0 flex-1 rounded-l-md border border-slate-200 px-3 text-sm" /><span className="grid h-11 place-items-center rounded-r-md border border-l-0 border-slate-200 bg-slate-50 px-4 text-sm text-slate-500">menit</span></div></label><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Status Ujian *</span><select value={status} onChange={(e) => setStatus(e.target.value as Exam["status"])} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"><option>Draft</option><option>Terjadwal</option><option>Sedang Berlangsung</option><option>Selesai</option></select></label></div></section>
      <section className="rounded-md border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-5"><div><h2 className="font-bold text-slate-900">Peserta yang diizinkan</h2><p className="mt-1 text-xs text-slate-500">Hanya siswa terpilih yang akan melihat ujian ini.</p></div><Badge tone={selected.length ? "blue" : "gray"}>{selected.length} dipilih</Badge></div><label className="flex cursor-pointer items-center gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700"><input type="checkbox" checked={options.length > 0 && selected.length === options.length} onChange={() => setSelected(selected.length === options.length ? [] : options.map((o) => o.id))} className="size-4 accent-blue-700" />Pilih semua</label><div className="grid sm:grid-cols-2">{options.map((student) => <label key={student.id} className="flex cursor-pointer items-center gap-3 border-b border-slate-100 px-5 py-4 text-sm text-slate-700 hover:bg-slate-50"><input type="checkbox" checked={selected.includes(student.id)} onChange={() => toggle(student.id)} className="size-4 accent-blue-700" /><span>{student.name} • NIS {student.nis ?? "—"}</span></label>)}</div></section>
    </div><aside className="h-fit space-y-5"><section className="rounded-md border border-slate-200 bg-white p-5"><h2 className="font-bold text-slate-900">Penugasan pengawas</h2><p className="mt-1 text-xs leading-5 text-slate-500">Pengawas hanya dapat melihat sesi yang ditugaskan.</p><label className="mt-5 block"><span className="mb-2 block text-sm font-semibold text-slate-700">Pilih Pengawas *</span><select value={supervisor} onChange={(e) => setSupervisor(e.target.value)} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"><option value="">Pilih pengawas</option>{(supervisors.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label></section><section className="rounded-md border border-blue-100 bg-blue-50 p-5"><h3 className="font-bold text-blue-900">Ringkasan akses</h3><ul className="mt-4 space-y-3 text-xs leading-5 text-blue-800"><li>{selected.length} peserta dipilih</li><li>{supName || "Pengawas belum dipilih"}</li><li>Status: {status}</li><li>Jadwal ditentukan Admin dan tidak dapat diubah siswa.</li></ul></section></aside></div>
    <div className="mt-6 flex justify-end gap-3 border-t border-slate-200 pt-6"><Button variant="secondary" onClick={() => go("sessions")}>Batal</Button><Button disabled={busy} onClick={submit}>{busy ? "Menyimpan..." : "Buat Ujian"}</Button></div>
  </main></AppShell>;
}

function StudentHeader({ step }: { step?: number }) {
  const { user } = useUser();
  return <header className="flex h-18 items-center justify-between border-b border-slate-200 bg-white px-5 sm:px-10"><Logo /><div className="hidden items-center gap-3 sm:flex"><div className="grid size-8 place-items-center rounded-full bg-navy text-xs font-semibold text-gold-300">{initials(user?.name ?? "")}</div><div><p className="text-sm font-bold text-slate-800">{user?.name}</p><p className="text-xs text-slate-500">NIS {user?.nis ?? "—"}</p></div></div>{step && <div className="text-xs font-semibold text-slate-500 sm:hidden">Langkah {step} dari 2</div>}</header>;
}

function Consent({ go }: { go: (s: Screen) => void }) {
  const [agreed, setAgreed] = useState(false);
  const [audio, setAudio] = useState(false);          // optional, off by default
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { examId } = useSel();
  const jitsiServer = usePoll(() => api.jitsiConfig(), []);
  const jitsiText = jitsiServer.error ? JITSI_NOTICE_UNKNOWN : jitsiNotice(jitsiServer.data);
  const submit = async () => {
    if (!examId) return setError("Pilih ujian dari halaman Ujian Saya terlebih dahulu.");
    setBusy(true);
    try { await api.consent(examId, audio); go("exam"); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  // Formulir persetujuan resmi: satu kolom baca, bagian bernomor dipisah garis tipis, pernyataan persetujuan di akhir.
  // Isi kebijakan sama seperti sebelumnya (EVIDENCE_NOTICE, pemberitahuan Jitsi); hanya tata letaknya yang berubah.
  const sections: [string, ReactNode][] = [
    ["Data yang Dikumpulkan", "Gambar kamera selama ujian, status kamera/mikrofon, dan kualitas koneksi."],
    ["Tujuan Penggunaan", "Mendukung pengawas dalam meninjau jalannya ujian secara bertanggung jawab."],
    ["Analisis AI", "Keberadaan wajah, jumlah orang, arah kepala, gerak mulut, dan objek menyerupai ponsel. Suara hanya dianalisis jika Anda menyetujui pilihan di bawah."],
    ["Akses dan Masa Penyimpanan", EVIDENCE_NOTICE],
    ...(jitsiText ? [["Server Video", jitsiText] as [string, ReactNode]] : []),
  ];
  const canSubmit = agreed && !busy && !jitsiServer.loading;
  return <div className="min-h-screen bg-white sm:bg-paper"><StudentHeader step={2} /><main className="mx-auto w-full max-w-[46rem] sm:px-6 sm:py-12">
    <article aria-labelledby="judul-persetujuan" className="bg-white px-5 pb-6 pt-8 sm:rounded-sm sm:border sm:border-[#dfe2e5] sm:px-12 sm:py-11">
      <header className="border-b-2 border-navy pb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gold-700">Langkah 2 dari 2</p>
        <h1 id="judul-persetujuan" className="mt-2 font-sans text-[1.65rem] font-semibold leading-tight text-navy sm:text-[2rem]">Persetujuan Perekaman</h1>
        <p className="mt-3 text-[15px] leading-7 text-slate-600">Untuk mendukung pengawasan ujian, video kamera Anda dianalisis oleh AI selama sesi berlangsung untuk memberikan Indikasi kepada pengawas. Kamera dan mikrofon dapat disiarkan langsung ke pengawas.</p>
      </header>

      <section aria-labelledby="judul-informasi" className="mt-7">
        <h2 id="judul-informasi" className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Informasi perekaman</h2>
        <ol className="mt-3 border-b border-[#e3e5e8]">
          {sections.map(([title, copy], n) => <li key={title} className="grid grid-cols-[1.75rem_1fr] gap-x-1 border-t border-[#e3e5e8] py-5 sm:grid-cols-[2.25rem_1fr] sm:gap-x-2">
            <span aria-hidden="true" className="text-[15px] font-semibold tabular-nums text-gold-700">{n + 1}.</span>
            <div><h3 className="text-base font-semibold text-navy">{title}</h3><p className="mt-1.5 text-[15px] leading-7 text-slate-700">{copy}</p></div>
          </li>)}
        </ol>
        <p className="mt-6 border-l-2 border-gold-500 pl-4 text-sm leading-6 text-slate-700"><strong className="font-semibold text-navy">Perlu diketahui:</strong> AI hanya memberikan Indikasi. Setiap keputusan akhir selalu dibuat oleh pengawas setelah meninjau bukti. Video yang gelap atau buram dicatat sebagai "tidak dapat dianalisis", bukan pelanggaran.</p>
      </section>

      <section aria-labelledby="judul-pernyataan" className="mt-9 border border-[#d9dce1] bg-[#fbfaf7] p-5 sm:p-6">
        <h2 id="judul-pernyataan" className="text-base font-semibold text-navy">Pernyataan Persetujuan</h2>
        <label className="mt-4 flex cursor-pointer items-start gap-3.5"><input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} aria-describedby="wajib-persetujuan" className="mt-0.5 size-5 shrink-0 accent-[#14213d]" /><span><span className="block text-[15px] font-semibold leading-6 text-slate-900">Saya telah membaca dan menyetujui pemberitahuan perekaman dan analisis data.</span><span id="wajib-persetujuan" className="mt-1 block text-[13px] leading-5 text-slate-600">Wajib. Persetujuan diperlukan untuk mengikuti ujian ini.</span></span></label>
        <div className="my-5 border-t border-[#e3e5e8]" />
        <label className="flex cursor-pointer items-start gap-3.5"><input type="checkbox" role="switch" aria-checked={audio} checked={audio} onChange={(e) => setAudio(e.target.checked)} className="mt-0.5 size-5 shrink-0 accent-[#14213d]" /><span><span className="block text-[15px] font-semibold leading-6 text-slate-900">Opsional: saya setuju suara mikrofon dianalisis di perangkat saya.</span><span className="mt-1 block text-[13px] leading-5 text-slate-600">Model AI di browser ini menilai apakah terdengar suara bicara, bisikan, atau musik/TV. Yang dikirim ke EduAI hanya tiga angka skor; audio tidak direkam, tidak disimpan, dan tidak dikirim. Jika terdengar suara bicara saat mulut Anda tampak diam, pengawas menerima indikasi untuk ditinjau, bukan keputusan pelanggaran. Suara orang lain di sekitar Anda juga ikut dinilai, jadi beri tahu mereka. Ujian tetap dapat diikuti tanpa pilihan ini.</span></span></label>
      </section>

      {error && <p role="alert" className="mt-5 border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">{error}</p>}
      <div className="sticky bottom-0 -mx-5 mt-7 flex flex-col-reverse gap-3 border-t border-[#e3e5e8] bg-white px-5 pb-[max(1rem,env(safe-area-inset-bottom))] pt-4 sm:static sm:mx-0 sm:flex-row sm:items-center sm:justify-between sm:border-0 sm:px-0 sm:pb-0 sm:pt-0">
        <p aria-live="polite" className="text-[13px] leading-5 text-slate-500">{agreed ? "Anda dapat melanjutkan ke ruang ujian." : "Centang pernyataan wajib untuk melanjutkan."}</p>
        <Button disabled={!canSubmit} onClick={submit} className="h-12 w-full shrink-0 sm:h-11 sm:w-auto">Setuju & Masuk Ujian <Icon name="chevron" size={17} /></Button>
      </div>
    </article>
  </main></div>;
}

// Step 0 when the exam requires Safe Exam Browser. The lockdown comes from SEB and its configuration;
// this page only asks the backend whether this browser is that SEB, and never opens the exam otherwise.
async function checkSeb(examId: number): Promise<SebResult> {
  return api.verifySeb(examId, await readSeb());
}

function SebCheck({ go }: { go: (s: Screen) => void }) {
  const { examId } = useSel();
  const exam = usePoll(() => (examId ? api.exam(examId) : Promise.reject(new Error("Pilih ujian dari halaman Ujian Saya terlebih dahulu."))), [examId]);
  const check = usePoll(() => (examId ? checkSeb(examId) : Promise.reject(new Error("Pilih ujian dari halaman Ujian Saya terlebih dahulu."))), [examId]);
  const [busy, setBusy] = useState(false);
  const result: SebResult | null = check.data;
  const error = check.error;
  const run = async () => { setBusy(true); check.setData(null); await check.reload(); setBusy(false); };
  const launch = sebLaunchLink(exam.data?.seb?.config_url);
  const ok = !!result?.verified;
  return <div className="min-h-screen bg-slate-50"><StudentHeader /><main className="mx-auto max-w-3xl p-5 py-10 sm:py-16">
    <section className="rounded-md border border-slate-200 bg-white p-6 sm:p-10">
      <div className={`grid size-12 place-items-center rounded-md ${ok ? "bg-emerald-50 text-emerald-700" : "bg-blue-50 text-blue-700"}`}><Icon name="shield" size={25} /></div>
      <p className="mt-6 text-xs font-bold uppercase tracking-widest text-blue-700">Keamanan ujian</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">Safe Exam Browser</h1>
      <p className="mt-3 leading-7 text-slate-600">{exam.data?.name ?? "Ujian ini"} wajib dikerjakan di Safe Exam Browser (SEB). SEB membuka ujian dalam layar penuh, tanpa navigasi browser, dan membatasi perpindahan ke aplikasi atau situs lain sesuai konfigurasi sekolah.</p>
      <div role="status" className={`mt-6 rounded-md border p-4 text-sm leading-6 ${busy || !result && !error ? "border-slate-200 bg-slate-50 text-slate-600" : ok ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-red-200 bg-red-50 text-red-800"}`}>
        {busy ? "Memeriksa Safe Exam Browser..." : error ? error : result ? <><strong className="block">{result.state ? SEB_STATE_LABEL[result.state] : "Tidak diwajibkan"}</strong>{result.message}</> : "Memeriksa Safe Exam Browser..."}
      </div>
      {!busy && result && !ok && result.state === "not_seb" && <div className="mt-5 space-y-2 text-sm leading-6 text-slate-600"><p><strong className="text-slate-800">Cara masuk:</strong> tutup browser ini, lalu buka ujian melalui Safe Exam Browser dengan konfigurasi dari sekolah.</p>{launch ? <p><a className="font-semibold text-blue-700 underline" href={launch}>Buka di Safe Exam Browser</a> (SEB harus sudah terpasang di perangkat ini).</p> : <p>Minta berkas konfigurasi SEB (.seb) kepada admin atau pengawas.</p>}<p className="text-xs text-slate-500">Mode layar penuh browser biasa tidak menggantikan SEB.</p></div>}
      {!busy && result?.state === "key_mismatch" && <p className="mt-5 text-sm leading-6 text-slate-600">Gunakan berkas konfigurasi SEB terbaru dari sekolah untuk ujian ini, lalu buka ulang. Jika masih gagal, hubungi pengawas.</p>}
      <div className="mt-7 flex flex-wrap justify-end gap-3"><Button variant="secondary" onClick={() => go("my-exams")}>Kembali</Button>{!ok && <Button variant="secondary" disabled={busy} onClick={() => void run()}>Periksa lagi</Button>}<Button disabled={!ok || busy} onClick={() => go("device")}>Lanjut ke Cek Perangkat <Icon name="chevron" size={17} /></Button></div>
    </section>
  </main></div>;
}

function Device({ go }: { go: (s: Screen) => void }) {
  const { user } = useUser();
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [camError, setCamError] = useState("");
  const [latency, setLatency] = useState<number | null | undefined>(undefined);
  const level = useMicLevel(stream);
  const [heardMic, setHeardMic] = useState(false);
  const videoRef = useVideo(stream);
  useEffect(() => {
    let s: MediaStream | null = null;
    let cancelled = false;
    navigator.mediaDevices?.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 } }, audio: true })
      .then((m) => { if (cancelled) { m.getTracks().forEach((t) => t.stop()); return; } s = m; setStream(m); })
      .catch((e) => setCamError(mediaErrorMessage(e)));
    void measureLatency().then(setLatency);
    return () => { cancelled = true; s?.getTracks().forEach((t) => t.stop()); };
  }, []);
  if (level > 0.08 && !heardMic) setHeardMic(true);
  const camOk = !!stream?.getVideoTracks()[0];
  const micOk = !!stream?.getAudioTracks()[0];
  const netOk = latency != null;
  const bars = Array.from({ length: 12 }, (_, i) => Math.max(2, Math.round(level * 14 * (0.6 + 0.4 * Math.sin(i + level * 10) ** 2))));
  return <div className="min-h-screen bg-slate-50"><StudentHeader step={1} /><main className="mx-auto max-w-5xl p-5 py-10">
    <div className="mb-8 text-center"><p className="text-xs font-bold uppercase tracking-widest text-blue-700">Langkah 1 dari 2</p><h1 className="mt-2 text-3xl font-bold text-slate-900">Cek Perangkat</h1><p className="mt-2 text-slate-500">Pastikan perangkat Anda siap sebelum masuk ke ruang ujian.</p></div>
    <div className="grid gap-5 lg:grid-cols-[1.4fr_.8fr]">
      <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="relative flex aspect-video items-center justify-center bg-slate-800">{camOk ? <video ref={videoRef} muted playsInline className="absolute inset-0 size-full -scale-x-100 object-cover" /> : <div className="grid size-24 place-items-center rounded-full bg-white/10 text-2xl font-bold text-white ring-1 ring-white/20">{initials(user?.name ?? "")}</div>}<div className="absolute right-4 top-4"><Badge tone={camOk ? "green" : "amber"}><span className={`size-1.5 rounded-full ${camOk ? "bg-emerald-500" : "bg-amber-500"}`} />{camOk ? "Kamera aktif" : "Kamera belum aktif"}</Badge></div><div className="absolute bottom-4 left-4 rounded-md bg-slate-900/70 px-3 py-1.5 text-xs font-semibold text-white">{user?.name}</div></div><div className="flex items-center justify-between p-4"><div className="flex items-center gap-2 text-sm font-bold text-slate-800"><Icon name="camera" size={18} />Kamera</div><Badge tone={camOk ? "green" : "amber"}><Icon name={camOk ? "check" : "close"} size={13} />{camOk ? "Berfungsi" : "Tidak tersedia"}</Badge></div>{camError && <p className="border-t border-slate-100 px-4 py-3 text-sm text-red-700">{camError}</p>}</section>
      <div className="space-y-5"><section className="rounded-md border border-slate-200 bg-white p-5"><div className="flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-bold text-slate-800"><Icon name="mic" size={18} />Mikrofon</div><Badge tone={micOk && heardMic ? "green" : micOk ? "blue" : "amber"}><Icon name={micOk ? "check" : "close"} size={13} />{!micOk ? "Tidak tersedia" : heardMic ? "Berfungsi" : "Menunggu suara"}</Badge></div><div className="mt-5 flex h-12 items-end gap-1">{bars.map((h, i) => <span key={i} className="flex-1 rounded-sm bg-blue-500" style={{ height: `${h * 3}px`, opacity: .35 + i / 20 }} />)}</div><p className="mt-3 text-xs text-slate-500">Ucapkan beberapa kata untuk menguji mikrofon.</p></section><section className="rounded-md border border-slate-200 bg-white p-5"><div className="flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-bold text-slate-800"><Icon name="wifi" size={18} />Koneksi ke server</div><Badge tone={latency === undefined ? "gray" : netOk && latency! < 300 ? "green" : "amber"}><Icon name={netOk ? "check" : "close"} size={13} />{latency === undefined ? "Mengukur" : !netOk ? "Tidak terhubung" : latency! < 300 ? "Stabil" : "Lambat"}</Badge></div><div className="mt-5 flex items-end justify-between"><div><p className="text-2xl font-bold text-slate-900">{latency == null ? "—" : `${latency} ms`}</p><p className="text-xs text-slate-500">Waktu respons server EduAI</p></div><div className="flex items-end gap-1">{[2, 3, 4, 5].map((h, i) => <span key={h} className={`w-1.5 rounded-sm ${netOk && i < (latency! < 150 ? 4 : latency! < 300 ? 3 : 2) ? "bg-emerald-500" : "bg-slate-200"}`} style={{ height: `${h * 5}px` }} />)}</div></div></section></div>
    </div><div className={`mt-6 flex flex-col items-center justify-between gap-4 rounded-md border p-5 sm:flex-row ${camOk && netOk ? "border-emerald-100 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}><div className="flex items-center gap-3"><div className={`grid size-9 place-items-center rounded-full ${camOk && netOk ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}><Icon name={camOk && netOk ? "check" : "bell"} size={19} /></div><div><p className={`font-bold ${camOk && netOk ? "text-emerald-900" : "text-amber-900"}`}>{camOk && netOk ? (micOk ? "Semua perangkat siap" : "Kamera siap, mikrofon tidak tersedia") : "Perangkat belum siap"}</p><p className={`text-sm ${camOk && netOk ? "text-emerald-700" : "text-amber-800"}`}>{camOk && netOk ? "Lanjutkan untuk membaca pemberitahuan perekaman." : "Kamera dan koneksi ke server wajib berfungsi untuk mengikuti ujian."}</p></div></div><Button disabled={!camOk || !netOk} onClick={() => go("consent")}>Lanjut ke Persetujuan</Button></div>
  </main></div>;
}

function ExamRoom({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const { user } = useUser();
  const { examId } = useSel();
  const [exam, setExam] = useState<Exam | null>(null);
  const [media, setMedia] = useState<StudentMedia | null>(null);
  const [joinError, setError] = useState("");
  const [mon, setMon] = useState<MonitoringInfo | null>(null);
  const [examStatus, setExamStatus] = useState<string>("");
  const [conn, setConn] = useState<"baik" | "lemah" | "terputus">("baik");
  const [camOn, setCamOn] = useState(true);
  const [micOn, setMicOn] = useState(true);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [uploadInfo, setUploadInfo] = useState("");
  const videoRef = useVideo(stream);
  const uploader = useRef<FrameUploader | null>(null);
  const speech = useRef<SpeechScorer | null>(null);
  const [audioInfo, setAudioInfo] = useState("");
  const [sebLost, setSebLost] = useState("");
  const isStudent = role === "Siswa";
  const error = isStudent && !examId ? "Pilih ujian dari halaman Ujian Saya terlebih dahulu." : joinError;
  // Jitsi exam room: video only, nothing is rendered from other participants. Frames do not depend on it:
  // they go from the local camera to the backend, so a failed room only leaves a connection record.
  const [jitsiAttempt, setJitsiAttempt] = useState(0);
  const jitsi = useJitsiRoom(media && mon?.jitsi && examStatus === "Sedang Berlangsung" ? mon.jitsi.room : null,
    user?.name ?? "Siswa", mon?.jitsi ?? null, { devices: ["video"], attempt: jitsiAttempt, token: mon?.jitsi?.token ?? null, camera: media?.stream ?? null });
  // OpenVidu broadcast only while the backend hands out a ticket (never in Jitsi mode): one broadcast at a time,
  // carrying the same camera track the AI frames are taken from.
  const openvidu = useOpenViduBroadcast(media && examStatus === "Sedang Berlangsung" ? mon?.livekit ?? null : null,
    media?.stream ?? null, camOn, micOn);
  const jitsiReport = !mon?.jitsi ? null : jitsi.status === "joined" ? "connected" as const : jitsi.status === "error" ? "disconnected" as const : null;
  const jitsiState = useRef<"connected" | "disconnected" | null>(jitsiReport);
  useEffect(() => { jitsiState.current = jitsiReport; });

  useEffect(() => {
    if (jitsi.status !== "error") return;
    const t = window.setTimeout(() => setJitsiAttempt((n) => n + 1), 30000);
    return () => window.clearTimeout(t);
  }, [jitsi.status]);

  useEffect(() => {
    const t = jitsi.localTracks.find((x) => x.getType() === "video");
    if (t && t.isMuted() === camOn) void jitsi.toggle("video");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jitsi.localTracks, camOn]);

  useEffect(() => {
    if (!isStudent || !examId) return;
    let m: StudentMedia | null = null;
    let cancelled = false;
    (async () => {
      try {
        // SEB exams: the backend admits only a fresh SEB check, so check right before joining.
        const info = await api.exam(examId);
        if (info.seb?.required) {
          const r = await checkSeb(examId);
          if (!r.verified) throw new ApiError(403, r.message ?? "Safe Exam Browser belum terverifikasi.");
        }
        if (cancelled) return;
        const j = await api.join(examId);
        if (cancelled) return;
        setExam(j.exam); setMon(j.monitoring); setExamStatus(j.exam.status);
        m = await startStudentMedia();
        if (cancelled) { await m.stop(); return; }
        setMedia(m); setStream(m.stream);
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : mediaErrorMessage(e));
      }
    })();
    return () => { cancelled = true; uploader.current?.stop(); uploader.current = null; speech.current?.stop(); speech.current = null; void m?.stop(); void api.leave(examId).catch(() => undefined); };
  }, [examId, isStudent]);

  // SEB exams: re-check every 60 s so the supervisor sees a current state (a check counts for 3 minutes).
  const sebRequired = !!exam?.seb?.required;
  useEffect(() => {
    if (!media || !examId || !sebRequired) return;
    const t = window.setInterval(() => {
      checkSeb(examId).then((r) => setSebLost(r.verified ? "" : r.message ?? "Safe Exam Browser tidak terverifikasi.")).catch(() => undefined);
    }, 60000);
    return () => window.clearInterval(t);
  }, [media, examId, sebRequired]);

  // presence heartbeat + monitoring state (every 5 s)
  useEffect(() => {
    if (!media || !examId) return;
    const beat = async () => {
      const t0 = performance.now();
      try {
        const s = await api.sessionState(examId);
        const rtt = performance.now() - t0;
        const c = rtt < 400 ? "baik" : "lemah";
        setConn(c); setMon(s.monitoring); setExamStatus(s.status);
        await api.presence(examId, { camera_on: media.cameraOn(), mic_on: media.micOn(), connection: c, rtt_ms: Math.round(rtt), jitsi: jitsiState.current });
      } catch { setConn("terputus"); }
    };
    void beat();
    const t = window.setInterval(() => void beat(), 5000);
    return () => window.clearInterval(t);
  }, [media, examId]);

  // Frame upload: always in browser-frame and Jitsi mode; in OpenVidu-worker mode only as a fallback when this
  // browser is not connected to the OpenVidu room (the worker cannot see this student's camera then).
  const uploadWanted = !!mon?.active && examStatus === "Sedang Berlangsung"
    && (mon.source === "browser" || mon.source === "jitsi" || (mon.source === "livekit" && !openvidu.connected));
  const uploadFps = mon?.upload_fps ?? 0, maxWidth = mon?.max_width ?? 0, jpegQuality = mon?.jpeg_quality ?? 0;
  useEffect(() => {
    if (!media || !examId || !videoRef.current) return;
    if (uploadWanted) {
      if (!uploader.current) uploader.current = new FrameUploader(examId, videoRef.current, () => media.cameraOn());
      uploader.current.start({ upload_fps: uploadFps, max_width: maxWidth, jpeg_quality: jpegQuality });
    } else uploader.current?.stop();
  }, [media, examId, uploadWanted, uploadFps, maxWidth, jpegQuality, videoRef]);

  // optional speech-sound scores (only with the student's audio consent; sources whose frames come from this browser)
  const audioWanted = !!media && !!mon?.active && (mon.source === "browser" || mon.source === "jitsi") && examStatus === "Sedang Berlangsung"
    && !!mon.audio?.available && !!mon.audio?.consented;
  // consented but the server says audio cannot run now: tell the student instead of showing nothing
  const audioBlocked = mon?.active && mon.audio?.consented && !mon.audio.available && mon.audio.reason
    ? `Analisis suara tidak berjalan: ${AUDIO_REASON[mon.audio.reason]?.[1] ?? mon.audio.reason}` : "";
  useEffect(() => {
    if (!media || !examId) return;
    if (audioWanted && mon?.audio) {
      if (!speech.current) speech.current = new SpeechScorer(examId, () => media.micOn());
      if (!speech.current.running && speech.current.status !== "loading") void speech.current.start(media.stream, mon.audio);
    } else speech.current?.stop();
  }, [media, examId, audioWanted, mon?.audio]);

  useEffect(() => {
    const t = window.setInterval(() => {
      setNow(Date.now()); const u = uploader.current; setUploadInfo(u?.lastError ?? "");
      const sp = speech.current;
      setAudioInfo(!sp || sp.status === "off" ? "" : sp.status === "loading" ? "Menyiapkan analisis suara…"
        : sp.status === "muted" ? "Mikrofon mati: suara tidak dianalisis" : sp.status === "error" ? `Analisis suara tidak aktif: ${sp.lastError}`
        : "Analisis suara aktif di perangkat ini (audio tidak dikirim)");
    }, 1000);
    return () => window.clearInterval(t);
  }, []);

  const toggleCam = async () => { if (!media) return; await media.setCamera(!camOn); setCamOn(!camOn); setStream(media.stream); };
  const toggleMic = async () => { if (!media) return; await media.setMic(!micOn); setMicOn(!micOn); };
  const exit = async () => { go(isStudent ? "my-exams" : "sessions"); };

  if (!isStudent) return <div className="grid min-h-screen place-items-center bg-slate-950 p-6 text-center text-white"><div><p className="font-semibold">Ruang ujian hanya dibuka dengan akun siswa.</p><p className="mt-2 text-sm text-slate-400">Akun staf memantau melalui halaman Monitoring.</p><Button className="mt-5" onClick={() => go("sessions")}>Kembali</Button></div></div>;
  const ended = examStatus === "Selesai";
  return <div className="flex min-h-screen flex-col bg-slate-950 text-white">
    <header className="flex h-18 items-center justify-between border-b border-white/10 px-5 sm:px-8"><div><p className="text-sm font-bold">{exam?.name ?? "Ruang ujian"}</p><p className="text-xs text-slate-400">Ruang ujian • {exam?.student_count ?? "—"} peserta</p></div><div className="flex items-center gap-4"><div className="rounded-md bg-white/10 px-4 py-2 text-sm font-bold"><span className="mr-2 text-slate-400">Sisa waktu</span>{exam ? remaining(exam, now) : "—"}</div><button onClick={exit} className="hidden text-xs font-semibold text-slate-400 hover:text-white sm:block">Keluar ruang ujian</button></div></header>
    <main className="relative flex flex-1 items-center justify-center overflow-hidden p-5">
      {error ? <div className="max-w-md rounded-md border border-red-400/40 bg-red-500/10 p-5 text-center text-sm text-red-100"><p>{error}</p><Button variant="secondary" className="mt-4" onClick={() => go("my-exams")}>Kembali ke Ujian Saya</Button></div>
        : <div className="relative text-center"><div className="mx-auto grid size-28 place-items-center rounded-full bg-slate-800 text-3xl font-bold text-slate-200 ring-1 ring-slate-700">{initials(exam?.supervisor?.name ?? "P")}</div><p className="mt-5 font-semibold">{exam?.supervisor?.name ?? "Pengawas"} • Pengawas</p><p className="mt-1 text-sm text-slate-400">{ended ? "Ujian telah selesai. Anda dapat keluar dari ruang ujian." : media ? "Ujian sedang berlangsung" : "Menyiapkan kamera..."}</p>{openvidu.error && <p className="mx-auto mt-4 max-w-md rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-200">{openvidu.error} Pengawas tidak dapat melihat video langsung.</p>}{uploadInfo && <p className="mx-auto mt-2 max-w-md rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-200">Pengiriman frame tertunda: {uploadInfo}</p>}{(audioInfo || audioBlocked) && <p className="mx-auto mt-2 max-w-md text-xs text-slate-400">{audioInfo || audioBlocked}</p>}</div>}
      {sebLost && <p role="alert" className="absolute left-5 top-16 max-w-sm rounded-md border border-red-300/40 bg-red-500/15 px-3 py-2 text-xs leading-5 text-red-100">{sebLost} Pengawas melihat status ini.</p>}
      {jitsiReport === "disconnected" && <p role="status" className="absolute left-5 top-5 max-w-sm rounded-md border border-amber-300/40 bg-amber-500/15 px-3 py-2 text-xs leading-5 text-amber-100">Ruang Jitsi tidak terhubung. Ujian tetap berjalan dan kamera Anda tetap dipantau. Sistem mencoba menghubungkan kembali.</p>}
      <div className="absolute bottom-5 right-5 w-44 overflow-hidden rounded-md border border-white/20 bg-slate-800 sm:w-56"><div className="relative flex aspect-video items-center justify-center bg-slate-800">{stream && camOn ? <video ref={videoRef} muted playsInline className="absolute inset-0 size-full -scale-x-100 object-cover" /> : <><video ref={videoRef} muted playsInline className="hidden" /><div className="grid size-14 place-items-center rounded-full bg-white/10 font-bold">{initials(user?.name ?? "")}</div></>}</div><div className="flex items-center justify-between px-3 py-2 text-xs"><span>{user?.name}</span><span className={micOn ? "text-emerald-400" : "text-red-400"}><Icon name="mic" size={14} /></span></div></div>
    </main>
    <footer className="flex h-20 items-center justify-between border-t border-white/10 px-5 sm:px-8"><div className={`flex items-center gap-2 text-xs ${conn === "baik" ? "text-emerald-400" : conn === "lemah" ? "text-amber-300" : "text-red-400"}`}><span className={`size-2 rounded-full ${conn === "baik" ? "bg-emerald-400" : conn === "lemah" ? "bg-amber-300" : "bg-red-400"}`} />{conn === "baik" ? "Koneksi stabil" : conn === "lemah" ? "Koneksi lambat" : "Koneksi terputus"}</div><div className="flex gap-3"><button onClick={toggleMic} aria-label={micOn ? "Matikan mikrofon" : "Nyalakan mikrofon"} className={`grid size-11 place-items-center rounded-full ${micOn ? "bg-white/10" : "bg-red-600"}`}><Icon name="mic" /></button><button onClick={toggleCam} aria-label={camOn ? "Matikan kamera" : "Nyalakan kamera"} className={`grid size-11 place-items-center rounded-full ${camOn ? "bg-white/10" : "bg-red-600"}`}><Icon name="camera" /></button></div><div className="hidden text-xs text-slate-500 sm:block">{mon?.active ? "Pemantauan AI aktif" : "Pemantauan AI belum dimulai"}{openvidu.connected ? " · Siaran ke pengawas aktif (OpenVidu)" : jitsiReport === "connected" ? " · Siaran ke pengawas aktif (Jitsi)" : ""}</div></footer>
  </div>;
}

function MonitorState({ state, reason, onRetry }: { state: "empty" | "loading" | "offline"; reason?: string; onRetry?: () => void }) {
  if (state === "loading") return <div className="grid flex-1 grid-cols-1 gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 9 }).map((_, i) => <div key={i} className="aspect-video animate-pulse rounded-md bg-slate-200" />)}</div>;
  const offline = state === "offline";
  return <div className="flex flex-1 items-center justify-center p-8 text-center"><div className="max-w-sm"><div className={`mx-auto grid size-14 place-items-center rounded-full ${offline ? "bg-amber-50 text-amber-600" : "bg-slate-100 text-slate-400"}`}><Icon name={offline ? "wifi" : "users"} size={26} /></div><h3 className="mt-4 font-bold text-slate-800">{offline ? "AI belum tersedia" : "Belum ada peserta"}</h3><p className="mt-2 text-sm leading-6 text-slate-500">{offline ? `Pemantauan video tetap berjalan. Indikasi otomatis akan kembali setelah layanan AI tersambung.${reason ? ` (${reason})` : ""}` : "Peserta yang bergabung ke ruang ujian akan tampil di sini."}</p>{offline && <Button variant="secondary" className="mt-5" onClick={onRetry}>Coba lagi</Button>}</div></div>;
}

function Silhouette() {
  return <svg viewBox="0 0 40 40" aria-hidden="true" className="absolute bottom-0 left-1/2 h-4/5 -translate-x-1/2 text-white/70"><circle cx="20" cy="15" r="7" fill="currentColor" /><path d="M6 40c0-9 6-14 14-14s14 5 14 14z" fill="currentColor" /></svg>;
}

function LiveVideo({ track, className = "" }: { track: RemoteTrack | undefined; className?: string }) {
  const ref = useVideo(track ?? null);
  if (!track) return null;
  return <video ref={ref} muted playsInline autoPlay className={`absolute inset-0 size-full object-cover ${className}`} />;
}

type LiveFeed = { kind: "openvidu"; track: RemoteTrack } | { kind: "jitsi"; track: JitsiTrack };

/** Live student video from the source the AI analyses: Jitsi in Jitsi mode, otherwise OpenVidu. Opens nothing
 *  until the monitoring state is known, and never both servers at once. */
function useExamLiveVideo(examId: number | null, running: boolean, m: MonitoringState | null | undefined) {
  const { role } = useRole();
  const mode = examId && running && m ? (m.active && m.source === "jitsi" ? "jitsi" : "openvidu") : null;
  const ov = useExamVideoRoom(examId, mode === "openvidu");
  const watching = mode === "jitsi" && (role === "Pengawas" || role === "Admin");
  const watch = usePoll(() => (watching && examId ? api.jitsiWatch(examId) : Promise.resolve(null)), [watching, examId], 20000);
  const jitsi = useJitsiWatch(watching ? watch.data?.server ?? null : null, watching ? watch.data?.rooms ?? null : null);
  const feed = (id: number): LiveFeed | null => {
    if (mode === "jitsi") { const t = jitsi[id]?.track; return t ? { kind: "jitsi", track: t } : null; }
    return mode === "openvidu" && ov.tracks[id] ? { kind: "openvidu", track: ov.tracks[id] } : null;
  };
  return { mode, feed, label: mode === "jitsi" ? "Jitsi" : "OpenVidu", reason: mode === "openvidu" && !ov.connected ? ov.reason : null };
}

function LiveFeedVideo({ feed, className = "" }: { feed: LiveFeed; className?: string }) {
  return feed.kind === "jitsi" ? <JitsiVideo track={feed.track} className={className} /> : <LiveVideo track={feed.track} className={className} />;
}

function studentStatus(s: StudentRow) {
  const p = s.presence;
  if (!p?.joined) return "Belum bergabung";
  if (!p.online) return "Terputus";
  if (p.camera_on === false) return "Kamera mati";
  if (p.mic_on === false) return "Mikrofon mati";
  return "Hadir";
}

/** Supervisor label for one student's Safe Exam Browser check. */
function sebStatus(seb: SebRow): [string, "green" | "amber" | "gray"] {
  if (seb.fresh) return ["SEB terverifikasi", "green"];
  if (!seb.state) return ["SEB belum diperiksa", "gray"];
  if (seb.state === "verified") return ["Verifikasi SEB kedaluwarsa", "amber"];
  return [SEB_STATE_LABEL[seb.state], "amber"];
}

function SebBadge({ seb }: { seb: SebRow }) {
  const [text, tone] = sebStatus(seb);
  const detail = seb.checked_at ? `Diperiksa ${fmtTime(seb.checked_at)}${seb.method ? ` · lewat ${seb.method === "header" ? "header HTTP (sekali pakai)" : "JavaScript API SEB"}` : ""}${seb.version ? ` · ${seb.version}` : ""}` : "Siswa belum membuka pemeriksaan SEB";
  return <span title={detail} className="mt-2 inline-flex"><Badge tone={tone}><Icon name="shield" size={12} />{text}</Badge></span>;
}

function Monitoring({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const { setStudentId, setEventId } = useSel();
  const { exam, reload: reloadExam } = useCurrentExam();
  const examId = exam?.id ?? null;
  const students = usePoll(() => (examId ? api.students(examId) : Promise.resolve([] as StudentRow[])), [examId], 3000);
  const events = usePoll(() => (examId ? api.examEvents(examId, { limit: 30 }) : Promise.resolve({ server_time: "", events: [] as AIEvent[] })), [examId], 3000);
  // All indications of this exam for the timeline (text data only; no video or audio).
  const indEvents = usePoll(() => (examId ? api.examEvents(examId, { category: "indication", limit: 500 }) : Promise.resolve({ server_time: "", events: [] as AIEvent[] })), [examId], 5000);
  const mon = usePoll(() => (examId ? api.monitoring(examId) : Promise.reject(new Error(""))), [examId], 5000);
  const live = useExamLiveVideo(examId, exam?.status === "Sedang Berlangsung", mon.data);
  const [filter, setFilter] = useState("Semua");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [actionMsg, setActionMsg] = useState("");
  const [source, setSource] = useState<AnalysisSource>("browser");
  const servers = usePoll(() => Promise.all([api.health(), api.jitsiConfig()]), []);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t); }, []);
  const rows = students.data ?? [];
  const m: MonitoringState | null = mon.data;
  const sourceReady: Record<AnalysisSource, boolean> = { browser: true, livekit: !!servers.data?.[0].livekit.configured, jitsi: !!servers.data?.[1].configured };
  const jitsiLost = rows.filter((s) => m?.active && m.source === "jitsi" && s.presence?.jitsi === "disconnected");
  const sebRequired = !!exam?.seb?.required;
  const sebVerified = rows.filter((s) => s.seb?.fresh).length;
  const sebProblems = rows.filter((s) => s.seb?.required && s.seb.state && !s.seb.fresh);
  const needsAttention = (s: StudentRow) => (s.counts?.unreviewed ?? 0) > 0 || s.ai?.state === "indication";
  const connIssue = (s: StudentRow) => ["Terputus", "Kamera mati", "Mikrofon mati"].includes(studentStatus(s));
  const attention = rows.filter(needsAttention).length;
  const list = rows.filter((s) => (filter === "Semua" || (filter === "Perlu perhatian" && needsAttention(s)) || (filter === "Normal" && !needsAttention(s) && studentStatus(s) === "Hadir") || (filter === "Masalah koneksi" && connIssue(s)) || (filter === "Tidak dapat dianalisis" && s.ai?.state === "cannot_analyze")) && s.name.toLowerCase().includes(query.toLowerCase()));
  const status = students.data ? monitorStatus(rows) : null;
  const win = exam ? examTimes(exam) : null;
  const timeline = win && indEvents.data ? sessionTimeline(indEvents.data.events, win.start, win.end) : null;
  const ctl = (icon: IconName, off: boolean) => <span className={`grid size-6 place-items-center rounded text-white ${off ? "bg-red-600" : "bg-slate-900/70"}`}><Icon name={icon} size={13} /></span>;
  const canControl = MONITOR_ROLES.includes(role);
  const notify = useContext(NotifyContext);
  const toggleMonitoring = async () => {
    if (!examId || !m) return;
    try {
      if (m.active) { await api.stopMonitoring(examId); setActionMsg("Pemantauan AI dihentikan. Indikasi yang masih terbuka ditutup."); }
      else {
        const r = await api.startMonitoring(examId, source);
        const differs = r.source !== source ? ` Dipilih ${SOURCE_LABEL[source]}, tetapi server memakai ${SOURCE_LABEL[r.source]}.` : "";
        setActionMsg((r.note ?? `Pemantauan AI dimulai. Sumber analisis: ${SOURCE_LABEL[r.source]}.`) + differs);
      }
      void mon.reload(); void reloadExam();
    } catch (e) { setActionMsg((e as Error).message); }
  };
  const aiOffline = !!m && m.active && !m.ai.available && (m.source === "browser" || m.source === "jitsi");
  const workerDown = !!m && m.active && m.source === "livekit" && !m.worker.alive && (!m.started_at || now - new Date(m.started_at).getTime() > 15000);
  const view: "active" | "empty" | "loading" | "offline" = students.loading && !students.data ? "loading" : aiOffline ? "offline" : rows.length === 0 ? "empty" : "active";
  const exp = rows.find((s) => s.id === expanded);
  const openStudent = (id: number) => { setStudentId(id); go("student-detail"); };
  return <AppShell active="monitor" go={go} title="Pemantauan Langsung"><main className="p-4 sm:p-8">
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold text-slate-900">Pemantauan siswa</h1><p className="mt-1 text-sm text-slate-500">{exam ? `${exam.class_name} · ${exam.subject} · ${fmtDate(exam.date)}` : "Memuat sesi..."}</p></div><div className="flex max-w-full flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2.5"><span className={`size-2.5 rounded-full ${m?.active ? "animate-pulse bg-red-500" : "bg-slate-300"}`} /><div><p className="text-sm font-semibold text-slate-900">{exam?.name ?? "—"}</p><p className="text-xs text-slate-500">{exam ? `${exam.status} · sisa ${remaining(exam, now)}` : ""} · AI {m?.active ? "aktif" : "belum aktif"}{m?.active && m.source ? ` · Sumber: ${SOURCE_LABEL[m.source]}` : ""}</p></div>{canControl && examId && <Button variant="ghost" className="ml-2 h-9" onClick={() => notify.openSummary(examId)}>Ringkasan</Button>}{canControl && exam?.status === "Sedang Berlangsung" && !m?.active && <select aria-label="Sumber analisis" value={source} onChange={(e) => setSource(e.target.value as AnalysisSource)} className="ml-2 h-9 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700">{(["browser", "livekit", "jitsi"] as AnalysisSource[]).map((x) => <option key={x} value={x} disabled={!sourceReady[x]}>{SOURCE_LABEL[x]}{sourceReady[x] ? "" : " (belum dikonfigurasi)"}</option>)}</select>}{canControl && exam?.status === "Sedang Berlangsung" && <Button variant={m?.active ? "secondary" : "primary"} className="ml-2 h-9" onClick={toggleMonitoring}>{m?.active ? "Hentikan AI" : `Mulai AI · ${SOURCE_LABEL[source]}`}</Button>}</div></div>
    {actionMsg && <Notice tone="blue">{actionMsg}</Notice>}
    {exam && <div data-testid="seb-summary" className={`mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border px-4 py-3 text-sm ${!sebRequired ? "border-slate-200 bg-white text-slate-600" : sebProblems.length ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}><Icon name="shield" size={17} /><strong>Keamanan ujian:</strong>{!sebRequired ? <span>Safe Exam Browser tidak diwajibkan untuk ujian ini.</span> : <><span>Safe Exam Browser wajib · {sebVerified}/{rows.length} siswa terverifikasi.</span>{sebProblems.length > 0 && <span>Perlu dicek: {sebProblems.map((s) => `${s.name} (${sebStatus(s.seb!)[0]})`).join(", ")}.</span>}</>}</div>}
    {jitsiLost.length > 0 && <Notice>Koneksi Jitsi terputus: {jitsiLost.map((s) => s.name).join(", ")}. Ini catatan koneksi, bukan indikasi; analisis tetap berjalan selama kamera siswa hidup.</Notice>}
    {students.error && <Notice tone="red">{students.error}</Notice>}
    {workerDown && <Notice>Worker AI OpenVidu belum mengirim heartbeat{m?.worker.process_running ? "" : " (proses worker berhenti)"}. Pastikan server OpenVidu berjalan dan dapat dihubungi backend; sampai itu, status AI siswa tampil "Analisis AI terputus". {canControl && <button className="ml-1 font-semibold underline" onClick={async () => { if (!examId) return; try { await api.startMonitoring(examId, "browser"); setActionMsg("Analisis dialihkan ke frame dari browser siswa."); void mon.reload(); } catch (e) { setActionMsg((e as Error).message); } }}>Pakai frame dari browser</button>}</Notice>}
    {live.reason && <Notice tone="blue">Video langsung tidak ditampilkan: {live.reason}. Status kamera dan hasil AI tetap diperbarui.</Notice>}
    {!chartsOnDashboard(role) && <div className="mb-6"><Suspense fallback={<div className="grid gap-[18px]"><ChartSkeleton h={150} /><ChartSkeleton h={170} /></div>}><MonitoringCharts status={status} timeline={timeline} /></Suspense>
      {(indEvents.data?.events.length ?? 0) >= 500 && <p className="mt-2 text-xs text-[#8c621a]">Linimasa menampilkan 500 indikasi terbaru dari sesi ini.</p>}</div>}
    <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
      <section className="min-w-0">
        <div className="mb-4 flex flex-wrap items-center gap-3"><div className="flex min-w-0 max-w-full gap-1 overflow-x-auto rounded-lg bg-slate-200/70 p-1">{["Semua", "Normal", "Perlu perhatian", "Tidak dapat dianalisis", "Masalah koneksi"].map((t) => <button key={t} onClick={() => setFilter(t)} className={`flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ${filter === t ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"}`}>{t}{t === "Perlu perhatian" && <span className="rounded-full bg-amber-100 px-1.5 text-[11px] text-amber-700">{attention}</span>}</button>)}</div>
          <div className="relative ml-auto min-w-52 flex-1 sm:max-w-xs"><span className="absolute left-3 top-2.5 text-slate-400"><Icon name="search" size={17} /></span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Cari nama siswa" className="h-10 w-full rounded-md border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none focus:border-blue-500" /></div></div>
        {view !== "active" ? <div className="flex min-h-[420px] rounded-lg border border-slate-200 bg-white"><MonitorState state={view} reason={m?.ai.reason} onRetry={() => void mon.reload()} /></div> : list.length === 0 ? <div className="rounded-lg border border-slate-200 bg-white p-12 text-center text-sm text-slate-500">Tidak ada siswa yang cocok dengan filter ini.</div> : <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">{list.map((s, i) => {
          const st = studentStatus(s);
          const off = st === "Kamera mati" || st === "Terputus" || st === "Belum bergabung";
          const flagged = needsAttention(s);
          const ai = s.ai?.state ?? "no_data";
          const feed = live.feed(s.id);
          return <article key={s.id} className={`overflow-hidden rounded-lg border bg-white ${flagged ? "border-amber-300" : ai === "cannot_analyze" ? "border-slate-400" : "border-slate-200"}`}>
            <div className={`relative aspect-video ${off ? "bg-slate-800" : ["bg-blue-100", "bg-slate-200", "bg-blue-50", "bg-slate-300"][i % 4]}`}>
              {off ? <div className="absolute inset-0 grid place-items-center text-center text-slate-300"><div><Icon name="wifi" size={22} /><p className="mt-1 text-xs">{st === "Terputus" ? "Terputus / menyambung ulang" : st === "Belum bergabung" ? "Belum bergabung" : "Kamera dimatikan"}</p></div></div> : feed ? <LiveFeedVideo feed={feed} /> : <Silhouette />}
              {!off && <span className="absolute left-2 top-2 flex items-center gap-1.5 rounded bg-slate-900/75 px-2 py-0.5 text-[11px] font-medium text-white"><span className={`size-1.5 rounded-full ${feed ? "bg-red-500" : "bg-slate-400"}`} />{feed ? "LIVE" : "Online"}</span>}
              <div className="absolute right-2 top-2 flex gap-1">{ctl("mic", s.presence?.mic_on === false)}{ctl("camera", s.presence?.camera_on === false)}{ctl("wifi", st === "Terputus")}</div>
              {ai === "indication" ? <div className="absolute inset-x-0 bottom-0 flex items-center gap-2 bg-amber-600/95 px-3 py-1.5 text-xs font-semibold text-white"><Icon name="bell" size={14} />{s.last_indication?.status === "open" ? s.last_indication.label ?? "Indikasi" : "Indikasi"} · sedang berlangsung</div>
                : flagged ? <div className="absolute inset-x-0 bottom-0 flex items-center gap-2 bg-amber-50/95 px-3 py-1.5 text-xs font-medium text-amber-900"><Icon name="report" size={14} />{(() => { const li = s.last_indication; const txt = `${s.counts?.unreviewed ?? 0} belum ditinjau${li?.current_session === false ? " · sesi sebelumnya" : ""}${li ? ` · terakhir ${li.label ?? li.indicator} ${fmtTime(li.start_ts)}` : ""}`; return <span className="truncate" title={txt}>{txt}</span>; })()}</div>
                : ai === "cannot_analyze" && !off ? <div className="absolute inset-x-0 bottom-0 bg-slate-700/90 px-3 py-1.5 text-xs font-semibold text-white">Tidak dapat dianalisis{s.ai?.reason ? ` · ${FRAME_REASON[s.ai.reason] ?? s.ai.reason}` : ""}</div> : null}
            </div>
            <div className="p-3.5"><div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{s.name}</p><p className="text-xs text-slate-400">NIS {s.nis ?? "—"} · AI: {STATE_LABEL[ai]}</p>{s.seb?.required && <SebBadge seb={s.seb} />}</div><Badge tone={s.counts?.unreviewed ? "amber" : st === "Hadir" ? stateTone(ai) : "gray"}>{s.counts?.unreviewed ? `${s.counts.unreviewed} perlu ditinjau` : st === "Hadir" ? STATE_LABEL[ai] : st}</Badge></div>
              <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3 text-xs"><button onClick={() => setExpanded(s.id)} className="tap relative font-semibold text-slate-600 hover:text-slate-900">Perbesar</button><button onClick={() => openStudent(s.id)} className="tap relative flex items-center gap-1 font-semibold text-blue-700">Buka pemantauan <Icon name="chevron" size={14} /></button></div></div>
          </article>;
        })}</div>}
      </section>
      <aside className="h-fit rounded-lg border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-4"><div><h2 className="font-semibold text-slate-900">Aktivitas terbaru</h2><p className="text-xs text-slate-500">Diperbarui setiap 3 detik</p></div><button onClick={() => go("indications")} className="tap relative text-xs font-semibold text-blue-700">Lihat semua</button></div>
        <div className="max-h-[560px] divide-y divide-slate-100 overflow-y-auto">{aiOffline ? <p className="p-5 text-sm text-amber-800">AI belum tersedia. Daftar indikasi akan terisi lagi setelah layanan tersambung.</p> : (events.data?.events ?? []).length === 0 ? <p className="p-5 text-sm text-slate-500">Belum ada kejadian dari AI pada sesi ini.</p> : (events.data?.events ?? []).map((e) => { const ind = e.category === "indication"; return <button key={e.event_id} onClick={() => { if (ind) { setEventId(e.event_id); go("detail"); } else openStudent(e.student_id); }} className="flex w-full items-start gap-3 p-4 text-left hover:bg-slate-50"><span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-md ${ind ? "bg-amber-50 text-amber-600" : "bg-slate-100 text-slate-500"}`}><Icon name={ind ? "bell" : e.category === "info" ? "mic" : "camera"} size={16} /></span><span className="min-w-0 flex-1"><span className="block text-sm font-medium text-slate-800">{eventTitle(e)}</span><span className="text-xs text-slate-500">{e.student?.name} · {fmtTime(e.start_ts)} · {e.status === "open" ? "berlangsung" : fmtDuration(e.duration_s)}</span></span>{ind && !e.review_status && <span className="mt-2 size-2 rounded-full bg-blue-600" />}</button>; })}</div>
        <div className="m-4 flex gap-3 rounded-md bg-blue-50 p-3.5 text-xs leading-5 text-blue-900"><Icon name="shield" size={17} /><p><strong className="block font-semibold">Perlu verifikasi manusia</strong>Indikasi dari AI hanya membantu peninjauan dan tidak menentukan hasil secara otomatis. "Tidak dapat dianalisis" berarti kualitas video kurang, bukan pelanggaran.</p></div>
      </aside>
    </div>
    {exp && <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/80 p-3 sm:p-6"><section role="dialog" aria-modal="true" className="max-h-[90dvh] w-full max-w-4xl overflow-y-auto overflow-x-hidden rounded-lg border border-slate-700 bg-slate-900"><div className="flex items-center justify-between border-b border-white/10 p-4 text-white"><div><p className="font-semibold">{exp.name}</p><p className="text-xs text-slate-400">{live.feed(exp.id) ? `Siaran langsung · ${live.label}` : "Video langsung tidak tersedia"} · AI: {STATE_LABEL[exp.ai?.state ?? "no_data"]}</p></div><button onClick={() => setExpanded(null)} aria-label="Tutup" className="tap relative"><Icon name="close" /></button></div><div className="relative aspect-video bg-slate-800">{(() => { const f = live.feed(exp.id); return f ? <LiveFeedVideo feed={f} className="object-contain" /> : <Silhouette />; })()}</div><div className="flex justify-end gap-2 border-t border-white/10 p-4"><Button variant="secondary" onClick={() => { setExpanded(null); openStudent(exp.id); }}>Detail siswa</Button><Button onClick={() => setExpanded(null)}>Tutup</Button></div></section></div>}
  </main></AppShell>;
}

function StudentMonitoringDetail({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const { examId, studentId, setEventId } = useSel();
  const students = usePoll(() => (examId ? api.students(examId) : Promise.resolve([] as StudentRow[])), [examId], 3000);
  const timeline = usePoll(() => (examId && studentId ? api.timeline(examId, studentId) : Promise.resolve([] as TimelineItem[])), [examId, studentId], 5000);
  const exam = usePoll(() => (examId ? api.exam(examId) : Promise.reject(new Error("Pilih sesi"))), [examId]);
  const mon = usePoll(() => (examId ? api.monitoring(examId) : Promise.reject(new Error(""))), [examId], 5000);
  const live = useExamLiveVideo(examId, exam.data?.status === "Sedang Berlangsung", mon.data);
  const s = students.data?.find((x) => x.id === studentId);
  const feed = s ? live.feed(s.id) : null;
  const items = (timeline.data ?? []).slice().reverse();
  const st = s ? studentStatus(s) : "—";
  const openEvent = (id?: string) => { if (id) { setEventId(id); go("detail"); } };
  const lastInd = items.find((i) => i.kind === "indication");
  return <AppShell active="student-detail" go={go} title="Detail Pemantauan Siswa"><main className="p-4 sm:p-8">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><button onClick={() => go("monitor")} className="tap relative flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-800"><Icon name="arrow" size={18} />Kembali ke pemantauan</button><Button variant="secondary" onClick={() => go("timeline")}>Lihat linimasa lengkap</Button></div>
    {!s ? <Notice tone={students.loading ? "blue" : "red"}>{students.loading ? "Memuat..." : students.error || "Pilih siswa dari halaman Monitoring."}</Notice> : <>
      <div className="mb-6 flex flex-col justify-between gap-5 rounded-md border border-slate-200 bg-white p-5 sm:flex-row sm:items-center"><div className="flex items-center gap-4"><div className="grid size-14 place-items-center rounded-full bg-amber-100 font-bold text-amber-800">{initials(s.name)}</div><div><div className="flex items-center gap-2"><h1 className="text-xl font-bold text-slate-900">{s.name}</h1><Badge tone={s.counts?.unreviewed ? "amber" : stateTone(s.ai?.state)}>{s.counts?.unreviewed ? "Perlu perhatian" : STATE_LABEL[s.ai?.state ?? "no_data"]}</Badge></div><p className="mt-1 text-sm text-slate-500">NIS {s.nis ?? "—"} • {s.class_name}</p></div></div><div className="flex gap-5 text-center"><div><p className={`text-sm font-bold ${s.presence?.online ? "text-emerald-600" : "text-slate-500"}`}>{s.presence?.online ? (s.presence.connection === "baik" ? "Stabil" : s.presence.connection) : "Offline"}</p><p className="text-[10px] text-slate-400">Koneksi</p></div><div><p className="text-sm font-bold text-slate-700">{s.presence?.camera_on ? "Aktif" : "Mati"}</p><p className="text-[10px] text-slate-400">Kamera</p></div><div><p className="text-sm font-bold text-slate-700">{s.presence?.mic_on ? "Aktif" : "Mati"}</p><p className="text-[10px] text-slate-400">Mikrofon</p></div><div title={`Analisis suara di perangkat siswa (hanya skor, tanpa audio)${s.audio?.reason ? `. ${AUDIO_REASON[s.audio.reason]?.[1] ?? s.audio.reason}` : ""}`}><p className="text-sm font-bold text-slate-700">{!s.audio?.consented ? "Tidak disetujui" : s.audio.active ? "Aktif" : "Tidak aktif"}</p><p className="text-[10px] text-slate-400">Analisis suara</p>{s.audio?.consented && !s.audio.active && s.audio.reason && <p className="text-[10px] font-medium text-amber-700">{AUDIO_REASON[s.audio.reason]?.[0] ?? s.audio.reason}</p>}</div></div></div>
      <div className="grid gap-6 xl:grid-cols-[1.45fr_.8fr]"><div className="space-y-6"><section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="relative flex aspect-video items-center justify-center bg-slate-800">{feed ? <LiveFeedVideo feed={feed} className="object-contain" /> : <div className="grid size-24 place-items-center rounded-full bg-white/10 text-2xl font-bold text-white ring-1 ring-white/20">{initials(s.name)}</div>}<div className="absolute bottom-4 left-4 flex items-center gap-2 rounded-md bg-slate-900/70 px-3 py-2 text-xs text-white"><span className={`size-2 rounded-full ${feed ? "bg-emerald-400" : "bg-slate-400"}`} />{feed ? `Siaran langsung • ${live.label}` : live.reason ? "Video langsung tidak tersedia" : "Menunggu video siswa"}</div></div><div className="flex items-center justify-between p-4"><p className="text-sm font-semibold text-slate-700">{exam.data?.name}</p><div className="flex gap-2 text-slate-500"><Icon name="mic" size={17} /><Icon name="camera" size={17} /><Icon name="wifi" size={17} /></div></div></section>
        <section className="rounded-md border border-slate-200 bg-white p-6"><div className="flex items-center justify-between"><div><h2 className="font-bold text-slate-900">Aktivitas Siswa</h2><p className="mt-1 text-xs text-slate-500">Linimasa perangkat dan Indikasi selama sesi.</p></div><Badge tone={s.counts?.unreviewed ? "amber" : "gray"}>{s.counts?.unreviewed ?? 0} belum ditinjau</Badge></div><div className="mt-5 divide-y divide-slate-100">{items.slice(0, 8).map((it, idx) => <div key={it.ts + idx} className="flex items-center gap-4 py-3"><span className={`size-2 rounded-full ${it.kind === "indication" ? "bg-amber-500" : it.kind === "cannot_analyze" ? "bg-slate-400" : it.kind === "review" ? "bg-blue-500" : "bg-emerald-500"}`} /><span className="w-20 text-xs font-semibold text-slate-500">{fmtTime(it.ts)}</span><p className="flex-1 text-sm font-semibold text-slate-800">{it.title}{it.kind === "indication" && it.status === "open" ? " (berlangsung)" : ""}</p>{it.kind === "indication" && <button onClick={() => openEvent(it.event_id)} className="text-xs font-bold text-blue-700">{mayOpenEvidence(role) ? "Lihat Evidence" : "Lihat Detail"}</button>}</div>)}{items.length === 0 && <p className="py-3 text-sm text-slate-500">Belum ada aktivitas.</p>}</div><div className="mt-5 flex gap-3 border-t border-slate-100 pt-5"><Button onClick={() => go("indications")}>Lihat Indikasi</Button><Button variant="secondary" disabled={!lastInd} onClick={() => openEvent(lastInd?.event_id)}>Lihat Evidence</Button></div></section></div>
        <aside className="space-y-6"><section className="rounded-md border border-slate-200 bg-white p-5"><h2 className="font-bold text-slate-900">Status pemantauan</h2><div className="mt-5 space-y-4">{[["Status kehadiran", st], ["Waktu masuk", fmtTime(s.presence?.joined_at)], ["Koneksi", s.presence?.online ? `${s.presence.rtt_ms ? `${Math.round(s.presence.rtt_ms)} ms • ` : ""}${s.presence.connection ?? ""}` : "Offline"], ...(s.presence?.jitsi ? [["Ruang Jitsi", s.presence.jitsi === "connected" ? "Terhubung" : "Terputus"]] : []), ["Status AI", STATE_LABEL[s.ai?.state ?? "no_data"]], ["Sumber analisis", SOURCE_LABEL[s.ai?.source as AnalysisSource] ?? "—"], ["Kualitas video", s.ai?.frame_status === "cannot_analyze" ? `Tidak dapat dianalisis (${FRAME_REASON[s.ai.reason ?? ""] ?? s.ai.reason})` : s.ai?.frame_status === "analyzed" ? "Dapat dianalisis" : "—"], ["Jumlah Indikasi", `${s.counts?.indications ?? 0} kejadian`], ["Belum ditinjau", `${s.counts?.unreviewed ?? 0} Indikasi`]].map(([k, v], i) => <div key={k} className="flex justify-between gap-4 text-sm"><span className="text-slate-500">{k}</span><span className={`text-right font-semibold ${i === 0 && v === "Hadir" ? "text-emerald-700" : i === 6 && (s.counts?.unreviewed ?? 0) > 0 ? "text-amber-700" : "text-slate-800"}`}>{v}</span></div>)}</div></section><section className="rounded-md border border-blue-100 bg-blue-50 p-5"><div className="flex gap-3"><span className="text-blue-700"><Icon name="shield" size={19} /></span><div><p className="text-sm font-bold text-blue-900">Keputusan tetap pada pengawas</p><p className="mt-2 text-xs leading-5 text-blue-800">Periksa rekaman dan konteks sebelum membuat penilaian.</p></div></div></section></aside></div>
    </>}
  </main></AppShell>;
}

function MonitoringTimeline({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const { examId, studentId, setStudentId, setEventId } = useSel();
  const students = usePoll(() => (examId ? api.students(examId) : Promise.resolve([] as StudentRow[])), [examId]);
  const timeline = usePoll(() => (examId && studentId ? api.timeline(examId, studentId) : Promise.resolve([] as TimelineItem[])), [examId, studentId], 5000);
  const [kind, setKind] = useState("Semua jenis kejadian");
  const s = students.data?.find((x) => x.id === studentId);
  const kinds: Record<string, string> = { indication: "Indikasi", info: "Info suara (bukan indikasi)", cannot_analyze: "Kualitas video", presence: "Kehadiran", connection: "Koneksi", consent: "Persetujuan", review: "Tinjauan pengawas", note: "Catatan manual" };
  const tones: Record<string, string> = { indication: "amber", info: "blue", presence: "green", connection: "gray", consent: "green", review: "blue", cannot_analyze: "gray", note: "gray" };
  const events = (timeline.data ?? []).filter((e) => kind === "Semua jenis kejadian" || kinds[e.kind] === kind);
  return <AppShell active="timeline" go={go} title="Linimasa Pemantauan"><main className="mx-auto max-w-5xl p-4 sm:p-8"><button onClick={() => go("student-detail")} className="tap relative mb-5 flex items-center gap-2 text-sm font-semibold text-slate-500"><Icon name="arrow" size={18} />Kembali ke detail siswa</button><PageTitle title="Linimasa Pemantauan" description={`${s?.name ?? "Pilih siswa"} • ${s ? "" : ""}`} />
    <div className="mb-6 flex flex-wrap gap-2 rounded-md border border-slate-200 bg-white p-4"><select value={studentId ?? ""} onChange={(e) => setStudentId(Number(e.target.value))} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600"><option value="" disabled>Pilih siswa</option>{(students.data ?? []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select><select value={kind} onChange={(e) => setKind(e.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600"><option>Semua jenis kejadian</option>{Object.values(kinds).map((k) => <option key={k}>{k}</option>)}</select></div>
    <section className="rounded-md border border-slate-200 bg-white p-6">{events.length === 0 ? <p className="text-sm text-slate-500">Belum ada kejadian.</p> : <div className="relative ml-3 border-l border-slate-200 pl-8">{events.map((ev, i) => { const tone = tones[ev.kind] ?? "gray"; return <div key={ev.ts + i} className={`${i < events.length - 1 ? "pb-8" : ""} relative`}><span className={`absolute -left-[39px] top-1 grid size-5 place-items-center rounded-full ring-4 ring-white ${tone === "amber" ? "bg-amber-500" : tone === "green" ? "bg-emerald-500" : tone === "blue" ? "bg-blue-500" : "bg-slate-400"}`} /><div className="flex flex-col justify-between gap-2 sm:flex-row"><div><p className="text-sm font-bold text-slate-800">{ev.title}</p><p className="mt-1 text-xs text-slate-500">{kinds[ev.kind] ?? ev.kind} • {s?.name}{ev.reason ? ` • ${ev.reason}` : ""}{ev.sound_text ? ` • ${ev.sound_text}` : ""}{ev.note ? ` • ${ev.note}` : ""}</p>{ev.kind === "indication" && <button onClick={() => { setEventId(ev.event_id!); go("detail"); }} className="tap relative mt-1 text-xs font-bold text-blue-700">{mayOpenEvidence(role) ? "Lihat evidence" : "Lihat detail"}</button>}</div><span className="text-xs font-semibold text-slate-400">{fmtTime(ev.ts)} WIB</span></div></div>; })}</div>}</section>
  </main></AppShell>;
}

function EvidenceViewer({ event }: { event: AIEvent }) {
  const { role } = useRole();
  const allowed = mayOpenEvidence(role);
  const [meta, setMeta] = useState<{ frames: string[]; ts: number[]; key: number } | null>(null);
  const [error, setError] = useState("");
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!allowed || !event.evidence_id) return;
    let urls: string[] = [];
    let cancelled = false;
    (async () => {
      try {
        const m = await api.evidence(event.evidence_id!);
        urls = await Promise.all(Array.from({ length: m.frame_count }, (_, i) => api.evidenceFrameUrl(m.evidence_id, i)));
        if (cancelled) { urls.forEach(URL.revokeObjectURL); return; }
        setMeta({ frames: urls, ts: m.frame_ts, key: m.key_index }); setIdx(m.key_index);
      } catch (e) { if (!cancelled) setError((e as Error).message); }
    })();
    return () => { cancelled = true; urls.forEach(URL.revokeObjectURL); };
  }, [allowed, event.evidence_id]);
  useEffect(() => {
    if (!playing || !meta) return;
    const t = window.setInterval(() => setIdx((i) => (i + 1) % meta.frames.length), 600);
    return () => window.clearInterval(t);
  }, [playing, meta]);
  const n = meta?.frames.length ?? 0;
  const pct = n > 1 ? (idx / (n - 1)) * 100 : 0;
  const keyPct = n > 1 && meta ? (meta.key / (n - 1)) * 100 : 0;
  return <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="relative grid aspect-video place-items-center bg-slate-900">{meta && n ? <img src={meta.frames[idx]} alt={`Cuplikan evidence ${idx + 1} dari ${n}`} className="absolute inset-0 size-full object-contain" /> : <div className="text-center text-slate-300"><div className="mx-auto grid size-16 place-items-center rounded-full bg-white/10 text-white"><Icon name="video" size={26} /></div><p className="mt-3 px-6 text-sm">{error || (!allowed ? EVIDENCE_RESTRICTED : event.evidence_id ? "Memuat evidence..." : event.status === "open" ? "Evidence disimpan setelah kejadian selesai direkam (±5 detik)." : "Evidence tidak tersedia (tidak tersimpan atau melewati masa simpan).")}</p></div>}{n > 0 && <button onClick={() => setPlaying(!playing)} className="absolute bottom-5 left-5 grid size-10 place-items-center rounded-full bg-white text-slate-900" aria-label={playing ? "Pause" : "Play"}>{playing ? "Ⅱ" : "▶"}</button>}<span className="absolute right-4 top-4 rounded-md bg-slate-950/70 px-3 py-1.5 text-xs font-semibold text-white">{n ? `Cuplikan ${idx + 1}/${n}${meta && idx === meta.key ? " • saat indikasi" : ""}` : "Snapshot"}</span></div><div className="p-5"><div className="relative h-2 rounded-full bg-slate-200"><div className="h-2 rounded-full bg-blue-700" style={{ width: `${pct}%` }} />{n > 1 && <span className="absolute top-1/2 h-5 w-0.5 -translate-y-1/2 bg-amber-500" style={{ left: `${keyPct}%` }} />}</div><div className="mt-5 flex flex-wrap items-center justify-between gap-2"><span className="text-xs text-slate-500">{fmtTime(event.start_ts)} — {event.end_ts ? fmtTime(event.end_ts) : "berlangsung"}</span><div className="flex gap-2"><Button variant="secondary" className="h-9" disabled={!n} onClick={() => setIdx((i) => Math.max(0, i - 1))}>Sebelumnya</Button><Button variant="secondary" className="h-9" disabled={!n} onClick={() => setPlaying(true)}>Putar Evidence</Button><Button variant="ghost" className="h-9" disabled={!n} onClick={() => setIdx((i) => Math.min(n - 1, i + 1))}>Berikutnya</Button></div></div><p className="mt-3 text-[11px] text-slate-400">Evidence berupa cuplikan gambar beresolusi rendah (bukan video penuh, tanpa audio). Setiap akses dicatat di audit log.</p></div></section>;
}

function SupervisorEvidenceDetail({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const { eventId, setStudentId } = useSel();
  const readOnly = role === "Pihak Sekolah";
  const ev = usePoll(() => (eventId ? api.event(eventId) : Promise.reject(new Error("Pilih indikasi dari daftar Indikasi."))), [eventId], 5000);
  const [choice, setChoice] = useState<Decision>("Valid");
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");
  const [manual, setManual] = useState({ time: "", kind: "", note: "" });
  const [manualSaved, setManualSaved] = useState(false);
  const e = ev.data;
  const saveValidation = async () => {
    if (!e) return;
    try { const r = await api.review(e.event_id, choice, note); ev.setData(r); setSaved(true); setErr(""); } catch (x) { setErr((x as Error).message); }
  };
  const saveManual = async () => {
    if (!e || !manual.note.trim()) return;
    try { await api.addNote(e.exam_id, { student_id: e.student_id, time_text: manual.time, kind: manual.kind, note: manual.note }); setManualSaved(true); setManual({ time: "", kind: "", note: "" }); } catch (x) { setErr((x as Error).message); }
  };
  const history = e?.reviews ?? [];
  const isIndication = e?.category === "indication";
  return <AppShell active="detail" go={go} title="Detail Evidence"><main className="mx-auto max-w-6xl p-4 sm:p-8">
    <button onClick={() => go("indications")} className="tap relative mb-5 flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-800"><Icon name="arrow" size={18} />Kembali ke Indikasi</button>
    <PageTitle eyebrow={e ? `Indikasi #${e.event_id.slice(0, 8).toUpperCase()}` : undefined} title="Detail Evidence" description="Evidence terkait Indikasi pada waktu kejadian." />
    {ev.error && !e && <Notice tone="red">{ev.error}</Notice>}
    {err && <Notice tone="red">{err}</Notice>}
    {e && <div className="grid gap-6 xl:grid-cols-[1.45fr_.75fr]"><div className="space-y-6">
      <EvidenceViewer event={e} />
      {isIndication && <section className="rounded-md border border-slate-200 bg-white p-6"><h2 className="font-bold text-slate-900">Validasi Pengawas</h2><p className="mt-1 text-sm text-slate-500">{readOnly ? "Hasil ini hanya dapat dilihat dan tidak dapat diubah oleh pihak sekolah." : "Pilih hasil berdasarkan evidence dan konteks kejadian."}</p>{!readOnly && <><div className="mt-5 grid gap-3 sm:grid-cols-3">{(["Valid", "Tidak Valid", "Perlu Tinjauan Lanjut"] as Decision[]).map((label) => <button key={label} onClick={() => setChoice(label)} className={`rounded-md border p-4 text-left ${choice === label ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100" : "border-slate-200 hover:bg-slate-50"}`}><span className="text-sm font-bold text-slate-800">{label}</span></button>)}</div><label className="mt-5 block"><span className="mb-2 block text-sm font-semibold text-slate-700">Catatan Pengawas</span><textarea value={note} onChange={(x) => setNote(x.target.value)} rows={4} className="w-full resize-none rounded-md border border-slate-200 p-3 text-sm outline-none focus:border-blue-500" placeholder="Tuliskan alasan dan konteks validasi..." /></label><div className="mt-4 flex justify-end"><Button onClick={saveValidation}>Simpan Validasi</Button></div></>}{saved && <div className="mt-5 rounded-md border border-emerald-200 bg-emerald-50 p-4"><div className="flex items-center justify-between"><p className="text-sm font-bold text-emerald-900">Validasi berhasil disimpan</p><Badge tone="green">{e.review_status}</Badge></div><p className="mt-2 text-xs text-emerald-800">{history.at(-1)?.reviewer} • baru saja • {history.at(-1)?.note || "Tidak ada catatan tambahan."}</p></div>}<div className="mt-6 border-t border-slate-100 pt-6"><h3 className="text-sm font-bold text-slate-900">Riwayat Validasi</h3><div className="mt-3 divide-y divide-slate-100">{history.length === 0 ? <p className="py-3 text-sm text-slate-500">Belum ada validasi.</p> : history.map((item, index) => <div key={`${item.created_at}-${index}`} className="grid gap-2 py-3 text-sm sm:grid-cols-[70px_1fr_180px]"><span className="text-slate-500">{fmtTime(item.created_at).slice(0, 5)}</span><div><p className="font-semibold text-slate-800">{item.reviewer}</p><p className="mt-1 text-xs text-slate-500">{item.note || "Tidak ada catatan tambahan."}</p></div><Badge tone={reviewTone(item.decision)}>{item.decision}</Badge></div>)}</div></div></section>}
      {!isIndication && <Notice tone="blue">{e.category === "info" ? "Kejadian ini berkategori info: dicatat sebagai konteks, bukan indikasi, tanpa gambar bukti, dan tidak memerlukan validasi." : 'Kejadian ini berkategori "tidak dapat dianalisis" (kualitas video kurang). Ini bukan indikasi dan tidak memerlukan validasi.'}</Notice>}
      {!readOnly && <section className="rounded-md border border-slate-200 bg-white p-6"><h2 className="font-bold text-slate-900">Tambah Catatan Manual</h2><p className="mt-1 text-sm text-slate-500">Catat kejadian yang terlihat langsung tetapi tidak terdeteksi sistem.</p><div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Waktu Kejadian</span><input type="time" value={manual.time} onChange={(x) => setManual({ ...manual, time: x.target.value })} className="h-11 w-full rounded-md border border-slate-200 px-3.5 text-sm" /></label><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Jenis Kejadian</span><input value={manual.kind} onChange={(x) => setManual({ ...manual, kind: x.target.value })} placeholder="Contoh: Aktivitas di luar kamera" className="h-11 w-full rounded-md border border-slate-200 px-3.5 text-sm" /></label><label className="block sm:col-span-2"><span className="mb-2 block text-sm font-semibold text-slate-700">Catatan</span><textarea rows={3} value={manual.note} onChange={(x) => setManual({ ...manual, note: x.target.value })} className="w-full rounded-md border border-slate-200 p-3 text-sm" placeholder="Jelaskan kejadian yang diamati..." /></label></div><div className="mt-4 flex items-center justify-between">{manualSaved ? <span className="text-xs font-semibold text-emerald-700">Catatan manual berhasil disimpan.</span> : <span />}<Button variant="secondary" disabled={!manual.note.trim()} onClick={saveManual}>Simpan Catatan</Button></div></section>}
    </div><aside className="h-fit rounded-md border border-slate-200 bg-white p-6"><div className="flex items-center gap-3 border-b border-slate-100 pb-5"><div className="grid size-11 place-items-center rounded-full bg-slate-100 text-sm font-bold text-slate-700">{initials(e.student?.name ?? "")}</div><div><p className="font-bold text-slate-900">{e.student?.name}</p><p className="text-xs text-slate-500">NIS {e.student?.nis ?? "—"} • {e.student?.class_name}</p></div></div><dl className="mt-5 space-y-4 text-sm">{[["Jenis", eventTitle(e)], ["Kategori", isIndication ? "Indikasi (perlu ditinjau)" : e.category === "info" ? "Info (bukan indikasi)" : "Tidak dapat dianalisis"], ["Waktu kejadian", fmtTime(e.start_ts)], ["Durasi", e.status === "open" ? "Masih berlangsung" : fmtDuration(e.duration_s)], ["Skor model", scoreText(e)], ["Status validasi", reviewLabel(e.review_status)], ["Versi model", e.model_version || "—"]].map(([label, value]) => <div key={label} className="flex justify-between gap-4"><dt className="text-slate-500">{label}</dt><dd className="text-right font-semibold text-slate-800">{value}</dd></div>)}</dl><div className="mt-6 rounded-md bg-amber-50 p-4"><p className="text-xs font-bold uppercase tracking-wide text-amber-700">Alasan dari sistem</p><p className="mt-2 text-sm leading-6 text-amber-900">{e.reason || "—"}</p>{e.sound_text && <p data-testid="sound-text" className="mt-2 border-t border-amber-200 pt-2 text-sm font-semibold leading-6 text-amber-900">{e.sound_text}</p>}</div><p className="mt-4 text-xs leading-5 text-slate-500">Skor tersedia untuk deteksi objek dan suara; aturan durasi (mis. wajah tidak terlihat) tidak memiliki skor. Jenis suara hanya menyebut apa yang terdengar, bukan siapa yang berbicara atau berapa orang. Ambang aturan masih bersifat sementara dan belum divalidasi pada data sekolah.</p>{role !== "Pihak Sekolah" && <Button variant="secondary" className="mt-4 w-full" onClick={() => { setStudentId(e.student_id); go("student-detail"); }}>Buka detail siswa</Button>}</aside></div>}
  </main></AppShell>;
}

function ReportRow({ e, editable, retentionText, restrictedText, canViewEvidence, onSaved, onEnlarge, onImageError, go }: { e: ReportEvent; editable: boolean; retentionText: string; restrictedText: string; canViewEvidence: boolean; onSaved: (r: { event: ReportEvent; indications: ReportSummary }) => void; onEnlarge: (id: string) => void; onImageError: () => void; go: (s: Screen) => void }) {
  const { setEventId } = useSel();
  const saved = e.last_review?.note ?? "";
  const [note, setNote] = useState(saved);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [syncedNote, setSyncedNote] = useState(saved);
  if (saved !== syncedNote) { setSyncedNote(saved); setNote(saved); }
  const save = async (body: { decision?: Decision; note?: string }) => {
    setBusy(true); setError("");
    try { onSaved(await api.reviewPatch(e.event_id, body)); } catch (err) { setError((err as Error).message); setNote(saved); } finally { setBusy(false); }
  };
  const ev = e.evidence;
  return <tr className={`border-t border-slate-100 align-top ${!e.review_status ? "bg-amber-50/50" : ""}`}>
    <td className="px-5 py-4 font-semibold text-slate-800">{e.student?.name}</td>
    <td className="px-5 py-4 text-slate-600">{eventTitle(e)}{e.sound_text && <span className="mt-1 block text-xs leading-5 text-slate-500">{e.sound_text}</span>}</td>
    <td className="px-5 py-4 text-slate-500">{fmtTime(e.start_ts)}</td>
    <td className="px-5 py-4">{editable ? <select aria-label={`Status validasi ${e.student?.name}`} value={e.review_status ?? ""} disabled={busy} onChange={(x) => void save({ decision: x.target.value as Decision })} className="h-9 w-44 rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-700 disabled:opacity-60"><option value="" disabled>Belum ditinjau</option>{(["Valid", "Tidak Valid", "Perlu Tinjauan Lanjut"] as Decision[]).map((d) => <option key={d} value={d}>{d}</option>)}</select> : <Badge tone={reviewTone(e.review_status)}>{e.review_status ?? "Belum ditinjau"}</Badge>}{error && <p role="alert" className="mt-1.5 max-w-44 text-xs leading-5 text-red-700">{error}</p>}</td>
    <td className="px-5 py-4 text-slate-500">{editable ? <textarea aria-label={`Catatan pengawas ${e.student?.name}`} rows={2} maxLength={2000} value={note} disabled={busy || !e.review_status} placeholder={e.review_status ? "Tulis catatan" : "Pilih status dahulu"} onChange={(x) => setNote(x.target.value)} onBlur={() => { if (note.trim() !== saved) void save({ note }); }} className="w-52 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700 disabled:bg-slate-50" /> : e.last_review?.note || "—"}</td>
    <td className="px-5 py-4">{ev.url ? <button onClick={() => onEnlarge(e.event_id)} aria-label={`Perbesar gambar bukti ${e.student?.name}`} className="block overflow-hidden rounded-md"><img src={api.reportFrameSrc(ev.url)} alt="" onError={onImageError} className="h-14 w-20 bg-slate-100 object-cover" /></button> : <p className="max-w-36 text-xs leading-5 text-slate-500">{ev.state === "deleted" ? retentionText : ev.state === "none" ? "Tidak ada gambar" : restrictedText}</p>}{canViewEvidence && e.evidence_id && <button onClick={() => { setEventId(e.event_id); go("detail"); }} className="mt-1.5 block text-xs font-semibold text-blue-700 hover:underline">Lihat Evidence</button>}</td>
  </tr>;
}

/** Ringkasan angka pengganti diagram Laporan Sesi (Admin dan Pengawas). Data dan rumusnya sama dengan diagramnya. */
function StatRows({ rows, total, mismatch }: { rows: { label: ReactNode; value: ReactNode }[]; total: { label: string; value: number }; mismatch: string | null }) {
  return <div>
    <dl className="divide-y divide-slate-100 text-sm">
      {rows.map((r, i) => <div key={i} className="flex items-start justify-between gap-3 py-2"><dt className="text-slate-600">{r.label}</dt><dd className="text-right font-semibold tabular-nums text-navy">{r.value}</dd></div>)}
      <div className="flex items-start justify-between gap-3 border-t border-slate-200 pt-2.5 font-semibold text-slate-900"><dt>{total.label}</dt><dd className="tabular-nums">{total.value}</dd></div>
    </dl>
    {mismatch && <p className="mt-2 text-xs text-[#8c621a]">{mismatch}</p>}
  </div>;
}

function Report({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const { exam, exams, loading: examsLoading, error: examsError } = useCurrentExam();
  const { setExamId } = useSel();
  const rep = usePoll(() => (exam ? api.report(exam.id) : Promise.resolve(null)), [exam?.id]);
  const [confirm, setConfirm] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [finalError, setFinalError] = useState("");
  const [exportType, setExportType] = useState<"PDF" | "Excel" | null>(null);
  const [exporting, setExporting] = useState(false);
  const [enlarged, setEnlarged] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const refreshedAt = useRef(0);
  const r: ReportData | null = rep.data && rep.data.exam.id === exam?.id ? rep.data : null;   // never show the previous session
  const ind = r?.indications;
  const big = r?.events.find((e) => e.event_id === enlarged);
  const onSaved = (x: { event: ReportEvent; indications: ReportSummary }) => rep.setData((d) => d && { ...d, indications: x.indications, events: d.events.map((e) => (e.event_id === x.event.event_id ? x.event : e)) });
  // Signed image URLs last five minutes; ask for fresh ones, at most once a minute.
  const onImageError = () => { if (Date.now() - refreshedAt.current > 60000) { refreshedAt.current = Date.now(); void rep.reload(); } };
  const doExport = async () => {
    if (!r || !exportType) return;
    setExporting(true);
    try {
      await api.exportReport(r.exam.id, exportType === "PDF" ? "pdf" : "xlsx");
      setToast(`Laporan ${exportType} diunduh.`); setExportType(null);
    } catch (e) { setToast((e as Error).message); setExportType(null); } finally { setExporting(false); }
  };
  const finalize = async () => {
    if (!r) return;
    setFinalizing(true); setFinalError("");
    try { rep.setData(await api.finalizeReport(r.exam.id)); setConfirm(false); setToast("Laporan difinalisasi. Data sesi terkunci."); } catch (e) { setFinalError((e as Error).message); } finally { setFinalizing(false); }
  };
  const openConfirm = () => { setFinalError(""); setConfirm(true); };
  const blocked = ind?.unreviewed ? `Masih ada ${ind.unreviewed} indikasi yang belum ditinjau. Tinjau semuanya sebelum memfinalisasi laporan.` : r?.exam.monitoring_active ? "Pemantauan AI masih berjalan. Hentikan pemantauan sebelum memfinalisasi laporan." : "";
  const images = r?.events.filter((e) => e.evidence.state === "available").length ?? 0;
  return <AppShell active="report" go={go} title="Laporan Sesi"><main className="p-4 sm:p-8">
    <PageTitle eyebrow={r ? (r.final ? "Laporan final" : r.exam.status === "Selesai" ? "Sesi selesai" : r.exam.status) : undefined} title="Laporan Sesi" description={r ? `${r.exam.name} • ${fmtDate(r.exam.date)}, ${examTime(r.exam)}` : exam || examsLoading ? "Memuat..." : "Pilih sesi ujian."} action={<div className="flex flex-wrap gap-2"><select aria-label="Pilih sesi" value={exam?.id ?? ""} onChange={(e) => setExamId(Number(e.target.value))} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600">{exams.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select><Button variant="secondary" icon="download" disabled={!r} onClick={() => setExportType("PDF")}>Export PDF</Button><Button variant="secondary" icon="download" disabled={!r} onClick={() => setExportType("Excel")}>Export Excel</Button>{r?.can_edit && <Button onClick={openConfirm}>Finalisasi Laporan</Button>}</div>} />
    {(examsError || rep.error) && <div role="alert" className="mb-5 flex items-center justify-between gap-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-700"><span>{examsError || rep.error}</span><Button variant="secondary" className="h-8 shrink-0 px-3 text-xs" onClick={() => void rep.reload()}>Coba lagi</Button></div>}
    {!r && !rep.error && !examsError && <p role="status" className="rounded-md border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">{exam || examsLoading || rep.loading ? "Memuat laporan..." : "Belum ada sesi ujian untuk dilaporkan."}</p>}
    {r && <>
      {r.final && <div className="mb-5 flex items-start gap-3 rounded-md border border-emerald-200 bg-emerald-50 p-4"><span className="text-emerald-700"><Icon name="shield" size={18} /></span><div><p className="text-sm font-bold text-emerald-900">Laporan final, data terkunci</p><p className="mt-1 text-xs leading-5 text-emerald-800">Difinalisasi oleh {r.final.finalized_by} pada {fmtDateTime(r.final.finalized_at)}. Gambar bukti dihapus otomatis {r.frame_retention_hours} jam setelah finalisasi.</p></div></div>}
      <div className="mb-5 grid gap-4 xl:grid-cols-3"><section className="rounded-md border border-slate-200 bg-white p-5"><p className="text-xs font-bold uppercase tracking-widest text-slate-400">Informasi Sesi</p><div className="mt-4 space-y-2 text-sm">{[["Nama", r.exam.name], ["Tanggal", fmtDate(r.exam.date)], ["Jam", examTime(r.exam)], ["Durasi", `${r.exam.duration_min} menit`], ["Pengawas", r.exam.supervisor?.name ?? "—"]].map(([k, v]) => <div key={k} className="flex justify-between gap-4"><span className="text-slate-500">{k}</span><span className="text-right font-semibold text-slate-800">{v}</span></div>)}</div></section><section className="rounded-md border border-slate-200 bg-white p-5"><p className="text-xs font-bold uppercase tracking-widest text-slate-400">Kehadiran</p><div className="mt-4">{chartsOnDashboard(role) ? (() => { const a = attendanceParts(r.attendance); const periods = ind!.cannot_analyze; const mins = Math.round(ind!.cannot_analyze_s / 60);
          return <StatRows rows={[...a.segments.map((s) => ({ label: s.label, value: s.value })), { label: <>Periode tidak terbaca<span className="block text-xs text-[#7d8794]">Dihitung per periode, bukan per siswa</span></>, value: `${periods}${periods ? ` (± ${mins} menit)` : ""}` }]}
            total={{ label: "Total peserta", value: a.total }} mismatch={a.mismatch} />; })()
          : <Suspense fallback={<ChartSkeleton h={160} />}><ReportAttendance attendance={attendanceParts(r.attendance)} unreadable={{ periods: ind!.cannot_analyze, seconds: ind!.cannot_analyze_s }} /></Suspense>}</div></section>
        <section className="rounded-md border border-slate-200 bg-white p-5"><p className="text-xs font-bold uppercase tracking-widest text-slate-400">Hasil indikasi</p><p className="mt-1 text-xs text-slate-500">Valid = dikonfirmasi pengawas, bukan bukti dari AI.</p><div className="mt-4">{chartsOnDashboard(role) ? (() => { const res = reportResults(ind!);
          return <StatRows rows={res.segments.map((s) => ({ label: s.label, value: s.value }))} total={{ label: "Total indikasi", value: res.total }} mismatch={res.mismatch} />; })()
          : <Suspense fallback={<ChartSkeleton h={120} />}><ReportResults results={reportResults(ind!)} /></Suspense>}</div></section></div>
      {ind!.unreviewed > 0 && <div className="mb-5 flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-4"><span className="text-amber-600"><Icon name="bell" size={18} /></span><div><p className="text-sm font-bold text-amber-900">{ind!.unreviewed} indikasi belum ditinjau</p><p className="mt-1 text-xs leading-5 text-amber-800">Laporan baru dapat difinalisasi setelah semua indikasi ditinjau.</p></div></div>}
      <div className="overflow-x-auto rounded-md border border-slate-200 bg-white"><div className="flex min-w-[620px] divide-x divide-slate-200">{[[`${r.attendance.joined} dari ${r.attendance.enrolled}`, "Kehadiran", "green"], [String(ind!.total), "Total Indikasi", "amber"], [String(ind!.total - ind!.unreviewed), "Sudah ditinjau", "blue"], [String(ind!.unreviewed), "Belum ditinjau", "gray"]].map(([num, label, tone]) => <div key={label} className="flex flex-1 items-center gap-3 px-4 py-3"><span className={`size-2 rounded-full ${tone === "green" ? "bg-emerald-500" : tone === "amber" ? "bg-amber-500" : tone === "blue" ? "bg-blue-700" : "bg-slate-400"}`} /><div><p className="text-lg font-bold leading-5 text-slate-900">{num}</p><p className="mt-0.5 whitespace-nowrap text-xs text-slate-500">{label}</p></div></div>)}</div></div>
      <section className="mt-6 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex items-center justify-between gap-3 border-b border-slate-100 p-5"><div><h2 className="font-bold text-slate-900">Rincian Indikasi</h2><p className="mt-1 text-xs leading-5 text-slate-500">{r.ai_notice}</p></div><Badge tone={ind!.unreviewed ? "amber" : "green"}>{ind!.unreviewed} belum ditinjau</Badge></div>{r.events.length === 0 ? <p className="p-8 text-center text-sm text-slate-500">Belum ada kejadian yang tercatat oleh sistem pemantauan pada sesi ini.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[960px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Siswa</th><th className="px-5 py-3.5">Jenis Indikasi</th><th className="px-5 py-3.5">Waktu</th><th className="px-5 py-3.5">Status validasi</th><th className="px-5 py-3.5">Catatan Pengawas</th><th className="px-5 py-3.5">Gambar bukti</th></tr></thead><tbody>{r.events.map((e) => <ReportRow key={e.event_id} e={e} editable={r.can_edit} retentionText={r.retention_text} restrictedText={r.restricted_text} canViewEvidence={r.can_view_evidence} onSaved={onSaved} onEnlarge={setEnlarged} onImageError={onImageError} go={go} />)}</tbody></table></div>}</section>
      {(r.sound_info?.length ?? 0) > 0 && <section data-testid="sound-info" className="mt-6 rounded-md border border-slate-200 bg-white p-5"><h2 className="font-bold text-slate-900">Catatan suara (info, bukan indikasi)</h2><p className="mt-1 text-xs leading-5 text-slate-500">Dicatat sebagai konteks tanpa gambar bukti dan tanpa validasi. Hanya jenis suara, bukan identitas atau jumlah pembicara.</p><ul className="mt-3 space-y-1 text-sm text-slate-700">{r.sound_info!.map((x) => <li key={x.indicator}>{x.label}: {x.count} kali, sekitar {Math.round(x.total_s)} detik</li>)}</ul></section>}
      <section className="mt-6 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="border-b border-slate-100 p-5"><h2 className="font-bold text-slate-900">Aktivitas Pengawas</h2><p className="mt-1 text-xs text-slate-500">Audit log hanya-baca dan tidak dapat diedit atau dihapus.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Aktivitas</th><th className="px-5 py-3">Waktu</th><th className="px-5 py-3">User</th><th className="px-5 py-3">Status</th></tr></thead><tbody>{r.activity.map((row, i) => <tr key={i} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{row.action}</td><td className="px-5 py-4 text-slate-500">{fmtDateTime(row.ts)}</td><td className="px-5 py-4 text-slate-600">{row.user_name}</td><td className="px-5 py-4"><Badge tone="green">{row.status}</Badge></td></tr>)}</tbody></table>{r.activity.length === 0 && <p className="p-6 text-center text-sm text-slate-500">Belum ada aktivitas.</p>}</div></section>
    </>}
    {big?.evidence.url && <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/80 p-4" onClick={() => setEnlarged(null)}><section role="dialog" aria-modal="true" aria-label="Gambar bukti" className="w-full max-w-3xl overflow-hidden rounded-lg bg-white" onClick={(x) => x.stopPropagation()}><div className="flex items-center justify-between gap-3 border-b border-slate-100 p-4"><div><p className="text-sm font-bold text-slate-900">{big.student?.name} · {eventTitle(big)}</p><p className="mt-0.5 text-xs text-slate-500">{fmtTime(big.start_ts)} · hal yang perlu diperiksa pengawas</p></div><button onClick={() => setEnlarged(null)} aria-label="Tutup" className="tap relative"><Icon name="close" /></button></div><img src={api.reportFrameSrc(big.evidence.url)} alt={`Gambar bukti ${big.student?.name}`} onError={onImageError} className="max-h-[75vh] w-full bg-slate-900 object-contain" /></section></div>}
    {confirm && <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-900/40 p-4"><section role="dialog" aria-modal="true" className="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-md border border-slate-200 bg-white p-6"><div className="grid size-11 place-items-center rounded-md bg-amber-50 text-amber-700"><Icon name="report" /></div><h2 className="mt-5 text-lg font-bold text-slate-900">Finalisasi laporan?</h2><p className="mt-2 text-sm leading-6 text-slate-500">{blocked || `Semua indikasi sudah ditinjau. Data sesi akan dikunci dan finalisasi tidak dapat dibatalkan. ${images} gambar bukti disimpan untuk laporan dan dihapus otomatis ${r?.frame_retention_hours} jam setelah finalisasi.`}</p>{finalError && <p role="alert" className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm leading-5 text-red-700">{finalError}</p>}<div className="mt-6 flex justify-end gap-3"><Button variant="secondary" onClick={() => setConfirm(false)}>{blocked ? "Tutup" : "Batal"}</Button>{!blocked && <Button disabled={finalizing} onClick={() => void finalize()}>{finalizing ? "Memproses..." : "Ya, Finalisasi"}</Button>}</div></section></div>}
    {exportType && <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-900/40 p-4"><section role="dialog" aria-modal="true" className="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-md border border-slate-200 bg-white p-6"><div className="grid size-11 place-items-center rounded-md bg-blue-50 text-blue-700"><Icon name="download" /></div><h2 className="mt-5 text-lg font-bold text-slate-900">Export Laporan {exportType}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{exportType === "Excel" ? "Tabel indikasi diunduh sebagai berkas Excel." : `Laporan Hasil Pengawasan Ujian diunduh sebagai PDF.${r?.final ? "" : " Karena belum final, dokumen diberi tanda DRAF."}`} Berkas yang diunduh berada di luar aturan penghapusan otomatis EduAI, jadi simpan dengan hati-hati dan jangan disebarluaskan.</p><div className="mt-6 flex justify-end gap-3"><Button variant="secondary" onClick={() => setExportType(null)}>Batal</Button><Button disabled={exporting} onClick={() => void doExport()}>{exporting ? "Menyiapkan..." : "Ya, Export"}</Button></div></section></div>}
    {toast && <div role="status" className="fixed bottom-20 right-4 z-50 md:bottom-6 md:right-6 flex items-center gap-3 rounded-md border border-slate-200 bg-white p-4 text-sm font-semibold text-slate-800"><Icon name="check" size={18} />{toast}<button onClick={() => setToast("")} aria-label="Tutup" className="tap relative ml-3 text-slate-400"><Icon name="close" size={16} /></button></div>}
  </main></AppShell>;
}

function StudentList({ go }: { go: (s: Screen) => void }) {
  const { exam } = useCurrentExam();
  const { setStudentId } = useSel();
  const { role } = useRole();
  const rows = usePoll(() => (exam ? api.students(exam.id) : Promise.resolve([] as StudentRow[])), [exam?.id], 10000);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("Semua status");
  const [sort, setSort] = useState("Indikasi terbanyak");
  const data = (rows.data ?? []).filter((r) => (r.name.toLowerCase().includes(q.toLowerCase()) || (r.nis ?? "").includes(q)) && (status === "Semua status" || studentStatus(r) === status))
    .sort((a, b) => sort === "Nama A–Z" ? a.name.localeCompare(b.name) : (sort === "Indikasi terbanyak" ? -1 : 1) * ((a.counts?.indications ?? 0) - (b.counts?.indications ?? 0)));
  return <AppShell active="students" go={go} title="Daftar Siswa"><main className="p-4 sm:p-8"><PageTitle title="Daftar Siswa" description={exam ? `Peserta pada ${exam.name}.` : "Memuat..."} />
    {rows.error && <Notice tone="red">{rows.error}</Notice>}
    <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex flex-col gap-3 border-b border-slate-100 p-5 xl:flex-row xl:items-center"><div className="relative flex-1"><span className="absolute left-3 top-2.5 text-slate-400"><Icon name="search" size={17} /></span><input value={q} onChange={(e) => setQ(e.target.value)} className="h-10 w-full rounded-md border border-slate-200 pl-9 pr-3 text-sm" placeholder="Cari nama atau NIS/NISN" /></div><select value={status} onChange={(e) => setStatus(e.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600"><option>Semua status</option><option>Hadir</option><option>Belum bergabung</option><option>Kamera mati</option><option>Mikrofon mati</option><option>Terputus</option></select><select value={sort} onChange={(e) => setSort(e.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600"><option>Indikasi terbanyak</option><option>Indikasi tersedikit</option><option>Nama A–Z</option></select></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Nama Siswa</th><th className="px-5 py-3.5">NIS/NISN</th><th className="px-5 py-3.5">Status</th><th className="px-5 py-3.5">Jumlah Indikasi</th><th className="px-5 py-3.5">Belum Ditinjau</th><th className="px-5 py-3.5">Aksi</th></tr></thead><tbody>{data.map((r) => { const st = studentStatus(r); return <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50"><td className="px-5 py-4"><div className="flex items-center gap-3"><div className="grid size-9 place-items-center rounded-full bg-blue-50 text-xs font-bold text-blue-700">{initials(r.name)}</div><span className="font-semibold text-slate-800">{r.name}</span></div></td><td className="px-5 py-4 text-slate-500">{r.nis}</td><td className="px-5 py-4"><Badge tone={st === "Hadir" ? "green" : st === "Belum bergabung" ? "gray" : "amber"}>{st}</Badge></td><td className="px-5 py-4 font-semibold text-slate-700">{r.counts?.indications ?? "—"}</td><td className="px-5 py-4"><Badge tone={(r.counts?.unreviewed ?? 0) === 0 ? "gray" : "amber"}>{r.counts?.unreviewed ?? "—"}</Badge></td><td className="px-5 py-4">{MONITOR_ROLES.includes(role) && <button onClick={() => { setStudentId(r.id); go("student-detail"); }} className="tap relative text-xs font-semibold text-blue-700">Detail Siswa</button>}</td></tr>; })}</tbody></table></div></section>
    <div className="mt-4 flex items-start gap-3 rounded-md bg-slate-100 p-4 text-xs leading-5 text-slate-600"><Icon name="shield" size={17} /><p>Hanya informasi akademik dan pemantauan yang relevan yang ditampilkan. Data pribadi lain tidak disimpan pada halaman ini.</p></div>
  </main></AppShell>;
}

function Settings({ go }: { go: (s: Screen) => void }) {
  const [section, setSection] = useState("Profil");
  const { role } = useRole();
  const { user, setUser } = useUser();
  const school = useSchoolName();
  // Profil: the full name is saved on the server (PATCH /api/auth/me). Email (login), institution and role are read-only.
  const [name, setName] = useState(user?.name ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const cleanName = name.trim().replace(/\s+/g, " ");
  const nameError = cleanName.length < 2 ? "Nama lengkap minimal 2 karakter." : cleanName.length > 120 ? "Nama lengkap maksimal 120 karakter." : "";
  const dirty = !!user && cleanName !== user.name;
  const saveProfile = async () => {
    if (!dirty || nameError) return;
    setSaving(true); setMsg(null);
    try {
      const u = await api.updateMe(cleanName);
      setUser(u); const t = session.token(); if (t) session.set(t, u);
      setName(u.name); setMsg({ ok: true, text: "Profil tersimpan." });
    } catch (e) { setMsg({ ok: false, text: (e as Error).message || "Profil tidak tersimpan. Coba lagi." }); }
    finally { setSaving(false); }
  };
  const readOnlyField = (label: string, value: string, hint: string) => <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">{label}</span>
    <input readOnly value={value} aria-describedby={`hint-${label}`} className="h-11 w-full cursor-not-allowed rounded-md border border-slate-200 bg-slate-50 px-3.5 text-sm text-slate-600 outline-none" />
    <span id={`hint-${label}`} className="mt-1 block text-xs text-slate-500">{hint}</span></label>;
  const menu = role === "Pengawas" ? ["Profil", "Preferensi pemantauan", "Notifikasi", "Privasi", "Keamanan akun"] : ["Profil", "Keamanan akun"];
  return <AppShell active="settings" go={go} title="Pengaturan"><main className="mx-auto max-w-6xl p-4 sm:p-8"><PageTitle title="Pengaturan" description="Kelola preferensi akun, pemantauan, keamanan, dan privasi data." /><div className="grid gap-6 lg:grid-cols-[250px_1fr]"><aside className="h-fit rounded-md border border-slate-200 bg-white p-2">{menu.map(x => <button key={x} onClick={() => setSection(x)} className={`w-full rounded-md px-3 py-2.5 text-left text-sm font-semibold ${section === x ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50"}`}>{x}</button>)}</aside>
    <section className="rounded-md border border-slate-200 bg-white p-6"><div className="border-b border-slate-100 pb-5"><h2 className="font-bold text-slate-900">{section}{section !== "Profil" && section !== "Privasi" && <SampleTag />}</h2><p className="mt-1 text-sm text-slate-500">{section === "Privasi" ? "Atur akses dan penggunaan data pemantauan ujian." : `Kelola pengaturan ${section.toLowerCase()} Anda.`}</p></div>
      {section === "Profil" ? <form id="form-profil" onSubmit={(e) => { e.preventDefault(); void saveProfile(); }} className="mt-6 grid gap-5 sm:grid-cols-2">
        <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Nama lengkap</span>
          <input name="name" value={name} onChange={(e) => { setName(e.target.value); setMsg(null); }} maxLength={120} autoComplete="name" aria-invalid={!!nameError} aria-describedby="hint-nama"
            className={`h-11 w-full rounded-md border bg-white px-3.5 text-sm text-slate-800 outline-none transition focus:ring-4 ${nameError ? "border-red-400 focus:ring-red-50" : "border-slate-200 focus:border-blue-500 focus:ring-blue-50"}`} />
          <span id="hint-nama" className={`mt-1 block text-xs ${nameError ? "text-red-600" : "text-slate-500"}`}>{nameError || "Nama ini tampil untuk pengawas dan di laporan."}</span></label>
        {readOnlyField("Email", user?.email ?? NO_DATA, "Dipakai untuk masuk. Hubungi admin untuk mengubahnya.")}
        {readOnlyField("Institusi", school ?? NO_DATA, "Diatur oleh sekolah.")}
        {readOnlyField("Peran", role, "Diatur oleh admin.")}
      </form> : section === "Privasi" ? <div className="mt-6 space-y-4"><div className="rounded-md bg-blue-50 p-5"><div className="flex gap-3"><Icon name="shield" size={20} /><div><p className="text-sm font-bold text-blue-900">Data untuk pengawasan ujian</p><p className="mt-2 text-sm leading-6 text-blue-800">Cuplikan gambar bukti Indikasi hanya digunakan untuk pengawasan, peninjauan, dan pelaporan ujian oleh pihak berwenang, dan dihapus otomatis sesuai aturan masa simpan yang ditampilkan saat persetujuan. Video penuh dan audio tidak disimpan oleh EduAI.</p></div></div></div></div> : <div className="mt-6 space-y-3">{["Pemberitahuan Indikasi baru", "Peringatan masalah koneksi", "Keamanan akun"].map((x, i) => <div key={x} className="flex items-center justify-between rounded-md border border-slate-200 p-4"><div><p className="text-sm font-semibold text-slate-800">{x}</p><p className="mt-1 text-xs text-slate-500">{i === 0 ? "Tampilkan notifikasi tanpa mengganggu pemantauan." : "Kirimkan informasi penting ke pengguna."}</p></div><span className="relative h-6 w-11 rounded-full bg-blue-700"><span className="absolute right-1 top-1 size-4 rounded-full bg-white" /></span></div>)}</div>}
      <div className="mt-6 flex items-center justify-end gap-4">
        {section === "Profil" && msg && <p role="status" className={`text-sm ${msg.ok ? "text-emerald-700" : "text-red-600"}`}>{msg.text}</p>}
        {section === "Profil" ? <Button onClick={() => void saveProfile()} disabled={!dirty || !!nameError || saving}>{saving ? "Menyimpan…" : "Simpan perubahan"}</Button> : <Button disabled>Simpan perubahan</Button>}
      </div></section></div></main></AppShell>;
}

function StudentDashboard({ go }: { go: (s: Screen) => void }) {
  const { user } = useUser();
  const school = useSchoolName();
  const { setExamId } = useSel();
  const list = usePoll(() => api.exams(), [], 15000);
  const exams = list.data ?? [];
  const pick = (status: string) => exams.find((e) => e.status === status);
  const cards = [["Sedang berlangsung", pick("Sedang Berlangsung"), "blue"], ["Akan datang", pick("Terjadwal"), "gray"], ["Selesai", pick("Selesai"), "green"]] as [string, Exam | undefined, string][];
  return <AppShell active="dashboard" go={go} title="Dasbor Siswa"><main className="p-4 sm:p-8">
    <PageTitle title={`${greeting()}, ${user?.name.split(" ")[0] ?? ""}`} description="Lihat jadwal dan status ujian Anda di satu tempat." />
    {list.error && <Notice tone="red">{list.error}</Notice>}
    <div className="grid gap-5 lg:grid-cols-3">{cards.map(([status, e, tone]) => <section key={status} className="rounded-md border border-slate-200 bg-white p-5"><Badge tone={tone as "blue" | "gray" | "green"}>{status}</Badge><h2 className="mt-4 font-bold text-slate-900">{e?.name ?? "Tidak ada ujian"}</h2><p className="mt-2 text-sm text-slate-500">{e ? (status === "Sedang berlangsung" ? examTime(e) : `${fmtDate(e.date)} • ${e.start_time.replace(":", ".")} WIB`) : "—"}</p><p className="mt-1 text-xs text-slate-400">{e?.class_name ?? user?.class_name} • {school === undefined ? "…" : school ?? NO_DATA}</p>{status === "Sedang berlangsung" && e && <Button className="mt-5 w-full" onClick={() => { setExamId(e.id); go("device"); }}>Cek perangkat & masuk</Button>}</section>)}</div>
    <section className="mt-6 rounded-md border border-blue-100 bg-blue-50 p-5"><div className="flex gap-3"><Icon name="shield" size={20} /><div><p className="text-sm font-bold text-blue-900">Privasi peserta dilindungi</p><p className="mt-1 text-sm leading-6 text-blue-800">Siswa hanya dapat mengikuti ujian dan tidak memiliki akses ke video pemantauan, Indikasi, validasi, atau laporan final.</p></div></div></section>
  </main></AppShell>;
}

function MyExams({ go }: { go: (s: Screen) => void }) {
  const { user } = useUser();
  const { setExamId } = useSel();
  const list = usePoll(() => api.exams(), [], 15000);
  // Status filter so a student finds running, scheduled or finished exams quickly (counts from the same list).
  const [filter, setFilter] = useState<StudentFilter>("semua");
  const all = list.data ?? [];
  const counts = studentFilterCounts(all);
  const rows = filterStudentExams(all, filter).map((e) => ({ ...e, timing: e.status === "Sedang Berlangsung" ? "active" : e.status === "Selesai" ? "ended" : "upcoming" }));
  return <AppShell active="my-exams" go={go} title="Ujian Saya"><main className="p-4 sm:p-8"><PageTitle title="Ujian Saya" description={`Hanya ujian yang didaftarkan Admin untuk ${user?.name ?? ""} • ${user?.class_name ?? ""}.`} />{list.error && <Notice tone="red">{list.error}</Notice>}
    <div role="toolbar" aria-label="Saring status ujian" className="-mx-4 mb-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0">
      {STUDENT_FILTERS.map((f) => { const on = filter === f.key; return <button key={f.key} type="button" aria-pressed={on} data-exam-filter={f.key} data-count={counts[f.key]} onClick={() => setFilter(f.key)}
        className={`flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-full border px-3.5 text-[13px] font-semibold outline-none focus-visible:ring-2 focus-visible:ring-[#c9a227] ${on ? "border-navy bg-navy text-white" : "border-line bg-white text-[#334054] hover:bg-paper"}`}>
        {f.key !== "semua" && <i aria-hidden="true" className={`size-2 rounded-full ${f.key === "berlangsung" ? "bg-gold-500" : f.key === "terjadwal" ? "bg-[#3d628e]" : "bg-[#23856d]"}`} />}
        {f.label}<span className={`rounded-full px-1.5 text-xs tabular-nums ${on ? "bg-white/15 text-white" : "bg-paper text-[#687382]"}`}>{counts[f.key]}</span></button>; })}
    </div>
    <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Nama ujian</th><th className="px-5 py-3.5">Tanggal</th><th className="px-5 py-3.5">Jam mulai</th><th className="px-5 py-3.5">Durasi</th><th className="px-5 py-3.5">Status</th><th className="px-5 py-3.5">Aksi</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{row.name}</td><td className="px-5 py-4 text-slate-600">{fmtDate(row.date)}</td><td className="px-5 py-4 text-slate-600">{row.start_time.replace(":", ".")} WIB</td><td className="px-5 py-4 text-slate-600">{row.duration_min} menit</td><td className="px-5 py-4"><Badge tone={row.timing === "ended" ? "green" : row.timing === "active" ? "blue" : "gray"}>{row.status}</Badge></td><td className="px-5 py-4">{row.timing === "active" ? <Button className="h-9" onClick={() => { setExamId(row.id); go(row.seb?.required ? "seb-check" : "device"); }}>Mulai Ujian</Button> : <div><Button className="h-9" disabled>Mulai Ujian</Button><p className="mt-1.5 text-[10px] text-slate-400">{row.timing === "upcoming" ? "Aktif saat jadwal dimulai" : "Waktu ujian telah berakhir"}</p></div>}</td></tr>)}</tbody></table>{!list.loading && rows.length === 0 && <p data-empty-exams className="p-8 text-center text-sm text-slate-500">{filter === "semua" ? "Belum ada ujian untuk Anda." : `Tidak ada ujian dengan status "${STUDENT_FILTERS.find((f) => f.key === filter)!.label}".`}</p>}{!list.loading && rows.length === 0 && <p className="p-6 text-center text-sm text-slate-500">Belum ada ujian yang didaftarkan untuk Anda.</p>}</div><div className="border-t border-blue-100 bg-blue-50 p-4 text-xs leading-5 text-blue-800">Akses ujian divalidasi berdasarkan daftar peserta dan status ujian yang ditentukan Admin.</div></section></main></AppShell>;
}

function InstitutionDashboard({ go, role }: { go: (s: Screen) => void; role: "Penyelenggara Ujian" | "Pihak Sekolah" }) {
  const organizer = role === "Penyelenggara Ujian";
  const school = useSchoolName();
  const { setExamId } = useSel();
  const d = usePoll(() => api.dashboard(), [], 15000);
  const exams = d.data?.exams ?? [];
  const totalStudents = exams.reduce((a, e) => a + e.student_count, 0);
  const supervisors = new Set(exams.map((e) => e.supervisor?.id).filter(Boolean)).size;
  const validated = (d.data?.recent_indications ?? []).length;
  const cards = organizer ? [[exams.filter((e) => e.status === "Terjadwal").length, "Sesi terjadwal"], [totalStudents, "Kursi peserta"], [supervisors, "Pengawas bertugas"], [d.data?.summary?.active_sessions ?? 0, "Sesi aktif"]] : [[exams.length, "Sesi tercatat"], [exams.filter((e) => e.status === "Selesai").length, "Sesi selesai"], [validated, "Indikasi tervalidasi (terbaru)"], [exams.filter((e) => e.status === "Sedang Berlangsung").length, "Sesi berlangsung"]];
  return <AppShell active="dashboard" go={go} title={`Dasbor ${role}`}><main className="p-4 sm:p-8"><PageTitle title={organizer ? "Koordinasi ujian semester" : "Ringkasan akademik sekolah"} description={organizer ? "Pantau sesi, peserta, pengawas, dan laporan sesuai kewenangan yang diberikan." : "Pantau informasi sesi dan laporan final yang telah melalui validasi."} />
    {d.error && <Notice tone="red">{d.error}</Notice>}
    <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">{cards.map(([value, label]) => <section key={label} className="rounded-md border border-slate-200 bg-white p-4 sm:p-5"><p className="text-2xl font-bold text-slate-900">{value}</p><p className="mt-1 text-sm text-slate-500">{label}</p></section>)}</div>
    <section className="mt-6 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-5"><div><h2 className="font-bold text-slate-900">{organizer ? "Sesi dalam kewenangan Anda" : "Laporan terbaru"}</h2><p className="mt-1 text-xs text-slate-500">Data {school === undefined ? "…" : school ?? NO_DATA}</p></div><Button variant="ghost" onClick={() => go(organizer ? "sessions" : "report")}>Lihat semua</Button></div><div className="divide-y divide-slate-100">{exams.slice(0, 5).map((session) => <button key={session.id} onClick={() => { setExamId(session.id); go(organizer ? "exam-detail" : "report"); }} className="flex w-full items-center justify-between gap-4 p-5 text-left hover:bg-slate-50"><div><p className="text-sm font-semibold text-slate-800">{session.name}</p><p className="mt-1 text-xs text-slate-500">{fmtDate(session.date)} • {session.student_count} peserta</p></div><Badge tone={statusTone(session.status)}>{session.status}</Badge></button>)}</div></section>
  </main></AppShell>;
}

function AdminDashboard({ go }: { go: (s: Screen) => void }) {
  const users = usePoll(() => api.users(), []);
  const audit = usePoll(() => api.audit(), [], 15000);
  const health = usePoll<[Health, AIHealth]>(() => Promise.all([api.health(), api.aiHealth()]), [], 15000);
  const today = new Date().toDateString();
  const auditToday = (audit.data ?? []).filter((a) => new Date(a.ts).toDateString() === today).length;
  const ai = health.data?.[1];
  return <AppShell active="dashboard" go={go} title="Dasbor Admin"><main className="p-4 sm:p-8"><PageTitle title="Administrasi EduAI" description="Kelola ujian, akses, konfigurasi, retensi data, dan jejak aktivitas sistem." action={<Button icon="plus" onClick={() => go("create")}>Create Ujian</Button>} />
    <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">{[[String((users.data ?? []).filter((u) => u.active).length), "User aktif", "users"], ["5", "Role sistem", "shield"], [ai ? `${ai.evidence_retention_hours} jam` : "—", "Retensi evidence", "clock"], [String(auditToday), "Audit hari ini", "file"]].map(([value, label, icon]) => <button key={label} onClick={() => go(label === "User aktif" ? "users" : label === "Role sistem" ? "users" : label === "Retensi evidence" ? "retention" : "audit")} className="rounded-md border border-slate-200 bg-white p-4 text-left hover:border-blue-200 sm:p-5"><div className="flex items-center justify-between gap-2"><p className="text-xl font-bold text-slate-900 sm:text-2xl">{value}</p><span className="text-slate-400"><Icon name={icon as IconName} /></span></div><p className="mt-2 text-sm text-slate-500">{label}</p></button>)}</div>
    <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_.8fr]"><section className="rounded-md border border-slate-200 bg-white"><div className="border-b border-slate-100 p-5"><h2 className="font-bold text-slate-900">Aktivitas sistem terbaru</h2></div><div className="divide-y divide-slate-100">{(audit.data ?? []).slice(0, 6).map((row) => <div key={row.id} className="flex items-center gap-4 p-4"><div className="grid size-9 place-items-center rounded-full bg-slate-100 text-xs font-bold text-slate-600">{initials(row.user_name)}</div><div className="flex-1"><p className="text-sm font-semibold text-slate-800">{row.user_name}</p><p className="mt-0.5 text-xs text-slate-500">{row.action}</p></div><span className="text-xs text-slate-400">{fmtTime(row.ts).slice(0, 5)}</span></div>)}</div></section><section className="rounded-md border border-blue-100 bg-blue-50 p-5"><h2 className="font-bold text-blue-900">Status sistem</h2><div className="mt-5 space-y-4">{[["Backend", health.data ? "Normal" : health.error ? "Tidak terhubung" : "Memeriksa"], ["Layanan AI", ai ? (ai.available ? "Siap" : "Belum siap") : "—"], ["Model wajah", ai?.models.face_detector?.loaded ? "Dimuat" : "Tidak ada"], ["Head pose (Face Landmarker)", ai?.models.face_landmarker?.loaded ? "Dimuat" : "Tidak ada"], ["Deteksi ponsel (EfficientDet)", ai?.models.object_detector?.loaded ? "Dimuat" : "Tidak ada"], ["OpenVidu", health.data?.[0].livekit.configured ? "Terkonfigurasi" : "Belum dikonfigurasi"], ["Enkripsi evidence", ai?.evidence_encrypted ? "Aktif" : "Tidak aktif"]].map(([label, value]) => <div key={label} className="flex justify-between text-sm"><span className="text-blue-800">{label}</span><span className="font-semibold text-blue-900">{value}</span></div>)}</div>{ai && !ai.available && <p className="mt-4 text-xs text-blue-800">{ai.reason}</p>}</section></div>
    <DashboardChartHub go={go} withStatusDonut />
  </main></AppShell>;
}

function IndicationsPage({ go }: { go: (s: Screen) => void }) {
  // Grouped view: one row per case (same exam + student + indicator, repeated within the backend's gap window).
  // Original events stay available in the case panel and in the existing evidence page.
  const { role } = useRole();
  const { eventId } = useSel();
  const readOnly = role === "Pihak Sekolah";
  // Kind and status filter; kept in the URL query (?jenis=hp&status=belum) without changing the path. Only this staff
  // page writes the query (students in Safe Exam Browser never open it); the query is removed when leaving the page.
  const [filter, setFilterState] = useState<Filter>(() => parseFilter(window.location.search));
  const setFilter = (f: Filter) => { setFilterState(f); setSelId(null); };
  useEffect(() => {
    const { pathname, search, hash } = window.location;
    const next = filterQuery(filter, search);
    if (next !== search) window.history.replaceState(window.history.state, "", pathname + next + hash);
  }, [filter]);
  useEffect(() => () => {
    const { pathname, search, hash } = window.location;
    const q = new URLSearchParams(filterQuery({ jenis: null, status: null }, search)); q.delete("kasus");
    const next = q.toString() ? `?${q}` : "";
    if (next !== search) window.history.replaceState(window.history.state, "", pathname + next + hash);
  }, []);
  // ?kasus=<case_id> (link copied from the evidence viewer) selects that case.
  const [selId, setSelId] = useState<string | null>(() => new URLSearchParams(window.location.search).get("kasus"));
  const [since] = useState(() => sinceIso(Date.now()));
  const list = usePoll(() => api.cases(), [], 5000);
  const recent = usePoll(() => api.events({ category: "indication", since, limit: 500 }), [since], 30000);
  // last review per event (reviewer, decision, time) for "Aktivitas terbaru"; exams for the supervisor of each case
  const reviewed = usePoll(() => api.events({ category: "indication", limit: 500 }), [], 15000);
  const exams = usePoll(() => api.exams(), [], 60000);
  // Click = see the students: a kind button, a bar, a kind name or a donut part opens the drawer.
  const [drawer, setDrawer] = useState<DrawerSource | null>(null);
  // Kind buttons in the filter row: filter, then go straight to "Daftar kasus" below ("Tidak dapat dianalisis" is not a
  // case: go to its card). Bars, kind names and donut parts still open the student drawer.
  const scrollTo = (id: string) => window.setTimeout(() => document.getElementById(id)?.scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }), 60);
  const filterAndGo = (j: JenisKey | null) => { setFilter({ ...filter, jenis: j }); scrollTo("judul-daftar-kasus"); };
  const pickJenis = (j: JenisKey | null) => { const f = { ...filter, jenis: j }; setFilter(f); if (j && j !== "tidak-terbaca") setDrawer({ jenis: j, status: f.status }); };
  const pickStatus = (st: StatusKey | null) => { const f = { ...filter, status: st }; setFilter(f); if (st) setDrawer({ jenis: f.jenis, status: st }); };
  const rows = list.data?.cases ?? [];
  const visible = filterCases(rows, filter);
  const ofKind = filterCases(rows, { jenis: filter.jenis, status: null });
  const counts = jenisCounts(rows, [], filter.status);
  const ofStatus = filterCases(rows, { jenis: null, status: filter.status });
  const listRef = useRef<HTMLElement>(null);
  const toList = () => listRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  // open a case in the existing review panel below the list (the filter is cleared if it would hide the case)
  const openCase = (caseId: string) => {
    setDrawer(null);
    const c = rows.find((x) => x.case_id === caseId);
    if (c && !visible.some((x) => x.case_id === caseId)) setFilterState({ jenis: null, status: null });
    setSelId(caseId);
    window.setTimeout(() => document.querySelector(`[data-case="${CSS.escape(caseId)}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 50);
  };
  const now = list.data ? utcMs(list.data.server_time) ?? 0 : 0;
  const cur = visible.find((c) => c.case_id === selId) ?? (eventId ? visible.find((c) => c.event_ids.includes(eventId)) : undefined) ?? visible[0];
  return <AppShell active="indications" go={go} title="Daftar Indikasi"><main className="min-h-full bg-white p-4 sm:p-8">
    <div className="mb-5">
      <h1 className="text-2xl leading-tight">{readOnly ? "Indikasi Tervalidasi" : "Indikasi"}</h1>
      <p className="mt-1.5 text-sm text-[#626F86]">Indikasi bukan bukti pelanggaran. Keputusan tetap di tangan pengawas.{readOnly ? " Pihak sekolah hanya melihat hasil yang sudah ditinjau." : ""}</p>
    </div>
    {list.error && <Notice tone="red">{list.error}</Notice>}
    <div className="space-y-4">
      <FilterRow filter={filter} counts={counts} readOnly={readOnly} onJenis={filterAndGo} onStatus={(st) => setFilter({ ...filter, status: st })} />
      <KpiRow kpi={list.data && recent.data ? kpi7(visible, recent.data.events, utcMs(list.data.server_time) ?? 0) : null} />
      {/* three donuts side by side (one column on phones); Admin & Pengawas: on their Dasbor */}
      {!chartsOnDashboard(role) && <div className="grid gap-4 lg:grid-cols-3">
        <StatusDonut data={list.data ? statusSummary(ofKind) : null} selected={filter.status} onSelect={pickStatus} onAll={toList} />
        <KindDonut slices={list.data ? kindSlices(ofStatus) : null} selected={filter.jenis}
          onSelect={(sl) => (sl.kinds.length === 1 ? pickJenis(sl.kinds[0]) : setDrawer({ jenis: null, status: filter.status, kinds: sl.kinds, label: sl.label }))} />
        <LoadDonut slices={list.data && exams.data ? loadSlices(supervisorLoad(visible, exams.data)) : null} />
      </div>}
      <div className={`grid gap-4 ${chartsOnDashboard(role) ? "" : "lg:grid-cols-2"}`}>
        {!chartsOnDashboard(role) && <KindBarChart bars={list.data ? kindBars(ofStatus) : null} selected={filter.jenis} onSelect={pickJenis} />}
        <ActivityCard items={list.data && reviewed.data ? activityFeed(visible, reviewed.data.events) : null} now={now} capped={(reviewed.data?.events.length ?? 0) >= 500} onOpenCase={openCase} />
      </div>
    </div>
    {drawer && <StudentDrawer source={drawer} cases={drawerCases(rows, drawer)} canOpenEvidence={mayOpenEvidence(role)} onClose={() => setDrawer(null)} onOpenCase={openCase} />}
    <h2 id="judul-daftar-kasus" className="mb-3 mt-8 scroll-mt-24 font-sans text-sm font-bold text-[#1D2433]">Daftar kasus</h2>
    {list.data && <p className="mb-5 text-xs text-slate-500">{rows.length} kasus dari {list.data.total_events} deteksi. {list.data.gap_s > 0 ? `Kejadian dengan siswa, ujian, dan jenis indikasi sama yang berjarak paling lama ${Math.round(list.data.gap_s)} detik digabung` : "Satu kasus per siswa dan jenis perilaku untuk seluruh ujian; setiap kejadian tetap tercatat di dalamnya"}; jenis indikasi berbeda selalu menjadi kasus terpisah. Notifikasi muncul sekali, saat ambang perilaku pertama kali terpenuhi.</p>}
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <section ref={listRef} id="daftar-kasus" aria-label="Daftar kasus" className="scroll-mt-4 overflow-hidden rounded border border-[#DFE1E6] bg-white">
        <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm"><thead><tr><th className="px-3 py-3">Siswa</th><th className="px-3 py-3">Indikasi</th><th className="px-3 py-3">Kejadian</th><th className="px-3 py-3">Total durasi</th><th className="px-3 py-3">Pertama – terakhir</th><th className="px-3 py-3">Status</th></tr></thead><tbody>{visible.map((r) => <tr key={r.case_id} data-case={r.case_id} onClick={() => setSelId(r.case_id)} className={`cursor-pointer border-t border-slate-100 ${cur?.case_id === r.case_id ? "bg-blue-50" : ""}`}><td className="px-3 py-3.5 font-semibold text-slate-800">{r.student?.name}<p className="mt-0.5 text-xs font-normal text-slate-400">{r.exam?.name}</p></td><td className="px-3 py-3.5 text-slate-600">{eventTitle(r)}{r.status === "open" ? " (berlangsung)" : ""}{r.rule && !r.rule.met && <p className="mt-0.5 text-[11px] text-slate-400">Di bawah ambang ({r.rule.max_in_window}/{r.rule.min_count}{r.rule.window_s ? ` dalam ${Math.round(r.rule.window_s / 60)} mnt` : ""})</p>}</td><td className="px-3 py-3.5 font-semibold text-slate-700">{r.episode_count ?? r.event_count}×</td><td className="whitespace-nowrap px-3 py-3.5 text-slate-500">{fmtDuration(r.total_duration_s)}</td><td className="whitespace-nowrap px-3 py-3.5 text-slate-500">{fmtTime(r.first_start_ts)}{r.event_count > 1 ? ` – ${fmtTime(r.last_start_ts)}` : ""}</td><td className="px-3 py-3.5"><Badge tone={caseTone(r)}>{caseLabel(r)}</Badge></td></tr>)}</tbody></table></div>
        {!list.loading && visible.length === 0 && <p className="p-8 text-center text-sm text-slate-500">Tidak ada indikasi pada filter ini.</p>}
      </section>
      {cur && <CasePanel key={cur.case_id} c={cur} readOnly={readOnly} go={go} onSaved={() => void list.reload()} />}
    </div>
  </main></AppShell>;
}

/** One grouped case: summary, every original event (with its own evidence link) and one review for the group. */
function CasePanel({ c, readOnly, go, onSaved }: { c: CaseSummary; readOnly: boolean; go: (s: Screen) => void; onSaved: () => void }) {
  const { setEventId, setExamId } = useSel();
  // Re-load the original events whenever the case changes (new event, closed event or new review).
  const detail = usePoll(() => api.caseDetail(c.case_id), [c.case_id, c.updated_at, c.event_count]);
  const events = detail.data?.events ?? [];
  const [choice, setChoice] = useState<Decision>("Valid");
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<{ n: number; decision: Decision } | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadedThumb, setThumb] = useState<{ id: string; url: string } | null>(null);
  const { role } = useRole();
  const allowed = mayOpenEvidence(role);
  const evidenceEvent = [...events].reverse().find((e) => e.evidence_id);
  const thumbId = evidenceEvent?.evidence_id ?? c.latest_evidence_id;
  const thumb = loadedThumb && loadedThumb.id === thumbId ? loadedThumb.url : null;
  // The key frame of the selected case is shown right away (request 6 Nov 2026). Every opening is still written to the
  // audit log by the backend ("Melihat evidence") and turns the notification ring grey. Each evidence is requested once
  // per panel (the ref also covers React StrictMode's double effect in development); "Coba lagi" after an error.
  const [thumbState, setThumbState] = useState<{ id: string; state: "loading" | "error" } | null>(null);
  const thumbBusy = thumbState && thumbState.id === thumbId ? thumbState.state : null;
  const asked = useRef(new Set<string>());
  useEffect(() => () => { if (loadedThumb) URL.revokeObjectURL(loadedThumb.url); }, [loadedThumb]);
  const fetchThumb = useCallback((id: string) => {
    asked.current.add(id);
    return api.evidence(id).then((m) => api.evidenceFrameUrl(m.evidence_id, m.key_index))
      .then((u) => { setThumb({ id, url: u }); setThumbState(null); })
      .catch(() => setThumbState({ id, state: "error" }));
  }, []);
  useEffect(() => { if (allowed && thumbId && !asked.current.has(thumbId)) void fetchThumb(thumbId); }, [allowed, thumbId, fetchThumb]);
  const loadThumb = () => { if (allowed && thumbId) { setThumbState({ id: thumbId, state: "loading" }); void fetchThumb(thumbId); } };
  const save = async () => {
    if (!events.length) return;
    setBusy(true);
    try {
      // Only the events shown here are sent; an event that arrived after loading stays unreviewed.
      const r = await api.reviewCase(c.case_id, choice, note, events.map((e) => e.event_id));
      detail.setData(r); setSaved({ n: r.reviewed_event_ids?.length ?? events.length, decision: choice }); setErr(""); onSaved();
    } catch (x) { setErr((x as Error).message); void detail.reload(); } finally { setBusy(false); }
  };
  const openEvent = (id: string) => { setExamId(c.exam_id); setEventId(id); go("detail"); };
  const partly = c.unreviewed_count > 0 && c.unreviewed_count < c.event_count;
  return <aside className="h-fit min-w-0 rounded-lg border border-slate-200 bg-white p-5">
    <div className="flex items-center justify-between gap-3"><h2 className="font-semibold text-slate-900">{c.student?.name}</h2><Badge tone={caseTone(c)}>{caseLabel(c)}</Badge></div>
    <p className="mt-1 text-sm text-slate-500">{eventTitle(c)} · {c.exam?.name}</p>
    <div className="relative mt-4 grid aspect-video place-items-center overflow-hidden rounded-md bg-slate-800 text-xs text-slate-300">{thumb ? <img src={thumb} alt="Cuplikan evidence" data-thumb className="absolute inset-0 size-full object-cover" draggable={false} onContextMenu={(e) => e.preventDefault()} />
      : allowed && thumbId ? <button type="button" onClick={loadThumb} disabled={thumbBusy !== "error"} data-case-thumb className="absolute inset-0 grid place-items-center bg-[#F4F5F7] text-[13px] font-medium text-[#14213d] outline-none hover:bg-[#EBECF0] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#c9a227]" aria-label={`Tampilkan cuplikan bukti ${c.student?.name ?? ""}`}>{thumbBusy === "error" ? "Gagal memuat cuplikan, coba lagi" : "Memuat cuplikan…"}</button>
      : <Silhouette />}<span className="pointer-events-none absolute bottom-2 left-2 rounded bg-slate-900/70 px-2 py-0.5">{!allowed ? EVIDENCE_RESTRICTED : evidenceEvent ? `Evidence ${fmtTime(evidenceEvent.start_ts)} (${c.evidence_count} dari ${c.event_count} kejadian punya evidence)` : "Evidence belum tersedia"}</span></div>
    <dl className="mt-4 space-y-2.5 text-sm">{[["Jumlah kejadian", `${c.event_count} kejadian`], ["Kejadian pertama", fmtTime(c.first_start_ts)], ["Kejadian terakhir", c.status === "open" ? `${fmtTime(c.last_start_ts)} (berlangsung)` : fmtTime(c.last_start_ts)], ["Total durasi", fmtDuration(c.total_duration_s)], ["Skor model tertinggi", c.max_score == null ? "—" : `${Math.round(c.max_score * 100)}%`]].map(([k, v]) => <div key={k} className="flex justify-between gap-3"><dt className="text-slate-500">{k}</dt><dd className="text-right font-semibold text-slate-800">{v}</dd></div>)}</dl>
    {partly && <div className="mt-4"><Notice tone="amber">{c.unreviewed_count} kejadian baru masuk setelah kasus ini ditinjau. Keputusan sebelumnya tidak otomatis berlaku untuk kejadian baru.</Notice></div>}
    <h3 className="mt-5 text-sm font-bold text-slate-900">Kejadian asli ({events.length || c.event_count})</h3>
    {detail.error && <Notice tone="red">{detail.error}</Notice>}
    <ol className="mt-2 max-h-72 divide-y divide-slate-100 overflow-y-auto rounded-md border border-slate-100">{events.map((e, i) => <li key={e.event_id} className="flex items-start gap-3 p-3 text-xs"><span className="mt-0.5 w-5 shrink-0 text-slate-400">{i + 1}.</span><div className="min-w-0 flex-1"><p className="font-semibold text-slate-800">{fmtTime(e.start_ts)} – {e.end_ts ? fmtTime(e.end_ts) : "berlangsung"} · {fmtDuration(e.duration_s)}</p><p className="mt-0.5 text-slate-500">{e.indicator} · skor {scoreText(e)} · {e.evidence_id ? "ada evidence" : "tanpa evidence"}</p>{e.reason && <p className="mt-0.5 truncate text-slate-400" title={e.reason}>{e.reason}</p>}</div><div className="flex shrink-0 flex-col items-end gap-1.5"><Badge tone={reviewTone(e.review_status)}>{reviewLabel(e.review_status)}</Badge><button onClick={() => openEvent(e.event_id)} className="font-bold text-blue-700">{readOnly ? "Lihat" : "Buka"}</button></div></li>)}{detail.loading && !events.length && <li className="p-3 text-xs text-slate-500">Memuat kejadian...</li>}</ol>
    {!readOnly && <div className="mt-5 border-t border-slate-100 pt-5"><h3 className="text-sm font-bold text-slate-900">Validasi kasus</h3><p className="mt-1 text-xs leading-5 text-slate-500">Keputusan berlaku untuk <b>semua {events.length} kejadian</b> di atas. Setiap kejadian tetap tersimpan dengan riwayat validasinya sendiri.</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">{(["Valid", "Tidak Valid", "Perlu Tinjauan Lanjut"] as Decision[]).map((l) => <button key={l} onClick={() => setChoice(l)} className={`rounded-md border p-2.5 text-left text-xs font-bold text-slate-800 ${choice === l ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100" : "border-slate-200 hover:bg-slate-50"}`}>{l}</button>)}</div>
      <textarea value={note} onChange={(x) => setNote(x.target.value)} rows={3} className="mt-3 w-full resize-none rounded-md border border-slate-200 p-3 text-sm outline-none focus:border-blue-500" placeholder="Catatan validasi untuk kasus ini..." />
      {err && <Notice tone="red">{err}</Notice>}
      <Button className="mt-3 w-full" disabled={busy || !events.length} onClick={() => void save()}>{`Simpan validasi untuk ${events.length} kejadian`}</Button>
      {saved && <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs font-semibold text-emerald-900">Validasi kasus disimpan ({saved.decision}) untuk {saved.n} kejadian.</p>}
    </div>}
    <p className="mt-3 text-xs leading-5 text-slate-500">AI hanya memberi indikasi, bukan bukti kecurangan. Keputusan akhir ada pada pengawas.</p>
  </aside>;
}

function HistoryPage({ go }: { go: (s: Screen) => void }) {
  const { user } = useUser();
  const { role } = useRole();
  const { setExamId } = useSel();
  const data = usePoll(async () => {
    const finished = (await api.exams()).filter((e) => e.status === "Selesai");
    return Promise.all(finished.map((e) => api.report(e.id)));
  }, []);
  return <AppShell active="history" go={go} title="Riwayat Sesi"><main className="p-4 sm:p-8"><PageTitle title="Riwayat Sesi" description={`Sesi selesai yang pernah ditugaskan kepada ${user?.name ?? ""}.`} />{data.error && <Notice tone="red">{data.error}</Notice>}
    {!chartsOnDashboard(role) && <div className="mb-6"><Suspense fallback={<ChartSkeleton h={260} />}><HistoryChart data={data.data ? historyRows(data.data) : null} onOpen={(id) => { setExamId(id); go("report"); }} /></Suspense></div>}
    <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr>{["Nama Ujian", "Tanggal", "Peserta", "Indikasi", "Valid", "Tidak Valid", "Perlu Tinjauan", "Status Tinjauan", "Aksi"].map((head) => <th key={head} className="px-5 py-3.5">{head}</th>)}</tr></thead><tbody>{(data.data ?? []).map((r) => <tr key={r.exam.id} className="border-t border-slate-100">{[r.exam.name, fmtDate(r.exam.date), r.attendance.enrolled, r.indications.total, r.indications.valid, r.indications.invalid, r.indications.further].map((cell, index) => <td key={index} className={`px-5 py-4 ${index === 0 ? "font-semibold text-slate-800" : "text-slate-600"}`}>{cell}</td>)}<td className="px-5 py-4"><Badge tone={r.indications.unreviewed === 0 ? "green" : "amber"}>{r.indications.unreviewed === 0 ? "Semua ditinjau" : "Perlu Tinjauan"}</Badge></td><td className="px-5 py-4"><button onClick={() => { setExamId(r.exam.id); go("report"); }} className="text-xs font-bold text-blue-700">Lihat Detail</button></td></tr>)}</tbody></table>{!data.loading && !(data.data ?? []).length && <p className="p-6 text-center text-sm text-slate-500">Belum ada sesi yang selesai.</p>}</div></section></main></AppShell>;
}

function UserManagement({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [saved, setSaved] = useState("");
  const admin = role === "Admin";
  const school = role === "Pihak Sekolah";                 // "Akun Siswa": student accounts only
  const canEdit = admin || school;
  const list = usePoll(() => api.users(admin ? undefined : school ? "siswa" : "pengawas"), [admin, school]);
  const exams = usePoll(() => api.exams(), []);
  const [q, setQ] = useState("");
  const rows: UserRow[] = (list.data ?? []).filter((u) => u.name.toLowerCase().includes(q.toLowerCase()) || u.email.includes(q.toLowerCase()));
  const sessionsOf = (id: number) => (exams.data ?? []).filter((e) => e.supervisor?.id === id && e.status !== "Selesai").length;
  const pageTitle = admin ? "Manajemen User" : school ? "Akun Siswa" : "Pengawas Ujian";
  return <AppShell active="users" go={go} title={admin ? "Manajemen User" : school ? "Akun Siswa" : "Daftar Pengawas"}><main className="p-4 sm:p-8"><PageTitle title={pageTitle} description={admin ? "Kelola akun, status, dan role pengguna EduAI." : school ? "Kelola data akun siswa: nama, email, NIS, kelas, dan status akun." : "Tentukan pengawas untuk sesi yang menjadi kewenangan Anda."} action={school ? undefined : <Button icon="plus" onClick={() => setModal(true)}>{admin ? "Tambah User" : "Tambah Pengawas"}</Button>} />
    {list.error && <Notice tone="red">{list.error}</Notice>}
    {saved && <p role="status" className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{saved}</p>}
    <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex gap-3 border-b border-slate-100 p-4"><div className="relative max-w-sm flex-1"><span className="absolute left-3 top-2.5 text-slate-400"><Icon name="search" size={17} /></span><input value={q} onChange={(e) => setQ(e.target.value)} className="h-10 w-full rounded-md border border-slate-200 pl-9 pr-3 text-sm" placeholder="Cari nama atau email" /></div></div><div className="overflow-x-auto"><table className="w-full min-w-[880px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr>{(admin ? ["Nama", "Email", "Role", "Status", "Tanggal dibuat", "Aksi"] : school ? ["Nama", "Email", "NIS/NISN", "Kelas", "Status", "Aksi"] : ["Nama", "Email", "Penugasan", "Status", "Kelas"]).map((head) => <th key={head} className="px-5 py-3.5">{head}</th>)}</tr></thead><tbody>{rows.map((u) => { const status = u.active ? "Aktif" : "Nonaktif"; const cells = admin ? [u.name, u.email, u.role_label, status, fmtDate(u.created_at)] : school ? [u.name, u.email, u.nis || "—", u.class_name || "—", status] : [u.name, u.email, `${sessionsOf(u.id)} sesi aktif`, status, "—"]; const statusAt = school ? 4 : 3; return <tr key={u.id} data-user={u.email} className="border-t border-slate-100">{cells.map((cell, index) => <td key={index} className={`px-5 py-4 ${index === 0 ? "font-semibold text-slate-800" : "text-slate-600"}`}>{index === statusAt ? <Badge tone={cell === "Aktif" ? "green" : "gray"}>{cell}</Badge> : cell}</td>)}
        {canEdit && <td className="px-5 py-4"><button type="button" onClick={() => { setSaved(""); setEditing(u); }} aria-label={`Ubah ${u.name}`} className="tap relative inline-flex items-center gap-1.5 text-xs font-semibold text-[#836713] underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-[#c9a227]"><Icon name="edit" size={14} />Ubah</button></td>}</tr>; })}</tbody></table></div></section>
    {editing && <EditUserDialog u={editing} studentOnly={school} onClose={() => setEditing(null)} onSaved={(u) => { setEditing(null); setSaved(`Data ${u.name} tersimpan.`); void list.reload(); }} />}
    {modal && admin && <AddUserDialog onClose={() => setModal(false)} onSaved={(u) => { setModal(false); setSaved(`Akun ${u.name} (${u.role_label}) ditambahkan.`); void list.reload(); }} />}
    {modal && !admin && <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-900/40 p-4"><section role="dialog" aria-modal="true" className="max-h-[90dvh] w-full max-w-lg overflow-y-auto rounded-md border border-slate-200 bg-white p-6"><div className="flex items-center justify-between"><h2 className="text-lg font-bold text-slate-900">{admin ? "Tambah User" : "Tambah Pengawas"}<SampleTag /></h2><button onClick={() => setModal(false)} aria-label="Tutup" className="tap relative text-slate-400"><Icon name="close" /></button></div><p className="mt-3 text-sm text-slate-500">Pembuatan akun staf melalui antarmuka belum tersedia di backend. Untuk uji coba gunakan akun demo atau tambahkan akun lewat basis data.</p><div className="mt-6 space-y-4"><Field label="Nama lengkap" placeholder="Masukkan nama lengkap" /><Field label="Email institusi" placeholder="nama@sman8bdg.sch.id" type="email" /></div><div className="mt-6 flex justify-end gap-3"><Button variant="secondary" onClick={() => setModal(false)}>Tutup</Button><Button disabled>Simpan</Button></div></section></div>}
  </main></AppShell>;
}

const ROLE_OPTIONS: [RoleCode, string][] = [["siswa", "Siswa"], ["pengawas", "Pengawas"], ["penyelenggara", "Penyelenggara Ujian"], ["admin", "Admin"], ["sekolah", "Pihak Sekolah"]];

/** Manajemen User > Ubah: name, email, role, status (and NIS/class for students). The backend checks everything
 *  again (unique email, own role/status, last admin, accounts still linked to unfinished exams). */
function EditUserDialog({ u, studentOnly = false, onClose, onSaved }: { u: UserRow; studentOnly?: boolean; onClose: () => void; onSaved: (u: UserRow) => void }) {
  const { user, setUser } = useUser();
  const self = user?.id === u.id;
  const ref = useRef<HTMLElement>(null);
  useFocusTrap(ref, true, onClose);
  const [f, setF] = useState({ name: u.name, email: u.email, role: u.role, active: u.active, nis: u.nis ?? "", class_name: u.class_name ?? "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k: keyof typeof f, v: string | boolean) => { setF((x) => ({ ...x, [k]: v })); setErr(""); };
  const name = f.name.trim().replace(/\s+/g, " "), email = f.email.trim().toLowerCase();
  const nameErr = name.length < 2 ? "Nama lengkap minimal 2 karakter." : "";
  const emailErr = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) ? "" : "Format email tidak valid.";
  const body: Parameters<typeof api.updateUser>[1] = {};
  if (name !== u.name) body.name = name;
  if (email !== u.email) body.email = email;
  if (f.role !== u.role) body.role = f.role;
  if (f.active !== u.active) body.active = f.active;
  if (f.role === "siswa" && (f.nis.trim() || null) !== (u.nis ?? null)) body.nis = f.nis.trim() || null;
  if (f.role === "siswa" && (f.class_name.trim() || null) !== (u.class_name ?? null)) body.class_name = f.class_name.trim() || null;
  const changed = Object.keys(body).length > 0;
  const save = async () => {
    if (!changed || nameErr || emailErr) return;
    setBusy(true);
    try {
      const r = await api.updateUser(u.id, body);
      if (self && user) { const me = { ...user, name: r.name, email: r.email }; setUser(me); const t = session.token(); if (t) session.set(t, me); }
      onSaved(r);
    } catch (e) { setErr((e as Error).message || "Perubahan tidak tersimpan."); } finally { setBusy(false); }
  };
  const input = "h-11 w-full rounded-md border border-slate-200 bg-white px-3.5 text-sm text-slate-800 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500";
  const lab = (text: string, control: ReactNode, hint?: string, error?: string) => <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">{text}</span>{control}
    {(error || hint) && <span className={`mt-1 block text-xs ${error ? "text-red-600" : "text-slate-500"}`}>{error || hint}</span>}</label>;
  return <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-900/40 p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <section ref={ref} role="dialog" aria-modal="true" aria-labelledby="edit-user-title" className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-md border border-slate-200 bg-white p-6">
      <div className="flex items-center justify-between"><h2 id="edit-user-title" className="text-lg font-bold text-slate-900">Ubah pengguna</h2>
        <button type="button" onClick={onClose} aria-label="Tutup" className="tap relative text-slate-400 hover:text-slate-600"><Icon name="close" /></button></div>
      <form id="form-user" onSubmit={(e) => { e.preventDefault(); void save(); }} className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">{lab("Nama lengkap", <input name="name" value={f.name} maxLength={120} onChange={(e) => set("name", e.target.value)} className={input} />, undefined, nameErr)}</div>
        <div className="sm:col-span-2">{lab("Email", <input name="email" type="email" value={f.email} maxLength={200} onChange={(e) => set("email", e.target.value)} className={input} />, "Dipakai untuk masuk. Beri tahu pengguna bila diganti.", emailErr)}</div>
        {studentOnly ? lab("Peran", <input readOnly value="Siswa" className={`${input} cursor-not-allowed bg-slate-50 text-slate-500`} />, "Peran diatur oleh admin.") : lab("Peran", <select name="role" value={f.role} disabled={self} onChange={(e) => set("role", e.target.value)} className={input}>{ROLE_OPTIONS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>,
          self ? "Anda tidak dapat mengubah peran sendiri." : undefined)}
        {lab("Status", <select name="active" value={f.active ? "1" : "0"} disabled={self} onChange={(e) => set("active", e.target.value === "1")} className={input}><option value="1">Aktif</option><option value="0">Nonaktif</option></select>,
          self ? "Anda tidak dapat menonaktifkan akun sendiri." : !f.active ? "Akun nonaktif tidak bisa masuk; sesi yang sedang berjalan langsung berakhir." : undefined)}
        {f.role === "siswa" && <>{lab("NIS/NISN", <input name="nis" value={f.nis} maxLength={40} onChange={(e) => set("nis", e.target.value)} className={input} />)}
          {lab("Kelas", <input name="class_name" value={f.class_name} maxLength={60} onChange={(e) => set("class_name", e.target.value)} className={input} />)}</>}
      </form>
      {err && <p role="alert" className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p>}
      <div className="mt-6 flex justify-end gap-3"><Button variant="secondary" onClick={onClose}>Batal</Button>
        <Button onClick={() => void save()} disabled={!changed || !!nameErr || !!emailErr || busy}>{busy ? "Menyimpan…" : "Simpan"}</Button></div>
    </section>
  </div>;
}

const ROLE_INFO: Record<RoleCode, { about: string; email: string }> = {
  siswa: { about: "Mengikuti ujian. Wajib NIS/NISN dan kelas.", email: "siswa7@sekolah.sch.id" },
  pengawas: { about: "Mengawasi sesi ujian yang ditugaskan dan meninjau indikasi.", email: "nama.guru@sekolah.sch.id" },
  penyelenggara: { about: "Mengatur sesi ujian, peserta, dan pengawas.", email: "kurikulum@sekolah.sch.id" },
  admin: { about: "Akses penuh: pengguna, konfigurasi, retensi data, dan log audit.", email: "admin@sekolah.sch.id" },
  sekolah: { about: "Melihat indikasi tervalidasi dan laporan final, serta mengelola data akun siswa.", email: "tu@sekolah.sch.id" },
};

/** Manajemen User > Tambah User (admin). The form follows the role: students need NIS/NISN and class; an admin
 *  account asks for an explicit confirmation. The backend checks everything again (POST /api/users). */
function AddUserDialog({ onClose, onSaved }: { onClose: () => void; onSaved: (u: UserRow) => void }) {
  const ref = useRef<HTMLElement>(null);
  useFocusTrap(ref, true, onClose);
  const [f, setF] = useState({ role: "siswa" as RoleCode, name: "", email: "", password: "", nis: "", class_name: "" });
  const [show, setShow] = useState(false);
  const [adminOk, setAdminOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [touched, setTouched] = useState(false);
  const set = (k: keyof typeof f, v: string) => { setF((x) => ({ ...x, [k]: v })); setErr(""); };
  const student = f.role === "siswa";
  const name = f.name.trim().replace(/\s+/g, " "), email = f.email.trim().toLowerCase();
  const errors = {
    name: name.length < 2 ? "Nama lengkap minimal 2 karakter." : "",
    email: /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) ? "" : "Format email tidak valid.",
    password: f.password.length < 8 ? "Kata sandi awal minimal 8 karakter." : "",
    nis: student && !f.nis.trim() ? "NIS/NISN wajib untuk siswa." : "",
    class_name: student && !f.class_name.trim() ? "Kelas wajib untuk siswa." : "",
  };
  const invalid = Object.values(errors).some(Boolean) || (f.role === "admin" && !adminOk);
  const shown = (k: keyof typeof errors) => (touched ? errors[k] : "");
  const generate = () => {
    const abc = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
    const bytes = crypto.getRandomValues(new Uint8Array(12));
    set("password", Array.from(bytes, (b) => abc[b % abc.length]).join("")); setShow(true);
  };
  const save = async () => {
    setTouched(true);
    if (invalid) return;
    setBusy(true);
    try {
      onSaved(await api.createUser({ name, email, role: f.role, password: f.password, ...(student ? { nis: f.nis.trim(), class_name: f.class_name.trim() } : {}) }));
    } catch (e) { setErr((e as Error).message || "Akun tidak tersimpan."); } finally { setBusy(false); }
  };
  const input = "h-11 w-full rounded-md border border-slate-200 bg-white px-3.5 text-sm text-slate-800 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-50";
  const lab = (text: string, control: ReactNode, hint?: string, error?: string) => <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">{text}</span>{control}
    {(error || hint) && <span className={`mt-1 block text-xs ${error ? "text-red-600" : "text-slate-500"}`}>{error || hint}</span>}</label>;
  return <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-900/40 p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <section ref={ref} role="dialog" aria-modal="true" aria-labelledby="add-user-title" className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-md border border-slate-200 bg-white p-6">
      <div className="flex items-center justify-between"><h2 id="add-user-title" className="text-lg font-bold text-slate-900">Tambah User</h2>
        <button type="button" onClick={onClose} aria-label="Tutup" className="tap relative text-slate-400 hover:text-slate-600"><Icon name="close" /></button></div>
      <form id="form-add-user" onSubmit={(e) => { e.preventDefault(); void save(); }} className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">{lab("Peran", <select name="role" value={f.role} onChange={(e) => { set("role", e.target.value); setAdminOk(false); }} className={input}>{ROLE_OPTIONS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>,
          ROLE_INFO[f.role].about)}</div>
        <div className="sm:col-span-2">{lab("Nama lengkap", <input name="name" value={f.name} maxLength={120} onChange={(e) => set("name", e.target.value)} placeholder="Masukkan nama lengkap" className={input} />, undefined, shown("name"))}</div>
        <div className="sm:col-span-2">{lab(student ? "Email siswa" : "Email institusi", <input name="email" type="email" value={f.email} maxLength={200} onChange={(e) => set("email", e.target.value)} placeholder={ROLE_INFO[f.role].email} className={input} />,
          "Dipakai untuk masuk.", shown("email"))}</div>
        {student && <>{lab("NIS/NISN", <input name="nis" value={f.nis} maxLength={40} onChange={(e) => set("nis", e.target.value)} placeholder="2301040" className={input} />, undefined, shown("nis"))}
          {lab("Kelas", <input name="class_name" value={f.class_name} maxLength={60} onChange={(e) => set("class_name", e.target.value)} placeholder="XI IPA 2" className={input} />, undefined, shown("class_name"))}</>}
        <div className="sm:col-span-2">{lab("Kata sandi awal", <div className="flex gap-2"><input name="password" type={show ? "text" : "password"} value={f.password} maxLength={200} autoComplete="new-password" onChange={(e) => set("password", e.target.value)} className={input} />
          <button type="button" onClick={() => setShow((v) => !v)} className="h-11 shrink-0 rounded-md border border-slate-200 px-3 text-xs font-semibold text-slate-600 hover:bg-slate-50">{show ? "Sembunyikan" : "Tampilkan"}</button>
          <button type="button" onClick={generate} className="h-11 shrink-0 rounded-md border border-slate-200 px-3 text-xs font-semibold text-slate-600 hover:bg-slate-50">Buat acak</button></div>,
          "Minimal 8 karakter. Berikan langsung kepada pengguna; tidak dikirim lewat email dan tidak dicatat di log.", shown("password"))}</div>
        {f.role === "admin" && <label className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 sm:col-span-2">
          <input type="checkbox" name="admin-ok" checked={adminOk} onChange={(e) => setAdminOk(e.target.checked)} className="mt-0.5" />
          <span>Saya paham akun admin mendapat akses penuh, termasuk mengubah pengguna dan konfigurasi.</span></label>}
      </form>
      {err && <p role="alert" className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p>}
      <div className="mt-6 flex justify-end gap-3"><Button variant="secondary" onClick={onClose}>Batal</Button>
        <Button onClick={() => void save()} disabled={busy || (touched && invalid) || (f.role === "admin" && !adminOk)}>{busy ? "Menyimpan…" : "Tambah"}</Button></div>
    </section>
  </div>;
}

function ConfigurationPage({ go }: { go: (s: Screen) => void }) {
  const [tab, setTab] = useState("Sistem");
  const h = usePoll<[Health, AIHealth]>(() => Promise.all([api.health(), api.aiHealth()]), []);
  const ai = h.data?.[1];
  const rows: [string, string][] = [["Pemantauan AI", ai ? (ai.available ? `Siap • konfigurasi ${ai.config_version}` : `Belum siap • ${ai.reason}`) : "—"], ["Sumber frame analisis", h.data?.[0].analysis_source === "livekit" ? "Worker OpenVidu" : "Frame dari browser siswa"], ["Analisis paralel maksimum", ai ? `${ai.max_concurrent} frame` : "—"], ["Pencatatan audit", "Selalu aktif"]];
  return <AppShell active="configuration" go={go} title="Konfigurasi Sistem"><main className="p-4 sm:p-8"><PageTitle title="Konfigurasi Sistem" description="Nilai berikut dibaca dari backend. Perubahan dilakukan lewat file backend/.env dan ai/eduai-ai/config.yaml." /><div className="grid gap-6 lg:grid-cols-[240px_1fr]"><aside className="h-fit rounded-md border border-slate-200 bg-white p-2">{["Sistem"].map((item) => <button key={item} onClick={() => setTab(item)} className={`w-full rounded-md px-3 py-2.5 text-left text-sm font-semibold ${tab === item ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50"}`}>{item}</button>)}</aside><section className="rounded-md border border-slate-200 bg-white p-6"><h2 className="font-bold text-slate-900">Konfigurasi {tab.toLowerCase()}</h2><p className="mt-1 text-sm text-slate-500">Hanya-baca dari antarmuka.</p>{h.error && <Notice tone="red">{h.error}</Notice>}<div className="mt-6 space-y-4">{rows.map(([label, value]) => <div key={label} className="flex items-center justify-between rounded-md border border-slate-200 p-4"><div><p className="text-sm font-semibold text-slate-800">{label}</p><p className="mt-1 text-xs text-slate-500">{value}</p></div></div>)}{ai && Object.entries(ai.models).map(([k, v]) => <div key={k} className="flex items-center justify-between rounded-md border border-slate-200 p-4"><div><p className="text-sm font-semibold text-slate-800">Model {k}</p><p className="mt-1 text-xs text-slate-500">{v.file} • {v.loaded ? "dimuat" : v.reason || "tidak dimuat"}</p></div><Badge tone={v.loaded ? "green" : "gray"}>{v.loaded ? "Aktif" : "Tidak aktif"}</Badge></div>)}</div></section></div></main></AppShell>;
}

function RetentionPage({ go }: { go: (s: Screen) => void }) {
  const ai = usePoll(() => api.aiHealth(), []);
  const audit = usePoll(() => api.audit(), []);
  const purges = (audit.data ?? []).filter((a) => a.action.toLowerCase().includes("menghapus"));
  return <AppShell active="retention" go={go} title="Retensi Data"><main className="p-4 sm:p-8"><PageTitle eyebrow="FR-WEB-22" title="Retensi & Penghapusan Data" description="Masa simpan diatur di backend/.env (EDUAI_EVIDENCE_RETENTION_HOURS) dan ditampilkan di sini." />
    <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Data</th><th className="px-5 py-3.5">Masa simpan</th><th className="px-5 py-3.5">Status</th></tr></thead><tbody>{[["Video rekaman penuh", "Tidak disimpan oleh EduAI", "green"], ["Evidence (cuplikan gambar)", ai.data ? `${ai.data.evidence_retention_hours} jam${ai.data.evidence_encrypted ? " • terenkripsi" : ""}; ditahan sampai laporan final, maksimal ${ai.data.evidence_hold_days} hari sejak sesi selesai` : "—", "green"], ["Gambar bukti laporan final", ai.data ? `${ai.data.report_frame_retention_hours} jam sejak laporan difinalisasi` : "—", "green"], ["Data indikasi & validasi (teks)", "Disimpan untuk laporan; kebijakan sekolah belum dikonfigurasi", "amber"]].map(([data, days, tone]) => <tr key={data} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{data}</td><td className="px-5 py-4 text-slate-600">{days}</td><td className="px-5 py-4"><Badge tone={tone as "green" | "amber"}>{tone === "green" ? "Aktif" : "Perlu kebijakan"}</Badge></td></tr>)}</tbody></table></div><div className="border-t border-blue-100 bg-blue-50 p-4 text-sm text-blue-800">Evidence dan gambar bukti laporan yang melewati masa simpan dihapus otomatis (diperiksa setiap 10 menit) dan dicatat dalam Audit Log. Setelah itu laporan menampilkan keterangan "gambar bukti sudah dihapus sesuai kebijakan retensi". Masa simpan diatur lewat EDUAI_EVIDENCE_RETENTION_HOURS, EDUAI_EVIDENCE_HOLD_DAYS, dan EDUAI_REPORT_FRAME_RETENTION_HOURS.</div></section>
    <section className="mt-6 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="border-b border-slate-100 p-5"><h2 className="font-bold text-slate-900">Riwayat penghapusan</h2><p className="mt-1 text-xs text-slate-500">Catatan ini tidak dapat diubah melalui aplikasi.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Aktivitas</th><th className="px-5 py-3.5">Data</th><th className="px-5 py-3.5">Waktu</th><th className="px-5 py-3.5">Dijalankan oleh</th></tr></thead><tbody>{purges.map((row) => <tr key={row.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{row.action}</td><td className="px-5 py-4 text-slate-600">{row.target}</td><td className="px-5 py-4 text-slate-600">{fmtDateTime(row.ts)}</td><td className="px-5 py-4 text-slate-600">{row.user_name}</td></tr>)}</tbody></table>{purges.length === 0 && <p className="p-6 text-center text-sm text-slate-500">Belum ada penghapusan otomatis.</p>}</div></section>
  </main></AppShell>;
}

function AuditPage({ go }: { go: (s: Screen) => void }) {
  const list = usePoll(() => api.audit(), [], 15000);
  const [q, setQ] = useState("");
  const [roleF, setRoleF] = useState("Semua role");
  const rows: AuditRow[] = (list.data ?? []).filter((r) => (r.user_name + r.action + r.target).toLowerCase().includes(q.toLowerCase()) && (roleF === "Semua role" || r.role === roleF));
  return <AppShell active="audit" go={go} title="Audit Log"><main className="p-4 sm:p-8"><PageTitle title="Audit Log" description="Jejak aktivitas sistem bersifat hanya-baca dan tidak dapat dihapus melalui aplikasi." />{list.error && <Notice tone="red">{list.error}</Notice>}<section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="grid gap-3 border-b border-slate-100 p-4 md:grid-cols-4"><div className="relative md:col-span-2"><span className="absolute left-3 top-2.5 text-slate-400"><Icon name="search" size={17} /></span><input value={q} onChange={(e) => setQ(e.target.value)} className="h-10 w-full rounded-md border border-slate-200 pl-9 pr-3 text-sm" placeholder="Cari user atau aktivitas" /></div><select value={roleF} onChange={(e) => setRoleF(e.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"><option>Semua role</option>{["siswa", "pengawas", "penyelenggara", "admin", "sekolah", "sistem"].map((r) => <option key={r} value={r}>{r}</option>)}</select></div><div className="overflow-x-auto"><table className="w-full min-w-[1060px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr>{["User", "Role", "Waktu", "Aktivitas", "Data yang diakses", "Status"].map((head) => <th key={head} className="px-5 py-3.5">{head}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-t border-slate-100">{[row.user_name, row.role, fmtDateTime(row.ts), row.action, row.target, row.status].map((cell, index) => <td key={index} className={`px-5 py-4 ${index === 0 ? "font-semibold text-slate-800" : "text-slate-600"}`}>{index === 5 ? <Badge tone="green">{cell}</Badge> : cell}</td>)}</tr>)}</tbody></table></div></section></main></AppShell>;
}

function JitsiVideo({ track, mirror = false, className = "" }: { track: JitsiTrack | undefined; mirror?: boolean; className?: string }) {
  const ref = useJitsiTrack<HTMLVideoElement>(track);
  // Stay mounted while muted: the track is attached once per element, so remounting would leave it blank.
  return <video ref={ref} muted playsInline autoPlay className={`absolute inset-0 size-full object-cover ${className} ${mirror ? "-scale-x-100" : ""} ${!track || track.isMuted() ? "invisible" : ""}`} />;
}

function JitsiAudio({ track }: { track: JitsiTrack }) {
  const ref = useJitsiTrack<HTMLAudioElement>(track);
  return <audio ref={ref} autoPlay />;
}

function MeetingTile({ name, tracks, local = false }: { name: string; tracks: JitsiTrack[]; local?: boolean }) {
  const video = tracks.find((t) => t.getType() === "video");
  const audio = tracks.find((t) => t.getType() === "audio");
  return <div className="relative aspect-video overflow-hidden rounded-md bg-slate-800">
    <Silhouette />
    <JitsiVideo track={video} mirror={local} />
    {!local && audio && <JitsiAudio track={audio} />}
    <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/70 to-transparent px-3 py-2 text-xs font-semibold text-white"><span className="truncate">{name}{local && " (Anda)"}</span>{(!audio || audio.isMuted()) && <span className="rounded bg-red-500/80 px-1.5 py-0.5">Mik mati</span>}</div>
  </div>;
}

function MeetingPage({ go }: { go: (s: Screen) => void }) {
  const { user } = useUser();
  const [input, setInput] = useState("eduai-ruang-rapat");
  const [room, setRoom] = useState<string | null>(null);
  const server = usePoll(() => api.jitsiConfig(), []);
  const health = usePoll(() => api.jitsiHealth(), []);
  const { role } = useRole();
  const [token, setToken] = useState<{ room: string; token: string | null } | null>(null);
  const [joinError, setJoinError] = useState("");
  const jitsi = useJitsiRoom(token ? token.room : null, user?.name ?? "Pengguna EduAI", server.data, { token: token?.token ?? null });
  const { status, error, localTracks, participants, toggle } = jitsi;
  const muted = (type: "audio" | "video") => localTracks.find((t) => t.getType() === type)?.isMuted() ?? true;
  const join = async (e: FormEvent) => {
    e.preventDefault();
    const r = jitsiRoomName(input);
    if (!r) return;
    setJoinError("");
    try { setToken(await api.jitsiMeetingToken(r)); setRoom(r); } catch (x) { setJoinError((x as Error).message); }
  };
  const leave = () => { setRoom(null); setToken(null); };
  const h = health.data;
  const unavailable = !h ? null : h.state === "ready" ? null
    : role === "Admin" ? <Notice tone={h.state === "unreachable" ? "red" : "amber"}><p className="font-semibold">{h.state === "unreachable" ? "Server Jitsi tidak terjangkau." : "Server Jitsi belum diisi."}</p>
        {h.detail && <p className="mt-1 font-mono text-xs">{h.detail}</p>}
        {!!h.missing?.length && <><p className="mt-2">Isi di backend/.env lalu mulai ulang backend:</p><ul className="mt-1 font-mono text-xs">{h.missing.map((k) => <li key={k}>{k}={h.examples?.[k] ?? ""}</li>)}</ul></>}
        <p className="mt-2 text-xs">Server pengembangan: lihat dev/jitsi/README.md.</p></Notice>
    : <Notice>Rapat Video belum tersedia. Hubungi admin.</Notice>;
  return <AppShell active="meeting" go={go} title="Rapat Video"><main className="mx-auto max-w-7xl p-4 sm:p-8">
    <PageTitle eyebrow="Jitsi Meet" title="Rapat Video" description={`Konferensi video lewat lib-jitsi-meet${role === "Admin" && server.data?.domain ? ` di server ${server.data.domain}` : ""}. Terpisah dari pemantauan ujian; tidak dianalisis AI dan tidak direkam.`} />
    {server.error || health.error ? <Notice tone="red">{role === "Admin" ? `Pengaturan Jitsi tidak dapat dimuat: ${server.error || health.error}` : "Rapat Video belum tersedia. Hubungi admin."}</Notice>
      : !server.data || !h ? <p role="status" className="text-sm text-slate-500">Memeriksa server Jitsi...</p>
      : unavailable ? unavailable
      : !room ? <form onSubmit={(e) => void join(e)} className="max-w-lg rounded-md border border-slate-200 bg-white p-6">
      <label className="block text-sm font-semibold text-slate-700" htmlFor="jitsi-room">Nama ruang</label>
      <input id="jitsi-room" value={input} onChange={(e) => setInput(e.target.value)} className="mt-2 h-11 w-full rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
      <p className="mt-2 text-xs text-slate-500">Nama ruang: <span className="font-mono">{jitsiRoomName(input) || "—"}</span>. Siapa pun yang mengetahui nama ini dapat bergabung.</p>
      {joinError && <div className="mt-3"><Notice tone="red">{joinError}</Notice></div>}
      <Button type="submit" icon="video" className="mt-5" disabled={!jitsiRoomName(input)}>Gabung</Button>
    </form> : <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-4 py-3">
        <div><p className="text-sm font-semibold text-slate-900">{room}</p><p className="text-xs text-slate-500">{status === "joined" ? `Terhubung · ${participants.length + 1} peserta` : status === "connecting" ? "Menghubungkan..." : "Tidak terhubung"}</p></div>
        <div className="flex gap-2">
          <Button variant="secondary" icon="mic" disabled={!localTracks.some((t) => t.getType() === "audio")} onClick={() => void toggle("audio")}>{muted("audio") ? "Nyalakan mik" : "Matikan mik"}</Button>
          <Button variant="secondary" icon="camera" disabled={!localTracks.some((t) => t.getType() === "video")} onClick={() => void toggle("video")}>{muted("video") ? "Nyalakan kamera" : "Matikan kamera"}</Button>
          <Button onClick={leave}>Keluar rapat</Button>
        </div>
      </div>
      {error && <div className="mb-4"><Notice tone={status === "error" ? "red" : "amber"}>{error}</Notice></div>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MeetingTile name={user?.name ?? "Anda"} tracks={localTracks} local />
        {participants.map((p) => <MeetingTile key={p.id} name={p.name} tracks={p.tracks} />)}
      </div>
    </>}
  </main></AppShell>;
}

function AccessDenied({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  return <div className="grid min-h-screen place-items-center bg-slate-50 p-6"><section className="w-full max-w-lg rounded-md border border-slate-200 bg-white p-10 text-center"><div className="mx-auto grid size-14 place-items-center rounded-md bg-amber-50 text-amber-700"><Icon name="shield" size={27} /></div><p className="mt-6 text-xs font-bold uppercase tracking-widest text-amber-700">403 – Akses Ditolak</p><h1 className="mt-2 text-2xl font-bold text-slate-900">{role === "Pengawas" ? "Anda tidak memiliki akses ke sesi ujian ini." : "Anda tidak memiliki izin untuk mengakses halaman ini."}</h1><p className="mt-3 text-sm leading-6 text-slate-500">{role === "Pengawas" ? "Pengawas hanya dapat membuka sesi ujian yang ditugaskan kepadanya." : `Akun dengan role ${role} tidak memiliki kewenangan untuk melihat data atau menjalankan aksi pada halaman tersebut.`}</p><Button className="mt-7" onClick={() => go("dashboard")}>Kembali ke Dasbor</Button></section></div>;
}

/** Polls grouped cases for staff and raises ONE pop-up per case (one student + one behaviour for the
 *  whole exam), when its configured rule is first met. Further occurrences update the count in the
 *  bell list and Indikasi page without another pop-up; see ./notify.ts.
 *  Monitoring roles also get one pop-up per consolidated exam summary (made by the backend). */
function useIndicationNotifications(user: User | null): Notify {
  const [items, setItems] = useState<CaseSummary[]>([]);
  const [unread, setUnread] = useState(0);
  const [toast, setToast] = useState<CaseSummary | null>(null);
  const [summaries, setSummaries] = useState<ExamSummary[]>([]);
  const [summaryToast, setSummaryToast] = useState<ExamSummary | null>(null);
  const [summaryExam, setSummaryExam] = useState<number | null>(null);
  const [notifiedUser, setNotifiedUser] = useState(user);
  if (user !== notifiedUser) {           // never show one account's notifications to the next
    setNotifiedUser(user);
    setSummaries([]); setSummaryToast(null); setItems([]); setUnread(0); setToast(null);
  }
  useEffect(() => {
    if (!user || !["pengawas", "penyelenggara", "admin"].includes(user.role)) return;
    let store: Storage | null = null;
    try { store = window.localStorage; } catch { store = null; }
    const key = seenSummariesKey(user.id);
    let seen = loadSeen(store, key);
    let stop = false;
    const tick = async () => {
      try {
        const r = await api.summaries();
        if (stop) return;
        const res = newSummaryKeys(seen, r.summaries, Date.now());
        seen = res.seen; saveSeen(store, key, seen);
        setSummaries(r.summaries);
        if (res.fresh.length) {
          setUnread((u) => u + res.fresh.length);
          setSummaryToast(r.summaries.find((s) => `s-${s.exam_id}` === res.fresh[0]) ?? null);
        }
      } catch { /* keep the last list */ }
    };
    void tick();
    const t = window.setInterval(() => void tick(), 15000);
    return () => { stop = true; window.clearInterval(t); };
  }, [user]);
  useEffect(() => {
    if (!user || user.role === "siswa") return;
    let store: Storage | null = null;
    try { store = window.sessionStorage; } catch { store = null; }
    const key = seenKey(user.id);
    let seen = loadSeen(store, key);            // survives a page refresh in this tab
    let stop = false;
    const tick = async () => {
      try {
        const r = await api.cases();
        if (stop) return;
        const cases = r.cases;                   // newest activity first
        const res = newCaseIds(seen, notifiableCaseIds(cases));     // rule met; repeats keep the same case_id
        seen = res.seen; saveSeen(store, key, seen);
        setItems(cases);
        if (res.fresh.length && user.role !== "sekolah") {
          setUnread((u) => u + res.fresh.length);
          setToast(cases.find((c) => c.case_id === res.fresh[0]) ?? null);
          playAlarm();                           // bip buzzer ala Arduino; diam bila disenyapkan (alarm.ts)
        }
      } catch { /* keep last list; the page shows connection errors */ }
    };
    void tick();
    const t = window.setInterval(() => void tick(), 4000);
    return () => { stop = true; window.clearInterval(t); };
  }, [user]);
  return useMemo(() => ({ items, unread, markRead: () => setUnread(0), toast, dismiss: () => setToast(null),
    summaries, summaryToast, dismissSummary: () => setSummaryToast(null),
    summaryExam, openSummary: (id: number) => setSummaryExam(id), closeSummary: () => setSummaryExam(null) }),
  [items, unread, toast, summaries, summaryToast, summaryExam]);
}

export default function App() {
  // The stored session only says that a token exists. Who the user is and which role they have always comes from
  // the server (/auth/me) before any dashboard is shown; a role edited in sessionStorage is never trusted.
  const hasToken = !!session.token();
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(hasToken);
  const [checkError, setCheckError] = useState("");
  const [checkRun, setCheckRun] = useState(0);
  const [screen, setScreen] = useState<Screen>(() => initialScreen(window.location.pathname, hasToken));
  const [portal, setPortal] = useState<Portal>("siswa");
  const toLogin = useCallback(() => setScreen("login"), []);
  const enterDashboard = useCallback(() => setScreen("dashboard"), []);
  const [role, setRole] = useState<Role>("Pengawas");
  useEffect(() => {
    if (!session.token()) return;               // no session: `checking` already started as false
    let stop = false;
    api.me().then((me) => {
      if (stop) return;
      const token = session.token();
      if (token) session.set(token, me);
      const verified = ROLE_LABEL[me.role];
      setUser(me); setRole(verified);
      setScreen(opensIndications(window.location.search, verified) ? "indications" : "dashboard");
    }).catch((e) => {
      // 401: the request helper already cleared the session and opened Login. Other errors: ask to retry.
      if (!stop && !(e instanceof ApiError && e.status === 401)) setCheckError((e as Error).message);
    }).finally(() => { if (!stop) setChecking(false); });
    return () => { stop = true; };
  }, [checkRun]);
  const [examId, setExamId] = useState<number | null>(null);
  const [studentId, setStudentId] = useState<number | null>(null);
  const [eventId, setEventId] = useState<string | null>(null);
  const notify = useIndicationNotifications(user);
  useEffect(() => { setUnauthorizedHandler(() => { setUser(null); setScreen("login"); }); }, []);
  const allowed = ALLOWED_SCREENS as Record<Role, Screen[]>;
  const go = (next: Screen) => {
    if (next === "login") { session.clear(); setUser(null); }
    setScreen(next === "login" || next === "beranda" || allowed[role].includes(next) ? next : "access-denied");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  // Role comes from the server; going through setRole keeps the original context API.
  const setRoleAndGo = (r: Role) => setRole(r);
  let page: ReactNode;
  if (checking || checkError) page = <main className="grid min-h-screen place-items-center bg-paper px-6 text-center text-navy" aria-live="polite">
    {checking ? <p className="text-sm text-[#687483]">Memeriksa sesi…</p> : <div className="max-w-sm">
      <p className="text-sm text-[#536173]">Sesi belum dapat diperiksa: {checkError}</p>
      <div className="mt-4 flex justify-center gap-3"><Button onClick={() => { setCheckError(""); setChecking(true); setCheckRun((n) => n + 1); }}>Coba lagi</Button><Button variant="secondary" onClick={() => { session.clearAll(); setCheckError(""); setScreen("login"); }}>Masuk ulang</Button></div>
    </div>}
  </main>;
  else if (screen === "beranda") page = <Landing user={user} start={(next) => { setPortal(next); setScreen("loading"); window.scrollTo(0, 0); }} toDashboard={() => go("dashboard")} />;
  else if (screen === "loading" && !user) page = <LoginLoading onComplete={toLogin} />;
  else if (screen === "entering" && user) page = <AccountLoading user={user} onComplete={enterDashboard} />;
  else if (screen === "login" || !user) page = <Login key={portal} portal={portal} go={(s) => setScreen(s)} />;
  else if (screen === "dashboard") page = <Dashboard go={go} />;
  else if (screen === "sessions") page = <Sessions go={go} />;
  else if (screen === "create") page = <AdminCreateExam go={go} />;
  else if (screen === "exam-detail") page = <ExamDetail go={go} />;
  else if (screen === "waiting") page = <WaitingRoom go={go} />;
  else if (screen === "consent") page = <Consent go={go} />;
  else if (screen === "device") page = <Device go={go} />;
  else if (screen === "seb-check") page = <SebCheck go={go} />;
  else if (screen === "exam") page = <ExamRoom go={go} />;
  else if (screen === "monitor") page = <Monitoring go={go} />;
  else if (screen === "student-detail") page = <StudentMonitoringDetail go={go} />;
  else if (screen === "detail") page = <SupervisorEvidenceDetail go={go} />;
  else if (screen === "timeline") page = <MonitoringTimeline go={go} />;
  else if (screen === "report") page = <Report go={go} />;
  else if (screen === "indications") page = <IndicationsPage go={go} />;
  else if (screen === "history") page = <HistoryPage go={go} />;
  else if (screen === "my-exams") page = <MyExams go={go} />;
  else if (screen === "students") page = <StudentList go={go} />;
  else if (screen === "users") page = <UserManagement go={go} />;
  else if (screen === "configuration") page = <ConfigurationPage go={go} />;
  else if (screen === "retention") page = <RetentionPage go={go} />;
  else if (screen === "audit") page = <AuditPage go={go} />;
  else if (screen === "meeting") page = <MeetingPage go={go} />;
  else if (screen === "access-denied") page = <AccessDenied go={go} />;
  else page = <Settings go={go} />;
  return <RoleContext.Provider value={{ role, setRole: setRoleAndGo }}><UserContext.Provider value={{ user, setUser }}><SelectionContext.Provider value={{ examId, setExamId, studentId, setStudentId, eventId, setEventId }}><NotifyContext.Provider value={notify}>{page}</NotifyContext.Provider></SelectionContext.Provider></UserContext.Provider></RoleContext.Provider>;
}
