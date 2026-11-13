// Time display for staff pages. Backend timestamps are UTC; everything is shown in WIB (UTC+7, no daylight
// saving), independent of the computer's own time zone. No React here, so node:test can check it.

export const NO_DATA = "Belum ada data";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const WIB_OFFSET_MS = 7 * 3600_000;
/** Up to this many days "x hari lalu"; older data shows its date and time. */
export const RECENT_DAYS = 7;

/** Milliseconds since the epoch for a backend timestamp, or null. A timestamp without an offset is UTC too. */
export function parseUtc(iso?: string | null): number | null {
  const s = (iso ?? "").trim().replace(" ", "T");
  if (!s) return null;
  const t = Date.parse(/(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(s) ? s : `${s}Z`);
  return Number.isFinite(t) ? t : null;
}

const pad = (n: number) => String(n).padStart(2, "0");

/** "5 Nov 2026, 07.30 WIB" */
export function formatWib(ms: number): string {
  const d = new Date(ms + WIB_OFFSET_MS);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${pad(d.getUTCHours())}.${pad(d.getUTCMinutes())} WIB`;
}

/** Relative time ("baru saja", "x mnt lalu", "x jam lalu", "x hari lalu"), then the WIB date and time.
 *  `finished`: the session has ended, so always the date and time, never minutes. */
export function timeAgo(iso: string | null | undefined, now: number = Date.now(), opts: { finished?: boolean } = {}): string {
  const t = parseUtc(iso);
  if (t === null) return NO_DATA;
  const s = (now - t) / 1000;
  if (opts.finished || s < -60) return formatWib(t);      // ended session, or a time in the future (beyond clock skew)
  if (s < 60) return "baru saja";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} mnt lalu`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} jam lalu`;
  const days = Math.floor(h / 24);
  return days < RECENT_DAYS ? `${days} hari lalu` : formatWib(t);
}

/** Wall clock in WIB: "14.05.09". */
export function clockWib(now: number = Date.now()): string {
  const d = new Date(now + WIB_OFFSET_MS);
  return `${pad(d.getUTCHours())}.${pad(d.getUTCMinutes())}.${pad(d.getUTCSeconds())}`;
}

/** Greeting by the WIB hour. */
export function greetingWib(now: number = Date.now()): string {
  const h = new Date(now + WIB_OFFSET_MS).getUTCHours();
  return h < 11 ? "Selamat pagi" : h < 15 ? "Selamat siang" : h < 18 ? "Selamat sore" : "Selamat malam";
}

/** "Kamis, 5 November 2026" in WIB. */
export function longDateWib(now: number = Date.now()): string {
  const days = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
  const months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
  const d = new Date(now + WIB_OFFSET_MS);
  return `${days[d.getUTCDay()]}, ${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}
