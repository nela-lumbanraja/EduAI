// Camera / microphone handling, OpenVidu (LiveKit protocol) connection and the
// fallback frame uploader. Nothing here touches API secrets: the room token comes
// from the backend (join / session-state) and is valid for one room only.
import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track, type RemoteTrack, type RemoteParticipant } from "livekit-client";
import { api, type MonitoringInfo } from "./api";

export type StudentMedia = {
  stream: MediaStream;               // the one capture: preview, frame uploader and live broadcast
  setCamera: (on: boolean) => Promise<void>;
  setMic: (on: boolean) => Promise<void>;
  cameraOn: () => boolean;
  micOn: () => boolean;
  stop: () => Promise<void>;
};

const VIDEO = { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15, max: 24 } };

export function mediaErrorMessage(e: unknown): string {
  const name = (e as { name?: string })?.name;
  if (name === "NotAllowedError" || name === "SecurityError") return "Izin kamera/mikrofon ditolak. Izinkan akses di pengaturan browser, lalu muat ulang halaman.";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "Kamera atau mikrofon tidak ditemukan pada perangkat ini.";
  if (name === "NotReadableError") return "Kamera sedang dipakai aplikasi lain. Tutup aplikasi tersebut lalu coba lagi.";
  if (!window.isSecureContext) return "Kamera hanya dapat dipakai lewat HTTPS atau http://localhost.";
  if (name === "UnsupportedError") return "Browser ini tidak mendukung kamera/mikrofon. Buka EduAI di Chrome (Android) atau Safari (iPhone) versi terbaru, bukan dari browser di dalam aplikasi seperti WhatsApp atau Instagram.";
  return "Kamera/mikrofon tidak dapat dibuka.";
}

/** Open camera+mic once. The preview, the AI frames and the live broadcast (OpenVidu or Jitsi) all use these tracks,
 *  so what the supervisor watches and what the AI analyses come from the same capture. */
export async function startStudentMedia(): Promise<StudentMedia> {
  // Some in-app browsers and old phones have no camera API at all (navigator.mediaDevices is undefined).
  if (window.isSecureContext && !navigator.mediaDevices?.getUserMedia) throw Object.assign(new Error("getUserMedia unsupported"), { name: "UnsupportedError" });
  const stream = await navigator.mediaDevices.getUserMedia({ video: VIDEO, audio: true });
  const v = () => stream.getVideoTracks()[0];
  const a = () => stream.getAudioTracks()[0];
  return {
    stream,
    setCamera: async (on) => { if (v()) v().enabled = on; },
    setMic: async (on) => { if (a()) a().enabled = on; },
    cameraOn: () => !!v() && v().enabled && v().readyState === "live",
    micOn: () => !!a() && a().enabled && a().readyState === "live",
    stop: async () => { stream.getTracks().forEach((t) => t.stop()); },
  };
}

export type LiveKitTicket = { url: string; room: string; token: string };

/**
 * Student broadcast to OpenVidu while `ticket` is set; the backend withholds it in Jitsi mode, so a student is on one
 * broadcast only. Publishes the page's own tracks (never a second capture) and leaves them running when it stops:
 * they still feed the preview, the AI frames and Jitsi. A fresh token comes with every poll; only a room change reconnects.
 */
/** Wait before reconnect attempt n (0-based): 3 s, 6 s, 12 s, then every 20 s. */
export const reconnectDelay = (attempt: number) => Math.min(20_000, 3_000 * 2 ** Math.max(0, attempt));

