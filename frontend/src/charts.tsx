// Charts, drawn as plain SVG/HTML (no chart library). Loaded lazily from App.tsx (React.lazy), so this file is a
// separate chunk. Style follows design/figma-eduai: flat white cards, 4px corners, #dfe1e3 borders, Public Sans
// headings and text, navy #14213D and gold #C9A227. Every number comes from props (API data).
// Colour is never the only cue: every part has a text label and a number (legend, tooltip),
// every chart has alternative text and a hidden table.
import { useWidth } from "./hooks";
import { LineIcon } from "./IndikasiRingkasan";
import { useState, type ReactNode } from "react";
import {
  CASE_STATUS_LABEL, EMPTY_CHART, HISTORY_PARTS, historyRows, isEmpty, KINDS, sessionBins, STATUS_PARTS,
  type CaseStatusKey, type HistoryKey, type KindKey, type MonitorKey, type Segment, type StatusKey, type TimelinePoint,
} from "./chartData";

const NAVY = "#14213d";
const MUTED = "#687382";
const GRID = "#e5e7e9";
const EMPTY_FILL = "#eceff1";
const STATUS_COLOR: Record<StatusKey, string> = { belum: "#c9a227", valid: NAVY, tidak_valid: "#9aa2ac", lanjut: "#efd77f", campuran: "#5b84b1" };
const MONITOR_COLOR: Record<MonitorKey, string> = { online: NAVY, perhatian: "#c9a227", tidak_terbaca: "#9aa2ac", offline: "#dfe1e3" };
/** Light fills get a darker outline so the swatch stays visible on white. */
const OUTLINE: Record<string, string> = { "#efd77f": "#c9a227", "#dfe1e3": "#9aa2ac" };

type Shape = "circle" | "square" | "diamond" | "up" | "down" | "star" | "ring";
type Colored = Segment & { color: string };


export function Card({ title, sub, children, className = "" }: { title: string; sub?: string; children: ReactNode; className?: string }) {
  return <section className={`flex min-w-0 flex-col overflow-hidden rounded border border-line bg-white ${className}`}>
    <div className="border-b border-[#e4e6e8] px-[18px] py-4"><h2 className="text-[17px] leading-[1.3]">{title}</h2>{sub && <p className="mt-1 text-xs leading-5 text-[#89919d]">{sub}</p>}</div>
    <div className="flex flex-1 flex-col px-[18px] py-4">{children}</div>
  </section>;
}

/** Light gray stand-in in the chart's own shape, with the agreed text. */
function Placeholder({ shape }: { shape: "donut" | "line" | "bar" | "timeline" }) {
  return <div role="img" aria-label={EMPTY_CHART} className="flex flex-1 flex-col items-center justify-center gap-3 py-2">
    {shape === "donut" && <svg width="140" height="140" viewBox="0 0 140 140" aria-hidden="true"><circle cx="70" cy="70" r="54" fill="none" stroke={EMPTY_FILL} strokeWidth="18" /></svg>}
    {shape === "line" && <svg width="100%" height="110" viewBox="0 0 300 110" preserveAspectRatio="none" aria-hidden="true"><path d="M0 90 L60 70 L120 80 L180 50 L240 62 L300 40" fill="none" stroke={EMPTY_FILL} strokeWidth="3" /><line x1="0" x2="300" y1="100" y2="100" stroke={EMPTY_FILL} /></svg>}
    {shape === "bar" && <div aria-hidden="true" className="h-8 w-full rounded bg-[#eceff1]" />}
    {shape === "timeline" && <svg width="100%" height="56" viewBox="0 0 300 56" preserveAspectRatio="none" aria-hidden="true"><line x1="0" x2="300" y1="40" y2="40" stroke={EMPTY_FILL} strokeWidth="3" />{[40, 110, 190, 260].map((x) => <circle key={x} cx={x} cy="24" r="5" fill={EMPTY_FILL} />)}</svg>}
    <p className="text-center text-xs text-[#7d8794]">{EMPTY_CHART}</p>
  </div>;
}

