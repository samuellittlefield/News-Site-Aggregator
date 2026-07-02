/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        serif: ["Georgia", "serif"],
      },
      // Polling-page "liquid glass" theme tokens (see docs/features/polling-page-glass-theme).
      // Additive only — no other page references these; the dark theme stays on the stock gray-* scale.
      colors: {
        glass: {
          base: "#e9e3f6",
          panel: "rgba(255,255,255,0.55)",
          "panel-nested": "rgba(255,255,255,0.4)",
          border: "rgba(255,255,255,0.8)",
          "border-soft": "rgba(255,255,255,0.7)",
        },
        ink: {
          DEFAULT: "#241f33",
          muted: "#544a6e",
        },
        poll: {
          red: "#a83c37",
          "red-bar": "#c0453f",
          blue: "#2d5390",
          "blue-bar": "#3763a8",
          positive: "#047857",
          amber: "#b45309",
          "amber-bg": "#fef3c7",
          "amber-border": "#fcd34d",
          purple: "#7e22ce",
          "purple-bar": "#9333ea",
          "purple-bg": "#f3e8ff",
        },
      },
    },
  },
  plugins: [],
};
