// Optional speech-sound analysis in the STUDENT'S BROWSER (only after the student's separate consent).
//
// The microphone track that is already open for the exam is read through Web Audio into a 2-second
// circular buffer in memory. Every `interval_ms`, YAMNet (MediaPipe Audio Classifier, run locally in
// WebAssembly) classifies the last second and only three numbers are sent to the backend:
// speech, whisper and music/TV. Audio is never recorded, stored or uploaded.
import { api, assetUrl, type MonitoringInfo } from "./api";
import { groupScores, lastSamples, type AudioScores } from "./audioScores";

type Classifier = { classify: (data: Float32Array, sampleRate?: number) => { classifications: { categories: { categoryName: string; score: number }[] }[] }[]; close: () => void };
export type SpeechStatus = "off" | "loading" | "running" | "muted" | "error";

let classifierPromise: Promise<Classifier> | null = null;

/** Loads the Wasm runtime (served from /mediapipe-audio) and the YAMNet file (served by the backend) once. */
function loadClassifier(modelUrl: string): Promise<Classifier> {
  if (!classifierPromise) {
    classifierPromise = (async () => {
      const { AudioClassifier } = await import("@mediapipe/tasks-audio");
      // The 0.10.32 ES bundle does not export FilesetResolver, so the Wasm fileset is given explicitly.
      // Files are copied from node_modules to /mediapipe-audio by scripts/copy-mediapipe-wasm.mjs.
      const base = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/mediapipe-audio`;
      const fileset = { wasmLoaderPath: `${base}/audio_wasm_internal.js`, wasmBinaryPath: `${base}/audio_wasm_internal.wasm` };
      return await AudioClassifier.createFromOptions(fileset, { baseOptions: { modelAssetPath: assetUrl(modelUrl) } }) as unknown as Classifier;
    })();
    classifierPromise.catch(() => { classifierPromise = null; });       // allow a retry later
  }
  return classifierPromise;
}

export class SpeechScorer {
  status: SpeechStatus = "off";
  lastError = "";
  last: AudioScores | null = null;
  sent = 0;
  private ctx: AudioContext | null = null;
  private node: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private ring = new Float32Array(0);
  private writePos = 0;
  private filled = 0;
  private timer: number | null = null;
  private inFlight = false;
  private runId = 0;

  constructor(private examId: number, private micOn: () => boolean) {}

  get running() { return this.timer !== null; }

  async start(stream: MediaStream, cfg: NonNullable<MonitoringInfo["audio"]>) {
    this.stop();
    const run = ++this.runId;
    const track = stream.getAudioTracks()[0];
    if (!track) { this.status = "error"; this.lastError = "Mikrofon tidak tersedia."; return; }
    this.status = "loading";
    try {
      const classifier = await loadClassifier(cfg.model_url);
      if (run !== this.runId) return;                                   // stopped while loading
      this.ctx = new AudioContext();
      this.ring = new Float32Array(Math.round(this.ctx.sampleRate * 2));   // 2 s, memory only
      this.writePos = 0;
      this.filled = 0;
      this.source = this.ctx.createMediaStreamSource(new MediaStream([track]));
      this.node = this.ctx.createScriptProcessor(4096, 1, 1);
      this.node.onaudioprocess = (ev) => this.push(ev.inputBuffer.getChannelData(0));
      const sink = this.ctx.createGain();
      sink.gain.value = 0;                                              // keep the graph running, play nothing
      this.source.connect(this.node);
      this.node.connect(sink);
      sink.connect(this.ctx.destination);
      await this.ctx.resume().catch(() => undefined);
      this.status = "running";
      this.lastError = "";
      this.timer = window.setInterval(() => void this.tick(classifier), Math.max(250, cfg.interval_ms || 500));
    } catch (e) {
      if (run !== this.runId) return;
      this.status = "error";
      this.lastError = (e as Error).message || "Analisis suara tidak dapat dimulai.";
      this.teardown();
    }
  }

  stop() {
    this.runId++;
    if (this.timer !== null) window.clearInterval(this.timer);
    this.timer = null;
    this.teardown();
    this.status = "off";
    this.last = null;
  }

  private teardown() {
    this.node?.disconnect();
    this.source?.disconnect();
    if (this.node) this.node.onaudioprocess = null;
    void this.ctx?.close().catch(() => undefined);
    this.node = null; this.source = null; this.ctx = null;
    this.ring = new Float32Array(0);                                    // drop the buffered sound
    this.filled = 0;
  }

  private push(x: Float32Array) {
    const r = this.ring;
    if (!r.length) return;
    for (let i = 0; i < x.length; i++) {
      r[this.writePos] = x[i];
      this.writePos = (this.writePos + 1) % r.length;
    }
    this.filled = Math.min(r.length, this.filled + x.length);
  }

  private async tick(classifier: Classifier) {
    if (!this.ctx || this.inFlight) return;
    if (!this.micOn()) { this.status = "muted"; return; }               // student muted: send nothing
    this.status = "running";
    const clip = lastSamples(this.ring, this.writePos, this.filled, Math.round(this.ctx.sampleRate));
    if (!clip) return;
    let scores: AudioScores;
    try {
      const results = classifier.classify(clip, this.ctx.sampleRate);
      scores = groupScores(results.map((r) => r.classifications[0]?.categories ?? []));
    } catch (e) {
      this.lastError = (e as Error).message;
      return;
    }
    this.last = scores;
    this.inFlight = true;
    try {
      const r = await api.audioScores(this.examId, { speech: scores.speech, whisper: scores.whisper, media: scores.media });
      if (r.accepted) this.sent++;
      this.lastError = "";
    } catch (e) {
      this.lastError = (e as Error).message;
    } finally {
      this.inFlight = false;
    }
  }
}
