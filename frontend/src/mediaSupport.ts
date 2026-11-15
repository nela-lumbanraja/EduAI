// Camera/microphone rules shared by the device check and the exam room, kept free of React and the DOM so they can be
// unit tested (tests/mediaSupport.test.ts). Android Chrome and iOS Safari differ mostly in how permission is given
// back after a refusal and in when the camera is stopped by the system; the messages below say what to do on each.

export type Platform = "android" | "ios" | "desktop";

/** Phone platform from the user agent. iPadOS 13+ reports itself as a Mac; touch points tell them apart. */
export function detectPlatform(ua: string, maxTouchPoints = 0): Platform {
  if (/Android/i.test(ua)) return "android";
  if (/iPhone|iPad|iPod/i.test(ua) || (/Macintosh/i.test(ua) && maxTouchPoints > 1)) return "ios";
  return "desktop";
}

/** Browsers inside apps (WhatsApp, Instagram, Facebook, LINE, TikTok...) often have no or a broken camera API. */
export function isInAppBrowser(ua: string): boolean {
  return /FBAN|FBAV|Instagram|Line\/|WhatsApp|TikTok|musical_ly|Twitter|; wv\)|GSA\//i.test(ua);
}

/** Front camera first (phones), a size every phone camera can give, and a frame rate that keeps uploads light. */
export const CAMERA = { facingMode: { ideal: "user" }, width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15, max: 24 } } as const;

/** What to ask getUserMedia for, from the most to the least specific. An older phone camera that cannot meet a
 *  constraint (OverconstrainedError) or a phone without a working microphone still gets the camera. */
export function captureAttempts(): MediaStreamConstraints[] {
  return [
    { video: { ...CAMERA }, audio: true },
    { video: { facingMode: "user" }, audio: true },
    { video: { facingMode: "user" }, audio: false },
  ];
}

/** Errors after which a simpler request may still succeed. A refusal is final: asking again would only repeat it. */
export function retryWithSimplerRequest(name: string | undefined): boolean {
  return name === "OverconstrainedError" || name === "NotFoundError" || name === "NotReadableError" || name === "AbortError";
}

const PERMISSION_HELP: Record<Platform, string> = {
  android: "Di Chrome Android: ketuk ikon di kiri alamat situs → Izin → izinkan Kamera dan Mikrofon, lalu ketuk Coba lagi.",
  ios: "Di iPhone: ketuk aA di bilah alamat Safari → Pengaturan Situs Web → izinkan Kamera dan Mikrofon (atau Pengaturan → Safari → Kamera/Mikrofon), lalu ketuk Coba lagi.",
  desktop: "Klik ikon kamera atau gembok di bilah alamat, izinkan Kamera dan Mikrofon, lalu klik Coba lagi.",
};

/** Indonesian message for a failed camera/microphone request, with the steps for the student's own phone. */
export function mediaErrorText(name: string | undefined, secure: boolean, platform: Platform, inApp = false): string {
  if (!secure) return "Kamera hanya dapat dipakai lewat alamat HTTPS (atau http://localhost). Buka EduAI melalui alamat https:// dari sekolah.";
  if (name === "UnsupportedError" || name === "TypeError")
    return inApp ? "Browser di dalam aplikasi ini (misalnya WhatsApp atau Instagram) tidak mendukung kamera. Salin tautan EduAI lalu buka di Chrome (Android) atau Safari (iPhone)."
      : "Browser ini tidak mendukung kamera/mikrofon. Buka EduAI di Chrome (Android) atau Safari (iPhone) versi terbaru.";
  if (name === "NotAllowedError" || name === "SecurityError") return `Izin kamera/mikrofon ditolak. ${PERMISSION_HELP[platform]}`;
  if (name === "NotFoundError" || name === "OverconstrainedError") return "Kamera tidak ditemukan pada perangkat ini. Ujian memerlukan kamera yang berfungsi.";
  if (name === "NotReadableError" || name === "AbortError")
    return platform === "desktop" ? "Kamera sedang dipakai aplikasi lain. Tutup aplikasi tersebut lalu coba lagi."
      : "Kamera sedang dipakai aplikasi lain (misalnya panggilan video, Kamera, atau WhatsApp). Tutup aplikasi tersebut, kembali ke sini, lalu ketuk Coba lagi.";
  return "Kamera/mikrofon tidak dapat dibuka. Coba lagi; jika tetap gagal, muat ulang halaman.";
}

/** Fallback for browsers without requestVideoFrameCallback: frames are decoded (videoWidth > 0, readyState >= 2) and
 *  the playback time advanced since the previous check. */
export function frameAdvanced(prevTime: number, time: number, readyState: number, videoWidth: number): boolean {
  return readyState >= 2 && videoWidth > 0 && time > prevTime;
}

/** A camera counts as working only when its track is live and not muted (iOS mutes it while Safari is in the
 *  background or during a call) and new frames arrived since the last check. A granted permission is not enough. */
export function cameraWorking(track: { readyState: string; muted: boolean } | undefined, newFrames: boolean): boolean {
  return !!track && track.readyState === "live" && !track.muted && newFrames;
}

/** Student-facing state of the broadcast to the supervisor. */
export type BroadcastState = "off" | "connecting" | "reconnecting" | "sending" | "received";

export function broadcastText(s: BroadcastState): string {
  return s === "received" ? "Video Anda sudah diterima sistem pemantauan"
    : s === "sending" ? "Video terkirim ke server, menunggu pengawas membuka pemantauan"
    : s === "reconnecting" ? "Menyambung ulang siaran video…"
    : s === "connecting" ? "Menyambungkan siaran video…" : "";
}
