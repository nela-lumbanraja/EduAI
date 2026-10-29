// Run: node --experimental-strip-types tests/notify.test.ts   (no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { loadSeen, newCaseIds, saveSeen, seenKey, type KeyValueStore } from "../src/notify.ts";

const memory = (): KeyValueStore & { data: Map<string, string> } => {
  const data = new Map<string, string>();
  return { data, getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v) };
};

/** Simulates the hook: one poll = load seen, compare, save. Returns ids that would pop up. */
function poll(store: KeyValueStore, user: number, caseIds: string[]) {
  const key = seenKey(user);
  const r = newCaseIds(loadSeen(store, key), caseIds);
  saveSeen(store, key, r.seen);
  return r.fresh;
}

test("first load is a silent baseline", () => {
  const s = memory();
  assert.deepEqual(poll(s, 7, ["c-a", "c-b"]), []);
});

test("a new case pops up exactly once, repeated polling adds nothing", () => {
  const s = memory();
  poll(s, 7, ["c-a"]);
  assert.deepEqual(poll(s, 7, ["c-b", "c-a"]), ["c-b"]);
  assert.deepEqual(poll(s, 7, ["c-b", "c-a"]), []);
  assert.deepEqual(poll(s, 7, ["c-b", "c-a"]), []);
});

test("repeated events in the same case (same case_id) never pop up again", () => {
  const s = memory();
  poll(s, 7, []);
  assert.deepEqual(poll(s, 7, ["c-a"]), ["c-a"]);
  for (let i = 0; i < 70; i++) assert.deepEqual(poll(s, 7, ["c-a"]), []);   // 70 more FACE_ABSENT events
});

test("a different indicator type is a different case and pops up", () => {
  const s = memory();
  poll(s, 7, ["c-face1"]);
  assert.deepEqual(poll(s, 7, ["c-phone1", "c-face1"]), ["c-phone1"]);
});

test("page refresh (new hook instance, same tab storage) shows no duplicates", () => {
  const s = memory();
  poll(s, 7, ["c-a"]);
  assert.deepEqual(poll(s, 7, ["c-b", "c-a"]), ["c-b"]);
  // refresh: in-memory state is gone, sessionStorage is kept
  assert.deepEqual(poll(s, 7, ["c-b", "c-a"]), []);
  // a case that arrived while the page was reloading still pops up once
  assert.deepEqual(poll(s, 7, ["c-c", "c-b", "c-a"]), ["c-c"]);
});

test("seen ids are kept per user", () => {
  const s = memory();
  poll(s, 7, ["c-a"]);
  assert.deepEqual(poll(s, 8, ["c-a"]), []);              // other user: own silent baseline
  assert.deepEqual(poll(s, 8, ["c-x", "c-a"]), ["c-x"]);
});

test("broken or blocked storage does not throw", () => {
  const broken: KeyValueStore = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("full"); } };
  assert.equal(loadSeen(broken, "k"), null);
  assert.doesNotThrow(() => saveSeen(broken, "k", new Set(["c-a"])));
  const s = memory(); s.setItem("k", "not json");
  assert.equal(loadSeen(s, "k"), null);
});

// ---------------------------------------------------------------- consolidated notifications
import { newSummaryKeys, notifiableCaseIds } from "../src/notify.ts";

test("ten occurrences of one behaviour = one case = one pop-up", () => {
  const s = memory();
  poll(s, 9, []);                                                    // baseline
  let popups = 0;
  for (let n = 1; n <= 10; n++) {                                    // the case grows to 10 occurrences
    popups += poll(s, 9, notifiableCaseIds([{ case_id: "c-phone", rule: { met: true } }])).length;
  }
  assert.equal(popups, 1);
});

test("a case pops up only when its rule is first met", () => {
  const s = memory();
  poll(s, 9, []);
  const head = (met: boolean) => [{ case_id: "c-head", rule: { met } }];
  assert.deepEqual(poll(s, 9, notifiableCaseIds(head(false))), []);  // 3 of 4 episodes: listed, no pop-up
  assert.deepEqual(poll(s, 9, notifiableCaseIds(head(false))), []);
  assert.deepEqual(poll(s, 9, notifiableCaseIds(head(true))), ["c-head"]);   // 4th episode: one pop-up
  assert.deepEqual(poll(s, 9, notifiableCaseIds(head(true))), []);
});

test("cases from an older backend without a rule still pop up", () => {
  assert.deepEqual(notifiableCaseIds([{ case_id: "c-x" }]), ["c-x"]);
});

test("a summary pops up once, also after a refresh, and old ones never", () => {
  const now = Date.parse("2026-10-30T03:00:00Z");
  const fresh = { exam_id: 1, created_at: "2026-10-30T02:50:00Z" };
  const old = { exam_id: 2, created_at: "2026-10-29T20:00:00Z" };
  const a = newSummaryKeys(null, [fresh, old], now);
  assert.deepEqual(a.fresh, ["s-1"]);
  const b = newSummaryKeys(a.seen, [fresh, old], now + 60000);      // next poll / page refresh
  assert.deepEqual(b.fresh, []);
});
