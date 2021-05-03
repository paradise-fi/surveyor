module.exports = {
  purge: ['./src/**/*.{js,jsx,ts,tsx}', './public/index.html'],
  darkMode: false, // or 'media' or 'class'
  theme: {
    fontFamily: {
      'sans': ['Lato', 'Arial', 'sans-serif'],
    },
    extend: {},
  },
  variants: {
    backgroundColor: ({ after }) => after(['disabled']),
    cursor: ({ after }) => after(['disabled']),
    extend: {},
  },
  plugins: [
    require('@tailwindcss/forms')
  ],
}
