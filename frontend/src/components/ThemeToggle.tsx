/**
 * Theme toggle — three palettes via a CSS class on <html>:
 *   default  : dark slate + orange accent (R3 production)
 *   light    : muted day-mode for outdoor demos
 *   command  : NORAD green-on-black for the deep-cinematic mode
 *
 * Persisted in localStorage. Applied at mount + on toggle.
 */
import { useEffect, useState } from "react";
import { Moon, Sun, Crosshair } from "lucide-react";

const KEY = "astra:theme:v1";
type Theme = "dark" | "light" | "command";

function applyTheme(t: Theme) {
  document.documentElement.classList.remove("theme-dark", "theme-light", "theme-command");
  document.documentElement.classList.add(`theme-${t}`);
}

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<Theme>(() => {
    try { return (localStorage.getItem(KEY) as Theme) || "dark"; }
    catch { return "dark"; }
  });

  useEffect(() => {
    applyTheme(theme);
    try { localStorage.setItem(KEY, theme); } catch { /* noop */ }
  }, [theme]);

  const cycle = () => {
    setTheme((t) => (t === "dark" ? "command" : t === "command" ? "light" : "dark"));
  };

  const Icon = theme === "dark" ? Moon : theme === "command" ? Crosshair : Sun;
  const label = theme === "dark" ? "Dark" : theme === "command" ? "Cmd" : "Light";

  return (
    <button
      onClick={cycle}
      className={`flex items-center gap-1.5 rounded transition-fast text-2xs uppercase-wide font-mono tracking-wider ${
        compact ? "p-1.5 text-muted hover:text-text" : "px-2 py-1.5 border border-border bg-panel2 hover:bg-panel3 text-muted hover:text-text"
      }`}
      title={`Theme: ${label} (click to cycle)`}
    >
      <Icon size={12} />
      {!compact && label}
    </button>
  );
}
