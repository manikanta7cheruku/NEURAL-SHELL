/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      keyframes: {
        cardReveal: {
          '0%': {
            opacity: '0',
            transform: 'translateY(8px) scale(0.98)',
          },
          '100%': {
            opacity: '1',
            transform: 'translateY(0) scale(1)',
          },
        },
        formReveal: {
          '0%': {
            opacity: '0',
            transform: 'translateY(-6px) scale(0.99)',
            maxHeight: '0px',
          },
          '100%': {
            opacity: '1',
            transform: 'translateY(0) scale(1)',
            maxHeight: '2000px',
          },
        },
      },
    },
  },
  plugins: [],
}