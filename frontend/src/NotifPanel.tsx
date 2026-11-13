// Notification panel (slides in from the right) and the story-style evidence viewer.
// Evidence = the JPEG snapshots the backend already stores per event (no video, no audio): shown as a slideshow,
// 4 s per image. Opening evidence goes through GET /api/evidence/{id}, which the backend restricts to the exam's
// supervisor and admins and writes to the audit log. Nothing is recorded or stored here.
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { useFocusTrap } from "./hooks";
import { createPortal } from "react-dom";
import { api, type CaseSummary, type Decision, type ExamSummary, type NotifState, type User } from "./api";
import { JENIS, jenisOf } from "./indikasi";
import { LineIcon } from "./IndikasiRingkasan";
import {
  LEGACY_KEYS, NOTIF_FILTERS, SLIDE_MS, buildRows, dismissedCaseIds, filterRows, groupByTime, isUnread, nextPos, prevPos, ringOf, rowText,
  segmentFill, storySegments, visibleRows, withMark, type NotifFilter, type NotifRow, type Segment, type StoryPos,
} from "./notifikasi";
import { formatWib, timeAgo } from "./time";

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
function Avatar({ name, size = 44, ring = "tidak-ada" }: { name: string; size?: number; ring?: "baru" | "dilihat" | "tidak-ada" }) {
  const ringCls = ring === "baru" ? "ring-2 ring-[#C9A227] ring-offset-2" : ring === "dilihat" ? "ring-2 ring-[#C1C7D0] ring-offset-2" : "";
  return <span data-ring={ring} className={`grid shrink-0 place-items-center rounded-full bg-[#F1E7C4] font-semibold text-[#14213d] ${ringCls}`} style={{ width: size, height: size, fontSize: size * 0.32 }}>{initials(name)}</span>;
}

