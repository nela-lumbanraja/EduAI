// Pop-up de-duplication for grouped indication cases (pure logic, no React, so it can be unit-tested).
//
// Rule: one pop-up per new case_id. A repeated event that joins an existing case keeps the same
// case_id, so it never raises another pop-up. A different indicator type, student or exam, or a
// repeat after a long gap, is a different case_id and does raise one.
// The ids already seen are kept in sessionStorage (per user), so a page refresh or normal polling
// does not show old cases again. The first load in a fresh browser tab is a silent baseline.

export type KeyValueStore = { getItem(k: string): string | null; setItem(k: string, v: string): void };

const MAX_REMEMBERED = 5000;

export const seenKey = (userId: number | string) => `eduai.seenCases.${userId}`;

/** Ids seen before, or null when nothing was stored yet (fresh tab / storage unavailable). */
export function loadSeen(store: KeyValueStore | null, key: string): Set<string> | null {
  try {
    const raw = store?.getItem(key);
    if (!raw) return null;
    const ids = JSON.parse(raw);
    return Array.isArray(ids) ? new Set(ids.filter((x) => typeof x === "string")) : null;
  } catch {
    return null;
  }
}

export function saveSeen(store: KeyValueStore | null, key: string, seen: Set<string>) {
  try {
    store?.setItem(key, JSON.stringify([...seen].slice(-MAX_REMEMBERED)));
  } catch { /* storage full or blocked: de-duplication still works in memory for this page */ }
}

/**
 * Compare the current case list with what was seen. `prev === null` means "no baseline yet":
 * everything is recorded as seen and nothing pops up (same behaviour as before for a first load).
 * Returns the case ids that deserve a pop-up, newest first as given, and the updated seen set.
 */
export function newCaseIds(prev: Set<string> | null, currentIds: string[]): { fresh: string[]; seen: Set<string> } {
  const seen = new Set(prev ?? []);
  const fresh = prev === null ? [] : currentIds.filter((id) => !seen.has(id));
  currentIds.forEach((id) => seen.add(id));
  return { fresh, seen };
}

// ---------------------------------------------------------------- consolidated notifications
// One case = one student + one behaviour for the whole exam (backend default). Its occurrences keep
// accumulating inside it; the supervisor gets ONE pop-up for it, at the moment the configured rule is
// first met (e.g. 4 repeated head-turn episodes within an hour). Cases below their rule are still
// listed on the Indikasi page - they only do not pop up yet.

/** Case ids that may raise a pop-up (rule met; an older backend without `rule` counts as met). */
export function notifiableCaseIds(cases: { case_id: string; rule?: { met: boolean } | null }[]): string[] {
  return cases.filter((c) => c.rule?.met !== false).map((c) => c.case_id);
}

export const seenSummariesKey = (userId: number | string) => `eduai.seenSummaries.${userId}`;
export const summaryKey = (s: { exam_id: number }) => `s-${s.exam_id}`;     // the backend makes one per exam
export const SUMMARY_POPUP_MAX_AGE_MS = 2 * 60 * 60 * 1000;

/**
 * Exam summaries that deserve a pop-up: not seen before in this browser (kept in localStorage, so a
 * summary made while the supervisor was away still pops once) and created at most 2 hours ago (old
 * exams never flood a fresh browser). Returns fresh keys and the updated seen set.
 */
export function newSummaryKeys(prev: Set<string> | null, summaries: { exam_id: number; created_at: string | null }[],
                               nowMs: number): { fresh: string[]; seen: Set<string> } {
  const seen = new Set(prev ?? []);
  const fresh: string[] = [];
  for (const s of summaries) {
    const k = summaryKey(s);
    const age = s.created_at ? nowMs - Date.parse(s.created_at) : Infinity;
    if (!seen.has(k) && age >= 0 && age <= SUMMARY_POPUP_MAX_AGE_MS) fresh.push(k);
    seen.add(k);
  }
  return { fresh, seen };
}
