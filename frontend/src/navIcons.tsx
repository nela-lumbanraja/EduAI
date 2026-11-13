// Sidebar icons: a line version (2 px stroke, lucide-style paths on a 24 px grid) and a filled version for the
// active menu. Drawn here; no icon library. Filled shapes use the current colour; inner details are cut out in white.
import type { ReactNode } from "react";
import type { NavIconName } from "./nav";

type Pair = { line: ReactNode; fill: ReactNode };
const W = "#fff";

const ICONS: Record<NavIconName | "menu", Pair> = {
  dashboard: {
    line: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /></>,
    fill: <g fill="currentColor"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /></g>,
  },
  calendar: {
    line: <><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></>,
    fill: <><rect x="3" y="4" width="18" height="18" rx="2" fill="currentColor" /><path d="M16 2v4M8 2v4" /><path d="M3 10h18" stroke={W} /></>,
  },
  monitor: {
    line: <><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></>,
    fill: <><rect x="2" y="3" width="20" height="14" rx="2" fill="currentColor" /><path d="M8 21h8M12 17v4" /></>,
  },
  bell: {
    line: <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></>,
    fill: <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" fill="currentColor" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></>,
  },
  history: {
    line: <><circle cx="12" cy="12" r="9.5" /><path d="M12 7v5l3.5 2" /></>,
    fill: <><circle cx="12" cy="12" r="9.5" fill="currentColor" /><path d="M12 7v5l3.5 2" stroke={W} /></>,
  },
  report: {
    line: <><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z" /><path d="M14 2v4a2 2 0 0 0 2 2h4M16 13H8M16 17H8M10 9H8" /></>,
    fill: <><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z" fill="currentColor" /><path d="M16 13H8M16 17H8M10 9H8" stroke={W} /></>,
  },
  video: {
    line: <><path d="m16 13 5.22 3.48a.5.5 0 0 0 .78-.42V7.87a.5.5 0 0 0-.75-.43L16 10.5" /><rect x="2" y="6" width="14" height="12" rx="2" /></>,
    fill: <><path d="m16 13 5.22 3.48a.5.5 0 0 0 .78-.42V7.87a.5.5 0 0 0-.75-.43L16 10.5z" fill="currentColor" /><rect x="2" y="6" width="14" height="12" rx="2" fill="currentColor" /></>,
  },
  users: {
    line: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
    fill: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2z" fill="currentColor" /><circle cx="9" cy="7" r="4" fill="currentColor" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
  },
  "user-check": {
    line: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="m16 11 2 2 4-4" /></>,
    fill: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2z" fill="currentColor" /><circle cx="9" cy="7" r="4" fill="currentColor" /><path d="m16 11 2 2 4-4" /></>,
  },
  shield: {
    line: <><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" /><path d="m9 12 2 2 4-4" /></>,
    fill: <><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" fill="currentColor" /><path d="m9 12 2 2 4-4" stroke={W} /></>,
  },
  sliders: {
    line: <><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3" /><circle cx="4" cy="12" r="2" /><circle cx="12" cy="10" r="2" /><circle cx="20" cy="14" r="2" /></>,
    fill: <><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3" /><g fill="currentColor"><circle cx="4" cy="12" r="2.6" /><circle cx="12" cy="10" r="2.6" /><circle cx="20" cy="14" r="2.6" /></g></>,
  },
  archive: {
    line: <><rect x="2" y="3" width="20" height="5" rx="1" /><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8M10 12h4" /></>,
    fill: <><rect x="2" y="3" width="20" height="5" rx="1" fill="currentColor" /><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="currentColor" /><path d="M10 12h4" stroke={W} /></>,
  },
  clipboard: {
    line: <><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2M12 11h4M12 16h4M8 11h.01M8 16h.01" /></>,
    fill: <><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2z" fill="currentColor" /><rect x="8" y="2" width="8" height="4" rx="1" fill="currentColor" stroke={W} strokeWidth="1.5" /><path d="M12 11h4M12 16h4M8 11h.01M8 16h.01" stroke={W} /></>,
  },
  menu: { line: <path d="M4 6h16M4 12h16M4 18h16" />, fill: <path d="M4 6h16M4 12h16M4 18h16" strokeWidth="2.6" /> },
};

export function NavIcon({ name, filled = false, size = 24 }: { name: NavIconName | "menu"; filled?: boolean; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true" data-filled={filled ? "true" : "false"} className="shrink-0">{filled ? ICONS[name].fill : ICONS[name].line}</svg>;
}
