import type { Config } from "tailwindcss";

// Design system: Airlock Cybernetic Defense (from Stitch DESIGN.md)
const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surface layers
        "bg-base":     "#090D16",
        "bg-nav":      "#0D1320",
        "bg-card":     "#111827",
        "bg-elevated": "#172033",
        "border-base": "#263247",
        // Semantic accents
        "accent-blue": "#3B82F6",
        "accent-cyan": "#06B6D4",
        "ok":          "#22C55E",
        "warn":        "#F59E0B",
        "danger":      "#EF4444",
        "muted":       "#94A3B8",
        "text-base":   "#F8FAFC",
        "text-dim":    "#CBD5E1",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "4px",
        md: "4px",
        lg: "8px",
      },
    },
  },
  plugins: [],
};

export default config;
