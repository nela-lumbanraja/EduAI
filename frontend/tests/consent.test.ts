// Run: node --experimental-strip-types tests/consent.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { EVIDENCE_NOTICE, jitsiNotice } from "../src/consent.ts";

test("no Jitsi sentence without a configured server", () => {
  assert.equal(jitsiNotice(null), null);
  assert.equal(jitsiNotice({ configured: false, domain: null, operator: null }), null);
});

test("the school is only named when the backend declares it", () => {
  const text = jitsiNotice({ configured: true, domain: "meet.sekolah.sch.id", operator: "school" });
  assert.ok(text?.includes("server Jitsi yang dikelola sekolah"));
});

test("any other server is stated as a third party, with its domain", () => {
  const text = jitsiNotice({ configured: true, domain: "alpha.example.net", operator: "third_party" }) ?? "";
  assert.ok(text.includes("pihak ketiga") && text.includes("alpha.example.net"));
  assert.ok(!text.includes("dikelola sekolah"));
  assert.ok((jitsiNotice({ configured: true, domain: "x.test", operator: null }) ?? "").includes("pihak ketiga"));
});

test("the evidence notice states periods and who can open it", () => {
  for (const part of ["24 jam", "paling lama 7 hari setelah ujian selesai", "24 jam setelah finalisasi", "pengawas yang ditugaskan dan admin"]) {
    assert.ok(EVIDENCE_NOTICE.includes(part), part);
  }
});
