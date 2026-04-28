/**
 * time — formatting helpers tuned for an Indian-ops console.
 *
 * Defence operators read better with:
 *   • Relative time for the most-recent ~24h ("2m ago", "1h ago")
 *   • Absolute IST (en-IN, 24-hour) for everything older or on hover.
 *
 * No external deps — keeps the bundle small. Resolution caps at minutes
 * because second-level precision is noise on an audit log scrolling
 * every few seconds.
 */

const IST_LOCALE = "en-IN";
const IST_TZ = "Asia/Kolkata";

export function parseIso(input: string | Date | null | undefined): Date | null {
  if (input == null) return null;
  if (input instanceof Date) return input;
  const d = new Date(input);
  if (Number.isNaN(d.getTime())) return null;
  return d;
}

/** "2m ago", "1h ago", "yesterday", "Apr 28 11:43" — never seconds. */
export function relativeTime(input: string | Date | null | undefined, now: Date = new Date()): string {
  const d = parseIso(input);
  if (!d) return "—";
  const diffMs = now.getTime() - d.getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  if (hours < 48) return "yesterday";
  // Fall back to absolute short for older
  return d.toLocaleString(IST_LOCALE, {
    timeZone: IST_TZ,
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** Full IST timestamp — "2026-04-28 17:08:42 IST" — for tooltips. */
export function absoluteIst(input: string | Date | null | undefined): string {
  const d = parseIso(input);
  if (!d) return "—";
  const formatted = d.toLocaleString(IST_LOCALE, {
    timeZone: IST_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  // en-IN renders dd/mm/yyyy, hh:mm:ss — keep but append IST tag.
  return `${formatted} IST`;
}

/** Compact HH:MM:SS in IST for tight columns (e.g. live tail logs). */
export function clockIst(input: string | Date | null | undefined): string {
  const d = parseIso(input);
  if (!d) return "--:--:--";
  return d.toLocaleTimeString(IST_LOCALE, {
    timeZone: IST_TZ,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}
