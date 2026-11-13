// Run: node --experimental-strip-types --test tests/nav.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { BADGE_ROLES, NAV_MENUS, PROFILE_SCREEN, badgeText, isActive, mobileSplit } from "../src/nav.ts";

const labels = (role: keyof typeof NAV_MENUS) => NAV_MENUS[role].map((m) => m.label);

test("menus per role are the ones that already existed (Profil moved to the avatar)", () => {
  assert.deepEqual(labels("Siswa"), ["Dasbor", "Ujian Saya"]);                     // no "Rapat Video" for students
  assert.deepEqual(labels("Pengawas"), ["Dasbor", "Sesi Ujian", "Monitoring", "Indikasi", "Riwayat", "Laporan", "Rapat Video"]);
  assert.deepEqual(labels("Penyelenggara Ujian"), ["Dasbor", "Sesi Ujian", "Peserta", "Pengawas", "Laporan", "Rapat Video"]);
  assert.deepEqual(labels("Admin"), ["Dasbor", "Daftar Ujian", "Indikasi", "Manajemen User", "Role & Izin", "Konfigurasi", "Retensi Data", "Audit Log", "Rapat Video"]);
  assert.deepEqual(labels("Pihak Sekolah"), ["Dasbor", "Informasi Sesi", "Indikasi Tervalidasi", "Laporan Final", "Akun Siswa", "Rapat Video"]);
  for (const items of Object.values(NAV_MENUS)) {
    assert.ok(items.every((m) => m.id !== PROFILE_SCREEN), "Profil is the avatar, not an icon");
    assert.equal(new Set(items.map((m) => m.id)).size, items.length, "no duplicates");
  }
});

test("active menu: the page itself and its sub-pages", () => {
  assert.equal(isActive("indications", "indications"), true);
  assert.equal(isActive("exam-detail", "sessions"), true);
  assert.equal(isActive("create", "sessions"), true);
  assert.equal(isActive("student-detail", "monitor"), true);
  assert.equal(isActive("report", "monitor"), false);
  assert.equal(isActive("dashboard", "sessions"), false);
});

test("badge: hidden at 0, number otherwise, capped at 99+; only roles that see unreviewed cases", () => {
  assert.equal(badgeText(0), null);
  assert.equal(badgeText(null), null);
  assert.equal(badgeText(undefined), null);
  assert.equal(badgeText(3), "3");
  assert.equal(badgeText(120), "99+");
  assert.deepEqual(BADGE_ROLES, ["Pengawas", "Penyelenggara Ujian", "Admin"]);
});

test("phone bottom bar: at most 4 menus + 'Lainnya' (5 places); the rest goes under 'Lainnya'", () => {
  for (const [role, items] of Object.entries(NAV_MENUS)) {
    const { bar, more } = mobileSplit(items);
    assert.ok(bar.length + 1 <= 5, role);
    assert.deepEqual([...bar, ...more], items, role);
  }
  assert.deepEqual(mobileSplit(NAV_MENUS.Pengawas).more.map((m) => m.label), ["Riwayat", "Laporan", "Rapat Video"]);
  assert.deepEqual(mobileSplit(NAV_MENUS.Siswa).more, []);
});

test("every sidebar menu (and the profile page) can be opened by its role, so no menu leads to 403", async () => {
  const { ALLOWED_SCREENS } = await import("../src/routes.ts");
  for (const [role, menus] of Object.entries(NAV_MENUS) as [keyof typeof NAV_MENUS, typeof NAV_MENUS.Siswa][]) {
    for (const m of menus) assert.ok(ALLOWED_SCREENS[role].includes(m.id), `${role}: menu "${m.label}" (${m.id}) is not allowed`);
    assert.ok(ALLOWED_SCREENS[role].includes(PROFILE_SCREEN), `${role}: Profil`);
  }
  assert.ok(ALLOWED_SCREENS["Pihak Sekolah"].includes("users"));                 // Akun Siswa
});