// ---------------------------------------------------------------- panel
export function NotifPanel({ open, onClose, cases, summaries, user, canOpenEvidence, canMark, canReview, onReview, onReport, onOpenSummary }: {
  open: boolean; onClose: () => void; cases: CaseSummary[]; summaries: ExamSummary[]; user: User; canOpenEvidence: boolean; canReview: boolean;
  /** Read/Abaikan state on the server: only the exam's supervisor and admins (other roles: no blue dot, no Abaikan). */
  canMark: boolean;
  onReview: (c: CaseSummary) => void; onReport: (examId: number) => void; onOpenSummary: (examId: number) => void;
}) {
  const ref = useRef<HTMLElement>(null);
  const [filter, setFilter] = useState<NotifFilter>("semua");
  const [cannot, setCannot] = useState<Parameters<typeof buildRows>[1]>([]);
  const [now, setNow] = useState(() => Date.now());
  const [marks, setMarks] = useState<NotifState>({});
  const [markErr, setMarkErr] = useState("");
  const [story, setStory] = useState<NotifRow | null>(null);
  // the earlier version kept this state in localStorage: remove it, the server is the only store now
  useEffect(() => { try { for (const k of LEGACY_KEYS(user.id)) window.localStorage.removeItem(k); } catch { /* storage blocked */ } }, [user.id]);
  const activity = useMemo(() => cases.map((c) => `${c.case_id}:${c.event_count}:${c.evidence_count}`).join("|"), [cases]);
  const loadMarks = useCallback(() => {
    if (!canMark) return;
    api.notificationState().then((r) => setMarks(r.cases)).catch(() => undefined);
  }, [canMark]);
  useEffect(() => { if (open && !story) loadMarks(); }, [open, story, activity, loadMarks]);
  useFocusTrap(ref, open && !story, onClose);
  useEffect(() => {
    if (!open) return;
    let stop = false;
    const tick = () => { setNow(Date.now()); api.events({ category: "cannot_analyze", limit: 500 }).then((r) => { if (!stop) setCannot(r.events); }).catch(() => undefined); };
    tick();
    const t = window.setInterval(tick, 30000);
    return () => { stop = true; window.clearInterval(t); };
  }, [open]);
  /** PUT/DELETE on the server; the local copy changes at once and is reloaded from the server afterwards. */
  const send = (ids: string[], field: "read" | "dismissed", value: boolean) => {
    if (!canMark || !ids.length) return;
    setMarks((m) => withMark(m, ids, field, value)); setMarkErr("");
    Promise.all(ids.map((id) => (field === "read" ? api.notificationRead(id) : api.notificationDismiss(id, value))))
      .catch(() => setMarkErr("Status notifikasi tidak tersimpan di server. Coba lagi."))
      .finally(loadMarks);
  };
  const all = buildRows(cases, cannot);
  const rows = visibleRows(all, marks);
  const shown = filterRows(rows, filter);
  const unreviewed = cases.filter((c) => c.unreviewed_count > 0 || !c.review_status).length;
  const hiddenIds = dismissedCaseIds(all, marks);
  const dismissedCount = all.length - rows.length;
  const caseIds = (r: NotifRow) => r.cases.map((c) => c.case_id);
  const review = (r: NotifRow) => { send(caseIds(r), "read", true); onClose(); onReview(r.cases.find((c) => c.unreviewed_count > 0 || !c.review_status) ?? r.cases[0]); };
  const playStory = (r: NotifRow) => { send(caseIds(r), "read", true); setStory(r); };
  if (!open) return null;
  // Rendered into <body>: the top bar is its own stacking context, so the sidebar and bottom bar would cover the panel.
  return createPortal(<>
    <div className="fixed inset-0 z-[64] bg-[#14213d]/10" aria-hidden="true" onClick={onClose} />
    <aside ref={ref} role="dialog" aria-modal="true" aria-labelledby="notif-title" className="notif-panel fixed inset-y-0 right-0 z-[65] flex w-full flex-col border-l border-[#E2E5EA] bg-white text-[#1D2433] sm:w-[400px]">
      <div className="flex items-start justify-between gap-3 px-5 pb-3 pt-5">
        <div><h2 id="notif-title" className="font-sans text-xl font-bold text-[#14213d]">Notifikasi</h2><p className="mt-0.5 text-[13px] text-[#626F86]">{unreviewed} kasus belum ditinjau</p></div>
        <button type="button" onClick={onClose} aria-label="Tutup notifikasi" className="grid size-9 place-items-center rounded text-[#14213d] outline-none hover:bg-[#F4F5F7] focus-visible:ring-2 focus-visible:ring-[#c9a227]"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg></button>
      </div>
      <div role="toolbar" aria-label="Saring notifikasi" className="flex shrink-0 gap-2 overflow-x-auto border-b border-[#E2E5EA] px-5 pb-3">
        {NOTIF_FILTERS.map((f) => <button key={f.key} type="button" aria-pressed={filter === f.key} data-filter={f.key} onClick={() => setFilter(f.key)}
          className={`h-8 shrink-0 whitespace-nowrap rounded-md border px-3 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-[#c9a227] ${filter === f.key ? "border-[#14213d] bg-[#14213d] text-white" : "border-[#DFE1E6] bg-white hover:bg-[#F4F5F7]"}`}>{f.label}</button>)}
      </div>
      <div className="flex-1 overflow-y-auto px-5 pb-6">
        {filter === "semua" && summaries.length > 0 && <section className="pt-4"><h3 className="font-sans text-sm font-bold">Ringkasan ujian</h3>
          {summaries.slice(0, 2).map((s) => <button key={s.exam_id} type="button" onClick={() => { onClose(); onOpenSummary(s.exam_id); }} className="mt-2 flex w-full items-center gap-3 rounded py-1.5 text-left outline-none hover:bg-[#F4F5F7] focus-visible:ring-2 focus-visible:ring-[#c9a227]">
            <span className="grid size-11 shrink-0 place-items-center rounded-full bg-[#F4F5F7] text-[#14213d]"><LineIcon name="layers" size={18} /></span>
            <span className="min-w-0 text-[13px]"><span className="line-clamp-2">{s.kind === "pre_end" ? "Ringkasan 10 menit sebelum selesai" : "Ringkasan akhir"} · {s.summary.exam_name}</span><span className="text-xs text-[#626F86]">{s.summary.students.filter((x) => x.indications.length).length} siswa dengan indikasi</span></span>
          </button>)}</section>}
        {groupByTime(shown, now).map((g) => <section key={g.group} className="pt-4" aria-label={g.group}>
          <h3 className="font-sans text-sm font-bold" data-group={g.group}>{g.group}</h3>
          <ul>{g.rows.map((r) => { const ring = ringOf(r, marks, canOpenEvidence); const unread = canMark && isUnread(r, marks); return <li key={r.key} data-row={r.key} className="flex items-center gap-3 py-2.5">
            {ring === "tidak-ada" ? <Avatar name={r.student.name} /> :
              <button type="button" onClick={() => playStory(r)} aria-label={`Putar bukti ${r.student.name}${ring === "dilihat" ? " (sudah dilihat)" : ""}`} className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-[#14213d] focus-visible:ring-offset-4"><Avatar name={r.student.name} ring={ring} /></button>}
            <div className="min-w-0 flex-1">
              <p className="line-clamp-2 text-[13px] leading-[18px]" title={rowText(r)}><strong className="font-semibold">{r.student.name}</strong>{rowText(r).slice(r.student.name.length)}</p>
              <p className="mt-0.5 truncate text-xs text-[#626F86]">{r.exam.name} · <time dateTime={new Date(r.latest).toISOString()}>{timeAgo(new Date(r.latest).toISOString(), now)}</time></p>
            </div>
            {unread && <span aria-label="Belum dibaca" role="img" data-unread className="size-2 shrink-0 rounded-full bg-[#0095F6]" />}
            <div className="flex shrink-0 gap-1.5">
              {r.kind === "kasus" ? <button type="button" onClick={() => review(r)} aria-label={`Tinjau ${r.student.name}`} className="h-8 rounded bg-[#14213d] px-3 text-xs font-semibold text-white outline-none hover:bg-[#1d2b49] focus-visible:ring-2 focus-visible:ring-[#c9a227]">{canReview ? "Tinjau" : "Lihat"}</button>
                : <button type="button" onClick={() => { onClose(); onReport(r.exam.id); }} aria-label={`Lihat laporan ${r.exam.name}`} className="h-8 rounded bg-[#14213d] px-3 text-xs font-semibold text-white outline-none hover:bg-[#1d2b49] focus-visible:ring-2 focus-visible:ring-[#c9a227]">Lihat</button>}
              {canMark && r.kind === "kasus" && <button type="button" onClick={() => send(caseIds(r), "dismissed", true)} aria-label={`Abaikan notifikasi ${r.student.name}`} className="h-8 rounded bg-[#EFEFEF] px-3 text-xs font-semibold text-[#1D2433] outline-none hover:bg-[#E2E2E2] focus-visible:ring-2 focus-visible:ring-[#c9a227]">Abaikan</button>}
            </div>
          </li>; })}</ul>
        </section>)}
        {!shown.length && <div className="grid place-items-center py-16 text-center"><span className="grid size-14 place-items-center rounded-full border-2 border-[#DFE1E6] text-[#8590A2]"><LineIcon name="check" size={22} /></span><p className="mt-3 text-[13px] text-[#626F86]">Belum ada notifikasi untuk filter ini.</p></div>}
        {markErr && <p role="alert" className="mt-4 text-xs text-[#AE2E24]">{markErr}</p>}
        {dismissedCount > 0 && <button type="button" onClick={() => send(hiddenIds, "dismissed", false)} className="mt-4 text-xs font-medium text-[#14213d] underline-offset-2 hover:underline">{dismissedCount} notifikasi diabaikan · Tampilkan lagi</button>}
      </div>
    </aside>
    {story && <StoryViewer row={story} user={user} canReview={canReview} onClose={() => setStory(null)} />}
  </>, document.body);
}

// ---------------------------------------------------------------- story viewer
const DECISIONS: [Decision, string][] = [["Valid", "Valid"], ["Tidak Valid", "Tidak valid"], ["Perlu Tinjauan Lanjut", "Perlu tinjauan lanjut"]];

export function StoryViewer({ row, user, canReview, onClose }: { row: NotifRow; user: User; canReview: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, true, onClose);
  const [segs, setSegs] = useState<Segment[] | null>(null);
  const [eventIds, setEventIds] = useState<Record<string, string[]>>({});
  const [err, setErr] = useState("");
  const [frames, setFrames] = useState<number[]>([]);
  const [urls, setUrls] = useState<Record<string, string[]>>({});
  const [pos, setPos] = useState<StoryPos>({ seg: 0, frame: 0, done: false });
  const [elapsed, setElapsed] = useState(0);
  const [paused, setPaused] = useState(false);
  const [hold, setHold] = useState(false);                 // typing a note pauses the story
  const [menu, setMenu] = useState(false);
  const [copied, setCopied] = useState("");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<Record<string, Decision>>({});
  const [busy, setBusy] = useState(false);
  const [clock, setClock] = useState(() => Date.now());
  const all = useRef<string[]>([]);
  useEffect(() => { const t = window.setInterval(() => setClock(Date.now()), 30000); return () => window.clearInterval(t); }, []);
  useEffect(() => () => { for (const u of all.current) URL.revokeObjectURL(u); }, []);
  // case details -> one segment per event that has evidence
  useEffect(() => {
    let stop = false;
    Promise.all(row.cases.map((c) => api.caseDetail(c.case_id).then((d) => ({ caseId: c.case_id, events: d.events }))))
      .then((d) => { if (stop) return; const s = storySegments(d); setSegs(s); setFrames(s.map(() => 1)); setEventIds(Object.fromEntries(d.map((x) => [x.caseId, x.events.map((e) => e.event_id)]))); })
      .catch((e: Error) => { if (!stop) setErr(e.message || "Bukti tidak dapat dimuat."); });
    return () => { stop = true; };
  }, [row]);
  const seg = segs?.[pos.seg];
  // the images of the current evidence (GET /api/evidence/{id} is audited by the backend)
  useEffect(() => {
    if (!seg || urls[seg.evidenceId]) return;
    let stop = false;
    const si = pos.seg;
    api.evidence(seg.evidenceId).then(async (m) => {
      const list = await Promise.all(Array.from({ length: m.frame_count }, (_, i) => api.evidenceFrameUrl(m.evidence_id, i)));
      all.current.push(...list);
      if (stop) return;
      setUrls((u) => ({ ...u, [seg.evidenceId]: list }));
      setFrames((f) => f.map((n, i) => (i === si ? list.length : n)));
    }).catch((e: Error) => { if (!stop) setErr(e.message || "Bukti tidak dapat dimuat."); });
    return () => { stop = true; };
  }, [seg, urls, pos.seg]);
  const ready = !!seg && !!urls[seg.evidenceId];
  const running = ready && !paused && !hold && !menu && !pos.done;
  useEffect(() => {
    if (!running) return;
    const t0 = Date.now() - elapsed;
    const t = window.setInterval(() => {
      const e = Date.now() - t0;
      if (e >= SLIDE_MS) { setElapsed(0); setPos((p) => nextPos(p, frames)); } else setElapsed(e);
    }, 100);
    return () => window.clearInterval(t);
    // elapsed is read once when the timer starts
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, pos, frames]);
  const go = (dir: 1 | -1) => { setElapsed(0); setMenu(false); setPos((p) => (dir > 0 ? nextPos(p, frames) : prevPos(p, frames))); };
  const onKey = (e: ReactKeyboardEvent) => {
    if ((e.target as HTMLElement).closest("textarea, input")) return;
    if (e.key === "ArrowRight") { e.preventDefault(); go(1); } else if (e.key === "ArrowLeft") { e.preventDefault(); go(-1); } else if (e.key === " ") { e.preventDefault(); setPaused((p) => !p); }
  };
  const fill = segmentFill(pos, frames, elapsed);
  const kind = seg ? JENIS.find((j) => j.key === jenisOf(seg.indicator)) : undefined;
  const save = async () => {
    if (!seg || !decision) return;
    setBusy(true); setErr("");
    try { await api.reviewCase(seg.caseId, decision, note.trim(), eventIds[seg.caseId] ?? [seg.eventId]); setSaved((s) => ({ ...s, [seg.caseId]: decision })); setNote(""); }
    catch (e) { setErr((e as Error).message || "Keputusan tidak tersimpan."); }
    finally { setBusy(false); }
  };
  const copy = async () => {
    if (!seg) return;
    const link = `${window.location.origin}${window.location.pathname}?kasus=${encodeURIComponent(seg.caseId)}`;
    try { await navigator.clipboard.writeText(link); setCopied("Tautan kasus disalin."); } catch { setCopied(link); }
    setMenu(false);
  };
  const frameUrl = seg ? urls[seg.evidenceId]?.[pos.frame] : undefined;
  const btn = "grid size-9 place-items-center rounded text-white outline-none hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-[#c9a227]";
  const icon = (d: ReactNode) => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>;
  return <div ref={ref} role="dialog" aria-modal="true" aria-label={`Bukti indikasi ${row.student.name}`} onKeyDown={onKey} className="fixed inset-0 z-[80] flex items-stretch justify-center bg-[#111] text-white sm:items-center sm:p-6">
    <div className="flex h-full w-full flex-col sm:h-auto sm:max-h-full sm:w-[min(92vw,820px)]">
      <div className="relative min-h-0 flex-1 overflow-hidden bg-black sm:aspect-[4/3] sm:flex-none sm:rounded">
        {frameUrl && <img src={frameUrl} alt={`Cuplikan bukti ${pos.frame + 1} dari ${frames[pos.seg] ?? 1}: ${seg?.label ?? ""}`} draggable={false} onContextMenu={(e) => e.preventDefault()} className="absolute inset-0 size-full select-none object-contain" />}
        {!frameUrl && !err && <p className="absolute inset-0 grid place-items-center text-sm text-white/70">{segs && !segs.length ? "Belum ada cuplikan bukti untuk siswa ini." : "Memuat bukti…"}</p>}
        {err && <p role="alert" className="absolute inset-x-6 top-1/2 -translate-y-1/2 rounded bg-black/70 p-3 text-center text-sm">{err}</p>}
        {/* watermark */}
        <p aria-hidden="true" className="pointer-events-none absolute bottom-3 right-3 select-none text-[12px] text-white/55">EduAI · Rahasia · {user.name} · {formatWib(clock)}</p>
        {/* previous / next areas */}
        <button type="button" onClick={() => go(-1)} aria-label="Bukti sebelumnya" className="absolute inset-y-0 left-0 w-1/3 outline-none focus-visible:bg-white/5" />
        <button type="button" onClick={() => go(1)} aria-label="Bukti berikutnya" className="absolute inset-y-0 right-0 w-1/3 outline-none focus-visible:bg-white/5" />
        {/* top: progress + header */}
        <div className="absolute inset-x-0 top-0 bg-black/45 px-3 pb-2 pt-2.5">
          <div className="flex gap-1" aria-hidden="true">{fill.map((f, i) => <span key={i} className="h-[3px] flex-1 overflow-hidden rounded-full bg-white/35"><span data-segment-fill={f.toFixed(2)} className="block h-full bg-white" style={{ width: `${f * 100}%` }} /></span>)}</div>
          <div className="mt-2.5 flex items-center gap-2.5">
            <Avatar name={row.student.name} size={32} />
            <div className="min-w-0 flex-1 text-[13px] leading-tight"><p className="truncate font-semibold">{row.student.name}</p><p className="truncate text-white/75">{seg ? `${seg.label} · ${formatWib(new Date(seg.start).getTime())}` : row.exam.name}</p></div>
            <span className="sr-only" aria-live="polite">{segs?.length ? `Bukti ${pos.seg + 1} dari ${segs.length}, gambar ${pos.frame + 1} dari ${frames[pos.seg] ?? 1}${pos.done ? ", selesai" : ""}` : ""}</span>
            <button type="button" onClick={() => setPaused(!paused)} aria-label={paused ? "Putar" : "Jeda"} className={btn}>{icon(paused ? <path d="m7 4 13 8-13 8z" /> : <path d="M8 5v14M16 5v14" />)}</button>
            <div className="relative"><button type="button" onClick={() => setMenu(!menu)} aria-label="Opsi lainnya" aria-expanded={menu} className={btn}>{icon(<path d="M5 12h.01M12 12h.01M19 12h.01" strokeWidth="3" />)}</button>
              {menu && <div role="menu" className="absolute right-0 top-10 z-10 w-48 rounded border border-white/15 bg-[#262626] py-1 text-sm"><button type="button" role="menuitem" onClick={() => void copy()} className="block w-full px-3 py-2 text-left hover:bg-white/10 focus-visible:bg-white/10 outline-none">Salin tautan kasus</button></div>}</div>
            <button type="button" onClick={onClose} aria-label="Tutup penampil bukti" className={btn}>{icon(<path d="M18 6 6 18M6 6l12 12" />)}</button>
          </div>
        </div>
      </div>
      {/* bottom: kind, AI score, supervisor decision */}
      <div className="shrink-0 bg-[#1b1b1b] px-4 py-3 sm:rounded-b" onFocus={() => setHold(true)} onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setHold(false); }}>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]">
          <span className="inline-flex items-center gap-1.5 rounded bg-white/10 px-2 py-1 font-semibold">{kind && <LineIcon name={kind.icon} />}{seg?.label ?? "—"}</span>
          {seg && <span className="text-white/75">{seg.score !== null ? `Skor keyakinan AI ${seg.score.toFixed(2).replace(".", ",")}` : "Skor AI tidak tersedia"} · indikasi, bukan bukti</span>}
          {copied && <span role="status" className="text-xs text-[#E3C35B]">{copied}</span>}
        </div>
        {canReview && seg && <div className="mt-3">
          {saved[seg.caseId] && <p role="status" className="mb-2 text-xs text-[#E3C35B]">Keputusan tersimpan: {DECISIONS.find((d) => d[0] === saved[seg.caseId])?.[1]}.</p>}
          <div role="radiogroup" aria-label="Keputusan pengawas" className="flex flex-wrap gap-2">
            {DECISIONS.map(([d, l]) => <button key={d} type="button" role="radio" aria-checked={decision === d} onClick={() => setDecision(d)}
              className={`h-8 rounded border px-3 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-[#c9a227] ${decision === d ? "border-[#C9A227] bg-[#C9A227] text-[#14213d]" : "border-white/25 bg-transparent text-white hover:bg-white/10"}`}>{l}</button>)}
          </div>
          <div className="mt-2 flex gap-2">
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} placeholder="Catatan pengawas…" aria-label="Catatan pengawas"
              className="h-9 min-w-0 flex-1 rounded border border-white/25 bg-transparent px-3 text-[13px] text-white placeholder:text-white/50 outline-none focus-visible:ring-2 focus-visible:ring-[#c9a227]" />
            <button type="button" onClick={() => void save()} disabled={!decision || busy} className="h-9 rounded bg-white px-4 text-xs font-semibold text-[#14213d] outline-none disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-[#c9a227]">{busy ? "Menyimpan…" : "Simpan"}</button>
          </div>
        </div>}
        <p className="mt-2 text-xs text-white/65">Indikasi bukan bukti pelanggaran. Keputusan tetap di tangan pengawas.</p>
      </div>
    </div>
  </div>;
}