export function useOpenViduBroadcast(ticket: LiveKitTicket | null, stream: MediaStream | null, camOn: boolean, micOn: boolean) {
  const ticketRef = useRef(ticket);
  useEffect(() => { ticketRef.current = ticket; });
  const key = ticket && stream ? `${ticket.url}|${ticket.room}` : null;
  const [state, setState] = useState<{ connected: boolean; error: string | null }>({ connected: false, error: null });
  const [started, setStarted] = useState<string | null>(null);
  // Reconnect: the video server may start after the student (e.g. Docker still booting) or drop the connection.
  // Without this the student stayed unconnected and the supervisor saw "Video langsung tidak tersedia" until a reload.
  const [attempt, setAttempt] = useState(0);
  if (key !== started) { setStarted(key); setState({ connected: false, error: null }); setAttempt(0); }
  const roomRef = useRef<Room | null>(null);

  useEffect(() => {
    const t = ticketRef.current;
    if (!key || !t || !stream) return;
    let cancelled = false;
    let retry: number | undefined;
    const again = (why: string) => {
      if (cancelled || retry !== undefined) return;
      const wait = reconnectDelay(attempt);
      setState({ connected: false, error: `${why} Mencoba menyambung lagi dalam ${Math.round(wait / 1000)} detik…` });
      retry = window.setTimeout(() => { if (!cancelled) setAttempt((n) => n + 1); }, wait);
    };
    const room = new Room({ adaptiveStream: false, dynacast: true, stopLocalTrackOnUnpublish: false });
    room.on(RoomEvent.Disconnected, () => again("Terputus dari OpenVidu."));
    (async () => {
      try {
        await room.connect(t.url, t.token);
        const v = stream.getVideoTracks()[0], a = stream.getAudioTracks()[0];
        if (!cancelled && v) await room.localParticipant.publishTrack(v, { source: Track.Source.Camera });
        if (!cancelled && a) await room.localParticipant.publishTrack(a, { source: Track.Source.Microphone });
        if (cancelled) return;
        roomRef.current = room;
        setState({ connected: true, error: null });
      } catch (e) {
        again(`Tidak dapat terhubung ke OpenVidu (${(e as Error).message || "koneksi gagal"}).`);
      }
    })();
    return () => { cancelled = true; if (retry !== undefined) window.clearTimeout(retry); roomRef.current = null; void room.disconnect(false); };
  }, [key, stream, attempt]);

  // Camera/mic off: mute the publication too, so OpenVidu and the AI worker see a muted track, not black frames.
  useEffect(() => {
    const room = roomRef.current;
    if (!room || !state.connected) return;
    for (const [source, on] of [[Track.Source.Camera, camOn], [Track.Source.Microphone, micOn]] as const) {
      const t = room.localParticipant.getTrackPublication(source)?.track;
      if (t && t.isMuted === on) void (on ? t.unmute() : t.mute());
    }
  }, [camOn, micOn, state.connected]);
  return state;
}

type UploadConfig = Pick<MonitoringInfo, "upload_fps" | "max_width" | "jpeg_quality">;

/**
 * Fallback frame path (works without OpenVidu): every 1/upload_fps seconds draw the
 * preview <video> into a canvas, encode a JPEG and POST it. Never more than one upload
 * in flight; frames are skipped (not queued) when the network or server is slow.
 */
export class FrameUploader {
  private timer: number | null = null;
  private inFlight = false;
  private canvas = document.createElement("canvas");
  private abort: AbortController | null = null;
  sent = 0;
  skipped = 0;
  lastError = "";

  constructor(private examId: number, private video: HTMLVideoElement, private cameraOn: () => boolean) {}

  start(cfg: UploadConfig) {
    this.stop();
    const every = Math.max(200, Math.round(1000 / Math.max(0.2, cfg.upload_fps)));
    this.timer = window.setInterval(() => void this.tick(cfg), every);
  }

  stop() {
    if (this.timer !== null) window.clearInterval(this.timer);
    this.timer = null;
    this.abort?.abort();
  }

  get running() { return this.timer !== null; }

  private async tick(cfg: UploadConfig) {
    if (this.inFlight) { this.skipped++; return; }
    const v = this.video;
    if (!this.cameraOn() || v.readyState < 2 || !v.videoWidth) return;   // camera off: send nothing
    const scale = Math.min(1, cfg.max_width / v.videoWidth);
    this.canvas.width = Math.round(v.videoWidth * scale);
    this.canvas.height = Math.round(v.videoHeight * scale);
    const ctx = this.canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(v, 0, 0, this.canvas.width, this.canvas.height);
    const blob = await new Promise<Blob | null>((r) => this.canvas.toBlob(r, "image/jpeg", cfg.jpeg_quality || 0.8));
    if (!blob) return;
    this.inFlight = true;
    this.abort = new AbortController();
    try {
      const r = await api.uploadFrame(this.examId, blob, this.abort.signal);
      if (r.accepted) this.sent++; else this.skipped++;
      this.lastError = "";
    } catch (e) {
      if ((e as Error).name !== "AbortError") this.lastError = (e as Error).message;
    } finally {
      this.inFlight = false;
    }
  }
}

