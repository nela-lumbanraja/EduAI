// Run: node --experimental-strip-types tests/consent.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { AI_ANALYSIS_NOTICE, AUDIO_NOTICE, CONSENT_VERSION, DEFAULT_POLICY, EVIDENCE_NOTICE, evidenceNotice, jitsiNotice, noticeVersion } from "../src/consent.ts";

test("no Jitsi sentence without a configured server", () => {
  assert.equal(jitsiNotice(null), null);
  assert.equal(jitsiNotice({ configured: false, domain: null, operator: null }), null);
});

test("the school is only named when the backend declares it", () => {
  const text = jitsiNotice({ configured: true, domain: "meet.prodi.ac.id", operator: "school" });
  assert.ok(text?.includes("server Jitsi yang dikelola program studi"));
});

test("any other server is stated as a third party, with its domain", () => {
  const text = jitsiNotice({ configured: true, domain: "alpha.example.net", operator: "third_party" }) ?? "";
  assert.ok(text.includes("pihak ketiga") && text.includes("alpha.example.net"));
  assert.ok(!text.includes("dikelola program studi"));
  assert.ok((jitsiNotice({ configured: true, domain: "x.test", operator: null }) ?? "").includes("pihak ketiga"));
});

test("the evidence notice states periods and who can open it", () => {
  for (const part of ["24 jam", "paling lama 7 hari setelah ujian selesai", "24 jam setelah finalisasi", "pengawas yang ditugaskan dan admin"]) {
    assert.ok(EVIDENCE_NOTICE.includes(part), part);
  }
});

// ---------------------------------------------------------------- 20 Nov 2026: periods from the settings in force
const OCT_2026 = "Bukti berupa beberapa cuplikan gambar disimpan 24 jam, atau sampai laporan final dan paling lama 7 hari setelah ujian selesai; gambar pada laporan final dihapus 24 jam setelah finalisasi. Bukti hanya dapat dibuka oleh pengawas yang ditugaskan dan admin. Video penuh dan audio tidak pernah direkam atau disimpan.";

test("default settings give exactly the approved October 2026 wording", () => {
  assert.equal(evidenceNotice(DEFAULT_POLICY), OCT_2026);
  assert.equal(EVIDENCE_NOTICE, OCT_2026);
});

test("other periods are written as they are configured", () => {
  const t = evidenceNotice({ evidence_retention_hours: 48, evidence_hold_days: 14, report_frame_retention_hours: 72 });
  assert.ok(t.includes("disimpan 48 jam") && t.includes("paling lama 14 hari setelah ujian selesai") && t.includes("dihapus 3 hari setelah finalisasi"), t);
});

test("trial settings (no automatic deletion) are not described as 24 hours", () => {
  const t = evidenceNotice({ evidence_retention_hours: 876000, evidence_hold_days: 36500, report_frame_retention_hours: 876000 });
  assert.ok(t.includes("tanpa penghapusan otomatis") && t.includes("juga tidak dihapus otomatis"), t);
  assert.ok(!/24 jam|7 hari|876000|36500/.test(t), t);
  const holdOnly = evidenceNotice({ evidence_retention_hours: 24, evidence_hold_days: 36500, report_frame_retention_hours: 24 });
  assert.ok(holdOnly.includes("disimpan 24 jam, atau sampai laporan final;") && !holdOnly.includes("paling lama"), holdOnly);
});

test("an unknown policy is said to be unknown, never guessed", () => {
  const t = evidenceNotice(null);
  assert.ok(t.includes("tidak dapat dimuat") && !/\d+ (jam|hari)/.test(t), t);
});

test("the stored notice version records the periods that were shown, within 40 characters", () => {
  const v = noticeVersion({ evidence_retention_hours: 876000, evidence_hold_days: 36500, report_frame_retention_hours: 876000 });
  assert.equal(v, `${CONSENT_VERSION};r876000;h36500;f876000`);
  assert.ok(v.length <= 40 && noticeVersion(null).length <= 40);
});

test("AI and audio texts name every signal that can become an indication", () => {
  assert.ok(AI_ANALYSIS_NOTICE.includes("ponsel atau buku"));
  for (const part of ["bisikan", "kertas/halaman buku", "empat angka skor", "audio tidak direkam"]) assert.ok(AUDIO_NOTICE.includes(part), part);
  assert.ok(!AUDIO_NOTICE.includes("tiga angka skor"));
});
