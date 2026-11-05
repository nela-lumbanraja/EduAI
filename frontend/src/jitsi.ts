// Jitsi Meet video conference via lib-jitsi-meet. The library is loaded from the Jitsi deployment
// itself (https://<domain>/libs/lib-jitsi-meet.min.js) so its version always matches the server.
// No server is built in: the backend supplies it (EDUAI_JITSI_DOMAIN). This file never calls the EduAI API,
// so a meeting has no path to the AI; only the exam room sends frames, through FrameUploader.
import { useEffect, useRef, useState } from "react";

export type JitsiServer = { configured: boolean; domain: string | null; operator: "school" | "third_party" | null; xmpp_domain?: string | null; muc: string | null; service_url: string | null; auth?: boolean };
// One tokened connection per room: the token names the only room the Jitsi server lets it join.
const connectionOptions = (server: JitsiServer, room: string) => ({
  hosts: { domain: server.xmpp_domain || server.domain, muc: server.muc },
  serviceUrl: `${server.service_url}?room=${encodeURIComponent(room)}`,
});
// Media always goes through the bridge: no direct peer-to-peer link between a student and anyone else.
const CONFERENCE_OPTIONS = { p2p: { enabled: false } };
const JOIN_TIMEOUT_MS = 20000;

// Minimal typing of the lib-jitsi-meet surface used here.
export type JitsiTrack = {
  getType(): "audio" | "video";
  isLocal(): boolean;
  isMuted(): boolean;
  getParticipantId(): string;
  attach(el: HTMLMediaElement): void;
  detach(el: HTMLMediaElement): void;
  mute(): Promise<void>;
  unmute(): Promise<void>;
  dispose(): Promise<void>;
};
type JitsiConference = {
  on(event: string, fn: (...args: never[]) => void): void;
  addTrack(t: JitsiTrack): Promise<void>;
  setDisplayName(name: string): void;
  myUserId(): string;
  join(): void;
  leave(): Promise<void>;
};
type JitsiConnection = {
  addEventListener(event: string, fn: (...args: never[]) => void): void;
  connect(): void;
  disconnect(): Promise<void>;
  initJitsiConference(name: string, options: object): JitsiConference;
};
type JitsiMeetJSLib = {
  init(options: object): void;
  setLogLevel(level: unknown): void;
  logLevels: Record<string, unknown>;
  events: { connection: Record<string, string>; conference: Record<string, string>; track: Record<string, string> };
  errors: { conference: Record<string, string> };
  JitsiConnection: new (appId: null, token: string | null, options: object) => JitsiConnection;
  createLocalTracks(options: { devices: string[] }): Promise<JitsiTrack[]>;
  createLocalTracksFromMediaStreams?(items: { stream: MediaStream; track: MediaStreamTrack; sourceType: string; mediaType: string; videoType: string;
    constraints: { width?: number; height?: number } }[]): JitsiTrack[];
};
declare global { interface Window { JitsiMeetJS?: JitsiMeetJSLib } }

/** Jitsi tracks from camera/microphone tracks the page opened itself. */
function fromTracks(lib: JitsiMeetJSLib, list: MediaStreamTrack[]): JitsiTrack[] {
  return lib.createLocalTracksFromMediaStreams!(list.map((track) => {
    const { width, height } = track.getSettings();
    return { stream: new MediaStream([track]), track, mediaType: track.kind, sourceType: track.kind === "video" ? "camera" : "microphone",
      videoType: track.kind === "video" ? "camera" : "", constraints: { width, height } };
  }));
}

// Leaving a room (conference.leave -> dispose local tracks -> connection.disconnect) is asynchronous. Every leave on
// this page is queued here and every join waits for the queue first, so a re-entry never negotiates while the previous
// session of the same page is still leaving (lib-jitsi-meet can then throw in its codec selection, "reading 'payloads'").
let leaving: Promise<void> = Promise.resolve();
function queueLeave(steps: () => Promise<void>): Promise<void> {
  leaving = leaving.then(steps).catch(() => undefined);
  return leaving;
}
/** Resolves when every leave queued so far has finished. */
export function jitsiLeft(): Promise<void> {
  return leaving;
}

