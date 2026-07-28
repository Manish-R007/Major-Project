/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        canopy: {
          950: '#101F19',
          900: '#17332A',
          800: '#1F4438',
          700: '#2C5A49',
          600: '#3E6C55',
          400: '#6E9C7D',
          200: '#B7CFBC',
        },
        parchment: {
          100: '#F7F2E7',
          200: '#EFE7D8',
          300: '#E4D9C2',
        },
        ochre: {
          600: '#A66C1F',
          500: '#C98A2B',
          400: '#DDA84F',
        },
        rust: {
          600: '#8C3B2E',
          500: '#A64B3A',
        },
        ink: '#1B211C',
      },
      fontFamily: {
        display: ['"Fraunces"', 'serif'],
        body: ['"Work Sans"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      backgroundImage: {
        contour: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'%3E%3Cg fill='none' stroke='%23000000' stroke-opacity='0.04' stroke-width='1'%3E%3Cpath d='M0 80 Q100 40 200 80 T400 80'/%3E%3Cpath d='M0 140 Q100 100 200 140 T400 140'/%3E%3Cpath d='M0 200 Q100 160 200 200 T400 200'/%3E%3Cpath d='M0 260 Q100 220 200 260 T400 260'/%3E%3Cpath d='M0 320 Q100 280 200 320 T400 320'/%3E%3C/g%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [],
}
