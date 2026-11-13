// Indikasi page, top part: kind filter row, 7-day KPI row, status overview and "Tidak dapat dianalisis".
// Layout follows a work-tracker "summary" page: white page, white cards with a 1 px #DFE1E6 border, 4 px corners,
// 14 px bold titles, 12 px grey descriptions. Accent colours are only navy (active) and gold (selected).
// Every number comes from props (API data). Line icons are drawn here (lucide-style paths, no icon library).
import { useState, type ReactNode } from "react";
import { EMPTY_CHART } from "./chartData";
import { JENIS, STATUS, type Filter, type JenisIcon, type JenisKey, type Kpi, type StatusKey, type UnreadableRow } from "./indikasi";

const BORDER = "#DFE1E6";
const MUTED = "#626F86";
const TEXT = "#1D2433";

// ---------------------------------------------------------------- icons (24 px grid, 2 px stroke, drawn at 16 px)
type IconName = JenisIcon | "layers" | "check" | "activity" | "file-plus" | "clock" | "chevron";
const PATHS: Record<IconName, ReactNode> = {
  phone: <><rect x="5" y="2" width="14" height="20" rx="2" /><path d="M12 18h.01" /></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></>,
  book: <><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" /></>,
  "face-off": <><circle cx="12" cy="12" r="9" /><path d="M9 9h.01M15 9h.01M8.5 15a4.5 4.5 0 0 1 7 0" /><path d="m3 3 18 18" /></>,
  rotate: <><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /></>,
  speaker: <><path d="M11 5 6 9H2v6h4l5 4z" /><path d="M15.54 8.46a5 5 0 0 1 0 7.07" /><path d="M19.07 4.93a10 10 0 0 1 0 14.14" /></>,
  music: <><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></>,
  "video-off": <><path d="M10.66 6H14a2 2 0 0 1 2 2v2.5l5.25-3.06A.5.5 0 0 1 22 7.87v8.26" /><path d="M16 16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h2" /><path d="m2 2 20 20" /></>,
  "mic-off": <><path d="m2 2 20 20" /><path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2" /><path d="M5 10v2a7 7 0 0 0 12 5" /><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33" /><path d="M9 9v3a3 3 0 0 0 5.12 2.12" /><path d="M12 19v3" /></>,
  "camera-off": <><path d="m2 2 20 20" /><path d="M7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16" /><path d="M9.5 4h5L17 7h3a2 2 0 0 1 2 2v7.5" /><path d="M14.12 15.12a3 3 0 1 1-4.24-4.24" /></>,
  layers: <><path d="m12 2 10 5-10 5L2 7z" /><path d="m2 17 10 5 10-5" /><path d="m2 12 10 5 10-5" /></>,
  check: <><circle cx="12" cy="12" r="10" /><path d="m9 12 2 2 4-4" /></>,
  activity: <path d="M22 12h-4l-3 9L9 3l-3 9H2" />,
  "file-plus": <><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z" /><path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M9 15h6M12 12v6" /></>,
  clock: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
  chevron: <path d="m6 9 6 6 6-6" />,
};
export function LineIcon({ name, size = 16, className = "" }: { name: IconName; size?: number; className?: string }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={`shrink-0 ${className}`}>{PATHS[name]}</svg>;
}

// ---------------------------------------------------------------- card
export function SummaryCard({ title, sub, link, action, children, className = "" }: { title: string; sub?: string; link?: { label: string; onClick: () => void }; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`min-w-0 rounded border bg-white p-4 sm:p-5 ${className}`} style={{ borderColor: BORDER }}>
    <div className="flex items-start justify-between gap-3"><h2 className="font-sans text-sm font-bold" style={{ color: TEXT }}>{title}</h2>{action}</div>
    {(sub || link) && <p className="mt-1 text-xs leading-5" style={{ color: MUTED }}>{sub}{sub && link ? " " : ""}{link && <button type="button" onClick={link.onClick} className="font-medium text-[#14213d] underline-offset-2 hover:underline focus-visible:underline">{link.label}</button>}</p>}
    <div className="mt-4">{children}</div>
  </section>;
}

