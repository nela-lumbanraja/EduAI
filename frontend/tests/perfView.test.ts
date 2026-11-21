// Run: node --experimental-strip-types --test tests/perfView.test.ts   (no extra dependencies)
// Admin panel "Performa AI": display rows from GET /api/ai/performance. Measured values only, no invented thresholds.
import assert from "node:assert/strict";
import { test } from "node:test";
import type { AIPerformance } from "../src/api.ts";
import { dropText, heaviest, lagText, msPair, perfRows, perfSummary, statusText } from "../src/perfView.ts";

const ms = (median: number, p90: number, n = 10) => ({ n, median, p90, max: p90 });

const DATA: AIPerformance = {
  time: "2026-11-20T10:00:00+00:00", scope: "backend", state: "READY", active_analyzers: 2, max_concurrent: 2,
  frames_received: 120, frames_dropped_busy: 2, fps_sum: 4,
  students: [
    { exam_id: 1, student_id: 7, student_name: "Alya Putri", exam_name: "UTS Basis Data", source: "browser",
      frames_received: 60, frames_dropped_busy: 2, frames: 58, fps: 2, status: { analyzed: 55, cannot_analyze: 3 },
      latency_ms: { total: ms(16.24, 83.2), face: ms(1.8, 2.7), objects: ms(28, 29.5, 4), clip: ms(38.5, 41.6, 4), landmarks: null },
      extra_ms: { queue_wait: ms(0.4, 12.25) }, capture_lag_ms: { raw: ms(5150, 5400), above_min: ms(20, 85.4), min_raw: 5150 } },
    { exam_id: 1, student_id: 9, source: "jitsi", frames_received: 0, frames_dropped_busy: 0 },
  ],
};

test("numbers are written the Indonesian way, median / p90", () => {
  assert.equal(msPair(ms(16.24, 83.2)), "16,2 / 83,2 ms");
  assert.equal(msPair(null), "—");
  assert.equal(msPair({ n: 0, median: 0, p90: 0, max: 0 }), "—");
});

test("the heaviest component is the one with the highest median, the total is not a component", () => {
  assert.equal(heaviest(DATA.students[0].latency_ms), "CLIP (buku) 38,5 ms");
  assert.equal(heaviest({ total: ms(90, 99) }), "—");
});

test("dropped frames, lag and status", () => {
  assert.equal(dropText(60, 2), "2 dari 60 (3,3 %)");
  assert.equal(dropText(0, 0), "—");
  assert.equal(lagText(DATA.students[0].capture_lag_ms), "+85 ms (p90)");     // laptop clock difference removed
  assert.equal(lagText(null), "—");                                           // older browser: no capture time
  assert.equal(statusText({ analyzed: 55, cannot_analyze: 3 }), "55 dianalisis, 3 tidak dapat dianalisis");
});

test("rows use names when the backend gives them, ids otherwise, and never fill missing values with 0", () => {
  const [a, b] = perfRows(DATA);
  assert.deepEqual([a.student, a.exam, a.source, a.fps, a.latency, a.queue], ["Alya Putri", "UTS Basis Data", "Browser", "2,00", "16,2 / 83,2 ms", "12,3 ms"]);
  assert.deepEqual([b.student, b.exam, b.source, b.fps, b.latency, b.heaviest, b.lag, b.dropped], ["Mahasiswa #9", "Ujian #1", "Jitsi", "—", "—", "—", "—", "—"]);
  assert.deepEqual(perfRows(null), []);
});

test("summary line", () => {
  assert.equal(perfSummary(DATA), "2 analisis aktif (maks. 2 bersamaan) · total 4,00 fps · frame dibuang 2 dari 120 (1,7 %)");
  assert.equal(perfSummary(null), "—");
});
