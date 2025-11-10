
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          500: '#00c2ff',
          600: '#0094ff',
          700: '#005bff'
        }
      }
    }
  },
  plugins: []
}
