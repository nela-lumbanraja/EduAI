import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  api, ApiError, examWindow, fmtDate, fmtDateTime, fmtDuration, fmtTime, FRAME_REASON, initials, minutesAgo, remaining, ROLE_LABEL,
  session, setUnauthorizedHandler, STATE_LABEL, AUDIO_REASON,
  type AIEvent, type AIHealth, type AnalysisState, type AuditRow, type CaseSummary, type Decision, type Exam, type ExamSummary, type Health, type MonitoringInfo,
  type MonitoringState, type Report as ReportData, type StudentRow, type TimelineItem, type User, type UserRow,
} from "./api";
import { loadSeen, newCaseIds, newSummaryKeys, notifiableCaseIds, saveSeen, seenKey, seenSummariesKey } from "./notify";
import { SpeechScorer } from "./audio";
import { FrameUploader, measureLatency, mediaErrorMessage, startStudentMedia, useExamVideoRoom, useMicLevel, useVideo, type StudentMedia } from "./media";
import type { RemoteTrack } from "livekit-client";

type Role = "Siswa" | "Pengawas" | "Penyelenggara Ujian" | "Admin" | "Pihak Sekolah";

type Screen =
  | "login"
  | "dashboard"
  | "sessions"
  | "create"
  | "exam-detail"
  | "waiting"
  | "consent"
  | "device"
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
  | "permissions"
  | "configuration"
  | "retention"
  | "audit"
  | "access-denied"
  | "students"
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
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const load = useCallback(async () => {
    try { setData(await fnRef.current()); setError(""); } catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }, []);
  useEffect(() => {
    setLoading(true);
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

function Notice({ children, tone = "amber" }: { children: ReactNode; tone?: "amber" | "red" | "blue" }) {
  const s = { amber: "border-amber-200 bg-amber-50 text-amber-900", red: "border-red-200 bg-red-50 text-red-700", blue: "border-blue-100 bg-blue-50 text-blue-800" };
  return <div role={tone === "red" ? "alert" : "status"} className={`mb-5 rounded-md border px-4 py-3 text-sm leading-6 ${s[tone]}`}>{children}</div>;
}

function SampleTag() {
  return <span className="ml-2 inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 align-middle text-[11px] font-semibold text-slate-500 ring-1 ring-inset ring-slate-200" title="Bagian ini belum tersambung ke backend">Data contoh</span>;
}

type IconName =
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
  | "file";

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    monitor: <><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></>,
    report: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h6" /></>,
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
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function Logo({ compact = false, dark = false }: { compact?: boolean; dark?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative grid size-9 place-items-center rounded-lg bg-blue-700 text-[17px] font-semibold text-white">E<span className={`absolute -right-0.5 -top-0.5 size-2.5 rounded-full bg-amber-400 ring-2 ${dark ? "ring-[#16213a]" : "ring-white"}`} /></div>
      {!compact && <div className="leading-tight"><div className={`text-lg font-semibold tracking-tight ${dark ? "text-white" : "text-slate-900"}`}>EduAI</div><div className={`text-[11px] ${dark ? "text-slate-400" : "text-slate-500"}`}>Pengawasan Ujian</div></div>}
    </div>
  );
}

function Button({ children, variant = "primary", icon, disabled, onClick, className = "", type = "button" }: { children: ReactNode; variant?: "primary" | "secondary" | "ghost" | "success"; icon?: IconName; disabled?: boolean; onClick?: () => void; className?: string; type?: "button" | "submit" }) {
  const styles = { primary: "bg-blue-700 text-white hover:bg-blue-800", secondary: "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50", ghost: "text-slate-600 hover:bg-slate-100", success: "bg-emerald-600 text-white hover:bg-emerald-700" };
  return <button type={type} disabled={disabled} onClick={onClick} className={`inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none ${styles[variant]} ${className}`}>{icon && <Icon name={icon} size={18} />}{children}</button>;
}

function Badge({ children, tone = "gray" }: { children: ReactNode; tone?: "blue" | "green" | "amber" | "gray" }) {
  const styles = { blue: "bg-blue-50 text-blue-700 ring-blue-100", green: "bg-emerald-50 text-emerald-700 ring-emerald-100", amber: "bg-amber-50 text-amber-700 ring-amber-100", gray: "bg-slate-100 text-slate-600 ring-slate-200" };
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${styles[tone]}`}>{children}</span>;
}

function Field({ label, placeholder, type = "text", value, name }: { label: string; placeholder?: string; type?: string; value?: string; name?: string }) {
  return <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">{label}</span><input name={name} type={type} defaultValue={value} placeholder={placeholder} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-50" /></label>;
}

const statusTone = (s: string) => (s === "Selesai" ? "green" : s === "Sedang Berlangsung" ? "blue" : "gray") as "green" | "blue" | "gray";
const stateTone = (s?: AnalysisState | null) => (s === "normal" ? "green" : s === "indication" || s === "ai_offline" ? "amber" : s === "warming_up" ? "blue" : "gray") as "green" | "amber" | "blue" | "gray";
const reviewTone = (l?: string | null) => (l === "Valid" ? "green" : !l || l === "Perlu Tinjauan Lanjut" ? "amber" : "gray") as "green" | "amber" | "gray";
const reviewLabel = (l?: string | null) => l ?? "Belum ditinjau";
const eventTitle = (e: AIEvent | CaseSummary) => e.label ?? e.indicator;
// Review status of a grouped case. A case with unreviewed events counts as "Belum ditinjau" even if older
// events of it were reviewed (new events never inherit a decision).
const caseLabel = (c: CaseSummary) => (c.unreviewed_count > 0 ? (c.unreviewed_count < c.event_count ? `${c.unreviewed_count} baru belum ditinjau` : "Belum ditinjau") : c.review_status ?? "Belum ditinjau");
const caseTone = (c: CaseSummary) => (c.unreviewed_count > 0 ? "amber" : reviewTone(c.review_status === "Campuran" ? "Perlu Tinjauan Lanjut" : c.review_status));
const scoreText = (e: AIEvent) => (e.score == null ? "—" : `${Math.round(e.score * 100)}%`);
const examTime = (e: Exam) => { const { end } = examWindow(e); return `${e.start_time.replace(":", ".")}–${end.toTimeString().slice(0, 5).replace(":", ".")} WIB`; };

function Login({ go }: { go: (s: Screen) => void }) {
  const { setRole } = useRole();
  const { setUser } = useUser();
  const [register, setRegister] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const field = "h-11 w-full rounded-md border border-slate-300 bg-white px-3.5 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-blue-600 focus:ring-4 focus:ring-blue-100";
  const tiles = [["Alya P.", "bg-blue-100"], ["Bima P.", "bg-slate-200"], ["Citra L.", "bg-amber-100", true], ["Dimas S.", "bg-slate-200"], ["Farah N.", "bg-blue-100"], ["Gilang R.", "bg-slate-200"]] as [string, string, boolean?][];

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const mail = email.trim().toLowerCase();
    if (register && password.length < 6) return setError("Kata sandi minimal 6 karakter.");
    setBusy(true);
    setError("");
    try {
      const res = register ? await api.register(name.trim(), mail, password) : await api.login(mail, password);
      session.set(res.token, res.user);
      setUser(res.user);
      setRole(ROLE_LABEL[res.user.role]);
      go("dashboard");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const switchMode = () => { setRegister(!register); setError(""); };

  return (
    <main className="grid min-h-screen bg-white lg:grid-cols-[1.1fr_.9fr]">
      <section className="hidden flex-col justify-between border-r border-slate-200 bg-slate-50 p-14 lg:flex">
        <Logo />
        <div>
          <h1 className="max-w-md text-4xl font-semibold leading-tight text-slate-900">Pengawasan ujian online yang lebih teliti, keputusan tetap di tangan pengawas.</h1>
          <p className="mt-4 max-w-md text-base leading-7 text-slate-600">EduAI menandai momen yang perlu dicek, lalu pengawas meninjau buktinya dan memutuskan sendiri.</p>
          <div className="mt-10 w-full max-w-lg rounded-lg border border-slate-200 bg-white p-4" aria-label="Ilustrasi tampilan pemantauan">
            <div className="mb-3 flex items-center justify-between text-xs">
              <div><p className="font-semibold text-slate-800">Ujian Akhir Matematika XI</p><p className="text-slate-500">XI IPA 2 · 31 dari 32 siswa hadir</p></div>
              <span className="rounded-full bg-emerald-50 px-2.5 py-1 font-medium text-emerald-700">Berlangsung</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {tiles.map(([nama, warna, tandai]) => (
                <div key={nama} className={`relative aspect-[4/3] overflow-hidden rounded-md ${warna} ${tandai ? "ring-2 ring-amber-500" : ""}`}>
                  <svg viewBox="0 0 40 40" aria-hidden="true" className="absolute bottom-0 left-1/2 h-4/5 -translate-x-1/2 text-white/70"><circle cx="20" cy="15" r="7" fill="currentColor" /><path d="M6 40c0-9 6-14 14-14s14 5 14 14z" fill="currentColor" /></svg>
                  <span className="absolute bottom-1.5 left-1.5 rounded bg-slate-900/60 px-1.5 py-0.5 text-[10px] text-white">{nama}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 flex items-center justify-between rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <span>Citra Lestari · wajah tidak terlihat 12 detik</span>
              <span className="font-semibold">Tinjau</span>
            </div>
          </div>
        </div>
        <p className="text-sm text-slate-500">SMA Negeri 8 Bandung</p>
      </section>

      <section className="flex items-center justify-center px-6 py-12 sm:px-12">
        <div className="w-full max-w-sm">
          <div className="mb-10 lg:hidden"><Logo /></div>
          <h2 className="text-2xl font-semibold text-slate-900">{register ? "Buat akun EduAI" : "Masuk ke EduAI"}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">{register ? "Pendaftaran mandiri hanya untuk siswa (email diawali siswa, misalnya siswa7@gmail.com). Akun staf dibuat oleh Admin." : "Gunakan email yang sudah didaftarkan sekolah."}</p>
          <form onSubmit={submit} className="mt-8 space-y-4">
            {register && <label className="block"><span className="mb-1.5 block text-sm font-medium text-slate-700">Nama lengkap</span><input value={name} onChange={(e) => setName(e.target.value)} className={field} placeholder="Nama sesuai data sekolah" /></label>}
            <label className="block"><span className="mb-1.5 block text-sm font-medium text-slate-700">Email</span><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" className={field} placeholder="pengawas1@gmail.com" /></label>
            <label className="block"><span className="mb-1.5 block text-sm font-medium text-slate-700">Kata sandi</span>
              <div className="relative"><input type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={register ? "new-password" : "current-password"} className={`${field} pr-24`} placeholder="Minimal 6 karakter" />
                <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-3 text-xs font-medium text-slate-600 hover:text-slate-900">{show ? "Sembunyikan" : "Tampilkan"}</button></div>
            </label>
            {error && <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-sm leading-5 text-red-700">{error}</p>}
            <button type="submit" disabled={!email || !password || busy} className="h-11 w-full rounded-md bg-blue-700 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:opacity-40">{busy ? "Memproses..." : register ? "Daftar" : "Masuk"}</button>
            {!register && <button type="button" onClick={() => alert("Hubungi admin sekolah untuk mengatur ulang kata sandi.")} className="block w-full text-center text-sm text-blue-700 hover:underline">Lupa kata sandi?</button>}
          </form>
          <div className="my-6 flex items-center gap-4 text-xs text-slate-400"><span className="h-px flex-1 bg-slate-200" />atau<span className="h-px flex-1 bg-slate-200" /></div>
          <p className="text-center text-sm text-slate-600">{register ? "Sudah punya akun?" : "Belum punya akun?"} <button type="button" onClick={switchMode} className="font-semibold text-blue-700 hover:underline">{register ? "Masuk" : "Daftar"}</button></p>
          <p className="mt-8 rounded-md bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-500">Akun uji (hanya jika data demo backend aktif): siswa1, pengawas1, penyelenggara1, admin1, atau sekolah1@gmail.com, kata sandi 123456.</p>
        </div>
      </section>
    </main>
  );
}

function Sidebar({ active, go, open, setOpen }: { active: Screen; go: (s: Screen) => void; open: boolean; setOpen: (v: boolean) => void }) {
  const { role } = useRole();
  const { user } = useUser();
  const menus: Record<Role, { id: Screen; label: string; icon: IconName }[]> = {
    Siswa: [
      { id: "dashboard", label: "Dasbor", icon: "grid" },
      { id: "my-exams", label: "Ujian Saya", icon: "calendar" },
      { id: "settings", label: "Profil", icon: "settings" },
    ],
    Pengawas: [
      { id: "dashboard", label: "Dasbor", icon: "grid" },
      { id: "sessions", label: "Sesi Ujian", icon: "calendar" },
      { id: "monitor", label: "Monitoring", icon: "monitor" },
      { id: "indications", label: "Indikasi", icon: "bell" },
      { id: "history", label: "Riwayat", icon: "clock" },
      { id: "report", label: "Laporan", icon: "report" },
      { id: "settings", label: "Profil", icon: "settings" },
    ],
    "Penyelenggara Ujian": [
      { id: "dashboard", label: "Dasbor", icon: "grid" },
      { id: "sessions", label: "Sesi Ujian", icon: "calendar" },
      { id: "students", label: "Peserta", icon: "users" },
      { id: "users", label: "Pengawas", icon: "shield" },
      { id: "report", label: "Laporan", icon: "report" },
    ],
    Admin: [
      { id: "dashboard", label: "Dasbor", icon: "grid" },
      { id: "sessions", label: "Daftar Ujian", icon: "calendar" },
      { id: "users", label: "Manajemen User", icon: "users" },
      { id: "permissions", label: "Role & Izin", icon: "shield" },
      { id: "configuration", label: "Konfigurasi", icon: "settings" },
      { id: "retention", label: "Retensi Data", icon: "clock" },
      { id: "audit", label: "Audit Log", icon: "file" },
      { id: "settings", label: "Profil", icon: "settings" },
    ],
    "Pihak Sekolah": [
      { id: "dashboard", label: "Dasbor", icon: "grid" },
      { id: "sessions", label: "Informasi Sesi", icon: "calendar" },
      { id: "indications", label: "Indikasi Tervalidasi", icon: "bell" },
      { id: "report", label: "Laporan Final", icon: "report" },
      { id: "settings", label: "Profil", icon: "settings" },
    ],
  };
  const nav = menus[role];
  const logout = () => { session.clear(); go("login"); };
  return <>
    {open && <button className="fixed inset-0 z-40 bg-slate-900/30 lg:hidden" aria-label="Tutup navigasi" onClick={() => setOpen(false)} />}
    <aside className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-[#16213a] p-5 transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="flex items-center justify-between"><Logo dark /><button className="rounded-md p-2 text-slate-300 hover:bg-white/10 lg:hidden" onClick={() => setOpen(false)}><Icon name="close" /></button></div>
      <nav className="mt-10 flex-1 space-y-1">
        <p className="mb-3 px-3 text-[11px] font-bold uppercase tracking-widest text-slate-400">Ruang kerja</p>
        {nav.map((item) => <button key={item.id} onClick={() => { go(item.id); setOpen(false); }} className={`flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm font-semibold transition ${active === item.id || (["create", "exam-detail", "waiting"].includes(active) && item.id === "sessions") || (["detail", "student-detail", "timeline"].includes(active) && item.id === "monitor") ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}><Icon name={item.icon} size={19} />{item.label}</button>)}
      </nav>
      <div className="rounded-lg bg-white/5 p-3.5"><div className="flex items-center gap-3"><div className="grid size-9 place-items-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">{initials(user?.name ?? "")}</div><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-white">{user?.name}</p><p className="truncate text-[11px] text-slate-400">{role}</p></div><button onClick={logout} className="text-slate-400 hover:text-white" aria-label="Keluar"><Icon name="arrow" size={16} /></button></div></div>
    </aside>
  </>;
}

function Topbar({ title, onMenu, go }: { title: string; onMenu: () => void; go: (s: Screen) => void }) {
  const { role } = useRole();
  const { user } = useUser();
  const { setEventId, setExamId } = useSel();
  const notify = useContext(NotifyContext);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = window.setInterval(() => setNow(new Date()), 1000); return () => window.clearInterval(t); }, []);
  const staff = role !== "Siswa";
  // Pop-up "Tinjau": the new case's first event in the existing evidence page. Bell item: the case on the Indikasi page.
  const openToast = (c: CaseSummary) => { setExamId(c.exam_id); setEventId(c.first_event_id); go(role === "Pihak Sekolah" ? "indications" : "detail"); };
  const openCase = (c: CaseSummary) => { setNotificationsOpen(false); setExamId(c.exam_id); setEventId(c.first_event_id); go("indications"); };
  return <header className="sticky top-0 z-30 flex h-18 items-center justify-between border-b border-slate-200 bg-white/95 px-4 sm:px-8">
    <div className="flex min-w-0 items-center gap-3"><button className="rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={onMenu}><Icon name="menu" /></button><div className="min-w-0"><p className="truncate text-sm font-bold text-slate-900">{title}</p><p className="text-xs text-slate-500">SMA Negeri 8 Bandung</p></div></div>
    <div className="flex items-center gap-3 sm:gap-5">
      <div className="hidden items-center gap-2 rounded-md bg-blue-50 px-3 py-2 text-sm font-bold text-blue-700 md:flex" title="Waktu sekarang"><Icon name="clock" size={17} />{now.toLocaleTimeString("id-ID", { hour12: false })}</div>
      {staff && <div className="relative"><button onClick={() => { setNotificationsOpen(!notificationsOpen); notify.markRead(); }} className="relative rounded-md p-2 text-slate-500 hover:bg-slate-100" aria-label="Buka notifikasi"><Icon name="bell" />{notify.unread > 0 && <span className="absolute right-2 top-2 size-2 rounded-full bg-amber-500 ring-2 ring-white" />}</button>{notificationsOpen && <div className="absolute right-0 top-12 z-50 w-80 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="border-b border-slate-100 p-4"><p className="text-sm font-bold text-slate-900">Notifikasi {role === "Pihak Sekolah" ? "Sekolah" : "Pengawas"}</p><p className="mt-1 text-xs text-slate-500">{notify.items.filter((i) => i.unreviewed_count > 0).length} kasus belum ditinjau</p></div><div className="max-h-96 divide-y divide-slate-100 overflow-y-auto">{notify.summaries.slice(0, 2).flatMap((sm) => sm.summary.students.filter((st) => st.indications.length).slice(0, 6).map((st) => <button key={`s-${sm.exam_id}-${st.student_id}`} onClick={() => { setNotificationsOpen(false); notify.openSummary(sm.exam_id); }} className="flex w-full gap-3 bg-blue-50/40 p-4 text-left hover:bg-slate-50"><span className="mt-0.5 text-blue-700"><Icon name="report" size={15} /></span><span className="min-w-0"><span className="block text-xs font-semibold leading-5 text-slate-800">Ringkasan · {st.name}</span><span className="block text-xs leading-5 text-slate-600">{st.indications.map((i) => `${i.label ?? i.indicator} ${i.occurrences}×`).join(" · ")}</span><span className="mt-1 block text-[10px] text-slate-400">{sm.kind === "pre_end" ? "10 menit sebelum selesai" : "Ringkasan akhir"} · {sm.summary.exam_name}</span></span></button>))}{notify.items.length === 0 ? <p className="p-4 text-xs text-slate-500">Belum ada indikasi.</p> : notify.items.slice(0, 8).map((item) => <button key={item.case_id} onClick={() => openCase(item)} className="flex w-full gap-3 p-4 text-left hover:bg-slate-50"><span className={`mt-1 size-2 shrink-0 rounded-full ${item.unreviewed_count > 0 ? "bg-amber-500" : "bg-blue-600"}`} /><span><span className="block text-xs leading-5 text-slate-700">{eventTitle(item)} — {item.student?.name}</span><span className="mt-1 block text-[10px] text-slate-400">{item.episode_count ?? item.event_count} kejadian{item.rule && !item.rule.met ? " · di bawah ambang" : ""} · {item.exam?.name} · {minutesAgo(item.last_start_ts)}</span></span></button>)}</div></div>}</div>}
      <div className="flex items-center gap-3 border-l border-slate-200 pl-3 sm:pl-5"><div className="grid size-9 place-items-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">{initials(user?.name ?? "")}</div><div className="hidden sm:block"><p className="text-sm font-bold text-slate-800">{user?.name}</p><p className="text-xs text-slate-500">{role}</p></div></div>
    </div>
    {notify.summaryToast && <div role="alert" className="fixed right-6 top-20 z-[60] w-80 rounded-md border border-blue-300 bg-white p-4 shadow-lg"><div className="flex items-start gap-3"><span className="mt-0.5 text-blue-700"><Icon name="report" size={18} /></span><div className="min-w-0 flex-1"><p className="text-sm font-bold text-slate-900">{notify.summaryToast.kind === "pre_end" ? "Ringkasan indikasi · 10 menit lagi selesai" : "Ringkasan akhir indikasi"}</p><p className="mt-1 text-xs leading-5 text-slate-600">{notify.summaryToast.summary.exam_name} · {notify.summaryToast.summary.students.filter((s) => s.indications.length).length} siswa dengan indikasi tercatat</p><p className="mt-1 text-[11px] text-slate-400">Indikasi potensial untuk ditinjau — bukan keputusan pelanggaran.</p><div className="mt-3 flex gap-2"><Button className="h-8 px-3 text-xs" onClick={() => { const s = notify.summaryToast!; notify.dismissSummary(); notify.openSummary(s.exam_id); }}>Lihat ringkasan</Button><Button variant="ghost" className="h-8 px-3 text-xs" onClick={notify.dismissSummary}>Tutup</Button></div></div></div></div>}
    {notify.summaryExam !== null && <SummaryDialog examId={notify.summaryExam} onClose={notify.closeSummary} go={go} />}
    {notify.toast && <div role="alert" className="fixed bottom-6 right-6 z-[60] w-80 rounded-md border border-amber-300 bg-white p-4 shadow-lg"><div className="flex items-start gap-3"><span className="mt-0.5 text-amber-600"><Icon name="bell" size={18} /></span><div className="min-w-0 flex-1"><p className="text-sm font-bold text-slate-900">Indikasi baru</p><p className="mt-1 text-xs leading-5 text-slate-600">{notify.toast.student?.name} · {eventTitle(notify.toast)} · {fmtTime(notify.toast.first_start_ts)}</p><p className="mt-1 text-[11px] text-slate-500">Satu notifikasi untuk siswa dan perilaku ini. Kejadian berikutnya hanya menambah hitungan di kasus yang sama.</p><p className="mt-1 text-[11px] text-slate-400">Perlu ditinjau pengawas — bukan keputusan pelanggaran.</p><div className="mt-3 flex gap-2"><Button className="h-8 px-3 text-xs" onClick={() => { const t = notify.toast!; notify.dismiss(); openToast(t); }}>Tinjau</Button><Button variant="ghost" className="h-8 px-3 text-xs" onClick={notify.dismiss}>Tutup</Button></div></div></div></div>}
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
    <div className="flex items-start justify-between gap-3 border-b border-slate-100 p-5"><div><h2 className="font-bold text-slate-900">Ringkasan indikasi{d ? ` — ${d.summary.exam_name}` : ""}</h2><p className="mt-1 text-xs text-slate-500">{!d ? "Memuat..." : d.preview ? `Pratinjau langsung (belum dibuat). ${d.scheduled_at ? `Ringkasan otomatis pukul ${fmtTime(d.scheduled_at)} (10 menit sebelum selesai).` : "Jadwal selesai tidak diketahui: ringkasan dibuat saat ujian ditutup."}` : `${d.kind === "pre_end" ? "Dibuat 10 menit sebelum selesai" : "Ringkasan akhir"} · ${fmtTime(d.created_at)}`}</p></div><button onClick={onClose} aria-label="Tutup"><Icon name="close" /></button></div>
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
  const [open, setOpen] = useState(false);
  return <div className="min-h-screen bg-slate-50"><Sidebar active={active} go={go} open={open} setOpen={setOpen} /><div className="lg:pl-64"><Topbar title={title} onMenu={() => setOpen(true)} go={go} />{children}</div></div>;
}

function PageTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: ReactNode; description: string; action?: ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div>{eyebrow && <p className="mb-2 text-xs font-bold uppercase tracking-widest text-blue-700">{eyebrow}</p>}<h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{title}</h1><p className="mt-2 text-sm text-slate-500">{description}</p></div>{action}</div>;
}

