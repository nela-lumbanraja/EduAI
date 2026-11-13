// Run: node --experimental-strip-types tests/routes.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { authErrorMessage, dashboardKind, initialScreen, landingAction } from "../src/routes.ts";

test("signed out: / opens the Beranda, /login opens Login", () => {
  assert.equal(initialScreen("/", false), "beranda");
  assert.equal(initialScreen("/login", false), "login");
  assert.equal(initialScreen("/login/", false), "login");
  assert.equal(initialScreen("/anything", false), "beranda");
});

test("signed in: /login (and every other path) goes to the dashboard", () => {
  for (const p of ["/login", "/login/", "/", "/anything"]) assert.equal(initialScreen(p, true), "dashboard");
});

test("Beranda signed out: Masuk shows the rocket, which leads to Login", () => {
  assert.deepEqual(landingAction(false), { label: "Masuk", next: "loading" });
});

test("Beranda signed in: 'Kembali ke Dasbor' goes straight to the dashboard, without the rocket", () => {
  assert.deepEqual(landingAction(true), { label: "Kembali ke Dasbor", next: "dashboard" });
});

test("'Kembali ke Dasbor' opens the dashboard of the account's role", () => {
  assert.equal(dashboardKind("Siswa"), "siswa");
  assert.equal(dashboardKind("Pengawas"), "pengawas");
  assert.equal(dashboardKind("Admin"), "admin");
  assert.equal(dashboardKind("Penyelenggara Ujian"), "institusi");
  assert.equal(dashboardKind("Pihak Sekolah"), "institusi");
});

test("login errors are Indonesian and never reveal whether the account exists", () => {
  const unknown = authErrorMessage(401, "Email atau kata sandi salah.");
  assert.equal(unknown, "Email atau kata sandi salah.");
  for (const s of [401, 403, 404]) assert.equal(authErrorMessage(s, "User not found / akun nonaktif"), unknown);
  assert.equal(authErrorMessage(422, "Data yang dikirim tidak valid: value is not a valid email address"), "Periksa kembali email dan kata sandi.");
  assert.match(authErrorMessage(429, ""), /Terlalu banyak percobaan/);
  assert.match(authErrorMessage(0, "Failed to fetch"), /tidak dapat dihubungi/);
  assert.equal(authErrorMessage(500, "Internal Server Error"), "Masuk gagal. Coba lagi beberapa saat lagi.");
});

test("registration keeps the backend's own (Indonesian) explanation", () => {
  assert.equal(authErrorMessage(400, "Pendaftaran mandiri hanya untuk akun siswa.", true), "Pendaftaran mandiri hanya untuk akun siswa.");
  assert.equal(authErrorMessage(422, "value is not a valid email address", true), "Periksa kembali nama, email, dan kata sandi.");
});
