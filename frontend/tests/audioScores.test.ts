// Run: node --experimental-strip-types tests/audioScores.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { groupScores, lastSamples } from "../src/audioScores.ts";

test("groups YAMNet classes into speech / whisper / media (max over chunks)", () => {
  const s = groupScores([
    [{ categoryName: "Speech", score: 0.42 }, { categoryName: "Pop music", score: 0.2 }, { categoryName: "Silence", score: 0.1 }],
    [{ categoryName: "Conversation", score: 0.61 }, { categoryName: "Whispering", score: 0.15 }, { categoryName: "Television", score: 0.3 }],
  ]);
  assert.deepEqual(s, { speech: 0.61, whisper: 0.15, media: 0.3, paper: 0, top: "Conversation", topScore: 0.61 });
});

test("unknown classes only affect the top label, empty input is all zero", () => {
  assert.deepEqual(groupScores([[{ categoryName: "Dog", score: 0.9 }]]), { speech: 0, whisper: 0, media: 0, paper: 0, top: "Dog", topScore: 0.9 });
  assert.deepEqual(groupScores([]), { speech: 0, whisper: 0, media: 0, paper: 0, top: "", topScore: 0 });
});

test("paper/page sounds (book opened or leafed through) form their own score", () => {
  const s = groupScores([[{ categoryName: "Rustle", score: 0.31 }, { categoryName: "Speech", score: 0.2 }], [{ categoryName: "Crumpling, crinkling", score: 0.44 }, { categoryName: "Flap", score: 0.1 }]]);
  assert.equal(s.paper, 0.44); assert.equal(s.speech, 0.2);
  assert.equal(groupScores([[{ categoryName: "Rustling leaves", score: 0.9 }]]).paper, 0);     // leaves outside are not paper
});

test("scores are clamped to 0..1 and rounded (what the backend accepts)", () => {
  const s = groupScores([[{ categoryName: "Speech", score: 1.00001 }, { categoryName: "Music", score: 0.123456 }]]);
  assert.equal(s.speech, 1);
  assert.equal(s.media, 0.123);
});

test("lastSamples reads the newest samples in order from the ring buffer", () => {
  const ring = new Float32Array([5, 6, 7, 1, 2, 3, 4]);    // written 1..7, write position wrapped to index 3
  assert.deepEqual(Array.from(lastSamples(ring, 3, 7, 4)!), [4, 5, 6, 7]);
  assert.equal(lastSamples(ring, 3, 3, 4), null);           // not enough audio yet
});
