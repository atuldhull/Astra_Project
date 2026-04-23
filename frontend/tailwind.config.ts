import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0f14",
        panel: "#121821",
        panel2: "#1a222d",
        border: "#23303d",
        text: "#e5edf4",
        muted: "#8b9aad",
        accent: "#ff7a1a",
        threat: {
          low: "#4ade80",
          med: "#facc15",
          high: "#fb923c",
          crit: "#ef4444",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Consolas", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
