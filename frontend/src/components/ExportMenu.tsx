/**
 * Reusable Export dropdown — CSV / JSON.
 *
 * Drop into any page header.
 */
import { useState } from "react";
import { Download, FileText, FileJson, ChevronDown } from "lucide-react";
import { exportCSV, exportJSON } from "../lib/exports";

type Props = {
  /** filename stem — extension is added automatically */
  filename: string;
  /** rows used for both CSV and JSON */
  rows: any[];
  disabled?: boolean;
};

export function ExportMenu({ filename, rows, disabled = false }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={disabled || rows.length === 0}
        className="flex items-center gap-1 glass border border-border px-3 py-1.5 rounded text-xs hover:bg-panel2 disabled:opacity-50 transition-fast"
        title={rows.length === 0 ? "No rows to export" : `Export ${rows.length} rows`}
      >
        <Download size={12} /> Export
        <ChevronDown size={11} className={`transition-fast ${open ? "rotate-180" : ""}`} />
      </button>
      {open && !disabled && (
        <div
          className="absolute right-0 mt-1 z-50 glass-strong border border-border rounded-md py-1 min-w-[160px] shadow-panel-strong"
          onMouseLeave={() => setOpen(false)}
        >
          <button
            onClick={() => { exportCSV(`${filename}.csv`, rows); setOpen(false); }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left hover:bg-panel2 transition-fast"
          >
            <FileText size={12} className="text-accent" /> CSV ({rows.length} rows)
          </button>
          <button
            onClick={() => { exportJSON(`${filename}.json`, rows); setOpen(false); }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left hover:bg-panel2 transition-fast"
          >
            <FileJson size={12} className="text-cyan" /> JSON ({rows.length} rows)
          </button>
        </div>
      )}
    </div>
  );
}
