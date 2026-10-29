/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Marquee palette (R40 — mirrors the canvas palette file).
        navy: "#0d1b2a",
        navy2: "#1b263b",
        gold: "#ffcc33",
        carpet: "#c1121f",
        spotlight: "#fff5d6",
      },
      fontFamily: {
        pixel: ['"Press Start 2P"', "monospace"],
      },
    },
  },
  plugins: [],
};
