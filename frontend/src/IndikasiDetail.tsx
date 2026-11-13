// Indikasi page, rows 3–5 and the student drawer: recent activity, cases per kind (SVG bars), kind distribution,
// supervisor workload, review progress per exam. Same card style as IndikasiRingkasan (white, 1 px #DFE1E6, 4 px
// corners). Every number comes from props (API data); empty data shows the grey placeholder.
import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { api, type CaseSummary, type Decision } from "./api";
import { EMPTY_CHART } from "./chartData";
import { DonutCard, LineIcon, SummaryCard } from "./IndikasiRingkasan";
import { JENIS, axisTicks, drawerTitle, jenisOf, statusOf, type Activity, type DrawerSource, type JenisKey, type KindBar, type KindSlice, type LoadSlice, type StatusKey } from "./indikasi";
import { useFocusTrap, useWidth } from "./hooks";
import { formatWib, parseUtc, timeAgo } from "./time";

const BORDER = "#DFE1E6";
const MUTED = "#626F86";
const TEXT = "#1D2433";
const NAVY = "#14213D";
const GOLD = "#C9A227";
const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";

function Avatar({ name, size = 28 }: { name: string; size?: number }) {
  return <span aria-hidden="true" className="grid shrink-0 place-items-center rounded-full bg-[#F1E7C4] font-semibold text-[#14213d]" style={{ width: size, height: size, fontSize: Math.max(11, size * 0.36) }}>{initials(name)}</span>;
}

function Empty({ text = EMPTY_CHART }: { text?: string }) {
  return <p className="rounded bg-[#F4F5F7] px-3 py-6 text-center text-xs" style={{ color: MUTED }}>{text}</p>;
}

// ---------------------------------------------------------------- status badge (text + shape, colour is not the only cue)
const BADGE: Record<StatusKey, string> = {
  belum: "border-[#E9D48A] bg-[#FBF3D5] text-[#5C4600]", valid: "border-[#14213d] bg-[#14213d] text-white",
  "tidak-valid": "border-[#C1C7D0] bg-[#F4F5F7] text-[#44546F]", lanjut: "border-[#C9A227] bg-white text-[#5C4600]", campuran: "border-[#C1C7D0] bg-white text-[#44546F]",
};
const LABEL: Record<StatusKey, string> = { belum: "Belum ditinjau", valid: "Valid", "tidak-valid": "Tidak valid", lanjut: "Perlu tinjauan lanjut", campuran: "Campuran" };
const decisionKey = (d: Decision): StatusKey => (d === "Valid" ? "valid" : d === "Tidak Valid" ? "tidak-valid" : "lanjut");
export function StatusBadge({ status }: { status: StatusKey }) {
  return <span data-status={status} className={`inline-flex h-5 shrink-0 items-center rounded-sm border px-1.5 text-[12px] font-semibold leading-none ${BADGE[status]}`}>{LABEL[status]}</span>;
}
const kindIcon = (indicator: string) => JENIS.find((j) => j.key === jenisOf(indicator))?.icon ?? "layers";
const kindLabel = (c: CaseSummary) => JENIS.find((j) => j.key === jenisOf(c.indicator))?.label ?? c.label ?? c.indicator;

