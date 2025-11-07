/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./saas/templates/**/*.html",
    "./saas/static/**/*.js",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        gray: {
          950: '#0a0a0a',
          900: '#111111',
          850: '#1a1a1a',
          800: '#1f1f1f',
          750: '#2a2a2a',
          700: '#333333',
        }
      }
    }
  },
  plugins: [],
}