function greeting() { const h = new Date().getHours(); return h < 11 ? "Selamat pagi" : h < 15 ? "Selamat siang" : h < 18 ? "Selamat sore" : "Selamat malam"; }

function Dashboard({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  if (role === "Siswa") return <StudentDashboard go={go} />;
  if (role === "Admin") return <AdminDashboard go={go} />;
  if (role === "Penyelenggara Ujian" || role === "Pihak Sekolah") return <InstitutionDashboard go={go} role={role} />;
  return <SupervisorDashboard go={go} />;
}

function SupervisorDashboard({ go }: { go: (s: Screen) => void }) {
  const { user } = useUser();
  const { setExamId, setEventId } = useSel();
  const d = usePoll(() => api.dashboard(), [], 10000);
  const s = d.data?.summary;
  const exams = d.data?.exams ?? [];
  const active = exams.find((e) => e.status === "Sedang Berlangsung");
  const scheduled = exams.find((e) => e.status === "Terjadwal");
  const summary = [
    [String(s?.active_sessions ?? "—"), "Sesi aktif", "video", "blue"],
    [String(s?.students_online ?? "—"), "Siswa sedang ujian", "users", "blue"],
    [String(s?.cases_unreviewed ?? "—"), "Kasus belum ditinjau", "bell", "amber"],
    [String(s?.valid ?? "—"), "Deteksi valid", "check", "green"],
    [String(s?.further ?? "—"), "Deteksi perlu tinjauan lanjut", "clock", "amber"],
  ];
  const openExam = (id: number, screen: Screen) => { setExamId(id); go(screen); };
  return <AppShell active="dashboard" go={go} title="Dasbor"><main className="p-4 sm:p-8">
    <PageTitle title={`${greeting()}, ${user?.name.split(" ")[0] ?? ""}`} description="Berikut ringkasan kegiatan ujian yang ditugaskan kepada Anda hari ini." />
    {d.error && <Notice tone="red">{d.error}</Notice>}
    {s?.cases_total != null && <p className="mb-3 text-sm text-slate-600"><span className="font-bold text-slate-900">{s.cases_total} kasus</span> terkelompok dari <span className="font-bold text-slate-900">{s.detections_total} deteksi AI</span>. Satu kasus = kejadian berulang dari siswa, ujian, dan jenis indikasi yang sama; setiap deteksi asli tetap tersimpan.</p>}
    <section className="overflow-x-auto rounded-md border border-slate-200 bg-white"><div className="flex min-w-[760px] divide-x divide-slate-200">{summary.map(([num, label, icon, tone]) => <div key={label} className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3"><span className={tone === "amber" ? "text-amber-600" : tone === "green" ? "text-emerald-600" : "text-slate-400"}><Icon name={icon as IconName} size={17} /></span><div><p className="text-lg font-bold leading-5 text-slate-900">{num}</p><p className="mt-0.5 whitespace-nowrap text-xs text-slate-500">{label}</p></div></div>)}</div></section>
    <div className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_.8fr]">
      <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-5"><div><h2 className="font-bold text-slate-900">Sesi aktif</h2><p className="mt-1 text-xs text-slate-500">Ujian yang sedang membutuhkan pengawasan.</p></div><button onClick={() => go("sessions")} className="text-xs font-semibold text-blue-700">Lihat semua</button></div>
        <div className="p-4">{active ? <button onClick={() => openExam(active.id, "monitor")} className="w-full rounded-md border border-blue-100 bg-blue-50/50 p-5 text-left transition hover:border-blue-300"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start"><div><div className="flex items-center gap-2"><Badge tone="blue"><span className="size-1.5 animate-pulse rounded-full bg-blue-700" />Berlangsung</Badge><span className="text-xs text-slate-400">{examTime(active)}</span></div><h3 className="mt-3 font-bold text-slate-900">{active.name}</h3><p className="mt-1 text-sm text-slate-500">{active.subject} • {active.class_name}</p></div><div className="grid grid-cols-3 gap-5 text-center"><div><p className="font-bold text-slate-900">{active.student_count}</p><p className="text-[10px] text-slate-500">Peserta</p></div><div><p className="font-bold text-emerald-600">{active.online ?? 0}</p><p className="text-[10px] text-slate-500">Terhubung</p></div><div><p className="font-bold text-amber-600">{active.indications?.total ?? 0}</p><p className="text-[10px] text-slate-500">Indikasi</p></div></div></div><div className="mt-5 flex items-center justify-between border-t border-blue-100 pt-4"><p className="text-xs text-blue-700">Sisa waktu {remaining(active)}</p><span className="flex items-center gap-1 text-xs font-bold text-blue-700">Buka pemantauan <Icon name="chevron" size={14} /></span></div></button> : <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">{d.loading ? "Memuat..." : "Tidak ada sesi yang sedang berlangsung."}</p>}</div>
        {scheduled && <div className="border-t border-slate-100 px-4 py-3"><button onClick={() => openExam(scheduled.id, "waiting")} className="flex w-full items-center justify-between rounded-md p-3 text-left hover:bg-slate-50"><div><p className="text-sm font-semibold text-slate-800">{scheduled.name}</p><p className="mt-1 text-xs text-slate-500">{scheduled.class_name} • {fmtDate(scheduled.date)} pukul {scheduled.start_time.replace(":", ".")} • {scheduled.student_count} siswa</p></div><Badge tone="gray">Dijadwalkan</Badge></button></div>}
      </section>
      <section className="rounded-md border border-slate-200 bg-white"><div className="border-b border-slate-100 p-5"><h2 className="font-bold text-slate-900">Indikasi terbaru</h2><p className="mt-1 text-xs text-slate-500">Hanya tampilkan yang memerlukan perhatian.</p></div><div className="divide-y divide-slate-100">{(d.data?.recent_cases ?? []).slice(0, 3).map((item) => <button key={item.case_id} onClick={() => { setExamId(item.exam_id); setEventId(item.first_event_id); go("indications"); }} className="flex w-full gap-3 p-4 text-left hover:bg-slate-50"><div className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-amber-50 text-amber-600"><Icon name="bell" size={15} /></div><div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-800">{eventTitle(item)} <span className="font-normal text-slate-500">· {item.event_count} kejadian</span></p><p className="mt-1 truncate text-xs text-slate-500">{item.student?.name} • {item.exam?.name}</p></div><span className="text-[10px] text-slate-400">{minutesAgo(item.last_start_ts)}</span></button>)}{!d.loading && !(d.data?.recent_cases ?? []).length && <p className="p-5 text-sm text-slate-500">Belum ada indikasi dari AI.</p>}</div></section>
    </div>
    <section className="mt-6 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-5"><div><h2 className="font-bold text-slate-900">Ujian yang Ditugaskan</h2><p className="mt-1 text-xs text-slate-500">Hanya sesi yang ditugaskan kepada {user?.name}.</p></div><button onClick={() => go("sessions")} className="text-xs font-semibold text-blue-700">Lihat semua sesi</button></div><div className="overflow-x-auto"><table className="w-full min-w-[980px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Nama ujian</th><th className="px-5 py-3">Tanggal</th><th className="px-5 py-3">Jam</th><th className="px-5 py-3">Durasi</th><th className="px-5 py-3">Peserta</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Indikasi</th><th className="px-5 py-3">Aksi</th></tr></thead><tbody>{exams.slice(0, 5).map((s) => <tr key={s.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{s.name}</td><td className="px-5 py-4 text-slate-600">{fmtDate(s.date)}</td><td className="px-5 py-4 text-slate-600">{s.start_time.replace(":", ".")} WIB</td><td className="px-5 py-4 text-slate-600">{s.duration_min} menit</td><td className="px-5 py-4 text-slate-600">{s.student_count}</td><td className="px-5 py-4"><Badge tone={statusTone(s.status)}>{s.status === "Terjadwal" ? "Akan Dimulai" : s.status}</Badge></td><td className="px-5 py-4 font-semibold text-slate-700">{s.indications?.total ?? 0}</td><td className="px-5 py-4"><button onClick={() => openExam(s.id, "exam-detail")} className="text-xs font-bold text-blue-700">Lihat</button></td></tr>)}</tbody></table></div></section>
  </main></AppShell>;
}

function Sessions({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const { setExamId } = useSel();
  const canCreate = role === "Admin";
  const list = usePoll(() => api.exams(), []);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("Semua status");
  const rows = (list.data ?? []).filter((s) => s.name.toLowerCase().includes(q.toLowerCase()) && (status === "Semua status" || s.status === status));
  return <AppShell active="sessions" go={go} title="Daftar Sesi Ujian"><main className="p-4 sm:p-8">
    <PageTitle title={role === "Admin" ? "Daftar Ujian" : "Daftar Sesi Ujian"} description={role === "Pengawas" ? "Sesi yang ditugaskan kepada Anda." : role === "Admin" ? "Atur jadwal, peserta, pengawas, dan status ujian." : "Lihat jadwal dan aktivitas ujian sekolah."} action={canCreate ? <Button icon="plus" onClick={() => go("create")}>Create Ujian</Button> : undefined} />
    {list.error && <Notice tone="red">{list.error}</Notice>}
    <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
      <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between"><div className="relative max-w-sm flex-1"><span className="absolute left-3 top-2.5 text-slate-400"><Icon name="search" size={18} /></span><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari nama ujian..." className="h-10 w-full rounded-md border border-slate-200 pl-10 pr-3 text-sm outline-none focus:border-blue-500" /></div><select value={status} onChange={(e) => setStatus(e.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600"><option>Semua status</option><option>Sedang Berlangsung</option><option>Terjadwal</option><option>Selesai</option><option>Draft</option></select></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Nama ujian</th><th className="px-5 py-3.5">Tanggal & waktu</th><th className="px-5 py-3.5">Durasi</th><th className="px-5 py-3.5">Peserta</th><th className="px-5 py-3.5">Pengawas</th><th className="px-5 py-3.5">Status</th><th className="px-5 py-3.5">Aksi</th></tr></thead><tbody>{rows.map((s) => <tr key={s.id} className="border-t border-slate-100 hover:bg-slate-50/70"><td className="px-5 py-4 font-semibold text-slate-800">{s.name}<p className="mt-1 text-xs font-normal text-slate-400">{s.subject} • {s.class_name}</p></td><td className="px-5 py-4 text-slate-600">{fmtDate(s.date)}<span className="ml-2 text-slate-400">• {s.start_time.replace(":", ".")}</span></td><td className="px-5 py-4 text-slate-600">{s.duration_min} menit</td><td className="px-5 py-4 text-slate-600">{s.student_count} siswa</td><td className="px-5 py-4 text-slate-600">{s.supervisor?.name ?? "—"}</td><td className="px-5 py-4"><Badge tone={statusTone(s.status)}>{s.status}</Badge></td><td className="px-5 py-4"><div className="flex items-center gap-3 whitespace-nowrap"><button onClick={() => { setExamId(s.id); go("exam-detail"); }} className="text-xs font-bold text-blue-700">Lihat Detail</button>{role === "Admin" && <span className="text-xs text-slate-400" title="Edit/hapus ujian belum tersedia di backend">Edit & hapus belum tersedia</span>}</div></td></tr>)}</tbody></table></div>
      {!list.loading && rows.length === 0 && <p className="p-8 text-center text-sm text-slate-500">Belum ada sesi ujian.</p>}
    </div>
  </main></AppShell>;
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
    <button onClick={() => go("sessions")} className="mb-5 flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-800"><Icon name="arrow" size={18} />Kembali ke daftar ujian</button>
    {exam.error && <Notice tone="red">{exam.error}</Notice>}
    {e && <>
      <div className="rounded-md border border-slate-200 bg-white p-6"><div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-start"><div><div className="flex items-center gap-3"><Badge tone={statusTone(e.status)}><span className="size-1.5 rounded-full bg-current" />{e.status}</Badge><span className="text-xs text-slate-400">Kode ujian EX-{e.id}</span></div><h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-900">{e.name}</h1><p className="mt-2 text-sm text-slate-500">{e.subject} • Kelas {e.class_name}</p></div><div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => go("students")}>Daftar Siswa</Button><Button variant="secondary" onClick={() => go("indications")}>Lihat Indikasi</Button><Button variant="secondary" onClick={() => go("report")}>Lihat Laporan</Button>{canMonitor && <Button icon="monitor" onClick={() => go("monitor")}>Mulai Monitoring</Button>}</div></div>
        <div className="mt-7 grid gap-4 border-t border-slate-100 pt-6 sm:grid-cols-2 lg:grid-cols-4">{[["Tanggal & waktu", `${fmtDate(e.date)}, ${e.start_time.replace(":", ".")}`, "calendar"], ["Durasi", `${e.duration_min} menit`, "clock"], ["Peserta", `${e.student_count} siswa`, "users"], ["Pengawas", e.supervisor?.name ?? "—", "shield"]].map(([k, v, i]) => <div key={k} className="flex gap-3"><div className="grid size-9 shrink-0 place-items-center rounded-md bg-slate-50 text-slate-500"><Icon name={i as IconName} size={17} /></div><div><p className="text-xs text-slate-400">{k}</p><p className="mt-1 text-sm font-semibold text-slate-800">{v}</p></div></div>)}</div>
      </div>
      <div className="mt-6 border-b border-slate-200"><div className="flex gap-7 overflow-x-auto">{["Ringkasan", "Peserta", "Pemantauan", "Laporan"].map((x) => <button key={x} onClick={() => setTab(x)} className={`whitespace-nowrap border-b-2 px-1 pb-3 text-sm font-semibold ${tab === x ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500"}`}>{x}</button>)}</div></div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_.8fr]"><section className="rounded-md border border-slate-200 bg-white p-6"><h2 className="font-bold text-slate-900">{tab}</h2>{tab === "Ringkasan" ? <><p className="mt-3 text-sm leading-7 text-slate-600">{e.description} Seluruh peserta wajib mengaktifkan kamera dan mikrofon selama sesi.</p><div className="mt-6 rounded-md bg-blue-50 p-4"><div className="flex gap-3"><span className="text-blue-700"><Icon name="shield" size={19} /></span><div><p className="text-sm font-bold text-blue-900">Pemantauan bertanggung jawab</p><p className="mt-1 text-xs leading-5 text-blue-800">AI hanya memberikan Indikasi dan bukti pendukung. Pengawas meninjau bukti sebelum menentukan keputusan.</p></div></div></div></> : tab === "Peserta" ? <div className="mt-4 divide-y divide-slate-100">{st.map((s) => <div key={s.id} className="flex items-center justify-between py-2.5 text-sm"><span className="font-semibold text-slate-800">{s.name}</span><span className="text-xs text-slate-500">NIS {s.nis ?? "—"}</span></div>)}</div> : <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 p-10 text-center"><Icon name={tab === "Laporan" ? "report" : "monitor"} size={28} /><p className="mt-3 text-sm font-semibold text-slate-700">{tab === "Laporan" ? (e.status === "Selesai" ? "Laporan siap ditinjau" : "Laporan lengkap tersedia setelah ujian selesai") : e.monitoring_active ? `Pemantauan AI aktif (${e.analysis_source === "livekit" ? "OpenVidu" : "frame browser"})` : "Pemantauan AI belum dimulai"}</p><Button variant="secondary" className="mt-4" onClick={() => go(tab === "Laporan" ? "report" : "monitor")}>{tab === "Laporan" ? "Buka laporan" : "Buka pemantauan"}</Button></div>}</section>
        <aside className="rounded-md border border-slate-200 bg-white p-6"><h2 className="font-bold text-slate-900">Kesiapan sesi</h2><div className="mt-5 space-y-4">{[["Peserta terdaftar", String(e.student_count), "green"], ["Sudah terhubung", String(joined), "green"], ["Masalah perangkat", String(deviceIssues), deviceIssues ? "amber" : "gray"], ["Belum bergabung", String(Math.max(0, e.student_count - joined)), "gray"]].map(([k, v, t]) => <div key={k} className="flex items-center justify-between"><span className="text-sm text-slate-500">{k}</span><Badge tone={t as "green" | "amber" | "gray"}>{v}</Badge></div>)}</div>{canMonitor && <Button variant="secondary" className="mt-6 w-full" onClick={() => go("waiting")}>Periksa ruang tunggu</Button>}</aside></div>
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
  const minsToStart = exam ? Math.round((examWindow(exam).start.getTime() - Date.now()) / 60000) : 0;
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
    <button onClick={() => go("sessions")} className="mb-5 flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-800"><Icon name="arrow" size={18} />Kembali ke Daftar Ujian</button>
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
  return <header className="flex h-18 items-center justify-between border-b border-slate-200 bg-white px-5 sm:px-10"><Logo /><div className="hidden items-center gap-3 sm:flex"><div className="grid size-8 place-items-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">{initials(user?.name ?? "")}</div><div><p className="text-sm font-bold text-slate-800">{user?.name}</p><p className="text-xs text-slate-500">NIS {user?.nis ?? "—"}</p></div></div>{step && <div className="text-xs font-semibold text-slate-500 sm:hidden">Langkah {step} dari 2</div>}</header>;
}

function Consent({ go }: { go: (s: Screen) => void }) {
  const [agreed, setAgreed] = useState(false);
  const [audio, setAudio] = useState(false);          // optional, off by default
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { examId } = useSel();
  const submit = async () => {
    if (!examId) return setError("Pilih ujian dari halaman Ujian Saya terlebih dahulu.");
    setBusy(true);
    try { await api.consent(examId, audio); go("exam"); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return <div className="min-h-screen bg-slate-50"><StudentHeader step={2} /><main className="mx-auto max-w-3xl p-5 py-10 sm:py-16">
    <div className="mb-8 flex items-center justify-center gap-2">{[1, 2].map((n) => <div key={n} className="flex items-center gap-2">{n > 1 && <div className="h-px w-12 bg-blue-200" />}<div className="grid size-8 place-items-center rounded-full bg-blue-700 text-xs font-bold text-white">{n === 1 ? <Icon name="check" size={14} /> : n}</div></div>)}</div>
    <section className="rounded-md border border-slate-200 bg-white p-6 sm:p-10">
      <div className="grid size-12 place-items-center rounded-md bg-blue-50 text-blue-700"><Icon name="shield" size={25} /></div><p className="mt-6 text-xs font-bold uppercase tracking-widest text-blue-700">Langkah 2 dari 2</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">Persetujuan Perekaman</h1><p className="mt-3 leading-7 text-slate-600">Untuk mendukung pengawasan ujian, video kamera Anda dianalisis oleh AI selama sesi berlangsung untuk memberikan Indikasi kepada pengawas. Kamera dan mikrofon dapat disiarkan langsung ke pengawas.</p>
      <div className="my-7 grid gap-3 sm:grid-cols-2">{[["video", "Data yang diproses", "Gambar kamera selama ujian, status kamera/mikrofon, dan kualitas koneksi."], ["monitor", "Analisis AI", "Keberadaan wajah, jumlah orang, arah kepala, gerak mulut, dan objek menyerupai ponsel. Suara hanya dianalisis jika Anda menyetujui pilihan di bawah."], ["shield", "Tujuan penggunaan", "Mendukung pengawas dalam meninjau jalannya ujian secara bertanggung jawab."], ["users", "Akses & masa simpan", "Hanya pengawas berwenang yang dapat membuka bukti. Bukti berupa beberapa cuplikan gambar disimpan maksimal 1 hari (24 jam); video penuh dan audio tidak pernah direkam atau disimpan."]].map(([icon, title, copy]) => <div key={title} className="rounded-md bg-slate-50 p-4"><div className="flex items-center gap-2 font-bold text-slate-800"><Icon name={icon as IconName} size={18} />{title}</div><p className="mt-2 text-sm leading-6 text-slate-500">{copy}</p></div>)}</div>
      <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900"><strong>Perlu diketahui:</strong> AI hanya memberikan Indikasi. Setiap keputusan akhir selalu dibuat oleh pengawas setelah meninjau bukti. Video yang gelap atau buram dicatat sebagai "tidak dapat dianalisis", bukan pelanggaran.</div>
      <label className="mt-7 flex cursor-pointer items-start gap-3 rounded-md border border-slate-200 p-4 transition hover:bg-slate-50"><input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-0.5 size-5 rounded border-slate-300 accent-blue-600" /><span><span className="block text-sm font-bold text-slate-800">Saya telah membaca dan menyetujui pemberitahuan perekaman dan analisis data.</span><span className="mt-1 block text-xs leading-5 text-slate-500">Persetujuan diperlukan untuk mengikuti ujian ini.</span></span></label>
      <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-md border border-slate-200 p-4 transition hover:bg-slate-50"><input type="checkbox" role="switch" aria-checked={audio} checked={audio} onChange={(e) => setAudio(e.target.checked)} className="mt-0.5 size-5 rounded border-slate-300 accent-blue-600" /><span><span className="block text-sm font-bold text-slate-800">Opsional: saya setuju suara mikrofon dianalisis di perangkat saya.</span><span className="mt-1 block text-xs leading-5 text-slate-500">Model AI di browser ini menilai apakah terdengar suara bicara, bisikan, atau musik/TV. Yang dikirim ke EduAI hanya tiga angka skor; audio tidak direkam, tidak disimpan, dan tidak dikirim. Jika terdengar suara bicara saat mulut Anda tampak diam, pengawas menerima indikasi untuk ditinjau, bukan keputusan pelanggaran. Suara orang lain di sekitar Anda juga ikut dinilai, jadi beri tahu mereka. Ujian tetap dapat diikuti tanpa pilihan ini.</span></span></label>
      {error && <p role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">{error}</p>}
      <div className="mt-7 flex justify-end"><Button disabled={!agreed || busy} onClick={submit}>Setuju & Masuk Ujian <Icon name="chevron" size={17} /></Button></div>
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
  useEffect(() => { if (level > 0.08) setHeardMic(true); }, [level]);
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
  const [error, setError] = useState("");
  const [mon, setMon] = useState<MonitoringInfo | null>(null);
  const [examStatus, setExamStatus] = useState<string>("");
  const [conn, setConn] = useState<"baik" | "lemah" | "terputus">("baik");
  const [camOn, setCamOn] = useState(true);
  const [micOn, setMicOn] = useState(true);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [now, setNow] = useState(Date.now());
  const [uploadInfo, setUploadInfo] = useState("");
  const videoRef = useVideo(stream);
  const uploader = useRef<FrameUploader | null>(null);
  const speech = useRef<SpeechScorer | null>(null);
  const [audioInfo, setAudioInfo] = useState("");
  const isStudent = role === "Siswa";

  useEffect(() => {
    if (!isStudent) return;
    if (!examId) { setError("Pilih ujian dari halaman Ujian Saya terlebih dahulu."); return; }
    let m: StudentMedia | null = null;
    let cancelled = false;
    (async () => {
      try {
        const j = await api.join(examId);
        if (cancelled) return;
        setExam(j.exam); setMon(j.monitoring); setExamStatus(j.exam.status);
        m = await startStudentMedia(j);
        if (cancelled) { await m.stop(); return; }
        setMedia(m); setStream(m.stream);
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : mediaErrorMessage(e));
      }
    })();
    return () => { cancelled = true; uploader.current?.stop(); uploader.current = null; speech.current?.stop(); speech.current = null; void m?.stop(); void api.leave(examId).catch(() => undefined); };
  }, [examId, isStudent]);

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
        await api.presence(examId, { camera_on: media.cameraOn(), mic_on: media.micOn(), connection: c, rtt_ms: Math.round(rtt) });
      } catch { setConn("terputus"); }
    };
    void beat();
    const t = window.setInterval(() => void beat(), 5000);
    return () => window.clearInterval(t);
  }, [media, examId]);

  // Frame upload: always in browser-frame mode; in OpenVidu-worker mode only as a fallback when this
  // browser is not connected to the OpenVidu room (the worker cannot see this student's camera then).
  useEffect(() => {
    if (!media || !examId || !videoRef.current) return;
    const want = !!mon?.active && examStatus === "Sedang Berlangsung"
      && (mon.source === "browser" || (mon.source === "livekit" && !media.room));
    if (want) {
      if (!uploader.current) uploader.current = new FrameUploader(examId, videoRef.current, () => media.cameraOn());
      uploader.current.start(mon!);
    } else uploader.current?.stop();
  }, [media, examId, mon?.active, mon?.source, mon?.upload_fps, examStatus, videoRef, media?.room]);

  // optional speech-sound scores (only with the student's audio consent; browser frame path only)
  const audioWanted = !!media && !!mon?.active && mon.source === "browser" && examStatus === "Sedang Berlangsung"
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
        : <div className="relative text-center"><div className="mx-auto grid size-28 place-items-center rounded-full bg-slate-800 text-3xl font-bold text-slate-200 ring-1 ring-slate-700">{initials(exam?.supervisor?.name ?? "P")}</div><p className="mt-5 font-semibold">{exam?.supervisor?.name ?? "Pengawas"} • Pengawas</p><p className="mt-1 text-sm text-slate-400">{ended ? "Ujian telah selesai. Anda dapat keluar dari ruang ujian." : media ? "Ujian sedang berlangsung" : "Menyiapkan kamera..."}</p>{media?.livekitError && <p className="mx-auto mt-4 max-w-md rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-200">{media.livekitError}</p>}{uploadInfo && <p className="mx-auto mt-2 max-w-md rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-200">Pengiriman frame tertunda: {uploadInfo}</p>}{(audioInfo || audioBlocked) && <p className="mx-auto mt-2 max-w-md text-xs text-slate-400">{audioInfo || audioBlocked}</p>}</div>}
      <div className="absolute bottom-5 right-5 w-44 overflow-hidden rounded-md border border-white/20 bg-slate-800 sm:w-56"><div className="relative flex aspect-video items-center justify-center bg-slate-800">{stream && camOn ? <video ref={videoRef} muted playsInline className="absolute inset-0 size-full -scale-x-100 object-cover" /> : <><video ref={videoRef} muted playsInline className="hidden" /><div className="grid size-14 place-items-center rounded-full bg-white/10 font-bold">{initials(user?.name ?? "")}</div></>}</div><div className="flex items-center justify-between px-3 py-2 text-xs"><span>{user?.name}</span><span className={micOn ? "text-emerald-400" : "text-red-400"}><Icon name="mic" size={14} /></span></div></div>
    </main>
    <footer className="flex h-20 items-center justify-between border-t border-white/10 px-5 sm:px-8"><div className={`flex items-center gap-2 text-xs ${conn === "baik" ? "text-emerald-400" : conn === "lemah" ? "text-amber-300" : "text-red-400"}`}><span className={`size-2 rounded-full ${conn === "baik" ? "bg-emerald-400" : conn === "lemah" ? "bg-amber-300" : "bg-red-400"}`} />{conn === "baik" ? "Koneksi stabil" : conn === "lemah" ? "Koneksi lambat" : "Koneksi terputus"}</div><div className="flex gap-3"><button onClick={toggleMic} aria-label={micOn ? "Matikan mikrofon" : "Nyalakan mikrofon"} className={`grid size-11 place-items-center rounded-full ${micOn ? "bg-white/10" : "bg-red-600"}`}><Icon name="mic" /></button><button onClick={toggleCam} aria-label={camOn ? "Matikan kamera" : "Nyalakan kamera"} className={`grid size-11 place-items-center rounded-full ${camOn ? "bg-white/10" : "bg-red-600"}`}><Icon name="camera" /></button></div><div className="hidden text-xs text-slate-500 sm:block">{mon?.active ? "Pemantauan AI aktif" : "Pemantauan AI belum dimulai"}{media?.room ? " · Siaran ke pengawas aktif" : ""}</div></footer>
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

function studentStatus(s: StudentRow) {
  const p = s.presence;
  if (!p?.joined) return "Belum bergabung";
  if (!p.online) return "Terputus";
  if (p.camera_on === false) return "Kamera mati";
  if (p.mic_on === false) return "Mikrofon mati";
  return "Hadir";
}

function Monitoring({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const { setStudentId, setEventId } = useSel();
  const { exam, reload: reloadExam } = useCurrentExam();
  const examId = exam?.id ?? null;
  const students = usePoll(() => (examId ? api.students(examId) : Promise.resolve([] as StudentRow[])), [examId], 3000);
  const events = usePoll(() => (examId ? api.examEvents(examId, { limit: 30 }) : Promise.resolve({ server_time: "", events: [] as AIEvent[] })), [examId], 3000);
  const mon = usePoll(() => (examId ? api.monitoring(examId) : Promise.reject(new Error(""))), [examId], 5000);
  const video = useExamVideoRoom(examId, !!examId && exam?.status === "Sedang Berlangsung");
  const [filter, setFilter] = useState("Semua");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [actionMsg, setActionMsg] = useState("");
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t); }, []);
  const rows = students.data ?? [];
  const m: MonitoringState | null = mon.data;
  const needsAttention = (s: StudentRow) => (s.counts?.unreviewed ?? 0) > 0 || s.ai?.state === "indication";
  const connIssue = (s: StudentRow) => ["Terputus", "Kamera mati", "Mikrofon mati"].includes(studentStatus(s));
  const attention = rows.filter(needsAttention).length;
  const cannot = rows.filter((s) => s.ai?.state === "cannot_analyze").length;
  const list = rows.filter((s) => (filter === "Semua" || (filter === "Perlu perhatian" && needsAttention(s)) || (filter === "Normal" && !needsAttention(s) && studentStatus(s) === "Hadir") || (filter === "Masalah koneksi" && connIssue(s)) || (filter === "Tidak dapat dianalisis" && s.ai?.state === "cannot_analyze")) && s.name.toLowerCase().includes(query.toLowerCase()));
  const online = rows.filter((s) => s.presence?.online).length;
  const indTotal = rows.reduce((a, s) => a + (s.counts?.session_indications ?? s.counts?.indications ?? 0), 0);
  const stats: [string, string, IconName, string][] = [["Total siswa", String(rows.length), "users", "Terdaftar"], ["Sedang online", String(online), "wifi", rows.length ? `${Math.round((online / rows.length) * 100)}% terhubung` : "—"], ["Perlu perhatian", String(attention), "bell", `${cannot} tak terbaca`], ["Indikasi tercatat", String(indTotal), "report", "Sesi ini"]];
  const ctl = (icon: IconName, off: boolean) => <span className={`grid size-6 place-items-center rounded text-white ${off ? "bg-red-600" : "bg-slate-900/70"}`}><Icon name={icon} size={13} /></span>;
  const canControl = MONITOR_ROLES.includes(role);
  const notify = useContext(NotifyContext);
  const toggleMonitoring = async () => {
    if (!examId || !m) return;
    try {
      if (m.active) { await api.stopMonitoring(examId); setActionMsg("Pemantauan AI dihentikan. Indikasi yang masih terbuka ditutup."); }
      else { const r = await api.startMonitoring(examId); setActionMsg(r.note ?? `Pemantauan AI dimulai (${r.source === "livekit" ? "OpenVidu worker" : "frame dari browser siswa"}).`); }
      void mon.reload(); void reloadExam();
    } catch (e) { setActionMsg((e as Error).message); }
  };
  const aiOffline = !!m && m.active && !m.ai.available && m.source === "browser";
  const workerDown = !!m && m.active && m.source === "livekit" && !m.worker.alive && (!m.started_at || now - new Date(m.started_at).getTime() > 15000);
  const view: "active" | "empty" | "loading" | "offline" = students.loading && !students.data ? "loading" : aiOffline ? "offline" : rows.length === 0 ? "empty" : "active";
  const exp = rows.find((s) => s.id === expanded);
  const openStudent = (id: number) => { setStudentId(id); go("student-detail"); };
  return <AppShell active="monitor" go={go} title="Pemantauan Langsung"><main className="p-4 sm:p-8">
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold text-slate-900">Pemantauan siswa</h1><p className="mt-1 text-sm text-slate-500">{exam ? `${exam.class_name} · ${exam.subject} · ${fmtDate(exam.date)}` : "Memuat sesi..."}</p></div><div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2.5"><span className={`size-2.5 rounded-full ${m?.active ? "animate-pulse bg-red-500" : "bg-slate-300"}`} /><div><p className="text-sm font-semibold text-slate-900">{exam?.name ?? "—"}</p><p className="text-xs text-slate-500">{exam ? `${exam.status} · sisa ${remaining(exam, now)}` : ""} · AI {m?.active ? (m.source === "livekit" ? "aktif (OpenVidu)" : "aktif (frame browser)") : "belum aktif"}</p></div>{canControl && examId && <Button variant="ghost" className="ml-2 h-9" onClick={() => notify.openSummary(examId)}>Ringkasan</Button>}{canControl && exam?.status === "Sedang Berlangsung" && <Button variant={m?.active ? "secondary" : "primary"} className="ml-2 h-9" onClick={toggleMonitoring}>{m?.active ? "Hentikan AI" : "Mulai AI"}</Button>}</div></div>
    {actionMsg && <Notice tone="blue">{actionMsg}</Notice>}
    {students.error && <Notice tone="red">{students.error}</Notice>}
    {workerDown && <Notice>Worker AI OpenVidu belum mengirim heartbeat{m?.worker.process_running ? "" : " (proses worker berhenti)"}. Pastikan server OpenVidu berjalan dan dapat dihubungi backend; sampai itu, status AI siswa tampil "Analisis AI terputus". {canControl && <button className="ml-1 font-semibold underline" onClick={async () => { if (!examId) return; try { await api.startMonitoring(examId, "browser"); setActionMsg("Analisis dialihkan ke frame dari browser siswa."); void mon.reload(); } catch (e) { setActionMsg((e as Error).message); } }}>Pakai frame dari browser</button>}</Notice>}
    {!video.connected && video.reason && <Notice tone="blue">Video langsung tidak ditampilkan: {video.reason}. Status kamera dan hasil AI tetap diperbarui.</Notice>}
    <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{stats.map(([label, value, icon, note]) => <div key={label} className="flex items-center gap-4 rounded-lg border border-slate-200 bg-white p-4"><div className="grid size-11 place-items-center rounded-lg bg-blue-50 text-blue-700"><Icon name={icon} size={21} /></div><div className="min-w-0 flex-1"><p className="text-xs text-slate-500">{label}</p><p className="text-2xl font-semibold leading-8 text-slate-900">{value}</p></div><span className="whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">{note}</span></div>)}</div>
    <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
      <section>
        <div className="mb-4 flex flex-wrap items-center gap-3"><div className="flex gap-1 overflow-x-auto rounded-lg bg-slate-200/70 p-1">{["Semua", "Normal", "Perlu perhatian", "Tidak dapat dianalisis", "Masalah koneksi"].map((t) => <button key={t} onClick={() => setFilter(t)} className={`flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ${filter === t ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"}`}>{t}{t === "Perlu perhatian" && <span className="rounded-full bg-amber-100 px-1.5 text-[11px] text-amber-700">{attention}</span>}</button>)}</div>
          <div className="relative ml-auto min-w-52 flex-1 sm:max-w-xs"><span className="absolute left-3 top-2.5 text-slate-400"><Icon name="search" size={17} /></span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Cari nama siswa" className="h-10 w-full rounded-md border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none focus:border-blue-500" /></div></div>
        {view !== "active" ? <div className="flex min-h-[420px] rounded-lg border border-slate-200 bg-white"><MonitorState state={view} reason={m?.ai.reason} onRetry={() => void mon.reload()} /></div> : list.length === 0 ? <div className="rounded-lg border border-slate-200 bg-white p-12 text-center text-sm text-slate-500">Tidak ada siswa yang cocok dengan filter ini.</div> : <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">{list.map((s, i) => {
          const st = studentStatus(s);
          const off = st === "Kamera mati" || st === "Terputus" || st === "Belum bergabung";
          const flagged = needsAttention(s);
          const ai = s.ai?.state ?? "no_data";
          const track = video.tracks[s.id];
          return <article key={s.id} className={`overflow-hidden rounded-lg border bg-white ${flagged ? "border-amber-300" : ai === "cannot_analyze" ? "border-slate-400" : "border-slate-200"}`}>
            <div className={`relative aspect-video ${off ? "bg-slate-800" : ["bg-blue-100", "bg-slate-200", "bg-blue-50", "bg-slate-300"][i % 4]}`}>
              {off ? <div className="absolute inset-0 grid place-items-center text-center text-slate-300"><div><Icon name="wifi" size={22} /><p className="mt-1 text-xs">{st === "Terputus" ? "Terputus / menyambung ulang" : st === "Belum bergabung" ? "Belum bergabung" : "Kamera dimatikan"}</p></div></div> : track ? <LiveVideo track={track} /> : <Silhouette />}
              {!off && <span className="absolute left-2 top-2 flex items-center gap-1.5 rounded bg-slate-900/75 px-2 py-0.5 text-[11px] font-medium text-white"><span className={`size-1.5 rounded-full ${track ? "bg-red-500" : "bg-slate-400"}`} />{track ? "LIVE" : "Online"}</span>}
              <div className="absolute right-2 top-2 flex gap-1">{ctl("mic", s.presence?.mic_on === false)}{ctl("camera", s.presence?.camera_on === false)}{ctl("wifi", st === "Terputus")}</div>
              {ai === "indication" ? <div className="absolute inset-x-0 bottom-0 flex items-center gap-2 bg-amber-600/95 px-3 py-1.5 text-xs font-semibold text-white"><Icon name="bell" size={14} />{s.last_indication?.status === "open" ? s.last_indication.label ?? "Indikasi" : "Indikasi"} · sedang berlangsung</div>
                : flagged ? <div className="absolute inset-x-0 bottom-0 flex items-center gap-2 bg-amber-50/95 px-3 py-1.5 text-xs font-medium text-amber-900"><Icon name="report" size={14} />{(() => { const li = s.last_indication; const txt = `${s.counts?.unreviewed ?? 0} belum ditinjau${li?.current_session === false ? " · sesi sebelumnya" : ""}${li ? ` · terakhir ${li.label ?? li.indicator} ${fmtTime(li.start_ts)}` : ""}`; return <span className="truncate" title={txt}>{txt}</span>; })()}</div>
                : ai === "cannot_analyze" && !off ? <div className="absolute inset-x-0 bottom-0 bg-slate-700/90 px-3 py-1.5 text-xs font-semibold text-white">Tidak dapat dianalisis{s.ai?.reason ? ` · ${FRAME_REASON[s.ai.reason] ?? s.ai.reason}` : ""}</div> : null}
            </div>
            <div className="p-3.5"><div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{s.name}</p><p className="text-xs text-slate-400">NIS {s.nis ?? "—"} · AI: {STATE_LABEL[ai]}</p></div><Badge tone={s.counts?.unreviewed ? "amber" : st === "Hadir" ? stateTone(ai) : "gray"}>{s.counts?.unreviewed ? `${s.counts.unreviewed} perlu ditinjau` : st === "Hadir" ? STATE_LABEL[ai] : st}</Badge></div>
              <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3 text-xs"><button onClick={() => setExpanded(s.id)} className="font-semibold text-slate-600 hover:text-slate-900">Perbesar</button><button onClick={() => openStudent(s.id)} className="flex items-center gap-1 font-semibold text-blue-700">Buka pemantauan <Icon name="chevron" size={14} /></button></div></div>
          </article>;
        })}</div>}
      </section>
      <aside className="h-fit rounded-lg border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-4"><div><h2 className="font-semibold text-slate-900">Aktivitas terbaru</h2><p className="text-xs text-slate-500">Diperbarui setiap 3 detik</p></div><button onClick={() => go("indications")} className="text-xs font-semibold text-blue-700">Lihat semua</button></div>
        <div className="max-h-[560px] divide-y divide-slate-100 overflow-y-auto">{aiOffline ? <p className="p-5 text-sm text-amber-800">AI belum tersedia. Daftar indikasi akan terisi lagi setelah layanan tersambung.</p> : (events.data?.events ?? []).length === 0 ? <p className="p-5 text-sm text-slate-500">Belum ada kejadian dari AI pada sesi ini.</p> : (events.data?.events ?? []).map((e) => { const ind = e.category === "indication"; return <button key={e.event_id} onClick={() => { if (ind) { setEventId(e.event_id); go("detail"); } else openStudent(e.student_id); }} className="flex w-full items-start gap-3 p-4 text-left hover:bg-slate-50"><span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-md ${ind ? "bg-amber-50 text-amber-600" : "bg-slate-100 text-slate-500"}`}><Icon name={ind ? "bell" : "camera"} size={16} /></span><span className="min-w-0 flex-1"><span className="block text-sm font-medium text-slate-800">{eventTitle(e)}</span><span className="text-xs text-slate-500">{e.student?.name} · {fmtTime(e.start_ts)} · {e.status === "open" ? "berlangsung" : fmtDuration(e.duration_s)}</span></span>{ind && !e.review_status && <span className="mt-2 size-2 rounded-full bg-blue-600" />}</button>; })}</div>
        <div className="m-4 flex gap-3 rounded-md bg-blue-50 p-3.5 text-xs leading-5 text-blue-900"><Icon name="shield" size={17} /><p><strong className="block font-semibold">Perlu verifikasi manusia</strong>Indikasi dari AI hanya membantu peninjauan dan tidak menentukan hasil secara otomatis. "Tidak dapat dianalisis" berarti kualitas video kurang, bukan pelanggaran.</p></div>
      </aside>
    </div>
    {exp && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/80 p-6"><section role="dialog" aria-modal="true" className="w-full max-w-4xl overflow-hidden rounded-lg border border-slate-700 bg-slate-900"><div className="flex items-center justify-between border-b border-white/10 p-4 text-white"><div><p className="font-semibold">{exp.name}</p><p className="text-xs text-slate-400">{video.tracks[exp.id] ? "Siaran langsung · OpenVidu" : "Video langsung tidak tersedia"} · AI: {STATE_LABEL[exp.ai?.state ?? "no_data"]}</p></div><button onClick={() => setExpanded(null)} aria-label="Tutup"><Icon name="close" /></button></div><div className="relative aspect-video bg-slate-800">{video.tracks[exp.id] ? <LiveVideo track={video.tracks[exp.id]} className="object-contain" /> : <Silhouette />}</div><div className="flex justify-end gap-2 border-t border-white/10 p-4"><Button variant="secondary" onClick={() => { setExpanded(null); openStudent(exp.id); }}>Detail siswa</Button><Button onClick={() => setExpanded(null)}>Tutup</Button></div></section></div>}
  </main></AppShell>;
}

function StudentMonitoringDetail({ go }: { go: (s: Screen) => void }) {
  const { examId, studentId, setEventId } = useSel();
  const students = usePoll(() => (examId ? api.students(examId) : Promise.resolve([] as StudentRow[])), [examId], 3000);
  const timeline = usePoll(() => (examId && studentId ? api.timeline(examId, studentId) : Promise.resolve([] as TimelineItem[])), [examId, studentId], 5000);
  const exam = usePoll(() => (examId ? api.exam(examId) : Promise.reject(new Error("Pilih sesi"))), [examId]);
  const video = useExamVideoRoom(examId, exam.data?.status === "Sedang Berlangsung");
  const s = students.data?.find((x) => x.id === studentId);
  const items = (timeline.data ?? []).slice().reverse();
  const st = s ? studentStatus(s) : "—";
  const openEvent = (id?: string) => { if (id) { setEventId(id); go("detail"); } };
  const lastInd = items.find((i) => i.kind === "indication");
  return <AppShell active="student-detail" go={go} title="Detail Pemantauan Siswa"><main className="p-4 sm:p-8">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><button onClick={() => go("monitor")} className="flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-800"><Icon name="arrow" size={18} />Kembali ke pemantauan</button><Button variant="secondary" onClick={() => go("timeline")}>Lihat linimasa lengkap</Button></div>
    {!s ? <Notice tone={students.loading ? "blue" : "red"}>{students.loading ? "Memuat..." : students.error || "Pilih siswa dari halaman Monitoring."}</Notice> : <>
      <div className="mb-6 flex flex-col justify-between gap-5 rounded-md border border-slate-200 bg-white p-5 sm:flex-row sm:items-center"><div className="flex items-center gap-4"><div className="grid size-14 place-items-center rounded-full bg-amber-100 font-bold text-amber-800">{initials(s.name)}</div><div><div className="flex items-center gap-2"><h1 className="text-xl font-bold text-slate-900">{s.name}</h1><Badge tone={s.counts?.unreviewed ? "amber" : stateTone(s.ai?.state)}>{s.counts?.unreviewed ? "Perlu perhatian" : STATE_LABEL[s.ai?.state ?? "no_data"]}</Badge></div><p className="mt-1 text-sm text-slate-500">NIS {s.nis ?? "—"} • {s.class_name}</p></div></div><div className="flex gap-5 text-center"><div><p className={`text-sm font-bold ${s.presence?.online ? "text-emerald-600" : "text-slate-500"}`}>{s.presence?.online ? (s.presence.connection === "baik" ? "Stabil" : s.presence.connection) : "Offline"}</p><p className="text-[10px] text-slate-400">Koneksi</p></div><div><p className="text-sm font-bold text-slate-700">{s.presence?.camera_on ? "Aktif" : "Mati"}</p><p className="text-[10px] text-slate-400">Kamera</p></div><div><p className="text-sm font-bold text-slate-700">{s.presence?.mic_on ? "Aktif" : "Mati"}</p><p className="text-[10px] text-slate-400">Mikrofon</p></div><div title={`Analisis suara di perangkat siswa (hanya skor, tanpa audio)${s.audio?.reason ? `. ${AUDIO_REASON[s.audio.reason]?.[1] ?? s.audio.reason}` : ""}`}><p className="text-sm font-bold text-slate-700">{!s.audio?.consented ? "Tidak disetujui" : s.audio.active ? "Aktif" : "Tidak aktif"}</p><p className="text-[10px] text-slate-400">Analisis suara</p>{s.audio?.consented && !s.audio.active && s.audio.reason && <p className="text-[10px] font-medium text-amber-700">{AUDIO_REASON[s.audio.reason]?.[0] ?? s.audio.reason}</p>}</div></div></div>
      <div className="grid gap-6 xl:grid-cols-[1.45fr_.8fr]"><div className="space-y-6"><section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="relative flex aspect-video items-center justify-center bg-slate-800">{video.tracks[s.id] ? <LiveVideo track={video.tracks[s.id]} className="object-contain" /> : <div className="grid size-24 place-items-center rounded-full bg-white/10 text-2xl font-bold text-white ring-1 ring-white/20">{initials(s.name)}</div>}<div className="absolute bottom-4 left-4 flex items-center gap-2 rounded-md bg-slate-900/70 px-3 py-2 text-xs text-white"><span className={`size-2 rounded-full ${video.tracks[s.id] ? "bg-emerald-400" : "bg-slate-400"}`} />{video.tracks[s.id] ? "Siaran langsung • OpenVidu" : video.reason ? "Video langsung tidak tersedia" : "Menunggu video siswa"}</div></div><div className="flex items-center justify-between p-4"><p className="text-sm font-semibold text-slate-700">{exam.data?.name}</p><div className="flex gap-2 text-slate-500"><Icon name="mic" size={17} /><Icon name="camera" size={17} /><Icon name="wifi" size={17} /></div></div></section>
        <section className="rounded-md border border-slate-200 bg-white p-6"><div className="flex items-center justify-between"><div><h2 className="font-bold text-slate-900">Aktivitas Siswa</h2><p className="mt-1 text-xs text-slate-500">Linimasa perangkat dan Indikasi selama sesi.</p></div><Badge tone={s.counts?.unreviewed ? "amber" : "gray"}>{s.counts?.unreviewed ?? 0} belum ditinjau</Badge></div><div className="mt-5 divide-y divide-slate-100">{items.slice(0, 8).map((it, idx) => <div key={it.ts + idx} className="flex items-center gap-4 py-3"><span className={`size-2 rounded-full ${it.kind === "indication" ? "bg-amber-500" : it.kind === "cannot_analyze" ? "bg-slate-400" : it.kind === "review" ? "bg-blue-500" : "bg-emerald-500"}`} /><span className="w-20 text-xs font-semibold text-slate-500">{fmtTime(it.ts)}</span><p className="flex-1 text-sm font-semibold text-slate-800">{it.title}{it.kind === "indication" && it.status === "open" ? " (berlangsung)" : ""}</p>{it.kind === "indication" && <button onClick={() => openEvent(it.event_id)} className="text-xs font-bold text-blue-700">Lihat Evidence</button>}</div>)}{items.length === 0 && <p className="py-3 text-sm text-slate-500">Belum ada aktivitas.</p>}</div><div className="mt-5 flex gap-3 border-t border-slate-100 pt-5"><Button onClick={() => go("indications")}>Lihat Indikasi</Button><Button variant="secondary" disabled={!lastInd} onClick={() => openEvent(lastInd?.event_id)}>Lihat Evidence</Button></div></section></div>
        <aside className="space-y-6"><section className="rounded-md border border-slate-200 bg-white p-5"><h2 className="font-bold text-slate-900">Status pemantauan</h2><div className="mt-5 space-y-4">{[["Status kehadiran", st], ["Waktu masuk", fmtTime(s.presence?.joined_at)], ["Koneksi", s.presence?.online ? `${s.presence.rtt_ms ? `${Math.round(s.presence.rtt_ms)} ms • ` : ""}${s.presence.connection ?? ""}` : "Offline"], ["Status AI", STATE_LABEL[s.ai?.state ?? "no_data"]], ["Kualitas video", s.ai?.frame_status === "cannot_analyze" ? `Tidak dapat dianalisis (${FRAME_REASON[s.ai.reason ?? ""] ?? s.ai.reason})` : s.ai?.frame_status === "analyzed" ? "Dapat dianalisis" : "—"], ["Jumlah Indikasi", `${s.counts?.indications ?? 0} kejadian`], ["Belum ditinjau", `${s.counts?.unreviewed ?? 0} Indikasi`]].map(([k, v], i) => <div key={k} className="flex justify-between gap-4 text-sm"><span className="text-slate-500">{k}</span><span className={`text-right font-semibold ${i === 0 && v === "Hadir" ? "text-emerald-700" : i === 6 && (s.counts?.unreviewed ?? 0) > 0 ? "text-amber-700" : "text-slate-800"}`}>{v}</span></div>)}</div></section><section className="rounded-md border border-blue-100 bg-blue-50 p-5"><div className="flex gap-3"><span className="text-blue-700"><Icon name="shield" size={19} /></span><div><p className="text-sm font-bold text-blue-900">Keputusan tetap pada pengawas</p><p className="mt-2 text-xs leading-5 text-blue-800">Periksa rekaman dan konteks sebelum membuat penilaian.</p></div></div></section></aside></div>
    </>}
  </main></AppShell>;
}

function MonitoringTimeline({ go }: { go: (s: Screen) => void }) {
  const { examId, studentId, setStudentId, setEventId } = useSel();
  const students = usePoll(() => (examId ? api.students(examId) : Promise.resolve([] as StudentRow[])), [examId]);
  const timeline = usePoll(() => (examId && studentId ? api.timeline(examId, studentId) : Promise.resolve([] as TimelineItem[])), [examId, studentId], 5000);
  const [kind, setKind] = useState("Semua jenis kejadian");
  const s = students.data?.find((x) => x.id === studentId);
  const kinds: Record<string, string> = { indication: "Indikasi", cannot_analyze: "Kualitas video", presence: "Koneksi", consent: "Persetujuan", review: "Tinjauan pengawas", note: "Catatan manual" };
  const tones: Record<string, string> = { indication: "amber", presence: "green", consent: "green", review: "blue", cannot_analyze: "gray", note: "gray" };
  const events = (timeline.data ?? []).filter((e) => kind === "Semua jenis kejadian" || kinds[e.kind] === kind);
  return <AppShell active="timeline" go={go} title="Linimasa Pemantauan"><main className="mx-auto max-w-5xl p-4 sm:p-8"><button onClick={() => go("student-detail")} className="mb-5 flex items-center gap-2 text-sm font-semibold text-slate-500"><Icon name="arrow" size={18} />Kembali ke detail siswa</button><PageTitle title="Linimasa Pemantauan" description={`${s?.name ?? "Pilih siswa"} • ${s ? "" : ""}`} />
    <div className="mb-6 flex flex-wrap gap-2 rounded-md border border-slate-200 bg-white p-4"><select value={studentId ?? ""} onChange={(e) => setStudentId(Number(e.target.value))} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600"><option value="" disabled>Pilih siswa</option>{(students.data ?? []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select><select value={kind} onChange={(e) => setKind(e.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600"><option>Semua jenis kejadian</option>{Object.values(kinds).map((k) => <option key={k}>{k}</option>)}</select></div>
    <section className="rounded-md border border-slate-200 bg-white p-6">{events.length === 0 ? <p className="text-sm text-slate-500">Belum ada kejadian.</p> : <div className="relative ml-3 border-l border-slate-200 pl-8">{events.map((ev, i) => { const tone = tones[ev.kind] ?? "gray"; return <div key={ev.ts + i} className={`${i < events.length - 1 ? "pb-8" : ""} relative`}><span className={`absolute -left-[39px] top-1 grid size-5 place-items-center rounded-full ring-4 ring-white ${tone === "amber" ? "bg-amber-500" : tone === "green" ? "bg-emerald-500" : tone === "blue" ? "bg-blue-500" : "bg-slate-400"}`} /><div className="flex flex-col justify-between gap-2 sm:flex-row"><div><p className="text-sm font-bold text-slate-800">{ev.title}</p><p className="mt-1 text-xs text-slate-500">{kinds[ev.kind] ?? ev.kind} • {s?.name}{ev.reason ? ` • ${ev.reason}` : ""}{ev.note ? ` • ${ev.note}` : ""}</p>{ev.kind === "indication" && <button onClick={() => { setEventId(ev.event_id!); go("detail"); }} className="mt-1 text-xs font-bold text-blue-700">Lihat evidence</button>}</div><span className="text-xs font-semibold text-slate-400">{fmtTime(ev.ts)} WIB</span></div></div>; })}</div>}</section>
  </main></AppShell>;
}

function EvidenceViewer({ event }: { event: AIEvent }) {
  const [meta, setMeta] = useState<{ frames: string[]; ts: number[]; key: number } | null>(null);
  const [error, setError] = useState("");
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!event.evidence_id) return;
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
  }, [event.evidence_id]);
  useEffect(() => {
    if (!playing || !meta) return;
    const t = window.setInterval(() => setIdx((i) => (i + 1) % meta.frames.length), 600);
    return () => window.clearInterval(t);
  }, [playing, meta]);
  const n = meta?.frames.length ?? 0;
  const pct = n > 1 ? (idx / (n - 1)) * 100 : 0;
  const keyPct = n > 1 && meta ? (meta.key / (n - 1)) * 100 : 0;
  return <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="relative grid aspect-video place-items-center bg-slate-900">{meta && n ? <img src={meta.frames[idx]} alt={`Cuplikan evidence ${idx + 1} dari ${n}`} className="absolute inset-0 size-full object-contain" /> : <div className="text-center text-slate-300"><div className="mx-auto grid size-16 place-items-center rounded-full bg-white/10 text-white"><Icon name="video" size={26} /></div><p className="mt-3 px-6 text-sm">{error || (event.evidence_id ? "Memuat evidence..." : event.status === "open" ? "Evidence disimpan setelah kejadian selesai direkam (±5 detik)." : "Evidence tidak tersedia (tidak tersimpan atau melewati masa simpan 24 jam).")}</p></div>}{n > 0 && <button onClick={() => setPlaying(!playing)} className="absolute bottom-5 left-5 grid size-10 place-items-center rounded-full bg-white text-slate-900" aria-label={playing ? "Pause" : "Play"}>{playing ? "Ⅱ" : "▶"}</button>}<span className="absolute right-4 top-4 rounded-md bg-slate-950/70 px-3 py-1.5 text-xs font-semibold text-white">{n ? `Cuplikan ${idx + 1}/${n}${meta && idx === meta.key ? " • saat indikasi" : ""}` : "Snapshot"}</span></div><div className="p-5"><div className="relative h-2 rounded-full bg-slate-200"><div className="h-2 rounded-full bg-blue-700" style={{ width: `${pct}%` }} />{n > 1 && <span className="absolute top-1/2 h-5 w-0.5 -translate-y-1/2 bg-amber-500" style={{ left: `${keyPct}%` }} />}</div><div className="mt-5 flex flex-wrap items-center justify-between gap-2"><span className="text-xs text-slate-500">{fmtTime(event.start_ts)} — {event.end_ts ? fmtTime(event.end_ts) : "berlangsung"}</span><div className="flex gap-2"><Button variant="secondary" className="h-9" disabled={!n} onClick={() => setIdx((i) => Math.max(0, i - 1))}>Sebelumnya</Button><Button variant="secondary" className="h-9" disabled={!n} onClick={() => setPlaying(true)}>Putar Evidence</Button><Button variant="ghost" className="h-9" disabled={!n} onClick={() => setIdx((i) => Math.min(n - 1, i + 1))}>Berikutnya</Button></div></div><p className="mt-3 text-[11px] text-slate-400">Evidence berupa cuplikan gambar beresolusi rendah (bukan video penuh, tanpa audio). Setiap akses dicatat di audit log.</p></div></section>;
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
    <button onClick={() => go("indications")} className="mb-5 flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-800"><Icon name="arrow" size={18} />Kembali ke Indikasi</button>
    <PageTitle eyebrow={e ? `Indikasi #${e.event_id.slice(0, 8).toUpperCase()}` : undefined} title="Detail Evidence" description="Evidence terkait Indikasi pada waktu kejadian." />
    {ev.error && !e && <Notice tone="red">{ev.error}</Notice>}
    {err && <Notice tone="red">{err}</Notice>}
    {e && <div className="grid gap-6 xl:grid-cols-[1.45fr_.75fr]"><div className="space-y-6">
      <EvidenceViewer event={e} />
      {isIndication && <section className="rounded-md border border-slate-200 bg-white p-6"><h2 className="font-bold text-slate-900">Validasi Pengawas</h2><p className="mt-1 text-sm text-slate-500">{readOnly ? "Hasil ini hanya dapat dilihat dan tidak dapat diubah oleh pihak sekolah." : "Pilih hasil berdasarkan evidence dan konteks kejadian."}</p>{!readOnly && <><div className="mt-5 grid gap-3 sm:grid-cols-3">{(["Valid", "Tidak Valid", "Perlu Tinjauan Lanjut"] as Decision[]).map((label) => <button key={label} onClick={() => setChoice(label)} className={`rounded-md border p-4 text-left ${choice === label ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100" : "border-slate-200 hover:bg-slate-50"}`}><span className="text-sm font-bold text-slate-800">{label}</span></button>)}</div><label className="mt-5 block"><span className="mb-2 block text-sm font-semibold text-slate-700">Catatan Pengawas</span><textarea value={note} onChange={(x) => setNote(x.target.value)} rows={4} className="w-full resize-none rounded-md border border-slate-200 p-3 text-sm outline-none focus:border-blue-500" placeholder="Tuliskan alasan dan konteks validasi..." /></label><div className="mt-4 flex justify-end"><Button onClick={saveValidation}>Simpan Validasi</Button></div></>}{saved && <div className="mt-5 rounded-md border border-emerald-200 bg-emerald-50 p-4"><div className="flex items-center justify-between"><p className="text-sm font-bold text-emerald-900">Validasi berhasil disimpan</p><Badge tone="green">{e.review_status}</Badge></div><p className="mt-2 text-xs text-emerald-800">{history.at(-1)?.reviewer} • baru saja • {history.at(-1)?.note || "Tidak ada catatan tambahan."}</p></div>}<div className="mt-6 border-t border-slate-100 pt-6"><h3 className="text-sm font-bold text-slate-900">Riwayat Validasi</h3><div className="mt-3 divide-y divide-slate-100">{history.length === 0 ? <p className="py-3 text-sm text-slate-500">Belum ada validasi.</p> : history.map((item, index) => <div key={`${item.created_at}-${index}`} className="grid gap-2 py-3 text-sm sm:grid-cols-[70px_1fr_180px]"><span className="text-slate-500">{fmtTime(item.created_at).slice(0, 5)}</span><div><p className="font-semibold text-slate-800">{item.reviewer}</p><p className="mt-1 text-xs text-slate-500">{item.note || "Tidak ada catatan tambahan."}</p></div><Badge tone={reviewTone(item.decision)}>{item.decision}</Badge></div>)}</div></div></section>}
      {!isIndication && <Notice tone="blue">Kejadian ini berkategori "tidak dapat dianalisis" (kualitas video kurang). Ini bukan indikasi dan tidak memerlukan validasi.</Notice>}
      {!readOnly && <section className="rounded-md border border-slate-200 bg-white p-6"><h2 className="font-bold text-slate-900">Tambah Catatan Manual</h2><p className="mt-1 text-sm text-slate-500">Catat kejadian yang terlihat langsung tetapi tidak terdeteksi sistem.</p><div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Waktu Kejadian</span><input type="time" value={manual.time} onChange={(x) => setManual({ ...manual, time: x.target.value })} className="h-11 w-full rounded-md border border-slate-200 px-3.5 text-sm" /></label><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Jenis Kejadian</span><input value={manual.kind} onChange={(x) => setManual({ ...manual, kind: x.target.value })} placeholder="Contoh: Aktivitas di luar kamera" className="h-11 w-full rounded-md border border-slate-200 px-3.5 text-sm" /></label><label className="block sm:col-span-2"><span className="mb-2 block text-sm font-semibold text-slate-700">Catatan</span><textarea rows={3} value={manual.note} onChange={(x) => setManual({ ...manual, note: x.target.value })} className="w-full rounded-md border border-slate-200 p-3 text-sm" placeholder="Jelaskan kejadian yang diamati..." /></label></div><div className="mt-4 flex items-center justify-between">{manualSaved ? <span className="text-xs font-semibold text-emerald-700">Catatan manual berhasil disimpan.</span> : <span />}<Button variant="secondary" disabled={!manual.note.trim()} onClick={saveManual}>Simpan Catatan</Button></div></section>}
    </div><aside className="h-fit rounded-md border border-slate-200 bg-white p-6"><div className="flex items-center gap-3 border-b border-slate-100 pb-5"><div className="grid size-11 place-items-center rounded-full bg-slate-100 text-sm font-bold text-slate-700">{initials(e.student?.name ?? "")}</div><div><p className="font-bold text-slate-900">{e.student?.name}</p><p className="text-xs text-slate-500">NIS {e.student?.nis ?? "—"} • {e.student?.class_name}</p></div></div><dl className="mt-5 space-y-4 text-sm">{[["Jenis", eventTitle(e)], ["Kategori", isIndication ? "Indikasi (perlu ditinjau)" : "Tidak dapat dianalisis"], ["Waktu kejadian", fmtTime(e.start_ts)], ["Durasi", e.status === "open" ? "Masih berlangsung" : fmtDuration(e.duration_s)], ["Skor model", scoreText(e)], ["Status validasi", reviewLabel(e.review_status)], ["Versi model", e.model_version || "—"]].map(([label, value]) => <div key={label} className="flex justify-between gap-4"><dt className="text-slate-500">{label}</dt><dd className="text-right font-semibold text-slate-800">{value}</dd></div>)}</dl><div className="mt-6 rounded-md bg-amber-50 p-4"><p className="text-xs font-bold uppercase tracking-wide text-amber-700">Alasan dari sistem</p><p className="mt-2 text-sm leading-6 text-amber-900">{e.reason || "—"}</p></div><p className="mt-4 text-xs leading-5 text-slate-500">Skor hanya tersedia untuk deteksi objek; aturan durasi (mis. wajah tidak terlihat) tidak memiliki skor. Ambang aturan masih bersifat sementara dan belum divalidasi pada data sekolah.</p>{role !== "Pihak Sekolah" && <Button variant="secondary" className="mt-4 w-full" onClick={() => { setStudentId(e.student_id); go("student-detail"); }}>Buka detail siswa</Button>}</aside></div>}
  </main></AppShell>;
}

function downloadCsv(name: string, rows: (string | number | null | undefined)[][]) {
  const csv = rows.map((r) => r.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

function Report({ go }: { go: (s: Screen) => void }) {
  const { setEventId } = useSel();
  const { exam, exams } = useCurrentExam();
  const { setExamId } = useSel();
  const rep = usePoll(() => (exam ? api.report(exam.id) : Promise.reject(new Error(""))), [exam?.id]);
  const [confirm, setConfirm] = useState(false);
  const [exportType, setExportType] = useState<"PDF" | "Excel" | null>(null);
  const [toast, setToast] = useState("");
  const r: ReportData | null = rep.data;
  const doExport = () => {
    if (!r) return;
    if (exportType === "Excel") {
      downloadCsv(`laporan-${r.exam.id}.csv`, [["Siswa", "NIS", "Jenis Indikasi", "Mulai", "Selesai", "Status validasi", "Catatan pengawas"], ...r.events.map((e) => [e.student?.name, e.student?.nis, eventTitle(e), e.start_ts, e.end_ts, reviewLabel(e.review_status), e.last_review?.note])]);
      setToast("Laporan diekspor sebagai CSV (dapat dibuka di Excel).");
    } else { window.print(); setToast("Gunakan dialog cetak browser untuk menyimpan PDF."); }
    setExportType(null);
  };
  const ind = r?.indications;
  return <AppShell active="report" go={go} title="Laporan Sesi"><main className="p-4 sm:p-8">
    <PageTitle eyebrow={r ? (r.exam.status === "Selesai" ? "Sesi selesai" : r.exam.status) : undefined} title="Laporan Sesi" description={r ? `${r.exam.name} • ${fmtDate(r.exam.date)}, ${examTime(r.exam)}` : "Memuat..."} action={<div className="flex flex-wrap gap-2"><select aria-label="Pilih sesi" value={exam?.id ?? ""} onChange={(e) => setExamId(Number(e.target.value))} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600">{exams.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select><Button variant="secondary" icon="download" onClick={() => setExportType("PDF")}>Export PDF</Button><Button variant="secondary" icon="download" onClick={() => setExportType("Excel")}>Export Excel</Button><Button onClick={() => setConfirm(true)}>Finalisasi Laporan</Button></div>} />
    {rep.error && <Notice tone="red">{rep.error}</Notice>}
    {r && <>
      <div className="mb-5 grid gap-4 xl:grid-cols-3"><section className="rounded-md border border-slate-200 bg-white p-5"><p className="text-xs font-bold uppercase tracking-widest text-slate-400">Informasi Sesi</p><div className="mt-4 space-y-2 text-sm">{[["Nama", r.exam.name], ["Tanggal", fmtDate(r.exam.date)], ["Jam", examTime(r.exam)], ["Durasi", `${r.exam.duration_min} menit`], ["Pengawas", r.exam.supervisor?.name ?? "—"]].map(([k, v]) => <div key={k} className="flex justify-between gap-4"><span className="text-slate-500">{k}</span><span className="text-right font-semibold text-slate-800">{v}</span></div>)}</div></section><section className="rounded-md border border-slate-200 bg-white p-5"><p className="text-xs font-bold uppercase tracking-widest text-slate-400">Kehadiran</p><div className="mt-4 grid grid-cols-2 gap-4">{[[r.attendance.enrolled, "Total peserta"], [r.attendance.joined, "Hadir"], [r.attendance.not_joined, "Tidak hadir"], [ind!.cannot_analyze, "Periode tak terbaca"]].map(([value, label]) => <div key={label}><p className="text-xl font-bold text-slate-900">{value}</p><p className="text-xs text-slate-500">{label}</p></div>)}</div></section><section className="rounded-md border border-slate-200 bg-white p-5"><p className="text-xs font-bold uppercase tracking-widest text-slate-400">Indikasi</p><div className="mt-4 grid grid-cols-2 gap-4">{[[ind!.total, "Total"], [ind!.valid, "Valid"], [ind!.invalid, "Tidak Valid"], [ind!.further, "Perlu Tinjauan"]].map(([value, label]) => <div key={label}><p className="text-xl font-bold text-slate-900">{value}</p><p className="text-xs text-slate-500">{label}</p></div>)}</div></section></div>
      {ind!.unreviewed > 0 && <div className="mb-5 flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-4"><span className="text-amber-600"><Icon name="bell" size={18} /></span><div><p className="text-sm font-bold text-amber-900">{ind!.unreviewed} Indikasi belum ditinjau</p><p className="mt-1 text-xs leading-5 text-amber-800">Laporan final hanya akan memasukkan Indikasi yang telah melalui proses validasi.</p></div></div>}
      <div className="overflow-x-auto rounded-md border border-slate-200 bg-white"><div className="flex min-w-[620px] divide-x divide-slate-200">{[[`${r.attendance.joined} dari ${r.attendance.enrolled}`, "Kehadiran", "green"], [String(ind!.total), "Total Indikasi", "amber"], [String(ind!.total - ind!.unreviewed), "Sudah ditinjau", "blue"], [String(ind!.unreviewed), "Belum ditinjau", "gray"]].map(([num, label, tone]) => <div key={label} className="flex flex-1 items-center gap-3 px-4 py-3"><span className={`size-2 rounded-full ${tone === "green" ? "bg-emerald-500" : tone === "amber" ? "bg-amber-500" : tone === "blue" ? "bg-blue-700" : "bg-slate-400"}`} /><div><p className="text-lg font-bold leading-5 text-slate-900">{num}</p><p className="mt-0.5 whitespace-nowrap text-xs text-slate-500">{label}</p></div></div>)}</div></div>
      <section className="mt-6 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-5"><div><h2 className="font-bold text-slate-900">Rincian Indikasi</h2><p className="mt-1 text-xs text-slate-500">Status validasi, catatan pengawas, dan evidence.</p></div><Badge tone={ind!.unreviewed ? "amber" : "green"}>{ind!.unreviewed} belum ditinjau</Badge></div><div className="overflow-x-auto"><table className="w-full min-w-[800px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Siswa</th><th className="px-5 py-3.5">Jenis Indikasi</th><th className="px-5 py-3.5">Waktu</th><th className="px-5 py-3.5">Status validasi</th><th className="px-5 py-3.5">Catatan Pengawas</th><th className="px-5 py-3.5">Evidence</th></tr></thead><tbody>{r.events.map((e) => <tr key={e.event_id} className={`border-t border-slate-100 ${!e.review_status ? "bg-amber-50/50" : ""}`}><td className="px-5 py-4 font-semibold text-slate-800">{e.student?.name}</td><td className="px-5 py-4 text-slate-600">{eventTitle(e)}</td><td className="px-5 py-4 text-slate-500">{fmtTime(e.start_ts)}</td><td className="px-5 py-4"><Badge tone={reviewTone(e.review_status)}>{e.review_status ?? "BELUM DITINJAU"}</Badge></td><td className="max-w-56 truncate px-5 py-4 text-slate-500">{e.last_review?.note || "—"}</td><td className="px-5 py-4"><button onClick={() => { setEventId(e.event_id); go("detail"); }} className="font-semibold text-blue-700 hover:underline">Lihat Evidence</button></td></tr>)}</tbody></table>{r.events.length === 0 && <p className="p-6 text-center text-sm text-slate-500">Tidak ada indikasi pada sesi ini.</p>}</div></section>
      <section className="mt-6 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="border-b border-slate-100 p-5"><h2 className="font-bold text-slate-900">Aktivitas Pengawas</h2><p className="mt-1 text-xs text-slate-500">Audit log hanya-baca dan tidak dapat diedit atau dihapus.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Aktivitas</th><th className="px-5 py-3">Waktu</th><th className="px-5 py-3">User</th><th className="px-5 py-3">Status</th></tr></thead><tbody>{r.activity.map((row, i) => <tr key={i} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{row.action}</td><td className="px-5 py-4 text-slate-500">{fmtDateTime(row.ts)}</td><td className="px-5 py-4 text-slate-600">{row.user_name}</td><td className="px-5 py-4"><Badge tone="green">{row.status}</Badge></td></tr>)}</tbody></table>{r.activity.length === 0 && <p className="p-6 text-center text-sm text-slate-500">Belum ada aktivitas.</p>}</div></section>
    </>}
    {confirm && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4"><section role="dialog" aria-modal="true" className="w-full max-w-md rounded-md border border-slate-200 bg-white p-6"><div className="grid size-11 place-items-center rounded-md bg-amber-50 text-amber-700"><Icon name="report" /></div><h2 className="mt-5 text-lg font-bold text-slate-900">Finalisasi laporan?</h2><p className="mt-2 text-sm leading-6 text-slate-500">{ind?.unreviewed ? `Masih ada ${ind.unreviewed} Indikasi yang belum ditinjau. Tinjau seluruh Indikasi sebelum membuat laporan final.` : "Seluruh indikasi sudah ditinjau."} Penyimpanan status laporan final belum tersedia di backend.</p><div className="mt-6 flex justify-end gap-3"><Button variant="secondary" onClick={() => setConfirm(false)}>Tutup</Button></div></section></div>}
    {exportType && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4"><section role="dialog" aria-modal="true" className="w-full max-w-md rounded-md border border-slate-200 bg-white p-6"><div className="grid size-11 place-items-center rounded-md bg-blue-50 text-blue-700"><Icon name="download" /></div><h2 className="mt-5 text-lg font-bold text-slate-900">Export Laporan {exportType}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{exportType === "Excel" ? "Rincian indikasi diunduh sebagai CSV yang dapat dibuka di Excel." : "Halaman ini akan dicetak; pilih \"Simpan sebagai PDF\" di dialog cetak."}</p><div className="mt-6 flex justify-end gap-3"><Button variant="secondary" onClick={() => setExportType(null)}>Batal</Button><Button onClick={doExport}>Ya, Export</Button></div></section></div>}
    {toast && <div role="status" className="fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-md border border-slate-200 bg-white p-4 text-sm font-semibold text-slate-800"><Icon name="check" size={18} />{toast}<button onClick={() => setToast("")} className="ml-3 text-slate-400"><Icon name="close" size={16} /></button></div>}
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
      <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Nama Siswa</th><th className="px-5 py-3.5">NIS/NISN</th><th className="px-5 py-3.5">Status</th><th className="px-5 py-3.5">Jumlah Indikasi</th><th className="px-5 py-3.5">Belum Ditinjau</th><th className="px-5 py-3.5">Aksi</th></tr></thead><tbody>{data.map((r) => { const st = studentStatus(r); return <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50"><td className="px-5 py-4"><div className="flex items-center gap-3"><div className="grid size-9 place-items-center rounded-full bg-blue-50 text-xs font-bold text-blue-700">{initials(r.name)}</div><span className="font-semibold text-slate-800">{r.name}</span></div></td><td className="px-5 py-4 text-slate-500">{r.nis}</td><td className="px-5 py-4"><Badge tone={st === "Hadir" ? "green" : st === "Belum bergabung" ? "gray" : "amber"}>{st}</Badge></td><td className="px-5 py-4 font-semibold text-slate-700">{r.counts?.indications ?? "—"}</td><td className="px-5 py-4"><Badge tone={(r.counts?.unreviewed ?? 0) === 0 ? "gray" : "amber"}>{r.counts?.unreviewed ?? "—"}</Badge></td><td className="px-5 py-4">{MONITOR_ROLES.includes(role) && <button onClick={() => { setStudentId(r.id); go("student-detail"); }} className="text-xs font-semibold text-blue-700">Detail Siswa</button>}</td></tr>; })}</tbody></table></div></section>
    <div className="mt-4 flex items-start gap-3 rounded-md bg-slate-100 p-4 text-xs leading-5 text-slate-600"><Icon name="shield" size={17} /><p>Hanya informasi akademik dan pemantauan yang relevan yang ditampilkan. Data pribadi lain tidak disimpan pada halaman ini.</p></div>
  </main></AppShell>;
}

function Settings({ go }: { go: (s: Screen) => void }) {
  const [section, setSection] = useState("Profil");
  const { role } = useRole();
  const { user } = useUser();
  const menu = role === "Pengawas" ? ["Profil", "Preferensi pemantauan", "Notifikasi", "Privasi", "Keamanan akun"] : ["Profil", "Keamanan akun"];
  return <AppShell active="settings" go={go} title="Pengaturan"><main className="mx-auto max-w-6xl p-4 sm:p-8"><PageTitle title="Pengaturan" description="Kelola preferensi akun, pemantauan, keamanan, dan privasi data." /><div className="grid gap-6 lg:grid-cols-[250px_1fr]"><aside className="h-fit rounded-md border border-slate-200 bg-white p-2">{menu.map(x => <button key={x} onClick={() => setSection(x)} className={`w-full rounded-md px-3 py-2.5 text-left text-sm font-semibold ${section === x ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50"}`}>{x}</button>)}</aside>
    <section className="rounded-md border border-slate-200 bg-white p-6"><div className="border-b border-slate-100 pb-5"><h2 className="font-bold text-slate-900">{section}{section !== "Profil" && section !== "Privasi" && <SampleTag />}</h2><p className="mt-1 text-sm text-slate-500">{section === "Privasi" ? "Atur akses dan penggunaan data pemantauan ujian." : `Kelola pengaturan ${section.toLowerCase()} Anda.`}</p></div>
      {section === "Profil" ? <div className="mt-6 grid gap-5 sm:grid-cols-2"><Field label="Nama lengkap" value={user?.name} /><Field label="Email" value={user?.email} /><Field label="Institusi" value="SMA Negeri 8 Bandung" /><Field label="Peran" value={role} /></div> : section === "Privasi" ? <div className="mt-6 space-y-4"><div className="rounded-md bg-blue-50 p-5"><div className="flex gap-3"><Icon name="shield" size={20} /><div><p className="text-sm font-bold text-blue-900">Data untuk pengawasan ujian</p><p className="mt-2 text-sm leading-6 text-blue-800">Cuplikan gambar bukti Indikasi hanya digunakan untuk pengawasan, peninjauan, dan pelaporan ujian oleh pihak berwenang, dan dihapus otomatis setelah 24 jam. Video penuh dan audio tidak disimpan oleh EduAI.</p></div></div></div></div> : <div className="mt-6 space-y-3">{["Pemberitahuan Indikasi baru", "Peringatan masalah koneksi", "Keamanan akun"].map((x, i) => <div key={x} className="flex items-center justify-between rounded-md border border-slate-200 p-4"><div><p className="text-sm font-semibold text-slate-800">{x}</p><p className="mt-1 text-xs text-slate-500">{i === 0 ? "Tampilkan notifikasi tanpa mengganggu pemantauan." : "Kirimkan informasi penting ke pengguna."}</p></div><span className="relative h-6 w-11 rounded-full bg-blue-700"><span className="absolute right-1 top-1 size-4 rounded-full bg-white" /></span></div>)}</div>}
      <div className="mt-6 flex justify-end"><Button disabled>Simpan perubahan</Button></div></section></div></main></AppShell>;
}

function StudentDashboard({ go }: { go: (s: Screen) => void }) {
  const { user } = useUser();
  const { setExamId } = useSel();
  const list = usePoll(() => api.exams(), [], 15000);
  const exams = list.data ?? [];
  const pick = (status: string) => exams.find((e) => e.status === status);
  const cards = [["Sedang berlangsung", pick("Sedang Berlangsung"), "blue"], ["Akan datang", pick("Terjadwal"), "gray"], ["Selesai", pick("Selesai"), "green"]] as [string, Exam | undefined, string][];
  return <AppShell active="dashboard" go={go} title="Dasbor Siswa"><main className="p-4 sm:p-8">
    <PageTitle title={`${greeting()}, ${user?.name.split(" ")[0] ?? ""}`} description="Lihat jadwal dan status ujian Anda di satu tempat." />
    {list.error && <Notice tone="red">{list.error}</Notice>}
    <div className="grid gap-5 lg:grid-cols-3">{cards.map(([status, e, tone]) => <section key={status} className="rounded-md border border-slate-200 bg-white p-5"><Badge tone={tone as "blue" | "gray" | "green"}>{status}</Badge><h2 className="mt-4 font-bold text-slate-900">{e?.name ?? "Tidak ada ujian"}</h2><p className="mt-2 text-sm text-slate-500">{e ? (status === "Sedang berlangsung" ? examTime(e) : `${fmtDate(e.date)} • ${e.start_time.replace(":", ".")} WIB`) : "—"}</p><p className="mt-1 text-xs text-slate-400">{e?.class_name ?? user?.class_name} • SMA Negeri 8 Bandung</p>{status === "Sedang berlangsung" && e && <Button className="mt-5 w-full" onClick={() => { setExamId(e.id); go("device"); }}>Cek perangkat & masuk</Button>}</section>)}</div>
    <section className="mt-6 rounded-md border border-blue-100 bg-blue-50 p-5"><div className="flex gap-3"><Icon name="shield" size={20} /><div><p className="text-sm font-bold text-blue-900">Privasi peserta dilindungi</p><p className="mt-1 text-sm leading-6 text-blue-800">Siswa hanya dapat mengikuti ujian dan tidak memiliki akses ke video pemantauan, Indikasi, validasi, atau laporan final.</p></div></div></section>
  </main></AppShell>;
}

function MyExams({ go }: { go: (s: Screen) => void }) {
  const { user } = useUser();
  const { setExamId } = useSel();
  const list = usePoll(() => api.exams(), [], 15000);
  const rows = (list.data ?? []).map((e) => ({ ...e, timing: e.status === "Sedang Berlangsung" ? "active" : e.status === "Selesai" ? "ended" : "upcoming" }));
  return <AppShell active="my-exams" go={go} title="Ujian Saya"><main className="p-4 sm:p-8"><PageTitle title="Ujian Saya" description={`Hanya ujian yang didaftarkan Admin untuk ${user?.name ?? ""} • ${user?.class_name ?? ""}.`} />{list.error && <Notice tone="red">{list.error}</Notice>}<section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Nama ujian</th><th className="px-5 py-3.5">Tanggal</th><th className="px-5 py-3.5">Jam mulai</th><th className="px-5 py-3.5">Durasi</th><th className="px-5 py-3.5">Status</th><th className="px-5 py-3.5">Aksi</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{row.name}</td><td className="px-5 py-4 text-slate-600">{fmtDate(row.date)}</td><td className="px-5 py-4 text-slate-600">{row.start_time.replace(":", ".")} WIB</td><td className="px-5 py-4 text-slate-600">{row.duration_min} menit</td><td className="px-5 py-4"><Badge tone={row.timing === "ended" ? "green" : row.timing === "active" ? "blue" : "gray"}>{row.status}</Badge></td><td className="px-5 py-4">{row.timing === "active" ? <Button className="h-9" onClick={() => { setExamId(row.id); go("device"); }}>Mulai Ujian</Button> : <div><Button className="h-9" disabled>Mulai Ujian</Button><p className="mt-1.5 text-[10px] text-slate-400">{row.timing === "upcoming" ? "Aktif saat jadwal dimulai" : "Waktu ujian telah berakhir"}</p></div>}</td></tr>)}</tbody></table>{!list.loading && rows.length === 0 && <p className="p-6 text-center text-sm text-slate-500">Belum ada ujian yang didaftarkan untuk Anda.</p>}</div><div className="border-t border-blue-100 bg-blue-50 p-4 text-xs leading-5 text-blue-800">Akses ujian divalidasi berdasarkan daftar peserta dan status ujian yang ditentukan Admin.</div></section></main></AppShell>;
}

function InstitutionDashboard({ go, role }: { go: (s: Screen) => void; role: "Penyelenggara Ujian" | "Pihak Sekolah" }) {
  const organizer = role === "Penyelenggara Ujian";
  const { setExamId } = useSel();
  const d = usePoll(() => api.dashboard(), [], 15000);
  const exams = d.data?.exams ?? [];
  const totalStudents = exams.reduce((a, e) => a + e.student_count, 0);
  const supervisors = new Set(exams.map((e) => e.supervisor?.id).filter(Boolean)).size;
  const validated = (d.data?.recent_indications ?? []).length;
  const cards = organizer ? [[exams.filter((e) => e.status === "Terjadwal").length, "Sesi terjadwal"], [totalStudents, "Kursi peserta"], [supervisors, "Pengawas bertugas"], [d.data?.summary?.active_sessions ?? 0, "Sesi aktif"]] : [[exams.length, "Sesi tercatat"], [exams.filter((e) => e.status === "Selesai").length, "Sesi selesai"], [validated, "Indikasi tervalidasi (terbaru)"], [exams.filter((e) => e.status === "Sedang Berlangsung").length, "Sesi berlangsung"]];
  return <AppShell active="dashboard" go={go} title={`Dasbor ${role}`}><main className="p-4 sm:p-8"><PageTitle title={organizer ? "Koordinasi ujian semester" : "Ringkasan akademik sekolah"} description={organizer ? "Pantau sesi, peserta, pengawas, dan laporan sesuai kewenangan yang diberikan." : "Pantau informasi sesi dan laporan final yang telah melalui validasi."} />
    {d.error && <Notice tone="red">{d.error}</Notice>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([value, label]) => <section key={label} className="rounded-md border border-slate-200 bg-white p-5"><p className="text-2xl font-bold text-slate-900">{value}</p><p className="mt-1 text-sm text-slate-500">{label}</p></section>)}</div>
    <section className="mt-6 overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-5"><div><h2 className="font-bold text-slate-900">{organizer ? "Sesi dalam kewenangan Anda" : "Laporan terbaru"}</h2><p className="mt-1 text-xs text-slate-500">Data SMA Negeri 8 Bandung</p></div><Button variant="ghost" onClick={() => go(organizer ? "sessions" : "report")}>Lihat semua</Button></div><div className="divide-y divide-slate-100">{exams.slice(0, 5).map((session) => <button key={session.id} onClick={() => { setExamId(session.id); go(organizer ? "exam-detail" : "report"); }} className="flex w-full items-center justify-between gap-4 p-5 text-left hover:bg-slate-50"><div><p className="text-sm font-semibold text-slate-800">{session.name}</p><p className="mt-1 text-xs text-slate-500">{fmtDate(session.date)} • {session.student_count} peserta</p></div><Badge tone={statusTone(session.status)}>{session.status}</Badge></button>)}</div></section>
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
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[[String((users.data ?? []).filter((u) => u.active).length), "User aktif", "users"], ["5", "Role sistem", "shield"], [ai ? `${ai.evidence_retention_hours} jam` : "—", "Retensi evidence", "clock"], [String(auditToday), "Audit hari ini", "file"]].map(([value, label, icon]) => <button key={label} onClick={() => go(label === "User aktif" ? "users" : label === "Role sistem" ? "permissions" : label === "Retensi evidence" ? "retention" : "audit")} className="rounded-md border border-slate-200 bg-white p-5 text-left hover:border-blue-200"><div className="flex items-center justify-between"><p className="text-2xl font-bold text-slate-900">{value}</p><span className="text-slate-400"><Icon name={icon as IconName} /></span></div><p className="mt-2 text-sm text-slate-500">{label}</p></button>)}</div>
    <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_.8fr]"><section className="rounded-md border border-slate-200 bg-white"><div className="border-b border-slate-100 p-5"><h2 className="font-bold text-slate-900">Aktivitas sistem terbaru</h2></div><div className="divide-y divide-slate-100">{(audit.data ?? []).slice(0, 6).map((row) => <div key={row.id} className="flex items-center gap-4 p-4"><div className="grid size-9 place-items-center rounded-full bg-slate-100 text-xs font-bold text-slate-600">{initials(row.user_name)}</div><div className="flex-1"><p className="text-sm font-semibold text-slate-800">{row.user_name}</p><p className="mt-0.5 text-xs text-slate-500">{row.action}</p></div><span className="text-xs text-slate-400">{fmtTime(row.ts).slice(0, 5)}</span></div>)}</div></section><section className="rounded-md border border-blue-100 bg-blue-50 p-5"><h2 className="font-bold text-blue-900">Status sistem</h2><div className="mt-5 space-y-4">{[["Backend", health.data ? "Normal" : health.error ? "Tidak terhubung" : "Memeriksa"], ["Layanan AI", ai ? (ai.available ? "Siap" : "Belum siap") : "—"], ["Model wajah", ai?.models.face_detector?.loaded ? "Dimuat" : "Tidak ada"], ["Head pose (Face Landmarker)", ai?.models.face_landmarker?.loaded ? "Dimuat" : "Tidak ada"], ["Deteksi ponsel (EfficientDet)", ai?.models.object_detector?.loaded ? "Dimuat" : "Tidak ada"], ["OpenVidu", health.data?.[0].livekit.configured ? "Terkonfigurasi" : "Belum dikonfigurasi"], ["Enkripsi evidence", ai?.evidence_encrypted ? "Aktif" : "Tidak aktif"]].map(([label, value]) => <div key={label} className="flex justify-between text-sm"><span className="text-blue-800">{label}</span><span className="font-semibold text-blue-900">{value}</span></div>)}</div>{ai && !ai.available && <p className="mt-4 text-xs text-blue-800">{ai.reason}</p>}</section></div>
  </main></AppShell>;
}

function IndicationsPage({ go }: { go: (s: Screen) => void }) {
  // Grouped view: one row per case (same exam + student + indicator, repeated within the backend's gap window).
  // Original events stay available in the case panel and in the existing evidence page.
  const { role } = useRole();
  const { eventId } = useSel();
  const readOnly = role === "Pihak Sekolah";
  const [filter, setFilter] = useState("Semua");
  const [selId, setSelId] = useState<string | null>(null);
  const list = usePoll(() => api.cases(), [], 5000);
  const rows = list.data?.cases ?? [];
  const label = (c: CaseSummary) => (c.unreviewed_count > 0 ? "BELUM DITINJAU" : c.review_status ?? "BELUM DITINJAU");
  const visible = rows.filter((r) => filter === "Semua" || label(r) === filter);
  const cur = visible.find((c) => c.case_id === selId) ?? (eventId ? visible.find((c) => c.event_ids.includes(eventId)) : undefined) ?? visible[0];
  const count = (l: string) => rows.filter((r) => label(r) === l).length;
  const summary = [["Kasus", rows.length], ["Deteksi asli", list.data?.total_events ?? 0], ["Kasus belum ditinjau", count("BELUM DITINJAU")], ["Kasus perlu tinjauan lanjut", count("Perlu Tinjauan Lanjut")]];
  return <AppShell active="indications" go={go} title="Daftar Indikasi"><main className="p-4 sm:p-8">
    <PageTitle title={readOnly ? "Indikasi Tervalidasi" : "Indikasi perilaku yang perlu ditinjau"} description={readOnly ? "Hanya hasil yang telah divalidasi ditampilkan untuk pihak sekolah." : "Kejadian berulang dikelompokkan menjadi satu kasus. Pilih kasus untuk melihat semua kejadian aslinya dan memvalidasi sekaligus."} />
    {list.error && <Notice tone="red">{list.error}</Notice>}
    <div className="mb-2 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 xl:grid-cols-4">{summary.map(([l, n]) => <div key={l} className="bg-white px-5 py-4"><p className="text-2xl font-semibold text-slate-900">{n}</p><p className="text-xs text-slate-500">{l}</p></div>)}</div>
    {list.data && <p className="mb-5 text-xs text-slate-500">{rows.length} kasus dari {list.data.total_events} deteksi. {list.data.gap_s > 0 ? `Kejadian dengan siswa, ujian, dan jenis indikasi sama yang berjarak paling lama ${Math.round(list.data.gap_s)} detik digabung` : "Satu kasus per siswa dan jenis perilaku untuk seluruh ujian; setiap kejadian tetap tercatat di dalamnya"}; jenis indikasi berbeda selalu menjadi kasus terpisah. Notifikasi muncul sekali, saat ambang perilaku pertama kali terpenuhi.</p>}
    <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="flex flex-wrap gap-2 border-b border-slate-100 p-4">{["Semua", "BELUM DITINJAU", "Valid", "Tidak Valid", "Perlu Tinjauan Lanjut", "Campuran"].filter((f) => !readOnly || f !== "BELUM DITINJAU").map((f) => <button key={f} onClick={() => { setFilter(f); setSelId(null); }} className={`rounded-full border px-3 py-1 text-xs font-medium ${filter === f ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}>{f === "BELUM DITINJAU" ? "Belum ditinjau" : f}</button>)}</div>
        <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm"><thead><tr><th className="px-3 py-3">Siswa</th><th className="px-3 py-3">Indikasi</th><th className="px-3 py-3">Kejadian</th><th className="px-3 py-3">Total durasi</th><th className="px-3 py-3">Pertama – terakhir</th><th className="px-3 py-3">Status</th></tr></thead><tbody>{visible.map((r) => <tr key={r.case_id} onClick={() => setSelId(r.case_id)} className={`cursor-pointer border-t border-slate-100 ${cur?.case_id === r.case_id ? "bg-blue-50" : ""}`}><td className="px-3 py-3.5 font-semibold text-slate-800">{r.student?.name}<p className="mt-0.5 text-xs font-normal text-slate-400">{r.exam?.name}</p></td><td className="px-3 py-3.5 text-slate-600">{eventTitle(r)}{r.status === "open" ? " (berlangsung)" : ""}{r.rule && !r.rule.met && <p className="mt-0.5 text-[11px] text-slate-400">Di bawah ambang ({r.rule.max_in_window}/{r.rule.min_count}{r.rule.window_s ? ` dalam ${Math.round(r.rule.window_s / 60)} mnt` : ""})</p>}</td><td className="px-3 py-3.5 font-semibold text-slate-700">{r.episode_count ?? r.event_count}×</td><td className="whitespace-nowrap px-3 py-3.5 text-slate-500">{fmtDuration(r.total_duration_s)}</td><td className="whitespace-nowrap px-3 py-3.5 text-slate-500">{fmtTime(r.first_start_ts)}{r.event_count > 1 ? ` – ${fmtTime(r.last_start_ts)}` : ""}</td><td className="px-3 py-3.5"><Badge tone={caseTone(r)}>{caseLabel(r)}</Badge></td></tr>)}</tbody></table></div>
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
  const [thumb, setThumb] = useState<string | null>(null);
  const evidenceEvent = [...events].reverse().find((e) => e.evidence_id);
  useEffect(() => {
    setThumb(null);
    const id = evidenceEvent?.evidence_id ?? c.latest_evidence_id;
    if (!id) return;
    let url = "";
    let cancelled = false;
    api.evidence(id).then((m) => api.evidenceFrameUrl(m.evidence_id, m.key_index)).then((u) => { if (cancelled) URL.revokeObjectURL(u); else { url = u; setThumb(u); } }).catch(() => undefined);
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [evidenceEvent?.evidence_id, c.latest_evidence_id]);
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
  return <aside className="h-fit rounded-lg border border-slate-200 bg-white p-5">
    <div className="flex items-center justify-between gap-3"><h2 className="font-semibold text-slate-900">{c.student?.name}</h2><Badge tone={caseTone(c)}>{caseLabel(c)}</Badge></div>
    <p className="mt-1 text-sm text-slate-500">{eventTitle(c)} · {c.exam?.name}</p>
    <div className="relative mt-4 grid aspect-video place-items-center overflow-hidden rounded-md bg-slate-800 text-xs text-slate-300">{thumb ? <img src={thumb} alt="Cuplikan evidence" className="absolute inset-0 size-full object-cover" /> : <Silhouette />}<span className="absolute bottom-2 left-2 rounded bg-slate-900/70 px-2 py-0.5">{evidenceEvent ? `Evidence ${fmtTime(evidenceEvent.start_ts)} (${c.evidence_count} dari ${c.event_count} kejadian punya evidence)` : "Evidence belum tersedia"}</span></div>
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
  const { setExamId } = useSel();
  const data = usePoll(async () => {
    const finished = (await api.exams()).filter((e) => e.status === "Selesai");
    return Promise.all(finished.map((e) => api.report(e.id)));
  }, []);
  return <AppShell active="history" go={go} title="Riwayat Sesi"><main className="p-4 sm:p-8"><PageTitle title="Riwayat Sesi" description={`Sesi selesai yang pernah ditugaskan kepada ${user?.name ?? ""}.`} />{data.error && <Notice tone="red">{data.error}</Notice>}<section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr>{["Nama Ujian", "Tanggal", "Peserta", "Indikasi", "Valid", "Tidak Valid", "Perlu Tinjauan", "Status Tinjauan", "Aksi"].map((head) => <th key={head} className="px-5 py-3.5">{head}</th>)}</tr></thead><tbody>{(data.data ?? []).map((r) => <tr key={r.exam.id} className="border-t border-slate-100">{[r.exam.name, fmtDate(r.exam.date), r.attendance.enrolled, r.indications.total, r.indications.valid, r.indications.invalid, r.indications.further].map((cell, index) => <td key={index} className={`px-5 py-4 ${index === 0 ? "font-semibold text-slate-800" : "text-slate-600"}`}>{cell}</td>)}<td className="px-5 py-4"><Badge tone={r.indications.unreviewed === 0 ? "green" : "amber"}>{r.indications.unreviewed === 0 ? "Semua ditinjau" : "Perlu Tinjauan"}</Badge></td><td className="px-5 py-4"><button onClick={() => { setExamId(r.exam.id); go("report"); }} className="text-xs font-bold text-blue-700">Lihat Detail</button></td></tr>)}</tbody></table>{!data.loading && !(data.data ?? []).length && <p className="p-6 text-center text-sm text-slate-500">Belum ada sesi yang selesai.</p>}</div></section></main></AppShell>;
}

function UserManagement({ go }: { go: (s: Screen) => void }) {
  const { role } = useRole();
  const [modal, setModal] = useState(false);
  const admin = role === "Admin";
  const list = usePoll(() => api.users(admin ? undefined : "pengawas"), [admin]);
  const exams = usePoll(() => api.exams(), []);
  const [q, setQ] = useState("");
  const rows: UserRow[] = (list.data ?? []).filter((u) => u.name.toLowerCase().includes(q.toLowerCase()) || u.email.includes(q.toLowerCase()));
  const sessionsOf = (id: number) => (exams.data ?? []).filter((e) => e.supervisor?.id === id && e.status !== "Selesai").length;
  return <AppShell active="users" go={go} title={admin ? "Manajemen User" : "Daftar Pengawas"}><main className="p-4 sm:p-8"><PageTitle title={admin ? "Manajemen User" : "Pengawas Ujian"} description={admin ? "Kelola akun, status, dan role pengguna EduAI." : "Tentukan pengawas untuk sesi yang menjadi kewenangan Anda."} action={<Button icon="plus" onClick={() => setModal(true)}>{admin ? "Tambah User" : "Tambah Pengawas"}</Button>} />
    {list.error && <Notice tone="red">{list.error}</Notice>}
    <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="flex gap-3 border-b border-slate-100 p-4"><div className="relative max-w-sm flex-1"><span className="absolute left-3 top-2.5 text-slate-400"><Icon name="search" size={17} /></span><input value={q} onChange={(e) => setQ(e.target.value)} className="h-10 w-full rounded-md border border-slate-200 pl-9 pr-3 text-sm" placeholder="Cari nama atau email" /></div></div><div className="overflow-x-auto"><table className="w-full min-w-[880px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr>{(admin ? ["Nama", "Email", "Role", "Status", "Tanggal dibuat"] : ["Nama", "Email", "Penugasan", "Status", "Kelas"]).map((head) => <th key={head} className="px-5 py-3.5">{head}</th>)}</tr></thead><tbody>{rows.map((u) => { const cells = admin ? [u.name, u.email, u.role_label, u.active ? "Aktif" : "Nonaktif", fmtDate(u.created_at)] : [u.name, u.email, `${sessionsOf(u.id)} sesi aktif`, u.active ? "Aktif" : "Nonaktif", "—"]; return <tr key={u.id} className="border-t border-slate-100">{cells.map((cell, index) => <td key={index} className={`px-5 py-4 ${index === 0 ? "font-semibold text-slate-800" : "text-slate-600"}`}>{index === 3 ? <Badge tone={cell === "Aktif" ? "green" : "gray"}>{cell}</Badge> : cell}</td>)}</tr>; })}</tbody></table></div></section>
    {modal && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4"><section role="dialog" aria-modal="true" className="w-full max-w-lg rounded-md border border-slate-200 bg-white p-6"><div className="flex items-center justify-between"><h2 className="text-lg font-bold text-slate-900">{admin ? "Tambah User" : "Tambah Pengawas"}<SampleTag /></h2><button onClick={() => setModal(false)} className="text-slate-400"><Icon name="close" /></button></div><p className="mt-3 text-sm text-slate-500">Pembuatan akun staf melalui antarmuka belum tersedia di backend. Untuk uji coba gunakan akun demo atau tambahkan akun lewat basis data.</p><div className="mt-6 space-y-4"><Field label="Nama lengkap" placeholder="Masukkan nama lengkap" /><Field label="Email institusi" placeholder="nama@sman8bdg.sch.id" type="email" /></div><div className="mt-6 flex justify-end gap-3"><Button variant="secondary" onClick={() => setModal(false)}>Tutup</Button><Button disabled>Simpan</Button></div></section></div>}
  </main></AppShell>;
}

function PermissionsPage({ go }: { go: (s: Screen) => void }) {
  // Mirrors the checks enforced by the backend (app/api.py).
  const permissions: [string, Role[]][] = [
    ["Mengikuti ujian", ["Siswa"]],
    ["Melihat video langsung & status AI sesi", ["Pengawas", "Penyelenggara Ujian", "Admin"]],
    ["Memvalidasi Indikasi", ["Pengawas", "Penyelenggara Ujian", "Admin"]],
    ["Melihat indikasi tervalidasi & laporan", ["Pengawas", "Penyelenggara Ujian", "Admin", "Pihak Sekolah"]],
    ["Membuat ujian & melihat audit log", ["Admin"]],
  ];
  const roles: Role[] = ["Siswa", "Pengawas", "Penyelenggara Ujian", "Admin", "Pihak Sekolah"];
  return <AppShell active="permissions" go={go} title="Role & Permission"><main className="p-4 sm:p-8"><PageTitle title="Role & Permission" description="Matriks izin inti yang diterapkan oleh backend." /><section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="overflow-x-auto"><table className="w-full min-w-[980px] text-center text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-4 text-left">Fitur</th>{roles.map((role) => <th key={role} className="px-5 py-4">{role}</th>)}</tr></thead><tbody>{permissions.map(([permission, allowedRoles]) => <tr key={permission} className="border-t border-slate-100"><td className="px-5 py-4 text-left font-semibold text-slate-800">{permission}</td>{roles.map((role) => { const allowed = allowedRoles.includes(role); return <td key={role} className="px-5 py-4"><span className={`mx-auto grid size-7 place-items-center rounded-full ${allowed ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-400"}`}>{allowed ? <Icon name="check" size={14} /> : "×"}</span></td>; })}</tr>)}</tbody></table></div></section><div className="mt-5 rounded-md border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-800"><strong>Kontrol akses aktif.</strong> Pengawas hanya dapat membuka sesi yang ditugaskan. Siswa tidak pernah menerima akses ke data pemantauan, Indikasi, atau laporan. Pihak sekolah hanya melihat indikasi yang sudah divalidasi.</div></main></AppShell>;
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
    <section className="overflow-hidden rounded-md border border-slate-200 bg-white"><div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3.5">Data</th><th className="px-5 py-3.5">Masa simpan</th><th className="px-5 py-3.5">Status</th></tr></thead><tbody>{[["Video rekaman penuh", "Tidak disimpan oleh EduAI", "green"], ["Evidence (cuplikan gambar)", ai.data ? `${ai.data.evidence_retention_hours} jam${ai.data.evidence_encrypted ? " • terenkripsi" : ""}` : "—", "green"], ["Data indikasi & validasi (teks)", "Disimpan untuk laporan; kebijakan sekolah belum dikonfigurasi", "amber"]].map(([data, days, tone]) => <tr key={data} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{data}</td><td className="px-5 py-4 text-slate-600">{days}</td><td className="px-5 py-4"><Badge tone={tone as "green" | "amber"}>{tone === "green" ? "Aktif" : "Perlu kebijakan"}</Badge></td></tr>)}</tbody></table></div><div className="border-t border-blue-100 bg-blue-50 p-4 text-sm text-blue-800">Evidence yang melewati masa simpan dihapus otomatis (diperiksa setiap 10 menit) dan dicatat dalam Audit Log.</div></section>
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
  useEffect(() => {
    setSummaries([]); setSummaryToast(null);
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
    setItems([]); setUnread(0); setToast(null);
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
  const stored = session.user();
  const [user, setUser] = useState<User | null>(stored);
  const [screen, setScreen] = useState<Screen>(stored && session.token() ? "dashboard" : "login");
  const [role, setRole] = useState<Role>(stored ? ROLE_LABEL[stored.role] : "Pengawas");
  const [examId, setExamId] = useState<number | null>(null);
  const [studentId, setStudentId] = useState<number | null>(null);
  const [eventId, setEventId] = useState<string | null>(null);
  const notify = useIndicationNotifications(user);
  useEffect(() => { setUnauthorizedHandler(() => { setUser(null); setScreen("login"); }); }, []);
  const allowed: Record<Role, Screen[]> = {
    Siswa: ["login", "dashboard", "my-exams", "consent", "device", "exam", "settings", "access-denied"],
    Pengawas: ["login", "dashboard", "sessions", "exam-detail", "waiting", "monitor", "student-detail", "detail", "timeline", "report", "indications", "history", "students", "settings", "access-denied"],
    "Penyelenggara Ujian": ["login", "dashboard", "sessions", "exam-detail", "waiting", "monitor", "student-detail", "detail", "timeline", "report", "indications", "history", "students", "users", "settings", "access-denied"],
    Admin: ["login", "dashboard", "sessions", "create", "exam-detail", "waiting", "consent", "device", "exam", "monitor", "student-detail", "detail", "timeline", "report", "indications", "history", "students", "users", "permissions", "configuration", "retention", "audit", "settings", "access-denied"],
    "Pihak Sekolah": ["login", "dashboard", "sessions", "exam-detail", "detail", "report", "indications", "history", "settings", "access-denied"],
  };
  const go = (next: Screen) => {
    if (next === "login") { session.clear(); setUser(null); }
    setScreen(next === "login" || allowed[role].includes(next) ? next : "access-denied");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  // Role comes from the server; going through setRole keeps the original context API.
  const setRoleAndGo = (r: Role) => setRole(r);
  let page: ReactNode;
  if (screen === "login" || !user) page = <Login go={(s) => setScreen(s)} />;
  else if (screen === "dashboard") page = <Dashboard go={go} />;
  else if (screen === "sessions") page = <Sessions go={go} />;
  else if (screen === "create") page = <AdminCreateExam go={go} />;
  else if (screen === "exam-detail") page = <ExamDetail go={go} />;
  else if (screen === "waiting") page = <WaitingRoom go={go} />;
  else if (screen === "consent") page = <Consent go={go} />;
  else if (screen === "device") page = <Device go={go} />;
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
  else if (screen === "permissions") page = <PermissionsPage go={go} />;
  else if (screen === "configuration") page = <ConfigurationPage go={go} />;
  else if (screen === "retention") page = <RetentionPage go={go} />;
  else if (screen === "audit") page = <AuditPage go={go} />;
  else if (screen === "access-denied") page = <AccessDenied go={go} />;
  else page = <Settings go={go} />;
  return <RoleContext.Provider value={{ role, setRole: setRoleAndGo }}><UserContext.Provider value={{ user, setUser }}><SelectionContext.Provider value={{ examId, setExamId, studentId, setStudentId, eventId, setEventId }}><NotifyContext.Provider value={notify}>{page}</NotifyContext.Provider></SelectionContext.Provider></UserContext.Provider></RoleContext.Provider>;
}