/** Closing or reloading the tab: start leaving at once instead of lingering as a participant until the server notices. */
function onPageHide(leave: () => void): () => void {
  window.addEventListener("pagehide", leave);
  return () => window.removeEventListener("pagehide", leave);
}

let loading: Promise<JitsiMeetJSLib> | null = null;
function loadLib(domain: string): Promise<JitsiMeetJSLib> {
  if (window.JitsiMeetJS) return Promise.resolve(window.JitsiMeetJS);
  loading ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = `https://${domain}/libs/lib-jitsi-meet.min.js`;
    s.async = true;
    s.onload = () => {
      const lib = window.JitsiMeetJS;
      if (!lib) { loading = null; reject(new Error("lib-jitsi-meet tidak tersedia")); return; }
      lib.init({});
      lib.setLogLevel(lib.logLevels.ERROR);
      resolve(lib);
    };
    s.onerror = () => { loading = null; s.remove(); reject(new Error(`Tidak dapat memuat lib-jitsi-meet dari ${domain}`)); };
    document.head.appendChild(s);
  });
  return loading;
}

/** Jitsi room names are lowercase; keep letters, digits and dashes only. */
export function jitsiRoomName(raw: string): string {
  return raw.toLowerCase().trim().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
}

export type JitsiParticipant = { id: string; name: string; tracks: JitsiTrack[] };
export type JitsiStatus = "idle" | "connecting" | "joined" | "error";

