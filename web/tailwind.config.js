/** @type {import('tailwindcss').Config} */
// Colours come from CSS variables defined in src/index.css (values from branding/theme.json).
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        surface: v("surface"),
        border: v("border"),
        ink: v("ink"),
        muted: v("muted"),
        primary: v("primary"),
        "primary-ink": v("primary-ink"),
        "on-primary": v("on-primary"),
        header: v("header"),
        accent: v("accent"),
        thermo: v("thermo"),
        structural: v("structural"),
        electrical: v("electrical"),
        asme: v("asme"),
        ok: v("ok"),
        warn: v("warn"),
        fail: v("fail"),
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      borderRadius: { xl: "0.75rem", "2xl": "1rem" },
    },
  },
  plugins: [],
};