// ---------------------------------------------------------------- 3. recent activity
export function ActivityCard({ items, now, capped, onOpenCase }: { items: Activity[] | null; now: number; capped: boolean; onOpenCase: (caseId: string) => void }) {
  const [big, setBig] = useState(false);
  const action = <button type="button" onClick={() => setBig((b) => !b)} aria-expanded={big} aria-controls="aktivitas-list"
    aria-label={big ? "Perkecil aktivitas terbaru" : "Perbesar aktivitas terbaru"} title={big ? "Perkecil" : "Perbesar"}
    className="grid size-7 place-items-center rounded text-[#44546F] outline-none hover:bg-[#F4F5F7] focus-visible:ring-2 focus-visible:ring-[#c9a227]">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {big ? <path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" /> : <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />}</svg>
  </button>;
  return <SummaryCard title="Aktivitas terbaru" action={action}
    sub={`Keputusan tinjauan terakhir pada setiap kasus, terbaru di atas.${capped ? " Dihitung dari 500 deteksi terbaru." : ""}`}>
    {!items ? <p className="py-6 text-center text-xs" style={{ color: MUTED }}>Memuat…</p> : !items.length ? <Empty /> :
      <ul id="aktivitas-list" aria-label="Aktivitas terbaru" className={`divide-y overflow-y-auto pr-1 ${big ? "max-h-[640px]" : "max-h-[248px]"}`} style={{ borderColor: BORDER }}>
        {items.map((a) => <li key={a.key} data-activity={a.case.case_id} className="flex items-start gap-3 py-2.5" style={{ borderColor: BORDER }}>
          <Avatar name={a.reviewer} />
          <div className="min-w-0 flex-1 text-[13px] leading-6" style={{ color: TEXT }}>
            <strong className="font-semibold">{a.reviewer}</strong> memperbarui kasus{" "}
            <button type="button" onClick={() => onOpenCase(a.case.case_id)} className="inline-flex max-w-full items-center gap-1 rounded px-0.5 align-middle font-medium text-[#14213d] underline-offset-2 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-[#c9a227]"
              aria-label={`Buka kasus ${kindLabel(a.case)} ${a.case.student?.name ?? ""}`}>
              <LineIcon name={kindIcon(a.case.indicator)} size={14} /><span className="sr-only">{kindLabel(a.case)}: </span>
              <span className="truncate">{a.case.student?.name ?? "Siswa"} – {a.case.exam?.name ?? `Ujian ${a.case.exam_id}`}</span>
            </button>{" "}menjadi <StatusBadge status={decisionKey(a.decision)} />
            <p className="text-xs leading-5" style={{ color: MUTED }}><time dateTime={a.at} title={formatWib(parseUtc(a.at) ?? 0)}>{timeAgo(a.at, now)}</time>{a.events > 1 ? ` · ${a.events} kejadian` : ""}</p>
          </div>
        </li>)}
      </ul>}
  </SummaryCard>;
}

// ---------------------------------------------------------------- 4a. cases per kind (vertical bars, SVG)
export function KindBarChart({ bars, selected, onSelect }: { bars: KindBar[] | null; selected: JenisKey | null; onSelect: (k: JenisKey) => void }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [focus, setFocus] = useState<JenisKey | null>(null);
  const card = (body: ReactNode) => <SummaryCard title="Indikasi per jenis" sub="Jumlah kasus per jenis indikasi. Pilih batang untuk melihat siswanya.">{body}</SummaryCard>;
  if (!bars) return card(<p className="py-6 text-center text-xs" style={{ color: MUTED }}>Memuat…</p>);
  const max = Math.max(0, ...bars.map((b) => b.value));
  if (!max) return card(<Empty />);
  const ticks = axisTicks(max), top = ticks[ticks.length - 1];
  const H = 200, PAD_T = 18, AXIS = 28, BOTTOM = 46, plotW = Math.max(0, width - AXIS), slot = bars.length ? plotW / bars.length : 0;
  const barW = Math.max(8, Math.min(36, slot * 0.5));
  const y = (v: number) => PAD_T + (H - PAD_T) * (1 - v / top);
  const key = (e: ReactKeyboardEvent, k: JenisKey) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(k); } };
  const alt = `Indikasi per jenis: ${bars.map((b) => `${b.label} ${b.value} kasus`).join(", ")}.`;
  return card(<div ref={ref} className="w-full">
    {width > 0 && <svg width={width} height={H + BOTTOM} role="group" aria-label={alt} className="block overflow-visible">
      {ticks.map((t) => <g key={t} aria-hidden="true">
        <line x1={AXIS} x2={width} y1={y(t)} y2={y(t)} stroke={t === 0 ? "#C1C7D0" : "#EBECF0"} strokeWidth="1" />
        <text x={AXIS - 6} y={y(t)} dy="0.32em" textAnchor="end" fontSize="12" fill={MUTED}>{t}</text>
      </g>)}
      {bars.map((b, i) => {
        const cx = AXIS + slot * i + slot / 2, on = selected === b.key, h = H - y(b.value), x = cx - barW / 2, r = Math.min(4, h);
        const d = h > 0 ? `M${x},${H} V${H - h + r} Q${x},${H - h} ${x + r},${H - h} H${x + barW - r} Q${x + barW},${H - h} ${x + barW},${H - h + r} V${H} Z` : "";
        return <g key={b.key} role="button" tabIndex={0} aria-pressed={on} aria-label={`${b.label}: ${b.value} kasus${on ? ", dipilih" : ""}`} data-bar={b.key} data-value={b.value}
          onClick={() => onSelect(b.key)} onKeyDown={(e) => key(e, b.key)} onFocus={() => setFocus(b.key)} onBlur={() => setFocus(null)} className="cursor-pointer outline-none">
          <title>{`${b.label}: ${b.value} kasus (${b.pct}%)`}</title>
          <rect x={AXIS + slot * i + 2} y={0} width={Math.max(0, slot - 4)} height={H + BOTTOM - 2} fill="transparent" />
          {focus === b.key && <rect x={AXIS + slot * i + 2} y={1} width={Math.max(0, slot - 4)} height={H + BOTTOM - 4} rx="4" fill="none" stroke={GOLD} strokeWidth="2" />}
          {d && <path d={d} fill={on ? GOLD : NAVY} />}
          <text x={cx} y={y(b.value) - 6} textAnchor="middle" fontSize="12" fontWeight={on ? 700 : 500} fill={TEXT}>{b.value}</text>
          <g transform={`translate(${cx - 8},${H + 8})`} color={on ? "#5C4600" : "#44546F"}><LineIcon name={b.icon} /></g>
          <text x={cx} y={H + 38} textAnchor="middle" fontSize="12" fontWeight={on ? 700 : 400} fill={on ? TEXT : MUTED} textDecoration={on ? "underline" : undefined}>{b.short}</text>
        </g>;
      })}
    </svg>}
    <div className="sr-only"><table><caption>Indikasi per jenis</caption><thead><tr><th>Jenis</th><th>Kasus</th></tr></thead>
      <tbody>{bars.map((b) => <tr key={b.key}><td>{b.label}</td><td>{b.value}</td></tr>)}</tbody></table></div>
  </div>);
}

