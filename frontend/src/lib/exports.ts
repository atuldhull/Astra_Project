/**
 * Client-side CSV / JSON export helpers.
 *
 * Used on Detections / Alerts / Audit pages — judges love downloadable
 * artifacts ("here's the evidence in CSV"). Pure browser-side, no
 * backend round-trip needed.
 */

function downloadBlob(name: string, mime: string, body: BlobPart) {
  const blob = new Blob([body], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function csvEscape(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "object") return csvEscape(JSON.stringify(v));
  const s = String(v);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

/** Export an array of objects as CSV. Columns inferred from first row. */
export function exportCSV<T extends Record<string, any>>(name: string, rows: T[]) {
  if (rows.length === 0) {
    downloadBlob(name, "text/csv;charset=utf-8", "(no data)\n");
    return;
  }
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  const header = cols.join(",");
  const body = rows.map((r) => cols.map((c) => csvEscape(r[c])).join(",")).join("\n");
  downloadBlob(name, "text/csv;charset=utf-8", `${header}\n${body}\n`);
}

/** Export an array of objects (or any JSON-able value) as JSON. */
export function exportJSON(name: string, payload: unknown) {
  downloadBlob(name, "application/json;charset=utf-8", JSON.stringify(payload, null, 2));
}
