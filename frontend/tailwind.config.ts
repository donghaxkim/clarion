import type { Config } from "tailwindcss";
import { fontFamily } from "tailwindcss/defaultTheme";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#FAFAF8",
        surface: "#F5F5F0",
        "surface-raised": "#EFEFEA",
        border: "#E5E5E0",
        "border-bright": "#D4D4CE",
        ink: {
          DEFAULT: "#0A0A0A",
          400: "#262626",
          500: "#0A0A0A",
          600: "#171717",
        },
        gold: {
          DEFAULT: "#0A0A0A",
          400: "#262626",
          500: "#0A0A0A",
        },
        amber: {
          DEFAULT: "#737373",
          400: "#525252",
          500: "#737373",
        },
        indigo: {
          DEFAULT: "#525252",
          400: "#737373",
          500: "#525252",
        },
        success: {
          DEFAULT: "#4A7C59",
          muted: "rgba(74, 124, 89, 0.12)",
        },
        danger: "#A63D3D",
        "danger-muted": "rgba(166, 61, 61, 0.1)",
        "text-primary": "#0A0A0A",
        "text-secondary": "#525252",
        "text-muted": "#737373",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "DM Sans", ...fontFamily.sans],
        display: ["var(--font-display)", "Playfair Display", ...fontFamily.serif],
        mono: ["var(--font-mono)", "JetBrains Mono", "Fira Code", ...fontFamily.mono],
      },
      fontSize: {
        "display-2xl": ["4.5rem", { lineHeight: "1.1", letterSpacing: "-0.03em" }],
        "display-xl": ["3.75rem", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        "display-lg": ["3rem", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
        "display-md": ["2.25rem", { lineHeight: "1.2", letterSpacing: "-0.015em" }],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "mesh-amber":
          "radial-gradient(ellipse 80% 50% at 20% -20%, rgba(245,158,11,0.12) 0%, transparent 60%), radial-gradient(ellipse 60% 40% at 80% 110%, rgba(99,102,241,0.10) 0%, transparent 60%)",
      },
      boxShadow: {
        glass: "0 0 0 1px rgba(0,0,0,0.06), 0 4px 24px rgba(0,0,0,0.06)",
        "glass-amber": "0 0 0 1px rgba(0,0,0,0.08), 0 4px 24px rgba(0,0,0,0.08)",
        "glass-indigo": "0 0 0 1px rgba(0,0,0,0.06), 0 4px 24px rgba(0,0,0,0.06)",
        "glow-amber": "0 2px 12px rgba(0,0,0,0.08)",
        "glow-gold": "0 2px 12px rgba(0,0,0,0.08)",
        "glow-indigo": "0 2px 12px rgba(0,0,0,0.06)",
        "glow-danger": "0 2px 12px rgba(166,61,61,0.15)",
        "glass-gold": "0 0 0 1px rgba(0,0,0,0.08), 0 4px 24px rgba(0,0,0,0.08)",
      },
      keyframes: {
        grain: {
          "0%, 100%": { transform: "translate(0, 0)" },
          "10%": { transform: "translate(-2%, -3%)" },
          "20%": { transform: "translate(3%, 1%)" },
          "30%": { transform: "translate(-1%, 4%)" },
          "40%": { transform: "translate(2%, -2%)" },
          "50%": { transform: "translate(-3%, 1%)" },
          "60%": { transform: "translate(1%, 3%)" },
          "70%": { transform: "translate(-2%, -1%)" },
          "80%": { transform: "translate(3%, 2%)" },
          "90%": { transform: "translate(-1%, -3%)" },
        },
        flash: {
          "0%": { opacity: "0" },
          "30%": { opacity: "1" },
          "100%": { opacity: "0" },
        },
        "pulse-amber": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(0,0,0,0)" },
          "50%": { boxShadow: "0 0 0 3px rgba(0,0,0,0.12)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        "float-up": {
          from: { opacity: "0", transform: "translateY(16px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        grain: "grain 0.5s steps(1) infinite",
        flash: "flash 0.6s ease-out forwards",
        "pulse-amber": "pulse-amber 1.5s ease-in-out infinite",
        blink: "blink 1s step-end infinite",
        "float-up": "float-up 0.5s ease-out forwards",
      },
    },
  },
  plugins: [
    require("tailwindcss-animate"),
    require("@tailwindcss/typography"),
  ],
};

export default config;
