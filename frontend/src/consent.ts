// Student consent wording. Must be approved by the school before real exams (README, section 7b).
// The periods repeat the defaults of EDUAI_EVIDENCE_RETENTION_HOURS, EDUAI_EVIDENCE_HOLD_DAYS and
// EDUAI_REPORT_FRAME_RETENTION_HOURS: change this text when those settings change.
export type JitsiNoticeServer = { configured: boolean; domain: string | null; operator: "school" | "third_party" | null };

export const EVIDENCE_NOTICE = "Bukti berupa beberapa cuplikan gambar disimpan 24 jam, atau sampai laporan final dan paling lama 7 hari setelah ujian selesai; gambar pada laporan final dihapus 24 jam setelah finalisasi. Bukti hanya dapat dibuka oleh pengawas yang ditugaskan dan admin. Video penuh dan audio tidak pernah direkam atau disimpan.";
export const JITSI_NOTICE_UNKNOWN = "Bila ujian memakai Jitsi, video kamera melewati server Jitsi.";

/** Null when no Jitsi server is set. "Managed by the school" is only said when the backend declares it. */
export function jitsiNotice(server: JitsiNoticeServer | null): string | null {
  if (!server?.configured) return null;
  return server.operator === "school"
    ? "Bila ujian memakai Jitsi, video kamera melewati server Jitsi yang dikelola sekolah."
    : `Bila ujian memakai Jitsi, video kamera melewati server Jitsi pihak ketiga (${server.domain}), bukan server milik sekolah.`;
}