function Empty({ shape }: { shape: "donut" | "list" }) {
  return <div role="img" aria-label={EMPTY_CHART} className="flex flex-col items-center justify-center gap-3 py-6">
    {shape === "donut" ? <svg width="120" height="120" viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="44" fill="none" stroke="#EBECF0" strokeWidth="22" /></svg>
      : <div aria-hidden="true" className="w-full space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-8 rounded bg-[#F4F5F7]" />)}</div>}
    <p className="text-xs" style={{ color: MUTED }}>{EMPTY_CHART}</p>
  </div>;
}

// ---------------------------------------------------------------- 0. filter row
export function FilterRow({ filter, counts, onJenis, onStatus, readOnly }: {
  filter: Filter; counts: Record<JenisKey | "semua", number>; onJenis: (j: JenisKey | null) => void; onStatus: (s: StatusKey | null) => void; readOnly: boolean;
}) {
  const btn = (key: JenisKey | null, label: string, icon: IconName, n: number, quality = false) => {
    const on = filter.jenis === key;
    return <button key={key ?? "semua"} type="button" aria-pressed={on} data-jenis={key ?? "semua"} data-count={n} onClick={() => onJenis(key)}
      className={`flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded border px-2.5 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-[#c9a227] focus-visible:ring-offset-1 ${
        on ? "border-[#14213d] bg-[#14213d] text-white" : quality ? "border-dashed bg-white text-[#626F86] hover:bg-[#F4F5F7]" : "bg-white text-[#1D2433] hover:bg-[#F4F5F7]"}`}
      style={on ? undefined : { borderColor: quality ? "#B3B9C4" : BORDER }}>
      <LineIcon name={icon} />{label}<span className={on ? "text-white/75" : "text-[#626F86]"}>· {n}</span>
      {quality && <span className={`ml-0.5 rounded-sm px-1 text-[12px] ${on ? "bg-white/15 text-white" : "bg-[#F4F5F7] text-[#626F86]"}`}>bukan indikasi</span>}
    </button>;
  };
  const statuses = STATUS.filter((s) => !readOnly || s.key !== "belum");
  return <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
    <div role="toolbar" aria-label="Saring jenis indikasi" className="-mx-4 flex min-w-0 flex-1 gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0 lg:flex-wrap lg:overflow-visible lg:pb-0">
      {btn(null, "Semua", "layers", counts.semua)}
      {JENIS.filter((j) => !j.quality).map((j) => btn(j.key, j.label, j.icon, counts[j.key]))}
    </div>
    <label className="flex shrink-0 items-center gap-2 self-start text-[13px] lg:self-auto" style={{ color: MUTED }}>Status
      <span className="relative">
        <select value={filter.status ?? ""} onChange={(e) => onStatus((e.target.value || null) as StatusKey | null)}
          className={`h-8 appearance-none rounded border bg-white pl-2.5 pr-8 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-[#c9a227] ${filter.status ? "border-[#14213d] font-semibold text-[#14213d]" : "text-[#1D2433]"}`}
          style={filter.status ? undefined : { borderColor: BORDER }}>
          <option value="">Semua status</option>
          {statuses.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <LineIcon name="chevron" size={14} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2" />
      </span>
    </label>
  </div>;
}

// ---------------------------------------------------------------- 1. KPI row
export function KpiRow({ kpi }: { kpi: Kpi | null }) {
  const items: [IconName, string, number | null, string?][] = [
    ["check", "kasus ditinjau", kpi?.ditinjau ?? null],
    ["activity", "deteksi baru", kpi?.deteksi ?? null, kpi?.deteksiCapped ? "Dihitung dari 500 deteksi terbaru." : undefined],
    ["file-plus", "kasus baru", kpi?.kasusBaru ?? null],
    ["clock", "belum ditinjau", kpi?.belum ?? null],
  ];
  return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
    {items.map(([icon, label, n, note]) => <section key={label} className="flex min-w-0 items-center gap-3 rounded border bg-white p-4" style={{ borderColor: BORDER }}>
      <span className="grid size-8 shrink-0 place-items-center rounded bg-[#F4F5F7] text-[#14213d]"><LineIcon name={icon} /></span>
      <div className="min-w-0">
        <p className="text-sm font-semibold" style={{ color: TEXT }}>{n === null ? "…" : n}{note ? "+" : ""} {label}</p>
        <p className="text-xs" style={{ color: MUTED }} title={note}>dalam 7 hari terakhir</p>
      </div>
    </section>)}
  </div>;
}

// ---------------------------------------------------------------- 2a. status overview (donut)
const STATUS_COLOR: Record<StatusKey, string> = { belum: "#C9A227", valid: "#14213D", "tidak-valid": "#626F86", lanjut: "#E9D48A", campuran: "#DFE1E6" };
const OUTLINE: Partial<Record<StatusKey, string>> = { lanjut: "#C9A227", campuran: "#8590A2" };

export function StatusDonut({ data, selected, onSelect, onAll }: {
  data: { segments: { key: StatusKey; label: string; value: number }[]; total: number } | null; selected: StatusKey | null; onSelect: (s: StatusKey | null) => void; onAll: () => void;
}) {
  const [hover, setHover] = useState<StatusKey | null>(null);
  const card = (body: ReactNode) => <SummaryCard title="Ringkasan status" sub="Status tinjauan kasus. Pilih status untuk menyaring." link={{ label: "Lihat semua kasus", onClick: onAll }}>{body}</SummaryCard>;
  if (!data) return card(<p className="py-6 text-center text-xs" style={{ color: MUTED }}>Memuat…</p>);
  if (!data.total) return card(<Empty shape="donut" />);
  const R = 56, W = 26, C = 2 * Math.PI * R, shown = data.segments.filter((s) => s.value > 0), gap = shown.length > 1 ? 1.5 : 0;
  const arcs = shown.map((s, i) => ({ ...s, len: (s.value / data.total) * C, start: shown.slice(0, i).reduce((acc, x) => acc + (x.value / data.total) * C, 0) }));
  const focus = hover ?? selected;
  const alt = `Ringkasan status: total ${data.total} kasus. ${data.segments.map((s) => `${s.label} ${s.value}`).join(", ")}.`;
  return card(<div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center lg:gap-4 xl:gap-5">
    <div className="relative shrink-0" role="img" aria-label={alt}>
      <svg viewBox="0 0 152 152" aria-hidden="true" className="block size-[152px] lg:size-[120px] xl:size-[152px]"><g transform="rotate(-90 76 76)">
        {arcs.map((a) => <circle key={a.key} cx="76" cy="76" r={R} fill="none" stroke={STATUS_COLOR[a.key]} strokeWidth={focus === a.key ? W + 4 : W}
          strokeDasharray={`${Math.max(a.len - gap, 0.5)} ${C}`} strokeDashoffset={-a.start} opacity={focus && focus !== a.key ? 0.35 : 1}
          onMouseEnter={() => setHover(a.key)} onMouseLeave={() => setHover(null)} onClick={() => onSelect(selected === a.key ? null : a.key)} className="cursor-pointer" />)}
      </g></svg>
      <div className="pointer-events-none absolute inset-0 grid place-items-center text-center"><div className="max-w-[92px] lg:max-w-[66px] xl:max-w-[92px]">
        <strong className="block text-2xl font-semibold leading-none lg:text-xl xl:text-2xl" style={{ color: TEXT }}>{focus ? data.segments.find((s) => s.key === focus)!.value : data.total}</strong>
        <span className="mt-1 block text-xs" style={{ color: MUTED }}>{focus ? data.segments.find((s) => s.key === focus)!.label : "Total kasus"}</span>
      </div></div>
    </div>
    <ul className="w-full min-w-0 flex-1 space-y-1">
      {data.segments.map((s) => { const on = selected === s.key; return <li key={s.key}>
        <button type="button" aria-pressed={on} onClick={() => onSelect(on ? null : s.key)} onMouseEnter={() => setHover(s.key)} onMouseLeave={() => setHover(null)}
          onFocus={() => setHover(s.key)} onBlur={() => setHover(null)}
          className={`flex h-8 w-full items-center gap-2 rounded px-2 text-left text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-[#c9a227] ${on ? "bg-[#FBF3D5] font-semibold" : "hover:bg-[#F4F5F7]"}`} style={{ color: TEXT }}>
          <i aria-hidden="true" className="size-3 shrink-0 rounded-sm" style={{ background: STATUS_COLOR[s.key], boxShadow: OUTLINE[s.key] ? `inset 0 0 0 1px ${OUTLINE[s.key]}` : undefined }} />
          <span className="min-w-0 flex-1 truncate">{s.label}</span><span className="tabular-nums" style={{ color: on ? TEXT : MUTED }}>{s.value}</span>
        </button></li>; })}
    </ul>
    <div className="sr-only"><table><caption>Ringkasan status kasus</caption><thead><tr><th>Status</th><th>Kasus</th></tr></thead>
      <tbody>{data.segments.map((s) => <tr key={s.key}><td>{s.label}</td><td>{s.value}</td></tr>)}<tr><td>Total</td><td>{data.total}</td></tr></tbody></table></div>
  </div>);
}

// ---------------------------------------------------------------- generic donut card (kinds, supervisor load)
export type DonutSlice = { key: string; label: string; value: number; color: string; note?: string; icon?: JenisIcon };
export function DonutCard({ title, sub, slices, unit, alt, caption, selected, onSelect, attr }: {
  title: string; sub: string; slices: DonutSlice[] | null; unit: string; alt: (total: number) => string; caption: string;
  selected?: string | null; onSelect?: (key: string) => void; attr: string;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const card = (body: ReactNode) => <SummaryCard title={title} sub={sub}>{body}</SummaryCard>;
  if (!slices) return card(<p className="py-6 text-center text-xs" style={{ color: MUTED }}>Memuat…</p>);
  const total = slices.reduce((a, s) => a + s.value, 0);
  if (!total) return card(<Empty shape="donut" />);
  const R = 56, W = 26, C = 2 * Math.PI * R, shown = slices.filter((s) => s.value > 0), gap = shown.length > 1 ? 1.5 : 0;
  const arcs = shown.map((s, i) => ({ ...s, len: (s.value / total) * C, start: shown.slice(0, i).reduce((acc, x) => acc + (x.value / total) * C, 0) }));
  const focus = hover ?? selected ?? null;
  const hit = slices.find((s) => s.key === focus);
  return card(<div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center lg:gap-4 xl:gap-5">
    <div className="relative shrink-0" role="img" aria-label={alt(total)}>
      <svg viewBox="0 0 152 152" aria-hidden="true" className="block size-[152px] lg:size-[120px] xl:size-[152px]"><g transform="rotate(-90 76 76)">
        {arcs.map((a) => <circle key={a.key} cx="76" cy="76" r={R} fill="none" stroke={a.color} strokeWidth={focus === a.key ? W + 4 : W}
          strokeDasharray={`${Math.max(a.len - gap, 0.5)} ${C}`} strokeDashoffset={-a.start} opacity={focus && focus !== a.key ? 0.35 : 1}
          onMouseEnter={() => setHover(a.key)} onMouseLeave={() => setHover(null)} onClick={onSelect ? () => onSelect(a.key) : undefined} className={onSelect ? "cursor-pointer" : ""} />)}
      </g></svg>
      <div className="pointer-events-none absolute inset-0 grid place-items-center text-center"><div className="max-w-[92px] lg:max-w-[66px] xl:max-w-[92px]">
        <strong className="block text-2xl font-semibold leading-none lg:text-xl xl:text-2xl" style={{ color: TEXT }}>{hit ? hit.value : total}</strong>
        <span className="mt-1 line-clamp-2 block text-xs" style={{ color: MUTED }}>{hit ? hit.label : `Total ${unit}`}</span>
      </div></div>
    </div>
    <ul className="w-full min-w-0 flex-1 space-y-1">
      {slices.filter((s) => s.value > 0).map((s) => { const on = selected === s.key; const body = <>
        {s.icon ? <span aria-hidden="true" data-slice-icon={s.icon} className="grid size-6 shrink-0 place-items-center rounded-full text-white" style={{ background: s.color }}><LineIcon name={s.icon} size={14} /></span>
          : <i aria-hidden="true" className="size-3 shrink-0 rounded-sm" style={{ background: s.color }} />}
        <span className="min-w-0 flex-1"><span className="block truncate">{s.label}</span>{s.note && <span className="block text-xs" style={{ color: MUTED }}>{s.note}</span>}</span>
        <span className="tabular-nums" style={{ color: on ? TEXT : MUTED }}>{s.value}</span></>;
        const cls = `flex min-h-8 w-full items-center gap-2 rounded px-2 py-1 text-left text-[13px] ${on ? "bg-[#FBF3D5] font-semibold" : ""}`;
        return <li key={s.key} {...{ [`data-${attr}`]: s.label }} data-value={s.value} onMouseEnter={() => setHover(s.key)} onMouseLeave={() => setHover(null)}>
          {onSelect ? <button type="button" aria-pressed={on} onClick={() => onSelect(s.key)} onFocus={() => setHover(s.key)} onBlur={() => setHover(null)}
            className={`${cls} outline-none hover:bg-[#F4F5F7] focus-visible:ring-2 focus-visible:ring-[#c9a227]`} style={{ color: TEXT }}>{body}</button>
            : <div className={cls} style={{ color: TEXT }}>{body}</div>}
        </li>; })}
    </ul>
    <div className="sr-only"><table><caption>{caption}</caption><thead><tr><th>Bagian</th><th>Jumlah</th><th>Keterangan</th></tr></thead>
      <tbody>{slices.map((s) => <tr key={s.key}><td>{s.label}</td><td>{s.value}</td><td>{s.note ?? ""}</td></tr>)}<tr><td>Total</td><td>{total}</td><td /></tr></tbody></table></div>
  </div>);
}

// ---------------------------------------------------------------- 2b. "tidak dapat dianalisis" per exam
export function UnreadableCard({ rows, capped, onOpen }: { rows: UnreadableRow[] | null; capped: boolean; onOpen: (examId: number) => void }) {
  const total = rows?.reduce((a, r) => a + r.periods, 0) ?? 0;
  return <SummaryCard title="Tidak dapat dianalisis" sub={`Periode ketika kamera terlalu gelap, buram, atau tidak mengirim gambar. Ini masalah kualitas, bukan indikasi.${capped ? " Dihitung dari 500 periode terbaru." : ""}`}>
    {!rows ? <p className="py-6 text-center text-xs" style={{ color: MUTED }}>Memuat…</p> : !rows.length ? <Empty shape="list" /> :
      <ul className="max-h-[232px] divide-y overflow-y-auto" style={{ borderColor: BORDER }} aria-label={`Tidak dapat dianalisis: ${total} periode di ${rows.length} ujian`}>
        {rows.map((r) => <li key={r.examId} className="flex items-center gap-3 py-2.5" style={{ borderColor: BORDER }}>
          <span className="grid size-8 shrink-0 place-items-center rounded bg-[#F4F5F7] text-[#626F86]"><LineIcon name="camera-off" /></span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold" style={{ color: TEXT }}>{r.exam}</p>
            <p className="text-xs" style={{ color: MUTED }}>{r.periods} periode · {r.students} siswa{r.seconds ? ` · ± ${Math.max(1, Math.round(r.seconds / 60))} menit` : ""}</p>
          </div>
          <button type="button" onClick={() => onOpen(r.examId)} className="h-7 shrink-0 rounded border bg-white px-2.5 text-xs font-medium text-[#14213d] outline-none hover:bg-[#F4F5F7] focus-visible:ring-2 focus-visible:ring-[#c9a227]" style={{ borderColor: BORDER }}
            aria-label={`Lihat laporan ${r.exam}`}>Lihat</button>
        </li>)}
      </ul>}
  </SummaryCard>;
}
