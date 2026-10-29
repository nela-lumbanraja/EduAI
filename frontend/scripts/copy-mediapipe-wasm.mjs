// Copies the MediaPipe Audio Tasks Wasm files from node_modules into public/, so the browser loads
// them from this site (no CDN). Runs automatically before `npm run dev` and `npm run build`.
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "@mediapipe", "tasks-audio", "wasm");
const dest = join(root, "public", "mediapipe-audio");
if (!existsSync(src)) {
  console.error("[copy-mediapipe-wasm] @mediapipe/tasks-audio is not installed: run npm install");
  process.exit(1);
}
mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });
console.log("[copy-mediapipe-wasm] copied to public/mediapipe-audio");