/** Live microphone level 0..1 for the device check. */
export function useMicLevel(stream: MediaStream | null) {
  const [level, setLevel] = useState(0);
  useEffect(() => {
    if (!stream || !stream.getAudioTracks().length) return;
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const src = ctx.createMediaStreamSource(stream);
    const an = ctx.createAnalyser();
    an.fftSize = 512;
    src.connect(an);
    const buf = new Uint8Array(an.fftSize);
    let raf = 0;
    const loop = () => {
      an.getByteTimeDomainData(buf);
      let sum = 0;
      for (const b of buf) sum += ((b - 128) / 128) ** 2;
      setLevel(Math.min(1, Math.sqrt(sum / buf.length) * 4));
      raf = requestAnimationFrame(loop);
    };
    loop();
    return () => { cancelAnimationFrame(raf); src.disconnect(); void ctx.close(); };
  }, [stream]);
  return level;
}

/** Round-trip time to the EduAI backend (median of 3), in ms; null when unreachable. */
export async function measureLatency(): Promise<number | null> {
  const times: number[] = [];
  for (let i = 0; i < 3; i++) {
    const t0 = performance.now();
    try { await api.health(); times.push(performance.now() - t0); } catch { return null; }
  }
  return Math.round(times.sort((a, b) => a - b)[1]);
}

/** Attach a MediaStream or LiveKit track to a <video>. */
export function useVideo(source: MediaStream | RemoteTrack | null | undefined) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !source) return;
    if (source instanceof MediaStream) {
      el.srcObject = source;
      void el.play().catch(() => undefined);
      return () => { el.srcObject = null; };
    }
    source.attach(el);
    return () => { source.detach(el); };
  }, [source]);
  return ref;
}

/**
 * Supervisor view: join the exam room subscribe-only and expose each student's camera
 * track (identity "student-<id>"). Returns {} with a reason when OpenVidu is not configured.
 */
export function useExamVideoRoom(examId: number | null, enabled: boolean) {
  const [tracks, setTracks] = useState<Record<number, RemoteTrack>>({});
  const [status, setStatus] = useState<{ connected: boolean; reason: string | null }>({ connected: false, reason: null });
  useEffect(() => {
    if (!examId || !enabled) return;
    let room: Room | null = null;
    let cancelled = false;
    const refresh = () => {
      if (!room) return;
      const next: Record<number, RemoteTrack> = {};
      room.remoteParticipants.forEach((p: RemoteParticipant) => {
        const m = /^student-(\d+)$/.exec(p.identity);
        const t = p.getTrackPublication(Track.Source.Camera)?.track;
        if (m && t) next[Number(m[1])] = t as RemoteTrack;
      });
      setTracks(next);
    };
    (async () => {
      try {
        const j = await api.join(examId);
        if (cancelled) return;
        if (!j.livekit) { setStatus({ connected: false, reason: j.livekit_reason }); return; }
        room = new Room({ adaptiveStream: true, dynacast: true });
        room.on(RoomEvent.TrackSubscribed, refresh).on(RoomEvent.TrackUnsubscribed, refresh)
          .on(RoomEvent.ParticipantDisconnected, refresh).on(RoomEvent.TrackMuted, refresh).on(RoomEvent.TrackUnmuted, refresh)
          .on(RoomEvent.Disconnected, () => setStatus({ connected: false, reason: "Terputus dari OpenVidu" }));
        await room.connect(j.livekit.url, j.livekit.token);
        if (cancelled) { await room.disconnect(); return; }
        setStatus({ connected: true, reason: null });
        refresh();
      } catch (e) {
        if (!cancelled) setStatus({ connected: false, reason: `OpenVidu tidak dapat dihubungi: ${(e as Error).message}` });
      }
    })();
    return () => { cancelled = true; void room?.disconnect(); setTracks({}); };
  }, [examId, enabled]);
  return { tracks, ...status };
}
