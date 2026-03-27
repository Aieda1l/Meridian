/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#1E3A72',
        accent: '#5B8DEF',
        success: '#6DB88E',
        danger: '#E06C6C',
        surface: '#F5F7FA',
      },
    },
  },
  plugins: [],
};
