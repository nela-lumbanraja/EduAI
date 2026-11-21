// Student consent wording. Must be approved by the school before real exams (README, section 7b).
// The storage periods are NOT written here by hand any more (since 20 Nov 2026): evidenceNotice() builds the sentence
// from the values the backend really uses (GET /api/ai/health: EDUAI_EVIDENCE_RETENTION_HOURS,
// EDUAI_EVIDENCE_HOLD_DAYS, EDUAI_REPORT_FRAME_RETENTION_HOURS), so the text stays true when .env changes.
export type JitsiNoticeServer = { configured: boolean; domain: string | null; operator: "school" | "third_party" | null };
export type RetentionPolicy = { evidence_retention_hours: number; evidence_hold_days: number; report_frame_retention_hours: number };

export const CONSENT_VERSION = "2026-11-v3";
export const DEFAULT_POLICY: RetentionPolicy = { evidence_retention_hours: 24, evidence_hold_days: 7, report_frame_retention_hours: 24 };
const LONG_HOURS = 24 * 365;                 // a year or more: said as "not deleted automatically", not as a number
const ACCESS = "Bukti hanya dapat dibuka oleh pengawas yang ditugaskan dan admin. Video penuh dan audio tidak pernah direkam atau disimpan.";

const period = (hours: number) => (hours >= 72 && hours % 24 === 0 ? `${hours / 24} hari` : `${+hours.toFixed(1)} jam`);

/** The storage sentence for the policy in force. Default policy -> exactly the wording approved in Oct 2026.
 *  null (the policy could not be loaded) -> says so instead of guessing a period. */
export function evidenceNotice(p: RetentionPolicy | null): string {
  if (!p) return "Bukti berupa beberapa cuplikan gambar disimpan sesuai pengaturan masa simpan sistem; rinciannya tidak dapat dimuat saat ini, tanyakan kepada pengawas. " + ACCESS;
  const r = p.evidence_retention_hours, h = p.evidence_hold_days * 24, f = p.report_frame_retention_hours;
  const kept = r >= LONG_HOURS ? "disimpan tanpa penghapusan otomatis (sesuai pengaturan sistem saat ini)"
    : h >= LONG_HOURS ? `disimpan ${period(r)}, atau sampai laporan final`
    : `disimpan ${period(r)}, atau sampai laporan final dan paling lama ${period(h)} setelah ujian selesai`;
  const report = f >= LONG_HOURS ? "gambar pada laporan final juga tidak dihapus otomatis" : `gambar pada laporan final dihapus ${period(f)} setelah finalisasi`;
  return `Bukti berupa beberapa cuplikan gambar ${kept}; ${report}. ${ACCESS}`;
}

/** Stored with the consent (consents.notice_version, max 40 chars): which wording AND which periods were shown. */
export function noticeVersion(p: RetentionPolicy | null): string {
  return p ? `${CONSENT_VERSION};r${p.evidence_retention_hours};h${p.evidence_hold_days};f${p.report_frame_retention_hours}`
    : `${CONSENT_VERSION};masa-simpan-tidak-dimuat`;
}

export const EVIDENCE_NOTICE = evidenceNotice(DEFAULT_POLICY);
export const AI_ANALYSIS_NOTICE = "Keberadaan wajah, jumlah orang, arah kepala, gerak mulut, dan objek menyerupai ponsel atau buku. Suara hanya dianalisis jika Anda menyetujui pilihan di bawah.";
export const AUDIO_NOTICE = "Model AI di browser ini menilai apakah terdengar suara bicara, bisikan, musik/TV, atau suara kertas/halaman buku. Yang dikirim ke EduAI hanya empat angka skor; audio tidak direkam, tidak disimpan, dan tidak dikirim. Jika terdengar suara bicara saat mulut Anda tampak diam, bisikan, atau suara kertas/halaman buku, pengawas menerima indikasi untuk ditinjau, bukan keputusan pelanggaran. Suara orang lain di sekitar Anda juga ikut dinilai, jadi beri tahu mereka. Ujian tetap dapat diikuti tanpa pilihan ini.";
export const JITSI_NOTICE_UNKNOWN = "Bila ujian memakai Jitsi, video kamera melewati server Jitsi.";

/** Null when no Jitsi server is set. "Managed by the school" is only said when the backend declares it. */
export function jitsiNotice(server: JitsiNoticeServer | null): string | null {
  if (!server?.configured) return null;
  return server.operator === "school"
    ? "Bila ujian memakai Jitsi, video kamera melewati server Jitsi yang dikelola program studi."
    : `Bila ujian memakai Jitsi, video kamera melewati server Jitsi pihak ketiga (${server.domain}), bukan server milik program studi.`;
}
