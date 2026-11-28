import type { Config } from "tailwindcss";

// Warm, light reviewer workspace adapted from the supplied dashboard reference.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surface layers
        "bg-base":     "#F4F5F7",
        "bg-nav":      "#FFFFFF",
        "bg-card":     "#FFFFFF",
        "bg-elevated": "#FFF1ED",
        "border-base": "#E5E6E8",
        // Semantic accents
        "accent-blue":  "#EF492F",
        "accent-cyan":  "#E56828",
        "ok":          "#22C55E",
        "warn":        "#E56828",
        "danger":      "#EF492F",
        "muted":       "#52525B",
        "text-base":   "#191A1C",
        "text-dim":    "#52525B",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "6px",
        md: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
};

export default config;
