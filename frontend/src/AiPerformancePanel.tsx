// Admin only (Konfigurasi > Performa AI): live speed of the AI analysis per student, from GET /api/ai/performance.
// Presentational: App.tsx polls the endpoint and passes the result; the numbers are prepared by perfView.ts.
import type { AIPerformance } from "./api";
import { perfRows, perfSummary } from "./perfView";

const HEAD = ["Mahasiswa", "Ujian", "Sumber", "FPS", "Latensi (median / p90)", "Komponen terberat", "Antre (p90)",
  "Lag kamera → server", "Frame dibuang", "Frame 60 dtk terakhir"];

export function AiPerformancePanel({ data, error, loading }: { data: AIPerformance | null; error: string; loading: boolean }) {
  const rows = perfRows(data);
  return <section className="rounded-md border border-slate-200 bg-white p-6" aria-labelledby="judul-performa-ai">
    <h2 id="judul-performa-ai" className="font-bold text-slate-900">Performa analisis AI</h2>
    <p className="mt-1 text-sm text-slate-500">Kecepatan analisis per mahasiswa yang sedang dipantau, 60 detik terakhir, diperbarui tiap 5 detik. Angka operasional dari memori backend, bukan akurasi deteksi. Analisis oleh worker OpenVidu tidak termasuk.</p>
    {error && <p role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <p className="mt-4 text-sm font-semibold text-slate-800">{loading && !data ? "Memuat…" : perfSummary(data)}</p>
    {data && !rows.length && <p className="mt-4 rounded-md border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">Belum ada mahasiswa yang dianalisis di proses backend ini.</p>}
    {rows.length > 0 && <div className="mt-4 overflow-x-auto"><table className="m-stack w-full min-w-[960px] text-left text-sm">
      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr>{HEAD.map((h) => <th key={h} className="px-3 py-2.5">{h}</th>)}</tr></thead>
      <tbody>{rows.map((r) => <tr key={r.key} className="border-t border-slate-100 align-top">
        <td className="px-3 py-3 font-semibold text-slate-800">{r.student}</td>
        <td className="px-3 py-3 text-slate-600">{r.exam}</td>
        <td className="px-3 py-3 text-slate-600">{r.source}</td>
        <td className="px-3 py-3 font-semibold tabular-nums text-slate-800">{r.fps}</td>
        <td className="whitespace-nowrap px-3 py-3 tabular-nums text-slate-600">{r.latency}</td>
        <td className="px-3 py-3 text-slate-600">{r.heaviest}</td>
        <td className="whitespace-nowrap px-3 py-3 tabular-nums text-slate-600">{r.queue}</td>
        <td className="whitespace-nowrap px-3 py-3 tabular-nums text-slate-600">{r.lag}</td>
        <td className="whitespace-nowrap px-3 py-3 tabular-nums text-slate-600">{r.dropped}</td>
        <td className="px-3 py-3 text-xs text-slate-500">{r.status}</td>
      </tr>)}</tbody>
    </table></div>}
    <dl className="mt-5 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
      <div><dt className="inline font-semibold text-slate-600">Latensi: </dt><dd className="inline">waktu menganalisis satu frame di server.</dd></div>
      <div><dt className="inline font-semibold text-slate-600">Antre: </dt><dd className="inline">waktu frame menunggu giliran analisis.</dd></div>
      <div><dt className="inline font-semibold text-slate-600">Lag kamera → server: </dt><dd className="inline">variasi jeda dari kamera mahasiswa sampai server; selisih jam laptop sudah dikurangkan.</dd></div>
      <div><dt className="inline font-semibold text-slate-600">Frame dibuang: </dt><dd className="inline">frame yang datang saat frame sebelumnya masih dianalisis.</dd></div>
    </dl>
  </section>;
}
