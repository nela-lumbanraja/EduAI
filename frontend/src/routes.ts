// Screen choices around Beranda, Login and the dashboard, kept free of React so they can be tested with node:test.
//
// The page URL is read once, when the page loads, and is never changed afterwards: Safe Exam Browser hashes the
// page URL into its keys, so a history.pushState() after load could make the SEB check of a student fail.

export type Role = "Siswa" | "Pengawas" | "Penyelenggara Ujian" | "Admin" | "Pihak Sekolah";
export type Entry = "beranda" | "login" | "dashboard";

/** First screen for the URL the page was opened with. Signed in: always the dashboard (also for /login). */
export function initialScreen(pathname: string, signedIn: boolean): Entry {
  if (signedIn) return "dashboard";
  return pathname.replace(/\/+$/, "") === "/login" ? "login" : "beranda";
}

/** Signed-in staff who open a URL with an Indikasi filter (?jenis=..., ?status=...) or a case link (?kasus=...) start on the Indikasi page.
 *  Only the Indikasi page writes this query (a staff page; students in Safe Exam Browser never reach it). */
export function opensIndications(search: string, role: Role | null): boolean {
  if (!role || role === "Siswa") return false;
  const q = new URLSearchParams(search);
  return q.has("jenis") || q.has("status") || q.has("kasus");
}

/** What the Beranda's sign-in buttons do: signed out they show the rocket and then Login; signed in they go
 *  straight back to the dashboard, without the rocket. */
export function landingAction(signedIn: boolean): { label: string; next: "loading" | "dashboard" } {
  return signedIn ? { label: "Kembali ke Dasbor", next: "dashboard" } : { label: "Masuk", next: "loading" };
}

export type DashboardKind = "siswa" | "admin" | "institusi" | "pengawas";

/** The dashboard a role sees. The role always comes from the account the backend returned. */
export function dashboardKind(role: Role): DashboardKind {
  if (role === "Siswa") return "siswa";
  if (role === "Admin") return "admin";
  if (role === "Penyelenggara Ujian" || role === "Pihak Sekolah") return "institusi";
  return "pengawas";
}

/** Login/registration errors in Indonesian. A failed login never says whether the account exists. */
export function authErrorMessage(status: number, serverMessage: string, register = false): string {
  if (status === 0) return "Server EduAI tidak dapat dihubungi. Periksa koneksi Anda, lalu coba lagi.";
  if (status === 429) return "Terlalu banyak percobaan masuk. Coba lagi dalam 5 menit.";
  if (register) {
    // Registration (students only) explains itself; the backend messages are already Indonesian.
    if (status === 422) return "Periksa kembali nama, email, dan kata sandi.";
    return serverMessage || "Pendaftaran gagal. Coba lagi beberapa saat lagi.";
  }
  if (status === 401 || status === 403 || status === 404) return "Email atau kata sandi salah.";
  if (status === 400 || status === 422) return "Periksa kembali email dan kata sandi.";
  return "Masuk gagal. Coba lagi beberapa saat lagi.";
}

/** Screens each role may open (App.tsx shows "403 – Akses Ditolak" for any other). Every sidebar menu of a role
 *  (nav.ts) must be in its list; tests/nav.test.ts checks that. */
export const ALLOWED_SCREENS: Record<Role, string[]> = {
  Siswa: ["login", "dashboard", "my-exams", "seb-check", "consent", "device", "exam", "settings", "access-denied"],
  Pengawas: ["login", "dashboard", "sessions", "exam-detail", "waiting", "monitor", "student-detail", "detail", "timeline", "report", "indications", "history", "students", "meeting", "settings", "access-denied"],
  "Penyelenggara Ujian": ["login", "dashboard", "sessions", "exam-detail", "waiting", "monitor", "student-detail", "detail", "timeline", "report", "indications", "history", "students", "users", "meeting", "settings", "access-denied"],
  Admin: ["login", "dashboard", "sessions", "create", "exam-detail", "waiting", "seb-check", "consent", "device", "exam", "monitor", "student-detail", "detail", "timeline", "report", "indications", "history", "students", "users", "permissions", "configuration", "retention", "audit", "meeting", "settings", "access-denied"],
  "Pihak Sekolah": ["login", "dashboard", "sessions", "exam-detail", "detail", "report", "indications", "history", "users", "meeting", "settings", "access-denied"],
};
