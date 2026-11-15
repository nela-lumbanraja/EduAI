// Sidebar menus per role, kept free of React so node:test can check them.
// The lists are the menus that already existed per role (nothing added or removed). "Profil" (screen "settings")
// moved from the icon list to the avatar at the bottom of the sidebar.
import type { Role } from "./routes.ts";

export type NavIconName =
  | "dashboard" | "calendar" | "monitor" | "bell" | "history" | "report" | "video" | "users" | "user-check"
  | "shield" | "sliders" | "archive" | "clipboard";
export type NavItem = { id: string; label: string; icon: NavIconName };

export const NAV_MENUS: Record<Role, NavItem[]> = {
  Siswa: [
    { id: "dashboard", label: "Dasbor", icon: "dashboard" },
    { id: "my-exams", label: "Ujian Saya", icon: "calendar" },
  ],
  Pengawas: [
    { id: "dashboard", label: "Dasbor", icon: "dashboard" },
    { id: "sessions", label: "Sesi Ujian", icon: "calendar" },
    { id: "monitor", label: "Monitoring", icon: "monitor" },
    { id: "indications", label: "Indikasi", icon: "bell" },
    { id: "history", label: "Riwayat", icon: "history" },
    { id: "report", label: "Laporan", icon: "report" },
    { id: "meeting", label: "Rapat Video", icon: "video" },
  ],
  "Penyelenggara Ujian": [
    { id: "dashboard", label: "Dasbor", icon: "dashboard" },
    { id: "sessions", label: "Sesi Ujian", icon: "calendar" },
    { id: "students", label: "Peserta", icon: "users" },
    { id: "users", label: "Pengawas", icon: "user-check" },
    { id: "student-accounts", label: "Akun Siswa", icon: "users" },     // from the former role Pihak Sekolah
    { id: "report", label: "Laporan", icon: "report" },
    { id: "meeting", label: "Rapat Video", icon: "video" },
  ],
  Admin: [
    { id: "dashboard", label: "Dasbor", icon: "dashboard" },
    { id: "sessions", label: "Daftar Ujian", icon: "calendar" },
    { id: "indications", label: "Indikasi", icon: "bell" },
    { id: "users", label: "Manajemen User", icon: "users" },
    { id: "configuration", label: "Konfigurasi", icon: "sliders" },
    { id: "retention", label: "Retensi Data", icon: "archive" },
    { id: "audit", label: "Audit Log", icon: "clipboard" },
    { id: "meeting", label: "Rapat Video", icon: "video" },
  ],
};

/** Screen "settings" is the profile page (title "Pengaturan"): reached from the avatar and from "Lainnya". */
export const PROFILE_SCREEN = "settings";

/** Whether menu `id` is the current page. Sub-pages count for their parent menu. */
export function isActive(active: string, id: string): boolean {
  if (active === id) return true;
  if (id === "sessions" && ["create", "exam-detail", "waiting"].includes(active)) return true;
  if (id === "monitor" && ["detail", "student-detail", "timeline"].includes(active)) return true;
  return false;
}

/** Phone (< 768 px): a drawer from the left, opened with the ☰ button in the header (replaces the bottom bar and
 *  its "Lainnya" sheet). It lists every menu of the role (NAV_MENUS, nothing added or removed), then the group
 *  "Akun" with what "Lainnya" held: the profile/settings page and Keluar. */
export type DrawerChild = { id: string; label: string };
export const DRAWER_ACCOUNT = {
  id: "akun", label: "Akun",
  children: [{ id: PROFILE_SCREEN, label: "Profil & Pengaturan" }, { id: "logout", label: "Keluar" }] as DrawerChild[],
};
export function drawerMenu(role: Role): { items: NavItem[]; account: typeof DRAWER_ACCOUNT } {
  return { items: NAV_MENUS[role], account: DRAWER_ACCOUNT };
}

/** Text of a red count badge, or null when there is nothing to show (0 hides the badge). */
export function badgeText(n: number | null | undefined): string | null {
  if (!n || n < 0) return null;
  return n > 99 ? "99+" : String(n);
}

/** Roles whose "Indikasi" menu shows the number of unreviewed cases. */
export const BADGE_ROLES: Role[] = ["Pengawas", "Penyelenggara Ujian", "Admin"];
