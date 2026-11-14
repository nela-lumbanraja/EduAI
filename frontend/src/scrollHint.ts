// Penanda "bisa digeser" untuk area overflow-x-auto (tabel, baris filter, tab) di layar sempit.
// Setiap area diberi data-scroll="start" | "end" | "both" selama masih ada isi tersembunyi di sisi itu;
// index.css memudarkan tepi tersebut. Tanpa overflow, atributnya dihapus sehingga tampilan desktop tidak berubah.

const SELECTOR = ".overflow-x-auto";

function state(el: HTMLElement): string {
  const max = el.scrollWidth - el.clientWidth;
  if (max <= 2) return "";
  const left = el.scrollLeft > 2, right = el.scrollLeft < max - 2;
  return left && right ? "both" : left ? "start" : right ? "end" : "";
}

function update(el: HTMLElement) {
  const next = state(el);
  if ((el.dataset.scroll ?? "") === next) return;
  if (next) el.dataset.scroll = next; else delete el.dataset.scroll;
}

export function installScrollHints(root: ParentNode = document) {
  if (typeof ResizeObserver === "undefined" || typeof MutationObserver === "undefined") return;
  const tracked = new Set<HTMLElement>();
  const resize = new ResizeObserver((entries) => entries.forEach((e) => update(e.target as HTMLElement)));
  const onScroll = (e: Event) => update(e.currentTarget as HTMLElement);
  const scan = () => {
    for (const el of tracked) if (!el.isConnected) { tracked.delete(el); resize.unobserve(el); el.removeEventListener("scroll", onScroll); }
    root.querySelectorAll<HTMLElement>(SELECTOR).forEach((el) => {
      if (!tracked.has(el)) { tracked.add(el); resize.observe(el); el.addEventListener("scroll", onScroll, { passive: true }); }
    });
    tracked.forEach(update);            // content may have grown (data loaded) without the box resizing
  };
  let frame = 0;
  new MutationObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(scan); })
    .observe(document.body, { childList: true, subtree: true });
  scan();
}
