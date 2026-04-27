/**
 * HUD overlay primitives — used on top of the Mission viewer canvas.
 *
 * `<HudCornerStat>` — small mono key=value chip in any corner of a Bezel.
 * `<HudCrosshair>`  — center-screen crosshair with rotating outer ring.
 * `<HudRecBadge>`   — blinking 'REC' indicator (top-left).
 * `<HudThreatBar>`  — mini horizontal threat bar, bottom of viewer.
 */
import { ReactNode } from "react";

type Pos = "tl" | "tr" | "bl" | "br";

const POS_CLS: Record<Pos, string> = {
  tl: "top-3 left-3",
  tr: "top-3 right-3",
  bl: "bottom-3 left-3",
  br: "bottom-3 right-3",
};

export function HudCornerStat({
  pos = "tr",
  label,
  value,
  tone = "neutral",
}: {
  pos?: Pos;
  label: string;
  value: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "crit";
}) {
  const toneCls =
    tone === "ok" ? "text-threat-low border-threat-low/40"
    : tone === "warn" ? "text-threat-high border-threat-high/40"
    : tone === "crit" ? "text-threat-crit border-threat-crit/40 shadow-glow-crit"
    : "text-cyan border-cyan/30";
  return (
    <div className={`absolute ${POS_CLS[pos]} z-10 px-2 py-1 rounded font-mono text-2xs uppercase-wide tracking-wider bg-bg/70 backdrop-blur-sm border ${toneCls}`}>
      <span className="text-muted2 mr-1.5">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}

export function HudRecBadge({ label = "REC" }: { label?: string }) {
  return (
    <div className="absolute top-3 left-3 z-10 flex items-center gap-1.5 px-2 py-1 rounded font-mono text-2xs uppercase-wide tracking-[0.18em] bg-bg/70 backdrop-blur-sm border border-threat-crit/40 text-threat-crit">
      <span className="w-1.5 h-1.5 rounded-full bg-threat-crit animate-pulse-soft shadow-glow-crit" />
      {label}
    </div>
  );
}

export function HudCrosshair({ size = 80 }: { size?: number }) {
  return (
    <div
      aria-hidden
      className="absolute pointer-events-none top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-0"
      style={{ width: size, height: size }}
    >
      <div className="absolute inset-0 rounded-full border border-accent/35 animate-spin-slow" />
      <div className="absolute inset-3 rounded-full border border-accent/25" />
      <span className="absolute top-1/2 left-0 right-0 h-px bg-accent/30" />
      <span className="absolute left-1/2 top-0 bottom-0 w-px bg-accent/30" />
      <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-accent rounded-full" />
    </div>
  );
}

/** Inline threat-meter bar — used inside HUD bottom strip. */
export function HudThreatBar({ value, label = "THREAT" }: { value: number; label?: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const tone = value >= 0.75 ? "bg-threat-crit" : value >= 0.55 ? "bg-threat-high" : value >= 0.35 ? "bg-threat-med" : "bg-threat-low";
  return (
    <div className="flex items-center gap-2 min-w-[180px]">
      <span className="text-muted2 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-panel2 overflow-hidden border border-border">
        <div className={`h-full ${tone} transition-all duration-mid`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums shrink-0">{(value * 100).toFixed(0)}%</span>
    </div>
  );
}
