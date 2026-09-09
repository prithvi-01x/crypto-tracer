/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        police: {
          900: "#0b101b",
          800: "#131b2e",
          700: "#1d2844",
          600: "#2a3b63",
          500: "#3d538c",
        },
        cyber: {
          gold: "#f59e0b",
          blue: "#3b82f6",
          cyan: "#06b6d4",
          emerald: "#10b981",
          crimson: "#ef4444",
        }
      }
    },
  },
  plugins: [],
}