/** Joins `room` while it is non-null; leaving (room = null or unmount) disposes local tracks and disconnects. */
export function useJitsiRoom(room: string | null, displayName: string, server: JitsiServer | null,
  { devices = ["audio", "video"], attempt = 0, token = null, camera = null }:
  { devices?: ("audio" | "video")[]; attempt?: number; token?: string | null; camera?: MediaStream | null } = {}) {
  // A fresh token arrives with every poll; it must not restart the call, so it is read when connecting.
  const tokenRef = useRef(token);
  const cameraRef = useRef(camera);
  useEffect(() => { tokenRef.current = token; cameraRef.current = camera; });
  const [status, setStatus] = useState<JitsiStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [localTracks, setLocalTracks] = useState<JitsiTrack[]>([]);
  const [remotes, setRemotes] = useState<Record<string, JitsiParticipant>>({});
  const [, setTick] = useState(0); // re-render on mute changes
  const session = room && server?.domain ? [room, displayName, server.domain, server.muc, server.service_url, devices.join(), attempt].join("|") : null;
  const [startedSession, setStartedSession] = useState<string | null>(null);
  if (session !== startedSession) {
    setStartedSession(session);
    setStatus(session ? "connecting" : "idle");
    if (session) { setError(null); setRemotes({}); }
  }

  useEffect(() => {
    const domain = server?.domain;
    if (!room || !domain) return;
    let cancelled = false;
    let connection: JitsiConnection | null = null;
    let conference: JitsiConference | null = null;
    let tracks: JitsiTrack[] = [];
    const fail = (msg: string) => { if (!cancelled) { setStatus("error"); setError(msg); } };
    const timeout = window.setTimeout(() => fail(`Tidak dapat bergabung ke ${domain} (waktu habis).`), JOIN_TIMEOUT_MS);
    const upsert = (id: string, f: (p: JitsiParticipant) => JitsiParticipant) =>
      setRemotes((r) => ({ ...r, [id]: f(r[id] ?? { id, name: "Peserta", tracks: [] }) }));

    const stopHide = onPageHide(() => { void conference?.leave().catch(() => undefined); void connection?.disconnect().catch(() => undefined); });

    (async () => {
      const lib = await loadLib(domain);
      await jitsiLeft();                                // the previous session of this page has fully left
      if (cancelled) return;
      const ev = lib.events;
      connection = new lib.JitsiConnection(null, tokenRef.current ?? null, connectionOptions(server!, room));
      connection.addEventListener(ev.connection.CONNECTION_FAILED, (e: unknown) => fail(`Koneksi ke ${domain} gagal (${String(e)}).`));
      connection.addEventListener(ev.connection.CONNECTION_DISCONNECTED, () => fail(`Koneksi ke ${domain} terputus.`));
      connection.addEventListener(ev.connection.CONNECTION_ESTABLISHED, async () => {
        if (cancelled || !connection) return;
        const conf = connection.initJitsiConference(room, CONFERENCE_OPTIONS);
        conference = conf;
        conf.on(ev.conference.CONFERENCE_JOINED, () => { window.clearTimeout(timeout); if (!cancelled) { setStatus("joined"); setError(null); } });
        conf.on(ev.conference.CONFERENCE_FAILED, (e: string) => fail(
          e === lib.errors.conference.AUTHENTICATION_REQUIRED || e === lib.errors.conference.MEMBERS_ONLY_ERROR
            ? `Server ${domain} meminta login/moderator untuk membuat ruang ini. Gunakan server Jitsi sendiri (EDUAI_JITSI_DOMAIN).`
            : `Gagal bergabung ke ruang (${e}).`));
        conf.on(ev.conference.USER_JOINED, (id: string, user: { getDisplayName(): string | undefined }) =>
          upsert(id, (p) => ({ ...p, name: user.getDisplayName() || "Peserta" })));
        conf.on(ev.conference.USER_LEFT, (id: string) => setRemotes((r) => { const rest = { ...r }; delete rest[id]; return rest; }));
        conf.on(ev.conference.DISPLAY_NAME_CHANGED, (id: string, name: string) => upsert(id, (p) => ({ ...p, name })));
        conf.on(ev.conference.TRACK_ADDED, (t: JitsiTrack) => {
          if (t.isLocal()) return;
          upsert(t.getParticipantId(), (p) => ({ ...p, tracks: [...p.tracks.filter((x) => x !== t), t] }));
        });
        conf.on(ev.conference.TRACK_REMOVED, (t: JitsiTrack) => {
          if (t.isLocal()) return;
          const id = t.getParticipantId();
          // USER_LEFT may come first: do not bring a departed participant back as an empty tile.
          setRemotes((r) => (r[id] ? { ...r, [id]: { ...r[id], tracks: r[id].tracks.filter((x) => x !== t) } } : r));
        });
        conf.on(ev.conference.TRACK_MUTE_CHANGED, () => setTick((n) => n + 1));
        conf.setDisplayName(displayName);
        for (const t of tracks) await conf.addTrack(t).catch(() => undefined);
        conf.join();
      });
      try {
        // Exam room: only ever the camera the page already opened (a clone, so leaving Jitsi never stops the preview or
        // the AI frames). The broadcast is then the capture the AI analyses; a second capture is never opened.
        if (cameraRef.current) {
          const own = cameraRef.current.getVideoTracks()[0];
          if (!own || !lib.createLocalTracksFromMediaStreams) throw new Error("no own camera track");
          tracks = fromTracks(lib, [own.clone()]);
        } else {
          try { tracks = await lib.createLocalTracks({ devices }); } catch (e) {
            // Jitsi asks for sizes some cameras cannot give; open them plainly and hand the tracks over instead.
            if (!lib.createLocalTracksFromMediaStreams) throw e;
            const s = await navigator.mediaDevices.getUserMedia({ audio: devices.includes("audio"), video: devices.includes("video") });
            tracks = fromTracks(lib, s.getTracks());
          }
        }
      } catch {
        tracks = []; // join without camera/mic rather than not at all
        if (!cancelled) setError("Kamera/mikrofon tidak dapat dibuka; Anda bergabung tanpa video dan suara.");
      }
      if (cancelled) { tracks.forEach((t) => void t.dispose()); return; }
      setLocalTracks(tracks);
      connection.connect();
    })().catch((e) => fail((e as Error).message));

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
      stopHide();
      setLocalTracks([]); setRemotes({});
      void queueLeave(async () => {
        await conference?.leave().catch(() => undefined);
        await Promise.all(tracks.map((t) => t.dispose().catch(() => undefined)));
        await connection?.disconnect().catch(() => undefined);
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [room, displayName, server?.domain, server?.muc, server?.service_url, devices.join(), attempt]);

  const toggle = async (type: "audio" | "video") => {
    const t = localTracks.find((x) => x.getType() === type);
    if (!t) return;
    await (t.isMuted() ? t.unmute() : t.mute());
    setTick((n) => n + 1);
  };
  return { status, error, localTracks, participants: Object.values(remotes), toggle };
}

/** Attaches a Jitsi track to a <video>/<audio> element for as long as it is mounted. */
export function useJitsiTrack<T extends HTMLMediaElement>(track: JitsiTrack | undefined) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!track || !el) return;
    track.attach(el);
    return () => track.detach(el);
  }, [track]);
  return ref;
}

