import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: 'class',
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--bg-surface)",
        elevated: "var(--bg-elevated)",
        accent: "var(--accent)",
        "accent-light": "var(--accent-light)",
      },
      fontFamily: {
        sans: ["DM Sans", "sans-serif"],
        serif: ["Newsreader", "serif"],
        mono: ["DM Mono", "monospace"],
      },
      boxShadow: {
        sm: "0 1px 2px rgba(0,0,0,0.04)",
        DEFAULT: "0 1px 2px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
