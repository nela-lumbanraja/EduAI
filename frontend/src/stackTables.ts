// Tabel data di HP (< 768 px): setiap baris tampil sebagai kartu, dengan judul kolom di depan setiap nilai.
// Tabel yang ikut diberi kelas "m-stack". Modul ini hanya menyalin teks <th> ke atribut data-label pada sel
// (<td>) yang sesuai; index.css yang menampilkannya, hanya di bawah 768 px. Di desktop atribut itu tidak dipakai,
// jadi tampilannya tidak berubah. Pasang sekali dari main.tsx, seperti installScrollHints.

/** Label per sel untuk satu baris: kolom ke-n mengikuti <th> ke-n, sel dengan colspan memakan beberapa kolom.
 *  Sel yang mencakup lebih dari satu kolom (mis. baris "Belum ada data") tidak diberi label. */
export function cellLabels(headers: string[], colspans: number[]): (string | null)[] {
  const out: (string | null)[] = [];
  let col = 0;
  for (const span of colspans) {
    const n = Math.max(1, span || 1);
    out.push(n === 1 ? (headers[col] ?? "").trim() || null : null);
    col += n;
  }
  return out;
}

function label(table: HTMLTableElement) {
  const head = table.tHead?.rows[0];
  if (!head) return;
  const headers = [...head.cells].flatMap((th) => Array.from({ length: Math.max(1, th.colSpan) }, () => th.textContent ?? ""));
  for (const body of table.tBodies) {
    for (const row of body.rows) {
      const cells = [...row.cells];
      cellLabels(headers, cells.map((c) => c.colSpan)).forEach((text, i) => {
        const cell = cells[i];
        if (text && cell.dataset.label !== text) cell.dataset.label = text;
        else if (!text && cell.dataset.label !== undefined) delete cell.dataset.label;
        if (!text) cell.dataset.wide = ""; else if (cell.dataset.wide !== undefined) delete cell.dataset.wide;
      });
    }
  }
}

export function installStackLabels(root: ParentNode = document) {
  if (typeof MutationObserver === "undefined") return;
  let queued = false;
  const scan = () => { queued = false; root.querySelectorAll<HTMLTableElement>("table.m-stack").forEach(label); };
  // Only child-list changes (rows added, data loaded): the attributes written here never trigger another scan.
  new MutationObserver(() => { if (!queued) { queued = true; requestAnimationFrame(scan); } })
    .observe(root === document ? document.body : (root as Node), { childList: true, subtree: true });
  scan();
}