export type WatchRoom = { student_id: number; name: string; room: string; token: string | null };
export type WatchState = { status: JitsiStatus; track?: JitsiTrack; error?: string };

/** Supervisor view: joins every student's own room without a camera or microphone and keeps the student's video
 *  track. Nothing is recorded; leaving the page disconnects. */
export function useJitsiWatch(server: JitsiServer | null, rooms: WatchRoom[] | null) {
  const [state, setState] = useState<Record<number, WatchState>>({});
  const roomsRef = useRef(rooms);
  useEffect(() => { roomsRef.current = rooms; });
  const key = server?.domain && rooms?.length ? `${server.domain}|${rooms.map((r) => `${r.student_id}:${r.room}`).join(",")}` : null;
  const [watched, setWatched] = useState<string | null>(null);
  if (key !== watched) { setWatched(key); setState({}); }

  useEffect(() => {
    const list = roomsRef.current;
    if (!key || !server?.domain || !list) return;
    const domain = server.domain;
    let cancelled = false;
    const live: { conn?: JitsiConnection; conf?: JitsiConference }[] = [];
    const put = (id: number, f: (w: WatchState) => WatchState) =>
      setState((s) => (cancelled ? s : { ...s, [id]: f(s[id] ?? { status: "connecting" }) }));
    const stopHide = onPageHide(() => {
      for (const s of live) { void s.conf?.leave().catch(() => undefined); void s.conn?.disconnect().catch(() => undefined); }
    });
    (async () => {
      let lib: JitsiMeetJSLib;
      try { lib = await loadLib(domain); } catch (e) { list.forEach((r) => put(r.student_id, () => ({ status: "error", error: (e as Error).message }))); return; }
      await jitsiLeft();
      if (cancelled) return;
      const ev = lib.events;
      for (const r of list) {
        const slot: { conn?: JitsiConnection; conf?: JitsiConference } = {};
        live.push(slot);
        put(r.student_id, () => ({ status: "connecting" }));
        const conn = new lib.JitsiConnection(null, r.token, connectionOptions(server, r.room));
        slot.conn = conn;
        const fail = (msg: string) => put(r.student_id, (w) => ({ ...w, status: "error", error: msg }));
        conn.addEventListener(ev.connection.CONNECTION_FAILED, (e: unknown) => fail(`Koneksi gagal (${String(e)}).`));
        conn.addEventListener(ev.connection.CONNECTION_ESTABLISHED, () => {
          if (cancelled) return;
          const conf = conn.initJitsiConference(r.room, CONFERENCE_OPTIONS);
          slot.conf = conf;
          conf.on(ev.conference.CONFERENCE_JOINED, () => put(r.student_id, (w) => ({ ...w, status: "joined" })));
          conf.on(ev.conference.CONFERENCE_FAILED, (e: string) => fail(`Gagal bergabung (${e}).`));
          conf.on(ev.conference.TRACK_ADDED, (t: JitsiTrack) => {
            if (!t.isLocal() && t.getType() === "video") put(r.student_id, (w) => ({ ...w, track: t }));
          });
          conf.on(ev.conference.TRACK_REMOVED, (t: JitsiTrack) => put(r.student_id, (w) => (w.track === t ? { ...w, track: undefined } : w)));
          conf.setDisplayName("Pengawas");
          conf.join();
        });
        conn.connect();
      }
    })();
    return () => {
      cancelled = true;
      stopHide();
      void queueLeave(async () => {
        await Promise.all(live.map(async (s) => { await s.conf?.leave().catch(() => undefined); await s.conn?.disconnect().catch(() => undefined); }));
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}
