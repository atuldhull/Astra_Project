import type { Config } from "tailwindcss";

/**
 * ASTRA R3 design system.
 *
 * Tokens duplicated from src/index.css :root vars so Tailwind can emit
 * utility classes (`bg-panel`, `text-threat-crit`, etc.) for them. If you
 * add a CSS var, add the matching Tailwind entry here too.
 *
 * Reference aesthetic: Palantir Gotham · Anduril Lattice · Bloomberg
 * Terminal — dense, mono-first, dark by default. We don't use whitespace
 * to "breathe"; data density IS the credibility signal for defence judges.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surface stack
        bg:       "var(--bg)",
        "bg-elev": "var(--bg-elev)",
        panel:    "var(--panel)",
        panel2:   "var(--panel-2)",
        panel3:   "var(--panel-3)",
        border:   "var(--border)",
        border2:  "var(--border-2)",

        // Type
        text:     "var(--text)",
        muted:    "var(--muted)",
        muted2:   "var(--muted-2)",

        // Brand & accents
        accent:   "var(--accent)",
        accent2:  "var(--accent-2)",
        cyan:     "var(--cyan)",
        violet:   "var(--violet)",

        // Threat semantic levels
        threat: {
          low:  "var(--threat-low)",
          med:  "var(--threat-med)",
          high: "var(--threat-high)",
          crit: "var(--threat-crit)",
        },
        // Status pills
        status: {
          ok:   "var(--status-ok)",
          warn: "var(--status-warn)",
          err:  "var(--status-err)",
        },
      },
      fontFamily: {
        // Inter = display/body; JetBrains Mono = numbers / measurements / codepaths
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "ui-monospace", "monospace"],
      },
      fontSize: {
        // Tighter scale than Tailwind's default — defence dashboards stay small
        "2xs":  ["10px", { lineHeight: "14px" }],
        "xs":   ["11px", { lineHeight: "15px" }],
        "sm":   ["12px", { lineHeight: "17px" }],
        "base": ["14px", { lineHeight: "20px" }],
        "lg":   ["16px", { lineHeight: "22px" }],
        "xl":   ["18px", { lineHeight: "24px" }],
        "2xl":  ["22px", { lineHeight: "28px" }],
        "3xl":  ["28px", { lineHeight: "34px" }],
        "4xl":  ["36px", { lineHeight: "42px" }],
        "5xl":  ["48px", { lineHeight: "54px" }],
      },
      borderRadius: {
        sm: "var(--r-sm)",
        md: "var(--r-md)",
        lg: "var(--r-lg)",
        xl: "var(--r-xl)",
      },
      transitionTimingFunction: {
        "out-soft": "cubic-bezier(0.16, 1, 0.3, 1)",
        "in-out-soft": "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      transitionDuration: {
        fast: "150ms",
        mid:  "220ms",
        slow: "360ms",
      },
      boxShadow: {
        "glow-accent": "0 0 12px 0 var(--accent-glow)",
        "glow-cyan":   "0 0 12px 0 var(--cyan-glow)",
        "glow-low":    "0 0 10px 0 var(--threat-low-glow)",
        "glow-crit":   "0 0 14px 0 var(--threat-crit-glow)",
        "panel":       "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 16px -8px rgba(0,0,0,0.5)",
        "panel-strong": "0 8px 24px -8px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.03) inset",
      },
      backdropBlur: {
        xs: "2px",
        sm: "4px",
        md: "8px",
        lg: "16px",
        xl: "24px",
      },
      animation: {
        "pulse-soft":  "pulse-soft 2s ease-in-out infinite",
        "pulse-glow":  "pulse-glow 1.4s ease-in-out infinite",
        "blink-dot":   "blink-dot 1.6s linear infinite",
        "pin-pop":     "pin-pop 600ms cubic-bezier(0.16, 1, 0.3, 1)",
        "spin-slow":   "spin-slow 8s linear infinite",
        "count-flash": "count-flash 700ms cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
} satisfies Config;
