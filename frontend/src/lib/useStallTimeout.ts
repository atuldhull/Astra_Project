/**
 * useStallTimeout — flips `stalled` true if `loading` stays true past
 * `thresholdMs`. Use to surface a "this is taking longer than expected"
 * hint or to fall back from spinner to skeleton.
 *
 * Resets when `loading` flips false. No external deps.
 */
import { useEffect, useState } from "react";

export function useStallTimeout(loading: boolean, thresholdMs: number = 15_000): boolean {
  const [stalled, setStalled] = useState(false);
  useEffect(() => {
    if (!loading) {
      setStalled(false);
      return;
    }
    const t = window.setTimeout(() => setStalled(true), thresholdMs);
    return () => window.clearTimeout(t);
  }, [loading, thresholdMs]);
  return stalled;
}
