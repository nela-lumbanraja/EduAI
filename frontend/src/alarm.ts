// Bunyi peringatan indikasi baru: bip buzzer piezo ala Arduino (gelombang kotak 2 kHz, tiga bip pendek,
// seperti tone(pin, 2000, 150)). Dibuat dengan Web Audio API, tanpa berkas audio.
// Browser hanya mengizinkan suara setelah pengguna berinteraksi dengan halaman, jadi AudioContext
// dibuka/dilanjutkan pada klik atau tombol keyboard pertama (installAlarmUnlock, dipanggil di main.tsx).

const MUTE_KEY = "eduai.alarm.muted";
const FREQ_HZ = 2000;
const BEEP_S = 0.15;
const GAP_S = 0.1;
const BEEPS = 3;
const VOLUME = 0.06;          // gelombang kotak terdengar keras; tetap pelan agar tidak mengagetkan

let ctx: AudioContext | null = null;

function context(): AudioContext | null {
  if (ctx) return ctx;
  const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctx) return null;
  try { ctx = new Ctx(); } catch { ctx = null; }
  return ctx;
}

export function alarmMuted(): boolean {
  try { return window.localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
}

export function setAlarmMuted(muted: boolean) {
  try { if (muted) window.localStorage.setItem(MUTE_KEY, "1"); else window.localStorage.removeItem(MUTE_KEY); } catch { /* private mode */ }
}

/** Tiga bip 2 kHz. Diam saja bila disenyapkan, browser tidak mendukung, atau belum ada interaksi pengguna. */
export function playAlarm() {
  if (alarmMuted()) return;
  const ac = context();
  if (!ac) return;
  if (ac.state === "suspended") void ac.resume().catch(() => undefined);
  const start = ac.currentTime + 0.02;
  for (let i = 0; i < BEEPS; i++) {
    const t = start + i * (BEEP_S + GAP_S);
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = "square";
    osc.frequency.value = FREQ_HZ;
    gain.gain.setValueAtTime(0, t);                       // tepi lunak 5 ms agar tidak "klik"
    gain.gain.linearRampToValueAtTime(VOLUME, t + 0.005);
    gain.gain.setValueAtTime(VOLUME, t + BEEP_S - 0.005);
    gain.gain.linearRampToValueAtTime(0, t + BEEP_S);
    osc.connect(gain).connect(ac.destination);
    osc.start(t);
    osc.stop(t + BEEP_S + 0.01);
  }
}

/** Buka AudioContext pada interaksi pertama sehingga bunyi berikutnya boleh diputar oleh browser. */
export function installAlarmUnlock() {
  const unlock = () => {
    const ac = context();
    if (ac && ac.state === "suspended") void ac.resume().catch(() => undefined);
    if (ac?.state === "running") { window.removeEventListener("pointerdown", unlock); window.removeEventListener("keydown", unlock); }
  };
  window.addEventListener("pointerdown", unlock);
  window.addEventListener("keydown", unlock);
}
