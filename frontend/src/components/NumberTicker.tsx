/**
 * Count-up animated number. Used by HeroStat KPIs and any "big number"
 * display so values don't just snap into place.
 *
 * - Animates from current → new on each prop change (~300 ms ease-out).
 * - Tabular-nums styling assumed (parent .font-mono / .tabular-nums).
 * - Renders as a <span> so it can sit inline.
 */
import { useEffect, useRef, useState } from "react";

type Props = {
  value: number;
  decimals?: number;
  duration?: number; // ms
  className?: string;
};

export function NumberTicker({ value, decimals = 0, duration = 320, className = "" }: Props) {
  const [display, setDisplay] = useState<number>(value);
  const fromRef = useRef<number>(value);
  const startRef = useRef<number>(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    fromRef.current = display;
    startRef.current = performance.now();
    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    const tick = (t: number) => {
      const elapsed = t - startRef.current;
      const k = Math.min(1, elapsed / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - k, 3);
      const v = fromRef.current + (value - fromRef.current) * eased;
      setDisplay(v);
      if (k < 1) rafRef.current = requestAnimationFrame(tick);
      else { setDisplay(value); rafRef.current = null; }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration]);

  return (
    <span className={className}>
      {display.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}
    </span>
  );
}
