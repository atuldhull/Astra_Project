/**
 * Bottom-right toast stack. Singleton store via a tiny event bus so any
 * component can call `toast.success("done")` without prop drilling.
 *
 * Severity: info (cyan) | success (green) | warn (amber) | crit (red)
 * Auto-dismiss after 5 s; click anywhere on the toast to dismiss now.
 */
import { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, AlertOctagon, Info, X } from "lucide-react";

type Severity = "info" | "success" | "warn" | "crit";
type ToastEntry = { id: number; sev: Severity; title: string; body?: string; at: number };

let _id = 0;
const listeners = new Set<(e: ToastEntry[]) => void>();
const queue: ToastEntry[] = [];

function emit() {
  for (const fn of listeners) fn([...queue]);
}

function push(sev: Severity, title: string, body?: string) {
  const entry: ToastEntry = { id: ++_id, sev, title, body, at: Date.now() };
  queue.push(entry);
  emit();
  // auto-dismiss
  setTimeout(() => dismiss(entry.id), 5000);
  return entry.id;
}
function dismiss(id: number) {
  const idx = queue.findIndex((q) => q.id === id);
  if (idx >= 0) {
    queue.splice(idx, 1);
    emit();
  }
}

/** Public toast API — call from anywhere. */
export const toast = {
  info:    (title: string, body?: string) => push("info", title, body),
  success: (title: string, body?: string) => push("success", title, body),
  warn:    (title: string, body?: string) => push("warn", title, body),
  crit:    (title: string, body?: string) => push("crit", title, body),
  dismiss,
};

const ICONS = {
  info:    Info,
  success: CheckCircle2,
  warn:    AlertTriangle,
  crit:    AlertOctagon,
};
const COLOURS = {
  info:    "text-cyan border-cyan/40 shadow-glow-cyan",
  success: "text-threat-low border-threat-low/40 shadow-glow-low",
  warn:    "text-threat-high border-threat-high/40",
  crit:    "text-threat-crit border-threat-crit/40 shadow-glow-crit",
};

export function ToastViewport() {
  const [items, setItems] = useState<ToastEntry[]>([]);
  useEffect(() => {
    const fn = (e: ToastEntry[]) => setItems(e);
    listeners.add(fn);
    return () => { listeners.delete(fn); };
  }, []);

  return (
    <div className="fixed bottom-4 right-4 z-[10000] flex flex-col gap-2 max-w-sm pointer-events-none">
      {items.map((t) => {
        const Icon = ICONS[t.sev];
        return (
          <div
            key={t.id}
            onClick={() => dismiss(t.id)}
            className={`pointer-events-auto cursor-pointer glass-strong rounded-md px-3 py-2.5 ${COLOURS[t.sev]} flex items-start gap-2.5 min-w-[280px] animate-pin-pop`}
          >
            <Icon size={16} className="mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-text leading-tight">{t.title}</div>
              {t.body && <div className="text-xs text-muted mt-0.5 leading-snug">{t.body}</div>}
            </div>
            <button className="text-muted hover:text-text -m-1 p-1" aria-label="Dismiss">
              <X size={12} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
