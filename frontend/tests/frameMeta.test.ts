// Run: node --experimental-strip-types tests/frameMeta.test.ts   (no extra dependencies)
// G-F1 (20 Nov 2026): timing fields sent with every AI frame. Measurements only; implausible values are left out.
import assert from "node:assert/strict";
import { test } from "node:test";
import { frameTimingFields } from "../src/mediaSupport.ts";

test("all fields for a normal frame", () => {
  assert.deepEqual(frameTimingFields(1_795_000_000_123.4, 1000, 1012.25, 180.04),
    { captured_at: "1795000000123", client_age_ms: "12.3", prev_rtt_ms: "180.0" });
});

test("first frame has no round trip yet", () => {
  assert.deepEqual(Object.keys(frameTimingFields(1_795_000_000_000, 5, 9, null)), ["captured_at", "client_age_ms"]);
});

test("implausible values are left out, never sent as 0", () => {
  const f = frameTimingFields(Number.NaN, 100, 50, -3);           // clock missing, time went backwards, negative rtt
  assert.deepEqual(f, {});
  assert.equal(frameTimingFields(1, 0, 70_000, 999_999).client_age_ms, undefined);
  assert.equal(frameTimingFields(1, 0, 1, 999_999).prev_rtt_ms, undefined);
});