function SrTable({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  // sr-only on a wrapper: a <table> itself cannot be shrunk to 1px and would widen the page.
  return <div className="sr-only"><table><caption>{caption}</caption><thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody></table></div>;
}

function Swatch({ color, shape }: { color: string; shape?: Shape }) {
  if (shape) return <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" className="shrink-0"><path d={shapePath(shape, 6, 6, 5)} fill={shape === "ring" ? "none" : color} stroke={shape === "ring" ? color : "none"} strokeWidth="2" /></svg>;
  return <i aria-hidden="true" className="size-2.5 shrink-0 rounded-sm" style={{ background: color, boxShadow: OUTLINE[color] ? `inset 0 0 0 1px ${OUTLINE[color]}` : undefined }} />;
}

function shapePath(shape: Shape, cx: number, cy: number, r: number): string {
  const poly = (pts: [number, number][]) => `M${pts.map(([x, y]) => `${(cx + x).toFixed(1)} ${(cy + y).toFixed(1)}`).join(" L")} Z`;
  if (shape === "square") return poly([[-r * 0.85, -r * 0.85], [r * 0.85, -r * 0.85], [r * 0.85, r * 0.85], [-r * 0.85, r * 0.85]]);
  if (shape === "diamond") return poly([[0, -r * 1.15], [r * 1.15, 0], [0, r * 1.15], [-r * 1.15, 0]]);
  if (shape === "up") return poly([[0, -r * 1.1], [r * 1.05, r * 0.85], [-r * 1.05, r * 0.85]]);
  if (shape === "down") return poly([[-r * 1.05, -r * 0.85], [r * 1.05, -r * 0.85], [0, r * 1.1]]);
  if (shape === "star") return poly(Array.from({ length: 10 }, (_, i) => { const a = (Math.PI / 5) * i - Math.PI / 2; const rr = i % 2 ? r * 0.5 : r * 1.15; return [Math.cos(a) * rr, Math.sin(a) * rr] as [number, number]; }));
  return `M${cx - r} ${cy} a${r} ${r} 0 1 0 ${2 * r} 0 a${r} ${r} 0 1 0 ${-2 * r} 0`;   // circle / ring
}


// ---------------------------------------------------------------- donut
function Donut({ segments, total, unit, alt, caption, mismatch, note, below }: { segments: Colored[]; total: number; unit: string; alt: string; caption: string; mismatch?: string | null; note?: string; below?: ReactNode }) {
  const [active, setActive] = useState<string | null>(null);
  const values = segments.map((s) => s.value);
  const sum = values.reduce((a, b) => a + b, 0);
  const extra = <>{below}{mismatch && <p role="note" className="mt-3 w-full text-xs leading-5 text-[#8c621a]">{mismatch}</p>}{note && <p className="mt-3 w-full text-xs leading-5 text-[#7d8794]">{note}</p>}</>;
  if (isEmpty(values)) return <><Placeholder shape="donut" />{extra}</>;
  const R = 54, W = 18, C = 2 * Math.PI * R;
  const shown = segments.filter((s) => s.value > 0);
  const gap = shown.length > 1 ? 2 : 0;                                   // 2px surface gap between parts
  const arcs = shown.map((s, i) => ({ ...s, len: (s.value / sum) * C, start: shown.slice(0, i).reduce((a, x) => a + (x.value / sum) * C, 0) }));
  const hit = segments.find((s) => s.key === active);
  return <div className="flex flex-1 flex-col">
    <div className="flex flex-col items-center gap-4 sm:flex-row lg:flex-col xl:flex-row">
      <div className="relative shrink-0" role="img" aria-label={alt}>
        <svg width="148" height="148" viewBox="0 0 148 148" aria-hidden="true"><g transform="rotate(-90 74 74)">
          {arcs.map((s) => <circle key={s.key} cx="74" cy="74" r={R} fill="none" stroke={s.color} strokeWidth={active === s.key ? W + 4 : W}
            strokeDasharray={`${Math.max(s.len - gap, 0.5)} ${C}`} strokeDashoffset={-s.start} onMouseEnter={() => setActive(s.key)} onMouseLeave={() => setActive(null)} className="transition-[stroke-width]" />)}
        </g></svg>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div><strong className="block text-[28px] font-bold leading-none text-navy">{hit ? hit.value : total}</strong><span className="mt-1 block text-xs text-[#687382]">{hit ? hit.label : unit}</span></div>
        </div>
      </div>
      <ul className="w-full min-w-0 space-y-1.5 text-xs">
        {segments.map((s) => <li key={s.key} onMouseEnter={() => setActive(s.key)} onMouseLeave={() => setActive(null)} className={`flex items-center justify-between gap-3 rounded px-1.5 py-1 ${active === s.key ? "bg-[#f7f6f2]" : ""}`}>
          <span className="flex min-w-0 items-center gap-2 text-[#334054]"><Swatch color={s.color} />{s.label}</span><b className="text-navy">{s.value}</b></li>)}
        <li className="flex justify-between border-t border-[#e5e7e9] px-1.5 pt-1.5 text-[#687382]"><span>Total {unit}</span><b className="text-navy">{total}</b></li>
      </ul>
    </div>
    {extra}
    <SrTable caption={caption} head={["Bagian", "Jumlah"]} rows={[...segments.map((s) => [s.label, s.value]), [`Total ${unit}`, total]]} />
  </div>;
}

// ---------------------------------------------------------------- stacked bar (one row)
function StackedBar({ segments, total, height, alt, caption, unit, mismatch }: { segments: Colored[]; total: number; height: number; alt: string; caption: string; unit: string; mismatch?: string | null }) {
  const values = segments.map((s) => s.value);
  if (isEmpty(values)) return <Placeholder shape="bar" />;
  const sum = values.reduce((a, b) => a + b, 0);
  return <div>
    <div role="img" aria-label={alt} className="flex w-full gap-[2px] overflow-hidden rounded" style={{ height }}>
      {segments.filter((s) => s.value > 0).map((s) => <div key={s.key} title={`${s.label}: ${s.value} ${unit}`} className="h-full first:rounded-l last:rounded-r"
        style={{ flexGrow: s.value, flexBasis: 0, background: s.color, boxShadow: OUTLINE[s.color] ? `inset 0 0 0 1px ${OUTLINE[s.color]}` : undefined }} />)}
    </div>
    <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs">
      {segments.map((s) => <li key={s.key} className="flex items-center gap-1.5 whitespace-nowrap"><Swatch color={s.color} /><span className="text-[#334054]">{s.label}</span><b className="text-navy">{s.value}</b></li>)}
    </ul>
    <p className="mt-2 text-xs text-[#687382]">Total {total} {unit}</p>
    {mismatch && <p role="note" className="mt-2 text-xs leading-5 text-[#8c621a]">{mismatch}</p>}
    {sum !== total && !mismatch && <p role="note" className="mt-2 text-xs text-[#8c621a]">Jumlah bagian ({sum}) tidak sama dengan total ({total}).</p>}
    <SrTable caption={caption} head={["Bagian", "Jumlah"]} rows={[...segments.map((s) => [s.label, s.value]), ["Total", total]]} />
  </div>;
}

// ---------------------------------------------------------------- line: detections per WIB hour
export type HourPoint = { hour: number; label: string; count: number };
// ---------------------------------------------------------------- indications of one session: stacked columns per time slot
export type TimelineData = { points: TimelinePoint[]; outside: number; start: number; end: number; startLabel: string; endLabel: string };
// Categorical colours for the kinds, fixed order (dataviz reference palette, validated: lightness band, chroma floor,
// adjacent CVD separation and normal-vision floor all pass; light hues are always labelled in the legend, the
// tooltip and the table). "Lainnya" is the neutral fold.
const KIND_COLOR: Record<KindKey, string> = {
  orang: "#2a78d6", menoleh: "#eb6834", berulang: "#1baf7a", suara: "#eda100", wajah: "#e87ba4", benda: "#008300", perangkat: "#6250d6", lain: "#9aa2ac",
};

// One line icon per kind (same icons as the Indikasi page), drawn white on the kind's colour in the legend.
const KIND_ICON: Record<KindKey, Parameters<typeof LineIcon>[0]["name"]> = {
  orang: "users", menoleh: "rotate", berulang: "rotate", suara: "speaker", wajah: "face-off", benda: "phone", perangkat: "video-off", lain: "layers",
};
function KindBadge({ kind, size = 26 }: { kind: KindKey; size?: number }) {
  return <span aria-hidden="true" className="grid shrink-0 place-items-center rounded-full text-white" style={{ width: size, height: size, background: KIND_COLOR[kind] }}>
    <LineIcon name={KIND_ICON[kind]} size={Math.round(size * 0.58)} /></span>;
}

function SessionColumns({ data, title, stepMin: fixed, note }: { data: TimelineData; title: string; stepMin?: number; note?: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const { stepMin, bins } = sessionBins(data, 24, fixed);
  const kinds = KINDS.map((k) => ({ ...k, n: data.points.filter((p) => p.kind === k.key).length })).filter((k) => k.n);
  const peak = bins.reduce((best, b, i) => (b.total > (bins[best]?.total ?? -1) ? i : best), 0);
  const alt = `${title} dari ${data.startLabel} sampai ${data.endLabel}: ${data.points.length} indikasi. Per ${stepMin} menit, ${kinds.map((k) => `${k.label} ${k.n}`).join(", ")}.`
    + (data.points.length ? ` Terbanyak ${bins[peak].range} (${bins[peak].total}).` : "");
  if (!data.points.length) return <><Placeholder shape="line" />{data.outside > 0 && <p className="mt-2 text-xs text-[#7d8794]">{data.outside} indikasi di luar jadwal sesi tidak digambar.</p>}</>;
  const w = Math.max(width, 260), H = 200, top = 12, bottom = 26, left = 30, right = 4;
  const plotW = w - left - right, plotH = H - top - bottom;
  const max = Math.max(1, ...bins.map((b) => b.total));
  const step = [1, 2, 5, 10, 20, 50].find((s2) => max / s2 <= 4) ?? Math.ceil(max / 4);
  const yMax = Math.ceil(max / step) * step;
  const ticks = Array.from({ length: yMax / step + 1 }, (_, i) => i * step);
  const y = (v: number) => top + plotH * (1 - v / yMax);
  const slot = plotW / bins.length, barW = Math.max(4, Math.min(28, slot * 0.68));
  const labelEvery = Math.max(1, Math.ceil(bins.length / Math.max(2, Math.floor(plotW / 64))));
  const nonEmpty = bins.map((b, i) => (b.total ? i : -1)).filter((i) => i >= 0);
  const move = (dir: 1 | -1) => setHover((v) => {
    if (!nonEmpty.length) return null;
    if (v == null) return dir > 0 ? nonEmpty[0] : nonEmpty[nonEmpty.length - 1];
    const k = nonEmpty.indexOf(v);
    return nonEmpty[Math.min(nonEmpty.length - 1, Math.max(0, (k < 0 ? 0 : k) + dir))];
  });
  const pick = (clientX: number, el: SVGSVGElement) => {
    const i = Math.floor((clientX - el.getBoundingClientRect().left - left) / slot);
    setHover(i >= 0 && i < bins.length ? i : null);
  };
  const hb = hover == null ? null : bins[hover];
  return <div ref={ref} className="relative w-full">
    <svg width={w} height={H} role="img" aria-label={alt} tabIndex={0} className="block touch-none outline-none focus-visible:ring-2 focus-visible:ring-gold-500"
      onPointerMove={(e) => pick(e.clientX, e.currentTarget)} onPointerDown={(e) => pick(e.clientX, e.currentTarget)} onPointerLeave={() => setHover(null)} onBlur={() => setHover(null)}
      onKeyDown={(e) => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); move(e.key === "ArrowRight" ? 1 : -1); } else if (e.key === "Escape") setHover(null); }}>
      {ticks.map((t) => <g key={t}>
        <line x1={left} x2={w - right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "#c8ccd0" : GRID} strokeWidth="1" />
        <text x={left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize="12" fill={MUTED}>{t}</text>
      </g>)}
      {hb && <rect x={left + slot * hover!} y={top} width={slot} height={plotH} fill="#f3f4f6" />}
      {bins.map((b, i) => {
        const cx = left + slot * i + slot / 2;
        let acc = 0;
        const parts = KINDS.filter((k) => b.byKind[k.key]).map((k) => ({ key: k.key, v: b.byKind[k.key]! }));
        return <g key={b.start}>
          {parts.map((part, pi) => {
            const y0 = y(acc), y1 = y(acc + part.v); acc += part.v;
            const last = pi === parts.length - 1, gap = pi > 0 ? 2 : 0;          // 2px surface gap between stacked parts
            const h = Math.max(0, y0 - y1 - gap), x0 = cx - barW / 2, r = last ? Math.min(4, h, barW / 2) : 0;
            const d = `M${x0},${y0 - gap} V${y1 + r} ${r ? `Q${x0},${y1} ${x0 + r},${y1}` : ""} H${x0 + barW - r} ${r ? `Q${x0 + barW},${y1} ${x0 + barW},${y1 + r}` : ""} V${y0 - gap} Z`;
            return h > 0 ? <path key={part.key} d={d} fill={KIND_COLOR[part.key]} /> : null;
          })}
          {i % labelEvery === 0 && <text x={cx} y={H - 8} textAnchor="middle" fontSize="12" fill={MUTED}>{b.label}</text>}
        </g>;
      })}
    </svg>
    {hb && <div role="status" className="pointer-events-none absolute top-0 z-10 w-[220px] rounded border border-line bg-white px-3 py-2 text-xs leading-5 text-[#334054] shadow-sm"
      style={{ left: Math.min(Math.max(left + slot * (hover! + 0.5) - 110, 0), Math.max(w - 220, 0)) }}>
      <b className="block text-navy">{hb.range}</b>
      {hb.total ? <>
        <span className="block text-[#687382]">{hb.total} indikasi</span>
        <ul className="mt-1 space-y-0.5">{KINDS.filter((k) => hb.byKind[k.key]).map((k) => <li key={k.key} className="flex items-center justify-between gap-2"><span className="flex items-center gap-1.5"><KindBadge kind={k.key} size={18} />{k.label}</span><b className="text-navy">{hb.byKind[k.key]}</b></li>)}</ul>
        <span className="mt-1 block border-t border-[#e5e7e9] pt-1 text-[#687382]">Siswa: {hb.students.slice(0, 3).join(", ")}{hb.students.length > 3 ? ` +${hb.students.length - 3}` : ""}</span>
      </> : <span className="block text-[#687382]">Tidak ada indikasi</span>}
    </div>}
    <ul aria-label="Keterangan jenis indikasi" className="mt-3 flex flex-wrap gap-x-3 gap-y-2 text-xs text-[#334054]">{kinds.map((k) => <li key={k.key} data-kind-legend={k.key} title={`${k.label}: ${k.n} indikasi`}
      className="flex items-center gap-1.5 rounded-full border border-[#e5e7e9] py-0.5 pl-0.5 pr-2.5"><KindBadge kind={k.key} /><span data-legend-label>{k.label}</span><b className="tabular-nums text-navy">{k.n}</b></li>)}</ul>
    {data.outside > 0 && !fixed && <p className="mt-2 text-xs text-[#7d8794]">{data.outside} indikasi di luar jadwal sesi tidak digambar.</p>}
    {note && <p className="mt-2 text-xs text-[#7d8794]">{note}</p>}
    <SrTable caption={title} head={["Waktu (WIB)", "Jumlah", "Jenis", "Siswa"]}
      rows={bins.filter((b) => b.total).map((b) => [b.range, b.total, KINDS.filter((k) => b.byKind[k.key]).map((k) => `${k.label} ${b.byKind[k.key]}`).join(", "), b.students.join(", ")])} />
  </div>;
}

