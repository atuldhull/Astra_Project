/**
 * Bottom-right toast stack. Singleton store via a tiny event bus so any
 * component can call `toast.success("done")` without prop drilling.
 *
 * Severity: info (cyan) | success (green) | warn (amber) | crit (red)
 *
 * v3.0 upgrades:
 *   * Visible queue capped at MAX_VISIBLE — older toasts are dismissed
 *     to make room rather than letting the stack grow off-screen.
 *   * Identical (severity + title + body) toasts within DEDUPE_WINDOW_MS
 *     bump a count badge instead of stacking duplicates. Critical for
 *     the WebSocket flood path where one bad event can fire 30 toasts.
 *   * Auto-dismiss after AUTO_DISMISS_MS unless severity == "crit"
 *     (critical stays until user clicks).
 */
import { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, AlertOctagon, Info, X } from "lucide-react";

type Severity = "info" | "success" | "warn" | "crit";
type ToastEntry = {
  id: number;
  sev: Severity;
  title: string;
  body?: string;
  at: number;
  count: number; // bumped when an identical toast is replayed in the dedupe window
};

const MAX_VISIBLE = 5;
const DEDUPE_WINDOW_MS = 4000;
const AUTO_DISMISS_MS = 5000;

let _id = 0;
const listeners = new Set<(e: ToastEntry[]) => void>();
const queue: ToastEntry[] = [];
const timers = new Map<number, ReturnType<typeof setTimeout>>();

function emit() {
  for (const fn of listeners) fn([...queue]);
}

function scheduleDismiss(id: number, sev: Severity) {
  // Critical toasts stay until the user dismisses them — they're the
  // ones the operator must read.
  if (sev === "crit") return;
  const existing = timers.get(id);
  if (existing) clearTimeout(existing);
  const t = setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
  timers.set(id, t);
}

function push(sev: Severity, title: string, body?: string): number {
  // Dedupe: if an identical toast is already on screen and recent, bump count.
  const now = Date.now();
  const dup = queue.find(
    (q) => q.sev === sev && q.title === title && (q.body ?? "") === (body ?? "") && (now - q.at) < DEDUPE_WINDOW_MS,
  );
  if (dup) {
    dup.count += 1;
    dup.at = now; // refresh window so a steady stream stays grouped
    scheduleDismiss(dup.id, sev);
    emit();
    return dup.id;
  }

  const entry: ToastEntry = { id: ++_id, sev, title, body, at: now, count: 1 };
  queue.push(entry);
  scheduleDismiss(entry.id, sev);

  // Cap the stack — drop the oldest non-crit toast (or oldest period if
  // every visible is crit).
  while (queue.length > MAX_VISIBLE) {
    const oldestIdx = queue.findIndex((q) => q.sev !== "crit");
    const idx = oldestIdx >= 0 ? oldestIdx : 0;
    const dropped = queue.splice(idx, 1)[0];
    const t = timers.get(dropped.id);
    if (t) { clearTimeout(t); timers.delete(dropped.id); }
  }
  emit();
  return entry.id;
}

function dismiss(id: number) {
  const idx = queue.findIndex((q) => q.id === id);
  if (idx >= 0) {
    queue.splice(idx, 1);
    const t = timers.get(id);
    if (t) { clearTimeout(t); timers.delete(id); }
    emit();
  }
}

function clear() {
  queue.length = 0;
  for (const t of timers.values()) clearTimeout(t);
  timers.clear();
  emit();
}

/** Public toast API — call from anywhere. */
export const toast = {
  info:    (title: string, body?: string) => push("info", title, body),
  success: (title: string, body?: string) => push("success", title, body),
  warn:    (title: string, body?: string) => push("warn", title, body),
  crit:    (title: string, body?: string) => push("crit", title, body),
  dismiss,
  clear,
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
              <div className="text-sm font-semibold text-text leading-tight flex items-center gap-2">
                <span className="truncate">{t.title}</span>
                {t.count > 1 && (
                  <span className="text-2xs font-mono px-1.5 py-0.5 rounded bg-panel2 text-muted shrink-0">
                    ×{t.count}
                  </span>
                )}
              </div>
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
