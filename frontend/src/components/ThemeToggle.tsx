/**
 * Theme toggle — two palettes via a CSS class on <html>:
 *   dark    : slate + orange accent (R3 production default)
 *   command : NORAD green-on-black for the deep-cinematic mode
 *
 * Light theme was removed in v3.0 — it failed contrast audit on key
 * defence-genre chrome (corner brackets, telemetry strips, scan lines)
 * and shipping it half-broken hurt more than skipping it. If you had
 * `astra:theme:v1=light` saved, you'll be migrated to dark on next
 * mount.
 *
 * Persisted in localStorage. Applied at mount + on toggle.
 */
import { useEffect, useState } from "react";
import { Moon, Crosshair } from "lucide-react";

const KEY = "astra:theme:v1";
type Theme = "dark" | "command";

function applyTheme(t: Theme) {
  document.documentElement.classList.remove("theme-dark", "theme-light", "theme-command");
  document.documentElement.classList.add(`theme-${t}`);
}

function readPersistedTheme(): Theme {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw === "command") return "command";
    // anything else (dark, light, null) → dark
    return "dark";
  } catch {
    return "dark";
  }
}

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<Theme>(readPersistedTheme);

  useEffect(() => {
    applyTheme(theme);
    try { localStorage.setItem(KEY, theme); } catch { /* noop */ }
  }, [theme]);

  const cycle = () => {
    setTheme((t) => (t === "dark" ? "command" : "dark"));
  };

  const Icon = theme === "dark" ? Moon : Crosshair;
  const label = theme === "dark" ? "Dark" : "Cmd";

  return (
    <button
      onClick={cycle}
      className={`flex items-center gap-1.5 rounded transition-fast text-2xs uppercase-wide font-mono tracking-wider ${
        compact ? "p-1.5 text-muted hover:text-text" : "px-2 py-1.5 border border-border bg-panel2 hover:bg-panel3 text-muted hover:text-text"
      }`}
      title={`Theme: ${label} (click to swap)`}
    >
      <Icon size={12} />
      {!compact && label}
    </button>
  );
}