// ---------------------------------------------------------------- funnel and bars per kind
function Funnel({ stages }: { stages: Segment[] }) {
  const values = stages.map((s) => s.value);
  if (isEmpty(values)) return <Placeholder shape="bar" />;
  const max = Math.max(...values, 1);
  const alt = `Alur tinjauan: ${stages.map((s) => `${s.label} ${s.value}`).join(", ")}.`;
  return <div role="img" aria-label={alt} className="space-y-2.5">
    {stages.map((s, i) => <div key={s.key} className="grid grid-cols-[minmax(0,8.5rem)_1fr] items-center gap-3 text-xs">
      <span className="text-[#334054]">{s.label}</span>
      <div className="flex items-center gap-2"><div className="h-6 rounded-r" style={{ width: `${Math.max((s.value / max) * 100, s.value ? 1.5 : 0)}%`, background: i < 2 ? NAVY : STATUS_COLOR[s.key as StatusKey] ?? NAVY, boxShadow: s.key === "lanjut" ? "inset 0 0 0 1px #c9a227" : undefined }} /><b className="shrink-0 text-navy">{s.value}</b></div>
    </div>)}
    <SrTable caption="Alur tinjauan indikasi" head={["Tahap", "Jumlah"]} rows={stages.map((s) => [s.label, s.value])} />
  </div>;
}

