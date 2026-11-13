// Small shared hooks (kept out of component files so React fast refresh works).
import { useEffect, useRef, useState, type RefObject } from "react";

/** Width of an element. A callback ref, so it also works when the element appears later (after a placeholder). */
export function useWidth<T extends HTMLElement>() {
  const [el, setEl] = useState<T | null>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return [setEl, width] as const;
}

const FOCUSABLE = "button:not([disabled]), [href], input:not([disabled]), textarea, select, [tabindex]:not([tabindex='-1'])";

/** Keep Tab inside `ref` while `active`; Esc calls onEscape; focus returns to the opener afterwards. */
export function useFocusTrap(ref: RefObject<HTMLElement | null>, active: boolean, onEscape: () => void) {
  const esc = useRef(onEscape);
  useEffect(() => { esc.current = onEscape; }, [onEscape]);
  useEffect(() => {
    if (!active) return;
    const opener = document.activeElement as HTMLElement | null;
    const first = () => ref.current?.querySelector<HTMLElement>(FOCUSABLE);
    window.setTimeout(() => first()?.focus(), 0);
    const onKey = (e: KeyboardEvent) => {
      if (!ref.current) return;
      if (e.key === "Escape") { e.stopPropagation(); esc.current(); return; }
      if (e.key !== "Tab") return;
      const items = [...ref.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      if (!items.length) return;
      const a = items[0], z = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === a || !ref.current.contains(document.activeElement))) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && (document.activeElement === z || !ref.current.contains(document.activeElement))) { e.preventDefault(); a.focus(); }
    };
    document.addEventListener("keydown", onKey, true);
    return () => { document.removeEventListener("keydown", onKey, true); opener?.focus?.(); };
  }, [active, ref]);
}

