/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      colors: {
        // Cores baseadas no IMESC
        primary: '#FF6B35',
        secondary: '#004E98',
        accent: '#F7931E',
        success: '#2E8B57',
        warning: '#FF4444',
        dark: '#1A1A1A',
        light: '#F8F9FA',
        // Tons para gradientes
        orange: {
          50: '#FEF7F0',
          100: '#FDEDE0',
          500: '#FF6B35',
          600: '#E55A2B',
        },
        blue: {
          50: '#EBF4FF',
          100: '#D6E9FF',
          500: '#004E98',
          600: '#003D7A',
        }
      },
      animation: {
        'fade-in': 'fadeIn 0.6s ease-out',
        'spin': 'spin 1s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': {
            opacity: '0',
            transform: 'translateY(20px)'
          },
          '100%': {
            opacity: '1',
            transform: 'translateY(0)'
          }
        }
      }
    },
  },
  plugins: [],
}
