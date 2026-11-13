// Run: node --experimental-strip-types tests/time.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { clockWib, formatWib, greetingWib, longDateWib, NO_DATA, parseUtc, timeAgo } from "../src/time.ts";

const NOW = Date.parse("2026-11-05T07:00:00Z");      // 14.00 WIB
const ago = (ms: number) => new Date(NOW - ms).toISOString();
const MIN = 60_000, HOUR = 60 * MIN, DAY = 24 * HOUR;

test("backend UTC is shown in WIB (UTC+7), whatever the computer's time zone", () => {
  assert.equal(formatWib(Date.parse("2026-11-05T00:30:00+00:00")), "5 Nov 2026, 07.30 WIB");
  assert.equal(formatWib(Date.parse("2026-11-04T22:57:44.000+00:00")), "5 Nov 2026, 05.57 WIB");   // crosses midnight
  assert.equal(formatWib(Date.parse("2026-12-31T17:00:00Z")), "1 Jan 2027, 00.00 WIB");             // crosses the year
});

test("a timestamp without an offset is UTC, never local time", () => {
  assert.equal(parseUtc("2026-11-05 07:00:00"), NOW);
  assert.equal(parseUtc("2026-11-05T07:00:00"), NOW);
  assert.equal(parseUtc("2026-11-05T14:00:00+07:00"), NOW);
});

test("relative steps: baru saja, menit, jam, hari", () => {
  assert.equal(timeAgo(ago(20_000), NOW), "baru saja");
  assert.equal(timeAgo(ago(5 * MIN), NOW), "5 mnt lalu");
  assert.equal(timeAgo(ago(59 * MIN), NOW), "59 mnt lalu");
  assert.equal(timeAgo(ago(3 * HOUR + 10 * MIN), NOW), "3 jam lalu");
  assert.equal(timeAgo(ago(2 * DAY), NOW), "2 hari lalu");
});

test("old data shows the date and time, not thousands of minutes (the old '2864 mnt lalu')", () => {
  const t = ago(2864 * MIN);                             // 1 day 23 hours
  assert.equal(timeAgo(t, NOW), "1 hari lalu");
  assert.equal(timeAgo(ago(10 * DAY), NOW), "26 Okt 2026, 14.00 WIB");
  assert.doesNotMatch(timeAgo(ago(30 * DAY), NOW), /mnt/);
});

test("a finished session always shows the date and time, even for recent data", () => {
  assert.equal(timeAgo(ago(5 * MIN), NOW, { finished: true }), "5 Nov 2026, 13.55 WIB");
});

test("empty or invalid data says 'Belum ada data'", () => {
  for (const v of [null, undefined, "", "   ", "bukan tanggal"]) assert.equal(timeAgo(v, NOW), NO_DATA);
});

test("a time in the future (beyond clock skew) shows the date; small skew is 'baru saja'", () => {
  assert.equal(timeAgo(new Date(NOW + 30_000).toISOString(), NOW), "baru saja");
  assert.equal(timeAgo(new Date(NOW + 2 * HOUR).toISOString(), NOW), "5 Nov 2026, 16.00 WIB");
});

test("top bar clock and greeting follow WIB, not the computer's time zone", () => {
  assert.equal(clockWib(Date.parse("2026-11-04T19:56:10Z")), "02.56.10");
  assert.equal(clockWib(NOW), "14.00.00");
  assert.equal(greetingWib(NOW), "Selamat siang");                                  // 14.00 WIB
  assert.equal(greetingWib(Date.parse("2026-11-05T01:00:00Z")), "Selamat pagi");    // 08.00 WIB
  assert.equal(greetingWib(Date.parse("2026-11-05T10:30:00Z")), "Selamat sore");    // 17.30 WIB
  assert.equal(greetingWib(Date.parse("2026-11-05T13:00:00Z")), "Selamat malam");   // 20.00 WIB
});

test("long WIB date for the dashboard header", () => {
  assert.equal(longDateWib(NOW), "Kamis, 5 November 2026");
  assert.equal(longDateWib(Date.parse("2026-11-05T18:00:00Z")), "Jumat, 6 November 2026");   // already Friday in WIB
});