// ---------------------------------------------------------------- donuts: kinds and supervisor load
export function KindDonut({ slices, selected, onSelect }: { slices: KindSlice[] | null; selected: JenisKey | null; onSelect: (s: KindSlice) => void }) {
  const sel = slices?.find((s) => selected && s.kinds.includes(selected))?.key ?? null;
  return <DonutCard title="Jenis indikasi" sub="Bagian setiap jenis dari semua kasus. Pilih bagian untuk melihat siswanya." unit="kasus" attr="slice" caption="Jenis indikasi"
    slices={slices} selected={sel} onSelect={(key) => { const s = slices?.find((x) => x.key === key); if (s) onSelect(s); }}
    alt={(t) => `Jenis indikasi: total ${t} kasus. ${(slices ?? []).filter((s) => s.value).map((s) => `${s.label} ${s.value}`).join(", ")}.`} />;
}

export function LoadDonut({ slices }: { slices: LoadSlice[] | null }) {
  return <DonutCard title="Beban pengawas" sub="Kasus pada ujian yang diawasi setiap pengawas." unit="kasus" attr="load" caption="Beban pengawas"
    slices={slices && slices.map((s) => ({ key: s.key, label: s.label, value: s.value, color: s.color, note: `${s.pct}% · ${s.belum} belum ditinjau` }))}
    alt={(t) => `Beban pengawas: total ${t} kasus. ${(slices ?? []).map((s) => `${s.label} ${s.value} kasus, ${s.belum} belum ditinjau`).join("; ")}.`} />;
}

// ---------------------------------------------------------------- drawer: students behind a click
/** A small key frame of evidence that already exists. Loaded only on request: every opening is written to the audit
 *  log by the backend (and turns the notification ring grey), so the drawer does not open all evidence at once. */
