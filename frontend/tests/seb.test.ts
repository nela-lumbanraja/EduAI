// Run: node --experimental-strip-types tests/seb.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { pageUrl, readSeb, sebLaunchLink } from "../src/seb.ts";

const CK = "A".repeat(64);

test("a normal browser is not SEB", async () => {
  const r = await readSeb({}, "Mozilla/5.0 Chrome/140.0");
  assert.deepEqual(r, { present: false, version: null, configKey: null, browserExamKey: null });
});

test("SEB for Windows 3.3.2+: keys are already set, read as lower-case hex", async () => {
  const r = await readSeb({ SafeExamBrowser: { version: "SafeExamBrowser_Windows_3.8.0", security: { configKey: CK, browserExamKey: "zz" } } }, "");
  assert.equal(r.present, true);
  assert.equal(r.configKey, CK.toLowerCase());
  assert.equal(r.browserExamKey, null);               // not a 64-char hex hash: not sent as a key
  assert.equal(r.version, "SafeExamBrowser_Windows_3.8.0");
});

test("SEB 3.0 macOS/iOS: updateKeys() is called before reading", async () => {
  const sec: { configKey?: string; updateKeys: (cb: () => void) => void } = { updateKeys: (cb) => { sec.configKey = CK; setTimeout(cb, 5); } };
  const r = await readSeb({ SafeExamBrowser: { security: sec } }, "");
  assert.equal(r.configKey, CK.toLowerCase());
});

test("updateKeys that never answers does not hang the page", async () => {
  const t0 = Date.now();
  const r = await readSeb({ SafeExamBrowser: { security: { updateKeys: () => undefined } } }, "");
  assert.ok(Date.now() - t0 < 3000 && r.present && r.configKey === null);
});

test("user agent alone only marks SEB as present, without keys", async () => {
  const r = await readSeb({}, "Mozilla/5.0 ... SEB/3.8.0");
  assert.equal(r.present, true);
  assert.equal(r.version, "SEB/3.8.0");
  assert.equal(r.configKey, null);
});

test("launch link: https -> sebs, http -> seb, anything else -> none", () => {
  assert.equal(sebLaunchLink("https://sekolah.sch.id/ujian.seb"), "sebs://sekolah.sch.id/ujian.seb");
  assert.equal(sebLaunchLink("http://192.168.1.5:8080/u.seb"), "seb://192.168.1.5:8080/u.seb");
  assert.equal(sebLaunchLink("javascript:alert(1)"), null);
  assert.equal(sebLaunchLink(""), null);
});

test("the page URL SEB hashes has no fragment", () => {
  assert.equal(pageUrl("http://localhost:5173/?x=1#top"), "http://localhost:5173/?x=1");
});

test("no SEB key or secret is hard-coded in the frontend", () => {
  for (const f of ["../src/seb.ts", "../src/api.ts", "../src/App.tsx"]) {
    const src = readFileSync(new URL(f, import.meta.url), "utf8");
    assert.ok(!/["'`][0-9a-f]{64}["'`]/i.test(src), `${f} contains a 64-hex literal`);
  }
});
