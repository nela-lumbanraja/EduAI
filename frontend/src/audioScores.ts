// Grouping of YAMNet (AudioSet, 521 classes) scores into the numbers EduAI uses (speech, whisper, media, paper).
// Pure logic, no browser APIs, so it can be unit-tested with plain Node.
// Class names verified in YAMNet's yamnet_class_map.csv.

export const SPEECH = ["Speech", "Conversation", "Narration, monologue", "Babbling", "Child speech, kid speaking"];
export const WHISPER = ["Whispering"];
export const MEDIA = ["Music", "Television", "Radio"];
/** Paper/page sounds: a book or notes opened, leafed through or crumpled (names checked in the model's label list). */
export const PAPER = ["Rustle", "Crumpling, crinkling", "Tearing", "Flap"];

export type Category = { categoryName: string; score: number };
export type AudioScores = { speech: number; whisper: number; media: number; paper: number; top: string; topScore: number };

const round3 = (x: number) => Math.round(Math.min(1, Math.max(0, x)) * 1000) / 1000;

/** Max score per group over every category of every analysed chunk. */
export function groupScores(chunks: Category[][]): AudioScores {
  const out = { speech: 0, whisper: 0, media: 0, paper: 0, top: "", topScore: 0 };
  for (const cats of chunks) {
    for (const c of cats) {
      const name = c.categoryName;
      if (SPEECH.includes(name)) out.speech = Math.max(out.speech, c.score);
      else if (WHISPER.includes(name)) out.whisper = Math.max(out.whisper, c.score);
      else if (MEDIA.includes(name) || name.toLowerCase().endsWith(" music")) out.media = Math.max(out.media, c.score);
      else if (PAPER.includes(name)) out.paper = Math.max(out.paper, c.score);
      if (c.score > out.topScore) { out.top = name; out.topScore = c.score; }
    }
  }
  return { speech: round3(out.speech), whisper: round3(out.whisper), media: round3(out.media), paper: round3(out.paper), top: out.top, topScore: round3(out.topScore) };
}

/** Copy the most recent `n` samples out of a circular buffer (oldest first). */
export function lastSamples(ring: Float32Array, writePos: number, filled: number, n: number): Float32Array | null {
  if (filled < n) return null;
  const out = new Float32Array(n);
  let start = writePos - n;
  if (start < 0) start += ring.length;
  for (let i = 0; i < n; i++) out[i] = ring[(start + i) % ring.length];
  return out;
}
