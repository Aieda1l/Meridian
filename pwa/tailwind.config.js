/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Nunito Sans'", '-apple-system', 'BlinkMacSystemFont', "'Segoe UI'", 'Roboto', 'sans-serif'],
      },
      colors: {
        neo: {
          surface:    '#e6e7ee',
          'surface-d':'#D1D9E6',
          white:      '#ECF0F3',
          dark:       '#31344b',
          black:      '#262833',
          gray:       '#44476A',
          muted:      '#93a5be',
          border:     '#D1D9E6',
        },
        accent:   '#2D4CC8',
        success:  '#18634B',
        info:     '#0056B3',
        warning:  '#F0B400',
        danger:   '#A91E2C',
      },
      boxShadow: {
        'neo':       '6px 6px 12px #b8b9be, -6px -6px 12px #ffffff',
        'neo-sm':    '3px 3px 6px #b8b9be, -3px -3px 6px #ffffff',
        'neo-inset': 'inset 2px 2px 5px #b8b9be, inset -3px -3px 7px #ffffff',
        'neo-btn':   '3px 3px 6px #b8b9be, -3px -3px 6px #ffffff',
      },
      borderRadius: {
        'neo-sm': '0.55rem',
        'neo-md': '0.75rem',
        'neo-lg': '1rem',
        'neo-xl': '1.25rem',
      },
      borderColor: {
        light: '#D1D9E6',
      },
    },
  },
  plugins: [],
};
