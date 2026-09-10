/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      colors: {
        reactor: {
          orange: '#FF5300',
          'orange-tint': '#FFA352',
          navy: '#122149',
          'deep-blue': '#293972',
          teal: '#27FFBE',
          slate: '#F4F6FA',
          stroke: '#D1D3E0',
          'illicit-red': '#B50004',
          'illicit-bg': '#FFE4DF',
        },
        brand: {
          blue: "var(--brand-blue)",
          hover: "var(--brand-hover)",
          light: "var(--brand-light)",
        },
        surface: {
          DEFAULT: "var(--surface-default)",
          50: "var(--surface-50)",
          100: "var(--surface-100)",
          200: "var(--surface-200)",
          300: "var(--surface-300)",
          400: "var(--surface-400)",
          500: "var(--surface-500)",
          600: "var(--surface-600)",
          700: "var(--surface-700)",
          800: "var(--surface-800)",
          900: "var(--surface-900)",
        },
        police: {
          950: '#020617',
          900: '#0f172a',
          850: '#151f33',
          800: '#1e293b',
          750: '#26354a',
          700: '#334155',
          600: '#475569',
          500: '#64748b',
          400: '#94a3b8',
          300: '#cbd5e1',
          200: '#e2e8f0',
          100: '#f1f5f9',
          50: '#f8fafc',
        }
      }
    },
  },
  plugins: [],
}
