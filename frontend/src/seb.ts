// Safe Exam Browser (SEB) in the student's browser. The lockdown itself (full screen, no navigation,
// no switching to other apps, URL filter) comes from the SEB configuration, never from JavaScript here.
// This file only reads what SEB exposes; the backend compares it with the keys it alone knows.
// https://safeexambrowser.org/developer/seb-config-key.html

export type SebGlobal = {
  version?: string;
  security?: { configKey?: string; browserExamKey?: string; updateKeys?: (callback: () => void) => void };
};
export type SebReading = { present: boolean; version: string | null; configKey: string | null; browserExamKey: string | null };
export type SebState = "verified" | "not_seb" | "key_mismatch" | "url_mismatch" | "not_configured";

const UPDATE_TIMEOUT_MS = 2000;

/** SEB 3.0 for macOS/iOS fills the keys only after updateKeys(); SEB for Windows 3.3.2+ sets them at load. */
export async function readSeb(scope: { SafeExamBrowser?: SebGlobal } = globalThis as { SafeExamBrowser?: SebGlobal },
  userAgent: string = typeof navigator === "undefined" ? "" : navigator.userAgent): Promise<SebReading> {
  const g = scope.SafeExamBrowser;
  const sec = g?.security;
  if (sec?.updateKeys && !(sec.configKey || sec.browserExamKey)) {
    await new Promise<void>((resolve) => {
      const t = setTimeout(resolve, UPDATE_TIMEOUT_MS);
      try { sec.updateKeys!(() => { clearTimeout(t); resolve(); }); } catch { clearTimeout(t); resolve(); }
    });
  }
  const hex = (v: unknown) => (typeof v === "string" && /^[0-9a-fA-F]{64}$/.test(v) ? v.toLowerCase() : null);
  // The user agent is only a hint ("SEB/x.y"): anyone can fake it, so the backend never relies on it.
  const uaVersion = /\bSEB\/([\w.]+)/.exec(userAgent)?.[1] ?? null;
  return {
    present: !!g || uaVersion !== null,
    version: g?.version ?? (uaVersion ? `SEB/${uaVersion}` : null),
    configKey: hex(sec?.configKey),
    browserExamKey: hex(sec?.browserExamKey),
  };
}

/** Link that opens SEB with the exam configuration: https -> sebs, http -> seb. */
export function sebLaunchLink(configUrl: string | null | undefined): string | null {
  if (!configUrl) return null;
  const m = /^(https?):\/\/(.+)$/i.exec(configUrl.trim());
  if (!m) return null;
  return `${m[1].toLowerCase() === "https" ? "sebs" : "seb"}://${m[2]}`;
}

/** The page URL SEB hashes: absolute, without the fragment. */
export const pageUrl = (href: string) => href.split("#")[0];

export const SEB_STATE_LABEL: Record<SebState, string> = {
  verified: "SEB terverifikasi",
  not_seb: "Bukan Safe Exam Browser",
  key_mismatch: "Konfigurasi SEB tidak sesuai",
  url_mismatch: "Alamat halaman tidak diizinkan",
  not_configured: "Pengaturan SEB belum lengkap",
};
