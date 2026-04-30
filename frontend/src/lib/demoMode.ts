/**
 * demoMode — global flag that:
 *   • hides operator chrome (debug pills, dev-only links, internal IDs)
 *   • locks the splash + onboarding tour OFF (judges should land on the
 *     populated console immediately)
 *   • boosts animation drama on key elements
 *
 * Triggered via:
 *   1. URL flag — append ?demo=1 to any route (highest priority)
 *   2. localStorage — astra:demoMode=1 (persists across reloads)
 *   3. env — VITE_DEMO_MODE=true (compile-time default)
 *
 * Toggle from Sidebar or programmatically via setDemoMode().
 */

const KEY = "astra:demoMode";

function read(): boolean {
  // 1. URL override
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "1") return true;
    if (params.get("demo") === "0") return false;
  } catch { /* ignore */ }
  // 2. localStorage
  try {
    if (localStorage.getItem(KEY) === "1") return true;
    if (localStorage.getItem(KEY) === "0") return false;
  } catch { /* ignore */ }
  // 3. env
  return import.meta.env.VITE_DEMO_MODE === "true";
}

let _state = read();
const subs = new Set<(v: boolean) => void>();

export function isDemoMode(): boolean { return _state; }

export function setDemoMode(v: boolean): void {
  _state = v;
  try { localStorage.setItem(KEY, v ? "1" : "0"); } catch { /* ignore */ }
  for (const fn of subs) fn(v);
}

export function toggleDemoMode(): boolean {
  setDemoMode(!_state);
  return _state;
}

export function subscribeDemoMode(fn: (v: boolean) => void): () => void {
  subs.add(fn);
  return () => { subs.delete(fn); };
}

import { useEffect, useState } from "react";

export function useDemoMode(): [boolean, (v: boolean) => void] {
  const [v, setV] = useState<boolean>(() => isDemoMode());
  useEffect(() => subscribeDemoMode(setV), []);
  return [v, setDemoMode];
}