type KindRow = { key: string; label: string; parts: (Segment & { key: StatusKey })[]; total: number };
function KindBars({ rows }: { rows: KindRow[] }) {
  if (isEmpty(rows.map((r) => r.total))) return <Placeholder shape="bar" />;
  const max = Math.max(...rows.map((r) => r.total), 1);
  const used = STATUS_PARTS.filter((p) => p.key !== "campuran" || rows.some((r) => r.parts.some((x) => x.key === "campuran" && x.value)));
  const alt = `Kasus per jenis indikasi: ${rows.map((r) => `${r.label} ${r.total}`).join(", ")}.`;
  return <div>
    <div role="img" aria-label={alt} className="space-y-2.5">
      {rows.map((r) => <div key={r.key} className="grid grid-cols-[minmax(0,9rem)_1fr] items-center gap-3 text-xs">
        <span className="text-[#334054]">{r.label}</span>
        <div className="flex min-w-0 items-center gap-2">
          {r.total > 0 && <div className="flex h-5 gap-[2px] overflow-hidden rounded" style={{ width: `${(r.total / max) * 100}%`, minWidth: 6 }}>
            {r.parts.filter((p) => p.value).map((p) => <div key={p.key} title={`${r.label} · ${p.label}: ${p.value}`} style={{ flexGrow: p.value, flexBasis: 0, background: STATUS_COLOR[p.key], boxShadow: OUTLINE[STATUS_COLOR[p.key]] ? `inset 0 0 0 1px ${OUTLINE[STATUS_COLOR[p.key]]}` : undefined }} />)}
          </div>}
          <b className="shrink-0 text-navy">{r.total}</b>
        </div>
      </div>)}
    </div>
    <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-[#334054]">{used.map((p) => <li key={p.key} className="flex items-center gap-1.5"><Swatch color={STATUS_COLOR[p.key]} />{p.label}</li>)}</ul>
    <SrTable caption="Kasus per jenis indikasi dan status tinjauan" head={["Jenis indikasi", ...used.map((p) => p.label), "Total"]} rows={rows.map((r) => [r.label, ...used.map((u) => r.parts.find((p) => p.key === u.key)!.value), r.total])} />
  </div>;
}

// ---------------------------------------------------------------- page sections
const loadingText = <p className="py-6 text-center text-xs text-[#7d8794]">Memuat…</p>;

export type DashboardChartsProps = {
  breakdown: { segments: (Segment & { key: CaseStatusKey })[]; total: number; mismatch: string | null } | null;
  today: { data: TimelineData; capped: boolean } | null;
};

/** Thin progress bar with its label (review progress, students present). */
function Progress({ label, done, total, color = NAVY }: { label: ReactNode; done: number; total: number; color?: string }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return <div className="w-full">
    <div className="flex items-baseline justify-between gap-2 text-xs text-[#687382]"><span>{label}</span><b className="tabular-nums text-navy">{pct}%</b></div>
    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#eceff1]" role="img" aria-label={`${done} dari ${total} (${pct}%)`}><div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} /></div>
  </div>;
}
export default function DashboardCharts({ breakdown, today }: DashboardChartsProps) {
  // Same charts as Monitoring: status donut (1/3) and stacked columns per hour with the kind icons (2/3).
  return <div className="grid gap-[18px] lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
    <Card title="Status tinjauan kasus" sub={`Valid = dikonfirmasi pengawas, bukan bukti dari AI. ${CASE_STATUS_LABEL.belum} = masih menunggu tinjauan.`}>
      {breakdown ? <Donut segments={breakdown.segments.map((s) => ({ ...s, color: STATUS_COLOR[s.key] }))} total={breakdown.total} unit="kasus" caption="Status tinjauan kasus"
        alt={`Status tinjauan kasus. Total ${breakdown.total} kasus: ${breakdown.segments.map((s) => `${s.label} ${s.value}`).join(", ")}.`}
        mismatch={breakdown.mismatch} note="Dihitung per kasus. Satu kasus bisa berisi beberapa deteksi."
        below={breakdown.total > 0 ? <div className="mt-4 w-full border-t border-[#e5e7e9] pt-3" data-review-progress>
          <Progress label={<>Sudah ditinjau <b className="text-navy">{breakdown.total - (breakdown.segments.find((x) => x.key === "belum")?.value ?? 0)}</b> dari {breakdown.total} kasus</>}
            done={breakdown.total - (breakdown.segments.find((x) => x.key === "belum")?.value ?? 0)} total={breakdown.total} /></div> : undefined} /> : loadingText}
    </Card>
    <Card title="Deteksi hari ini" sub="Jumlah deteksi AI per jam (WIB) sejak 00.00, ditumpuk per jenis.">
      {today ? <SessionColumns data={today.data} title="Deteksi AI hari ini" stepMin={60} note={today.capped ? "Dihitung dari 500 deteksi terbaru hari ini." : undefined} /> : loadingText}
    </Card>
  </div>;
}

// ---------------------------------------------------------------- Riwayat Sesi: review result per session
const HISTORY_COLOR: Record<HistoryKey, string> = { valid: NAVY, tidak_valid: "#9aa2ac", lanjut: "#efd77f", belum: "#c9a227" };
export function HistoryChart({ data }: { data: ReturnType<typeof historyRows> | null; onOpen?: (examId: number) => void }) {
  // Same donut as Dasbor and Pemantauan: review results of every indication in the finished sessions.
  const sums = data ? HISTORY_PARTS.map((p) => ({ key: p.key, label: p.label, value: data.rows.reduce((a, r) => a + r.parts[p.key], 0), color: HISTORY_COLOR[p.key] })) : null;
  const reviewed = data ? data.total - data.open : 0;
  return <div className="grid gap-[18px] lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
    <Card title="Hasil tinjauan semua sesi" sub="Indikasi dari semua sesi yang sudah selesai, menurut hasil tinjauan.">
      {data && sums ? <Donut segments={sums} total={data.total} unit="indikasi" caption="Hasil tinjauan semua sesi"
        alt={`Hasil tinjauan semua sesi: total ${data.total} indikasi. ${sums.map((x) => `${x.label} ${x.value}`).join(", ")}.`} /> : loadingText}
    </Card>
    <Card title="Ringkasan riwayat" sub="Sesi yang pernah ditugaskan kepada Anda dan sudah selesai.">
      {data ? <div className="flex flex-1 flex-col justify-center gap-5" data-history-summary>
        <dl className="grid grid-cols-3 gap-3 text-xs text-[#687382]">
          <div><dt>Sesi selesai</dt><dd className="mt-1 text-[26px] font-bold tabular-nums leading-none text-navy">{data.sessions}</dd></div>
          <div><dt>Sesi dengan indikasi</dt><dd className="mt-1 text-[26px] font-bold tabular-nums leading-none text-navy">{data.rows.filter((r) => r.total > 0).length}</dd></div>
          <div><dt>Total indikasi</dt><dd className="mt-1 text-[26px] font-bold tabular-nums leading-none text-navy">{data.total}</dd></div>
        </dl>
        <Progress label={<>Sudah ditinjau <b className="text-navy">{reviewed}</b> dari {data.total} indikasi</>} done={reviewed} total={data.total} />
        {data.open > 0 && <p className="text-xs text-[#8c621a]">{data.open} indikasi masih menunggu tinjauan. Buka sesinya lewat "Lihat Detail" di tabel.</p>}
      </div> : loadingText}
    </Card>
  </div>;
}

export function MonitoringCharts({ status, timeline }: { status: { segments: (Segment & { key: MonitorKey })[]; total: number } | null; timeline: TimelineData | null }) {
  return <div className="grid gap-[18px] lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
    <Card title="Status siswa" sub="Setiap siswa dihitung satu kali (Offline, Perlu perhatian, Tidak dapat dianalisis, Online). Diperbarui setiap 3 detik.">
      {status ? <Donut segments={status.segments.map((s) => ({ ...s, color: MONITOR_COLOR[s.key] }))} total={status.total} unit="siswa" caption="Status siswa"
        alt={`Status siswa, total ${status.total}: ${status.segments.map((s) => `${s.label} ${s.value}`).join(", ")}.`} /> : loadingText}
    </Card>
    <Card title="Indikasi sesi ini" sub="Jumlah indikasi per selang waktu sepanjang jadwal ujian (WIB), ditumpuk per jenis.">
      {timeline ? <SessionColumns data={timeline} title="Indikasi sesi ini" /> : loadingText}
    </Card>
  </div>;
}

export function IndicationCharts({ funnel, kinds }: { funnel: Segment[] | null; kinds: KindRow[] | null }) {
  return <div className="grid gap-[18px] lg:grid-cols-2">
    <Card title="Alur tinjauan" sub="Dari deteksi AI sampai kasus yang perlu tindak lanjut.">{funnel ? <Funnel stages={funnel} /> : loadingText}</Card>
    <Card title="Kasus per jenis indikasi" sub="Setiap bar dibagi per status tinjauan. Angka di ujung bar = jumlah kasus.">{kinds ? <KindBars rows={kinds} /> : loadingText}</Card>
  </div>;
}

const ATT_COLOR: Record<string, string> = { hadir: NAVY, tidak_hadir: "#9aa2ac" };
const RES_COLOR: Record<string, string> = { valid: NAVY, tidak_valid: "#9aa2ac", lanjut: "#efd77f", belum: "#c9a227" };

export function ReportAttendance({ attendance, unreadable }: { attendance: { segments: Segment[]; total: number; mismatch: string | null }; unreadable: { periods: number; seconds: number } }) {
  const mins = Math.round(unreadable.seconds / 60);
  return <Donut segments={attendance.segments.map((s) => ({ ...s, color: ATT_COLOR[s.key] }))} total={attendance.total} unit="peserta" caption="Kehadiran"
    alt={`Kehadiran: ${attendance.segments.map((s) => `${s.label} ${s.value}`).join(", ")} dari ${attendance.total} peserta. Periode tidak terbaca: ${unreadable.periods}.`} mismatch={attendance.mismatch}
    below={<p className="mt-3 flex items-center justify-between gap-3 rounded bg-[#f7f6f2] px-2.5 py-2 text-xs text-[#334054]"><span>Periode tidak terbaca<span className="block text-[#7d8794]">Dihitung per periode, bukan per siswa</span></span><b className="text-right text-navy">{unreadable.periods}{unreadable.periods ? ` (± ${mins} menit)` : ""}</b></p>} />;
}

export function ReportResults({ results }: { results: { segments: Segment[]; total: number; mismatch: string | null } }) {
  return <StackedBar segments={results.segments.map((s) => ({ ...s, color: RES_COLOR[s.key] }))} total={results.total} height={32} unit="indikasi" caption="Hasil indikasi" mismatch={results.mismatch}
    alt={`Hasil indikasi, total ${results.total}: ${results.segments.map((s) => `${s.label} ${s.value}`).join(", ")}. Valid berarti dikonfirmasi pengawas, bukan bukti dari AI.`} />;
}

