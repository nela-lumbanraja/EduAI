// Admin panel "Performa AI" (Konfigurasi): turns GET /api/ai/performance into display rows. Pure functions, tested in
// tests/perfView.test.ts. Operational numbers only (speed of the analysis), never accuracy; no invented "slow/fast"
// thresholds: the panel shows the measured values and lets the admin judge them.
import type { AIPerformance, AIPerformanceStudent, MsSummary } from "./api";

export const COMPONENT_LABEL: Record<string, string> = {
  prepare: "Persiapan", quality: "Cek kualitas", face: "Wajah", landmarks: "Landmark wajah", objects: "Detektor objek", clip: "CLIP (buku)",
};
const SOURCE_LABEL: Record<string, string> = { browser: "Browser", jitsi: "Jitsi", livekit: "OpenVidu (cadangan browser)" };
const STATUS_LABEL: Record<string, string> = { analyzed: "dianalisis", cannot_analyze: "tidak dapat dianalisis", model_unavailable: "model tidak siap" };

export const num = (x: number, d = 1) => x.toFixed(d).replace(".", ",");

/** "16,2 / 83,2 ms" (median / p90), or "—" without samples. */
export function msPair(s: MsSummary | null | undefined): string {
  return s && s.n ? `${num(s.median)} / ${num(s.p90)} ms` : "—";
}

/** The component with the highest median latency in the window, e.g. "CLIP (buku) 38,5 ms". */
export function heaviest(latency: Record<string, MsSummary | null> | undefined): string {
  let best: [string, number] | null = null;
  for (const [k, s] of Object.entries(latency ?? {})) {
    if (k === "total" || !s || !s.n) continue;
    if (!best || s.median > best[1]) best = [k, s.median];
  }
  return best ? `${COMPONENT_LABEL[best[0]] ?? best[0]} ${num(best[1])} ms` : "—";
}

/** "2 dari 40 (5,0 %)": frames dropped because the previous frame was still being analysed. */
export function dropText(received: number, dropped: number): string {
  if (!received) return "—";
  return `${dropped} dari ${received} (${num((dropped / received) * 100)} %)`;
}

/** Variation of the camera -> server lag (the laptop clock difference removed), p90; "—" without browser timing. */
export function lagText(lag: AIPerformanceStudent["capture_lag_ms"]): string {
  const a = lag?.above_min;
  return a && a.n ? `+${num(a.p90, 0)} ms (p90)` : "—";
}

export function statusText(status: Record<string, number> | undefined): string {
  const parts = Object.entries(status ?? {}).filter(([, n]) => n).map(([k, n]) => `${n} ${STATUS_LABEL[k] ?? k}`);
  return parts.length ? parts.join(", ") : "—";
}

export type PerfRow = { key: string; student: string; exam: string; source: string; fps: string; latency: string; heaviest: string;
  queue: string; lag: string; dropped: string; status: string; frames: number };

export function perfRows(p: AIPerformance | null): PerfRow[] {
  return (p?.students ?? []).map((s) => ({
    key: `${s.exam_id}-${s.student_id}`,
    student: s.student_name ?? `Mahasiswa #${s.student_id}`,
    exam: s.exam_name ?? `Ujian #${s.exam_id}`,
    source: SOURCE_LABEL[s.source] ?? s.source,
    fps: s.fps == null ? "—" : num(s.fps, 2),
    latency: msPair(s.latency_ms?.total),
    heaviest: heaviest(s.latency_ms),
    queue: s.extra_ms?.queue_wait?.n ? `${num(s.extra_ms.queue_wait.p90)} ms` : "—",
    lag: lagText(s.capture_lag_ms),
    dropped: dropText(s.frames_received, s.frames_dropped_busy),
    status: statusText(s.status),
    frames: s.frames ?? 0,
  }));
}

/** Header line: "2 dari maks. 2 analisis bersamaan · total 4,00 fps · 2 dari 120 frame dibuang (1,7 %)". */
export function perfSummary(p: AIPerformance | null): string {
  if (!p) return "—";
  const fps = p.fps_sum == null ? "belum ada fps" : `total ${num(p.fps_sum, 2)} fps`;
  return `${p.active_analyzers} analisis aktif (maks. ${p.max_concurrent} bersamaan) · ${fps} · frame dibuang ${dropText(p.frames_received, p.frames_dropped_busy)}`;
}
