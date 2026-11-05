// Run: node --experimental-strip-types tests/meetingIsolation.test.ts   (no extra dependencies)
// The "Rapat Video" page must have no route to the analysis: it may only ask the backend for the Jitsi server.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

const src = (name: string) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const app = src("App.tsx");

/** The source of one top-level function of App.tsx. */
function fn(name: string) {
  const start = app.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `${name} not found`);
  const end = app.indexOf("\nfunction ", start + 1);
  return app.slice(start, end < 0 ? undefined : end);
}
const meeting = ["MeetingPage", "MeetingTile", "JitsiVideo", "JitsiAudio"].map(fn).join("\n");

test("the meeting page only calls the Jitsi endpoints (settings, health, meeting token)", () => {
  const calls = new Set([...meeting.matchAll(/\bapi\.(\w+)/g)].map((m) => m[1]));
  assert.deepEqual([...calls].sort(), ["jitsiConfig", "jitsiHealth", "jitsiMeetingToken"]);
});

test("the meeting page has no frame, audio or presence path", () => {
  for (const banned of ["FrameUploader", "SpeechScorer", "uploadFrame", "uploadAudio", "startStudentMedia", "presence", "examId", "fetch("]) {
    assert.ok(!meeting.includes(banned), `${banned} must not appear in the meeting page`);
  }
});

test("jitsi.ts cannot reach the EduAI API", () => {
  const jitsi = src("jitsi.ts");
  assert.ok(!/from "\.\/(api|media|audio)"/.test(jitsi.replace(/import type .*\n/g, "")));
  assert.ok(!jitsi.includes("fetch(") && !jitsi.includes("XMLHttpRequest"));
});

test("FrameUploader is only created in the exam room", () => {
  const uses = app.split("new FrameUploader(").length - 1;
  assert.equal(uses, 1);
  assert.ok(fn("ExamRoom").includes("new FrameUploader("));
});

test("no Jitsi server is built into the frontend", () => {
  for (const f of readdirSync(new URL("../src/", import.meta.url))) {
    const text = src(f);
    assert.ok(!text.includes("alpha.jitsi.net") && !text.includes("meet.jit.si"), f);
    assert.ok(!text.includes("VITE_JITSI"), f);
  }
});
