// Exam sessions list (Figma "ExamSessionsPage"): status filter, search, WIB date text. No React.
import type { Exam, ExamStatus } from "./api.ts";

export const ALL_STATUSES = "Semua status";
export const STATUS_OPTIONS: (ExamStatus | typeof ALL_STATUSES)[] = [ALL_STATUSES, "Sedang Berlangsung", "Terjadwal", "Draft", "Selesai"];

/** Sessions matching the search text (name, subject or class) and the chosen status. */
export function filterSessions<T extends Pick<Exam, "name" | "subject" | "class_name" | "status">>(list: T[], query: string, status: string): T[] {
  const q = query.trim().toLowerCase();
  return list.filter((e) => (status === ALL_STATUSES || e.status === status)
    && (!q || [e.name, e.subject, e.class_name].some((v) => (v ?? "").toLowerCase().includes(q))));
}

/** Badge colour per status: gold for a running session (Figma "In progress"). */
export function sessionTone(status: string): "gold" | "blue" | "gray" | "green" {
  if (status === "Sedang Berlangsung") return "gold";
  if (status === "Terjadwal") return "blue";
  if (status === "Selesai") return "green";
  return "gray";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
/** "5 Nov 2026 · 13.00 WIB". The exam date and start time are already school (WIB) times. */
export function sessionDateText(e: Pick<Exam, "date" | "start_time">): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(e.date ?? "");
  const time = /^\d{2}:\d{2}$/.test(e.start_time ?? "") ? `${e.start_time.replace(":", ".")} WIB` : "";
  if (!m) return time || "Belum ada data";
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}${time ? ` · ${time}` : ""}`;
}

// ---------------------------------------------------------------- "Ujian Saya" (siswa): status filter
export type StudentFilter = "semua" | "berlangsung" | "terjadwal" | "selesai";
export const STUDENT_FILTERS: { key: StudentFilter; label: string }[] = [
  { key: "semua", label: "Semua" }, { key: "berlangsung", label: "Sedang berlangsung" }, { key: "terjadwal", label: "Terjadwal" }, { key: "selesai", label: "Selesai" },
];
/** Students never see drafts; anything not running or finished is scheduled. */
export const studentKind = (status: string): Exclude<StudentFilter, "semua"> =>
  status === "Sedang Berlangsung" ? "berlangsung" : status === "Selesai" ? "selesai" : "terjadwal";
export function filterStudentExams<T extends Pick<Exam, "status">>(list: T[], f: StudentFilter): T[] {
  return f === "semua" ? list : list.filter((e) => studentKind(e.status) === f);
}
export function studentFilterCounts(list: Pick<Exam, "status">[]): Record<StudentFilter, number> {
  const out: Record<StudentFilter, number> = { semua: list.length, berlangsung: 0, terjadwal: 0, selesai: 0 };
  for (const e of list) out[studentKind(e.status)] += 1;
  return out;
}
