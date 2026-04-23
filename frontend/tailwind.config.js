/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
      },
      colors: {
        ink: { 950: "#0b1220", 900: "#111827", 700: "#374151" },
        accent: {
          DEFAULT: "#2563eb",
          700: "#1d4ed8",
          600: "#2563eb",
          500: "#3b82f6",
          200: "#bfdbfe",
          soft: "#dbeafe",
        },
        violet: { 600: "#7c3aed", soft: "#ede9fe" },
        teal: { 600: "#0d9488", soft: "#ccfbf1" },
        danger: { DEFAULT: "#dc2626", soft: "#fee2e2" },
        ok: { DEFAULT: "#059669", soft: "#d1fae5" },
      },
    },
  },
  plugins: [],
};