function Thumb({ c, canOpen }: { c: CaseSummary; canOpen: boolean }) {
  const [url, setUrl] = useState<string | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const made = useRef<string | null>(null);
  useEffect(() => () => { if (made.current) URL.revokeObjectURL(made.current); }, []);
  const box = "grid h-[60px] w-20 shrink-0 place-items-center overflow-hidden rounded bg-[#F4F5F7] text-center text-[12px] leading-4";
  if (!c.latest_evidence_id) return <span className={box} style={{ color: MUTED }}>Tanpa bukti</span>;
  if (!canOpen) return <span className={box} style={{ color: MUTED }} title="Bukti gambar hanya untuk pengawas ujian dan admin">Terbatas</span>;
  if (url) return <img src={url} alt={`Cuplikan bukti ${c.student?.name ?? ""}`} data-thumb className="h-[60px] w-20 shrink-0 rounded object-cover" draggable={false} onContextMenu={(e) => e.preventDefault()} />;
  const load = () => {
    setState("loading");
    api.evidence(c.latest_evidence_id!).then((m) => api.evidenceFrameUrl(m.evidence_id, m.key_index))
      .then((u) => { made.current = u; setUrl(u); }).catch(() => setState("error"));
  };
  return <button type="button" onClick={load} disabled={state === "loading"} className={`${box} font-medium text-[#14213d] outline-none hover:bg-[#EBECF0] focus-visible:ring-2 focus-visible:ring-[#c9a227]`}
    aria-label={`Tampilkan cuplikan bukti ${c.student?.name ?? ""}`}>{state === "loading" ? "Memuat…" : state === "error" ? "Gagal, coba lagi" : "Tampilkan cuplikan"}</button>;
}

export function StudentDrawer({ source, cases, canOpenEvidence, onClose, onOpenCase }: {
  source: DrawerSource; cases: CaseSummary[]; canOpenEvidence: boolean; onClose: () => void; onOpenCase: (caseId: string) => void;
}) {
  const ref = useRef<HTMLElement>(null);
  useFocusTrap(ref, true, onClose);
  const title = drawerTitle(source);
  return createPortal(<>
    <div className="fixed inset-0 z-[64] bg-[#14213d]/20" aria-hidden="true" onClick={onClose} />
    <aside ref={ref} role="dialog" aria-modal="true" aria-labelledby="drawer-title" data-drawer className="notif-panel fixed inset-y-0 right-0 z-[65] flex w-full flex-col border-l bg-white sm:w-[440px]" style={{ borderColor: BORDER, color: TEXT }}>
      <div className="flex items-start justify-between gap-3 border-b px-5 py-4" style={{ borderColor: BORDER }}>
        <div className="min-w-0"><h2 id="drawer-title" className="font-sans text-base font-bold">{title}</h2>
          <p className="mt-0.5 text-xs" style={{ color: MUTED }}>{cases.length} kasus · pilih siswa untuk membuka tinjauan kasus</p></div>
        <button type="button" onClick={onClose} aria-label="Tutup daftar siswa" className="grid size-8 shrink-0 place-items-center rounded outline-none hover:bg-[#F4F5F7] focus-visible:ring-2 focus-visible:ring-[#c9a227]">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg></button>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-2">
        {!cases.length ? <div className="pt-4"><Empty /></div> :
          <ul className="divide-y" style={{ borderColor: BORDER }}>{cases.map((c) => <li key={c.case_id} data-drawer-case={c.case_id} className="flex items-start gap-3 py-3" style={{ borderColor: BORDER }}>
            <Thumb c={c} canOpen={canOpenEvidence} />
            <div className="min-w-0 flex-1">
              <button type="button" onClick={() => onOpenCase(c.case_id)} className="max-w-full truncate rounded text-left text-[13px] font-semibold text-[#14213d] underline-offset-2 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-[#c9a227]"
                aria-label={`Buka kasus ${c.student?.name ?? "Siswa"}, ${kindLabel(c)}`}>{c.student?.name ?? "Siswa"}</button>
              <p className="truncate text-xs" style={{ color: MUTED }}>{c.exam?.name ?? `Ujian ${c.exam_id}`}</p>
              <p className="mt-1 flex items-center gap-1 text-xs" style={{ color: MUTED }}><LineIcon name={kindIcon(c.indicator)} size={14} />{kindLabel(c)} · {c.event_count} kejadian</p>
              <p className="text-xs" style={{ color: MUTED }}><time dateTime={c.last_start_ts}>{formatWib(parseUtc(c.last_start_ts) ?? 0)}</time></p>
            </div>
            <StatusBadge status={statusOf(c)} />
          </li>)}</ul>}
      </div>
      <p className="border-t px-5 py-3 text-xs" style={{ borderColor: BORDER, color: MUTED }}>Indikasi bukan bukti pelanggaran. Keputusan tetap di tangan pengawas.</p>
    </aside>
  </>, document.body);
}
