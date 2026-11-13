// Data for the supervisor dashboard (Figma "ProctorPortalDashboard"), computed from the API only. No React.
import type { Exam, StudentRow } from "./api.ts";
import { NO_DATA } from "./time.ts";

const WIB = "+07:00";                          // exam date and start time are school (WIB) times

/** Start and end of an exam in epoch milliseconds. */
export function examTimes(e: Pick<Exam, "date" | "start_time" | "duration_min">): { start: number; end: number } {
  const start = Date.parse(`${e.date}T${e.start_time}:00${WIB}`);
  return { start, end: start + e.duration_min * 60_000 };
}

export const activeExams = (exams: Exam[]) => exams.filter((e) => e.status === "Sedang Berlangsung");

/** Scheduled exams, soonest first. */
export const upcomingExams = (exams: Exam[], limit = 4) =>
  exams.filter((e) => e.status === "Terjadwal").sort((a, b) => examTimes(a).start - examTimes(b).start).slice(0, limit);

/** "1 jam 12 mnt", "42 mnt", or a clear text once the scheduled time is over. */
export function remainingText(e: Pick<Exam, "date" | "start_time" | "duration_min">, now: number): string {
  const { end } = examTimes(e);
  if (!Number.isFinite(end)) return NO_DATA;
  const m = Math.ceil((end - now) / 60_000);
  if (m <= 0) return "Waktu ujian habis";
  const h = Math.floor(m / 60);
  return h ? `${h} jam ${m % 60} mnt` : `${m} mnt`;
}

/** A dashboard number: 0 is real data; a missing value says so instead of showing a made-up number. */
export const statText = (n: number | null | undefined) => (n == null ? NO_DATA : String(n));

/** Students whose camera or sound cannot be analysed right now. The decision stays with the supervisor:
 *  "Tidak dapat dianalisis" is a quality state, never an indication. */
export function analysisGaps(students: StudentRow[]): { camera: number; sound: number; students: number; label: string | null } {
  let camera = 0, sound = 0, total = 0;
  for (const s of students) {
    const cam = s.ai?.state === "cannot_analyze" || (s.counts?.open_cannot_analyze ?? 0) > 0;
    const snd = !!s.audio?.consented && !s.audio.active && (s.audio.reason === "mic_off" || s.audio.reason === "no_scores");
    camera += cam ? 1 : 0;
    sound += snd ? 1 : 0;
    total += cam || snd ? 1 : 0;
  }
  const parts = [camera ? `kamera ${camera}` : "", sound ? `suara ${sound}` : ""].filter(Boolean).join(", ");
  return { camera, sound, students: total, label: total ? `Tidak dapat dianalisis: ${total} siswa (${parts})` : null };
}

/** Icon for an indicator on the dashboard list. */
export function indicatorIcon(indicator: string): "phone" | "book" | "users" | "eye" | "camera" | "mic" | "bell" {
  if (indicator.startsWith("PHONE")) return "phone";
  if (indicator.startsWith("BOOK")) return "book";
  if (indicator === "MULTIPLE_PERSONS") return "users";
  if (indicator.startsWith("HEAD_TURN")) return "eye";
  if (indicator === "FACE_ABSENT" || indicator === "CAMERA_OFF") return "camera";
  if (["OTHER_VOICE", "WHISPER", "BISIKAN", "BICARA_MULUT_DIAM", "MIC_OFF"].includes(indicator)) return "mic";
  return "bell";
}
