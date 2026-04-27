/**
 * Status pill — small inline badge with status colour, dot, and label.
 *
 * Used for: backend connection status, GPU health, federated state,
 * audit chain validity, alert status, OOD flags, etc.
 *
 * Variants:
 *   - "ok"       green dot + green text
 *   - "warn"     amber dot
 *   - "err"      red dot, optional pulse
 *   - "info"     cyan dot
 *   - "neutral"  muted dot
 *   - "live"     green pulsing dot (e.g. WebSocket connected)
 */
import { ReactNode } from "react";

type Variant = "ok" | "warn" | "err" | "info" | "neutral" | "live";
type Size = "sm" | "md";

const VARIANT_CLASS: Record<Variant, { bg: string; text: string; border: string; dot: string; pulse?: boolean }> = {
  ok:      { bg: "bg-threat-low/15",  text: "text-threat-low",  border: "border-threat-low/40",  dot: "bg-threat-low" },
  warn:    { bg: "bg-threat-med/15",  text: "text-threat-med",  border: "border-threat-med/40",  dot: "bg-threat-med" },
  err:     { bg: "bg-threat-crit/15", text: "text-threat-crit", border: "border-threat-crit/40", dot: "bg-threat-crit", pulse: true },
  info:    { bg: "bg-cyan/15",        text: "text-cyan",        border: "border-cyan/40",        dot: "bg-cyan" },
  neutral: { bg: "bg-panel2",         text: "text-muted",       border: "border-border",         dot: "bg-muted" },
  live:    { bg: "bg-threat-low/15",  text: "text-threat-low",  border: "border-threat-low/40",  dot: "bg-threat-low", pulse: true },
};

const SIZE_CLASS: Record<Size, { box: string; text: string; dot: string }> = {
  sm: { box: "px-1.5 py-0.5 gap-1",   text: "text-2xs", dot: "w-1.5 h-1.5" },
  md: { box: "px-2 py-1 gap-1.5",     text: "text-xs",  dot: "w-2 h-2" },
};

type Props = {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
  className?: string;
  /** Optional title attribute for tooltip */
  title?: string;
};

export function StatusPill({ variant = "neutral", size = "md", children, className = "", title }: Props) {
  const v = VARIANT_CLASS[variant];
  const s = SIZE_CLASS[size];
  return (
    <span
      className={`inline-flex items-center font-mono uppercase-wide tracking-wider border rounded ${v.bg} ${v.text} ${v.border} ${s.box} ${s.text} ${className}`}
      title={title}
    >
      <span className={`rounded-full ${v.dot} ${s.dot} ${v.pulse ? "animate-pulse-soft" : ""}`} />
      {children}
    </span>
  );
}
