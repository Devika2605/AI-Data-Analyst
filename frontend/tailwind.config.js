/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#dbeafe',
          500: '#3b6fe0',
          600: '#2f56c9',
          700: '#2645a3',
        },
        surface: {
          DEFAULT: '#ffffff',
          muted: '#f7f8fa',
        },
        ink: {
          900: '#111318',
          700: '#3a3f4b',
          500: '#6b7280',
          300: '#d1d5db',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.06), 0 1px 3px rgba(16, 24, 40, 0.08)',
      },
    },
  },
  plugins: [],
}
