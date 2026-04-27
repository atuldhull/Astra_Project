/**
 * Hero-stat KPI card — the "big number" shown at the top of every page.
 *
 * Defence dashboards put the punch numbers above the fold. This is that
 * card — title, value (with optional NumberTicker animation), optional
 * sub-label and trend indicator.
 *
 * Use in a 4-column grid at the top of each page.
 */
import { ReactNode } from "react";
import { NumberTicker } from "./NumberTicker";
import { LucideIcon, TrendingUp, TrendingDown, Minus } from "lucide-react";

type Trend = "up" | "down" | "flat" | null;

type Props = {
  label: string;
  value: number | string;
  unit?: string;
  /** If `value` is a number, animate count-up. Set false to render instantly. */
  ticker?: boolean;
  /** Decimal places for ticker (only when value is a number) */
  decimals?: number;
  /** Optional small label below the value (e.g. "since last sync") */
  sub?: string;
  /** Trend arrow shown next to the value */
  trend?: Trend;
  /** Optional left-aligned icon */
  icon?: LucideIcon;
  /** Color for the trend icon AND the top accent bar */
  tone?: "neutral" | "low" | "med" | "high" | "crit" | "cyan";
  children?: ReactNode;
};

const TONE_CLASS: Record<NonNullable<Props["tone"]>, string> = {
  neutral: "text-muted",
  low:     "text-threat-low",
  med:     "text-threat-med",
  high:    "text-threat-high",
  crit:    "text-threat-crit",
  cyan:    "text-cyan",
};

export function HeroStat({
  label, value, unit, ticker = true, decimals = 0, sub, trend, icon: Icon, tone = "neutral", children,
}: Props) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : trend === "flat" ? Minus : null;
  const trendCls = trend === "up" ? "text-threat-low" : trend === "down" ? "text-threat-crit" : "text-muted";

  return (
    <div className="hero-stat">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-2xs uppercase-wide text-muted2 font-mono tracking-wider">{label}</span>
        {Icon && <Icon size={12} className={TONE_CLASS[tone]} />}
      </div>
      <div className="flex items-baseline gap-2">
        <div className={`text-2xl font-mono text-display tabular-nums ${TONE_CLASS[tone]}`}>
          {typeof value === "number" && ticker ? (
            <NumberTicker value={value} decimals={decimals} />
          ) : (
            value
          )}
        </div>
        {unit && <span className="text-xs text-muted">{unit}</span>}
        {TrendIcon && <TrendIcon size={11} className={`ml-auto ${trendCls}`} />}
      </div>
      {sub && <div className="text-2xs text-muted mt-1 font-mono">{sub}</div>}
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}
